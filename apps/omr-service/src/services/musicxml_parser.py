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


def _choose_lead_voice(stats: dict[tuple[str, str], VoiceStats]) -> tuple[str, str] | None:
    if not stats:
        return None
    ranked = sorted(
        stats.items(),
        key=lambda item: (-item[1].count, -item[1].avg_pitch, item[0][0], item[0][1]),
    )
    return ranked[0][0]


def _choose_voice_in_staff(
    stats: dict[tuple[str, str], VoiceStats], staff: str
) -> tuple[str, str] | None:
    scoped = {key: value for key, value in stats.items() if key[0] == staff}
    return _choose_lead_voice(scoped)


def _merge_ties(notes: list[RenderNote]) -> list[RenderNote]:
    merged: list[RenderNote] = []
    active: dict[int, RenderNote] = {}

    for note in notes:
        key = note.midi
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
        next_note = notes[index + 1] if index + 1 < len(notes) else None
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
    grouped: dict[tuple[float, int], list[RecognizedNote]] = {}
    for note in notes:
        grouped.setdefault((note.startBeat, note.sourceMeasure), []).append(note)

    events: list[PlaybackEvent] = []
    for (start_beat, source_measure), chord_notes in sorted(grouped.items()):
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

    part = next((n for n in root if _strip_ns(n.tag) == "part"), None)
    if part is None:
        raise ValueError("No part found in MusicXML")

    warnings: list[str] = []
    tempo = None
    time_signature = "4/4"
    timeline: list[TimelineNote] = []
    voice_stats: dict[tuple[str, str], VoiceStats] = {}
    cursor_beat = 0.0
    divisions = 1
    chord_anchor: dict[tuple[str, str], float] = {}

    for measure_idx, measure in enumerate(_find_children(part, "measure"), start=1):
        source_measure = int(measure.attrib.get("number", str(measure_idx)))
        measure_cursor = cursor_beat
        measure_max = cursor_beat

        for child in measure:
            tag = _strip_ns(child.tag)
            if tag == "attributes":
                divisions_node = next(
                    (x for x in child if _strip_ns(x.tag) == "divisions"), None
                )
                if divisions_node is not None and _text(divisions_node, "1").isdigit():
                    divisions = max(1, int(_text(divisions_node, "1")))

                time_node = next((x for x in child if _strip_ns(x.tag) == "time"), None)
                if time_node is not None:
                    beats = _text(_find_first(time_node, "beats"), "4")
                    beat_type = _text(_find_first(time_node, "beat-type"), "4")
                    time_signature = f"{beats}/{beat_type}"
                continue

            if tag == "direction" and tempo is None:
                metronome = _find_first(child, "metronome")
                if metronome is not None:
                    per_minute = _as_number(_text(_find_first(metronome, "per-minute"), ""))
                    if per_minute is not None:
                        tempo = int(per_minute)
                        continue
                sound = _find_first(child, "sound")
                if sound is not None and "tempo" in sound.attrib:
                    raw = _as_number(sound.attrib["tempo"])
                    if raw is not None:
                        tempo = int(raw)
                continue

            if tag == "backup":
                backup_duration = _as_number(_text(_find_first(child, "duration"), "0")) or 0.0
                measure_cursor -= backup_duration / divisions if divisions else 0.0
                continue

            if tag == "forward":
                forward_duration = _as_number(_text(_find_first(child, "duration"), "0")) or 0.0
                measure_cursor += forward_duration / divisions if divisions else 0.0
                measure_max = max(measure_max, measure_cursor)
                continue

            if tag != "note":
                continue

            parsed, next_cursor = _parse_note_node(
                child,
                cursor_beat=measure_cursor,
                divisions=divisions,
                source_measure=source_measure,
                chord_anchor=chord_anchor,
            )
            if parsed is None:
                measure_cursor = next_cursor
                measure_max = max(measure_max, measure_cursor)
                continue

            timeline.append(parsed)
            measure_cursor = next_cursor
            measure_max = max(measure_max, parsed.start_beat + parsed.duration_beat, measure_cursor)

            if not parsed.is_rest and parsed.midi is not None:
                key = (parsed.staff, parsed.voice)
                current = voice_stats.setdefault(key, VoiceStats())
                current.count += 1
                current.pitch_sum += parsed.midi

        cursor_beat = max(cursor_beat, measure_max)

    right_voice = _choose_voice_in_staff(voice_stats, "1")
    if right_voice is None and voice_stats:
        right_voice = _choose_lead_voice(voice_stats)
        if right_voice is not None:
            warnings.append(
                "Right-hand staff=1 not found; fallback to detected lead voice "
                f"staff={right_voice[0]} voice={right_voice[1]}."
            )

    left_voice = _choose_voice_in_staff(voice_stats, "2")
    right_staff_voices = {voice for staff, voice in voice_stats if staff == "1"}
    left_staff_voices = {voice for staff, voice in voice_stats if staff == "2"}

    if right_voice is not None:
        warnings.append(
            f"Right-hand lead voice selected: staff={right_voice[0]} voice={right_voice[1]}."
        )
        if len(right_staff_voices) > 1:
            warnings.append(
                f"Detected multi-voice right hand; kept voice {right_voice[1]} on staff=1."
            )
    if left_voice is not None:
        warnings.append(
            f"Left-hand accompaniment voice selected: staff={left_voice[0]} voice={left_voice[1]}."
        )
        if len(left_staff_voices) > 1:
            warnings.append(
                f"Detected multi-voice left hand; kept voice {left_voice[1]} on staff=2."
            )
    else:
        warnings.append("Left-hand staff=2 not detected; playback will use right hand only.")

    right_timeline = (
        [event for event in timeline if (event.staff, event.voice) == right_voice]
        if right_voice is not None
        else []
    )
    left_timeline = (
        [event for event in timeline if (event.staff, event.voice) == left_voice]
        if left_voice is not None
        else []
    )

    right_timeline.sort(key=lambda event: (event.start_beat, event.source_measure, event.midi or -1))
    left_timeline.sort(key=lambda event: (event.start_beat, event.source_measure, event.midi or -1))

    chord_warning_sent = False
    right_melody_render, chord_warning_sent = _build_render_notes(
        right_timeline,
        include_chords=False,
        chord_warning_sent=chord_warning_sent,
        warnings=warnings,
    )
    right_playback_render, chord_warning_sent = _build_render_notes(
        right_timeline,
        include_chords=True,
        chord_warning_sent=chord_warning_sent,
        warnings=warnings,
    )
    left_playback_render, _ = _build_render_notes(
        left_timeline,
        include_chords=True,
        chord_warning_sent=chord_warning_sent,
        warnings=warnings,
    )

    notes = _to_recognized_notes(_merge_ties(right_melody_render))
    right_playback_notes = _to_recognized_notes(_merge_ties(right_playback_render))
    left_playback_notes = _to_recognized_notes(_merge_ties(left_playback_render))

    playback_events: list[PlaybackEvent] = []
    if right_voice is not None:
        playback_events.extend(
            _to_playback_events(
                right_playback_notes,
                hand="right",
                staff=right_voice[0],
                voice=right_voice[1],
            )
        )
    if left_voice is not None:
        playback_events.extend(
            _to_playback_events(
                left_playback_notes,
                hand="left",
                staff=left_voice[0],
                voice=left_voice[1],
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
        timeSignature=time_signature,
        notes=notes,
        playbackEvents=playback_events,
        meta=ResponseMeta(engine="audiveris", inputType=input_type, warnings=warnings),
    )
