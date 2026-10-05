"""Application configuration.

Every tunable value lives here so the demo can be re-pointed (different model,
different chunking, different provider) without touching the core pipeline.
Provider-specific client code lives in ``config/llm.py``.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", DATA_DIR / "chroma_db"))
SAMPLE_PAPERS_DIR = DATA_DIR / "sample_papers"
OCR_CACHE_DIR = DATA_DIR / "ocr_cache"
EXAMS_DIR = DATA_DIR / "exams"
SYLLABUS_DIR = DATA_DIR / "syllabus"
ATTEMPTS_DIR = DATA_DIR / "attempts"
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

# --- LLM provider ------------------------------------------------------------
# Swap the provider by adding a class in config/llm.py and changing this value.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

GENERATION_MODEL = os.getenv("GENERATION_MODEL", "gemini-3.8-flash")
OCR_MODEL = os.getenv("OCR_MODEL", "gemini-3.5-flash-lite")  # reads scanned pages; separate model = separate quota
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = 768  # gemini-embedding-001 supports 768 / 1536 / 3072

MAX_OUTPUT_TOKENS = 16384  # includes the model's thinking tokens
THINKING_BUDGET = 2048  # 0 disables thinking (faster, lower quality)
TEMPERATURE = 0.3  # low temperature for accurate, consistent exam generation
GRADING_TEMPERATURE = 0.1

# Free tier is ~10 requests/minute: back off and retry before giving up.
REQUEST_TIMEOUT_SECONDS = 180  # a hung request must fail, not freeze a live demo
MAX_RETRIES = 4
RETRY_BASE_DELAY_SECONDS = 4.0
EMBED_BATCH_SIZE = 50

# --- Chunking ----------------------------------------------------------------
# Token targets from the spec, converted with the usual ~4 chars/token heuristic
# so we do not need a tokenizer dependency.
CHARS_PER_TOKEN = 4
CHUNK_SIZE_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 100
CHUNK_SIZE = CHUNK_SIZE_TOKENS * CHARS_PER_TOKEN
CHUNK_OVERLAP = CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN
MIN_CHUNK_CHARS = 80  # drop near-empty fragments (page numbers, headers)

# --- OCR (image-only PDF pages are transcribed with Gemini vision) -------------
MIN_PAGE_TEXT_CHARS = 40  # pages with less text than this are treated as images
OCR_PAGES_PER_CALL = 5
MIN_OCR_IMAGE_PX = 150  # ignore logos / icons smaller than this

# --- Retrieval ---------------------------------------------------------------
COLLECTION_NAME = "curriculum_chunks"
RETRIEVAL_TOP_K = 8  # chunks passed to the LLM (spec: 5-8)
RETRIEVAL_CANDIDATES_PER_QUERY = 6
# Cosine distance (0 = identical, 2 = opposite). Chunks further than this are
# treated as irrelevant; if none survive, generation is refused.
MAX_RELEVANT_DISTANCE = 0.85

# --- Human in the loop ----------------------------------------------------------
# Students only receive teacher-approved papers. Set ALLOW_STUDENT_ON_DEMAND=true (demo mode) to let a student
# generate an unreviewed draft when no approved paper exists; it is flagged and queued for teacher review.
ALLOW_STUDENT_ON_DEMAND = os.getenv("ALLOW_STUDENT_ON_DEMAND", "false").lower() == "true"
SYLLABUS_MAX_CHARS = 60000  # reference text sent to the model when proposing syllabus topics

# --- Originality (legal safety) ---------------------------------------------------
# Generated extracts must not reuse the reference material. We compare word n-grams.
ORIGINALITY_NGRAM = 8
MAX_COPIED_NGRAM_SHARE = 0.03  # more than 3% of an extract's 8-word runs found in the reference = too close

# --- Grounding validation ----------------------------------------------------
# Share of an extract's words that must appear in the cited source chunks.
MIN_EXTRACT_OVERLAP = 0.85
MIN_QUESTION_OVERLAP = 0.15

# --- Grading -----------------------------------------------------------------
# Indicative 9-1 boundaries by percentage. Real boundaries vary per series.
GRADE_BOUNDARIES = [
    (80, "9"), (72, "8"), (64, "7"), (56, "6"), (48, "5"),
    (40, "4"), (30, "3"), (20, "2"), (10, "1"), (0, "U"),
]
WEAK_AREA_THRESHOLD = 0.5  # below 50% of available marks = weak area

# --- UI ----------------------------------------------------------------------
APP_TITLE = "I Learn Tutors — AI Exam Preparation Platform"
FOOTER_TEXT = "I Learn Tutors — Powered by RTA AI"
DYSLEXIA_FONT_URL = "https://cdn.jsdelivr.net/gh/antijingoist/opendyslexic@master/compiled/OpenDyslexic-Regular.woff"
SUBJECT_CHOICES = [
    "English Language",
    "English Literature",
    "Mathematics",
    "Biology",
    "Chemistry",
    "Physics",
    "History",
    "Geography",
]
