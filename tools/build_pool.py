"""Build demo_pool/exams/*.json from demo_pool/authored/*.json. Offline: makes no API calls.

    .venv\\Scripts\\python tools/build_pool.py

Each paper is validated (structure, line references, syllabus topics, and an
originality check against the local reference documents if they are present).
Existing review status (approved / draft) is preserved when a paper is rebuilt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from core import pool  # noqa: E402
from core.exam_store import ExamRecord  # noqa: E402
from core.schemas import Syllabus  # noqa: E402


def local_reference_text() -> str:
    """All reference chunks from the local ChromaDB, read directly (no embedding or API calls)."""
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
        col = client.get_collection(settings.COLLECTION_NAME)
        return "\n".join(col.get(include=["documents"])["documents"] or [])
    except Exception:  # noqa: BLE001 - no local reference library: originality check is skipped
        return ""


def main() -> int:
    syllabus_file = pool.SYLLABUS_DIR / "english-language.json"
    topics = Syllabus.model_validate_json(syllabus_file.read_text(encoding="utf-8")).topics
    reference = local_reference_text()
    print(f"reference text: {len(reference):,} chars" + ("" if reference else "  (originality check SKIPPED: no local library)"))
    problems = 0
    for path in sorted(pool.AUTHORED_DIR.glob("*.json")):
        paper = pool.AuthoredPaper.model_validate_json(path.read_text(encoding="utf-8"))
        exam, scheme = pool.build(paper, topics, reference)
        target = pool.EXAMS_DIR / f"{exam.exam_id}.json"
        if target.exists():  # keep the teacher's review decision
            old = ExamRecord.model_validate_json(target.read_text(encoding="utf-8")).exam
            exam.status, exam.reviewer_note, exam.reviewed_at = old.status, old.reviewer_note, old.reviewed_at
        pool.write_exam(exam, scheme)
        words = sum(len(" ".join(s.lines).split()) for s in exam.sources)
        print(f"{exam.exam_id:14} {paper.paper_key} {exam.total_marks} marks, {exam.duration_minutes} min, "
              f"{len(exam.sources)} source(s) {words} words, status={exam.status}, originality_ok={exam.originality_ok}")
        for w in exam.validation_warnings:
            print("   WARNING:", w)
            problems += 1
    print("done" if not problems else f"done with {problems} warning(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
