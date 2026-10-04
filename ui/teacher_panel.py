"""Teacher view: reference library, syllabus scope, paper generation and review.

Human-in-the-loop gates:
  1. The teacher approves the syllabus topics. Generation can only use them.
  2. The teacher reviews every generated paper and mark scheme before students can get it.
"""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from config import exam_specs, settings
from config.llm import LLMProvider
from core import exam_store, syllabus
from core.document_processor import process_pdf
from core.exam_generator import generate_exam
from core.mark_scheme import generate_mark_scheme
from core.schemas import Exam, ExamConfig
from core.vector_store import VectorStore
from ui import components as ui

OTHER = "Other..."


def render(store: VectorStore, llm: LLMProvider) -> None:
    ui.page_header(
        "Teacher Panel",
        "Upload reference material, approve the syllabus scope, then review the practice papers the AI writes.",
    )
    t_lib, t_syl, t_gen, t_rev = st.tabs(
        ["1. Reference library", "2. Syllabus scope", "3. Generate paper", "4. Review & approve"]
    )
    with t_lib:
        left, right = st.columns([1, 1.3], gap="large")
        with left:
            _upload_section(store, llm)
        with right:
            _library_section(store)
    with t_syl:
        _syllabus_section(store, llm)
    with t_gen:
        _generate_section(store, llm)
    with t_rev:
        _review_section(store, llm)


# --- 1. Reference library ---------------------------------------------------------
def _upload_section(store: VectorStore, llm: LLMProvider) -> None:
    st.subheader("Upload reference material")
    st.caption(
        "Past papers and revision guides are used only as a reference for format, style and syllabus. "
        "Students never see this material, and generated papers contain original text."
    )
    choice = st.selectbox("Subject of these documents", settings.SUBJECT_CHOICES + [OTHER])
    subject = st.text_input("Subject name") if choice == OTHER else choice
    files = st.file_uploader("Reference PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("Process documents", disabled=not files or not subject):
        uploaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        stored = 0
        for f in files:
            with ui.friendly_errors(f"process {f.name}"), st.status(f"Processing {f.name}...") as status:
                status.write("Extracting text...")
                doc = process_pdf(f.getvalue(), f.name, subject.strip(), llm=llm, progress=status.write)
                status.write(f"{doc.pages} pages, {len(doc.chunks)} chunks. Embedding and storing...")
                info = store.add_document(doc, uploaded_at)
                status.update(label=f"{f.name}: {info.chunks} chunks stored", state="complete")
                stored += 1
        if stored == len(files):  # keep error messages on screen if anything failed
            st.rerun()


def _library_section(store: VectorStore) -> None:
    st.subheader("Document library")
    docs = store.list_documents()
    if not docs:
        st.caption("Nothing uploaded yet.")
        return
    for d in docs:
        c1, c2 = st.columns([5, 1])
        c1.markdown(f"**{d.filename}**  \n{d.subject} · {d.pages} pages · {d.chunks} chunks")
        if c2.button("Remove", key=f"del_{d.doc_id}"):
            store.delete_document(d.doc_id)
            st.rerun()


# --- 2. Syllabus scope -----------------------------------------------------------------
def _syllabus_section(store: VectorStore, llm: LLMProvider) -> None:
    st.subheader("Approve the syllabus scope")
    st.caption(
        "The AI proposes topics from your reference material. Edit the list so it matches the real syllabus. "
        "Papers can only be generated for approved topics, and any question outside them is flagged."
    )
    subjects = store.subjects()
    if not subjects:
        st.info("Upload reference material first.")
        return
    subject = st.selectbox("Subject", subjects, key="syl_subject")
    current = syllabus.load(subject)

    if current is None:
        st.warning("No topics yet for this subject.")
        if st.button("Propose topics from uploaded material", type="primary"):
            with ui.friendly_errors("propose syllabus topics"), st.spinner("Reading the material..."):
                syllabus.propose_topics(subject, store, llm)
                st.rerun()
        return

    st.markdown(ui.badge("Approved" if current.approved else "Draft: needs your approval"), unsafe_allow_html=True)
    text = st.text_area(
        "Syllabus topics (one per line)", "\n".join(current.topics), height=300,
        key=f"syl_text_{subject}_{current.updated_at}",
    )
    topics = [t for t in text.splitlines() if t.strip()]
    c1, c2, c3 = st.columns(3)
    if c1.button("Approve syllabus", type="primary", disabled=not topics, use_container_width=True):
        syllabus.save(subject, topics, approved=True)
        st.toast("Syllabus approved")
        st.rerun()
    if c2.button("Save as draft", use_container_width=True):
        syllabus.save(subject, topics, approved=False)
        st.rerun()
    if c3.button("Re-propose from material", use_container_width=True):
        with ui.friendly_errors("propose syllabus topics"), st.spinner("Reading the material..."):
            syllabus.propose_topics(subject, store, llm)
            st.rerun()


# --- 3. Generate ---------------------------------------------------------------------------
def _generate_section(store: VectorStore, llm: LLMProvider) -> None:
    st.subheader("Generate a practice paper")
    st.caption("Creates a new, original paper with the same structure, marks and timing as the real exam. "
               "It is saved as a draft until you approve it.")
    subjects = [s for s in store.subjects() if (syl := syllabus.load(s)) and syl.approved]
    if not subjects:
        st.info("Approve the syllabus scope for a subject first (tab 2).")
        return
    subject = st.selectbox("Subject", subjects, key="gen_subject")
    spec = st.selectbox("Paper", exam_specs.formats_for_subject(subject), format_func=lambda s: s.title)
    section, num_questions = "", 0
    if spec.sections:
        section = st.selectbox("Questions", spec.sections, help="Full paper = Q1-Q5 with the full marks and time.")
    else:
        num_questions = st.radio("Number of questions", [5, 10], horizontal=True)
    difficulty = st.radio("Difficulty", ["Foundation", "Higher"], index=1, horizontal=True)
    docs = [d for d in store.list_documents() if d.subject == subject]
    chosen = st.multiselect("Reference documents", docs, default=docs, format_func=lambda d: d.filename)

    if st.button("Generate draft paper", type="primary", disabled=not chosen):
        config = ExamConfig(
            subject=subject, paper_key=spec.key, section=section, num_questions=num_questions,
            difficulty=difficulty, doc_ids=[d.doc_id for d in chosen],
        )
        with ui.friendly_errors("generate the paper"):
            exam = create_draft(config, store, llm)
            st.session_state["review_id"] = exam.exam_id
            st.success("Draft saved. Open the 'Review & approve' tab to check it.")


def create_draft(config: ExamConfig, store: VectorStore, llm: LLMProvider, feedback: str = "",
                 origin: str = "teacher") -> Exam:
    with st.spinner("Writing the paper from the reference material..."):
        exam = generate_exam(config, store, llm, feedback=feedback, origin=origin)
    with st.spinner("Writing the mark scheme..."):
        scheme = generate_mark_scheme(exam, llm)
    exam_store.save(exam, scheme)
    return exam


# --- 4. Review & approve ----------------------------------------------------------------------
def _review_section(store: VectorStore, llm: LLMProvider) -> None:
    drafts = exam_store.list_records(status="draft")
    approved = exam_store.list_records(status="approved")
    st.subheader("Review queue")
    if not drafts:
        st.info("No drafts waiting for review.")
    else:
        ids = [r.exam.exam_id for r in drafts]
        default = ids.index(st.session_state["review_id"]) if st.session_state.get("review_id") in ids else 0
        label = {r.exam.exam_id: _label(r.exam) for r in drafts}
        chosen = st.selectbox("Draft to review", ids, index=default, format_func=label.get)
        _review_draft(exam_store.load(chosen), store, llm)

    st.divider()
    st.subheader(f"Approved paper bank ({len(approved)})")
    st.caption("Students are served papers from here only.")
    for r in approved:
        c1, c2 = st.columns([6, 1])
        c1.markdown(f"**{_label(r.exam)}**  \nApproved {r.exam.reviewed_at[:16].replace('T', ' ')} UTC")
        if c2.button("Withdraw", key=f"wd_{r.exam.exam_id}"):
            exam_store.set_status(r.exam.exam_id, "draft", note="Withdrawn from bank")
            st.rerun()


def _label(exam: Exam) -> str:
    origin = " [student-requested]" if exam.origin == "student_on_demand" else ""
    return (f"{exam.title} · {exam.config.section or str(exam.config.num_questions) + ' questions'} · "
            f"{exam.config.difficulty} · {exam.total_marks} marks · {exam.created_at[5:16].replace('T', ' ')}{origin}")


def _review_draft(rec, store: VectorStore, llm: LLMProvider) -> None:
    exam, scheme = rec.exam, rec.mark_scheme

    if exam.origin == "student_on_demand":
        st.warning("A student requested this paper and received it before review. Please check it.")
    if not exam.originality_ok:
        st.error("Originality check failed: an extract reuses wording from the reference material. "
                 "This paper cannot be approved. Reject it and regenerate.")
    for w in exam.validation_warnings:
        (st.error if w.startswith("ORIGINALITY") else st.warning)(w)

    t_paper, t_ms, t_ctx = st.tabs(["Question paper", "Mark scheme", "Reference used"])
    with t_paper:
        ui.render_exam(exam)
    with t_ms:
        if scheme:
            ui.render_mark_scheme(exam, scheme)
    with t_ctx:
        st.caption("Reference passages the AI saw. The paper's own texts are original and must not copy these.")
        st.markdown("**Approved syllabus topics:** " + ", ".join(exam.syllabus_topics))
        for c in exam.context_chunks:
            with st.expander(f"{c.source} · page {c.page}"):
                st.text(c.text)

    st.markdown("#### Your review")
    st.caption("Tick any question that is out of syllabus or unsuitable. You can also edit the wording.")
    flagged: list[int] = []
    for q in exam.questions:
        auto = q.number in exam.flagged_questions
        with st.container(border=True):
            c1, c2 = st.columns([1, 6])
            if c1.checkbox(f"Flag Q{q.number}", value=auto, key=f"flag_{exam.exam_id}_{q.number}"):
                flagged.append(q.number)
            c2.caption(f"{q.marks} marks · topic: {q.focus_topic or 'none'}"
                       + ("  ·  outside approved syllabus" if auto else ""))
            new_text = st.text_area("Question text", q.question_text, key=f"edit_{exam.exam_id}_{q.number}",
                                    height=110, label_visibility="collapsed")
            if new_text != q.question_text and st.button(f"Save edit to Q{q.number}", key=f"save_{exam.exam_id}_{q.number}"):
                exam_store.update_question_text(exam.exam_id, q.number, new_text)
                st.toast(f"Question {q.number} updated. Check the mark scheme still fits.")
                st.rerun()

    note = st.text_area("Reviewer note (sent to the AI if you reject and regenerate)",
                        key=f"note_{exam.exam_id}", placeholder="e.g. Q3 is about poetry, which is not on this paper.")
    a, b, c = st.columns(3)
    if a.button("Approve for students", type="primary", disabled=not exam.originality_ok or bool(flagged),
                use_container_width=True, help="Disabled while any question is flagged."):
        exam_store.set_status(exam.exam_id, "approved", note=note, flagged=[])
        st.session_state.pop("review_id", None)
        st.toast("Approved. Students can now receive this paper.")
        st.rerun()
    if b.button("Reject and regenerate", use_container_width=True):
        feedback = _feedback_text(exam, flagged, note)
        exam_store.set_status(exam.exam_id, "rejected", note=note, flagged=flagged)
        with ui.friendly_errors("regenerate the paper"):
            new = create_draft(exam.config, store, llm, feedback=feedback)
            st.session_state["review_id"] = new.exam_id
            st.rerun()
    if c.button("Reject", use_container_width=True):
        exam_store.set_status(exam.exam_id, "rejected", note=note, flagged=flagged)
        st.rerun()


def _feedback_text(exam: Exam, flagged: list[int], note: str) -> str:
    parts = [note.strip()] if note.strip() else []
    for n in flagged:
        q = exam.question(n)
        if q:
            parts.append(f"Question {n} was rejected as out of syllabus or unsuitable. Do not reuse this idea: "
                         f"{q.question_text[:300]}")
    return "\n".join(parts)
