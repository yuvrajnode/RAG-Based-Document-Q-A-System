"""SQLite-backed embedding cache.

Re-ingesting a document you already indexed - or re-running the evaluation
harness - should not cost another round of API calls. Vectors are keyed by
(provider, model, text hash) so switching models never returns a stale vector.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path

import numpy as np

from verbatim.embeddings.base import Embedder

_SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    key   TEXT PRIMARY KEY,
    dim   INTEGER NOT NULL,
    vector BLOB NOT NULL
);
"""


def _key(provider: str, model: str, text: str) -> str:
    payload = f"{provider}\x1f{model}\x1f{text}".encode()
    return hashlib.sha256(payload).hexdigest()


class CachedEmbedder(Embedder):
    """Decorator around any Embedder. Misses are batched through to the inner one."""

    def __init__(self, inner: Embedder, path: str | Path):
        self.inner = inner
        self.name = f"{inner.name}+cache"
        self.model = inner.model
        self._lock = threading.Lock()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute(_SCHEMA)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.commit()

    @property
    def dimension(self) -> int:
        return self.inner.dimension

    def _get_many(self, keys: list[str]) -> dict[str, np.ndarray]:
        found: dict[str, np.ndarray] = {}
        with self._lock:
            for start in range(0, len(keys), 500):  # SQLite caps variables per statement
                window = keys[start : start + 500]
                placeholders = ",".join("?" * len(window))
                rows = self._db.execute(
                    f"SELECT key, dim, vector FROM embeddings WHERE key IN ({placeholders})", window
                ).fetchall()
                for key, dim, blob in rows:
                    found[key] = np.frombuffer(blob, dtype=np.float32, count=dim)
        return found

    def _put_many(self, items: list[tuple[str, np.ndarray]]) -> None:
        if not items:
            return
        rows = [(key, int(vec.shape[0]), vec.astype(np.float32).tobytes()) for key, vec in items]
        with self._lock:
            self._db.executemany(
                "INSERT OR REPLACE INTO embeddings (key, dim, vector) VALUES (?, ?, ?)", rows
            )
            self._db.commit()

    def _encode(self, texts: list[str], *, is_query: bool) -> np.ndarray:
        # Queries are rarely repeated verbatim and caching them would hide
        # nothing but a millisecond, so only document vectors are persisted.
        if is_query:
            return self.inner._encode(texts, is_query=True)

        keys = [_key(self.inner.name, self.inner.model, t) for t in texts]
        cached = self._get_many(list(dict.fromkeys(keys)))

        missing_positions = [i for i, key in enumerate(keys) if key not in cached]
        if missing_positions:
            fresh = self.inner.embed_documents([texts[i] for i in missing_positions])
            writes = []
            for row, position in enumerate(missing_positions):
                vector = fresh[row]
                cached[keys[position]] = vector
                writes.append((keys[position], vector))
            self._put_many(writes)

        return np.vstack([cached[key] for key in keys])

    def stats(self) -> dict[str, int]:
        with self._lock:
            (count,) = self._db.execute("SELECT COUNT(*) FROM embeddings").fetchone()
        return {"cached_vectors": int(count)}

    def close(self) -> None:
        with self._lock:
            self._db.close()
