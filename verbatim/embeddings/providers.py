"""Concrete embedding providers."""

from __future__ import annotations

import hashlib
import os
import re

import numpy as np

from verbatim.embeddings.base import Embedder, batched
from verbatim.logging import get_logger

log = get_logger(__name__)

# BGE and E5 families expect an instruction prefix on the query side only.
# Skipping it costs a few points of recall, which is easy to lose and hard to
# notice, so it is applied automatically by model name.
_QUERY_PREFIXES = {
    "bge": "Represent this sentence for searching relevant passages: ",
    "e5": "query: ",
}
_PASSAGE_PREFIXES = {"e5": "passage: "}


def _prefix_for(model: str, table: dict[str, str]) -> str:
    lowered = model.lower()
    for key, prefix in table.items():
        if key in lowered:
            return prefix
    return ""


class SentenceTransformerEmbedder(Embedder):
    """Local embeddings. No API key, no per-token cost, ~120MB for bge-small."""

    name = "sentence-transformers"

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", batch_size: int = 32):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on the install extra
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run `pip install -e '.[local-embeddings]'` or set "
                "VERBATIM_EMBEDDING_PROVIDER=hashing."
            ) from exc
        log.info("loading embedding model %s", model)
        self.model = model
        self.batch_size = batch_size
        self._encoder = SentenceTransformer(model)
        self._dimension = int(self._encoder.get_sentence_embedding_dimension())
        self._query_prefix = _prefix_for(model, _QUERY_PREFIXES)
        self._passage_prefix = _prefix_for(model, _PASSAGE_PREFIXES)

    @property
    def dimension(self) -> int:
        return self._dimension

    def _encode(self, texts: list[str], *, is_query: bool) -> np.ndarray:
        prefix = self._query_prefix if is_query else self._passage_prefix
        payload = [prefix + t for t in texts] if prefix else texts
        return self._encoder.encode(
            payload,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(payload) > 512,
        )


class _HTTPEmbedder(Embedder):
    """Shared plumbing for the hosted providers."""

    endpoint = ""
    dimension_by_model: dict[str, int] = {}

    def __init__(self, model: str, api_key: str, batch_size: int = 64, timeout: float = 60.0):
        if not api_key:
            raise RuntimeError(f"{self.name} selected but no API key was provided")
        self.model = model
        self.batch_size = batch_size
        self._api_key = api_key
        self._timeout = timeout
        self._dimension = self.dimension_by_model.get(model, 1024)

    @property
    def dimension(self) -> int:
        return self._dimension

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def _payload(self, texts: list[str], *, is_query: bool) -> dict:
        raise NotImplementedError

    def _encode(self, texts: list[str], *, is_query: bool) -> np.ndarray:
        import httpx

        vectors: list[list[float]] = []
        with httpx.Client(timeout=self._timeout) as client:
            for batch in batched(texts, self.batch_size):
                response = client.post(
                    self.endpoint,
                    headers=self._headers(),
                    json=self._payload(batch, is_query=is_query),
                )
                response.raise_for_status()
                data = response.json()["data"]
                vectors.extend(item["embedding"] for item in data)
        array = np.asarray(vectors, dtype=np.float32)
        self._dimension = array.shape[1]
        return array


class VoyageEmbedder(_HTTPEmbedder):
    """Voyage's retrieval models are asymmetric - query and document differ."""

    name = "voyage"
    endpoint = "https://api.voyageai.com/v1/embeddings"
    dimension_by_model = {"voyage-3": 1024, "voyage-3-lite": 512, "voyage-code-3": 1024}

    def _payload(self, texts: list[str], *, is_query: bool) -> dict:
        return {
            "model": self.model,
            "input": texts,
            "input_type": "query" if is_query else "document",
        }


class OpenAIEmbedder(_HTTPEmbedder):
    name = "openai"
    endpoint = "https://api.openai.com/v1/embeddings"
    dimension_by_model = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}

    def _payload(self, texts: list[str], *, is_query: bool) -> dict:
        return {"model": self.model, "input": texts}


_TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbedder(Embedder):
    """Deterministic hashed bag-of-features. No downloads, no network.

    This exists so `git clone && make test` works on any machine and so the
    first run of the API is not blocked on a model download. Retrieval quality
    is materially worse than a trained encoder - it has no notion of synonymy -
    so it is a development convenience, not a deployment option.
    """

    name = "hashing"

    def __init__(self, dimension: int = 384, model: str = "hashed-trigram-v1"):
        self._dimension = dimension
        self.model = model

    @property
    def dimension(self) -> int:
        return self._dimension

    @staticmethod
    def _features(text: str) -> list[str]:
        tokens = _TOKEN.findall(text.lower())
        features = list(tokens)
        features += [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for token in tokens:
            if len(token) > 4:
                padded = f"#{token}#"
                features += [padded[i : i + 3] for i in range(len(padded) - 2)]
        return features

    def _encode(self, texts: list[str], *, is_query: bool) -> np.ndarray:
        matrix = np.zeros((len(texts), self._dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature in self._features(text):
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                value = int.from_bytes(digest, "big")
                # Signed hashing keeps collisions from systematically inflating
                # the dot product between unrelated texts.
                sign = 1.0 if value & 1 else -1.0
                matrix[row, (value >> 1) % self._dimension] += sign
        return matrix


def build_embedder(settings) -> Embedder:
    provider = settings.embedding_provider
    if provider == "sentence-transformers":
        return SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_batch_size)
    if provider == "voyage":
        key = settings.voyage_api_key or os.getenv("VOYAGE_API_KEY", "")
        model = settings.embedding_model if "voyage" in settings.embedding_model else "voyage-3"
        return VoyageEmbedder(model, key, settings.embedding_batch_size)
    if provider == "openai":
        key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        model = (
            settings.embedding_model
            if settings.embedding_model.startswith("text-embedding")
            else "text-embedding-3-small"
        )
        return OpenAIEmbedder(model, key, settings.embedding_batch_size)
    if provider == "hashing":
        return HashingEmbedder(settings.embedding_dim)
    raise ValueError(f"unknown embedding provider {provider!r}")
