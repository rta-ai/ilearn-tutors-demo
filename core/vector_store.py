"""ChromaDB persistence and retrieval.

Embeddings are computed by the configured LLM provider and passed to Chroma
explicitly, so Chroma never downloads its own embedding model.
"""
from __future__ import annotations

from collections import defaultdict

import chromadb

from config import settings
from config.llm import LLMProvider
from core.document_processor import ProcessedDocument
from core.schemas import DocumentInfo, RetrievedChunk


class NoRelevantContentError(Exception):
    """No uploaded material matches the requested exam."""


class VectorStore:
    def __init__(self, llm: LLMProvider, path: str | None = None):
        self._llm = llm
        self._client = chromadb.PersistentClient(path=str(path or settings.CHROMA_DIR))
        self._collection = self._client.get_or_create_collection(
            name=settings.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    @property
    def llm(self) -> LLMProvider:
        return self._llm

    # -- write -------------------------------------------------------------
    def has_document(self, doc_id: str) -> bool:
        return bool(self._collection.get(where={"doc_id": doc_id}, limit=1)["ids"])

    def add_document(self, doc: ProcessedDocument, uploaded_at: str) -> DocumentInfo:
        if self.has_document(doc.doc_id):
            self.delete_document(doc.doc_id)
        texts = [c.text for c in doc.chunks]
        embeddings = self._llm.embed_documents(texts)
        self._collection.add(
            ids=[c.chunk_id for c in doc.chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "doc_id": doc.doc_id,
                    "source": doc.filename,
                    "subject": doc.subject,
                    "page": c.page,
                    "pages": doc.pages,
                    "uploaded_at": uploaded_at,
                }
                for c in doc.chunks
            ],
        )
        return DocumentInfo(
            doc_id=doc.doc_id, filename=doc.filename, subject=doc.subject,
            pages=doc.pages, chunks=len(doc.chunks), uploaded_at=uploaded_at,
        )

    def delete_document(self, doc_id: str) -> None:
        self._collection.delete(where={"doc_id": doc_id})

    # -- read --------------------------------------------------------------
    def list_documents(self) -> list[DocumentInfo]:
        metas = self._collection.get(include=["metadatas"])["metadatas"] or []
        grouped: dict[str, list[dict]] = defaultdict(list)
        for m in metas:
            grouped[m["doc_id"]].append(m)
        docs = [
            DocumentInfo(
                doc_id=doc_id, filename=ms[0]["source"], subject=ms[0]["subject"],
                pages=ms[0].get("pages", 0), chunks=len(ms), uploaded_at=ms[0].get("uploaded_at", ""),
            )
            for doc_id, ms in grouped.items()
        ]
        return sorted(docs, key=lambda d: d.uploaded_at, reverse=True)

    def reference_texts(self, subject: str, doc_ids: list[str] | None = None) -> list[str]:
        """Every stored chunk for the subject, in document order (syllabus proposal and originality checks)."""
        where: dict = {"subject": subject}
        if doc_ids:
            where = {"$and": [where, {"doc_id": {"$in": doc_ids}}]}
        res = self._collection.get(where=where, include=["documents", "metadatas"])
        rows = sorted(
            zip(res["ids"], res["documents"], res["metadatas"]),
            key=lambda r: (r[2]["source"], int(r[2]["page"]), _chunk_index(r[0])),
        )
        return [r[1] for r in rows]

    def subjects(self) -> list[str]:
        return sorted({d.subject for d in self.list_documents()})

    def retrieve(
        self,
        queries: list[str],
        subject: str,
        doc_ids: list[str] | None = None,
        top_k: int = settings.RETRIEVAL_TOP_K,
    ) -> list[RetrievedChunk]:
        """Multi-query retrieval: run each query, merge, keep the best ``top_k``.

        Several queries per exam spec give broader coverage of the material
        than a single query, which matters for whole-paper generation.
        """
        where: dict = {"subject": subject}
        if doc_ids:
            where = {"$and": [where, {"doc_id": {"$in": doc_ids}}]}
        available = len(self._collection.get(where=where, include=[])["ids"])
        if not available:
            raise NoRelevantContentError(
                f"No documents uploaded for {subject}. Upload relevant curriculum PDFs in the Teacher Panel first."
            )

        best: dict[str, RetrievedChunk] = {}
        n = min(settings.RETRIEVAL_CANDIDATES_PER_QUERY, available)
        for query in queries:
            res = self._collection.query(
                query_embeddings=[self._llm.embed_query(f"{subject}: {query}")],
                n_results=n,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            for cid, text, meta, dist in zip(
                res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
            ):
                if dist > settings.MAX_RELEVANT_DISTANCE:
                    continue
                if cid not in best or dist < best[cid].distance:
                    best[cid] = RetrievedChunk(
                        chunk_id=cid, text=text, source=meta["source"], page=int(meta["page"]),
                        subject=meta["subject"], distance=float(dist),
                    )
        if not best:
            raise NoRelevantContentError(
                f"The uploaded {subject} documents do not contain content relevant to this exam. "
                "Upload material that covers it."
            )
        chunks = sorted(best.values(), key=lambda c: c.distance)[:top_k]
        # Present chunks in document order so extracts read naturally.
        return sorted(chunks, key=lambda c: (c.source, c.page, _chunk_index(c.chunk_id)))


def _chunk_index(chunk_id: str) -> int:
    try:
        return int(chunk_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0
