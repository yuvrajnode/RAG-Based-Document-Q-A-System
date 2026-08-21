from verbatim.embeddings.base import Embedder, l2_normalise
from verbatim.embeddings.cache import CachedEmbedder
from verbatim.embeddings.providers import (
    HashingEmbedder,
    OpenAIEmbedder,
    SentenceTransformerEmbedder,
    VoyageEmbedder,
    build_embedder,
)


def create_embedder(settings, *, use_cache: bool = True) -> Embedder:
    embedder = build_embedder(settings)
    if not use_cache:
        return embedder
    return CachedEmbedder(embedder, settings.storage_dir / "embedding-cache.sqlite3")


__all__ = [
    "Embedder",
    "CachedEmbedder",
    "HashingEmbedder",
    "OpenAIEmbedder",
    "SentenceTransformerEmbedder",
    "VoyageEmbedder",
    "build_embedder",
    "create_embedder",
    "l2_normalise",
]
