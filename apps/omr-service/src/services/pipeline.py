from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import traceback
from uuid import uuid4

from src.models import RecognizeResponse
from src.services.audiveris import AudiverisRunner
from src.services.errors import OMRPipelineError
from src.services.musicxml_parser import parse_musicxml
from src.services.pdf_utils import pdf_first_page_to_png
from src.services.preprocess import preprocess_image


def _log_base_dir() -> Path:
    configured_raw = os.getenv("OMR_RUN_LOG_DIR")
    if configured_raw:
        return Path(configured_raw).expanduser()
    return Path(__file__).resolve().parents[2] / "run-logs"


def _new_run_dir() -> Path:
    run_id = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
    run_dir = _log_base_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def recognize_file(file_path: Path, input_type: str) -> RecognizeResponse:
    run_dir = _new_run_dir()
    _write_json(
        run_dir / "run-meta.json",
        {
            "input_type": input_type,
            "source_file": str(file_path),
            "started_at": datetime.now().isoformat(),
        },
    )

    with TemporaryDirectory(prefix="omr-work-") as temp_dir:
        temp = Path(temp_dir)
        source_image = file_path

        if input_type == "pdf":
            source_image = pdf_first_page_to_png(file_path, temp / "page-1.png")
            shutil.copy2(source_image, run_dir / "pdf-first-page.png")
        else:
            shutil.copy2(file_path, run_dir / f"input.{input_type}")

        try:
            runner = AudiverisRunner()
            attempts = [("base", 1.0), ("up2", 2.0)]
            attempt_errors: list[dict[str, str | float]] = []

            for attempt_name, scale_factor in attempts:
                preprocessed = preprocess_image(
                    source_image,
                    temp / f"preprocessed-{attempt_name}.png",
                    scale_factor=scale_factor,
                )
                shutil.copy2(preprocessed, run_dir / preprocessed.name)

                try:
                    musicxml = runner.run(
                        preprocessed,
                        temp / f"audiveris-out-{attempt_name}",
                        debug_dir=run_dir / f"attempt-{attempt_name}",
                    )
                    shutil.copy2(musicxml, run_dir / f"{attempt_name}-{musicxml.name}")

                    result = parse_musicxml(musicxml, input_type=input_type)
                    if input_type == "pdf":
                        result.meta.warnings.append("PDF only first page is processed in MVP.")
                    if scale_factor > 1.0:
                        result.meta.warnings.append(
                            f"Input was upscaled x{scale_factor:.1f} for OMR stability."
                        )
                    result.meta.warnings.append(f"Run log: {run_dir}")

                    _write_json(
                        run_dir / "result-summary.json",
                        {
                            "tempo": result.tempo,
                            "time_signature": result.timeSignature,
                            "note_count": len(result.notes),
                            "status": "ok",
                            "attempt": attempt_name,
                            "scale_factor": scale_factor,
                        },
                    )
                    return result
                except OMRPipelineError as exc:
                    attempt_errors.append(
                        {
                            "attempt": attempt_name,
                            "scale_factor": scale_factor,
                            "error": str(exc),
                        }
                    )
                    continue

            _write_json(run_dir / "attempt-errors.json", {"attempts": attempt_errors})
            raise OMRPipelineError(
                "OMR failed for all preprocessing attempts (base, upscaled x2). "
                f"Last error: {attempt_errors[-1]['error'] if attempt_errors else 'unknown'}"
            )
        except Exception as exc:
            _write_json(
                run_dir / "result-summary.json",
                {
                    "status": "error",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            if isinstance(exc, OMRPipelineError):
                raise OMRPipelineError(f"{exc} [run-log: {run_dir}]") from exc
            raise
