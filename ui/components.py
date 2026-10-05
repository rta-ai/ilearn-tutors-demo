"""Reusable Streamlit components and session helpers."""
from __future__ import annotations

import html
import logging
from contextlib import contextmanager

import streamlit as st

from config import settings
from config.llm import LLMError
from core.document_processor import DocumentError
from core.schemas import Exam, MarkScheme, QuestionType
from core.syllabus import SyllabusNotApprovedError
from core.vector_store import NoRelevantContentError
from utils.text_cleaner import question_lines

log = logging.getLogger(__name__)

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.ilt-header h1 {margin-bottom: 0; font-size: 1.9rem;}
.ilt-header p {color: #6b7280; margin-top: .25rem;}
.ilt-card {border: 1px solid rgba(128,128,128,.25); border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 1rem;}
.ilt-source {font-family: Georgia, 'Times New Roman', serif; font-size: .98rem; line-height: 1.55;}
.ilt-source td {padding: 0 .5rem; vertical-align: top; border: none;}
.ilt-source table {border: none;}
.ilt-ln {color: #9ca3af; font-family: ui-monospace, monospace; font-size: .75rem; text-align: right; width: 2.5rem;}
.ilt-q {line-height: 1.55;}
.ilt-marks {float: right; color: #6b7280; font-weight: 600;}
.ilt-badge {display: inline-block; padding: .1rem .55rem; border-radius: 999px; font-size: .78rem;
            background: rgba(37,99,235,.12); color: #2563eb; margin-right: .35rem;}
.ilt-footer {font-size: .78rem; color: #6b7280; text-align: center; padding-top: .5rem;}
.ilt-hero {text-align: center; padding: 1.5rem 0 1rem;}
.ilt-hero h1 {font-size: 2.6rem; margin-bottom: 0;}
.ilt-hero h3 {font-weight: 500; color: #2563eb; margin-top: .25rem;}
.ilt-hero p {color: #6b7280; max-width: 640px; margin: .5rem auto 0;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='ilt-header'><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>",
        unsafe_allow_html=True,
    )


def sidebar_footer() -> None:
    with st.sidebar:
        st.divider()
        if settings.LOGO_PATH.exists():
            st.image(str(settings.LOGO_PATH), width=120)


def main_footer() -> None:
    st.markdown(f"<hr/><div class='ilt-footer'>{html.escape(settings.FOOTER_TEXT)}</div>", unsafe_allow_html=True)


def badge(text: str) -> str:
    return f"<span class='ilt-badge'>{html.escape(text)}</span>"


@contextmanager
def friendly_errors(action: str):
    """Show user-friendly messages instead of stack traces."""
    try:
        yield
    except (NoRelevantContentError, SyllabusNotApprovedError) as err:
        st.warning(str(err))
    except (LLMError, DocumentError) as err:
        st.error(str(err))
    except Exception:  # noqa: BLE001 - last line of defence during a live demo
        log.exception("Unexpected error while trying to %s", action)
        st.error(f"Something went wrong while trying to {action}. Please try again.")


def goto(view: str) -> None:
    """Switch to another screen on the next rerun."""
    st.session_state["view"] = view
    st.rerun()


# --- Exam rendering ----------------------------------------------------------
def render_source(lines: list[str]) -> None:
    rows = "".join(
        f"<tr><td class='ilt-ln'>{i if i == 1 or i % 5 == 0 else ''}</td><td>{html.escape(line)}</td></tr>"
        for i, line in enumerate(lines, start=1)
    )
    st.markdown(f"<div class='ilt-source'><table>{rows}</table></div>", unsafe_allow_html=True)


def render_sources(exam: Exam) -> None:
    if not exam.sources:
        return
    tabs = st.tabs([f"{s.label}: {s.title}" for s in exam.sources])
    for tab, src in zip(tabs, exam.sources):
        with tab:
            if src.citation:
                st.caption(src.citation if src.original else f"Extracted from {src.citation}")
            render_source(src.lines)


def question_html(number: int, marks: int, text: str, minutes: int = 0) -> str:
    body = "".join(
        f"<div style='margin-left:1.2rem'>&bull; {html.escape(line)}</div>" if bullet else f"<div>{html.escape(line)}</div>"
        for bullet, line in question_lines(text)
    )
    return (
        f"<div class='ilt-q'><span class='ilt-marks'>[{marks} mark{'s' if marks != 1 else ''}"
        f"{f' · about {minutes} min' if minutes else ''}]</span>"
        f"<b>Question {number}</b>{body}</div>"
    )


def render_exam(exam: Exam) -> None:
    st.markdown(
        badge(f"{exam.total_marks} marks") + badge(f"{exam.duration_minutes} minutes")
        + badge(exam.config.difficulty) + badge(f"{len(exam.questions)} questions"),
        unsafe_allow_html=True,
    )
    if exam.instructions:
        with st.expander("Instructions to candidates"):
            st.text("\n".join(f"• {i}" for i in exam.instructions))
    render_sources(exam)
    section = None
    for q in exam.questions:
        if q.section != section:
            section = q.section
            st.subheader(section)
        with st.container(border=True):
            st.markdown(question_html(q.number, q.marks, q.question_text), unsafe_allow_html=True)
            for i, opt in enumerate(q.options):
                st.markdown(f"&nbsp;&nbsp;{chr(65 + i)}. {html.escape(opt)}", unsafe_allow_html=True)
            st.caption(f"{q.assessment_objective} · {q.focus_topic}")


def render_mark_scheme(exam: Exam, scheme: MarkScheme) -> None:
    for item in scheme.items:
        q = exam.question(item.number)
        with st.container(border=True):
            st.markdown(f"**Question {item.number}** · {item.marks} marks · {item.assessment_objective}")
            if q and q.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE, QuestionType.MULTI_SELECT):
                st.success("Correct: " + "; ".join(item.correct_options))
            if item.marking_criteria:
                st.table([{"Level": lv.level, "Marks": lv.marks, "Descriptor": lv.descriptor}
                          for lv in item.marking_criteria])
            if item.acceptable_answers:
                st.markdown("**Indicative content**")
                st.text("\n".join(f"• {a}" for a in item.acceptable_answers))
            st.markdown("**Model answer**")
            st.text(item.model_answer)
            if item.examiner_notes:
                st.caption(f"Examiner notes: {item.examiner_notes}")
