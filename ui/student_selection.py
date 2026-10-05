"""Student flow: Country -> Curriculum -> Board -> Qualification -> Subject -> Paper -> Mode -> Confirm.

Every option is shown so the whole platform is visible. Only AQA GCSE English
Language works; anything else shows a polished "Coming Soon" message.
"""
from __future__ import annotations

import time
from collections.abc import Callable

import streamlit as st

from config import curriculum_data as cd
from config import exam_specs, settings
from config.llm import LLMProvider
from core import exam_store
from core.schemas import ExamConfig
from core.vector_store import VectorStore
from ui import components as ui
from ui.teacher_panel import create_draft

TOTAL_STEPS = len(cd.STEPS) + 2


def _coming_soon(kind: str, name: str = "") -> None:
    st.info(f"**{name + ': ' if name else ''}Coming Soon.** {cd.COMING_SOON.get(kind, cd.COMING_SOON['empty'])}", icon="🚧")


def _format_label(fmt: tuple[str, str, str, int]) -> str:
    key, section, difficulty, n = fmt
    spec = exam_specs.PAPER_SPECS[key]
    if spec.questions:
        qs = spec.questions_for(section)
        return f"{section} · {sum(q.marks for q in qs)} marks · {spec.duration_for(section)} min · {difficulty}"
    return f"{n} questions · {difficulty}"


def render(services: Callable[[], tuple[LLMProvider, VectorStore] | None]) -> None:
    ui.page_header("Choose your exam", "Follow the steps below. Everything on the platform is shown; "
                                       "AQA GCSE English Language is fully working in this demo.")

    node_children = cd.countries()
    path: list[str] = []
    picked: dict[str, tuple[str, dict]] = {}

    for i, (label, level) in enumerate(cd.STEPS, start=1):
        if not node_children:
            _coming_soon("empty")
            return
        key = f"sel_{level}_{'/'.join(path)}"
        choice = st.selectbox(
            f"Step {i}: Select {label}", list(node_children), index=None, placeholder="Choose...", key=key,
            format_func=lambda k, nc=node_children, lv=level: nc[k]["name"] + (" ✓" if nc[k].get("active") and lv in ("subject", "paper") else ""),
        )
        if choice is None:
            st.progress((i - 1) / TOTAL_STEPS)
            return
        node = node_children[choice]
        picked[level] = (choice, node)
        path.append(choice)
        if not node.get("active"):
            _coming_soon(level, node["name"])
            return
        node_children = cd.children(level, node)

    # Step 7: mode
    mode_key = st.radio(
        f"Step {len(cd.STEPS) + 1}: Select mode", list(cd.STUDY_MODES), index=None, key=f"sel_mode_{'/'.join(path)}",
        format_func=lambda k: f"{cd.STUDY_MODES[k]['name']}: {cd.STUDY_MODES[k]['description']}"
        + ("" if cd.STUDY_MODES[k]["active"] else "  (Coming Soon)"),
    )
    if mode_key is None:
        st.progress((len(cd.STEPS)) / TOTAL_STEPS)
        return
    if not cd.STUDY_MODES[mode_key]["active"]:
        _coming_soon("mode", cd.STUDY_MODES[mode_key]["name"])
        return

    _confirm(picked, services)


def _confirm(picked: dict, services) -> None:
    st.progress((TOTAL_STEPS - 1) / TOTAL_STEPS)
    st.subheader(f"Step {TOTAL_STEPS}: Confirm and start")
    subject_node = picked["subject"][1]
    paper_node = picked["paper"][1]
    qual = picked["qualification"][1]
    store_subject = subject_node["store_subject"]
    spec_key = paper_node["spec_key"]

    with st.container(border=True):
        st.markdown(
            f"**{picked['country'][1]['name']}** → {picked['curriculum'][1]['name']} → **{picked['board'][1]['name']}** → "
            f"**{qual['name']}** ({qual.get('level', '')})  \n"
            f"**{subject_node['name']}** ({subject_node.get('code', '')}) · {paper_node['full_name']}  \n"
            f"{paper_node['duration_mins']} minutes · {paper_node['total_marks']} marks · grading {qual.get('grading', '')}"
        )

    formats = [f for f in exam_store.approved_formats(store_subject) if f[0] == spec_key]
    if settings.ALLOW_STUDENT_ON_DEMAND:
        spec = exam_specs.PAPER_SPECS[spec_key]
        for section in spec.sections:
            for diff in ("Foundation", "Higher"):
                fmt = (spec_key, section, diff, 0)
                if fmt not in formats:
                    formats.append(fmt)
    if not formats:
        st.warning("No approved practice paper is available for this exam yet. A teacher needs to generate and "
                   "approve one first (Teacher Panel).")
        return
    fmt = st.selectbox("Which part of the paper?", formats, format_func=_format_label)

    st.caption("The timer starts when you press Start. Answer every question, then submit.")
    if st.button("Start exam", type="primary"):
        rec = exam_store.pick_approved(store_subject, fmt, exclude=st.session_state.setdefault("attempted_ids", set()))
        if rec is None:
            rec = _generate_on_demand(services, store_subject, fmt)
        if rec is not None:
            st.session_state.update(
                exam=rec.exam, mark_scheme=rec.mark_scheme, result=None, exam_started_at=time.time(),
            )
            ui.goto("exam")


def _generate_on_demand(services, subject: str, fmt):
    if not settings.ALLOW_STUDENT_ON_DEMAND:
        st.warning("No approved paper is available for this exam yet. Please ask your teacher.")
        return None
    svc = services()
    if svc is None:
        st.error("The AI service is not configured.")
        return None
    llm, store = svc
    key, section, difficulty, n = fmt
    config = ExamConfig(subject=subject, paper_key=key, section=section, num_questions=n, difficulty=difficulty)
    with ui.friendly_errors("generate your paper"):
        exam = create_draft(config, store, llm, origin="student_on_demand")
        return exam_store.load(exam.exam_id)
    return None
