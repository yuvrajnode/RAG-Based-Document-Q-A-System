"""Retrieval metrics.

All of these operate on a ranked list of chunk texts and a set of substrings
that a correct passage must contain. Judging by substring rather than by chunk
id matters: chunk ids move whenever chunk_size changes, and the whole point of
the harness is to compare configurations against each other.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def _matches(text: str, expected: list[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in expected)


def relevance_vector(ranked_texts: list[str], expected: list[str]) -> list[int]:
    return [1 if _matches(text, expected) else 0 for text in ranked_texts]


def hit_rate(relevance: list[int], k: int) -> float:
    """Did any relevant passage make the top k? The metric that decides whether
    the model even had a chance to answer correctly."""
    return 1.0 if any(relevance[:k]) else 0.0


def precision_at_k(relevance: list[int], k: int) -> float:
    """Divided by k, not by the number of results returned - otherwise a
    configuration that returns two passages looks more precise than one that
    returns five, and the comparison table stops meaning anything."""
    return sum(relevance[:k]) / k if k else 0.0


def recall_at_k(relevance: list[int], k: int, total_relevant: int) -> float:
    if total_relevant <= 0:
        return 0.0
    return min(sum(relevance[:k]) / total_relevant, 1.0)


def reciprocal_rank(relevance: list[int]) -> float:
    for position, value in enumerate(relevance, start=1):
        if value:
            return 1.0 / position
    return 0.0


def ndcg_at_k(relevance: list[int], k: int) -> float:
    gain = sum(
        value / math.log2(position + 1) for position, value in enumerate(relevance[:k], start=1)
    )
    ideal_hits = min(sum(relevance), k)
    ideal = sum(1 / math.log2(position + 1) for position in range(1, ideal_hits + 1))
    return gain / ideal if ideal else 0.0


@dataclass(slots=True)
class QuestionScore:
    question: str
    hit: float
    precision: float
    recall: float
    reciprocal_rank: float
    ndcg: float
    took_ms: int
    top_text: str = ""


@dataclass(slots=True)
class EvaluationReport:
    label: str
    k: int
    scores: list[QuestionScore] = field(default_factory=list)

    def _mean(self, attribute: str) -> float:
        if not self.scores:
            return 0.0
        return sum(getattr(score, attribute) for score in self.scores) / len(self.scores)

    def summary(self) -> dict[str, float | int | str]:
        return {
            "config": self.label,
            "questions": len(self.scores),
            f"hit@{self.k}": round(self._mean("hit"), 3),
            f"precision@{self.k}": round(self._mean("precision"), 3),
            f"recall@{self.k}": round(self._mean("recall"), 3),
            "mrr": round(self._mean("reciprocal_rank"), 3),
            f"ndcg@{self.k}": round(self._mean("ndcg"), 3),
            "median_ms": self.median_latency(),
        }

    def median_latency(self) -> int:
        if not self.scores:
            return 0
        latencies = sorted(score.took_ms for score in self.scores)
        return latencies[len(latencies) // 2]

    def failures(self) -> list[QuestionScore]:
        return [score for score in self.scores if score.hit == 0.0]
