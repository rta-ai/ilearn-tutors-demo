"""Data contracts for the assessment engine.

These Pydantic models are the integration surface for the main I Learn Tutors
platform: they serialise to JSON for an API (e.g. FastAPI request/response
models) and map one-to-one onto database tables (e.g. Supabase: exams,
mark_schemes, attempts).

Two families of models:
  * ``*Draft`` models: the exact JSON shape the LLM is asked to return. They are
    kept flat and simple so they work as Gemini response schemas.
  * Domain models (Exam, MarkScheme, GradingResult, ...): what the app stores
    and renders, enriched with ids, metadata and computed totals.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class QuestionType(str, Enum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    MULTI_SELECT = "multi_select"
    SHORT_ANSWER = "short_answer"
    EXTENDED = "extended"

    @property
    def is_objective(self) -> bool:
        return self in (QuestionType.MCQ, QuestionType.TRUE_FALSE, QuestionType.MULTI_SELECT)


# --- Retrieval ---------------------------------------------------------------
class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source: str
    page: int
    subject: str
    distance: float = 0.0


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    subject: str
    pages: int
    chunks: int
    uploaded_at: str = Field(default_factory=_now)


# --- LLM output drafts ---------------------------------------------------------
class SourceDraft(BaseModel):
    label: str = Field(description="'Source A' or 'Source B'")
    title: str = Field(description="Short descriptive title for the extract")
    lines: list[str] = Field(description="The extract copied VERBATIM from the source material, split into short lines")
    chunk_ids: list[str] = Field(description="Ids of the source chunks the extract was copied from")


class QuestionDraft(BaseModel):
    number: int
    question_text: str = Field(description="Full question wording, including any bullet prompts as plain lines")
    options: list[str] = Field(description="Answer options for mcq / true_false / multi_select; empty otherwise")
    focus_topic: str = Field(description="The curriculum topic or skill this question assesses, in 2-6 words")
    chunk_ids: list[str] = Field(description="Ids of the source chunks this question is based on")


class ExamDraft(BaseModel):
    instructions: list[str] = Field(description="Instructions to candidates, one per item")
    sources: list[SourceDraft]
    questions: list[QuestionDraft]


class SyllabusDraft(BaseModel):
    topics: list[str] = Field(description="Short names of the topics and skills this subject's exams assess")


class Syllabus(BaseModel):
    subject: str
    topics: list[str]
    approved: bool = False
    updated_at: str = Field(default_factory=_now)


class OcrPage(BaseModel):
    page: int
    text: str = Field(description="Full transcription of the page, in reading order, plain text")


class OcrDraft(BaseModel):
    pages: list[OcrPage]


class LevelDescriptor(BaseModel):
    level: str = Field(description="e.g. 'Level 4' or 'Full marks'")
    marks: str = Field(description="Mark range, e.g. '7-8'")
    descriptor: str


class MarkSchemeItemDraft(BaseModel):
    number: int
    correct_options: list[str] = Field(description="Exact correct option text(s) for objective questions; empty otherwise")
    model_answer: str = Field(description="A high-scoring model answer grounded in the source material")
    acceptable_answers: list[str] = Field(description="Acceptable points or alternative answers that should earn credit")
    marking_criteria: list[LevelDescriptor]
    examiner_notes: str = Field(description="Guidance on common errors and what not to credit")


class MarkSchemeDraft(BaseModel):
    items: list[MarkSchemeItemDraft]


class QuestionGradeDraft(BaseModel):
    number: int
    marks_awarded: int
    level: str = Field(description="Level or band reached, e.g. 'Level 3'")
    what_went_well: str
    what_was_missing: str
    how_to_improve: str


class GradingDraft(BaseModel):
    grades: list[QuestionGradeDraft]
    weak_areas: list[str] = Field(description="Skills or topics the student is weak in, based on this attempt")
    revision_topics: list[str] = Field(description="Topics to revise, named as they appear in the source material")
    overall_feedback: str


# --- Domain models -------------------------------------------------------------
class SourceExtract(BaseModel):
    label: str
    title: str
    lines: list[str]
    chunk_ids: list[str] = []  # reference chunks that informed the style (original texts) or were copied from
    citation: str = ""  # e.g. "booklet.pdf, p.4"
    original: bool = False  # True: written for this paper, not taken from the reference material


class Question(BaseModel):
    number: int
    section: str
    question_type: QuestionType
    marks: int
    assessment_objective: str
    question_text: str
    options: list[str] = []
    focus_topic: str = ""
    chunk_ids: list[str] = []
    grounding_score: float = 0.0  # 0-1 lexical overlap with cited chunks


class ExamConfig(BaseModel):
    subject: str
    paper_key: str
    section: str = ""
    num_questions: int = 0
    difficulty: str = "Higher"
    include_mark_scheme: bool = True
    doc_ids: list[str] = []


class Exam(BaseModel):
    exam_id: str = Field(default_factory=_id)
    created_at: str = Field(default_factory=_now)
    config: ExamConfig
    title: str
    paper_title: str
    duration_minutes: int
    total_marks: int
    instructions: list[str]
    sources: list[SourceExtract]
    questions: list[Question]
    context_chunks: list[RetrievedChunk] = []  # RAG context, kept for traceability
    validation_warnings: list[str] = []
    prompt_version: str = ""
    model: str = ""
    # Human-in-the-loop review
    status: str = "draft"  # draft | approved | rejected
    origin: str = "teacher"  # teacher | student_on_demand
    syllabus_topics: list[str] = []  # approved topics this paper was restricted to
    originality_ok: bool = True  # False if extracts closely match the reference material
    flagged_questions: list[int] = []
    reviewer_note: str = ""
    reviewed_at: str = ""

    def question(self, number: int) -> Question | None:
        return next((q for q in self.questions if q.number == number), None)


class MarkSchemeItem(MarkSchemeItemDraft):
    marks: int = 0
    assessment_objective: str = ""


class MarkScheme(BaseModel):
    exam_id: str
    items: list[MarkSchemeItem]

    def item(self, number: int) -> MarkSchemeItem | None:
        return next((i for i in self.items if i.number == number), None)


class StudentAnswer(BaseModel):
    number: int
    text: str = ""
    selected_options: list[str] = []

    @property
    def is_blank(self) -> bool:
        return not self.text.strip() and not self.selected_options


class QuestionGrade(BaseModel):
    number: int
    marks_awarded: int
    marks_available: int
    level: str = ""
    what_went_well: str = ""
    what_was_missing: str = ""
    how_to_improve: str = ""
    auto_marked: bool = False


class AreaScore(BaseModel):
    area: str
    awarded: int
    available: int

    @property
    def ratio(self) -> float:
        return self.awarded / self.available if self.available else 0.0


class GradingResult(BaseModel):
    attempt_id: str = Field(default_factory=_id)
    exam_id: str
    submitted_at: str = Field(default_factory=_now)
    time_taken_seconds: int = 0
    answers: list[StudentAnswer]
    grades: list[QuestionGrade]
    total_awarded: int
    total_available: int
    percentage: float
    grade: str
    weak_areas: list[str] = []
    revision_topics: list[str] = []
    area_scores: list[AreaScore] = []
    overall_feedback: str = ""
