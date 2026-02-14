from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from src.models import RecognizeResponse, RecognizedNote, ResponseMeta

SEMITONES = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_first(node: ET.Element, name: str) -> ET.Element | None:
    for child in node.iter():
        if _strip_ns(child.tag) == name:
            return child
    return None


def _find_children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in node if _strip_ns(child.tag) == name]


def _text(node: ET.Element | None, default: str = "") -> str:
    if node is None or node.text is None:
        return default
    return node.text.strip()


def _pitch_to_midi(step: str, alter: int, octave: int) -> int:
    return (octave + 1) * 12 + SEMITONES[step] + alter


def _read_mxl_root(path: Path) -> ET.Element:
    with zipfile.ZipFile(path, "r") as archive:
        container_xml = archive.read("META-INF/container.xml")
        container_root = ET.fromstring(container_xml)

        rootfile_path = None
        for node in container_root.iter():
            if _strip_ns(node.tag) == "rootfile":
                rootfile_path = node.attrib.get("full-path")
                if rootfile_path:
                    break

        if not rootfile_path:
            raise ValueError("Invalid MXL: missing rootfile path")

        score_data = archive.read(rootfile_path)
        return ET.fromstring(score_data)


def parse_musicxml(path: Path, *, input_type: str = "png") -> RecognizeResponse:
    root = _read_mxl_root(path) if path.suffix.lower() == ".mxl" else ET.parse(path).getroot()

    part = next((n for n in root if _strip_ns(n.tag) == "part"), None)
    if part is None:
        raise ValueError("No part found in MusicXML")

    warnings: list[str] = []
    tempo = None
    time_signature = "4/4"
    notes: list[RecognizedNote] = []

    current_beat = 0.0
    divisions = 1
    chord_warning_sent = False
    staff_values = {
        _text(_find_first(note_node, "staff"))
        for measure in _find_children(part, "measure")
        for note_node in _find_children(measure, "note")
        if _text(_find_first(note_node, "staff"))
    }
    lead_staff = None
    if staff_values:
        if "1" in staff_values:
            lead_staff = "1"
        else:
            lead_staff = sorted(staff_values)[0]
        if len(staff_values) > 1:
            warnings.append(
                f"Detected multi-staff score ({', '.join(sorted(staff_values))}); only right-hand staff {lead_staff} is kept in MVP."
            )

    for measure_idx, measure in enumerate(_find_children(part, "measure"), start=1):
        attrs = next((x for x in measure if _strip_ns(x.tag) == "attributes"), None)
        if attrs is not None:
            divisions_node = next(
                (x for x in attrs if _strip_ns(x.tag) == "divisions"), None
            )
            if divisions_node is not None and _text(divisions_node, "1").isdigit():
                divisions = max(1, int(_text(divisions_node, "1")))

            time_node = next((x for x in attrs if _strip_ns(x.tag) == "time"), None)
            if time_node is not None:
                beats = _text(_find_first(time_node, "beats"), "4")
                beat_type = _text(_find_first(time_node, "beat-type"), "4")
                time_signature = f"{beats}/{beat_type}"

        if tempo is None:
            for direction in _find_children(measure, "direction"):
                metronome = _find_first(direction, "metronome")
                if metronome is not None:
                    per_minute = _text(_find_first(metronome, "per-minute"))
                    if per_minute.replace(".", "", 1).isdigit():
                        tempo = int(float(per_minute))
                        break
                sound = _find_first(direction, "sound")
                if sound is not None and "tempo" in sound.attrib:
                    raw = sound.attrib["tempo"]
                    if raw.replace(".", "", 1).isdigit():
                        tempo = int(float(raw))
                        break

        source_measure = int(measure.attrib.get("number", str(measure_idx)))
        for note_node in _find_children(measure, "note"):
            staff = _text(_find_first(note_node, "staff"))
            if lead_staff is not None and staff and staff != lead_staff:
                continue

            if _find_first(note_node, "grace") is not None:
                continue

            is_chord = _find_first(note_node, "chord") is not None
            duration_node = _find_first(note_node, "duration")
            duration_value = float(_text(duration_node, "0") or 0)
            duration_beat = duration_value / divisions if divisions else 0
            if duration_beat <= 0:
                continue

            if _find_first(note_node, "rest") is not None:
                if not is_chord:
                    current_beat += duration_beat
                continue

            if is_chord:
                if not chord_warning_sent:
                    warnings.append("Detected chord notes; only lead note is kept in MVP.")
                    chord_warning_sent = True
                continue

            pitch_node = _find_first(note_node, "pitch")
            if pitch_node is None:
                continue

            step = _text(_find_first(pitch_node, "step"), "C")
            alter = int(_text(_find_first(pitch_node, "alter"), "0") or 0)
            octave = int(_text(_find_first(pitch_node, "octave"), "4") or 4)
            midi = _pitch_to_midi(step, alter, octave)

            accidental = ""
            if alter == 1:
                accidental = "#"
            elif alter == -1:
                accidental = "b"

            notes.append(
                RecognizedNote(
                    pitch=f"{step}{accidental}{octave}",
                    midi=midi,
                    startBeat=round(current_beat, 4),
                    durationBeat=round(duration_beat, 4),
                    sourceMeasure=source_measure,
                )
            )
            current_beat += duration_beat

    if tempo is None:
        tempo = 120
        warnings.append("Tempo not found in score; fallback to 120 BPM.")

    return RecognizeResponse(
        tempo=tempo,
        timeSignature=time_signature,
        notes=notes,
        meta=ResponseMeta(engine="audiveris", inputType=input_type, warnings=warnings),
    )
