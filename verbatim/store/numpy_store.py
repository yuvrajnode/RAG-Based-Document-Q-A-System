"""Exact flat index over NumPy arrays.

Brute force is O(n*d) per query. On the corpora this project is aimed at
(a few hundred documents, tens of thousands of chunks) that is well under a
millisecond and it removes a whole class of "why did recall drop" questions
that come with approximate indexes. Chroma is there for when it stops being
true.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from verbatim.logging import get_logger
from verbatim.models import Chunk
from verbatim.store.base import SearchHit, StoredChunk, VectorStore

log = get_logger(__name__)


class NumpyVectorStore(VectorStore):
    kind = "numpy"

    def __init__(self, path: str | Path, dimension: int):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._vectors_file = self.path / "vectors.npy"
        self._records_file = self.path / "records.jsonl"
        self._dimension = dimension
        self._lock = threading.RLock()
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metadata: list[dict[str, Any]] = []
        self._matrix = np.zeros((0, dimension), dtype=np.float32)
        self._load()

    # --- persistence ---------------------------------------------------
    def _load(self) -> None:
        if not (self._vectors_file.exists() and self._records_file.exists()):
            return
        matrix = np.load(self._vectors_file)
        records = [json.loads(line) for line in self._records_file.read_text().splitlines() if line]
        if matrix.shape[0] != len(records):
            log.warning("index at %s is inconsistent; starting empty", self.path)
            return
        if matrix.size and matrix.shape[1] != self._dimension:
            log.warning(
                "index at %s has dimension %d but the embedder produces %d; "
                "delete the storage directory and re-ingest",
                self.path,
                matrix.shape[1],
                self._dimension,
            )
            return
        self._matrix = matrix.astype(np.float32)
        self._ids = [r["id"] for r in records]
        self._texts = [r["text"] for r in records]
        self._metadata = [r["metadata"] for r in records]

    def _flush(self) -> None:
        np.save(self._vectors_file, self._matrix)
        with self._records_file.open("w", encoding="utf-8") as handle:
            for id_, text, meta in zip(self._ids, self._texts, self._metadata):
                handle.write(json.dumps({"id": id_, "text": text, "metadata": meta}) + "\n")

    # --- VectorStore ---------------------------------------------------
    def add(self, chunks: list[Chunk], vectors: np.ndarray, document_title: str) -> None:
        if not chunks:
            return
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.shape[0] != len(chunks):
            raise ValueError("vector count does not match chunk count")

        with self._lock:
            known = {id_: i for i, id_ in enumerate(self._ids)}
            fresh_rows, fresh_vectors = [], []
            for chunk, vector in zip(chunks, vectors):
                payload = (chunk.id, chunk.text, chunk.to_metadata(document_title))
                if chunk.id in known:  # re-ingest of identical content
                    row = known[chunk.id]
                    self._texts[row], self._metadata[row] = payload[1], payload[2]
                    self._matrix[row] = vector
                    continue
                fresh_rows.append(payload)
                fresh_vectors.append(vector)

            if fresh_rows:
                self._ids.extend(r[0] for r in fresh_rows)
                self._texts.extend(r[1] for r in fresh_rows)
                self._metadata.extend(r[2] for r in fresh_rows)
                block = np.asarray(fresh_vectors, dtype=np.float32)
                self._matrix = np.vstack([self._matrix, block]) if self._matrix.size else block
            self._flush()

    def search(
        self, vector: np.ndarray, k: int, *, document_ids: list[str] | None = None
    ) -> list[SearchHit]:
        with self._lock:
            if not self._ids:
                return []
            scores = self._matrix @ np.asarray(vector, dtype=np.float32)

            if document_ids:
                allowed = set(document_ids)
                mask = np.fromiter(
                    (m.get("document_id") in allowed for m in self._metadata),
                    dtype=bool,
                    count=len(self._metadata),
                )
                if not mask.any():
                    return []
                scores = np.where(mask, scores, -np.inf)

            k = min(k, int(np.isfinite(scores).sum()))
            if k <= 0:
                return []
            top = np.argpartition(-scores, k - 1)[:k]
            top = top[np.argsort(-scores[top])]
            return [
                SearchHit(
                    id=self._ids[i],
                    text=self._texts[i],
                    score=float(scores[i]),
                    metadata=self._metadata[i],
                )
                for i in top
            ]

    def delete_document(self, document_id: str) -> int:
        with self._lock:
            keep = [i for i, m in enumerate(self._metadata) if m.get("document_id") != document_id]
            removed = len(self._ids) - len(keep)
            if not removed:
                return 0
            self._ids = [self._ids[i] for i in keep]
            self._texts = [self._texts[i] for i in keep]
            self._metadata = [self._metadata[i] for i in keep]
            self._matrix = (
                self._matrix[keep] if keep else np.zeros((0, self._dimension), dtype=np.float32)
            )
            self._flush()
            return removed

    def iter_chunks(self) -> Iterator[StoredChunk]:
        with self._lock:
            snapshot = list(zip(self._ids, self._texts, self._metadata))
        for id_, text, meta in snapshot:
            yield StoredChunk(id=id_, text=text, metadata=meta)

    def count(self) -> int:
        return len(self._ids)

    def reset(self) -> None:
        with self._lock:
            self._ids, self._texts, self._metadata = [], [], []
            self._matrix = np.zeros((0, self._dimension), dtype=np.float32)
            self._flush()
