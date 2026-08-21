"""Vector store interface.

Two backends implement it: Chroma (HNSW, persistent, what you would actually
deploy) and a flat NumPy index (exact, no extra dependency, handy for tests and
for corpora small enough that an approximate index buys nothing).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator

import numpy as np

from verbatim.models import Chunk


@dataclass(slots=True)
class StoredChunk:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchHit:
    id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    kind: str = "base"

    @abstractmethod
    def add(self, chunks: list[Chunk], vectors: np.ndarray, document_title: str) -> None: ...

    @abstractmethod
    def search(
        self, vector: np.ndarray, k: int, *, document_ids: list[str] | None = None
    ) -> list[SearchHit]: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> int: ...

    @abstractmethod
    def iter_chunks(self) -> Iterator[StoredChunk]:
        """Every chunk in the index. The lexical index is rebuilt from this."""

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def reset(self) -> None: ...

    def stats(self) -> dict[str, Any]:
        return {"backend": self.kind, "chunks": self.count()}
