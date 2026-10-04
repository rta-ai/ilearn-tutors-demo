"""PDF upload handling: text extraction and chunking."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from config import settings
from config.llm import LLMError, LLMProvider, RateLimitError
from utils.text_cleaner import normalise_pdf_text


log = logging.getLogger(__name__)


class DocumentError(Exception):
    """User-presentable document problem."""


@dataclass
class Chunk:
    chunk_id: str
    text: str
    page: int


@dataclass
class ProcessedDocument:
    doc_id: str
    filename: str
    subject: str
    pages: int
    chunks: list[Chunk]


_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
)


def document_id(data: bytes) -> str:
    """Content hash, so re-uploading the same file is detected."""
    return hashlib.sha256(data).hexdigest()[:16]


def _page_images(page) -> list[tuple[bytes, str]]:
    """Usable images on a page as (bytes, mime). Tiny logos/icons are skipped."""
    out = []
    for im in page.images:
        try:
            pil = im.image
            if min(pil.size) < settings.MIN_OCR_IMAGE_PX:
                continue
            if im.name.lower().endswith((".png", ".jpg", ".jpeg")):
                out.append((im.data, "image/png" if im.name.lower().endswith(".png") else "image/jpeg"))
            else:  # JPX, TIFF, etc.: convert to PNG for the model
                buf = io.BytesIO()
                pil.convert("RGB").save(buf, "PNG")
                out.append((buf.getvalue(), "image/png"))
        except Exception:  # noqa: BLE001 - an undecodable image should not fail the whole upload
            continue
    return out


def _cache_path(doc_id: str):
    return settings.OCR_CACHE_DIR / f"{doc_id}.json"


def _load_cache(doc_id: str) -> dict[int, str]:
    try:
        return {int(k): v for k, v in json.loads(_cache_path(doc_id).read_text(encoding="utf-8")).items()}
    except (OSError, ValueError):
        return {}


def _save_cache(doc_id: str, cache: dict[int, str]) -> None:
    try:
        settings.OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(doc_id).write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        log.warning("Could not write OCR cache")


def _ocr_pages(doc_id, scanned, llm: LLMProvider, say) -> dict[int, str]:
    """Transcribe image-only pages. Cached per page; failed batches fall back to single pages."""
    cache = _load_cache(doc_id)
    todo = [item for item in scanned if item[0] not in cache]
    if len(todo) < len(scanned):
        say(f"Reusing {len(scanned) - len(todo)} previously read pages.")
    step = settings.OCR_PAGES_PER_CALL
    failed: list[int] = []
    for start in range(0, len(todo), step):
        batch = todo[start : start + step]
        say(f"Reading scanned pages {batch[0][0]}-{batch[-1][0]} ({start + len(batch)}/{len(todo)})...")
        try:
            got = llm.transcribe_pages(batch)
        except RateLimitError:
            raise
        except LLMError:
            got = {}
            for item in batch:  # retry one page at a time so one bad page cannot sink the batch
                try:
                    got.update(llm.transcribe_pages([item]))
                except RateLimitError:
                    raise
                except LLMError:
                    failed.append(item[0])
        for page_no, text in got.items():
            cache[page_no] = normalise_pdf_text(text)
        _save_cache(doc_id, cache)  # keep progress even if a later batch fails
    if failed:
        say(f"Could not read pages {', '.join(map(str, failed))}; they were skipped.")
    return {n: t for n, t in cache.items() if len(t) >= settings.MIN_PAGE_TEXT_CHARS}


def extract_pages(
    data: bytes, llm: LLMProvider | None = None, progress: Callable[[str], None] | None = None
) -> list[tuple[int, str]]:
    """Return (page_number, text) for every page.

    Pages with real text use it directly. Image-only pages (screenshots, scans)
    are transcribed with the LLM's vision when ``llm`` is given.
    """
    say = progress or (lambda _msg: None)
    doc_id = document_id(data)
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        texts: dict[int, str] = {}
        scanned: list[tuple[int, list[tuple[bytes, str]]]] = []
        for i, page in enumerate(reader.pages, start=1):
            text = normalise_pdf_text(page.extract_text() or "")
            if len(text) >= settings.MIN_PAGE_TEXT_CHARS:
                texts[i] = text
            elif llm is not None and (images := _page_images(page)):
                scanned.append((i, images))
    except (PdfReadError, ValueError, KeyError) as err:
        raise DocumentError(f"Could not read this PDF ({err}).") from err

    if scanned and llm is not None:
        texts.update(_ocr_pages(doc_id, scanned, llm, say))

    if not texts:
        raise DocumentError("No readable text was found in this PDF.")
    return sorted(texts.items())


def chunk_pages(doc_id: str, pages: list[tuple[int, str]]) -> list[Chunk]:
    """Split page by page so every chunk keeps an accurate page number."""
    chunks: list[Chunk] = []
    for page_no, text in pages:
        for piece in _splitter.split_text(text):
            piece = piece.strip()
            if len(piece) < settings.MIN_CHUNK_CHARS or not re.search(r"[A-Za-z]{3}", piece):
                continue
            chunks.append(Chunk(chunk_id=f"{doc_id}-{len(chunks)}", text=piece, page=page_no))
    return chunks


def process_pdf(
    data: bytes, filename: str, subject: str, llm: LLMProvider | None = None,
    progress: Callable[[str], None] | None = None,
) -> ProcessedDocument:
    doc_id = document_id(data)
    pages = extract_pages(data, llm, progress)
    chunks = chunk_pages(doc_id, pages)
    if not chunks:
        raise DocumentError("The PDF contained too little text to use.")
    return ProcessedDocument(doc_id=doc_id, filename=filename, subject=subject, pages=pages[-1][0], chunks=chunks)
