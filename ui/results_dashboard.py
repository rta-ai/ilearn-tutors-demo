"""Results view: scores, per-question feedback, weak areas, revision plan."""
from __future__ import annotations

import html

import streamlit as st

from core.feedback import next_steps, source_pages_for_topic
from core.schemas import Exam, GradingResult
from ui import components as ui
from utils import pdf_exporter


def render() -> None:
    ui.page_header("Your results", "AI marking against the mark scheme, with feedback and a revision plan.")
    exam: Exam | None = st.session_state.get("exam")
    result: GradingResult | None = st.session_state.get("result")
    scheme = st.session_state.get("mark_scheme")
    if exam is None or result is None or result.exam_id != exam.exam_id:
        st.info("No results yet. Complete and submit an exam in the Student Panel.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score", f"{result.total_awarded} / {result.total_available}")
    c2.metric("Percentage", f"{result.percentage:.0f}%")
    c3.metric("Indicative grade", result.grade, help="Approximate 9-1 grade from percentage; real boundaries vary.")
    c4.metric("Time taken", f"{result.time_taken_seconds // 60}m {result.time_taken_seconds % 60}s")
    st.progress(min(1.0, result.percentage / 100))

    if result.overall_feedback:
        with st.container(border=True):
            st.markdown("**Overall feedback**")
            st.write(result.overall_feedback)

    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.subheader("Performance by area")
        for area in result.area_scores:
            pct = round(100 * area.ratio)
            colour = "#dc2626" if area.ratio < 0.5 else "#d97706" if area.ratio < 0.7 else "#16a34a"
            st.markdown(
                f"<div style='margin-bottom:.6rem'><div style='display:flex;justify-content:space-between'>"
                f"<span>{html.escape(area.area)}</span><b>{area.awarded}/{area.available} ({pct}%)</b></div>"
                f"<div style='background:rgba(128,128,128,.25);border-radius:6px;height:10px'>"
                f"<div style='width:{pct}%;background:{colour};height:10px;border-radius:6px'></div></div></div>",
                unsafe_allow_html=True,
            )
        st.caption("Red: needs work · Amber: developing · Green: secure")
    with right:
        st.subheader("Areas to work on")
        if result.weak_areas:
            for w in result.weak_areas:
                st.markdown(f":red[●] **{w}**")
        else:
            st.success("No significant weak areas: well done.")
        st.subheader("Recommended revision")
        for t in result.revision_topics:
            where = source_pages_for_topic(exam, t)
            st.markdown(f"- {t}" + (f"  \n  <small>See {where}</small>" if where else ""), unsafe_allow_html=True)

    st.subheader("Recommended next steps")
    for step in next_steps(exam, result.area_scores, result.revision_topics):
        st.markdown(f"- {step}")

    st.subheader("Question-by-question feedback")
    answers = {a.number: a for a in result.answers}
    for g in result.grades:
        q = exam.question(g.number)
        ratio = g.marks_awarded / g.marks_available if g.marks_available else 0
        icon = "✅" if ratio == 1 else "🟡" if ratio >= 0.5 else "🔴"
        with st.expander(f"{icon} Question {g.number}: {g.marks_awarded}/{g.marks_available}"
                         + (f" · {g.level}" if g.level else "")):
            if q:
                st.caption(q.question_text)
            a = answers.get(g.number)
            st.markdown("**Your answer**")
            st.text(", ".join(a.selected_options) if a and a.selected_options else (a.text if a and a.text else "(blank)"))
            if g.what_went_well:
                st.markdown(f"**What went well:** {g.what_went_well}")
            if g.what_was_missing:
                st.markdown(f"**What was missing:** {g.what_was_missing}")
            if g.how_to_improve:
                st.markdown(f"**How to improve:** {g.how_to_improve}")
            if g.auto_marked:
                st.caption("Auto-marked against the mark scheme.")
            item = scheme.item(g.number) if scheme else None
            if item:
                st.markdown("**Model answer for comparison**")
                if item.correct_options:
                    st.text("Correct: " + "; ".join(item.correct_options))
                st.text(item.model_answer)

    c1, c2 = st.columns(2)
    c1.download_button("Download results report (PDF)", pdf_exporter.export_results(exam, result),
                       file_name=f"results_{result.attempt_id}.pdf", mime="application/pdf",
                       use_container_width=True)
    if c2.button("Retake exam", use_container_width=True):
        st.session_state.update(result=None, exam_started_at=None)
        ui.goto("exam")

    with st.expander("Coming soon: progress analytics and adaptive difficulty"):
        st.info("Track your scores over time, compare topics, and get papers that adapt to your level. "
                "Available after full platform integration.", icon="🚧")

    with st.expander("Attempt record (JSON sent to the platform in production)"):
        st.json(result.model_dump(mode="json"), expanded=False)
