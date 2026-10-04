"""I Learn Tutors: AI Assessment Engine (demo).

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import logging

import streamlit as st

from config import settings

st.set_page_config(page_title=settings.APP_TITLE, page_icon="📝", layout="wide")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from config.llm import LLMError, LLMProvider, get_llm  # noqa: E402
from core.vector_store import VectorStore  # noqa: E402
from ui import components as ui  # noqa: E402
from ui import results_panel, student_panel, teacher_panel  # noqa: E402

VIEWS = ["Teacher Panel", "Student Panel", "Results"]


@st.cache_resource(show_spinner=False)
def services() -> tuple[LLMProvider, VectorStore]:
    llm = get_llm()
    return llm, VectorStore(llm)


def main() -> None:
    ui.inject_css()
    for key in ("exam", "mark_scheme", "result", "exam_started_at"):
        st.session_state.setdefault(key, None)
    if pending := st.session_state.pop("_goto", None):
        st.session_state["nav"] = pending

    with st.sidebar:
        st.markdown("## I Learn Tutors")
        st.caption("AI Assessment Engine")
        view = st.radio("Navigate", VIEWS, key="nav", label_visibility="collapsed")
        st.divider()

    try:
        llm, store = services()
    except LLMError as err:
        st.error(str(err))
        ui.sidebar_footer()
        st.stop()

    if view == "Teacher Panel":
        teacher_panel.render(store, llm)
    elif view == "Student Panel":
        student_panel.render(store, llm)
    else:
        results_panel.render()
    ui.sidebar_footer()


main()
