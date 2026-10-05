"""I Learn Tutors: AI Exam Preparation Platform (demo).

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import logging

import streamlit as st

from config import settings

st.set_page_config(page_title=settings.APP_TITLE, page_icon="📝", layout="wide")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from config.llm import LLMError, LLMProvider, get_llm  # noqa: E402
from core import pool  # noqa: E402
from core.vector_store import VectorStore  # noqa: E402
from ui import accessibility  # noqa: E402
from ui import components as ui  # noqa: E402
from ui import (  # noqa: E402
    exam_interface, landing_page, results_dashboard, student_selection, teacher_panel,
)


@st.cache_resource(show_spinner=False)
def _build_services() -> tuple[LLMProvider, VectorStore]:
    llm = get_llm()
    return llm, VectorStore(llm)


def services() -> tuple[LLMProvider, VectorStore] | None:
    """The AI services, or None when the API key is missing (screens that need it show a message)."""
    try:
        return _build_services()
    except LLMError as err:
        st.session_state["_service_error"] = str(err)
        return None


def _nav() -> None:
    role = st.session_state.get("role")
    with st.sidebar:
        st.markdown("## I Learn Tutors")
        st.caption("AI Exam Preparation Platform")
        if st.button("🏠 Home", use_container_width=True, key="nav_home"):
            ui.goto("landing")
        if role == "student":
            if st.button("Choose an exam", use_container_width=True, key="nav_select"):
                ui.goto("student_selection")
            if st.session_state.get("exam") is not None and st.button("Current exam", use_container_width=True, key="nav_exam"):
                ui.goto("exam")
            if st.session_state.get("result") is not None and st.button("My results", use_container_width=True, key="nav_results"):
                ui.goto("results")
        elif role == "teacher":
            if st.button("Teacher Panel", use_container_width=True, key="nav_teacher"):
                ui.goto("teacher")
        st.divider()


@st.cache_resource(show_spinner=False)
def _seed_pool() -> int:
    """Load the pre-authored demo papers into the runtime store (once per server start, no API calls)."""
    return pool.seed()


def main() -> None:
    _seed_pool()
    ui.inject_css()
    accessibility.init()
    for key in ("exam", "mark_scheme", "result", "exam_started_at", "role"):
        st.session_state.setdefault(key, None)
    st.session_state.setdefault("view", "landing")

    _nav()
    accessibility.render_panel()
    accessibility.apply()

    view = st.session_state["view"]
    if view == "landing":
        landing_page.render()
    elif view == "student_selection":
        student_selection.render(services)
    elif view == "exam":
        svc = services()
        exam_interface.render(svc[0] if svc else None)
    elif view == "results":
        results_dashboard.render()
    elif view == "teacher":
        svc = services()
        if svc is None:
            st.error(st.session_state.get("_service_error", "The AI service is not configured."))
        else:
            teacher_panel.render(svc[1], svc[0])

    ui.main_footer()
    ui.sidebar_footer()


main()
