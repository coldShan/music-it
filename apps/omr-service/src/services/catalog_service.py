from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from src.models import (
    CatalogEntryDetail,
    CatalogEntrySummary,
    InstrumentId,
    PlaybackEvent,
    RecognizedNote,
    RecognizeResponse,
    SUPPORTED_INSTRUMENTS,
)


class CatalogError(RuntimeError):
    """Base catalog service error."""


class CatalogNotFoundError(CatalogError):
    """Catalog entry does not exist."""


class CatalogValidationError(CatalogError):
    """Catalog request payload is invalid."""


class CatalogStorageError(CatalogError):
    """Catalog storage is broken or unreadable."""


class CatalogService:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or self._project_root()
        self.catalog_dir = self.root_dir / "storage" / "catalog"
        self.images_dir = self.catalog_dir / "images"
        self.records_dir = self.catalog_dir / "records"
        self.index_path = self.catalog_dir / "index.json"
        self._ensure_layout()

    @staticmethod
    def _project_root() -> Path:
        configured = os.getenv("CATALOG_PROJECT_ROOT")
        if configured:
            return Path(configured).expanduser().resolve()
        return Path(__file__).resolve().parents[4]

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def compute_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _default_instruments() -> tuple[InstrumentId, InstrumentId]:
        return "piano", "piano"

    def _ensure_layout(self) -> None:
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.records_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index({"version": 1, "entries": []})

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(content)
            temp_name = handle.name
        os.replace(temp_name, path)

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as handle:
            handle.write(content)
            temp_name = handle.name
        os.replace(temp_name, path)

    def _read_index(self) -> dict:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover
            raise CatalogStorageError(f"Failed to read catalog index: {exc}") from exc

        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise CatalogStorageError("Catalog index format is invalid")

        return data

    def _write_index(self, data: dict) -> None:
        self._atomic_write_text(
            self.index_path,
            json.dumps(data, ensure_ascii=False, indent=2),
        )

    def _record_path(self, entry_id: str) -> Path:
        return self.records_dir / f"{entry_id}.json"

    def _entry_by_id(self, entries: list[dict], entry_id: str) -> tuple[int, dict]:
        for index, item in enumerate(entries):
            if item.get("id") == entry_id:
                return index, item
        raise CatalogNotFoundError(f"Catalog entry not found: {entry_id}")

    def _summary_from_raw(self, raw: dict) -> CatalogEntrySummary:
        payload = dict(raw)
        melody_default, left_default = self._default_instruments()
        if payload.get("melodyInstrument") not in SUPPORTED_INSTRUMENTS:
            payload["melodyInstrument"] = melody_default
        if payload.get("leftHandInstrument") not in SUPPORTED_INSTRUMENTS:
            payload["leftHandInstrument"] = left_default
        return CatalogEntrySummary(**payload)

    @staticmethod
    def _normalize_instrument(value: str | None) -> InstrumentId | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized not in SUPPORTED_INSTRUMENTS:
            supported = ", ".join(SUPPORTED_INSTRUMENTS)
            raise CatalogValidationError(
                f"Unsupported instrument: {normalized}. Supported values: {supported}"
            )
        return normalized  # type: ignore[return-value]

    def _normalize_entries(self, entries: list[dict]) -> list[CatalogEntrySummary]:
        normalized = [self._summary_from_raw(item) for item in entries]
        normalized.sort(key=lambda item: item.updatedAt, reverse=True)
        return normalized

    def list_entries(self) -> list[CatalogEntrySummary]:
        index = self._read_index()
        return self._normalize_entries(index["entries"])

    def find_by_hash(self, image_hash: str) -> CatalogEntrySummary | None:
        index = self._read_index()
        for entry in index["entries"]:
            if entry.get("imageHash") == image_hash:
                return self._summary_from_raw(entry)
        return None

    @staticmethod
    def _fallback_playback_events(notes: list[RecognizedNote]) -> list[PlaybackEvent]:
        grouped: dict[tuple[float, int], list[RecognizedNote]] = {}
        for note in notes:
            key = (note.startBeat, note.sourceMeasure)
            grouped.setdefault(key, []).append(note)

        events: list[PlaybackEvent] = []
        for (start_beat, source_measure), chord_notes in sorted(grouped.items()):
            ordered = sorted(chord_notes, key=lambda item: item.midi)
            events.append(
                PlaybackEvent(
                    startBeat=round(start_beat, 4),
                    durationBeat=round(max(item.durationBeat for item in ordered), 4),
                    gateBeat=round(max(item.gateBeat for item in ordered), 4),
                    pitches=[item.pitch for item in ordered],
                    midis=[item.midi for item in ordered],
                    hand="right",
                    staff="1",
                    voice="1",
                    sourceMeasure=source_measure,
                )
            )
        return events

    def get_entry(self, entry_id: str) -> CatalogEntryDetail:
        index = self._read_index()
        _, raw_summary = self._entry_by_id(index["entries"], entry_id)
        summary = self._summary_from_raw(raw_summary)

        record_path = self._record_path(entry_id)
        if not record_path.exists():
            raise CatalogStorageError(f"Catalog record is missing: {record_path}")

        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            result = RecognizeResponse(**record["result"])
            if not result.playbackEvents:
                result.playbackEvents = self._fallback_playback_events(result.notes)
        except Exception as exc:
            raise CatalogStorageError(f"Failed to read catalog record: {exc}") from exc

        return CatalogEntryDetail(**summary.model_dump(), result=result)

    def _sync_record_summary(self, summary: CatalogEntrySummary) -> None:
        record_path = self._record_path(summary.id)
        if not record_path.exists():
            return

        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover
            raise CatalogStorageError(f"Failed to update catalog record: {exc}") from exc

        record["summary"] = summary.model_dump()
        self._atomic_write_text(
            record_path,
            json.dumps(record, ensure_ascii=False, indent=2),
        )

    def touch_entry(self, entry_id: str) -> CatalogEntrySummary:
        index = self._read_index()
        entry_index, raw_summary = self._entry_by_id(index["entries"], entry_id)
        summary = self._summary_from_raw(raw_summary)
        summary.updatedAt = self._now_iso()
        index["entries"][entry_index] = summary.model_dump()
        self._write_index(index)
        self._sync_record_summary(summary)
        return summary

    def create_entry(
        self,
        *,
        content: bytes,
        original_filename: str,
        input_type: str,
        result: RecognizeResponse,
        image_hash: str,
    ) -> CatalogEntryDetail:
        existing = self.find_by_hash(image_hash)
        if existing:
            self.touch_entry(existing.id)
            return self.get_entry(existing.id)

        suffix = Path(original_filename).suffix.lower()
        if not suffix:
            suffix = f".{input_type}"

        image_rel_path = Path("storage") / "catalog" / "images" / f"{image_hash}{suffix}"
        image_abs_path = self.root_dir / image_rel_path
        if not image_abs_path.exists():
            self._atomic_write_bytes(image_abs_path, content)

        now = self._now_iso()
        title = Path(original_filename).stem.strip() or f"score-{image_hash[:8]}"
        melody_default, left_default = self._default_instruments()
        summary = CatalogEntrySummary(
            id=image_hash,
            title=title,
            imagePath=image_rel_path.as_posix(),
            inputType=input_type,
            tempo=result.tempo,
            timeSignature=result.timeSignature,
            noteCount=len(result.notes),
            createdAt=now,
            updatedAt=now,
            imageHash=image_hash,
            melodyInstrument=melody_default,
            leftHandInstrument=left_default,
        )

        index = self._read_index()
        index["entries"].append(summary.model_dump())
        self._write_index(index)

        record = {
            "summary": summary.model_dump(),
            "result": result.model_dump(),
        }
        self._atomic_write_text(
            self._record_path(summary.id),
            json.dumps(record, ensure_ascii=False, indent=2),
        )

        return CatalogEntryDetail(**summary.model_dump(), result=result)

    def update_entry(
        self,
        entry_id: str,
        *,
        title: str | None = None,
        melody_instrument: str | None = None,
        left_hand_instrument: str | None = None,
    ) -> CatalogEntrySummary:
        normalized_title = title.strip() if title is not None else None
        normalized_melody = self._normalize_instrument(melody_instrument)
        normalized_left = self._normalize_instrument(left_hand_instrument)

        if title is not None and not normalized_title:
            raise CatalogValidationError("Title cannot be empty")

        has_update = any(
            value is not None and value != ""
            for value in (normalized_title, normalized_melody, normalized_left)
        )
        if not has_update:
            raise CatalogValidationError(
                "At least one of title, melodyInstrument, leftHandInstrument is required"
            )

        index = self._read_index()
        entry_index, raw_summary = self._entry_by_id(index["entries"], entry_id)
        summary = self._summary_from_raw(raw_summary)
        if normalized_title is not None:
            summary.title = normalized_title
        if normalized_melody is not None:
            summary.melodyInstrument = normalized_melody
        if normalized_left is not None:
            summary.leftHandInstrument = normalized_left
        summary.updatedAt = self._now_iso()

        index["entries"][entry_index] = summary.model_dump()
        self._write_index(index)
        self._sync_record_summary(summary)

        return summary

    def delete_entry(self, entry_id: str) -> CatalogEntrySummary:
        index = self._read_index()
        entry_index, raw_summary = self._entry_by_id(index["entries"], entry_id)
        summary = self._summary_from_raw(raw_summary)

        del index["entries"][entry_index]
        self._write_index(index)

        image_abs_path = self.root_dir / Path(summary.imagePath)
        if image_abs_path.exists():
            image_abs_path.unlink()

        record_path = self._record_path(summary.id)
        if record_path.exists():
            record_path.unlink()

        return summary

    def reset_catalog(self, confirm: str) -> int:
        if confirm != "WIPE_CATALOG":
            raise CatalogValidationError("Invalid reset confirmation token")

        index = self._read_index()
        removed_entries = len(index["entries"])

        for directory in (self.images_dir, self.records_dir):
            if not directory.exists():
                continue
            for item in directory.iterdir():
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)

        self._write_index({"version": 1, "entries": []})
        return removed_entries
