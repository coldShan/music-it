from pathlib import Path
from textwrap import dedent
import zipfile

from src.services.musicxml_parser import parse_musicxml


def _write_score(path: Path, body: str) -> None:
    path.write_text(
        dedent(
            f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <score-partwise version="3.1">
              <part-list>
                <score-part id="P1"><part-name>Music</part-name></score-part>
              </part-list>
              <part id="P1">
                {body}
              </part>
            </score-partwise>
            """
        ).lstrip(),
        encoding="utf-8",
    )


def test_parse_musicxml_extracts_tempo_signature_and_phrase_fields() -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample.musicxml"

    result = parse_musicxml(fixture)

    assert result.tempo == 90
    assert result.timeSignature == "4/4"
    assert len(result.notes) == 3
    assert result.notes[0].pitch == "G4"
    assert result.notes[0].midi == 67
    assert result.notes[0].startBeat == 0.0
    assert result.notes[0].durationBeat == 1.0
    assert result.notes[0].gateBeat == 0.92
    assert result.notes[0].phraseBreakAfter is False
    assert result.notes[0].articulation == "normal"
    assert result.notes[1].phraseBreakAfter is True
    assert result.notes[1].gateBeat == 0.782
    assert result.notes[2].pitch == "B4"
    assert result.notes[2].startBeat == 3.0
    assert result.notes[2].phraseBreakAfter is True
    assert result.playbackEvents
    assert result.playbackEvents[0].hand == "right"


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
    assert all(note.gateBeat > 0 for note in result.notes)
    assert all(event.hand in {"right", "left"} for event in result.playbackEvents)


def test_parse_musicxml_uses_backup_forward_timeline(tmp_path: Path) -> None:
    score = tmp_path / "timeline.musicxml"
    _write_score(
        score,
        """
        <measure number="1">
          <attributes>
            <divisions>1</divisions>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes>
          <note>
            <pitch><step>C</step><octave>5</octave></pitch>
            <duration>1</duration>
            <voice>1</voice>
            <staff>1</staff>
          </note>
          <backup><duration>1</duration></backup>
          <note>
            <pitch><step>C</step><octave>3</octave></pitch>
            <duration>2</duration>
            <voice>2</voice>
            <staff>2</staff>
          </note>
          <forward><duration>1</duration></forward>
          <note>
            <pitch><step>D</step><octave>5</octave></pitch>
            <duration>1</duration>
            <voice>1</voice>
            <staff>1</staff>
          </note>
        </measure>
        """,
    )

    result = parse_musicxml(score)
    assert [note.pitch for note in result.notes] == ["C5", "D5"]
    assert [note.startBeat for note in result.notes] == [0.0, 3.0]


def test_parse_musicxml_prefers_staff_one_for_melody(tmp_path: Path) -> None:
    score = tmp_path / "voice-pick.musicxml"
    _write_score(
        score,
        """
        <measure number="1">
          <attributes><divisions>1</divisions></attributes>
          <note>
            <pitch><step>C</step><octave>6</octave></pitch>
            <duration>1</duration>
            <voice>1</voice>
            <staff>1</staff>
          </note>
          <backup><duration>1</duration></backup>
          <note>
            <pitch><step>C</step><octave>3</octave></pitch>
            <duration>1</duration>
            <voice>2</voice>
            <staff>2</staff>
          </note>
          <note>
            <pitch><step>D</step><octave>3</octave></pitch>
            <duration>1</duration>
            <voice>2</voice>
            <staff>2</staff>
          </note>
        </measure>
        """,
    )

    result = parse_musicxml(score)
    assert [note.pitch for note in result.notes] == ["C6"]
    assert any("Right-hand lead voice selected" in warning for warning in result.meta.warnings)


def test_parse_musicxml_selects_voice_by_density_then_pitch_within_staff(tmp_path: Path) -> None:
    score = tmp_path / "voice-pick-same-staff.musicxml"
    _write_score(
        score,
        """
        <measure number="1">
          <attributes><divisions>1</divisions></attributes>
          <note>
            <pitch><step>C</step><octave>5</octave></pitch>
            <duration>1</duration>
            <voice>1</voice>
            <staff>1</staff>
          </note>
          <backup><duration>1</duration></backup>
          <note>
            <pitch><step>C</step><octave>4</octave></pitch>
            <duration>1</duration>
            <voice>2</voice>
            <staff>1</staff>
          </note>
          <note>
            <pitch><step>D</step><octave>4</octave></pitch>
            <duration>1</duration>
            <voice>2</voice>
            <staff>1</staff>
          </note>
        </measure>
        """,
    )

    result = parse_musicxml(score)
    assert [note.pitch for note in result.notes] == ["C4", "D4"]
    assert any("multi-voice" in warning for warning in result.meta.warnings)


def test_parse_musicxml_merges_tie_chain(tmp_path: Path) -> None:
    score = tmp_path / "tie-chain.musicxml"
    _write_score(
        score,
        """
        <measure number="1">
          <attributes><divisions>1</divisions></attributes>
          <note>
            <pitch><step>G</step><octave>4</octave></pitch>
            <duration>1</duration>
            <tie type="start"/>
          </note>
        </measure>
        <measure number="2">
          <note>
            <pitch><step>G</step><octave>4</octave></pitch>
            <duration>1</duration>
            <tie type="stop"/>
            <tie type="start"/>
          </note>
          <note>
            <pitch><step>G</step><octave>4</octave></pitch>
            <duration>1</duration>
            <tie type="stop"/>
          </note>
        </measure>
        """,
    )

    result = parse_musicxml(score)
    assert len(result.notes) == 1
    assert result.notes[0].durationBeat == 3.0
    assert result.notes[0].gateBeat == 3.0
    assert result.notes[0].articulation == "tie"
    assert result.notes[0].phraseBreakAfter is True


def test_parse_musicxml_slur_and_staccato_affect_gate(tmp_path: Path) -> None:
    score = tmp_path / "slur-staccato.musicxml"
    _write_score(
        score,
        """
        <measure number="1">
          <attributes><divisions>1</divisions></attributes>
          <note>
            <pitch><step>C</step><octave>4</octave></pitch>
            <duration>1</duration>
            <notations><slur type="start"/></notations>
          </note>
          <note>
            <pitch><step>D</step><octave>4</octave></pitch>
            <duration>1</duration>
            <notations><slur type="stop"/></notations>
          </note>
          <note>
            <pitch><step>E</step><octave>4</octave></pitch>
            <duration>1</duration>
            <notations><articulations><staccato/></articulations></notations>
          </note>
        </measure>
        """,
    )

    result = parse_musicxml(score)
    assert len(result.notes) == 3
    assert result.notes[0].articulation == "slur"
    assert result.notes[0].gateBeat == 0.98
    assert result.notes[1].articulation == "slur"
    assert result.notes[2].articulation == "staccato"
    assert result.notes[2].gateBeat == 0.425


def test_parse_musicxml_outputs_both_hands_and_chord_events(tmp_path: Path) -> None:
    score = tmp_path / "both-hands.musicxml"
    _write_score(
        score,
        """
        <measure number="1">
          <attributes><divisions>1</divisions></attributes>
          <note>
            <pitch><step>G</step><octave>4</octave></pitch>
            <duration>1</duration>
            <voice>1</voice>
            <staff>1</staff>
          </note>
          <backup><duration>1</duration></backup>
          <note>
            <pitch><step>C</step><octave>3</octave></pitch>
            <duration>1</duration>
            <voice>1</voice>
            <staff>2</staff>
          </note>
          <note>
            <chord/>
            <pitch><step>G</step><octave>3</octave></pitch>
            <duration>1</duration>
            <voice>1</voice>
            <staff>2</staff>
          </note>
        </measure>
        """,
    )

    result = parse_musicxml(score)
    assert [note.pitch for note in result.notes] == ["G4"]

    right_events = [event for event in result.playbackEvents if event.hand == "right"]
    left_events = [event for event in result.playbackEvents if event.hand == "left"]
    assert len(right_events) == 1
    assert len(left_events) == 1
    assert left_events[0].pitches == ["C3", "G3"]
    assert left_events[0].midis == [48, 55]
    assert any("Left-hand accompaniment voice selected" in warning for warning in result.meta.warnings)
