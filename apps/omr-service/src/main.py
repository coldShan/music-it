from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.models import (
    CatalogEntryDetail,
    CatalogEntrySummary,
    RecognizeApiResponse,
    UpdateCatalogEntryRequest,
)
from src.services.catalog_service import (
    CatalogNotFoundError,
    CatalogService,
    CatalogStorageError,
    CatalogValidationError,
)
from src.services.errors import OMRPipelineError
from src.services.pipeline import recognize_file

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

app = FastAPI(title="music-it-omr-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/catalog", response_model=list[CatalogEntrySummary])
def list_catalog() -> list[CatalogEntrySummary]:
    service = CatalogService()
    try:
        return service.list_entries()
    except CatalogStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/catalog/{entry_id}", response_model=CatalogEntryDetail)
def get_catalog_entry(entry_id: str) -> CatalogEntryDetail:
    service = CatalogService()
    try:
        return service.get_entry(entry_id)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/v1/catalog/{entry_id}", response_model=CatalogEntrySummary)
def update_catalog_entry(entry_id: str, payload: UpdateCatalogEntryRequest) -> CatalogEntrySummary:
    service = CatalogService()
    try:
        return service.update_entry(
            entry_id,
            title=payload.title,
            melody_instrument=payload.melodyInstrument,
            left_hand_instrument=payload.leftHandInstrument,
        )
    except CatalogValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/v1/catalog/{entry_id}")
def delete_catalog_entry(entry_id: str) -> dict[str, Any]:
    service = CatalogService()
    try:
        deleted = service.delete_entry(entry_id)
        return {"id": deleted.id, "deleted": True}
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/catalog/reset")
def reset_catalog(confirm: str) -> dict[str, Any]:
    service = CatalogService()
    try:
        removed = service.reset_catalog(confirm)
        return {"reset": True, "removedEntries": removed}
    except CatalogValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CatalogStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/recognize", response_model=RecognizeApiResponse)
async def recognize(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PNG/JPG/JPEG/PDF are supported")

    service = CatalogService()

    content = await file.read()
    image_hash = service.compute_hash(content)
    existing_entry = service.find_by_hash(image_hash)
    if existing_entry is not None:
        try:
            touched = service.touch_entry(existing_entry.id)
            detail = service.get_entry(touched.id)
            return RecognizeApiResponse(
                **detail.result.model_dump(),
                catalogEntryId=detail.id,
                catalogTitle=detail.title,
                melodyInstrument=detail.melodyInstrument,
                leftHandInstrument=detail.leftHandInstrument,
                isReused=True,
            )
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except CatalogStorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    with NamedTemporaryFile(suffix=f".{suffix}", delete=True) as temp:
        temp.write(content)
        temp.flush()

        try:
            result = recognize_file(Path(temp.name), suffix)
            entry = service.create_entry(
                content=content,
                original_filename=file.filename or f"score.{suffix}",
                input_type=suffix,
                result=result,
                image_hash=image_hash,
            )
            return RecognizeApiResponse(
                **result.model_dump(),
                catalogEntryId=entry.id,
                catalogTitle=entry.title,
                melodyInstrument=entry.melodyInstrument,
                leftHandInstrument=entry.leftHandInstrument,
                isReused=False,
            )
        except CatalogStorageError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except OMRPipelineError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc
