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


def test_merge_preserves_leading_trailing_and_silent_pages() -> None:
    from src.models import RecognizeResponse, RecognizedNote, ResponseMeta
    from src.services.pipeline import merge_recognize_results

    note = RecognizedNote(
        pitch="C4", midi=60, startBeat=3, durationBeat=1, gateBeat=0.92,
        phraseBreakAfter=True, articulation="normal", sourceMeasure=2,
    )
    first = RecognizeResponse(
        tempo=120, timeSignature="3/4", notes=[note], durationBeats=9,
        measureCount=3, meta=ResponseMeta(inputType="png"),
    )
    silent = first.model_copy(update={"notes": [], "durationBeats": 6, "measureCount": 2})
    last = first.model_copy(update={
        "notes": [note.model_copy(update={"startBeat": 1, "sourceMeasure": 1})],
        "durationBeats": 3, "measureCount": 1,
    })
    merged = merge_recognize_results([first, silent, last])
    assert [n.startBeat for n in merged.notes] == [3, 16]
    assert [n.sourceMeasure for n in merged.notes] == [2, 6]
    assert merged.durationBeats == 18
    assert merged.measureCount == 6


@pytest.mark.parametrize('second_beats,expected_beats', [(3, 3), (5, 4)])
def test_successful_but_irregular_export_is_retried(monkeypatch, tmp_path, second_beats, expected_beats):
    monkeypatch.setenv('OMR_RUN_LOG_DIR', str(tmp_path / 'runs'))
    calls = []
    def preprocess(src, dst, **kwargs):
        dst.write_bytes(b'x')
        return dst
    def run(*args, **kwargs):
        beats = 4 if not calls else second_beats
        calls.append(beats)
        path = tmp_path / f'{len(calls)}.musicxml'
        path.write_text(f'''<score-partwise><part id="P1">
          <measure number="1"><attributes><divisions>1</divisions><time><beats>3</beats><beat-type>4</beat-type></time></attributes>
          <note><pitch><step>C</step><octave>4</octave></pitch><duration>3</duration></note></measure>
          <measure number="2"><note><pitch><step>D</step><octave>4</octave></pitch><duration>{beats}</duration></note></measure>
        </part></score-partwise>''')
        return path
    monkeypatch.setattr('src.services.pipeline.preprocess_image', preprocess)
    monkeypatch.setattr('src.services.pipeline.AudiverisRunner.run', run)
    source = tmp_path / 'input.png'
    source.write_bytes(b'x')
    result = recognize_file(source, 'png')
    assert len(calls) == 2
    assert result.notes[1].durationBeat == expected_beats
    assert bool(result.meta.rhythmIssues) == (expected_beats != 3)
