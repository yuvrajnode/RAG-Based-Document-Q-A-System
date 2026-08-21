"""Ingestion: file in, indexed chunks out."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from verbatim.embeddings.base import Embedder
from verbatim.ingest.chunking import Chunker
from verbatim.ingest.loaders import SUPPORTED_EXTENSIONS, load_document
from verbatim.logging import get_logger
from verbatim.models import DocumentRecord, stable_id
from verbatim.store.base import VectorStore
from verbatim.store.catalogue import DocumentCatalogue

log = get_logger(__name__)


@dataclass(slots=True)
class IngestionResult:
    record: DocumentRecord
    took_ms: int
    replaced: bool


class IngestionPipeline:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        catalogue: DocumentCatalogue,
        *,
        chunk_size: int = 900,
        chunk_overlap: int = 150,
    ):
        self.store = store
        self.embedder = embedder
        self.catalogue = catalogue
        self.chunker = Chunker(chunk_size, chunk_overlap)

    def ingest_file(self, path: str | Path, *, title: str | None = None) -> IngestionResult:
        started = time.perf_counter()
        path = Path(path)
        document = load_document(path, title=title)

        # Content-addressed: the same bytes under a different filename resolve to
        # the same document id, so re-uploading replaces rather than duplicates.
        document_id = stable_id(document.text)
        existing = self.catalogue.get(document_id)
        if existing is not None:
            self.store.delete_document(document_id)

        chunks = self.chunker.split(document, document_id)
        if not chunks:
            raise ValueError(f"{path.name} produced no chunks")

        vectors = self.embedder.embed_documents([chunk.text for chunk in chunks])
        self.store.add(chunks, vectors, document.title)

        record = DocumentRecord(
            id=document_id,
            title=document.title,
            source_type=document.source_type,
            chunk_count=len(chunks),
            char_count=len(document.text),
            metadata={
                **document.metadata,
                "pages": len({c.page for c in chunks if c.page is not None}) or None,
                "embedding_model": self.embedder.model,
            },
        )
        if existing is not None:
            record.created_at = existing.created_at
        self.catalogue.upsert(record)

        took = int((time.perf_counter() - started) * 1000)
        log.info(
            "ingested %s: %d chunks, %d chars in %dms", path.name, len(chunks), record.char_count, took
        )
        return IngestionResult(record=record, took_ms=took, replaced=existing is not None)

    def ingest_directory(self, directory: str | Path, *, recursive: bool = True) -> list[IngestionResult]:
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(directory)
        pattern = "**/*" if recursive else "*"
        results: list[IngestionResult] = []
        for path in sorted(directory.glob(pattern)):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                results.append(self.ingest_file(path))
            except Exception as exc:
                # One unreadable file in a folder of two hundred should not abort
                # the run; the caller gets a partial result and the log says why.
                log.error("skipping %s: %s", path.name, exc)
        return results

    def delete(self, document_id: str) -> bool:
        removed_chunks = self.store.delete_document(document_id)
        removed_record = self.catalogue.delete(document_id)
        if removed_chunks or removed_record:
            log.info("deleted document %s (%d chunks)", document_id, removed_chunks)
        return removed_record or bool(removed_chunks)
