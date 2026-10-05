# CLAUDE.md

> Brief v2 (2026-10-04): show the whole platform, make one subject work. See "Platform shell" below.

Original-practice-paper generator (Streamlit + Gemini + ChromaDB) for the client I Learn Tutors. The live client
demo is on **7 October 2026**. Original brief: `CLAUDE_CODE_PROMPT_ILearnTutors_Demo.md` (superseded where this file
differs).

## Commands
- Run: `.venv\Scripts\streamlit run app.py`
- Install: `.venv\Scripts\pip install -r requirements.txt` (Python 3.11 venv in `.venv/`)
- Key: `GOOGLE_API_KEY` in `.env` (never commit; `.env.example` is the template)

## Product rules (from the client, 2026-10-04)
- Uploaded papers are **reference only**. Generated papers must be original: same pattern, marks and timing, new texts
  and questions. Never copy reference text (legal risk). `utils/validators.copied_share` enforces this with 8-word runs.
- A student picks subject + exam, gets a paper from the **teacher-approved bank**, sits it, and gets results with weak
  areas highlighted.
- **Human in the loop**: (1) teacher approves the syllabus topics (`core/syllabus.py`), generation refuses without
  them and flags questions outside them; (2) teacher reviews and approves each draft (`Exam.status`) before students
  get it. `ALLOW_STUDENT_ON_DEMAND=true` is a demo-only escape hatch (labelled unreviewed drafts, queued for review).

## Demo pool (authored offline)
- **Do not call Gemini without the user's explicit approval** (free quota is ~20 requests/day/model and was drained once).
  Test with fake LLMs. Claude writes content; Gemini only marks student answers at demo time.
- Papers live in `demo_pool/authored/*.json` (AuthoredPaper in `core/pool.py`); `tools/build_pool.py` builds them into
  `demo_pool/exams/` as drafts, validated offline. `core/rubrics.py` holds our own levels-based marking criteria.
- `pool.seed()` runs on app start; `pool.export()` ("Save review decisions to the demo pool") persists approvals, pins and
  syllabus. Pool records never contain reference-document text (`context_chunks` is stripped).
- Pins: `exam_store.set_pin / get_pins` (`data/pins.json`); a pinned paper is served to every student of that format,
  withdrawing a paper unpins it.
- The syllabus in `demo_pool/syllabus/` ships UNAPPROVED; a human must approve it in the Teacher Panel.

## Platform shell (brief v2)
- Navigation is `st.session_state["view"]`: landing, student_selection, exam, results, teacher (`ui.components.goto`).
- `config/curriculum_data.py` holds the full hierarchy; nodes without `active: True` show Coming Soon. English
  Language papers link to `exam_specs` via `spec_key` and to the reference store via `store_subject`.
- `ui/accessibility.py`: settings in `a11y_*` session keys, injected as CSS on every screen. Dyslexia font loads from the
  jsDelivr GitHub mirror of OpenDyslexic (`settings.DYSLEXIA_FONT_URL`). Streamlit's icon font lives on `<span>`s, so the
  font override targets text elements only.
- Quick Quiz and Practice by Topic are Coming Soon. Plan: Quick Quiz reuses questions from approved papers (reviewed and
  free of extra generation cost), with objective questions marked instantly and written answers in one call.
- Not yet built from the v2 brief: Quick Quiz / Practice by Topic, per-question Approve/Edit/Reject plus a question bank
  (teacher review is per paper with per-question flag and edit), placeholder analytics charts.

## Decisions that differ from the brief (deliberate)
- `google-genai` SDK, `gemini-embedding-001` (768 dims). `gemini-2.5-flash` returns 404 for new keys; default
  `GENERATION_MODEL=gemini-3.8-flash`, `OCR_MODEL=gemini-3.5-flash-lite` (separate models = separate quotas).
- `pypdf` instead of PyPDF2.
- The LLM returns **structured JSON** validated against the `*Draft` models in `core/schemas.py`; `clean_model()`
  strips markdown from every string field.
- Gemini-specific code lives in `config/llm.py`. `config/settings.py` holds config only.
- `config/exam_specs.py` is the source of truth for question numbers, types, marks and timing; it overrides the model.
- Objective questions are marked locally; written answers go to Gemini in one batched call.

## Conventions
- `core/` must stay free of Streamlit imports so it can move into the main platform's API.
- User-facing errors: raise `LLMError` / `DocumentError` / `NoRelevantContentError` / `SyllabusNotApprovedError`
  with a friendly message; the UI wraps actions in `ui.components.friendly_errors`.
- Bump `PROMPT_VERSION` in `config/prompts.py` when a prompt changes.
- Navigate views with `ui.components.goto(view)`; never set `st.session_state["nav"]` after the radio is rendered.
- Runtime data (`data/chroma_db`, `ocr_cache`, `exams`, `syllabus`, `attempts`) and `data/sample_papers/*.pdf` are
  gitignored: they contain third-party reference material.

## Learned the hard way
- The sample booklet is ~70% screenshot pages; `document_processor` OCRs image-only pages with Gemini vision and caches
  the text in `data/ocr_cache/`. Without OCR only 20k of 73k characters are readable. Page 16 refuses to transcribe.
- **Free-tier quota is ~20 requests/day per model.** `DailyQuotaError` fires immediately rather than retrying. A full
  run is ~3 calls, a first scanned-PDF upload ~8. Enable billing before rehearsals and the demo.
- `gemini-3.7-flash` took 153 s for a full Paper 1 and one mark-scheme call hung for 46 min before
  `REQUEST_TIMEOUT_SECONDS` was added. Serving from the approved bank avoids live generation latency during the demo:
  generate and approve papers beforehand.
- Verified live (Paper 1 full paper, gemini-3.7-flash): original extract, 0.0% overlap with the reference, 80 marks /
  105 min, official stems, topics all inside the approved syllabus, usable mark scheme.
- Paper 2 Q1 (choose four) needed a stricter prompt plus `_lift_statements` repair; **not yet re-verified live**.

## Next steps
0. Human review: approve the syllabus, review the four pool papers, pin/approve, then "Save review decisions" and commit demo_pool/.
1. Build Quick Quiz and Practice by Topic, and per-question teacher actions with a question bank.
2. Enable billing, then live-test `gcse_eng_p2` (Q1 should have 8 options) and the Topic Test format.
3. Click through the Streamlit UI by hand: syllabus approve, generate, review (flag/edit/approve/reject), student attempt,
   results, PDF downloads. Only the offline AppTest render checks have been run.
4. Pre-generate and approve a few papers for demo day; deploy to HF Space `RTAAI/ilearn-tutors-demo` with the
   `GOOGLE_API_KEY` secret.
