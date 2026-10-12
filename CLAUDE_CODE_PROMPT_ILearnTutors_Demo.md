# I Learn Tutors — AI Exam Preparation System (Demo v2)
## Updated Comprehensive Prompt for Claude Code

---

## STRATEGY: Show Everything, One Subject Works

Build a complete exam preparation platform UI showing ALL levels, boards, subjects, and accessibility options — but only **GCSE English Language (AQA, Paper 1)** generates real exams using RAG. All other options are visible but show "Coming Soon — Available after full integration" when selected. This demonstrates the full system architecture while proving the AI engine works.

---

## TECH STACK

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| LLM | Google Gemini 2.5 Flash (free tier) |
| Embeddings | Google Gemini text-embedding-004 |
| Vector Store | ChromaDB (persistent, local) |
| PDF Processing | PyPDF2 + LangChain text splitters |
| Frontend | Streamlit |
| Deployment | Hugging Face Spaces |
| Version Control | GitHub (private repo: rta-ai/ilearn-tutors-demo) |

---

## PROJECT STRUCTURE

```
ilearn-tutors-demo/
├── app.py                          # Main entry point
├── requirements.txt
├── .env.example
├── README.md
├── config/
│   ├── __init__.py
│   ├── settings.py                 # API keys, model config, chunk settings
│   ├── prompts.py                  # All LLM prompt templates
│   └── curriculum_data.py          # Complete curriculum hierarchy (ALL levels, boards, subjects)
├── core/
│   ├── __init__.py
│   ├── document_processor.py       # PDF upload, extract, chunk
│   ├── vector_store.py             # ChromaDB operations
│   ├── exam_generator.py           # RAG-based exam generation
│   ├── mark_scheme.py              # Mark scheme generation
│   ├── grader.py                   # AI grading engine
│   └── feedback.py                 # Feedback + weak area analysis
├── ui/
│   ├── __init__.py
│   ├── landing_page.py             # Welcome screen with platform branding
│   ├── student_selection.py        # Level → Board → Subject → Topic selection
│   ├── teacher_panel.py            # Upload content + generate exams
│   ├── exam_interface.py           # Student takes the exam
│   ├── results_dashboard.py        # Results, feedback, recommendations
│   ├── accessibility.py            # Accessibility controls
│   └── components.py               # Reusable styled components
├── utils/
│   ├── __init__.py
│   ├── text_cleaner.py             # Strip markdown from LLM output
│   └── pdf_exporter.py             # Export exams/results as PDF
├── data/
│   ├── chroma_db/                  # Vector store (gitignored)
│   └── sample_papers/              # GCSE English Language revision booklet
└── assets/
    └── logo.png                    # I Learn Tutors / RTA AI branding
```

---

## CURRICULUM DATA STRUCTURE (config/curriculum_data.py)

This file defines the ENTIRE curriculum hierarchy. ALL options show in the UI. Only items marked `active: True` actually work in the demo.

```python
CURRICULUM_DATA = {
    "UK": {
        "name": "United Kingdom",
        "curricula": {
            "national": {
                "name": "National Curriculum",
                "exam_boards": {
                    "aqa": {
                        "name": "AQA",
                        "qualifications": {
                            "gcse": {
                                "name": "GCSE",
                                "level": "KS4 (Years 10-11, Ages 14-16)",
                                "grading": "9-1",
                                "subjects": {
                                    "english_language": {
                                        "name": "English Language",
                                        "code": "8700",
                                        "active": True,  # ← THIS ONE WORKS IN DEMO
                                        "papers": {
                                            "paper_1": {
                                                "name": "Paper 1: Explorations in Creative Reading and Writing",
                                                "duration_mins": 105,
                                                "total_marks": 80,
                                                "sections": {
                                                    "section_a": {
                                                        "name": "Section A: Reading",
                                                        "marks": 40,
                                                        "questions": [
                                                            {"q_num": 1, "type": "list_retrieval", "marks": 4, "time_mins": 5, "ao": "AO1", "instruction": "List four things from this part of the source about [topic]"},
                                                            {"q_num": 2, "type": "language_analysis", "marks": 8, "time_mins": 10, "ao": "AO2", "instruction": "How does the writer use language to [effect]?"},
                                                            {"q_num": 3, "type": "structural_analysis", "marks": 8, "time_mins": 15, "ao": "AO2", "instruction": "How does the writer use structure to [effect]?"},
                                                            {"q_num": 4, "type": "evaluation", "marks": 20, "time_mins": 20, "ao": "AO4", "instruction": "To what extent do you agree? [statement about the text]"}
                                                        ]
                                                    },
                                                    "section_b": {
                                                        "name": "Section B: Writing",
                                                        "marks": 40,
                                                        "questions": [
                                                            {"q_num": 5, "type": "extended_writing", "marks": 40, "time_mins": 45, "ao": "AO5/AO6", "instruction": "Write a description/narrative based on [prompt]"}
                                                        ]
                                                    }
                                                }
                                            },
                                            "paper_2": {
                                                "name": "Paper 2: Writers' Viewpoints and Perspectives",
                                                "duration_mins": 105,
                                                "total_marks": 80,
                                                "sections": {
                                                    "section_a": {
                                                        "name": "Section A: Reading",
                                                        "marks": 40,
                                                        "questions": [
                                                            {"q_num": 1, "type": "true_false", "marks": 4, "time_mins": 5, "ao": "AO1", "instruction": "Choose four statements that are TRUE"},
                                                            {"q_num": 2, "type": "summary", "marks": 8, "time_mins": 10, "ao": "AO1", "instruction": "Write a summary of differences between the sources"},
                                                            {"q_num": 3, "type": "language_analysis", "marks": 12, "time_mins": 15, "ao": "AO2", "instruction": "How does the writer use language to [effect]?"},
                                                            {"q_num": 4, "type": "comparison", "marks": 16, "time_mins": 20, "ao": "AO3", "instruction": "Compare how the writers convey their viewpoints"}
                                                        ]
                                                    },
                                                    "section_b": {
                                                        "name": "Section B: Writing",
                                                        "marks": 40,
                                                        "questions": [
                                                            {"q_num": 5, "type": "viewpoint_writing", "marks": 40, "time_mins": 45, "ao": "AO5/AO6", "instruction": "Write to express a viewpoint (article/letter/speech/essay)"}
                                                        ]
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    "english_literature": {"name": "English Literature", "code": "8702", "active": False},
                                    "mathematics": {"name": "Mathematics", "code": "8300", "active": False},
                                    "combined_science": {"name": "Combined Science: Trilogy", "code": "8464", "active": False},
                                    "biology": {"name": "Biology", "code": "8461", "active": False},
                                    "chemistry": {"name": "Chemistry", "code": "8462", "active": False},
                                    "physics": {"name": "Physics", "code": "8463", "active": False},
                                    "geography": {"name": "Geography", "code": "8035", "active": False},
                                    "history": {"name": "History", "code": "8145", "active": False},
                                    "french": {"name": "French", "code": "8658", "active": False},
                                    "spanish": {"name": "Spanish", "code": "8698", "active": False},
                                    "arabic": {"name": "Arabic", "code": "8632", "active": False},
                                    "religious_studies": {"name": "Religious Studies", "code": "8062", "active": False}
                                }
                            },
                            "a_level": {
                                "name": "A-Level",
                                "level": "KS5 (Years 12-13, Ages 16-18)",
                                "grading": "A*-E",
                                "subjects": {
                                    # Same subject keys, all active: False for demo
                                }
                            },
                            "sats": {
                                "name": "SATs",
                                "level": "KS2 (Year 6, Ages 10-11)",
                                "grading": "Scaled Score (100 = expected)",
                                "subjects": {}
                            }
                        }
                    },
                    "edexcel": {"name": "Pearson Edexcel", "qualifications": {}},  # Structure exists, no active subjects
                    "ocr": {"name": "OCR", "qualifications": {}},
                    "wjec": {"name": "WJEC / Eduqas", "qualifications": {}}
                }
            }
        }
    },
    "International": {
        "name": "International",
        "curricula": {
            "cambridge": {
                "name": "Cambridge International",
                "exam_boards": {
                    "cambridge": {
                        "name": "Cambridge Assessment",
                        "qualifications": {
                            "igcse": {"name": "IGCSE", "level": "Ages 14-16", "subjects": {}},
                            "int_a_level": {"name": "International A-Level", "level": "Ages 16-18", "subjects": {}}
                        }
                    }
                }
            },
            "ib": {"name": "International Baccalaureate", "exam_boards": {}},
            "american": {"name": "American Curriculum", "exam_boards": {}},
            "australian": {"name": "Australian Curriculum", "exam_boards": {}}
        }
    }
}

# Other exam types (not curriculum-based)
OTHER_ASSESSMENTS = {
    "ielts": {"name": "IELTS", "type": "Language Proficiency", "active": False},
    "11_plus": {"name": "11+ Entrance Exam", "type": "Selective School Entry", "active": False},
    "functional_skills": {"name": "Functional Skills", "type": "Adult Education", "active": False}
}
```

---

## UI FLOW — WHAT THE USER SEES

### Screen 1: Landing Page (landing_page.py)
- I Learn Tutors logo and branding
- "AI-Powered Exam Preparation Platform"
- Two role buttons: "I'm a Student" | "I'm a Teacher/Admin"
- Accessibility toolbar at top right (always visible):
  - Font size slider (Small / Medium / Large / Extra Large)
  - High contrast toggle (ON/OFF)
  - "Audio Support" badge showing "Available" (placeholder for future)
  - "BSL Support" badge showing "Coming Soon"
  - Dyslexia-friendly font toggle (switches to OpenDyslexic font)

### Screen 2: Student Selection Flow (student_selection.py)
Step-by-step dropdown selection:

**Step 1 — Select Country**
Dropdown: United Kingdom | International
(Both show as options)

**Step 2 — Select Curriculum**
If UK: National Curriculum
If International: Cambridge International | IB | American | Australian

**Step 3 — Select Exam Board**
If National Curriculum: AQA | Pearson Edexcel | OCR | WJEC / Eduqas
(All show; selecting non-AQA shows "Coming Soon" message)

**Step 4 — Select Qualification**
If AQA: GCSE | A-Level | SATs
(All show; only GCSE proceeds)

**Step 5 — Select Subject**
If GCSE: English Language ✓ | English Literature | Mathematics | Combined Science | Biology | Chemistry | Physics | Geography | History | French | Spanish | Arabic | Religious Studies
(All listed; only English Language works — others show "This subject will be available after full integration. Currently demonstrating with English Language.")

**Step 6 — Select Paper**
If English Language: Paper 1: Creative Reading & Writing | Paper 2: Writers' Viewpoints & Perspectives
(Both show; Paper 1 works for demo, Paper 2 can also work if time permits since the revision booklet covers both)

**Step 7 — Select Mode**
- Full Exam (timed, all questions, formal)
- Quick Quiz (5-10 questions, untimed, immediate feedback)
- Practice by Topic (choose specific question types to practice)

**Step 8 — Confirm and Start**
Summary card showing all selections + "Start Exam" button

### Screen 3: Teacher/Admin Panel (teacher_panel.py)
- Upload curriculum content (PDF upload → RAG pipeline)
- View uploaded documents and chunk status
- Generate exam manually (select subject, paper, difficulty)
- Review generated questions before publishing
- "Approve" / "Edit" / "Reject" buttons on each question
- View question bank (list of all generated and approved questions)

### Screen 4: Exam Interface (exam_interface.py)
Clean exam layout matching real GCSE format:
- Header: Subject, Paper, Duration, Total Marks
- Timer (counts up for demo; can be set to count down)
- Questions displayed with clear mark allocation: "Q1 [4 marks]"
- Source text displayed in a bordered box (extracted from RAG content)
- Input types per question:
  - Q1 (List): 4 text input fields ("Thing 1:", "Thing 2:", etc.)
  - Q2 (Language): Large text area with word count
  - Q3 (Structure): Large text area with word count
  - Q4 (Evaluation): Large text area with word count
  - Q5 (Writing): Large text area with word count and planning space
- "Submit Exam" button
- Anti-cheating notice: "In production: fullscreen mode, tab-switch detection, copy/paste restrictions will be active" (text banner only for demo)
- Accessibility: font size applies to all text, high contrast applies to all elements

### Screen 5: Results Dashboard (results_dashboard.py)
After submission:
- Score summary card: Total marks / Available marks, Percentage, Estimated Grade
- Per-question breakdown:
  - Question text (collapsed)
  - Student's answer
  - Marks awarded / Marks available
  - AI feedback: what was good, what was missing, how to improve
  - Model answer for comparison
- Weak areas section: "Based on your performance, focus on: [topics]"
- Recommended next steps: "Practice more [question type] questions" / "Review [topic]"
- Download results as PDF button

---

## ACCESSIBILITY FEATURES (ui/accessibility.py)

These must be visible and functional in the demo:

```python
ACCESSIBILITY_OPTIONS = {
    "font_size": {
        "label": "Text Size",
        "options": ["Small (14px)", "Medium (16px)", "Large (20px)", "Extra Large (24px)"],
        "default": "Medium (16px)",
        "status": "active"  # Works in demo
    },
    "high_contrast": {
        "label": "High Contrast Mode",
        "type": "toggle",
        "default": False,
        "status": "active"  # Works in demo
    },
    "dyslexia_font": {
        "label": "Dyslexia-Friendly Font",
        "type": "toggle",
        "default": False,
        "status": "active"  # Works in demo — switches to OpenDyslexic
    },
    "line_spacing": {
        "label": "Line Spacing",
        "options": ["Normal", "1.5x", "2x"],
        "default": "Normal",
        "status": "active"  # Works in demo
    },
    "text_to_speech": {
        "label": "Read Aloud (Text-to-Speech)",
        "type": "toggle",
        "default": False,
        "status": "coming_soon"  # Shows as option but displays "Coming Soon" badge
    },
    "bsl_support": {
        "label": "BSL (British Sign Language) Support",
        "type": "toggle",
        "default": False,
        "status": "coming_soon"
    },
    "screen_reader": {
        "label": "Screen Reader Compatible",
        "type": "info",
        "status": "active",  # Semantic HTML ensures this works
        "note": "This platform uses semantic markup for screen reader compatibility"
    },
    "colour_overlay": {
        "label": "Colour Overlay",
        "options": ["None", "Yellow", "Blue", "Green", "Pink"],
        "default": "None",
        "status": "active"  # Works in demo — applies tinted overlay
    },
    "extended_time": {
        "label": "Extended Time (25% extra)",
        "type": "toggle",
        "default": False,
        "status": "active"  # Works in demo — adds 25% to timer
    },
    "reduced_distraction": {
        "label": "Reduced Distraction Mode",
        "type": "toggle",
        "default": False,
        "status": "active"  # Hides sidebar, simplifies UI
    }
}
```

Implement accessibility as a **persistent sidebar panel** or **floating toolbar** that stays visible on every screen. When a student changes font size, it immediately applies to all text on screen. Use Streamlit's `st.markdown` with custom CSS to inject these styles dynamically.

---

## RAG PIPELINE — CORE ENGINE

Same as v1 prompt but with this critical addition:

**When generating questions, the prompt must include the exam template structure:**

```
You are an experienced AQA GCSE English Language examiner.

EXAM SPECIFICATION:
- Paper: Paper 1 — Explorations in Creative Reading and Writing
- Section: Section A — Reading
- Total Section Marks: 40
- Assessment Objectives: AO1 (retrieve info), AO2 (analyse language/structure), AO4 (evaluate critically)

QUESTION TEMPLATE (generate exactly this structure):
- Q1: List four things from the source about [topic]. [4 marks]
  → 4 short factual statements from the source text
- Q2: How does the writer use language to [effect]? [8 marks]
  → Reference specific lines, identify techniques (simile, metaphor, etc.)
- Q3: How does the writer use structure to [effect]? [8 marks]
  → Analyse beginning/middle/end, shifts in focus, perspective changes
- Q4: [Statement about the text]. To what extent do you agree? [20 marks]
  → Evaluative question requiring evidence-based argument

SOURCE MATERIAL (generate questions ONLY from this text):
---
{retrieved_chunks_from_chromadb}
---

RULES:
1. Questions must reference THIS source text only — no general knowledge
2. Include specific line references where the source text has line numbers
3. Use formal exam language — clear, unambiguous, professional
4. Do NOT reproduce existing exam questions — create original questions inspired by the content
5. Output in clean plain text — NO markdown, NO asterisks, NO bold markers
6. Each question must specify its mark allocation
7. Q4 must begin with a student's statement about the text that the candidate evaluates

Generate the exam questions now:
```

---

## WHAT SHOWS "COMING SOON" vs WHAT WORKS

| Feature | Demo Status | What User Sees |
|---|---|---|
| Country/Board/Subject selection UI | All options visible | Full dropdowns with all choices |
| GCSE English Language (AQA) Paper 1 | **FULLY WORKING** | Complete exam generation, grading, feedback |
| GCSE English Language Paper 2 | Partially working (if time) | May work with same RAG content |
| All other subjects | Coming Soon | "Available after full integration" message |
| Non-AQA exam boards | Coming Soon | "Exam board templates being configured" message |
| A-Level, SATs, IGCSE, IELTS | Coming Soon | Visible in dropdown, message when selected |
| Font size adjustment | **WORKING** | Immediately changes all text |
| High contrast mode | **WORKING** | Inverts/adjusts colours |
| Dyslexia-friendly font | **WORKING** | Switches to OpenDyslexic |
| Line spacing | **WORKING** | Adjusts spacing |
| Colour overlay | **WORKING** | Applies tinted overlay |
| Extended time | **WORKING** | Adds 25% to exam timer |
| Reduced distraction mode | **WORKING** | Simplifies UI |
| Text-to-speech | Coming Soon | Badge visible, not functional |
| BSL support | Coming Soon | Badge visible, not functional |
| PDF upload (RAG) | **WORKING** | Teacher uploads content |
| Exam generation from RAG | **WORKING** | Generates questions from uploaded PDF |
| Mark scheme generation | **WORKING** | Generates model answers + criteria |
| AI grading | **WORKING** | Grades answers against mark scheme |
| Feedback + weak areas | **WORKING** | Shows improvement recommendations |
| Teacher review workflow | **WORKING** | Approve/Edit/Reject buttons |
| Anti-cheating (fullscreen, tab detect) | Placeholder | Text notice only |
| Adaptive difficulty | Coming Soon | Mentioned in UI, not functional |
| Analytics dashboard | Coming Soon | Placeholder charts |
| Multi-language | Coming Soon | Language selector visible |
| PDF export of results | **WORKING** | Download button |

---

## IMPORTANT CONSTRAINTS

1. **RAG ONLY** — Never generate from Gemini's general knowledge. Always retrieve from ChromaDB.
2. **Clean Output** — Strip ALL markdown formatting from LLM responses.
3. **Real Exam Format** — Match the actual AQA GCSE English Language paper structure exactly.
4. **Model Agnostic** — Keep Gemini-specific code in config/settings.py only.
5. **Accessibility First** — Font size, contrast, and dyslexia font must work on EVERY screen.
6. **Coming Soon ≠ Broken** — Non-working features show a polished "Coming Soon" message, not an error.
7. **Professional Branding** — "I Learn Tutors — Powered by RTA AI" in footer.
8. **No Hardcoded Exam Content** — All questions come from RAG. System works with ANY uploaded PDF.

---

## BUILD ORDER

| Day | What to Build | Test With |
|---|---|---|
| Day 1 | config/ (settings, curriculum_data, prompts) + core/document_processor.py + core/vector_store.py | Upload English Language PDF, verify chunks stored |
| Day 2 | core/exam_generator.py + core/mark_scheme.py + core/grader.py + core/feedback.py | Generate Paper 1 questions, verify quality |
| Day 3 | ui/landing_page.py + ui/student_selection.py + ui/exam_interface.py + ui/accessibility.py | Full UI flow with working accessibility |
| Day 4 | ui/results_dashboard.py + ui/teacher_panel.py + utils/pdf_exporter.py + polish + deploy | End-to-end test, deploy to HF Spaces |

---

## SUCCESS CRITERIA

The demo succeeds if it can:
1. ✅ Show the complete platform structure (all levels, boards, subjects)
2. ✅ Upload a GCSE English PDF and process it via RAG
3. ✅ Student selects: UK → National Curriculum → AQA → GCSE → English Language → Paper 1
4. ✅ Generate 4 exam questions matching the real GCSE format from the uploaded content
5. ✅ Generate corresponding mark scheme
6. ✅ Student answers questions in a clean exam interface
7. ✅ AI grades answers and provides meaningful feedback
8. ✅ Show weak areas and recommendations
9. ✅ Accessibility controls work (font size, contrast, dyslexia font)
10. ✅ Non-working subjects show polished "Coming Soon" messages
11. ✅ Teacher can review and approve/reject generated questions
12. ✅ Export results as PDF
13. ✅ Look professional during a live demo call on 7 October 2026

---

**START BUILDING. Begin with config/curriculum_data.py and config/settings.py, then the RAG pipeline. Test with the GCSE English Language PDF the client shared.**