"""Persistence for generated exams, mark schemes, reviews and attempts.

Plain JSON files for the demo. The platform integration replaces this module
with database access (e.g. Supabase tables ``exams``, ``mark_schemes``,
``attempts``) behind the same functions; the Pydantic models are the row shapes.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from pydantic import BaseModel

from config import settings
from core.schemas import Exam, GradingResult, MarkScheme


class ExamRecord(BaseModel):
    exam: Exam
    mark_scheme: MarkScheme | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(exam: Exam, scheme: MarkScheme | None) -> None:
    settings.EXAMS_DIR.mkdir(parents=True, exist_ok=True)
    record = ExamRecord(exam=exam, mark_scheme=scheme)
    (settings.EXAMS_DIR / f"{exam.exam_id}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")


def load(exam_id: str) -> ExamRecord | None:
    try:
        return ExamRecord.model_validate_json((settings.EXAMS_DIR / f"{exam_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_records(subject: str | None = None, status: str | None = None) -> list[ExamRecord]:
    records = []
    for path in settings.EXAMS_DIR.glob("*.json") if settings.EXAMS_DIR.exists() else []:
        try:
            rec = ExamRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if (subject is None or rec.exam.config.subject == subject) and (status is None or rec.exam.status == status):
            records.append(rec)
    return sorted(records, key=lambda r: r.exam.created_at, reverse=True)


def set_status(exam_id: str, status: str, note: str = "", flagged: list[int] | None = None) -> ExamRecord | None:
    rec = load(exam_id)
    if rec is None:
        return None
    rec.exam.status = status
    if status != "approved":
        set_pin(rec.exam, False)
    rec.exam.reviewer_note = note
    rec.exam.reviewed_at = _now()
    if flagged is not None:
        rec.exam.flagged_questions = flagged
    save(rec.exam, rec.mark_scheme)
    return rec


def update_question_text(exam_id: str, number: int, text: str) -> None:
    rec = load(exam_id)
    q = rec.exam.question(number) if rec else None
    if q is not None:
        q.question_text = text
        save(rec.exam, rec.mark_scheme)


def delete(exam_id: str) -> None:
    (settings.EXAMS_DIR / f"{exam_id}.json").unlink(missing_ok=True)


def approved_subjects() -> list[str]:
    return sorted({r.exam.config.subject for r in list_records(status="approved")})


def _format_key(exam: Exam) -> tuple[str, str, str, int]:
    c = exam.config
    return (c.paper_key, c.section, c.difficulty, c.num_questions)


def approved_formats(subject: str) -> list[tuple[str, str, str, int]]:
    """Distinct (paper_key, section, difficulty, num_questions) that have at least one approved paper."""
    return sorted({_format_key(r.exam) for r in list_records(subject, "approved")})


def pin_key(exam: Exam) -> str:
    return "|".join(map(str, _format_key(exam)))


def get_pins() -> dict[str, str]:
    """Teacher-pinned paper per format: {format key: exam_id}. Pinned papers are served to every student."""
    try:
        return json.loads(settings.PINS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_pin(exam: Exam, pinned: bool) -> None:
    pins = get_pins()
    if pinned:
        pins[pin_key(exam)] = exam.exam_id
    elif pins.get(pin_key(exam)) == exam.exam_id:
        del pins[pin_key(exam)]
    settings.PINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings.PINS_FILE.write_text(json.dumps(pins, indent=2), encoding="utf-8")


def is_pinned(exam: Exam) -> bool:
    return get_pins().get(pin_key(exam)) == exam.exam_id


def pick_approved(
    subject: str, fmt: tuple[str, str, str, int], exclude: set[str] = frozenset()
) -> ExamRecord | None:
    """The pinned paper if the teacher pinned one, else a random approved paper (preferring unseen ones)."""
    pool = [r for r in list_records(subject, "approved") if _format_key(r.exam) == fmt and r.mark_scheme]
    pinned_id = get_pins().get("|".join(map(str, fmt)))
    pinned = next((r for r in pool if r.exam.exam_id == pinned_id), None)
    if pinned:
        return pinned
    fresh = [r for r in pool if r.exam.exam_id not in exclude]
    choices = fresh or pool
    return random.choice(choices) if choices else None


def save_attempt(result: GradingResult) -> None:
    settings.ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
    (settings.ATTEMPTS_DIR / f"{result.attempt_id}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
