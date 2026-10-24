from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import xml.etree.ElementTree as ET
import zipfile

from src.models import PlaybackEvent, RecognizeResponse, RecognizedNote, ResponseMeta

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


@dataclass(slots=True)
class TimelineNote:
    start_beat: float
    duration_beat: float
    source_measure: int
    part: str
    staff: str
    voice: str
    is_rest: bool
    is_chord: bool
    pitch: str | None = None
    midi: int | None = None
    tie_start: bool = False
    tie_stop: bool = False
    slur_starts: int = 0
    slur_stops: int = 0
    staccato: bool = False


@dataclass(slots=True)
class VoiceStats:
    count: int = 0
    pitch_sum: int = 0

    @property
    def avg_pitch(self) -> float:
        return self.pitch_sum / self.count if self.count else 0.0


@dataclass(slots=True)
class RenderNote:
    pitch: str
    midi: int
    start_beat: float
    duration_beat: float
    source_measure: int
    part: str
    staff: str
    voice: str
    tie_start: bool
    tie_stop: bool
    is_tie: bool
    in_slur: bool
    staccato: bool


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


def _as_number(text: str) -> float | None:
    if not text:
        return None
    normalized = text.replace(".", "", 1).replace("-", "", 1)
    if not normalized.isdigit():
        return None
    return float(text)


def _parse_note_node(
    note_node: ET.Element,
    *,
    cursor_beat: float,
    divisions: int,
    source_measure: int,
    part: str,
    chord_anchor: dict[tuple[str, str], float],
) -> tuple[TimelineNote | None, float]:
    if _find_first(note_node, "grace") is not None:
        return None, cursor_beat

    duration_node = _find_first(note_node, "duration")
    duration_raw = _text(duration_node, "0")
    duration_value = _as_number(duration_raw) or 0.0
    duration_beat = duration_value / divisions if divisions else 0.0
    if duration_beat <= 0:
        return None, cursor_beat

    staff = _text(_find_first(note_node, "staff"), "1") or "1"
    voice = _text(_find_first(note_node, "voice"), "1") or "1"
    key = (staff, voice)
    is_chord = _find_first(note_node, "chord") is not None
    is_rest = _find_first(note_node, "rest") is not None

    if is_chord:
        start_beat = chord_anchor.get(key, cursor_beat)
        next_cursor = cursor_beat
    else:
        start_beat = cursor_beat
        chord_anchor[key] = start_beat
        next_cursor = cursor_beat + duration_beat

    tie_types = {
        tie.attrib.get("type", "")
        for tie in note_node
        if _strip_ns(tie.tag) == "tie"
    }
    notations = _find_first(note_node, "notations")
    slur_starts = 0
    slur_stops = 0
    staccato = False
    if notations is not None:
        for child in notations:
            tag = _strip_ns(child.tag)
            if tag == "slur":
                slur_type = child.attrib.get("type", "")
                if slur_type == "start":
                    slur_starts += 1
                elif slur_type == "stop":
                    slur_stops += 1
            elif tag == "articulations":
                for arti in child:
                    if _strip_ns(arti.tag) == "staccato":
                        staccato = True
                        break

    pitch = None
    midi = None
    if not is_rest:
        pitch_node = _find_first(note_node, "pitch")
        if pitch_node is None:
            return None, next_cursor

        step = _text(_find_first(pitch_node, "step"), "C")
        alter = int(_text(_find_first(pitch_node, "alter"), "0") or 0)
        octave = int(_text(_find_first(pitch_node, "octave"), "4") or 4)
        midi = _pitch_to_midi(step, alter, octave)

        accidental = ""
        if alter == 1:
            accidental = "#"
        elif alter == -1:
            accidental = "b"
        pitch = f"{step}{accidental}{octave}"

    return (
        TimelineNote(
            start_beat=start_beat,
            duration_beat=duration_beat,
            source_measure=source_measure,
            part=part,
            staff=staff,
            voice=voice,
            is_rest=is_rest,
            is_chord=is_chord,
            pitch=pitch,
            midi=midi,
            tie_start="start" in tie_types,
            tie_stop="stop" in tie_types,
            slur_starts=slur_starts,
            slur_stops=slur_stops,
            staccato=staccato,
        ),
        next_cursor,
    )


def _choose_lead_voice(
    stats: dict[tuple[str, str, str], VoiceStats],
) -> tuple[str, str, str] | None:
    if not stats:
        return None
    ranked = sorted(
        stats.items(),
        key=lambda item: (-item[1].count, -item[1].avg_pitch, *item[0]),
    )
    return ranked[0][0]


def _merge_ties(notes: list[RenderNote]) -> list[RenderNote]:
    merged: list[RenderNote] = []
    active: dict[tuple[str, str, str, int], RenderNote] = {}

    for note in notes:
        key = (note.part, note.staff, note.voice, note.midi)
        if note.tie_stop and key in active:
            base = active[key]
            base.duration_beat = round(base.duration_beat + note.duration_beat, 4)
            base.in_slur = base.in_slur or note.in_slur
            base.staccato = base.staccato or note.staccato
            if note.tie_start:
                active[key] = base
            else:
                merged.append(base)
                del active[key]
            continue

        if note.tie_start:
            active[key] = RenderNote(
                pitch=note.pitch,
                midi=note.midi,
                start_beat=note.start_beat,
                duration_beat=note.duration_beat,
                source_measure=note.source_measure,
                part=note.part,
                staff=note.staff,
                voice=note.voice,
                tie_start=False,
                tie_stop=False,
                is_tie=True,
                in_slur=note.in_slur,
                staccato=note.staccato,
            )
            continue

        merged.append(note)

    merged.extend(active.values())
    merged.sort(key=lambda note: (note.start_beat, note.source_measure, note.midi))
    return merged


def _to_recognized_notes(notes: list[RenderNote]) -> list[RecognizedNote]:
    recognized: list[RecognizedNote] = []
    epsilon = 1e-4
    for index, note in enumerate(notes):
        next_note = next(
            (candidate for candidate in notes[index + 1 :] if candidate.start_beat > note.start_beat + epsilon),
            None,
        )
        phrase_break_after = next_note is None or (
            next_note.start_beat - (note.start_beat + note.duration_beat)
        ) > epsilon

        if note.is_tie:
            articulation = "tie"
            gate = note.duration_beat
        elif note.staccato:
            articulation = "staccato"
            gate = note.duration_beat * 0.50
        elif note.in_slur:
            articulation = "slur"
            gate = note.duration_beat * 0.98
        else:
            articulation = "normal"
            gate = note.duration_beat * 0.92

        if phrase_break_after and articulation != "tie":
            gate *= 0.85

        recognized.append(
            RecognizedNote(
                pitch=note.pitch,
                midi=note.midi,
                startBeat=round(note.start_beat, 4),
                durationBeat=round(note.duration_beat, 4),
                gateBeat=round(max(gate, 0.01), 4),
                phraseBreakAfter=phrase_break_after,
                articulation=articulation,
                sourceMeasure=note.source_measure,
            )
        )

    return recognized


def _build_render_notes(
    timeline: list[TimelineNote],
    *,
    include_chords: bool,
    chord_warning_sent: bool,
    warnings: list[str],
) -> tuple[list[RenderNote], bool]:
    slur_depth = 0
    render_notes: list[RenderNote] = []

    for event in timeline:
        if event.is_rest:
            slur_depth = max(0, slur_depth + event.slur_starts - event.slur_stops)
            continue

        if event.pitch is None or event.midi is None:
            continue

        if event.is_chord and not include_chords:
            if not chord_warning_sent:
                warnings.append("Detected chord notes; only lead note is kept in melody notes.")
                chord_warning_sent = True
            continue

        in_slur = slur_depth > 0 or event.slur_starts > 0 or event.slur_stops > 0
        slur_depth = max(0, slur_depth + event.slur_starts - event.slur_stops)

        render_notes.append(
            RenderNote(
                pitch=event.pitch,
                midi=event.midi,
                start_beat=event.start_beat,
                duration_beat=event.duration_beat,
                source_measure=event.source_measure,
                part=event.part,
                staff=event.staff,
                voice=event.voice,
                tie_start=event.tie_start,
                tie_stop=event.tie_stop,
                is_tie=event.tie_start or event.tie_stop,
                in_slur=in_slur,
                staccato=event.staccato,
            )
        )

    return render_notes, chord_warning_sent


def _to_playback_events(
    notes: list[RecognizedNote],
    *,
    hand: Literal["right", "left"],
    staff: str,
    voice: str,
) -> list[PlaybackEvent]:
    grouped: dict[tuple[float, int, float, float], list[RecognizedNote]] = {}
    for note in notes:
        grouped.setdefault(
            (note.startBeat, note.sourceMeasure, note.durationBeat, note.gateBeat), []
        ).append(note)

    events: list[PlaybackEvent] = []
    for (start_beat, source_measure, _, _), chord_notes in sorted(grouped.items()):
        ordered = sorted(chord_notes, key=lambda item: item.midi)
        events.append(
            PlaybackEvent(
                startBeat=round(start_beat, 4),
                durationBeat=round(max(item.durationBeat for item in ordered), 4),
                gateBeat=round(max(item.gateBeat for item in ordered), 4),
                pitches=[item.pitch for item in ordered],
                midis=[item.midi for item in ordered],
                hand=hand,
                staff=staff,
                voice=voice,
                sourceMeasure=source_measure,
            )
        )
    return events


def parse_musicxml(path: Path, *, input_type: str = "png") -> RecognizeResponse:
    root = _read_mxl_root(path) if path.suffix.lower() == ".mxl" else ET.parse(path).getroot()

    parts = [node for node in root if _strip_ns(node.tag) == "part"]
    if not parts:
        raise ValueError("No part found in MusicXML")

    warnings: list[str] = []
    rhythm_issues: list[str] = []
    tempo = None
    time_signature: str | None = None
    timeline: list[TimelineNote] = []
    voice_stats: dict[tuple[str, str, str], VoiceStats] = {}
    part_measures: list[
        tuple[str, list[tuple[list[TimelineNote], float, int, bool, float | None]]]
    ] = []
    staff_clefs: dict[tuple[str, str], str] = {}

    for part_idx, part in enumerate(parts, start=1):
        part_id = part.attrib.get("id", f"P{part_idx}")
        divisions = 1
        active_time_beats: float | None = None
        measures = []
        for measure_idx, measure in enumerate(_find_children(part, "measure"), start=1):
            source_measure = measure_idx
            measure_cursor = 0.0
            measure_max = 0.0
            measure_notes: list[TimelineNote] = []
            chord_anchor: dict[tuple[str, str], float] = {}

            for child in measure:
                tag = _strip_ns(child.tag)
                if tag == "attributes":
                    divisions_node = next((x for x in child if _strip_ns(x.tag) == "divisions"), None)
                    if divisions_node is not None and _text(divisions_node, "1").isdigit():
                        divisions = max(1, int(_text(divisions_node, "1")))
                    time_node = next((x for x in child if _strip_ns(x.tag) == "time"), None)
                    if time_node is not None:
                        beats_text = _text(_find_first(time_node, "beats"))
                        beat_type_text = _text(_find_first(time_node, "beat-type"))
                        beats = _as_number(beats_text)
                        beat_type = _as_number(beat_type_text)
                        if beats is not None and beat_type:
                            active_time_beats = beats * 4 / beat_type
                            time_signature = time_signature or f"{beats_text}/{beat_type_text}"
                    for clef in _find_children(child, "clef"):
                        staff = clef.attrib.get("number", "1")
                        sign = _text(_find_first(clef, "sign"))
                        if sign:
                            staff_clefs[(part_id, staff)] = sign
                    continue
                if tag == "direction" and tempo is None:
                    metronome = _find_first(child, "metronome")
                    raw = _as_number(_text(_find_first(metronome, "per-minute"))) if metronome is not None else None
                    sound = _find_first(child, "sound")
                    raw = raw or (_as_number(sound.attrib.get("tempo", "")) if sound is not None else None)
                    if raw is not None:
                        tempo = int(raw)
                    continue
                if tag == "backup":
                    raw = _as_number(_text(_find_first(child, "duration"), "0")) or 0.0
                    measure_cursor -= raw / divisions
                    continue
                if tag == "forward":
                    raw = _as_number(_text(_find_first(child, "duration"), "0")) or 0.0
                    measure_cursor += raw / divisions
                    measure_max = max(measure_max, measure_cursor)
                    continue
                if tag != "note":
                    continue
                parsed, measure_cursor = _parse_note_node(
                    child, cursor_beat=measure_cursor, divisions=divisions,
                    source_measure=source_measure, part=part_id, chord_anchor=chord_anchor,
                )
                if parsed is not None:
                    measure_notes.append(parsed)
                    measure_max = max(measure_max, parsed.start_beat + parsed.duration_beat)
                measure_max = max(measure_max, measure_cursor)
            measures.append((measure_notes, measure_max, source_measure, measure.attrib.get("implicit") == "yes", active_time_beats))
        part_measures.append((part_id, measures))

    measure_count = max(len(measures) for _, measures in part_measures)
    cursor_beat = 0.0
    for measure_idx in range(measure_count):
        present = [
            measures[measure_idx]
            for _, measures in part_measures
            if measure_idx < len(measures)
        ]
        measure_length = max((item[1] for item in present), default=0.0)
        for part_id, measures in part_measures:
            if measure_idx >= len(measures):
                rhythm_issues.append(f"Measure {measure_idx + 1} missing from part {part_id}.")
                continue
            measure_notes, actual, source_measure, implicit, expected = measures[measure_idx]
            for event in measure_notes:
                event.start_beat += cursor_beat
                timeline.append(event)
                if not event.is_rest and event.midi is not None:
                    key = (event.part, event.staff, event.voice)
                    stat = voice_stats.setdefault(key, VoiceStats())
                    stat.count += 1
                    stat.pitch_sum += event.midi
            if expected is not None and not implicit:
                if actual > expected + 1e-4:
                    rhythm_issues.append(
                        f"Measure {source_measure} in part {part_id} exceeds its time "
                        f"signature ({actual:g} beats, expected {expected:g})."
                    )
                elif actual < expected - 1e-4 and not (measure_idx == 0 and actual > 0):
                    rhythm_issues.append(
                        f"Measure {source_measure} in part {part_id} is short "
                        f"({actual:g} beats, expected {expected:g})."
                    )
        cursor_beat += measure_length

    if time_signature is None:
        rhythm_issues.append("Time signature not found; measures aligned by their longest actual duration.")

    roles: dict[tuple[str, str, str], Literal["right", "left"]] = {}
    for key in voice_stats:
        part_id, staff, _ = key
        clef = staff_clefs.get((part_id, staff))
        if clef == "G" or (len(parts) == 1 and clef is None and staff == "1"):
            roles[key] = "right"
        elif clef == "F" or (len(parts) == 1 and clef is None and staff == "2"):
            roles[key] = "left"
        else:
            rhythm_issues.append(f"Unsupported or missing clef for part={part_id} staff={staff}; excluded from playback.")

    right_stats = {key: stat for key, stat in voice_stats.items() if roles.get(key) == "right"}
    right_voice = _choose_lead_voice(right_stats)
    if right_voice is not None:
        warnings.append(f"Right-hand lead voice selected: part={right_voice[0]} staff={right_voice[1]} voice={right_voice[2]}.")
    for hand in ("right", "left"):
        hand_identities = [key for key, role in roles.items() if role == hand]
        if len(hand_identities) > 1:
            warnings.append(f"Detected multi-voice {hand} hand; retained all voices for playback.")
    if not any(role == "left" for role in roles.values()):
        warnings.append("Bass-clef staff not detected; playback will use right hand only.")

    timeline.sort(key=lambda event: (event.start_beat, event.source_measure, event.part, event.staff, event.voice, event.midi or -1))
    right_timeline = [event for event in timeline if (event.part, event.staff, event.voice) == right_voice]

    chord_warning_sent = False
    right_melody_render, chord_warning_sent = _build_render_notes(
        right_timeline,
        include_chords=False,
        chord_warning_sent=chord_warning_sent,
        warnings=warnings,
    )
    notes = _to_recognized_notes(_merge_ties(right_melody_render))
    playback_events: list[PlaybackEvent] = []
    for identity, hand in roles.items():
        part_id, staff, voice = identity
        identity_timeline = [event for event in timeline if (event.part, event.staff, event.voice) == identity]
        playback_render, chord_warning_sent = _build_render_notes(
            identity_timeline, include_chords=True,
            chord_warning_sent=chord_warning_sent, warnings=warnings,
        )
        playback_events.extend(
            _to_playback_events(
                _to_recognized_notes(_merge_ties(playback_render)), hand=hand,
                staff=staff if len(parts) == 1 else f"{part_id}:{staff}", voice=voice,
            )
        )

    playback_events.sort(
        key=lambda event: (
            event.startBeat,
            0 if event.hand == "right" else 1,
            event.sourceMeasure,
            event.midis[0] if event.midis else -1,
        )
    )

    if tempo is None:
        tempo = 120
        warnings.append("Tempo not found in score; fallback to 120 BPM.")

    return RecognizeResponse(
        tempo=tempo,
        timeSignature=time_signature or "4/4",
        notes=notes,
        playbackEvents=playback_events,
        durationBeats=round(cursor_beat, 4),
        measureCount=measure_count,
        meta=ResponseMeta(engine="audiveris", inputType=input_type, warnings=[*warnings, *rhythm_issues], rhythmIssues=rhythm_issues),
    )
