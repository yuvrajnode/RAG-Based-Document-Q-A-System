"""The retriever: dense + lexical -> fusion -> MMR -> top-k."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np

from verbatim.embeddings.base import Embedder
from verbatim.logging import get_logger
from verbatim.models import RetrievedChunk
from verbatim.retrieval.bm25 import BM25Index
from verbatim.retrieval.fusion import normalise, reciprocal_rank_fusion, relative_score_fusion
from verbatim.retrieval.mmr import mmr_select
from verbatim.store.base import SearchHit, VectorStore

log = get_logger(__name__)


@dataclass(slots=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    took_ms: int
    dense_candidates: int
    lexical_candidates: int
    strategy: str


class Retriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        *,
        top_k: int = 5,
        candidate_k: int = 40,
        hybrid_alpha: float = 0.6,
        use_mmr: bool = True,
        mmr_lambda: float = 0.65,
        min_score: float = 0.15,
        fusion: str = "relative",
    ):
        self.store = store
        self.embedder = embedder
        self.top_k = top_k
        self.candidate_k = candidate_k
        self.hybrid_alpha = hybrid_alpha
        self.use_mmr = use_mmr
        self.mmr_lambda = mmr_lambda
        self.min_score = min_score
        self.fusion = fusion

        self._bm25 = BM25Index()
        self._bm25_lock = threading.Lock()
        self._bm25_stale = True

    # --- lexical index lifecycle ---------------------------------------
    def invalidate(self) -> None:
        """Called after ingestion or deletion; the rebuild happens lazily on the
        next query so a bulk upload does not pay for it once per file."""
        with self._bm25_lock:
            self._bm25_stale = True

    def _lexical_index(self) -> BM25Index:
        with self._bm25_lock:
            if self._bm25_stale:
                started = time.perf_counter()
                pairs = [(chunk.id, chunk.text) for chunk in self.store.iter_chunks()]
                self._bm25.build(pairs)
                self._bm25_stale = False
                log.info(
                    "rebuilt lexical index: %d chunks in %.0fms",
                    len(pairs),
                    (time.perf_counter() - started) * 1000,
                )
            return self._bm25

    # --- retrieval ------------------------------------------------------
    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        document_ids: list[str] | None = None,
    ) -> RetrievalResult:
        started = time.perf_counter()
        top_k = top_k or self.top_k
        query = query.strip()
        if not query or self.store.count() == 0:
            return RetrievalResult([], 0, 0, 0, self._strategy_name())

        query_vector = self.embedder.embed_query(query)
        dense_hits = self.store.search(query_vector, self.candidate_k, document_ids=document_ids)
        dense_scores = {hit.id: hit.score for hit in dense_hits}
        by_id = {hit.id: hit for hit in dense_hits}

        lexical_scores: dict[str, float] = {}
        if self.hybrid_alpha < 1.0:
            allowed = set(document_ids) if document_ids else None
            raw = self._lexical_index().search(query, self.candidate_k)
            missing = [chunk_id for chunk_id, _ in raw if chunk_id not in by_id]
            # BM25 surfaced chunks the dense pass missed; fetch their text in one
            # round trip so they can compete on equal footing.
            hydrated = {chunk.id: chunk for chunk in self.store.get(missing)} if missing else {}
            for chunk_id, score in raw:
                if chunk_id not in by_id:
                    chunk = hydrated.get(chunk_id)
                    if chunk is None:
                        continue
                    if allowed and chunk.metadata.get("document_id") not in allowed:
                        continue
                    by_id[chunk_id] = SearchHit(
                        id=chunk.id, text=chunk.text, score=0.0, metadata=chunk.metadata
                    )
                lexical_scores[chunk_id] = score

        fused = self._fuse(dense_scores, lexical_scores)
        if not fused:
            return RetrievalResult([], self._elapsed(started), len(dense_hits), 0, self._strategy_name())

        ordered = sorted(fused.items(), key=lambda item: -item[1])
        pool = ordered[: max(self.candidate_k, top_k)]

        if self.use_mmr and len(pool) > top_k:
            texts = [by_id[chunk_id].text for chunk_id, _ in pool]
            vectors = self.embedder.embed_documents(texts)
            priors = np.asarray([score for _, score in pool], dtype=np.float32)
            keep = mmr_select(query_vector, vectors, top_k, self.mmr_lambda, prior_scores=priors)
            selection = [pool[i] for i in keep]
        else:
            selection = pool[:top_k]

        results: list[RetrievedChunk] = []
        for chunk_id, score in selection:
            if score < self.min_score:
                continue
            hit = by_id[chunk_id]
            meta = hit.metadata or {}
            results.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    document_id=str(meta.get("document_id", "")),
                    document_title=str(meta.get("document_title", "Untitled")),
                    text=hit.text,
                    score=float(score),
                    dense_score=float(dense_scores.get(chunk_id, 0.0)),
                    lexical_score=float(lexical_scores.get(chunk_id, 0.0)),
                    page=meta.get("page"),
                    heading=meta.get("heading"),
                    metadata=meta,
                )
            )

        return RetrievalResult(
            chunks=results,
            took_ms=self._elapsed(started),
            dense_candidates=len(dense_scores),
            lexical_candidates=len(lexical_scores),
            strategy=self._strategy_name(),
        )

    # --- helpers --------------------------------------------------------
    def _fuse(self, dense: dict[str, float], lexical: dict[str, float]) -> dict[str, float]:
        if not lexical:
            return normalise(dense)
        if not dense:
            return normalise(lexical)
        if self.fusion == "rrf":
            dense_ranking = [k for k, _ in sorted(dense.items(), key=lambda i: -i[1])]
            lexical_ranking = [k for k, _ in sorted(lexical.items(), key=lambda i: -i[1])]
            weights = [self.hybrid_alpha, 1.0 - self.hybrid_alpha]
            return normalise(reciprocal_rank_fusion([dense_ranking, lexical_ranking], weights))
        return relative_score_fusion(dense, lexical, self.hybrid_alpha)

    def _strategy_name(self) -> str:
        if self.hybrid_alpha >= 1.0:
            base = "dense"
        elif self.hybrid_alpha <= 0.0:
            base = "lexical"
        else:
            base = f"hybrid-{self.fusion}"
        return f"{base}+mmr" if self.use_mmr else base

    @staticmethod
    def _elapsed(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
