"""Core data types shared by ingestion, retrieval and answering."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_id(*parts: Any) -> str:
    """Content-addressed id, so re-ingesting the same file is idempotent."""
    digest = hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8"))
    return digest.hexdigest()[:24]


@dataclass(slots=True)
class Segment:
    """A contiguous run of text from a source, tagged with where it came from."""

    text: str
    page: int | None = None
    heading: str | None = None


@dataclass(slots=True)
class LoadedDocument:
    """Whatever a loader managed to pull out of one file."""

    title: str
    source_type: str
    segments: list[Segment]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(s.text for s in self.segments)


@dataclass(slots=True)
class Chunk:
    id: str
    document_id: str
    text: str
    index: int
    page: int | None = None
    heading: str | None = None
    char_start: int = 0
    char_end: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self, document_title: str) -> dict[str, Any]:
        """Flat dict for the vector store; Chroma rejects nested values."""
        meta = {
            "document_id": self.document_id,
            "document_title": document_title,
            "chunk_index": self.index,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }
        if self.page is not None:
            meta["page"] = self.page
        if self.heading:
            meta["heading"] = self.heading
        for key, value in self.metadata.items():
            if isinstance(value, (str, int, float, bool)):
                meta[key] = value
        return meta


@dataclass(slots=True)
class DocumentRecord:
    """The catalogue entry for an ingested file."""

    id: str
    title: str
    source_type: str
    chunk_count: int
    char_count: int
    created_at: str = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source_type": self.source_type,
            "chunk_count": self.chunk_count,
            "char_count": self.char_count,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class RetrievedChunk:
    """A chunk plus the scores that got it into the context window."""

    chunk_id: str
    document_id: str
    document_title: str
    text: str
    score: float
    dense_score: float = 0.0
    lexical_score: float = 0.0
    page: int | None = None
    heading: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "text": self.text,
            "score": round(self.score, 4),
            "dense_score": round(self.dense_score, 4),
            "lexical_score": round(self.lexical_score, 4),
            "page": self.page,
            "heading": self.heading,
        }


@dataclass(slots=True)
class Citation:
    marker: int
    chunk_id: str
    document_id: str
    document_title: str
    page: int | None
    snippet: str


@dataclass(slots=True)
class Answer:
    question: str
    text: str
    citations: list[Citation]
    contexts: list[RetrievedChunk]
    model: str
    latency_ms: int
    grounded: bool = True
