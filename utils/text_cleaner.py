"""Text cleanup for PDF extraction and LLM output."""
from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "­": "", "​": ""}


def normalise_pdf_text(text: str) -> str:
    """Tidy raw PDF text: ligatures, hyphenated line breaks, stray whitespace."""
    for bad, good in _LIGATURES.items():
        text = text.replace(bad, good)
    text = unicodedata.normalize("NFKC", text).replace("�", "-")  # lost bullet / dash glyphs
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join hyphenated words
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_llm_output(text: str) -> str:
    """Strip markdown artefacts (bold, headings, bullets) from LLM text."""
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"(?<!\w)_{2}(.*?)_{2}(?!\w)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-•*]\s+", "  ", text, flags=re.MULTILINE)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.replace("*", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_source_line(text: str) -> str:
    """Lighter clean for verbatim extract lines: keep dashes used for dialogue."""
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text).replace("*", "")
    return re.sub(r"^#{1,6}\s*", "", text).strip()


def clean_model(model: BaseModel, skip: frozenset[str] = frozenset()) -> BaseModel:
    """Recursively apply clean_llm_output to every string field of a model."""

    def _clean(value, key: str = ""):
        if key in skip:
            return value
        if isinstance(value, str):
            return clean_llm_output(value)
        if isinstance(value, list):
            return [_clean(v) for v in value]
        if isinstance(value, BaseModel):
            return clean_model(value, skip)
        return value

    return model.model_copy(update={k: _clean(getattr(model, k), k) for k in type(model).model_fields})


_WORD = re.compile(r"[a-z0-9']+")
STOPWORDS = frozenset(
    "a an the and or but of to in on at for with by from as is are was were be been it its this that these those "
    "you your their they he she his her we our i my me which what how why who whom when where do does did not no "
    "so if then than there here into about over can could would should will may might must has have had more most "
    "lines line source text writer write question words".split()
)


def content_words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in STOPWORDS and len(w) > 2]


def question_lines(text: str) -> list[tuple[bool, str]]:
    """Split question text into (is_bullet, line). Lines after one ending in ':' are bullet prompts."""
    out: list[tuple[bool, str]] = []
    bullets = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            bullets = False
            continue
        out.append((bullets, line))
        if line.endswith(":"):
            bullets = True
    return out
