from __future__ import annotations

import numpy as np

from verbatim.embeddings.providers import HashingEmbedder
from verbatim.models import Chunk
from verbatim.retrieval.bm25 import BM25Index, tokenize
from verbatim.retrieval.fusion import (
    normalise,
    reciprocal_rank_fusion,
    relative_score_fusion,
)
from verbatim.retrieval.mmr import mmr_select
from verbatim.retrieval.retriever import Retriever
from verbatim.store.numpy_store import NumpyVectorStore

CORPUS = [
    "Chroma persists embeddings on disk and queries them with an HNSW index.",
    "BM25 ranks documents by term frequency scaled against inverse document frequency.",
    "Refunds are issued within 30 days when the order reference GH-7781 is supplied.",
    "Maximal marginal relevance reduces redundancy between the passages that are returned.",
    "Annual leave accrues at twenty days per year for full time staff.",
]


def build_retriever(tmp_path, **kwargs) -> Retriever:
    embedder = HashingEmbedder(256)
    store = NumpyVectorStore(tmp_path / "index", embedder.dimension)
    chunks = [
        Chunk(id=f"c{i}", document_id="doc", text=text, index=i, page=i + 1)
        for i, text in enumerate(CORPUS)
    ]
    store.add(chunks, embedder.embed_documents(CORPUS), "Corpus")
    kwargs.setdefault("min_score", 0.0)
    return Retriever(store, embedder, top_k=3, candidate_k=10, **kwargs)


# --- BM25 -----------------------------------------------------------------
def test_tokenizer_drops_stopwords_and_folds_plurals():
    tokens = tokenize("The Documents are indexed by the system")
    assert "the" not in tokens
    assert "document" in tokens


def test_bm25_ranks_the_literal_match_first():
    index = BM25Index().build([(f"c{i}", t) for i, t in enumerate(CORPUS)])
    top = index.search("order reference GH-7781", k=3)
    assert top[0][0] == "c2"


def test_bm25_returns_nothing_for_unknown_terms():
    index = BM25Index().build([(f"c{i}", t) for i, t in enumerate(CORPUS)])
    assert index.search("zzzz qqqq", k=5) == []


def test_empty_index_is_safe_to_query():
    assert BM25Index().search("anything") == []


# --- fusion ---------------------------------------------------------------
def test_normalise_maps_to_the_unit_interval():
    out = normalise({"a": 2.0, "b": 4.0, "c": 6.0})
    assert out["a"] == 0.0 and out["c"] == 1.0


def test_normalise_handles_a_flat_distribution():
    assert set(normalise({"a": 3.0, "b": 3.0}).values()) == {1.0}


def test_alpha_shifts_the_balance_between_retrievers():
    dense = {"a": 1.0, "b": 0.0}
    lexical = {"a": 0.0, "b": 1.0}
    assert relative_score_fusion(dense, lexical, alpha=1.0)["a"] == 1.0
    assert relative_score_fusion(dense, lexical, alpha=0.0)["b"] == 1.0
    balanced = relative_score_fusion(dense, lexical, alpha=0.5)
    assert balanced["a"] == balanced["b"]


def test_rrf_rewards_agreement_between_lists():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "c"]])
    assert fused["b"] > fused["c"] and fused["a"] > fused["c"]


# --- MMR ------------------------------------------------------------------
def test_mmr_prefers_coverage_over_near_duplicates():
    query = np.array([1.0, 0.0], dtype=np.float32)
    # Two near-identical vectors and one orthogonal alternative.
    candidates = np.array([[1.0, 0.0], [0.99, 0.14], [0.0, 1.0]], dtype=np.float32)
    selected = mmr_select(query, candidates, k=2, lambda_=0.3)
    assert selected[0] == 0
    assert selected[1] == 2


def test_mmr_with_lambda_one_is_plain_relevance_ranking():
    query = np.array([1.0, 0.0], dtype=np.float32)
    candidates = np.array([[1.0, 0.0], [0.9, 0.44], [0.2, 0.98]], dtype=np.float32)
    assert mmr_select(query, candidates, k=3, lambda_=1.0) == [0, 1, 2]


def test_mmr_on_an_empty_candidate_set():
    assert mmr_select(np.array([1.0]), np.zeros((0, 1), dtype=np.float32), k=3) == []


# --- retriever ------------------------------------------------------------
def test_hybrid_retrieval_finds_a_rare_literal_token(tmp_path):
    result = build_retriever(tmp_path).retrieve("What does GH-7781 refer to?")
    assert result.chunks[0].chunk_id == "c2"
    assert result.chunks[0].lexical_score > 0


def test_retrieval_respects_top_k(tmp_path):
    assert len(build_retriever(tmp_path).retrieve("leave", top_k=2).chunks) <= 2


def test_document_filter_restricts_the_candidate_set(tmp_path):
    retriever = build_retriever(tmp_path)
    assert retriever.retrieve("refunds", document_ids=["missing"]).chunks == []
    assert retriever.retrieve("refunds", document_ids=["doc"]).chunks


def test_min_score_drops_weak_matches(tmp_path):
    retriever = build_retriever(tmp_path, min_score=0.99)
    assert len(retriever.retrieve("annual leave").chunks) <= 1


def test_empty_query_returns_nothing(tmp_path):
    assert build_retriever(tmp_path).retrieve("   ").chunks == []


def test_strategy_name_reflects_configuration(tmp_path):
    assert build_retriever(tmp_path, hybrid_alpha=1.0, use_mmr=False).strategy_name() == "dense"
    assert build_retriever(tmp_path, hybrid_alpha=0.0, use_mmr=False).strategy_name() == "lexical"
    assert "mmr" in build_retriever(tmp_path, use_mmr=True).strategy_name()
