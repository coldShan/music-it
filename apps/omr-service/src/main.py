from __future__ import annotations

import hashlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory
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
from src.services.pipeline import merge_recognize_results, recognize_file

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
async def recognize(file: list[UploadFile] = File(...)):
    uploads = sorted(file, key=lambda item: _filename_sort_key(item.filename or ""))
    suffixes = [Path(item.filename or "").suffix.lower().lstrip(".") for item in uploads]
    if not uploads or any(suffix not in ALLOWED_EXTENSIONS for suffix in suffixes):
        raise HTTPException(status_code=400, detail="Only PNG/JPG/JPEG/PDF are supported")

    service = CatalogService()

    contents = [await item.read() for item in uploads]
    image_hash = _files_hash(contents, service)
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

    with TemporaryDirectory(prefix="omr-upload-") as temp_dir:
        try:
            temp = Path(temp_dir)
            page_results = []
            for index, (content, suffix) in enumerate(zip(contents, suffixes, strict=True)):
                page_path = temp / f"{index:04d}.{suffix}"
                page_path.write_bytes(content)
                page_results.append(recognize_file(page_path, suffix))
            result = merge_recognize_results(page_results)
            first_upload = uploads[0]
            entry = service.create_entry(
                content=contents[0],
                original_filename=first_upload.filename or f"score.{suffixes[0]}",
                input_type=result.meta.inputType,
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


def _filename_sort_key(filename: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", filename)
    )


def _files_hash(contents: list[bytes], service: CatalogService) -> str:
    if len(contents) == 1:
        return service.compute_hash(contents[0])

    digest = hashlib.sha256()
    for content in contents:
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()
