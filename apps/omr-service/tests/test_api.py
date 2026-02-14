from io import BytesIO

from fastapi.testclient import TestClient

from src.main import app


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recognize_png_returns_notes(monkeypatch) -> None:
    from src.models import RecognizeResponse, RecognizedNote, ResponseMeta

    def fake_recognize(file_path, input_type):
        assert input_type == "png"
        return RecognizeResponse(
            tempo=90,
            timeSignature="4/4",
            notes=[
                RecognizedNote(
                    pitch="G4",
                    midi=67,
                    startBeat=0,
                    durationBeat=1,
                    sourceMeasure=1,
                )
            ],
            meta=ResponseMeta(engine="audiveris", inputType="png", warnings=[]),
        )

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


def test_recognize_pdf_calls_pipeline(monkeypatch) -> None:
    from src.models import RecognizeResponse, ResponseMeta

    def fake_recognize(file_path, input_type):
        assert input_type == "pdf"
        return RecognizeResponse(
            tempo=120,
            timeSignature="4/4",
            notes=[],
            meta=ResponseMeta(engine="audiveris", inputType="pdf", warnings=[]),
        )

    monkeypatch.setattr("src.main.recognize_file", fake_recognize)
    client = TestClient(app)

    response = client.post(
        "/api/v1/recognize",
        files={"file": ("score.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["meta"]["inputType"] == "pdf"
