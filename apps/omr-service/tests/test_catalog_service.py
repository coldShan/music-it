from pathlib import Path

from src.models import PlaybackEvent, RecognizeResponse, RecognizedNote, ResponseMeta
from src.services.catalog_service import CatalogService, CatalogValidationError


def _result() -> RecognizeResponse:
    return RecognizeResponse(
        tempo=88,
        timeSignature="4/4",
        notes=[
            RecognizedNote(
                pitch="A4",
                midi=69,
                startBeat=0,
                durationBeat=1,
                gateBeat=0.92,
                phraseBreakAfter=False,
                articulation="normal",
                sourceMeasure=1,
            )
        ],
        playbackEvents=[
            PlaybackEvent(
                startBeat=0,
                durationBeat=1,
                gateBeat=0.92,
                pitches=["A4"],
                midis=[69],
                hand="right",
                staff="1",
                voice="1",
                sourceMeasure=1,
            )
        ],
        meta=ResponseMeta(engine="audiveris", inputType="png", warnings=[]),
    )


def test_create_reuse_and_list_entries(tmp_path: Path) -> None:
    service = CatalogService(root_dir=tmp_path)
    content = b"demo-image"
    image_hash = service.compute_hash(content)

    first = service.create_entry(
        content=content,
        original_filename="demo.png",
        input_type="png",
        result=_result(),
        image_hash=image_hash,
    )
    reused_summary = service.find_by_hash(image_hash)
    assert reused_summary is not None

    service.touch_entry(first.id)
    detail = service.get_entry(first.id)
    entries = service.list_entries()

    assert detail.id == first.id
    assert len(entries) == 1
    assert entries[0].imageHash == image_hash
    assert entries[0].melodyInstrument == "piano"
    assert entries[0].leftHandInstrument == "piano"
    assert detail.result.playbackEvents[0].pitches == ["A4"]


def test_update_and_delete_entry(tmp_path: Path) -> None:
    service = CatalogService(root_dir=tmp_path)
    content = b"another-image"
    image_hash = service.compute_hash(content)
    detail = service.create_entry(
        content=content,
        original_filename="a.png",
        input_type="png",
        result=_result(),
        image_hash=image_hash,
    )

    updated = service.update_entry(
        detail.id,
        title="新标题",
        melody_instrument="violin",
        left_hand_instrument="guitar",
    )
    assert updated.title == "新标题"
    assert updated.melodyInstrument == "violin"
    assert updated.leftHandInstrument == "guitar"

    deleted = service.delete_entry(detail.id)
    assert deleted.id == detail.id
    assert service.list_entries() == []


def test_update_entry_rejects_invalid_payload(tmp_path: Path) -> None:
    service = CatalogService(root_dir=tmp_path)
    content = b"another-image"
    image_hash = service.compute_hash(content)
    detail = service.create_entry(
        content=content,
        original_filename="a.png",
        input_type="png",
        result=_result(),
        image_hash=image_hash,
    )

    try:
        service.update_entry(detail.id, title="   ")
        raise AssertionError("should raise")
    except CatalogValidationError:
        pass

    try:
        service.update_entry(detail.id, melody_instrument="bad-value")
        raise AssertionError("should raise")
    except CatalogValidationError:
        pass


def test_reset_catalog_clears_files_and_rebuilds_index(tmp_path: Path) -> None:
    service = CatalogService(root_dir=tmp_path)
    content = b"for-reset"
    image_hash = service.compute_hash(content)
    detail = service.create_entry(
        content=content,
        original_filename="reset.png",
        input_type="png",
        result=_result(),
        image_hash=image_hash,
    )

    removed = service.reset_catalog("WIPE_CATALOG")
    assert removed == 1
    assert service.list_entries() == []
    assert not (service.root_dir / detail.imagePath).exists()
    assert not (service.records_dir / f"{detail.id}.json").exists()


def test_reset_catalog_rejects_wrong_token(tmp_path: Path) -> None:
    service = CatalogService(root_dir=tmp_path)
    try:
        service.reset_catalog("NOPE")
        raise AssertionError("should raise")
    except CatalogValidationError:
        pass


def test_get_entry_fallbacks_playback_events_for_legacy_record(tmp_path: Path) -> None:
    service = CatalogService(root_dir=tmp_path)
    content = b"legacy-image"
    image_hash = service.compute_hash(content)
    detail = service.create_entry(
        content=content,
        original_filename="legacy.png",
        input_type="png",
        result=_result(),
        image_hash=image_hash,
    )

    record_path = service.records_dir / f"{detail.id}.json"
    raw = record_path.read_text(encoding="utf-8")
    raw = raw.replace('"playbackEvents": [', '"playbackEvents_legacy_removed": [')
    record_path.write_text(raw, encoding="utf-8")

    loaded = service.get_entry(detail.id)
    assert len(loaded.result.playbackEvents) == 1
    assert loaded.result.playbackEvents[0].hand == "right"


def test_list_entries_fallbacks_instruments_for_legacy_index(tmp_path: Path) -> None:
    service = CatalogService(root_dir=tmp_path)
    detail = service.create_entry(
        content=b"legacy",
        original_filename="legacy.png",
        input_type="png",
        result=_result(),
        image_hash=service.compute_hash(b"legacy"),
    )

    index_data = service._read_index()  # noqa: SLF001
    index_data["entries"][0].pop("melodyInstrument", None)
    index_data["entries"][0].pop("leftHandInstrument", None)
    service._write_index(index_data)  # noqa: SLF001

    entries = service.list_entries()
    assert entries[0].id == detail.id
    assert entries[0].melodyInstrument == "piano"
    assert entries[0].leftHandInstrument == "piano"
