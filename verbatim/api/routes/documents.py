from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from verbatim.api.deps import service_dependency, settings_dependency
from verbatim.api.schemas import (
    BatchIngestResponse,
    DocumentListResponse,
    DocumentSummary,
    IngestResponse,
)
from verbatim.config import Settings
from verbatim.ingest.loaders import SUPPORTED_EXTENSIONS, UnsupportedFileType
from verbatim.logging import get_logger
from verbatim.service import RagService

log = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

_CHUNK = 1024 * 1024


def _spool(upload: UploadFile, destination: Path, limit: int) -> int:
    """Stream to disk with a hard cap, so a large upload cannot exhaust memory."""
    written = 0
    with destination.open("wb") as handle:
        while chunk := upload.file.read(_CHUNK):
            written += len(chunk)
            if written > limit:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"file exceeds the {limit // (1024 * 1024)}MB upload limit",
                )
            handle.write(chunk)
    return written


def _ingest_upload(upload: UploadFile, service: RagService, settings: Settings) -> IngestResponse:
    name = Path(upload.filename or "upload").name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"{suffix or 'this file type'} is not supported. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    workspace = Path(tempfile.mkdtemp(prefix="verbatim-", dir=settings.storage_dir / "uploads"))
    target = workspace / name
    try:
        size = _spool(upload, target, settings.max_upload_bytes)
        if size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "the uploaded file is empty")
        result = service.ingest_file(target, title=Path(name).stem.replace("_", " "))
    except UnsupportedFileType as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    return IngestResponse(
        document=DocumentSummary(**result.record.as_dict()),
        replaced=result.replaced,
        took_ms=result.took_ms,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = 200, offset: int = 0, service: RagService = Depends(service_dependency)
) -> DocumentListResponse:
    records = service.documents(limit=limit, offset=offset)
    return DocumentListResponse(
        documents=[DocumentSummary(**record.as_dict()) for record in records],
        total_chunks=sum(record.chunk_count for record in records),
    )


@router.post("", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    service: RagService = Depends(service_dependency),
    settings: Settings = Depends(settings_dependency),
) -> IngestResponse:
    return _ingest_upload(file, service, settings)


@router.post("/batch", response_model=BatchIngestResponse, status_code=status.HTTP_201_CREATED)
def upload_documents(
    files: list[UploadFile] = File(...),
    service: RagService = Depends(service_dependency),
    settings: Settings = Depends(settings_dependency),
) -> BatchIngestResponse:
    """Partial success is the useful behaviour here: one bad file in a drop of
    twenty should not lose the other nineteen."""
    ingested, failed = [], []
    for upload in files:
        try:
            ingested.append(_ingest_upload(upload, service, settings))
        except HTTPException as exc:
            failed.append({"filename": upload.filename or "unknown", "error": str(exc.detail)})
        except Exception as exc:
            log.exception("ingestion failed for %s", upload.filename)
            failed.append({"filename": upload.filename or "unknown", "error": str(exc)})
    return BatchIngestResponse(ingested=ingested, failed=failed)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, service: RagService = Depends(service_dependency)) -> None:
    if not service.delete_document(document_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such document")


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_documents(service: RagService = Depends(service_dependency)) -> None:
    service.clear()
