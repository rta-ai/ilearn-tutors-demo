"""The demo paper pool: hand-authored papers, seeding and export.

Papers are written offline (by Claude, not by a live LLM call) as JSON in
``demo_pool/authored/``, then built into exam records in ``demo_pool/exams/``
with ``tools/build_pool.py``. On app start the records are copied into the
runtime store, so the demo needs no document upload, OCR or generation.

Human in the loop: built papers are drafts. A teacher reviews and approves them
in the Teacher Panel, then "Save to demo pool" writes the approval back here so
it survives restarts (Hugging Face storage is ephemeral).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from pydantic import BaseModel

from config import exam_specs, settings
from core import exam_store, rubrics
from core.schemas import (
    Exam, ExamConfig, MarkScheme, MarkSchemeItem, Question, QuestionType, SourceExtract,
)
from utils.validators import validate_exam

POOL_DIR = settings.BASE_DIR / "demo_pool"
AUTHORED_DIR = POOL_DIR / "authored"
EXAMS_DIR = POOL_DIR / "exams"
SYLLABUS_DIR = POOL_DIR / "syllabus"
PINS_FILE = POOL_DIR / "pins.json"

AUTHORED_MODEL = "authored-by-claude"
AUTHORED_PROMPT_VERSION = "authored-2026-10-05"


class AuthoredSource(BaseModel):
    label: str
    title: str
    lines: list[str]


class AuthoredQuestion(BaseModel):
    number: int
    text: str
    options: list[str] = []
    topic: str
    correct_options: list[str] = []
    model_answer: str
    acceptable: list[str] = []
    notes: str = ""


class AuthoredPaper(BaseModel):
    slug: str  # stable id, e.g. "p1-ferry"
    paper_key: str
    difficulty: str = "Higher"
    instructions: list[str]
    sources: list[AuthoredSource]
    questions: list[AuthoredQuestion]


def build(paper: AuthoredPaper, topics: list[str], reference_text: str = "") -> tuple[Exam, MarkScheme]:
    """Turn an authored paper into an Exam + MarkScheme, using the official structure and validating it."""
    spec = exam_specs.PAPER_SPECS[paper.paper_key]
    plan = {q.number: q for q in spec.questions_for(exam_specs.FULL_PAPER)}
    by_number = {q.number: q for q in paper.questions}
    missing = set(plan) - set(by_number)
    if missing:
        raise ValueError(f"{paper.slug}: missing questions {sorted(missing)}")

    config = ExamConfig(
        subject=spec.subject, paper_key=paper.paper_key, section=exam_specs.FULL_PAPER, difficulty=paper.difficulty,
    )
    questions = [
        Question(
            number=n, section=p.section, question_type=QuestionType(p.qtype), marks=p.marks,
            assessment_objective=p.ao, question_text=by_number[n].text, options=by_number[n].options,
            focus_topic=by_number[n].topic, suggested_minutes=exam_specs.SUGGESTED_MINUTES.get(n, 0),
        )
        for n, p in sorted(plan.items())
    ]
    exam = Exam(
        exam_id=f"pool-{paper.slug}", config=config, title=f"{spec.subject}: {spec.title}", paper_title=spec.title,
        duration_minutes=spec.duration_minutes, total_marks=sum(q.marks for q in questions),
        instructions=paper.instructions,
        sources=[SourceExtract(label=s.label, title=s.title, lines=s.lines, original=True) for s in paper.sources],
        questions=questions, syllabus_topics=topics, origin="authored", model=AUTHORED_MODEL,
        prompt_version=AUTHORED_PROMPT_VERSION,
    )
    exam.validation_warnings.extend(validate_exam(exam, [], reference_text, topics))
    exam.validation_warnings.extend(_authoring_checks(paper, exam))

    items = [
        MarkSchemeItem(
            number=q.number, correct_options=by_number[q.number].correct_options,
            model_answer=by_number[q.number].model_answer, acceptable_answers=by_number[q.number].acceptable,
            marking_criteria=rubrics.criteria_for(paper.paper_key, q.number),
            examiner_notes=by_number[q.number].notes, marks=q.marks, assessment_objective=q.assessment_objective,
        )
        for q in questions
    ]
    return exam, MarkScheme(exam_id=exam.exam_id, items=items)


def _authoring_checks(paper: AuthoredPaper, exam: Exam) -> list[str]:
    """Checks specific to hand-authored content."""
    warnings = []
    spec = exam_specs.PAPER_SPECS[paper.paper_key]
    if len(paper.sources) != spec.num_sources:
        warnings.append(f"Expected {spec.num_sources} source(s), found {len(paper.sources)}.")
    for src in paper.sources:
        if not 28 <= len(src.lines) <= 50:
            warnings.append(f"{src.label} has {len(src.lines)} lines (expected about 30-45).")
    for q in paper.questions:
        plan_q = next((p for p in spec.questions if p.number == q.number), None)
        if plan_q and plan_q.qtype == exam_specs.MULTI_SELECT:
            if len(q.options) != 8 or len(q.correct_options) != 4 or not set(q.correct_options) <= set(q.options):
                warnings.append(f"Question {q.number} needs eight options with exactly four correct.")
        if not q.model_answer.strip():
            warnings.append(f"Question {q.number} has no model answer.")
    return warnings


# --- files ----------------------------------------------------------------------------
def write_exam(exam: Exam, scheme: MarkScheme, directory: Path | None = None) -> None:
    """Write a sanitized record (never any reference-document text)."""
    directory = directory or EXAMS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    exam = exam.model_copy(update={"context_chunks": []})
    record = exam_store.ExamRecord(exam=exam, mark_scheme=scheme)
    (directory / f"{exam.exam_id}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")


def seed() -> int:
    """Copy pool papers, syllabus and pins into the runtime store where missing. Returns papers added."""
    added = 0
    settings.EXAMS_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(EXAMS_DIR.glob("*.json")) if EXAMS_DIR.exists() else []:
        target = settings.EXAMS_DIR / path.name
        if not target.exists():
            shutil.copyfile(path, target)
            added += 1
    if SYLLABUS_DIR.exists():
        settings.SYLLABUS_DIR.mkdir(parents=True, exist_ok=True)
        for path in SYLLABUS_DIR.glob("*.json"):
            target = settings.SYLLABUS_DIR / path.name
            if not target.exists():
                shutil.copyfile(path, target)
    if PINS_FILE.exists() and not settings.PINS_FILE.exists():
        shutil.copyfile(PINS_FILE, settings.PINS_FILE)
    return added


def export() -> int:
    """Save the current review state (status, pins, syllabus) back into the pool so it survives restarts."""
    count = 0
    for rec in exam_store.list_records():
        if rec.exam.origin == "authored" and rec.mark_scheme and rec.exam.status != "rejected":
            write_exam(rec.exam, rec.mark_scheme)
            count += 1
    pins = exam_store.get_pins()
    if pins:
        PINS_FILE.write_text(json.dumps(pins, indent=2), encoding="utf-8")
    elif PINS_FILE.exists():
        PINS_FILE.unlink()
    if settings.SYLLABUS_DIR.exists():
        SYLLABUS_DIR.mkdir(parents=True, exist_ok=True)
        for path in settings.SYLLABUS_DIR.glob("*.json"):
            shutil.copyfile(path, SYLLABUS_DIR / path.name)
    return count
