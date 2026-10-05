"""RAG-based exam generation.

Pipeline: exam config + approved syllabus topics -> retrieval queries -> ChromaDB
reference chunks -> structured prompt -> Gemini JSON -> enforce official structure
-> originality / grounding / syllabus validation. The reference material teaches the
format and style; reading extracts are written fresh and checked against it.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import exam_specs, prompts, settings
from config.exam_specs import PaperSpec
from config.llm import LLMProvider
from core.schemas import (
    Exam, ExamConfig, ExamDraft, Question, QuestionType, RetrievedChunk, SourceExtract,
)
from core import syllabus
from core.vector_store import VectorStore
from utils.text_cleaner import clean_model, clean_source_line
from utils.validators import validate_exam


@dataclass(frozen=True)
class PlannedQuestion:
    number: int
    section: str
    qtype: str
    marks: int
    ao: str
    pattern: str = ""
    guidance: str = ""


class ChunkAliases:
    """Short ids (c1, c2, ...) for the prompt; long Chroma ids stay internal."""

    def __init__(self, chunks: list[RetrievedChunk]):
        self.chunks = chunks
        self.to_real = {f"c{i}": c.chunk_id for i, c in enumerate(chunks, start=1)}
        self.to_alias = {v: k for k, v in self.to_real.items()}

    def format(self) -> str:
        return "\n\n".join(
            f"[{self.to_alias[c.chunk_id]}] (from {c.source}, page {c.page})\n{c.text}" for c in self.chunks
        )

    def resolve(self, ids: list[str]) -> list[str]:
        out = []
        for i in ids:
            key = i.strip().strip("[]").lower()
            real = self.to_real.get(key) or (i if i in self.to_alias else None)
            if real and real not in out:
                out.append(real)
        return out


def plan_questions(spec: PaperSpec, config: ExamConfig) -> list[PlannedQuestion]:
    if spec.key == exam_specs.GENERIC_TOPIC_TEST.key:
        return [
            PlannedQuestion(i, "Questions", qtype, marks, "Knowledge and understanding")
            for i, (qtype, marks) in enumerate(exam_specs.generic_question_plan(config.num_questions), start=1)
        ]
    return [
        PlannedQuestion(q.number, q.section, q.qtype, q.marks, q.ao, q.pattern, q.guidance)
        for q in spec.questions_for(config.section)
    ]


def _spec_lines(plan: list[PlannedQuestion]) -> str:
    lines = []
    for q in plan:
        line = f"Q{q.number} [{q.section}] type={q.qtype}, {q.marks} marks, {q.ao}"
        if q.pattern:
            line += f"\n   Official stem pattern: {q.pattern}\n   Requirements: {q.guidance}"
        lines.append(line)
    return "\n".join(lines)


def build_prompt(
    spec: PaperSpec, config: ExamConfig, plan: list[PlannedQuestion], aliases: ChunkAliases,
    topics: list[str], feedback: str = "",
) -> str:
    total = sum(q.marks for q in plan)
    difficulty = prompts.DIFFICULTY_GUIDANCE.get(config.difficulty, "")
    syllabus_block = prompts.SYLLABUS_BLOCK.format(topics="\n".join(f"- {t}" for t in topics))
    reviewer_block = prompts.REVIEWER_BLOCK.format(feedback=feedback) if feedback else ""
    if spec.key == exam_specs.GENERIC_TOPIC_TEST.key:
        return prompts.GENERIC_EXAM_PROMPT.format(
            subject=config.subject, total_marks=total, difficulty=config.difficulty,
            chunks=aliases.format(), question_specs=_spec_lines(plan), num_questions=len(plan),
            difficulty_guidance=difficulty, syllabus_block=syllabus_block, reviewer_block=reviewer_block,
        )
    needs_sources = any(q.section == exam_specs.SECTION_A for q in plan)
    if needs_sources:
        labels = " and ".join(f"'Source {chr(65 + i)}'" for i in range(spec.num_sources))
        source_instructions = prompts.GCSE_SOURCES_WITH_EXTRACTS.format(
            num_sources=spec.num_sources, labels=labels,
            source_guidance=prompts.GCSE_SOURCE_GUIDANCE[spec.num_sources],
        )
    else:
        source_instructions = prompts.SECTION_B_ONLY_SOURCES
    return prompts.GCSE_EXAM_PROMPT.format(
        subject=config.subject, paper_title=spec.title, section=config.section, total_marks=total,
        duration=spec.duration_for(config.section), difficulty=config.difficulty,
        num_sources=spec.num_sources if needs_sources else 0, chunks=aliases.format(),
        source_instructions=source_instructions, question_specs=_spec_lines(plan),
        num_questions=len(plan), difficulty_guidance=difficulty,
        syllabus_block=syllabus_block, reviewer_block=reviewer_block,
    )


def generate_exam(
    config: ExamConfig, store: VectorStore, llm: LLMProvider, feedback: str = "", origin: str = "teacher",
) -> Exam:
    """Generate a draft exam. Raises SyllabusNotApprovedError / NoRelevantContentError when it must not run."""
    spec = exam_specs.PAPER_SPECS[config.paper_key]
    topics = syllabus.approved_topics(config.subject)  # human-approved scope; raises if not approved
    plan = plan_questions(spec, config)
    chunks = store.retrieve(list(spec.retrieval_queries), config.subject, config.doc_ids or None)
    aliases = ChunkAliases(chunks)
    reference_text = "\n".join(store.reference_texts(config.subject, config.doc_ids or None))

    exam = _generate_once(spec, config, plan, chunks, aliases, topics, llm, feedback, reference_text)
    if not exam.originality_ok:  # extract too close to the reference: one automatic rewrite
        retry = _generate_once(
            spec, config, plan, chunks, aliases, topics, llm,
            (feedback + "\n" + prompts.ORIGINALITY_RETRY).strip(), reference_text,
        )
        if retry.originality_ok or len(retry.validation_warnings) <= len(exam.validation_warnings):
            exam = retry
    exam.origin = origin
    return exam


def _generate_once(spec, config, plan, chunks, aliases, topics, llm, feedback, reference_text) -> Exam:
    system = prompts.EXAM_SYSTEM_ORIGINAL if spec.original_sources else prompts.EXAM_SYSTEM_GROUNDED
    draft = llm.generate_json(system, build_prompt(spec, config, plan, aliases, topics, feedback), ExamDraft)
    draft = clean_model(draft, skip=frozenset({"lines"}))

    # The official structure always wins over what the model returned.
    drafts_by_number = {d.number: d for d in draft.questions}
    questions: list[Question] = []
    for i, p in enumerate(plan):
        d = drafts_by_number.get(p.number) or (draft.questions[i] if i < len(draft.questions) else None)
        if d is None:
            continue
        if p.qtype == exam_specs.MULTI_SELECT:
            d.question_text, d.options = _lift_statements(d.question_text, d.options)
        questions.append(Question(
            number=p.number, section=p.section, question_type=QuestionType(p.qtype), marks=p.marks,
            assessment_objective=p.ao, question_text=d.question_text, options=d.options,
            focus_topic=d.focus_topic, chunk_ids=aliases.resolve(d.chunk_ids),
            suggested_minutes=exam_specs.SUGGESTED_MINUTES.get(p.number, 0) if spec.questions else 0,
        ))

    sources = [
        SourceExtract(
            label=s.label, title=s.title,
            lines=[clean_source_line(ln) for ln in s.lines if ln.strip()],
            chunk_ids=aliases.resolve(s.chunk_ids), original=spec.original_sources,
        )
        for s in draft.sources
    ]

    duration = (
        spec.duration_for(config.section) if spec.duration_minutes
        else max(10, sum(q.marks for q in questions) * 2)
    )
    section_note = f" ({config.section})" if config.section and config.section != exam_specs.FULL_PAPER else ""
    exam = Exam(
        config=config,
        title=f"{config.subject}: {spec.title}" if spec.questions else f"{config.subject} {spec.title}",
        paper_title=f"{spec.title}{section_note}",
        duration_minutes=duration,
        total_marks=sum(q.marks for q in questions),
        instructions=draft.instructions,
        sources=sources,
        questions=questions,
        context_chunks=chunks,
        syllabus_topics=topics,
        prompt_version=prompts.PROMPT_VERSION,
        model=settings.GENERATION_MODEL,
    )
    if len(questions) < len(plan):
        exam.validation_warnings.append(f"Only {len(questions)} of {len(plan)} questions were generated.")
    exam.validation_warnings.extend(validate_exam(exam, chunks, reference_text, topics))
    return exam


def _lift_statements(text: str, options: list[str]) -> tuple[str, list[str]]:
    """Repair choose-four questions where statements leaked into the question text instead of options."""
    if len(options) >= 8:
        return text, options
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    stem = [ln for ln in lines if not ln.endswith(".") or len(ln.split()) > 14 or ln.lower().startswith(("read ", "choose "))]
    stmts = [ln for ln in lines if ln not in stem]
    if len(stmts) + len(options) >= 8 and stmts:
        merged = stmts + [o for o in options if o not in stmts]
        return chr(10).join(stem), merged[:8]
    return text, options


def exam_as_text(exam: Exam, include_sources: bool = True) -> str:
    """Plain-text rendering used in prompts (mark scheme, grading)."""
    parts = [exam.title, exam.paper_title, f"Total marks: {exam.total_marks}"]
    if include_sources:
        for s in exam.sources:
            parts.append(f"\n{s.label}: {s.title}")
            parts.extend(f"{i:>3}  {line}" for i, line in enumerate(s.lines, start=1))
    for q in exam.questions:
        parts.append(f"\nQuestion {q.number} ({q.marks} marks, {q.question_type.value}, {q.assessment_objective})")
        parts.append(q.question_text)
        parts.extend(f"  {chr(65 + i)}. {opt}" for i, opt in enumerate(q.options))
    return "\n".join(parts)
