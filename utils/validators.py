"""Grounding, originality and structure checks for generated exams.

These run after every generation. Deterministic problems (wrong marks, invented
chunk ids, topic names that differ only in wording) are repaired in place;
everything else is reported as a warning for the reviewing teacher.
"""
from __future__ import annotations

import re
import textwrap

from config import settings
from core.schemas import Exam, QuestionType, RetrievedChunk
from utils.text_cleaner import content_words

_WORD = re.compile(r"[a-z0-9']+")
_LINE_REF = re.compile(r"\blines?\s+(\d+)\s*(?:to|-|–)\s*(\d+)", re.IGNORECASE)


def word_overlap(text: str, reference: str) -> float:
    """Share of ``text``'s content words that also appear in ``reference``."""
    words = content_words(text)
    if not words:
        return 0.0
    ref = set(content_words(reference))
    return sum(w in ref for w in words) / len(words)


def _ngrams(text: str, n: int) -> list[tuple[str, ...]]:
    words = _WORD.findall(text.lower())
    return [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]


def copied_share(text: str, reference: str, n: int = settings.ORIGINALITY_NGRAM) -> float:
    """Share of ``text``'s n-word runs that appear verbatim in ``reference`` (0 = fully original)."""
    grams = _ngrams(text, n)
    if not grams:
        return 0.0
    ref = set(_ngrams(reference, n))
    return sum(g in ref for g in grams) / len(grams)


def originality_failures(exam: Exam, reference_text: str) -> list[str]:
    """Labels of extracts that reuse the reference material too closely."""
    bad = []
    for src in exam.sources:
        if copied_share(" ".join(src.lines), reference_text) > settings.MAX_COPIED_NGRAM_SHARE:
            bad.append(src.label)
    return bad


def _canonical_topic(topic: str, allowed: list[str]) -> str | None:
    t = topic.strip().lower()
    for a in allowed:
        if t == a.lower():
            return a
    for a in allowed:
        al = a.lower()
        if t and (t in al or al in t):
            return a
    return None


def validate_exam(
    exam: Exam, chunks: list[RetrievedChunk], reference_text: str = "", topics: list[str] | None = None
) -> list[str]:
    warnings: list[str] = []
    by_id = {c.chunk_id: c for c in chunks}
    all_text = "\n".join(c.text for c in chunks)

    for src in exam.sources:
        src.chunk_ids = [cid for cid in src.chunk_ids if cid in by_id]
        extract = " ".join(src.lines)
        if src.original:
            src.citation = "Original practice text written for this paper"
            share = copied_share(extract, reference_text or all_text)
            if share > settings.MAX_COPIED_NGRAM_SHARE:
                exam.originality_ok = False
                warnings.append(
                    f"ORIGINALITY: {src.label} reuses wording from the reference material ({share:.0%} of its "
                    "phrases match). It must not be approved as is."
                )
        else:
            cited = "\n".join(by_id[cid].text for cid in src.chunk_ids) or all_text
            overlap = max(word_overlap(extract, cited), word_overlap(extract, all_text))
            if overlap < settings.MIN_EXTRACT_OVERLAP:
                warnings.append(f"{src.label} is not a close copy of the uploaded material ({overlap:.0%} match).")
            src.citation = _citation(src.chunk_ids, by_id)

    total_lines = max((len(s.lines) for s in exam.sources), default=0)
    for q in exam.questions:
        q.chunk_ids = [cid for cid in q.chunk_ids if cid in by_id]
        reference = "\n".join(by_id[cid].text for cid in q.chunk_ids) or all_text
        reference += "\n" + "\n".join(" ".join(s.lines) for s in exam.sources)
        q.grounding_score = round(word_overlap(q.question_text + " " + " ".join(q.options), reference), 2)

        original_exam = any(s.original for s in exam.sources)
        if not q.chunk_ids and not original_exam:
            warnings.append(f"Question {q.number} did not cite any source chunk.")
        elif (
            q.grounding_score < settings.MIN_QUESTION_OVERLAP
            and q.section != "Section B: Writing"
            # Templated stems on extended reading questions ("How does the writer...") share few words
            # with the text by design, so lexical overlap only means something for the other types.
            and (q.question_type != QuestionType.EXTENDED or not exam.sources)
        ):
            warnings.append(f"Question {q.number} has weak overlap with the source material; review before use.")

        if q.question_type in (QuestionType.MCQ, QuestionType.MULTI_SELECT) and len(q.options) < 3:
            warnings.append(f"Question {q.number} is missing answer options.")
        if q.question_type == QuestionType.TRUE_FALSE:
            q.options = ["True", "False"]
        if q.question_type == QuestionType.MULTI_SELECT and len(q.options) != 8:
            warnings.append(f"Question {q.number} should have eight statements (has {len(q.options)}).")

        for start, end in (map(int, m.groups()) for m in _LINE_REF.finditer(q.question_text)):
            if total_lines and (end > total_lines or start > end):
                warnings.append(f"Question {q.number} refers to lines {start}-{end} but the extract has {total_lines} lines.")

        if topics:
            canon = _canonical_topic(q.focus_topic, topics)
            if canon:
                q.focus_topic = canon
            else:
                warnings.append(f"Question {q.number} topic '{q.focus_topic}' is not in the approved syllabus topics.")
                if q.number not in exam.flagged_questions:
                    exam.flagged_questions.append(q.number)
    return warnings


def _citation(chunk_ids: list[str], by_id: dict[str, RetrievedChunk]) -> str:
    refs: dict[str, set[int]] = {}
    for cid in chunk_ids:
        c = by_id[cid]
        refs.setdefault(c.source, set()).add(c.page)
    return "; ".join(f"{src}, p.{', '.join(map(str, sorted(pages)))}" for src, pages in refs.items())


def wrap_lines(text: str, width: int = 80) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        lines.extend(textwrap.wrap(para, width) or [""])
    return [ln for ln in lines if ln.strip()]
