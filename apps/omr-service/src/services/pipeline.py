from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import traceback
import xml.etree.ElementTree as ET
from uuid import uuid4

from src.models import RecognizeResponse, ResponseMeta
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


def merge_recognize_results(results: list[RecognizeResponse]) -> RecognizeResponse:
    if not results:
        raise ValueError("At least one recognition result is required")
    if len(results) == 1:
        return results[0]

    notes = []
    playback_events = []
    warnings = []
    rhythm_issues = []
    beat_offset = 0.0
    measure_offset = 0

    for result in results:
        page_items = [*result.notes, *result.playbackEvents]
        first_measure = 1 if result.measureCount is not None else min(
            (item.sourceMeasure for item in page_items), default=1
        )
        notes.extend(
            note.model_copy(
                update={
                    "startBeat": round(note.startBeat + beat_offset, 4),
                    "sourceMeasure": note.sourceMeasure - first_measure + 1 + measure_offset,
                }
            )
            for note in result.notes
        )
        playback_events.extend(
            event.model_copy(
                update={
                    "startBeat": round(event.startBeat + beat_offset, 4),
                    "sourceMeasure": event.sourceMeasure - first_measure + 1 + measure_offset,
                }
            )
            for event in result.playbackEvents
        )
        warnings.extend(result.meta.warnings)
        rhythm_issues.extend(result.meta.rhythmIssues)

        event_end = max((item.startBeat + item.durationBeat for item in page_items), default=0.0)
        beat_offset += max(result.durationBeats or 0.0, event_end)
        measure_offset += result.measureCount if result.measureCount is not None else max(
            (item.sourceMeasure - first_measure + 1 for item in page_items), default=0
        )
        if result.durationBeats is None:
            warnings.append("Page duration unavailable; trailing rests cannot be recovered from legacy note data.")

    warnings.append(f"Merged {len(results)} files in filename order.")
    return RecognizeResponse(
        durationBeats=round(beat_offset, 4),
        measureCount=measure_offset,
        tempo=results[0].tempo,
        timeSignature=results[0].timeSignature,
        notes=notes,
        playbackEvents=playback_events,
        meta=ResponseMeta(engine="audiveris", inputType="multi-image", warnings=warnings, rhythmIssues=rhythm_issues),
    )


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
            candidates: list[tuple[RecognizeResponse, str, float]] = []

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
                    candidates.append((result, attempt_name, scale_factor))
                    _write_json(run_dir / f"{attempt_name}-quality.json", {
                        "rhythm_issues": result.meta.rhythmIssues,
                        "measure_count": result.measureCount,
                        "note_count": len(result.notes),
                    })
                    if not result.meta.rhythmIssues and result.playbackEvents:
                        break
                except (OMRPipelineError, ValueError, ET.ParseError) as exc:
                    attempt_errors.append(
                        {
                            "attempt": attempt_name,
                            "scale_factor": scale_factor,
                            "error": str(exc),
                        }
                    )
                    continue

            if candidates:
                # A shorter export may merely have lost problematic measures.
                # Compare only complete candidates; ties keep the earlier result.
                max_measures = max(item[0].measureCount or 0 for item in candidates)
                complete = [item for item in candidates if (item[0].measureCount or 0) == max_measures]
                result, attempt_name, scale_factor = min(
                    complete,
                    key=lambda item: (not bool(item[0].playbackEvents), len(item[0].meta.rhythmIssues)),
                )
                if result.meta.rhythmIssues:
                    result.meta.warnings.append("节奏校验未通过：已尝试不同分辨率，仍有小节或拍号需要核对原谱；未自动拉伸音长。")
                _write_json(run_dir / "result-summary.json", {
                    "tempo": result.tempo, "time_signature": result.timeSignature,
                    "note_count": len(result.notes), "status": "needs_review" if result.meta.rhythmIssues else "ok",
                    "attempt": attempt_name, "scale_factor": scale_factor,
                    "rhythm_issues": result.meta.rhythmIssues,
                })
                _write_json(run_dir / "attempt-errors.json", {"attempts": attempt_errors})
                return result

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
