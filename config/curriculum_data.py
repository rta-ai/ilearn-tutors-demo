"""The complete curriculum hierarchy shown in the UI.

Every country, curriculum, board, qualification and subject is listed so the demo
shows the whole platform. Only nodes with ``active: True`` actually work; anything
else shows a polished "Coming Soon" message.

Hierarchy:  country -> curriculum -> board -> qualification -> subject -> paper
Papers link to the real exam structures in ``config/exam_specs.py`` via ``spec_key``;
``store_subject`` is the subject name used for reference documents and syllabus scope.
"""
from __future__ import annotations

CHILD_KEY = {
    "country": "curricula",
    "curriculum": "exam_boards",
    "board": "qualifications",
    "qualification": "subjects",
    "subject": "papers",
}

# (code) per GCSE subject, in the order shown to students
_GCSE_SUBJECTS = {
    "english_language": ("English Language", "8700"),
    "english_literature": ("English Literature", "8702"),
    "mathematics": ("Mathematics", "8300"),
    "combined_science": ("Combined Science: Trilogy", "8464"),
    "biology": ("Biology", "8461"),
    "chemistry": ("Chemistry", "8462"),
    "physics": ("Physics", "8463"),
    "geography": ("Geography", "8035"),
    "history": ("History", "8145"),
    "french": ("French", "8658"),
    "spanish": ("Spanish", "8698"),
    "arabic": ("Arabic", "8632"),
    "religious_studies": ("Religious Studies", "8062"),
}

_ENGLISH_PAPERS = {
    "paper_1": {
        "name": "Paper 1: Creative Reading & Writing",
        "full_name": "Paper 1: Explorations in Creative Reading and Writing",
        "duration_mins": 105,
        "total_marks": 80,
        "spec_key": "gcse_eng_p1",
        "active": True,
        "sections": [("Section A: Reading", 40), ("Section B: Writing", 40)],
    },
    "paper_2": {
        "name": "Paper 2: Writers' Viewpoints & Perspectives",
        "full_name": "Paper 2: Writers' Viewpoints and Perspectives",
        "duration_mins": 105,
        "total_marks": 80,
        "spec_key": "gcse_eng_p2",
        "active": True,
        "sections": [("Section A: Reading", 40), ("Section B: Writing", 40)],
    },
}


def _gcse_subjects() -> dict:
    subjects = {k: {"name": n, "code": c, "active": False} for k, (n, c) in _GCSE_SUBJECTS.items()}
    subjects["english_language"].update(
        active=True, store_subject="English Language", papers=_ENGLISH_PAPERS,
    )
    return subjects


def _a_level_subjects() -> dict:
    return {k: {"name": n, "active": False} for k, (n, _c) in _GCSE_SUBJECTS.items()}


CURRICULUM_DATA = {
    "uk": {
        "name": "United Kingdom",
        "active": True,
        "curricula": {
            "national": {
                "name": "National Curriculum",
                "active": True,
                "exam_boards": {
                    "aqa": {
                        "name": "AQA",
                        "active": True,
                        "qualifications": {
                            "gcse": {
                                "name": "GCSE",
                                "level": "KS4 (Years 10-11, Ages 14-16)",
                                "grading": "9-1",
                                "active": True,
                                "subjects": _gcse_subjects(),
                            },
                            "a_level": {
                                "name": "A-Level",
                                "level": "KS5 (Years 12-13, Ages 16-18)",
                                "grading": "A*-E",
                                "active": False,
                                "subjects": _a_level_subjects(),
                            },
                            "sats": {
                                "name": "SATs",
                                "level": "KS2 (Year 6, Ages 10-11)",
                                "grading": "Scaled score (100 = expected)",
                                "active": False,
                                "subjects": {},
                            },
                        },
                    },
                    "edexcel": {"name": "Pearson Edexcel", "active": False, "qualifications": {}},
                    "ocr": {"name": "OCR", "active": False, "qualifications": {}},
                    "wjec": {"name": "WJEC / Eduqas", "active": False, "qualifications": {}},
                },
            }
        },
    },
    "international": {
        "name": "International",
        "active": False,
        "curricula": {
            "cambridge": {
                "name": "Cambridge International",
                "active": False,
                "exam_boards": {
                    "cambridge": {
                        "name": "Cambridge Assessment",
                        "active": False,
                        "qualifications": {
                            "igcse": {"name": "IGCSE", "level": "Ages 14-16", "active": False, "subjects": {}},
                            "int_a_level": {
                                "name": "International A-Level", "level": "Ages 16-18", "active": False, "subjects": {},
                            },
                        },
                    }
                },
            },
            "ib": {"name": "International Baccalaureate", "active": False, "exam_boards": {}},
            "american": {"name": "American Curriculum", "active": False, "exam_boards": {}},
            "australian": {"name": "Australian Curriculum", "active": False, "exam_boards": {}},
        },
    },
}

# Exam types that are not curriculum based
OTHER_ASSESSMENTS = {
    "ielts": {"name": "IELTS", "type": "Language Proficiency", "active": False},
    "11_plus": {"name": "11+ Entrance Exam", "type": "Selective School Entry", "active": False},
    "functional_skills": {"name": "Functional Skills", "type": "Adult Education", "active": False},
}

STUDY_MODES = {
    "full_exam": {
        "name": "Full Exam",
        "description": "Timed, all questions, formal exam conditions.",
        "active": True,
    },
    "quick_quiz": {
        "name": "Quick Quiz",
        "description": "5-10 questions, untimed, with immediate feedback.",
        "active": False,
    },
    "practice_by_topic": {
        "name": "Practice by Topic",
        "description": "Choose the question types you want to practise.",
        "active": False,
    },
}

STEPS = [
    ("Country", "country"),
    ("Curriculum", "curriculum"),
    ("Exam board", "board"),
    ("Qualification", "qualification"),
    ("Subject", "subject"),
    ("Paper", "paper"),
]

COMING_SOON = {
    "country": "This region will be available after full integration.",
    "curriculum": "This curriculum will be available after full integration. Currently demonstrating with the UK National Curriculum.",
    "board": "Exam board templates are being configured. Currently demonstrating with AQA.",
    "qualification": "This qualification will be available after full integration. Currently demonstrating with AQA GCSE.",
    "subject": "This subject will be available after full integration. Currently demonstrating with English Language.",
    "paper": "This paper will be available after full integration.",
    "mode": "This study mode is coming soon. Currently demonstrating with Full Exam.",
    "empty": "Coming soon: options for this selection are being configured.",
}


def countries() -> dict:
    """Top-level choices: regions plus non-curriculum assessments."""
    top = dict(CURRICULUM_DATA)
    top["other"] = {
        "name": "Other Assessments (IELTS, 11+, Functional Skills)",
        "active": False,
        "curricula": OTHER_ASSESSMENTS,
    }
    return top


def children(level: str, node: dict) -> dict:
    return node.get(CHILD_KEY.get(level, ""), {})
