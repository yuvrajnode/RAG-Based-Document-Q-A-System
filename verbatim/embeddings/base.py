"""Embedder interface.

Every provider returns L2-normalised float32 vectors, which means cosine
similarity is just a dot product and the vector store never has to care which
provider produced the index.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


def l2_normalise(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.maximum(norms, 1e-12, out=norms)
    return matrix / norms


class Embedder(ABC):
    """Turns text into vectors. Implementations must be safe to reuse."""

    name: str = "embedder"
    model: str = ""

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    def _encode(self, texts: list[str], *, is_query: bool) -> np.ndarray: ...

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        return l2_normalise(self._encode(list(texts), is_query=False))

    def embed_query(self, text: str) -> np.ndarray:
        return l2_normalise(self._encode([text], is_query=True))[0]

    def describe(self) -> dict[str, object]:
        return {"provider": self.name, "model": self.model, "dimension": self.dimension}


def batched(items: list[str], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]
