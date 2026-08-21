from pathlib import Path

from verbatim.store.base import SearchHit, StoredChunk, VectorStore
from verbatim.store.catalogue import DocumentCatalogue
from verbatim.store.numpy_store import NumpyVectorStore


def create_store(settings, dimension: int) -> VectorStore:
    """Build the configured backend, falling back to the flat index if Chroma
    is not installed - a missing optional dependency should not take the API
    down."""
    if settings.vector_store == "chroma":
        from verbatim.logging import get_logger

        try:
            from verbatim.store.chroma_store import ChromaVectorStore

            return ChromaVectorStore(
                Path(settings.storage_dir) / "chroma", settings.collection_name, dimension
            )
        except RuntimeError as exc:
            get_logger(__name__).warning("%s falling back to the numpy index", exc)

    return NumpyVectorStore(Path(settings.storage_dir) / "index", dimension)


__all__ = [
    "DocumentCatalogue",
    "NumpyVectorStore",
    "SearchHit",
    "StoredChunk",
    "VectorStore",
    "create_store",
]
