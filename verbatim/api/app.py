"""FastAPI application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from verbatim import __version__
from verbatim.api.routes import documents, query, system
from verbatim.config import get_settings
from verbatim.logging import get_logger
from verbatim.service import get_service

log = get_logger(__name__)

DESCRIPTION = """
Ask questions against your own documents and get answers with the passage each
claim came from.

Retrieval is hybrid: a dense vector index and BM25 run in parallel, their
rankings are fused, and MMR trims the redundancy before the passages reach the
model. Answers cite the passages they used; unsupported questions are refused
rather than answered.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the service on startup rather than on the first request - loading an
    # embedding model behind a user-facing request makes the first question look
    # like a 30-second hang.
    started = time.perf_counter()
    get_service()
    log.info("startup complete in %.1fs", time.perf_counter() - started)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Verbatim",
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def timing(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Response-Time-ms"] = f"{elapsed:.1f}"
        if elapsed > 2000:
            log.warning("slow request %s %s took %.0fms", request.method, request.url.path, elapsed)
        return response

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    api = FastAPI(title="Verbatim API", version=__version__, docs_url="/docs")
    for module in (system, documents, query):
        api.include_router(module.router)
    app.mount("/api", api)

    # The built frontend, when there is one. Mounted last so it never shadows /api.
    dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        def index() -> dict:
            return {
                "name": "Verbatim",
                "version": __version__,
                "docs": "/api/docs",
                "note": "run `make web` for the UI, or `npm run build` in web/ to serve it here",
            }

    return app


app = create_app()
