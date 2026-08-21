"""Assembly point.

Everything that has to be constructed once per process - the embedder (which
may hold a model in memory), the vector store, the lexical index, the LLM
client - is wired together here so the API layer, the CLI and the evaluation
harness all get the same object graph.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from verbatim.config import Settings, get_settings
from verbatim.embeddings import create_embedder
from verbatim.ingest.pipeline import IngestionPipeline, IngestionResult
from verbatim.llm.answer import AnswerEngine, create_client
from verbatim.logging import get_logger
from verbatim.models import Answer, DocumentRecord
from verbatim.retrieval.retriever import RetrievalResult, Retriever
from verbatim.store import DocumentCatalogue, create_store

log = get_logger(__name__)


class RagService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()

        self.embedder = create_embedder(self.settings)
        self.store = create_store(self.settings, self.embedder.dimension)
        self.catalogue = DocumentCatalogue(Path(self.settings.storage_dir) / "catalogue.sqlite3")
        self.retriever = Retriever(
            self.store,
            self.embedder,
            top_k=self.settings.top_k,
            candidate_k=self.settings.candidate_k,
            hybrid_alpha=self.settings.hybrid_alpha,
            use_mmr=self.settings.use_mmr,
            mmr_lambda=self.settings.mmr_lambda,
            min_score=self.settings.min_score,
        )
        self.pipeline = IngestionPipeline(
            self.store,
            self.embedder,
            self.catalogue,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        self.engine = AnswerEngine(
            self.retriever, create_client(self.settings), self.settings.llm_model
        )
        self._write_lock = threading.Lock()

        log.info(
            "service ready: %s embeddings (dim %d), %s store, %d chunks indexed",
            self.embedder.name,
            self.embedder.dimension,
            self.store.kind,
            self.store.count(),
        )

    # --- writes ---------------------------------------------------------
    def ingest_file(self, path: str | Path, *, title: str | None = None) -> IngestionResult:
        with self._write_lock:
            result = self.pipeline.ingest_file(path, title=title)
        self.retriever.invalidate()
        return result

    def ingest_directory(self, directory: str | Path) -> list[IngestionResult]:
        with self._write_lock:
            results = self.pipeline.ingest_directory(directory)
        self.retriever.invalidate()
        return results

    def delete_document(self, document_id: str) -> bool:
        with self._write_lock:
            removed = self.pipeline.delete(document_id)
        self.retriever.invalidate()
        return removed

    def clear(self) -> None:
        with self._write_lock:
            self.store.reset()
            self.catalogue.clear()
        self.retriever.invalidate()

    # --- reads ----------------------------------------------------------
    def documents(self, limit: int = 200, offset: int = 0) -> list[DocumentRecord]:
        return self.catalogue.list(limit=limit, offset=offset)

    def search(self, query: str, **kwargs: Any) -> RetrievalResult:
        return self.retriever.retrieve(query, **kwargs)

    def ask(self, question: str, **kwargs: Any) -> Answer:
        return self.engine.answer(question, **kwargs)

    def stats(self) -> dict[str, Any]:
        totals = self.catalogue.totals()
        return {
            "documents": totals["documents"],
            "chunks": max(totals["chunks"], self.store.count()),
            "characters": totals["characters"],
            "vector_store": self.store.kind,
            "embedding": self.embedder.describe(),
            "llm": {
                "model": self.settings.llm_model if self.engine.generative else None,
                "generative": self.engine.generative,
            },
            "retrieval": {
                "top_k": self.settings.top_k,
                "candidate_k": self.settings.candidate_k,
                "hybrid_alpha": self.settings.hybrid_alpha,
                "mmr": self.settings.use_mmr,
                "strategy": self.retriever.strategy_name(),
            },
        }


_service: RagService | None = None
_service_lock = threading.Lock()


def get_service() -> RagService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = RagService()
    return _service


def reset_service() -> None:
    """Used by the tests to force a rebuild against a fresh storage directory."""
    global _service
    with _service_lock:
        _service = None
