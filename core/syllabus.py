"""Syllabus scope: the human-approved list of topics exams may assess.

The model proposes topics from the uploaded reference material; a teacher edits
and approves them. Generation is refused until a syllabus is approved, and every
generated question must map to one of the approved topics.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from config import prompts, settings
from config.llm import LLMProvider
from core.schemas import Syllabus, SyllabusDraft
from core.vector_store import VectorStore


class SyllabusNotApprovedError(Exception):
    """Generation requested for a subject whose syllabus topics have not been approved."""


def _path(subject: str):
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-") or "subject"
    return settings.SYLLABUS_DIR / f"{slug}.json"


def load(subject: str) -> Syllabus | None:
    try:
        return Syllabus.model_validate_json(_path(subject).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(subject: str, topics: list[str], approved: bool) -> Syllabus:
    clean = list(dict.fromkeys(t.strip() for t in topics if t.strip()))
    syllabus = Syllabus(
        subject=subject, topics=clean, approved=approved and bool(clean),
        updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    settings.SYLLABUS_DIR.mkdir(parents=True, exist_ok=True)
    _path(subject).write_text(syllabus.model_dump_json(indent=2), encoding="utf-8")
    return syllabus


def approved_topics(subject: str) -> list[str]:
    syllabus = load(subject)
    if syllabus is None or not syllabus.approved:
        raise SyllabusNotApprovedError(
            f"The syllabus topics for {subject} have not been approved yet. "
            "A teacher must review and approve them in the Teacher Panel first."
        )
    return syllabus.topics


def propose_topics(subject: str, store: VectorStore, llm: LLMProvider) -> Syllabus:
    """Ask the model for candidate topics. Saved as an UNAPPROVED draft for the teacher to review."""
    material = "\n\n".join(store.reference_texts(subject))[: settings.SYLLABUS_MAX_CHARS]
    draft = llm.generate_json(
        prompts.SYLLABUS_SYSTEM, prompts.SYLLABUS_PROMPT.format(subject=subject, material=material),
        SyllabusDraft, temperature=settings.GRADING_TEMPERATURE,
    )
    return save(subject, draft.topics, approved=False)
