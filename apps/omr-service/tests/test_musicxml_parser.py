from pathlib import Path
import zipfile

from src.services.musicxml_parser import parse_musicxml


def test_parse_musicxml_extracts_tempo_signature_and_notes() -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample.musicxml"

    result = parse_musicxml(fixture)

    assert result.tempo == 90
    assert result.timeSignature == "4/4"
    assert len(result.notes) == 3
    assert result.notes[0].pitch == "G4"
    assert result.notes[0].midi == 67
    assert result.notes[0].startBeat == 0.0
    assert result.notes[0].durationBeat == 1.0
    assert result.notes[2].pitch == "B4"
    assert result.notes[2].startBeat == 3.0


def test_parse_mxl_extracts_notes(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample.musicxml"
    mxl_path = tmp_path / "sample.mxl"

    with zipfile.ZipFile(mxl_path, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="score.musicxml" media-type="application/vnd.recordare.musicxml+xml"/>
  </rootfiles>
</container>
""",
        )
        archive.write(fixture, arcname="score.musicxml")

    result = parse_musicxml(mxl_path)

    assert result.tempo == 90
    assert result.timeSignature == "4/4"
    assert len(result.notes) == 3


def test_parse_musicxml_keeps_right_hand_staff_only(tmp_path: Path) -> None:
    score = tmp_path / "two-staff.musicxml"
    score.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Music</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>C</step><octave>5</octave></pitch>
        <duration>1</duration>
        <staff>1</staff>
      </note>
      <note>
        <pitch><step>C</step><octave>3</octave></pitch>
        <duration>1</duration>
        <staff>2</staff>
      </note>
    </measure>
  </part>
</score-partwise>
""",
        encoding="utf-8",
    )

    result = parse_musicxml(score)

    assert len(result.notes) == 1
    assert result.notes[0].pitch == "C5"
    assert any("multi-staff" in warning for warning in result.meta.warnings)
