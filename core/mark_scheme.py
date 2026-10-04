"""Mark scheme generation, grounded in the same RAG context as the exam."""
from __future__ import annotations

from config import prompts
from config.llm import LLMProvider
from core.exam_generator import ChunkAliases, exam_as_text
from core.schemas import Exam, MarkScheme, MarkSchemeDraft, MarkSchemeItem
from utils.text_cleaner import clean_model


def generate_mark_scheme(exam: Exam, llm: LLMProvider) -> MarkScheme:
    prompt = prompts.MARK_SCHEME_PROMPT.format(
        exam_text=exam_as_text(exam),
        chunks=ChunkAliases(exam.context_chunks).format(),
        numbers=", ".join(str(q.number) for q in exam.questions),
    )
    draft = clean_model(llm.generate_json(prompts.MARK_SCHEME_SYSTEM, prompt, MarkSchemeDraft))
    by_number = {d.number: d for d in draft.items}

    items = []
    for q in exam.questions:
        d = by_number.get(q.number)
        if d is None:
            continue
        correct = d.correct_options
        if q.question_type.is_objective:
            correct = _match_options(correct, q.options)
        items.append(MarkSchemeItem(
            **d.model_dump(exclude={"correct_options"}), correct_options=correct,
            marks=q.marks, assessment_objective=q.assessment_objective,
        ))
    return MarkScheme(exam_id=exam.exam_id, items=items)


def _match_options(answers: list[str], options: list[str]) -> list[str]:
    """Map model answers ('B', 'b) ...', or loosely matching text) onto exact option text."""
    matched = []
    norm = {o.strip().lower().rstrip("."): o for o in options}
    for a in answers:
        key = a.strip().lower().rstrip(".")
        if key in norm:
            opt = norm[key]
        elif len(key) == 1 and key.isalpha() and ord(key) - 97 < len(options):
            opt = options[ord(key) - 97]
        elif len(key) > 2 and key[1] in ".)" and key[0].isalpha() and ord(key[0]) - 97 < len(options):
            opt = options[ord(key[0]) - 97]
        else:
            opt = next((o for k, o in norm.items() if key in k or k in key), None)
        if opt and opt not in matched:
            matched.append(opt)
    return matched


def mark_scheme_as_text(exam: Exam, scheme: MarkScheme) -> str:
    parts = []
    for item in scheme.items:
        q = exam.question(item.number)
        parts.append(f"\nQuestion {item.number} ({item.marks} marks, {item.assessment_objective})")
        if q and q.question_type.is_objective:
            parts.append("Correct: " + "; ".join(item.correct_options))
        parts.append("Model answer: " + item.model_answer)
        if item.acceptable_answers:
            parts.append("Credit: " + "; ".join(item.acceptable_answers))
        for lv in item.marking_criteria:
            parts.append(f"  {lv.level} ({lv.marks}): {lv.descriptor}")
        if item.examiner_notes:
            parts.append("Notes: " + item.examiner_notes)
    return "\n".join(parts)
