from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

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


@app.post("/api/v1/recognize")
async def recognize(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PNG/JPG/JPEG/PDF are supported")

    with NamedTemporaryFile(suffix=f".{suffix}", delete=True) as temp:
        content = await file.read()
        temp.write(content)
        temp.flush()

        try:
            response = recognize_file(Path(temp.name), suffix)
            return response.model_dump()
        except OMRPipelineError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc
