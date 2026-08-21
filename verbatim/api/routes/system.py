from __future__ import annotations

from fastapi import APIRouter, Depends

from verbatim import __version__
from verbatim.api.deps import service_dependency
from verbatim.api.schemas import HealthResponse
from verbatim.service import RagService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(service: RagService = Depends(service_dependency)) -> HealthResponse:
    stats = service.stats()
    return HealthResponse(
        version=__version__,
        documents=stats["documents"],
        chunks=stats["chunks"],
        generative=stats["llm"]["generative"],
    )


@router.get("/stats")
def stats(service: RagService = Depends(service_dependency)) -> dict:
    """Everything the UI needs to describe the running configuration."""
    return service.stats()
