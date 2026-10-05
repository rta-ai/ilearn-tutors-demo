"""Landing screen: platform branding and role choice."""
from __future__ import annotations

import streamlit as st

from config import settings
from ui import components as ui


def render() -> None:
    if settings.LOGO_PATH.exists():
        st.image(str(settings.LOGO_PATH), width=160)
    st.markdown(
        "<div class='ilt-hero'><h1>I Learn Tutors</h1>"
        "<h3>AI-Powered Exam Preparation Platform</h3>"
        "<p>Original practice papers in the real exam format, marked by AI against a mark scheme, "
        "with clear feedback on exactly where to improve.</p></div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="large")
    with left, st.container(border=True):
        st.subheader("I'm a Student")
        st.write("Choose your exam, sit a fresh practice paper and see your results and weak areas.")
        if st.button("Start as a student", type="primary", use_container_width=True, key="role_student"):
            st.session_state["role"] = "student"
            ui.goto("student_selection")
    with right, st.container(border=True):
        st.subheader("I'm a Teacher / Admin")
        st.write("Upload reference material, approve the syllabus, and review papers before students see them.")
        if st.button("Continue as teacher", use_container_width=True, key="role_teacher"):
            st.session_state["role"] = "teacher"
            ui.goto("teacher")

    st.caption("Demo: sign-in is skipped. In production, roles come from the I Learn Tutors account system.")
    with st.expander("What works in this demo"):
        st.markdown(
            "- **Working:** AQA GCSE English Language (Paper 1 and Paper 2), AI marking, feedback, weak areas, "
            "teacher review, accessibility controls, PDF export.\n"
            "- **Coming soon:** other subjects, boards and qualifications, Quick Quiz, Practice by Topic, "
            "text-to-speech, BSL, analytics and adaptive difficulty."
        )
