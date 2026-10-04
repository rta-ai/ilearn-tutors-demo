"""AI grading engine.

Objective questions (MCQ, true/false, choose-four) are marked locally against
the mark scheme: instant, free and exact. Written answers are batched into a
single Gemini call to stay well inside free-tier rate limits.
"""
from __future__ import annotations

from config import prompts, settings
from config.llm import LLMProvider
from core.exam_generator import exam_as_text
from core.feedback import area_scores, revision_topics_from_context
from core.mark_scheme import mark_scheme_as_text
from core.schemas import (
    Exam, GradingDraft, GradingResult, MarkScheme, Question, QuestionGrade, QuestionType, StudentAnswer,
)
from utils.text_cleaner import clean_model


def grade_attempt(
    exam: Exam, scheme: MarkScheme, answers: list[StudentAnswer], llm: LLMProvider, time_taken_seconds: int = 0
) -> GradingResult:
    answers_by_q = {a.number: a for a in answers}
    grades: dict[int, QuestionGrade] = {}
    written: list[tuple[Question, StudentAnswer]] = []

    for q in exam.questions:
        ans = answers_by_q.get(q.number, StudentAnswer(number=q.number))
        if q.question_type.is_objective:
            grades[q.number] = _mark_objective(q, ans, scheme)
        elif ans.is_blank:
            grades[q.number] = QuestionGrade(
                number=q.number, marks_awarded=0, marks_available=q.marks, level="No response",
                what_was_missing="No answer was given.",
                how_to_improve="Always attempt every question: even a short answer can earn marks.",
            )
        else:
            written.append((q, ans))

    draft = None
    if written:
        draft = _grade_written(exam, scheme, written, grades, llm)
        for g in draft.grades:
            q = exam.question(g.number)
            if q is None or g.number in grades:
                continue
            grades[g.number] = QuestionGrade(
                number=g.number, marks_awarded=max(0, min(g.marks_awarded, q.marks)), marks_available=q.marks,
                level=g.level, what_went_well=g.what_went_well, what_was_missing=g.what_was_missing,
                how_to_improve=g.how_to_improve,
            )
        for q, _ in written:  # the model skipped a question
            grades.setdefault(q.number, QuestionGrade(
                number=q.number, marks_awarded=0, marks_available=q.marks, level="Not marked",
                what_was_missing="This answer could not be marked automatically; please ask your teacher to review it.",
            ))

    ordered = [grades[q.number] for q in exam.questions]
    awarded = sum(g.marks_awarded for g in ordered)
    available = sum(g.marks_available for g in ordered)
    pct = round(100 * awarded / available, 1) if available else 0.0
    scores = area_scores(exam, ordered)

    weak = list(draft.weak_areas) if draft else []
    weak += [s.area for s in scores if s.ratio < settings.WEAK_AREA_THRESHOLD and s.area not in weak]
    return GradingResult(
        exam_id=exam.exam_id, time_taken_seconds=time_taken_seconds, answers=answers, grades=ordered,
        total_awarded=awarded, total_available=available, percentage=pct, grade=indicative_grade(pct),
        weak_areas=weak, area_scores=scores,
        revision_topics=(draft.revision_topics if draft and draft.revision_topics
                         else revision_topics_from_context(exam, ordered)),
        overall_feedback=draft.overall_feedback if draft else _objective_only_feedback(pct),
    )


def indicative_grade(percentage: float) -> str:
    return next(g for threshold, g in settings.GRADE_BOUNDARIES if percentage >= threshold)


def _mark_objective(q: Question, ans: StudentAnswer, scheme: MarkScheme) -> QuestionGrade:
    item = scheme.item(q.number)
    correct = set(item.correct_options) if item else set()
    chosen = set(ans.selected_options)
    if q.question_type == QuestionType.MULTI_SELECT:
        # Choose-four: one mark per correct choice; extra choices beyond the limit lose credit.
        limit = len(correct) or 4
        awarded = len(chosen & correct) if len(chosen) <= limit else max(0, len(chosen & correct) - (len(chosen) - limit))
    else:
        awarded = q.marks if chosen and chosen <= correct else 0
    awarded = min(awarded, q.marks)
    missed = sorted(correct - chosen)
    return QuestionGrade(
        number=q.number, marks_awarded=awarded, marks_available=q.marks, auto_marked=True,
        level="Correct" if awarded == q.marks else ("Partially correct" if awarded else "Incorrect"),
        what_went_well="Correct." if awarded == q.marks else (
            f"{awarded} correct choice(s)." if awarded else ""),
        what_was_missing="" if awarded == q.marks else "Correct answer(s): " + "; ".join(missed or sorted(correct)),
        how_to_improve="" if awarded == q.marks else (
            "Re-read the relevant lines carefully and check each statement against the text."),
    )


def _grade_written(exam, scheme, written, objective_grades, llm: LLMProvider) -> GradingDraft:
    answers_text = "\n\n".join(
        f"Question {q.number} ({q.marks} marks):\n{a.text.strip()}" for q, a in written
    )
    objective_summary = "\n".join(
        f"Question {g.number} ({exam.question(g.number).focus_topic}): {g.marks_awarded}/{g.marks_available}"
        for g in objective_grades.values() if g.auto_marked
    ) or "None"
    topics = exam.syllabus_topics or sorted({q.focus_topic for q in exam.questions if q.focus_topic})
    prompt = prompts.GRADING_PROMPT.format(
        exam_text=exam_as_text(exam),
        mark_scheme_text=mark_scheme_as_text(exam, scheme),
        numbers=", ".join(str(q.number) for q, _ in written),
        answers_text=answers_text,
        objective_summary=objective_summary,
        topics="; ".join(topics) or "See exam questions",
    )
    return clean_model(llm.generate_json(
        prompts.GRADING_SYSTEM, prompt, GradingDraft, temperature=settings.GRADING_TEMPERATURE
    ))


def _objective_only_feedback(pct: float) -> str:
    if pct >= 80:
        return "Excellent work: you answered almost every question correctly."
    if pct >= 50:
        return "Solid attempt. Review the questions you missed and re-read the matching parts of the material."
    return "This topic needs more revision. Work through the recommended topics and then try again."
