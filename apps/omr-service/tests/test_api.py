from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app
from src.models import PlaybackEvent, RecognizeResponse, RecognizedNote, ResponseMeta


def _fake_result(input_type: str = "png") -> RecognizeResponse:
    return RecognizeResponse(
        tempo=90,
        timeSignature="4/4",
        notes=[
            RecognizedNote(
                pitch="G4",
                midi=67,
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
                pitches=["G4"],
                midis=[67],
                hand="right",
                staff="1",
                voice="1",
                sourceMeasure=1,
            )
        ],
        meta=ResponseMeta(engine="audiveris", inputType=input_type, warnings=[]),
    )


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recognize_png_returns_notes_and_catalog_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CATALOG_PROJECT_ROOT", str(tmp_path))

    def fake_recognize(file_path, input_type):
        assert input_type == "png"
        return _fake_result(input_type)

    monkeypatch.setattr("src.main.recognize_file", fake_recognize)
    client = TestClient(app)

    response = client.post(
        "/api/v1/recognize",
        files={"file": ("score.png", BytesIO(b"fake-image"), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tempo"] == 90
    assert body["notes"][0]["pitch"] == "G4"
    assert body["notes"][0]["gateBeat"] == 0.92
    assert body["notes"][0]["phraseBreakAfter"] is False
    assert body["notes"][0]["articulation"] == "normal"
    assert body["playbackEvents"][0]["hand"] == "right"
    assert body["playbackEvents"][0]["pitches"] == ["G4"]
    assert body["catalogEntryId"]
    assert body["catalogTitle"] == "score"
    assert body["isReused"] is False


def test_recognize_same_file_reuses_catalog(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CATALOG_PROJECT_ROOT", str(tmp_path))

    calls = {"count": 0}

    def fake_recognize(file_path, input_type):
        calls["count"] += 1
        return _fake_result(input_type)

    monkeypatch.setattr("src.main.recognize_file", fake_recognize)
    client = TestClient(app)

    payload = {"file": ("score.png", BytesIO(b"same-image"), "image/png")}
    first = client.post("/api/v1/recognize", files=payload)
    second = client.post(
        "/api/v1/recognize",
        files={"file": ("score.png", BytesIO(b"same-image"), "image/png")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert second.json()["isReused"] is True


def test_catalog_endpoints(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CATALOG_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr("src.main.recognize_file", lambda *_: _fake_result())
    client = TestClient(app)

    recognize = client.post(
        "/api/v1/recognize",
        files={"file": ("song.png", BytesIO(b"catalog-image"), "image/png")},
    )
    entry_id = recognize.json()["catalogEntryId"]

    catalog = client.get("/api/v1/catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()) == 1

    detail = client.get(f"/api/v1/catalog/{entry_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == entry_id

    rename = client.patch(f"/api/v1/catalog/{entry_id}", json={"title": "遇见"})
    assert rename.status_code == 200
    assert rename.json()["title"] == "遇见"

    delete = client.delete(f"/api/v1/catalog/{entry_id}")
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True


def test_catalog_reset_endpoint(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CATALOG_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr("src.main.recognize_file", lambda *_: _fake_result())
    client = TestClient(app)

    client.post(
        "/api/v1/recognize",
        files={"file": ("song.png", BytesIO(b"catalog-image"), "image/png")},
    )

    denied = client.post("/api/v1/catalog/reset?confirm=WRONG")
    assert denied.status_code == 400

    reset = client.post("/api/v1/catalog/reset?confirm=WIPE_CATALOG")
    assert reset.status_code == 200
    assert reset.json()["reset"] is True
    assert reset.json()["removedEntries"] == 1

    catalog = client.get("/api/v1/catalog")
    assert catalog.status_code == 200
    assert catalog.json() == []
