from __future__ import annotations

import numpy as np
import pytest

from verbatim.embeddings.cache import CachedEmbedder
from verbatim.embeddings.providers import HashingEmbedder
from verbatim.models import Chunk, DocumentRecord
from verbatim.store.catalogue import DocumentCatalogue
from verbatim.store.numpy_store import NumpyVectorStore


def chunks_for(document_id: str, count: int, offset: int = 0) -> list[Chunk]:
    return [
        Chunk(id=f"{document_id}-{i}", document_id=document_id, text=f"chunk {i + offset}", index=i)
        for i in range(count)
    ]


def unit_vectors(count: int, dimension: int = 8) -> np.ndarray:
    matrix = np.eye(dimension, dtype=np.float32)[:count]
    return matrix


# --- vector store ---------------------------------------------------------
def test_search_ranks_by_cosine_similarity(tmp_path):
    store = NumpyVectorStore(tmp_path, 8)
    store.add(chunks_for("d", 3), unit_vectors(3), "Doc")
    hits = store.search(np.eye(8, dtype=np.float32)[1], k=2)
    assert hits[0].id == "d-1"
    assert hits[0].score == pytest.approx(1.0)


def test_index_survives_a_reload(tmp_path):
    store = NumpyVectorStore(tmp_path, 8)
    store.add(chunks_for("d", 3), unit_vectors(3), "Doc")
    assert NumpyVectorStore(tmp_path, 8).count() == 3


def test_reingesting_the_same_chunk_updates_in_place(tmp_path):
    store = NumpyVectorStore(tmp_path, 8)
    store.add(chunks_for("d", 2), unit_vectors(2), "Doc")
    store.add(chunks_for("d", 2), unit_vectors(2), "Doc")
    assert store.count() == 2


def test_delete_removes_only_the_target_document(tmp_path):
    store = NumpyVectorStore(tmp_path, 8)
    store.add(chunks_for("a", 2), unit_vectors(2), "A")
    store.add(chunks_for("b", 2), unit_vectors(2), "B")
    assert store.delete_document("a") == 2
    assert {chunk.metadata["document_id"] for chunk in store.iter_chunks()} == {"b"}


def test_metadata_filter_scopes_the_search(tmp_path):
    store = NumpyVectorStore(tmp_path, 8)
    store.add(chunks_for("a", 2), unit_vectors(2), "A")
    store.add(chunks_for("b", 2), unit_vectors(2), "B")
    hits = store.search(np.eye(8, dtype=np.float32)[0], k=4, document_ids=["b"])
    assert {hit.metadata["document_id"] for hit in hits} == {"b"}


def test_get_hydrates_by_id(tmp_path):
    store = NumpyVectorStore(tmp_path, 8)
    store.add(chunks_for("d", 3), unit_vectors(3), "Doc")
    assert [c.id for c in store.get(["d-2", "missing"])] == ["d-2"]


def test_dimension_mismatch_starts_clean_instead_of_crashing(tmp_path):
    store = NumpyVectorStore(tmp_path, 8)
    store.add(chunks_for("d", 2), unit_vectors(2), "Doc")
    assert NumpyVectorStore(tmp_path, 16).count() == 0


def test_search_on_an_empty_index(tmp_path):
    assert NumpyVectorStore(tmp_path, 8).search(np.zeros(8, dtype=np.float32), k=5) == []


# --- catalogue ------------------------------------------------------------
def test_catalogue_upsert_preserves_the_original_created_at(tmp_path):
    catalogue = DocumentCatalogue(tmp_path / "c.sqlite3")
    record = DocumentRecord(id="d", title="One", source_type="md", chunk_count=1, char_count=10)
    catalogue.upsert(record)
    catalogue.upsert(
        DocumentRecord(id="d", title="Two", source_type="md", chunk_count=4, char_count=40)
    )
    stored = catalogue.get("d")
    assert stored.title == "Two" and stored.chunk_count == 4
    assert stored.created_at == record.created_at


def test_catalogue_totals(tmp_path):
    catalogue = DocumentCatalogue(tmp_path / "c.sqlite3")
    for i in range(3):
        catalogue.upsert(
            DocumentRecord(
                id=f"d{i}", title=f"D{i}", source_type="md", chunk_count=2, char_count=100
            )
        )
    assert catalogue.totals() == {"documents": 3, "chunks": 6, "characters": 300}


def test_catalogue_delete(tmp_path):
    catalogue = DocumentCatalogue(tmp_path / "c.sqlite3")
    catalogue.upsert(
        DocumentRecord(id="d", title="D", source_type="md", chunk_count=1, char_count=1)
    )
    assert catalogue.delete("d") is True
    assert catalogue.delete("d") is False


# --- embeddings -----------------------------------------------------------
def test_embeddings_are_unit_length():
    matrix = HashingEmbedder(64).embed_documents(["alpha beta", "gamma delta"])
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-5)


def test_related_text_scores_above_unrelated_text():
    embedder = HashingEmbedder(512)
    matrix = embedder.embed_documents(
        ["vector databases index embeddings", "a recipe for lemon cake"]
    )
    query = embedder.embed_query("how are embeddings indexed")
    assert float(matrix[0] @ query) > float(matrix[1] @ query)


def test_cache_returns_identical_vectors_and_only_stores_once(tmp_path):
    cached = CachedEmbedder(HashingEmbedder(64), tmp_path / "cache.sqlite3")
    texts = ["one", "two", "one"]
    first = cached.embed_documents(texts)
    second = cached.embed_documents(texts)
    assert np.allclose(first, second)
    assert cached.stats()["cached_vectors"] == 2
