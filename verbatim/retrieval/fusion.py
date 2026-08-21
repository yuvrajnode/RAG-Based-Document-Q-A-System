"""Combining two ranked lists.

Two strategies, both here because they fail differently:

- Relative score fusion normalises each list to [0, 1] and takes a weighted
  sum. It keeps the magnitude of a very confident dense hit, which matters when
  one retriever is clearly right.
- Reciprocal rank fusion ignores scores entirely and works on rank. It is
  robust when the two score distributions are not comparable, which is most of
  the time, and it is what the default falls back to for the lexical side.
"""

from __future__ import annotations

from collections import defaultdict


def normalise(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return {key: 1.0 for key in scores}
    return {key: (value - low) / (high - low) for key, value in scores.items()}


def relative_score_fusion(
    dense: dict[str, float], lexical: dict[str, float], alpha: float = 0.6
) -> dict[str, float]:
    """alpha weights the dense side: 1.0 is dense-only, 0.0 is lexical-only."""
    dense_normalised = normalise(dense)
    lexical_normalised = normalise(lexical)
    fused: dict[str, float] = {}
    for key in set(dense_normalised) | set(lexical_normalised):
        fused[key] = alpha * dense_normalised.get(key, 0.0) + (1.0 - alpha) * (
            lexical_normalised.get(key, 0.0)
        )
    return fused


def reciprocal_rank_fusion(
    rankings: list[list[str]], weights: list[float] | None = None, k: int = 60
) -> dict[str, float]:
    """k=60 is the constant from the original Cormack et al. paper; it damps the
    influence of the head of each list enough that one confident-but-wrong
    retriever cannot dominate."""
    weights = weights or [1.0] * len(rankings)
    fused: dict[str, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights):
        for rank, key in enumerate(ranking, start=1):
            fused[key] += weight / (k + rank)
    return dict(fused)
