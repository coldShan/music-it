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

    updated = service.update_title(detail.id, "新标题")
    assert updated.title == "新标题"

    deleted = service.delete_entry(detail.id)
    assert deleted.id == detail.id
    assert service.list_entries() == []


def test_update_title_rejects_empty_value(tmp_path: Path) -> None:
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
        service.update_title(detail.id, "   ")
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
