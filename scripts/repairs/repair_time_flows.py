"""Rebuild the reviewed four-page score without modifying the original OMR files.

Run from the repository root with:
  PYTHONPATH=apps/omr-service apps/omr-service/.venv/bin/python scripts/repairs/repair_time_flows.py
Add --apply to back up and replace only the matching catalog record and its index summary.
The rhythm transcription below was checked against the four archived input.jpg pages.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from src.models import RecognizeResponse
from src.services.catalog_service import CatalogService
from src.services.musicxml_parser import _read_mxl_root, parse_musicxml
from src.services.pipeline import merge_recognize_results

ROOT = Path(__file__).resolve().parents[2]
ENTRY_ID = "3b21855739312939cf5239134337a0fbf2ba7b6f8f9e2af383c3c7e83257f5a0"
RUNS = ["20260912T164201-106ec03d", "20260912T164212-e5c3c948", "20260912T164222-9dadb17f", "20260912T164232-2c471d0a"]
SOURCE_HASHES = [
    "a3eb43bcbc71450aecca9081cfd6ab7ebee4418eb31b5b5ceed0abd57f0157ad",
    "391d93884230c243fadc110c29ca6b19f479527139f73559c683fb17656516c6",
    "0937795cc2f68cd4e84e05a1b508a8999714f8b7d9fd70439b552fcc772cdd34",
    "f058bee98be07d2793d997b855619d641576ab1e8df07dae292c03b1386610b3",
]
# Quarter-note beats, one list per measure, with chord tones sharing one onset.
RIGHT_RHYTHMS = [
    [[1.5,.5,1],[3],[1.5,.5,1],[1.5,.5,1],[1,1,.5,.5],[2,.5,.5],
     [1.5,.5,1],[1,1,1],[3],[3],[1.5,.5,1],[2,1],[1,1,.75,.25],
     [3],[2,.5,.5],[1,1,1],[3],[3]],
    [[3],[2,.5,.5],[1.5,.5,1],[1.5,.5,1],[1,1,.5,.5],[2,.5,.5],
     [1.5,.5,1],[1,1,1],[3],[3],[1.5,.5,1],[2,1],[1,1,.75,.25],
     [3],[2,1],[1,1,1],[1,1,1],[2,.75,.25]],
    [[2,.75,.25],[2,1],[1.5,.5,1],[2,.5,.5],[2,.5,.5],[.25,.75,1,.5,.5],
     [1,1,1],[2,.75,.25],[2,.75,.25],[2,1],[1.5,.5,1],[3],[2,1],
     [1,.25,.25,.5,.5,.5],[1,1.5,.5],[.5,.5,1,1],[3],[3]],
    [[1.5,.5,1],[1.5,.5,1],[1,1,.5,.5],[2,.5,.5],[1.5,.5,1],[1,1,1],
     [2,1],[3],[1.5,.5,1],[2,1],[1,1,.75,.25],[3],[2,.5,.5],
     [1,1,1],[1,1,1],[3],[3],[3]],
]
LEFT_RHYTHMS = [
    [[1,2],[3],[1,1,1],[1,1,1],[1,1,1],[3],[1,1,1],[1,1,1],[1,1,1],
     [3],[1,1,1],[1,1,1],[1,1,1],[3],[1,1,1],[1,1,1],[2,1],[1,2]],
    [[3],[3],[1,1,1],[1,1,1],[1,1,1],[3],[1,1,1],[1,1,1],[1,1,1],
     [3],[1,1,1],[1,1,1],[1,1,1],[3],[1,1,1],[1,1,1],[2,1],[2,1]],
    [[3] for _ in range(18)],
    [[1,1,1],[1,1,1],[1,1,1],[3],[1,1,1],[1,1,1],[1,1,1],[3],
     [1,1,1],[1,1,1],[1,1,1],[3],[1,1,1],[1,1,1],[1,1,1],[3],[3],[3]],
]


def groups(measure):
    result = []
    for note in measure.findall("note"):
        if note.find("chord") is None:
            result.append([])
        result[-1].append(note)
    return result


def make_note(pitch=None):
    note = ET.Element("note")
    if pitch is None:
        ET.SubElement(note, "rest", measure="yes")
    else:
        node = ET.SubElement(note, "pitch")
        ET.SubElement(node, "step").text = pitch[0]
        ET.SubElement(node, "octave").text = pitch[1:]
    ET.SubElement(note, "duration").text = "12"
    ET.SubElement(note, "voice").text = "1"
    return note


def insert_pitch(measure, group_index, pitch):
    before = groups(measure)[group_index][0] if group_index < len(groups(measure)) else None
    note = make_note(pitch)
    if before is None:
        measure.append(note)
    else:
        measure.insert(list(measure).index(before), note)


def remove_group(measure, index):
    for note in groups(measure)[index]:
        measure.remove(note)


def add_tie(note, kind):
    if not any(t.get("type") == kind for t in note.findall("tie")):
        ET.SubElement(note, "tie", type=kind)
        notations = note.find("notations")
        if notations is None:
            notations = ET.SubElement(note, "notations")
        ET.SubElement(notations, "tied", type=kind)


def correct_page(root, page, changes):
    parts = root.findall("part")
    if [p.get("id") for p in parts] != ["P1", "P2"]:
        raise ValueError("Unexpected score layout; refuse to apply transcription")
    right = parts[0].findall("measure")
    left = parts[1].findall("measure")
    # Visible omissions and hallucinations, before applying the reviewed durations.
    if page == 0:
        insert_pitch(right[6], 1, "E5")
        group = groups(right[14])[1]
        if [n.findtext("pitch/step") + n.findtext("pitch/octave") for n in group] != ["E5", "D6"]:
            raise ValueError("Unexpected measure 15 notes")
        right[14].remove(group[0])
        group[1].remove(group[1].find("chord"))
    elif page == 1:
        remove_group(right[2], 3)  # Spurious F4 half note after the three melody notes.
        remove_group(left[5], 1)  # Spurious A2 half note after the dotted-half chord.
        insert_pitch(right[12], 3, "G6")
    elif page == 2:
        insert_pitch(right[2], 1, "E4")
        insert_pitch(right[14], 2, "D5")
        add_tie(groups(right[5])[1][0], "start")
        add_tie(groups(right[5])[2][0], "stop")
        add_tie(groups(right[16])[0][0], "start")
        add_tie(groups(right[17])[0][0], "stop")
    elif page == 3:
        insert_pitch(right[10], 3, "G6")
        remove_group(right[11], 1)  # Spurious F4/C5 chord.
        remove_group(left[11], 1)   # Spurious A2/E3 chord.
        for part in parts:
            ET.SubElement(part, "measure", number="18")  # Final bar of silence missed by OMR.
    for hand, part in enumerate(parts):
        measures = part.findall("measure")
        rhythms = [RIGHT_RHYTHMS, LEFT_RHYTHMS][hand][page]
        if len(measures) != len(rhythms):
            raise ValueError("Unexpected measure count")
        for index, (measure, durations) in enumerate(zip(measures, rhythms)):
            if abs(sum(durations) - 3) > 1e-8:
                raise ValueError("Reviewed measure must contain three quarter-note beats")
            measure.set("number", str(index + 1))
            attributes = measure.find("attributes")
            if attributes is None:
                attributes = ET.Element("attributes")
                measure.insert(0, attributes)
            for node in list(attributes):
                if node.tag in {"divisions", "time"}:
                    attributes.remove(node)
            ET.SubElement(attributes, "divisions").text = "4"
            time = ET.SubElement(attributes, "time")
            ET.SubElement(time, "beats").text = "3"
            ET.SubElement(time, "beat-type").text = "4"
            if not groups(measure):
                measure.append(make_note())
            if len(groups(measure)) != len(durations):
                raise ValueError(f"Unexpected onset count: page {page+1}, hand {hand}, measure {index+1}")
            for group, beats in zip(groups(measure), durations):
                for note in group:
                    for node in list(note):
                        if node.tag in {"duration", "type", "dot", "beam"}:
                            note.remove(node)
                    ET.SubElement(note, "duration").text = str(round(beats * 4))
                    note_type, dotted = {3:("half",True), 2:("half",False), 1.5:("quarter",True), 1:("quarter",False), .75:("eighth",True), .5:("eighth",False), .25:("16th",False)}[beats]
                    ET.SubElement(note, "type").text = note_type
                    if dotted:
                        ET.SubElement(note, "dot")
            # Keep generated XML in MusicXML child order after adding durations/ties.
            attribute_order = ["divisions", "key", "time", "staves", "part-symbol", "instruments", "clef", "staff-details", "transpose", "directive", "measure-style"]
            attributes[:] = sorted(attributes, key=lambda n: attribute_order.index(n.tag) if n.tag in attribute_order else 99)
            note_order = ["grace", "cue", "chord", "pitch", "unpitched", "rest", "duration", "tie", "instrument", "footnote", "level", "voice", "type", "dot", "accidental", "time-modification", "stem", "notehead", "notehead-text", "staff", "beam", "notations", "lyric", "play", "listen"]
            for note in measure.findall("note"):
                note[:] = sorted(note, key=lambda n: note_order.index(n.tag) if n.tag in note_order else 99)
            changes.append({"page":page+1,"hand":"right" if hand == 0 else "left", "measure":page*18+index+1,"beats":durations})
    return root


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--apply", action="store_true")
    apply = args.parse_args().apply
    record_path = ROOT / "storage/catalog/records" / f"{ENTRY_ID}.json"
    record_before = record_path.read_text()
    record = json.loads(record_before)
    output = ROOT / "storage/repairs" / (datetime.now().strftime("%Y%m%dT%H%M%S") + "-time-flows")
    output.mkdir(parents=True, exist_ok=False)
    pages, changes, sources = [], [], []
    for page, run in enumerate(RUNS):
        source = ROOT / "apps/omr-service/run-logs" / run / "up2-preprocessed-up2.mxl"
        if not source.exists():
            source = source.with_name("base-preprocessed-base.mxl")
        if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_HASHES[page]:
            raise ValueError("Source differs from the reviewed score; refusing transcription")
        original = _read_mxl_root(source)
        sources.append({"path":str(source.relative_to(ROOT)),"sha256":hashlib.sha256(source.read_bytes()).hexdigest()})
        corrected = correct_page(deepcopy(original), page, changes)
        target = output / f"page-{page+1}.musicxml"
        ET.indent(corrected)
        ET.ElementTree(corrected).write(target, encoding="utf-8", xml_declaration=True)
        parsed = parse_musicxml(target, input_type="jpg")
        assert parsed.measureCount == 18 and parsed.durationBeats == 54
        pages.append(parsed)
    result = merge_recognize_results(pages)
    assert result.durationBeats == 216 and result.measureCount == 72
    assert {e.hand for e in result.playbackEvents} == {"left", "right"}
    # Keep the user's tempo, title and instrument choices.
    result.tempo = record["result"]["tempo"]
    result.meta.warnings.append("本曲已按存档四页原谱人工校正节奏、休止与延音线；速度沿用原设置，尚未与原曲录音校准。")
    (output / "result.json").write_text(result.model_dump_json(indent=2))
    (output / "review.json").write_text(json.dumps({"entryId":ENTRY_ID,"sources":sources,"reviewedRhythms":changes},ensure_ascii=False,indent=2))
    if apply:
        # Preserve the complete previous index and this record before writing.
        index_path = ROOT / "storage/catalog/index.json"
        if record_path.read_text() != record_before:
            raise ValueError("Catalog record changed during repair; retry after editing finishes")
        shutil.copy2(record_path, output / "record-before.json")
        shutil.copy2(index_path, output / "index-before.json")
        index = json.loads(index_path.read_text())
        summary = dict(record["summary"])
        summary.update(timeSignature=result.timeSignature, noteCount=len(result.notes), updatedAt=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        for i, entry in enumerate(index["entries"]):
            if entry["id"] == ENTRY_ID:
                index["entries"][i] = summary
                break
        else:
            raise ValueError("Catalog entry disappeared; refusing to write")
        CatalogService._atomic_write_text(record_path, json.dumps({"summary":summary,"result":result.model_dump()},ensure_ascii=False,indent=2))
        CatalogService._atomic_write_text(index_path, json.dumps(index,ensure_ascii=False,indent=2))
        assert RecognizeResponse.model_validate(json.loads(record_path.read_text())["result"]) == result
    print(json.dumps({"output":str(output),"applied":apply,"notes":len(result.notes),"events":len(result.playbackEvents),"beats":result.durationBeats},ensure_ascii=False))


if __name__ == "__main__":
    main()
