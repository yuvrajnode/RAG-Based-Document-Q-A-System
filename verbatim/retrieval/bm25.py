"""Okapi BM25 over the chunk texts.

Dense retrieval is very good at paraphrase and very bad at rare literal tokens -
an error code, a part number, a surname that never appeared in the encoder's
training data. BM25 is the opposite. Running both and fusing them is the
cheapest reliable win available in a RAG pipeline, so the lexical half is a
first-class index here rather than an afterthought.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

_TOKEN = re.compile(r"[a-z0-9][a-z0-9'._-]*")

# Deliberately short. An aggressive stop list hurts exact-phrase questions
# ("what is the state of the art") more than it helps.
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "how",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "your",
        "you",
    ]
)


def tokenize(text: str) -> list[str]:
    tokens = []
    for match in _TOKEN.findall(text.lower()):
        token = match.strip("'._-")
        if len(token) < 2 or token in _STOPWORDS:
            continue
        # Crude but effective plural folding; a full stemmer is not worth the
        # dependency for the gain it produces at this corpus size.
        if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
            token = token[:-1]
        tokens.append(token)
    return tokens


class BM25Index:
    """Standard Okapi BM25 with an inverted index."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._ids: list[str] = []
        self._lengths: list[int] = []
        self._postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self._document_frequency: dict[str, int] = defaultdict(int)
        self._average_length = 0.0

    def __len__(self) -> int:
        return len(self._ids)

    def build(self, documents: list[tuple[str, str]]) -> BM25Index:
        """documents: (chunk_id, text) pairs. Rebuilds from scratch."""
        self._ids = []
        self._lengths = []
        self._postings = defaultdict(list)
        self._document_frequency = defaultdict(int)

        for chunk_id, text in documents:
            position = len(self._ids)
            tokens = tokenize(text)
            self._ids.append(chunk_id)
            self._lengths.append(len(tokens))

            frequencies: dict[str, int] = defaultdict(int)
            for token in tokens:
                frequencies[token] += 1
            for token, count in frequencies.items():
                self._postings[token].append((position, count))
                self._document_frequency[token] += 1

        self._average_length = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        return self

    def _idf(self, term: str) -> float:
        n = len(self._ids)
        df = self._document_frequency.get(term, 0)
        if not df:
            return 0.0
        # Robertson/Sparck-Jones idf with the +1 that keeps it non-negative for
        # terms appearing in more than half the corpus.
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 40) -> list[tuple[str, float]]:
        if not self._ids:
            return []
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self._idf(term)
            if idf <= 0.0:
                continue
            for position, frequency in self._postings.get(term, ()):
                length_norm = (
                    1.0
                    - self.b
                    + self.b * (self._lengths[position] / (self._average_length or 1.0))
                )
                scores[position] += idf * (
                    frequency * (self.k1 + 1.0) / (frequency + self.k1 * length_norm)
                )
        ranked = sorted(scores.items(), key=lambda item: -item[1])[:k]
        return [(self._ids[position], score) for position, score in ranked]
