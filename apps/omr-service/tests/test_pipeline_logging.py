from pathlib import Path

import pytest

from src.services.errors import OMRPipelineError
from src.services.pipeline import recognize_file


def test_recognize_file_error_contains_run_log(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OMR_RUN_LOG_DIR", str(tmp_path / "runs"))

    def fake_preprocess(src: Path, dst: Path, *, scale_factor: float = 1.0) -> Path:
        dst.write_bytes(b"x")
        return dst

    def fake_run(*args, **kwargs):
        raise OMRPipelineError("Audiveris finished but no MusicXML was generated.")

    monkeypatch.setattr("src.services.pipeline.preprocess_image", fake_preprocess)
    monkeypatch.setattr("src.services.pipeline.AudiverisRunner.run", fake_run)

    input_png = tmp_path / "input.png"
    input_png.write_bytes(b"fake")

    with pytest.raises(OMRPipelineError) as exc:
        recognize_file(input_png, "png")

    assert "run-log:" in str(exc.value)


def test_recognize_file_retries_with_upscaled_input(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OMR_RUN_LOG_DIR", str(tmp_path / "runs"))

    scales_used: list[float] = []
    run_count = {"value": 0}

    def fake_preprocess(src: Path, dst: Path, *, scale_factor: float = 1.0) -> Path:
        scales_used.append(scale_factor)
        dst.write_bytes(b"x")
        return dst

    def fake_run(*args, **kwargs):
        run_count["value"] += 1
        if run_count["value"] == 1:
            raise OMRPipelineError("With a too low interline value of 9 pixels")
        result = tmp_path / "score.musicxml"
        result.write_text(
            "<score-partwise><part-list/><part id='P1'><measure number='1'>"
            "<attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
            "<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>"
            "</measure></part></score-partwise>",
            encoding="utf-8",
        )
        return result

    monkeypatch.setattr("src.services.pipeline.preprocess_image", fake_preprocess)
    monkeypatch.setattr("src.services.pipeline.AudiverisRunner.run", fake_run)

    input_png = tmp_path / "input.png"
    input_png.write_bytes(b"fake")

    result = recognize_file(input_png, "png")

    assert run_count["value"] == 2
    assert scales_used == [1.0, 2.0]
    assert any("upscaled x2.0" in warning for warning in result.meta.warnings)
