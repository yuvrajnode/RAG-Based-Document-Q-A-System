"""Request and response models for the HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    documents: int
    chunks: int
    generative: bool


class DocumentSummary(BaseModel):
    id: str
    title: str
    source_type: str
    chunk_count: int
    char_count: int
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    total_chunks: int


class IngestResponse(BaseModel):
    document: DocumentSummary
    replaced: bool
    took_ms: int


class BatchIngestResponse(BaseModel):
    ingested: list[IngestResponse]
    failed: list[dict[str, str]] = Field(default_factory=list)


class SourceChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    text: str
    score: float
    dense_score: float
    lexical_score: float
    page: int | None = None
    heading: str | None = None


class CitationModel(BaseModel):
    marker: int
    chunk_id: str
    document_id: str
    document_title: str
    page: int | None = None
    snippet: str


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    document_ids: list[str] | None = None
    history: list[Turn] | None = None

    @field_validator("question")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question cannot be empty")
        return value


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationModel]
    sources: list[SourceChunk]
    model: str
    grounded: bool
    latency_ms: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    document_ids: list[str] | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SourceChunk]
    strategy: str
    took_ms: int
    dense_candidates: int
    lexical_candidates: int
