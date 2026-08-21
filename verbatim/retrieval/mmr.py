"""Maximal Marginal Relevance.

Top-k by similarity alone tends to return the same paragraph five times over -
especially with overlapping chunks, where neighbours share half their text. The
model then reads one fact repeated five ways and misses the fact that answered
the other half of the question. MMR trades a little relevance for coverage.
"""

from __future__ import annotations

import numpy as np


def mmr_select(
    query_vector: np.ndarray,
    candidate_vectors: np.ndarray,
    k: int,
    lambda_: float = 0.65,
    *,
    prior_scores: np.ndarray | None = None,
) -> list[int]:
    """Return indices of the selected candidates, best first.

    lambda_ = 1.0 is plain relevance ranking, 0.0 is pure diversity.
    `prior_scores` lets the fused hybrid score drive relevance instead of raw
    cosine, so the lexical signal is not silently discarded at this stage.
    """
    if candidate_vectors.size == 0 or k <= 0:
        return []

    candidate_vectors = np.asarray(candidate_vectors, dtype=np.float32)
    total = candidate_vectors.shape[0]
    k = min(k, total)

    relevance = (
        np.asarray(prior_scores, dtype=np.float32)
        if prior_scores is not None
        else candidate_vectors @ np.asarray(query_vector, dtype=np.float32)
    )
    similarity = candidate_vectors @ candidate_vectors.T

    selected: list[int] = [int(np.argmax(relevance))]
    remaining = set(range(total)) - set(selected)

    while len(selected) < k and remaining:
        best_index, best_score = None, -np.inf
        for index in remaining:
            redundancy = float(np.max(similarity[index, selected]))
            score = lambda_ * float(relevance[index]) - (1.0 - lambda_) * redundancy
            if score > best_score:
                best_index, best_score = index, score
        selected.append(int(best_index))
        remaining.discard(int(best_index))

    return selected
