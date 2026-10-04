"""LLM provider abstraction.

The rest of the app only talks to :class:`LLMProvider`. All Gemini-specific code
is in :class:`GeminiProvider`; to move to another model, implement the same
three methods and register it in :func:`get_llm`.
"""
from __future__ import annotations

import logging
import re
import time

import httpx
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from config import settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """User-presentable error. ``str(err)`` is safe to show in the UI."""


class RateLimitError(LLMError):
    pass


class DailyQuotaError(RateLimitError):
    """The free-tier daily quota for a model is used up; retrying will not help."""


class LLMProvider(ABC):
    @abstractmethod
    def generate_json(self, system: str, prompt: str, schema: type[T], temperature: float | None = None) -> T:
        """Return a validated instance of ``schema`` generated from the prompt."""

    @abstractmethod
    def transcribe_pages(self, pages: list[tuple[int, list[tuple[bytes, str]]]]) -> dict[int, str]:
        """OCR: map page number -> transcribed text. Each page is a list of (image bytes, mime type)."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        ...


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        if not api_key:
            raise LLMError("GOOGLE_API_KEY is not set. Add it to .env (local) or the Space secrets (Hugging Face).")
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=settings.REQUEST_TIMEOUT_SECONDS * 1000),
        )

    # -- generation --------------------------------------------------------
    def generate_json(self, system: str, prompt: str, schema: type[T], temperature: float | None = None) -> T:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=settings.TEMPERATURE if temperature is None else temperature,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=types.ThinkingConfig(thinking_budget=settings.THINKING_BUDGET),
        )
        last_error: Exception | None = None
        # One extra attempt covers a malformed/truncated JSON response.
        for attempt in range(2):
            response = self._call(
                lambda: self._client.models.generate_content(
                    model=settings.GENERATION_MODEL, contents=prompt, config=config
                )
            )
            text = response.text or ""
            try:
                return schema.model_validate_json(text)
            except ValidationError as err:
                last_error = err
                log.warning("Invalid JSON from model (attempt %d): %s", attempt + 1, err)
        raise LLMError("The AI returned an incomplete response. Please try again.") from last_error

    def transcribe_pages(self, pages: list[tuple[int, list[tuple[bytes, str]]]]) -> dict[int, str]:
        from google.genai import types

        from core.schemas import OcrDraft

        parts: list = [
            "Transcribe every page below exactly as written, in reading order, as plain text. Include headings, "
            "boxed text, bullet points, quoted extracts and handwritten-style sample answers. Do not summarise, "
            "correct or add anything. Skip purely decorative graphics. Return one entry per page using the page "
            "number given."
        ]
        for number, images in pages:
            parts.append(f"PAGE {number}:")
            parts.extend(types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images)
        config = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            response_schema=OcrDraft,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        for attempt in range(2):  # the model occasionally returns an empty body
            response = self._call(
                lambda: self._client.models.generate_content(
                    model=settings.OCR_MODEL, contents=parts, config=config
                )
            )
            try:
                return {p.page: p.text for p in OcrDraft.model_validate_json(response.text or "").pages}
            except ValidationError:
                log.warning("Invalid OCR response (attempt %d)", attempt + 1)
        raise LLMError("Could not read the scanned pages of this PDF.")

    # -- embeddings --------------------------------------------------------
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), settings.EMBED_BATCH_SIZE):
            batch = texts[start : start + settings.EMBED_BATCH_SIZE]
            vectors.extend(self._embed(batch, "RETRIEVAL_DOCUMENT"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        from google.genai import types

        response = self._call(
            lambda: self._client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=settings.EMBEDDING_DIMENSIONS
                ),
            )
        )
        return [list(e.values) for e in response.embeddings]

    # -- error handling ----------------------------------------------------
    def _call(self, fn):
        from google.genai import errors

        for attempt in range(settings.MAX_RETRIES + 1):
            try:
                return fn()
            except (httpx.TimeoutException, httpx.TransportError) as err:
                if attempt >= 1:  # one retry only: each attempt can take up to the full timeout
                    raise LLMError("The AI service took too long to respond. Please try again.") from err
                log.warning("Gemini request timed out or dropped (%s), retrying", type(err).__name__)
            except errors.APIError as err:
                if err.code == 429 and "PerDay" in str(err):
                    raise _friendly(err) from err
                retryable = err.code in (429, 500, 502, 503, 504)
                if not retryable or attempt == settings.MAX_RETRIES:
                    raise _friendly(err) from err
                delay = settings.RETRY_BASE_DELAY_SECONDS * (2**attempt)
                log.warning("Gemini %s, retrying in %.0fs", err.code, delay)
                time.sleep(delay)
        raise AssertionError("unreachable")


def _friendly(err) -> LLMError:
    code = getattr(err, "code", None)
    if code == 429 and "PerDay" in str(err):
        model = re.search(r"model: ([\w.-]+)", str(err))
        return DailyQuotaError(
            f"Daily free-tier quota used up for model {model.group(1) if model else 'in use'}. "
            "Enable billing on the Google AI project or switch GENERATION_MODEL / OCR_MODEL to another model."
        )
    if code == 429:
        return RateLimitError(
            "The AI service is busy (free-tier rate limit reached). Please wait about a minute and try again."
        )
    if code in (401, 403):
        return LLMError("The AI service rejected the API key. Check GOOGLE_API_KEY.")
    if code == 404:
        return LLMError(f"Model not found. Check GENERATION_MODEL / EMBEDDING_MODEL in settings ({err}).")
    if code and code >= 500:
        return LLMError("The AI service is temporarily unavailable. Please try again shortly.")
    return LLMError(f"The AI service returned an error: {getattr(err, 'message', err)}")


def get_llm() -> LLMProvider:
    if settings.LLM_PROVIDER == "gemini":
        return GeminiProvider(settings.GOOGLE_API_KEY)
    raise LLMError(f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'.")
