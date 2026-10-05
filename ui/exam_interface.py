"""Exam screen: the student sits the paper and submits for marking."""
from __future__ import annotations

import time

import streamlit as st

from config.llm import LLMProvider
from core import exam_store
from core.grader import grade_attempt
from core.schemas import Exam, Question, QuestionType, StudentAnswer
from ui import accessibility
from ui import components as ui

LIST_BOXES = 4


def _is_list_four(q: Question) -> bool:
    return q.question_type == QuestionType.SHORT_ANSWER and q.marks == 4 and "list four" in q.question_text.lower()


def render(llm: LLMProvider | None) -> None:
    exam: Exam | None = st.session_state.get("exam")
    if exam is None:
        st.info("You haven't chosen an exam yet.")
        if st.button("Choose an exam", type="primary"):
            ui.goto("student_selection")
        return
    if llm is None:
        st.error("The AI service is not configured, so answers cannot be marked.")
        return

    if not st.session_state.get("exam_started_at"):
        st.markdown(f"### {exam.title}")
        st.caption(exam.paper_title)
        if st.session_state.get("result") is not None:
            if st.button("View my results", type="primary"):
                ui.goto("results")
        if st.button("Start exam" if st.session_state.get("result") is None else "Retake this exam"):
            st.session_state.update(exam_started_at=time.time(), result=None)
            st.rerun()
        return

    _sit_exam(exam, llm)


def _sit_exam(exam: Exam, llm: LLMProvider) -> None:
    started = st.session_state["exam_started_at"]
    minutes = round(exam.duration_minutes * accessibility.time_factor())

    st.markdown(f"## {exam.title}")
    st.caption(f"{exam.paper_title}")
    st.markdown(
        ui.badge(f"{exam.total_marks} marks") + ui.badge(f"{minutes} minutes"
                                                           + (" (extended time)" if accessibility.time_factor() > 1 else ""))
        + ui.badge(exam.config.difficulty),
        unsafe_allow_html=True,
    )
    st.info("In production: fullscreen mode, tab-switch detection and copy/paste restrictions will be active.",
            icon="🔒")
    if exam.status != "approved":
        st.warning("AI draft not yet reviewed by a teacher.")

    _timer(minutes)
    ui.render_sources(exam)

    section = None
    for q in exam.questions:
        if q.section != section:
            section = q.section
            st.subheader(section)
        _question(exam, q)

    if st.button("Submit exam", type="primary", use_container_width=True):
        _submit(exam, llm, int(time.time() - started))


def _question(exam: Exam, q: Question) -> None:
    key = f"ans_{exam.exam_id}_{q.number}"
    with st.container(border=True):
        st.markdown(ui.question_html(q.number, q.marks, q.question_text, q.suggested_minutes), unsafe_allow_html=True)
        if q.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
            st.radio("Your answer", q.options, index=None, key=key, label_visibility="collapsed")
        elif q.question_type == QuestionType.MULTI_SELECT:
            st.caption("Tick the four statements you think are true.")
            for i, opt in enumerate(q.options):
                st.checkbox(f"{chr(65 + i)}. {opt}", key=f"{key}_{i}")
        elif _is_list_four(q):
            for i in range(LIST_BOXES):
                st.text_input(f"Thing {i + 1}:", key=f"{key}_li{i}")
        else:
            if q.marks >= 40:
                with st.expander("Planning space (not marked)"):
                    st.text_area("Plan", key=f"{key}_plan", height=140, label_visibility="collapsed",
                                 placeholder="Jot down your ideas, structure and key phrases here...")
            height = 140 if q.marks <= 4 else 260 if q.marks <= 12 else 380
            text = st.text_area("Your answer", key=key, height=height, label_visibility="collapsed",
                                placeholder="Type your answer here...")
            words = len(text.split())
            st.caption(f"{words} word{'s' if words != 1 else ''}")


@st.fragment(run_every=1)
def _timer(duration_minutes: int) -> None:
    started = st.session_state.get("exam_started_at")
    if not started:
        return
    elapsed = int(time.time() - started)
    remaining = duration_minutes * 60 - elapsed
    c1, c2 = st.columns(2)
    c1.metric("Time elapsed", f"{elapsed // 60:02d}:{elapsed % 60:02d}")
    if remaining >= 0:
        c2.metric("Time remaining", f"{remaining // 60:02d}:{remaining % 60:02d}")
    else:
        c2.metric("Time remaining", "00:00", delta=f"{-remaining // 60} min over", delta_color="inverse")


def _collect_answers(exam: Exam) -> list[StudentAnswer]:
    answers = []
    for q in exam.questions:
        key = f"ans_{exam.exam_id}_{q.number}"
        if q.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
            choice = st.session_state.get(key)
            answers.append(StudentAnswer(number=q.number, selected_options=[choice] if choice else []))
        elif q.question_type == QuestionType.MULTI_SELECT:
            chosen = [opt for i, opt in enumerate(q.options) if st.session_state.get(f"{key}_{i}")]
            answers.append(StudentAnswer(number=q.number, selected_options=chosen))
        elif _is_list_four(q):
            items = [st.session_state.get(f"{key}_li{i}", "").strip() for i in range(LIST_BOXES)]
            text = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(items) if t)
            answers.append(StudentAnswer(number=q.number, text=text))
        else:
            answers.append(StudentAnswer(number=q.number, text=st.session_state.get(key, "")))
    return answers


def _submit(exam: Exam, llm: LLMProvider, elapsed: int) -> None:
    answers = _collect_answers(exam)
    with ui.friendly_errors("mark your exam"):
        with st.spinner("Marking your answers..."):
            result = grade_attempt(exam, st.session_state["mark_scheme"], answers, llm, elapsed)
        exam_store.save_attempt(result)
        st.session_state.setdefault("attempted_ids", set()).add(exam.exam_id)
        st.session_state.update(result=result, exam_started_at=None)
        ui.goto("results")
