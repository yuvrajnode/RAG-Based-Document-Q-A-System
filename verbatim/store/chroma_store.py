"""ChromaDB backend.

Chroma is configured with cosine space and given already-normalised vectors, so
its distance is 1 - dot and similarity is recovered as 1 - distance. Embeddings
are always supplied explicitly; Chroma's default embedding function is never
used, because the provider choice belongs to this project's configuration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import numpy as np

from verbatim.logging import get_logger
from verbatim.models import Chunk
from verbatim.store.base import SearchHit, StoredChunk, VectorStore

log = get_logger(__name__)

_BATCH = 512  # Chroma is happiest well under its max batch size


class ChromaVectorStore(VectorStore):
    kind = "chroma"

    def __init__(self, path: str | Path, collection: str = "documents", dimension: int = 384):
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as exc:  # pragma: no cover - depends on the install extra
            raise RuntimeError(
                "chromadb is not installed. Run `pip install -e '.[chroma]'` "
                "or set VERBATIM_VECTOR_STORE=numpy."
            ) from exc

        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._dimension = dimension
        self._client = chromadb.PersistentClient(
            path=str(self.path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine", "hnsw:construction_ef": 200, "hnsw:M": 32},
        )
        log.info("chroma collection %r ready (%d chunks)", collection, self._collection.count())

    def add(self, chunks: list[Chunk], vectors: np.ndarray, document_title: str) -> None:
        if not chunks:
            return
        vectors = np.asarray(vectors, dtype=np.float32)
        for start in range(0, len(chunks), _BATCH):
            window = chunks[start : start + _BATCH]
            self._collection.upsert(
                ids=[c.id for c in window],
                documents=[c.text for c in window],
                metadatas=[c.to_metadata(document_title) for c in window],
                embeddings=vectors[start : start + len(window)].tolist(),
            )

    def search(
        self, vector: np.ndarray, k: int, *, document_ids: list[str] | None = None
    ) -> list[SearchHit]:
        total = self._collection.count()
        if not total:
            return []
        where: dict[str, Any] | None = None
        if document_ids:
            where = (
                {"document_id": document_ids[0]}
                if len(document_ids) == 1
                else {"document_id": {"$in": document_ids}}
            )
        result = self._collection.query(
            query_embeddings=[np.asarray(vector, dtype=np.float32).tolist()],
            n_results=min(k, total),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[SearchHit] = []
        for id_, text, meta, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            hits.append(
                SearchHit(id=id_, text=text, score=1.0 - float(distance), metadata=dict(meta or {}))
            )
        return hits

    def delete_document(self, document_id: str) -> int:
        existing = self._collection.get(where={"document_id": document_id}, include=[])
        ids = existing.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def get(self, ids: list[str]) -> list[StoredChunk]:
        if not ids:
            return []
        page = self._collection.get(ids=ids, include=["documents", "metadatas"])
        return [
            StoredChunk(id=id_, text=text or "", metadata=dict(meta or {}))
            for id_, text, meta in zip(page.get("ids", []), page["documents"], page["metadatas"])
        ]

    def iter_chunks(self) -> Iterator[StoredChunk]:
        offset, total = 0, self._collection.count()
        while offset < total:
            page = self._collection.get(
                limit=_BATCH, offset=offset, include=["documents", "metadatas"]
            )
            ids = page.get("ids", [])
            if not ids:
                break
            for id_, text, meta in zip(ids, page["documents"], page["metadatas"]):
                yield StoredChunk(id=id_, text=text or "", metadata=dict(meta or {}))
            offset += len(ids)

    def count(self) -> int:
        return int(self._collection.count())

    def reset(self) -> None:
        name = self._collection.name
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )
