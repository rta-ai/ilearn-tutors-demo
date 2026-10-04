"""Performance analysis: scores per skill/topic and revision pointers."""
from __future__ import annotations

from collections import OrderedDict

from config import settings
from config.exam_specs import AO_LABELS
from core.schemas import AreaScore, Exam, QuestionGrade


def area_scores(exam: Exam, grades: list[QuestionGrade]) -> list[AreaScore]:
    """Aggregate marks by assessment objective (GCSE) or focus topic (topic tests)."""
    use_ao = any(q.assessment_objective.startswith("AO") for q in exam.questions)
    totals: "OrderedDict[str, list[int]]" = OrderedDict()
    for g in grades:
        q = exam.question(g.number)
        if q is None:
            continue
        key = q.assessment_objective.split(" ")[0] if use_ao else (q.focus_topic or f"Question {q.number}")
        if use_ao and key in ("AO5",):  # writing task is AO5+AO6 combined
            key = "AO5/AO6"
        t = totals.setdefault(key, [0, 0])
        t[0] += g.marks_awarded
        t[1] += g.marks_available
    return [AreaScore(area=AO_LABELS.get(k, k), awarded=a, available=b) for k, (a, b) in totals.items()]


def revision_topics_from_context(exam: Exam, grades: list[QuestionGrade]) -> list[str]:
    """Fallback revision list: weak questions mapped to the pages they came from."""
    by_id = {c.chunk_id: c for c in exam.context_chunks}
    topics: list[str] = []
    for g in grades:
        if g.marks_available and g.marks_awarded / g.marks_available >= settings.WEAK_AREA_THRESHOLD:
            continue
        q = exam.question(g.number)
        if q is None:
            continue
        pages = sorted({(by_id[c].source, by_id[c].page) for c in q.chunk_ids if c in by_id})
        where = ", ".join(f"{src} p.{p}" for src, p in pages)
        topics.append(f"{q.focus_topic or 'Question ' + str(q.number)}" + (f" ({where})" if where else ""))
    return topics


def source_pages_for_topic(exam: Exam, topic: str) -> str:
    """Best-effort page pointer for a revision topic named by the LLM."""
    topic_l = topic.lower()
    for q in exam.questions:
        if q.focus_topic and (q.focus_topic.lower() in topic_l or topic_l in q.focus_topic.lower()):
            chunks = [c for c in exam.context_chunks if c.chunk_id in q.chunk_ids]
            if chunks:
                return ", ".join(sorted({f"{c.source} p.{c.page}" for c in chunks}))
    return ""
