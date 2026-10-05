---
title: I Learn Tutors AI Exam Preparation
emoji: 📝
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.65.0
python_version: "3.11"
app_file: app.py
pinned: false
short_description: Original practice exams, AI marking and weak-area feedback
---

# I Learn Tutors: AI Exam Preparation Platform (Demo)

Built by RTA AI. Teachers upload past papers and revision guides **as reference only**. The system learns the exam
format, style and syllabus from them and writes **new, original practice papers** with the same question pattern,
marks and timing. A teacher approves the syllabus scope and every paper before students see it. Students sit the
paper, get AI marking against a mark scheme, and see their weak areas.

## Workflow

```
TEACHER                                                    STUDENT
1. Upload reference PDFs (never shown to students)
2. Approve syllabus topics  <-- human gate 1
3. Generate draft paper (original texts, official format)
4. Review: flag / edit questions, approve  <-- human gate 2
        |                                              
        v                                              
   Approved paper bank  ------------------------>  Pick subject + exam -> sit paper (timed)
                                                       -> AI marking -> score, grade,
                                                          weak areas, revision plan
```

## How it stays original, accurate and in syllabus

| Risk | Safeguard |
|---|---|
| Copying a past paper or copyrighted text | Reading extracts are written fresh. Each is compared with every reference chunk using 8-word runs. More than 3% overlap triggers one automatic rewrite, and if it still fails the paper cannot be approved. |
| Questions outside the syllabus | The model may only assess teacher-approved topics. Every question must map to one. Any that do not are flagged. |
| Wrong structure | Question numbers, types, marks, assessment objectives and timing come from [config/exam_specs.py](config/exam_specs.py), whatever the model returns. |
| Unreviewed content reaching students | Students only get papers with status `approved`. (Optional demo switch: `ALLOW_STUDENT_ON_DEMAND=true` lets a student generate a labelled draft that is queued for review.) |
| Bad line references or option lists | Validated after generation and shown to the reviewer as warnings. |

## What the demo shows

The full platform structure is visible, but only **AQA GCSE English Language (Paper 1 and Paper 2, Full Exam mode)**
generates real papers. Everything else is shown with a polished "Coming Soon" message.

| Area | Status |
|---|---|
| Landing page, student / teacher roles | Working |
| 8-step selection: country, curriculum, board, qualification, subject, paper, mode, confirm | Working (full hierarchy in [config/curriculum_data.py](config/curriculum_data.py)) |
| AQA GCSE English Language, Full Exam | Working |
| Other subjects, boards, A-Level, SATs, IGCSE, IELTS, Quick Quiz, Practice by Topic | Coming Soon |
| Accessibility: text size, high contrast, dyslexia font (OpenDyslexic), line spacing, colour overlay, extended time (+25%), reduced distraction | Working on every screen |
| Text-to-speech, BSL, multi-language, analytics, adaptive difficulty | Coming Soon |

## Supported formats

| Format | Questions |
|---|---|
| GCSE English Language Paper 1 (80 marks, 1h45) | Q1 list four (4), Q2 language (8), Q3 structure (8), Q4 evaluation (20), Q5 writing (40) |
| GCSE English Language Paper 2 (80 marks, 1h45) | Q1 choose four true (4), Q2 summary (8), Q3 language (12), Q4 compare (16), Q5 viewpoint writing (40) |
| Topic Test (any subject) | 5 or 10 mixed questions (MCQ, true/false, short answer, extended) generated from the uploaded content |

Add a format by adding a `PaperSpec` to [config/exam_specs.py](config/exam_specs.py).

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then set GOOGLE_API_KEY
streamlit run app.py
```

Get a key at https://aistudio.google.com/apikey. **The free tier allows only about 20 requests per model per day.**
One full paper costs about 3 requests and the first read of a scanned PDF about 8, so enable billing on the Google AI
project for rehearsals and the live demo.

Demo run-through: Home → Teacher → upload a PDF → Syllabus scope → Approve → Generate paper → Review & approve →
Home → Student → the 8 selection steps → Start exam → Submit → Results.

## Deploy to Hugging Face Spaces

1. Create a Space `RTAAI/ilearn-tutors-demo` with the Streamlit SDK and push this repository to it.
2. Add the secret `GOOGLE_API_KEY` under Settings → Variables and secrets.
3. Space storage is ephemeral: the reference library, syllabus, approved papers and attempts are lost on restart.
   Rebuild them before a demo.

## Project layout

| Path | Purpose |
|---|---|
| `config/settings.py` | Tunables: models, chunking, retrieval, originality, grading |
| `config/llm.py` | Provider abstraction. All Gemini-specific code lives here |
| `config/exam_specs.py` | Official paper structures (questions, marks, AOs, timing) |
| `config/prompts.py` | Versioned prompts |
| `core/schemas.py` | Pydantic data contracts (integration surface) |
| `core/document_processor.py`, `core/vector_store.py` | RAG ingestion (with OCR for scanned pages) and retrieval |
| `core/syllabus.py` | Proposed and approved syllabus scope |
| `core/exam_generator.py`, `core/mark_scheme.py` | Generation |
| `core/exam_store.py` | Drafts, review status, approved bank, attempts |
| `core/grader.py`, `core/feedback.py` | Marking and weak-area analysis |
| `config/curriculum_data.py` | The whole curriculum hierarchy, with `active` flags |
| `ui/` | Screens: landing, student selection, exam interface, results dashboard, teacher panel, accessibility |
| `utils/` | Output cleaning, originality and syllabus validation, PDF export |

## Integrating with the I Learn Tutors platform

`core/` has no Streamlit dependency.

- **API:** wrap `generate_exam`, `generate_mark_scheme` and `grade_attempt` in FastAPI endpoints. The Pydantic models in
  `core/schemas.py` serve as request and response bodies.
- **Storage:** `core/exam_store.py` and `core/syllabus.py` write JSON files. Replace them with database access
  (e.g. Supabase tables `exams`, `mark_schemes`, `syllabus`, `attempts`) behind the same functions.
- **Review workflow:** `Exam.status` (`draft`, `approved`, `rejected`), `flagged_questions` and `reviewer_note` are the
  fields a platform review UI needs.
- **Vector store:** reimplement `VectorStore` on pgvector with the same methods.
- **Model:** add a provider class in `config/llm.py` and set `LLM_PROVIDER`.

---
Built by RTA AI | AI-Powered Assessment Engine for I Learn Tutors
