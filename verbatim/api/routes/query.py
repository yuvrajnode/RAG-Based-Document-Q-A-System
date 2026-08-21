from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from verbatim.api.deps import service_dependency
from verbatim.api.schemas import (
    AskRequest,
    AskResponse,
    CitationModel,
    SearchRequest,
    SearchResponse,
    SourceChunk,
)
from verbatim.service import RagService

router = APIRouter(tags=["query"])


def _history(request: AskRequest) -> list[dict] | None:
    if not request.history:
        return None
    return [turn.model_dump() for turn in request.history]


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, service: RagService = Depends(service_dependency)) -> AskResponse:
    answer = service.ask(
        request.question,
        top_k=request.top_k,
        document_ids=request.document_ids,
        history=_history(request),
    )
    return AskResponse(
        question=answer.question,
        answer=answer.text,
        citations=[CitationModel(**citation.as_dict()) for citation in answer.citations],
        sources=[SourceChunk(**chunk.as_dict()) for chunk in answer.contexts],
        model=answer.model,
        grounded=answer.grounded,
        latency_ms=answer.latency_ms,
    )


@router.post("/ask/stream")
def ask_stream(request: AskRequest, service: RagService = Depends(service_dependency)):
    """Server-sent events. One JSON object per event, `event:` naming the type.

    SSE rather than a websocket: the traffic is one-directional, it survives
    proxies that mangle upgrades, and the browser reconnects on its own.
    """

    def events() -> Iterator[str]:
        stream = service.engine.stream(
            request.question,
            top_k=request.top_k,
            document_ids=request.document_ids,
            history=_history(request),
        )
        for name, payload in stream:
            yield f"event: {name}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx would otherwise buffer the whole stream
        },
    )


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, service: RagService = Depends(service_dependency)) -> SearchResponse:
    """Retrieval without generation - useful for tuning, and for the UI's
    'show me what would be retrieved' panel."""
    result = service.search(
        request.query, top_k=request.top_k, document_ids=request.document_ids
    )
    return SearchResponse(
        query=request.query,
        results=[SourceChunk(**chunk.as_dict()) for chunk in result.chunks],
        strategy=result.strategy,
        took_ms=result.took_ms,
        dense_candidates=result.dense_candidates,
        lexical_candidates=result.lexical_candidates,
    )
