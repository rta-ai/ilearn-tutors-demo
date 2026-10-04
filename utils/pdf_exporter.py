"""PDF export (reportlab): exam paper, mark scheme and results report."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from config import settings
from core.schemas import Exam, GradingResult, MarkScheme, QuestionType
from utils.text_cleaner import question_lines

_BASE = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=_BASE["Title"], fontSize=18, spaceAfter=6),
    "subtitle": ParagraphStyle("st", parent=_BASE["Normal"], fontSize=12, alignment=TA_CENTER, spaceAfter=12),
    "h2": ParagraphStyle("h2", parent=_BASE["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4),
    "h3": ParagraphStyle("h3", parent=_BASE["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=2),
    "body": ParagraphStyle("b", parent=_BASE["Normal"], fontSize=10.5, leading=14, spaceAfter=4),
    "small": ParagraphStyle("s", parent=_BASE["Normal"], fontSize=9, leading=12, textColor=colors.grey),
    "source": ParagraphStyle("src", parent=_BASE["Normal"], fontName="Times-Roman", fontSize=10.5, leading=13.5),
    "bullet": ParagraphStyle("bl", parent=_BASE["Normal"], fontSize=10.5, leading=14, leftIndent=14, bulletIndent=4),
    "marks": ParagraphStyle("m", parent=_BASE["Normal"], fontSize=10, alignment=2),
}

# Characters outside the built-in fonts' WinAnsi set render as boxes.
_REPLACE = {"−": "-", "‑": "-", " ": " ", " ": " ", "→": "->", "≤": "<=", "≥": ">="}


def _safe(text: str) -> str:
    for bad, good in _REPLACE.items():
        text = text.replace(bad, good)
    text = escape(text.encode("cp1252", errors="replace").decode("cp1252"))
    return text.replace("\n", "<br/>")


def _p(text: str, style: str = "body", label: str = "") -> Paragraph:
    prefix = f"<b>{_safe(label)}:</b> " if label else ""
    return Paragraph(prefix + _safe(text), S[style])


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(20 * mm, 12 * mm, settings.FOOTER_TEXT)
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _build(story) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _cover(exam: Exam, subtitle: str) -> list:
    story = [
        Spacer(1, 20 * mm),
        _p("I Learn Tutors", "subtitle"),
        _p(exam.title, "title"),
        _p(exam.paper_title, "subtitle"),
        _p(subtitle, "subtitle"),
        Spacer(1, 6 * mm),
    ]
    info = Table(
        [["Time allowed", f"{exam.duration_minutes} minutes"], ["Total marks", str(exam.total_marks)],
         ["Tier", exam.config.difficulty]],
        colWidths=[45 * mm, 80 * mm],
    )
    info.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke), ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info)
    return story


def _question_body(text: str) -> list:
    return [
        Paragraph(_safe(line), S["bullet"], bulletText="•") if bullet else _p(line)
        for bullet, line in question_lines(text)
    ]


def _answer_lines(n: int) -> list:
    return [Spacer(1, 6 * mm)] + [
        item for _ in range(n) for item in (HRFlowable(width="100%", thickness=0.4, color=colors.grey), Spacer(1, 7 * mm))
    ]


def _question_header(number: int, marks: int) -> Table:
    t = Table([[_p(f"Question {number}", "h3"), _p(f"[{marks} mark{'s' if marks != 1 else ''}]", "marks")]],
              colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _source_table(lines: list[str]) -> Table:
    rows = [[_p(str(i) if i % 5 == 0 or i == 1 else "", "small"), _p(line, "source")]
            for i, line in enumerate(lines, start=1)]
    t = Table(rows, colWidths=[10 * mm, 160 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


def export_exam(exam: Exam) -> bytes:
    story = _cover(exam, "Question Paper")
    if exam.instructions:
        story += [Spacer(1, 6 * mm), _p("Instructions", "h2")]
        story += [_p(f"• {i}") for i in exam.instructions]
    for src in exam.sources:
        story += [PageBreak(), _p(f"{src.label}: {src.title}", "h2")]
        if src.citation:
            story.append(_p(f"Source: {src.citation}", "small"))
        story += [Spacer(1, 3 * mm), _source_table(src.lines)]
    story.append(PageBreak())
    section = None
    for q in exam.questions:
        if q.section != section:
            section = q.section
            story.append(_p(section, "h2"))
        block = [_question_header(q.number, q.marks), *_question_body(q.question_text)]
        if q.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE, QuestionType.MULTI_SELECT):
            block += [_p(f"☐  {chr(65 + i)}. {opt}") for i, opt in enumerate(q.options)]
        else:
            n_lines = 4 if q.marks <= 4 else 8
            block += _answer_lines(n_lines)
        story += [KeepTogether(block), Spacer(1, 4 * mm)]
    story += [Spacer(1, 6 * mm), _p("END OF QUESTIONS", "subtitle")]
    return _build(story)


def export_mark_scheme(exam: Exam, scheme: MarkScheme) -> bytes:
    story = _cover(exam, "Mark Scheme")
    story.append(PageBreak())
    for item in scheme.items:
        q = exam.question(item.number)
        story += [_question_header(item.number, item.marks), _p(f"Assessment objective: {item.assessment_objective}", "small")]
        if q:
            story.append(_p(q.question_text, "small"))
        if item.correct_options:
            story += [_p("Correct answer(s)", "h3")] + [_p(f"• {o}") for o in item.correct_options]
        if item.marking_criteria:
            rows = [[_p("Level", "small"), _p("Marks", "small"), _p("Descriptor", "small")]] + [
                [_p(lv.level), _p(lv.marks), _p(lv.descriptor)] for lv in item.marking_criteria
            ]
            t = Table(rows, colWidths=[25 * mm, 18 * mm, 127 * mm], repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
            story += [_p("Marking criteria", "h3"), t]
        if item.acceptable_answers:
            story += [_p("Indicative content / acceptable answers", "h3")]
            story += [_p(f"• {a}") for a in item.acceptable_answers]
        story += [_p("Model answer", "h3"), _p(item.model_answer)]
        if item.examiner_notes:
            story += [_p("Examiner notes", "h3"), _p(item.examiner_notes)]
        story.append(Spacer(1, 6 * mm))
    return _build(story)


def export_results(exam: Exam, result: GradingResult, student_name: str = "Student") -> bytes:
    story = _cover(exam, f"Results Report: {student_name}")
    summary = Table(
        [["Score", f"{result.total_awarded} / {result.total_available}"],
         ["Percentage", f"{result.percentage:.0f}%"], ["Indicative grade", result.grade],
         ["Time taken", f"{result.time_taken_seconds // 60} min {result.time_taken_seconds % 60} s"]],
        colWidths=[45 * mm, 80 * mm],
    )
    summary.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                 ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("PADDING", (0, 0), (-1, -1), 6)]))
    story += [Spacer(1, 6 * mm), summary]
    if result.overall_feedback:
        story += [_p("Overall feedback", "h2"), _p(result.overall_feedback)]
    if result.area_scores:
        story.append(_p("Performance by area", "h2"))
        story += [_p(f"{a.area}: {a.awarded}/{a.available} ({a.ratio:.0%})") for a in result.area_scores]
    if result.weak_areas:
        story += [_p("Areas to work on", "h2")] + [_p(f"• {w}") for w in result.weak_areas]
    if result.revision_topics:
        story += [_p("Recommended revision", "h2")] + [_p(f"• {t}") for t in result.revision_topics]
    story += [PageBreak(), _p("Question-by-question feedback", "h2")]
    for g in result.grades:
        block = [_question_header(g.number, g.marks_available),
                 _p(f"Marks awarded: {g.marks_awarded}/{g.marks_available}" + (f"  ({g.level})" if g.level else ""))]
        for label, text in (("What went well", g.what_went_well), ("What was missing", g.what_was_missing),
                            ("How to improve", g.how_to_improve)):
            if text:
                block.append(_p(text, label=label))
        story += [KeepTogether(block), Spacer(1, 3 * mm)]
    return _build(story)
