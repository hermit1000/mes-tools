"""Extract Ballade MES and MEC text into paired info/lang JSON files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from modules.adv_common.mes_decoder import make_records
from modules.adv_common.mes_lexer import decode_mes as decode_lexical_mes
from modules.adv_common.ascii import resolve_ascii_and_gaiji
from modules.adv_common.tokens import is_sjis_lead, is_sjis_trail, make_token
from .speaker_groups import annotate_directory, annotate_speakers
from .special_text import merge_special_text
from .text_layout import annotate_layout
from .inline_names import merge_inline_names
from .graph_titles import graph_op_title
from .quoted_display import promote_display_quotes


def split_f0_control(tokens: list[dict], data: bytes) -> list[dict]:
    """F0 before compressed kana is a control, not a Shift-JIS lead byte."""
    result = []
    for token in tokens:
        raw = token["bytes"]
        if token["type"] == "text" and len(raw) == 2 and raw[0] == 0xF0 and 0x2D <= raw[1] <= 0x7F:
            offset = token["offset"]
            expanded = bytes((0x82, (raw[1] + 0x72) & 0xFF))
            result.append(make_token(offset, 1, data[offset:offset + 1], "control", "CONTROL_F0"))
            result.append(make_token(
                offset + 1, 1, data[offset + 1:offset + 2], "text",
                expanded.decode("cp932", errors="replace"),
                encoding="adv98-compressed-sjis", expandedBytes=list(expanded),
            ))
        else:
            result.append(token)
    return result


def decode_ballade_mes(data: bytes) -> list[dict]:
    """Treat 22 as an operand when a putative quote crosses an END command."""
    probe = bytearray(data)
    display_parameters: set[int] = set()
    single_byte_controls: set[int] = set()
    single_byte_arguments: set[int] = set()
    marker = b"\x1a\x00\x0a\x0d\x8f\xea"
    start = 0
    # F0 introduces the following display text here; 8E A9 is the SJIS
    # first glyph of "jibun", not the trail byte of an F0 8E gaiji.
    marker_f0_before_ji = b"\xa4\x0a\xf0\x8e\xa9"
    while (start := data.find(marker_f0_before_ji, start)) >= 0:
        offset = start + 2
        single_byte_controls.add(offset)
        probe[offset] = 0x0B
        start = offset + 1
    start = 0
    while (start := data.find(marker, start)) >= 0:
        offset = start + 3
        single_byte_controls.add(offset)
        probe[offset] = 0x0B
        start = offset + 1
    for start in range(len(data) - 4):
        if (data[start] in (0xA2, 0xA4)
                and data[start + 1] == 0x09
                and 0xE0 <= data[start + 2] <= 0xFC
                and data[start + 3:start + 5] != b"\x81\x97"):
            offset = start + 2
            single_byte_controls.add(offset)
            probe[offset] = 0x0B
        if (data[start] in (0xA2, 0xA4)
                and data[start + 1] == 0x0E
                and 0x6F <= data[start + 2] <= 0x80):
            offset = start + 1
            display_parameters.add(offset)
            probe[offset] = 0x08
            if data[start + 3] == 0x09 and 0xE0 <= data[start + 4] <= 0xFC:
                offset = start + 4
                single_byte_controls.add(offset)
                probe[offset] = 0x0B
    for marker in (b"\xa4\x09\x0c\x89\xc9\x38\x56",
                   b"\xa4\x09\x0c\x96\x6c\x8e\xa9",
                   b"\xa4\x09\x0c\x8a\xc4\x93\xc2",
                   b"\xa4\x09\x0c\x83\x54\x83\x93",
                   b"\xa4\x09\x0c\x8c\x78\x8e\x40",
                   b"\xa4\x09\x98\x88\xea\x91\xcc",
                   b"\xa2\x09\x99\x83\x4b",
                   b"\xa4\x09\x9a\x49\x78",
                   b"\xa4\x09\x9d\x83\x4d",
                   b"\xa4\x09\x9e\x83\x4a",
                   b"\xa4\x09\x84\x74\x37",
                   b"\xa4\x09\x86\x54\x32",
                   b"\xa2\x09\x88\x83\x47",
                   b"\xa4\x09\x89\x83\x47",
                   b"\xa4\x09\x8c\x8f\x45",
                   b"\x09\x9b\xba\x28\x0e",
                   b"\xa4\x09\x9c\xba\x28\x0e"):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + (1 if marker.startswith(b"\x09") else 2)
            single_byte_controls.add(offset)
            probe[offset] = 0x0B
            start = offset + 1
    for marker, advance in ((b"\xa2\x0e\x7a\x09\xf3\x93\x96", 4),
                            (b"\xa4\x0e\x7a\x09\xf4\x83\x8c", 4),
                            (b"\xa4\x0a\x85\x83\x4b", 2),
                            (b"\x0e\x85\xa4\x91\x53", 1),
                            (b"\xa2\x0a\x86\x83\x67", 2),
                            (b"\xa4\x0f\x1b\x0e\x88\x83\x56", 4),
                            (b"\x0e\xf9\xa4\xba\x28", 1),
                            (b"\xa2\x0f\x1c\x09\xf7\x92\x4e", 4),
                            (b"\xa2\x0f\x1b\x09\xf9\x83\x4d", 4),
                            (b"\xa4\x0a\xef\x8d\x6c", 2)):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + advance
            single_byte_controls.add(offset)
            probe[offset] = 0x0B
            start = offset + 1
    for marker, advance in ((b"\xa4\x0a\x7f\x3f\x78", 1),
                            (b"\xa4\x0a\x81\x83\x81", 1),
                            (b"\xa2\x0a\x83\x8a\x6d", 1),
                            (b"\xa4\x0a\x78\x83\x67", 1),
                            (b"\x0e\x88\xa4\xba\x28", 0)):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + advance
            display_parameters.add(offset)
            probe[offset] = 0x08
            start = offset + 2
    marker = b"\x0e\x6f\xa3\xff\xff"
    start = 0
    while (start := data.find(marker, start)) >= 0:
        display_parameters.add(start)
        probe[start] = 0x08
        start += len(marker)
    marker = b"\x28\x09\x23\x0e\x72\x97\xe1"
    start = 0
    while (start := data.find(marker, start)) >= 0:
        offset = start + 3
        display_parameters.add(offset)
        probe[offset] = 0x08
        start = offset + 2
    for marker in (b"\xa4\x0d\xf2\x0e\x70", b"\xa4\x0d\xf6\x0e\x70"):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + 3
            display_parameters.add(offset)
            probe[offset] = 0x08
            start = offset + 2
    marker = b"\x24\x24\x0e\x74\xba\x28\x0e"
    start = 0
    while (start := data.find(marker, start)) >= 0:
        offset = start + 2
        display_parameters.add(offset)
        probe[offset] = 0x08
        start = offset + 2
    for marker in (b"\xa4\x09\x08\x8e\x64\x8e\x96",
                   b"\xa4\x09\x08\x93\xcb\x91\x52",
                   b"\xa4\x09\x19\x83\x4b\x83\x43",
                   b"\xa4\x09\x08\x96\x6c\x57\x5b",
                   b"\xa4\x09\x08\x83\x4b\x83\x43"):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + 2
            single_byte_controls.add(offset)
            probe[offset] = 0x0B
            start = offset + 1
    marker = b"\x1a\x00\x0a\x93"
    start = 0
    while (start := data.find(marker, start)) >= 0:
        offset = start + 2
        display_parameters.add(offset)
        probe[offset] = 0x08
        if data[offset + 2:offset + 4] == b"\x0a\x0c":
            display_parameters.add(offset + 2)
            probe[offset + 2] = 0x08
        start = offset + 2
    marker = b"\x1a\x01\x0a\x8e"
    start = 0
    while (start := data.find(marker, start)) >= 0:
        offset = start + 2
        display_parameters.add(offset)
        probe[offset] = 0x08
        start = offset + 2
    for marker in (b"\xa4\x0e\x91", b"\xa2\x0e\x93\x90\x53", b"\x0e\x8e\xa4",
                   b"\x0e\x2c\x83\x81\x83\x8a",
                   b"\xa2\x0e\xfb\x83\x81\x83\x8a\x83\x8b"):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start if marker.startswith(b"\x0e") else start + 1
            display_parameters.add(offset)
            probe[offset] = 0x08
            start = offset + 2
    for marker in (b"\x10\x2a\x00\x89\xbd\x7e", b"\x10\x2a\x00\x90\xe6",
                   b"\x10\x2a\x00\x8e\xca\x90\x5e",
                   b"\x10\x2a\x00\x54\x57\x37",
                   b"\x10\x2a\x00\x32\x4f\x45",
                   b"\x10\x2a\x03\x6a\x4c\x89\xbd",
                   b"\x10\x2a\x04\x81\x97\x96\x6c",
                   b"\x10\x2a\x03\x83\x57\x83\x46",
                   b"\x10\x2a\x04\x96\x6c\x5b",
                   b"\x10\x2a\x03\x41\x52\x81\x41",
                   b"\x10\x2a\x03\x0a\x43\x54",
                   b"\x10\x2a\x03\x91\x81\x30\x54"):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + 1
            display_parameters.add(offset)
            probe[offset] = 0x08
            start = offset + 2
            if marker == b"\x10\x2a\x03\x0a\x43\x54":
                display_parameters.add(start)
                probe[start] = 0x08
    for marker in (b"\x09\x2a\x94\xc6\x8d\x73",
                   b"\x09\x2a\x89\xbd\x8c\xcc",
                   b"\x09\x2a\x6e\x32\x83\x4a",
                   b"\x09\x2a\x81\x40\x81\x40"):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            display_parameters.add(start)
            probe[start] = 0x08
            start += 2
    for suffix, next_byte in ((0x71, 0x8B), (0x72, 0x6A), (0x73, 0x8E),
                              (0x74, 0x49), (0x75, 0x8F), (0x76, 0x83),
                              (0x77, 0x97)):
        marker = b"\x10\x2a\x02\x08" + bytes((suffix, next_byte))
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + 1
            display_parameters.add(offset)
            probe[offset] = 0x08
            start = offset + 2
    # 0A 28 is a one-byte selector here; the following SJIS pair is display text.
    for start in range(len(data) - 4):
        if (data[start:start + 3] == b"\xa4\x0a\x28"
                and is_sjis_lead(data[start + 3])
                and is_sjis_trail(data[start + 4])):
            offset = start + 2
            single_byte_arguments.add(offset)
            probe[offset] = 0x0B
    # The E6 flag operand must not pair with the following 81 97 control.
    marker = b"\x0e\xe6\x81\x97\xcc"
    start = 0
    while (start := data.find(marker, start)) >= 0:
        offset = start + 1
        single_byte_controls.add(offset)
        probe[offset] = 0x0B
        start = offset + 1
    operands: set[int] = set()
    while True:
        tokens = decode_lexical_mes(bytes(probe), ascii_output=True)
        bad = next((token for token in tokens if token["type"] == "quoted"
                    and (token["size"] > 100
                         or b"\xff\xff" in bytes(token["bytes"])
                         or b"\xff\xfe" in bytes(token["bytes"]))), None)
        if bad is None:
            break
        offset = bad["offset"]
        operands.add(offset)
        probe[offset] = 0x0B
    tokens = [make_token(token["offset"], 1, data[token["offset"]:token["offset"] + 1],
                         "argument", 5)
              if token["offset"] in single_byte_arguments else
              make_token(token["offset"], 1, data[token["offset"]:token["offset"] + 1],
                         "control", f"CONTROL_{data[token['offset']]:02X}")
              if token["offset"] in single_byte_controls else
              make_token(token["offset"], 1, b"\x22", "control", "CONTROL_22")
              if token["offset"] in operands else
              make_token(token["offset"], 2, data[token["offset"]:token["offset"] + 2],
                         "control", f"CONTROL_{data[token['offset']]:02X}",
                         parameter=data[token["offset"] + 1])
              if token["offset"] in display_parameters else token for token in tokens]
    return resolve_ascii_and_gaiji(data, split_f0_control(tokens, data))


def annotate_ascii_half_spaces(info: dict, lang: dict, data: bytes) -> int:
    """Expose ASCII space commands immediately beside MES text records."""
    token = "{반각공백}"
    command = b"\x21\x20\x00"
    records = {record["offset"]: record for record in info["records"] if record.get("type") == "text"}
    entries = sorted(lang["entries"], key=lambda entry: int(entry["offset"], 16))
    previous_end = -1
    changed = 0
    for entry in entries:
        record = records[entry["offset"]]
        start, end = int(record["offset"], 16), int(record["end"], 16)
        left = right = 0
        while start - 3 * (left + 1) > previous_end and data[start - 3 * (left + 1):start - 3 * left] == command:
            left += 1
        while data[end + 1 + 3 * right:end + 4 + 3 * right] == command:
            right += 1
        # The same command can separate two records. Assign it to the earlier one.
        if start - 3 * left <= previous_end:
            left = 0
        previous_end = end + 3 * right
        if not (left or right):
            continue
        edges = {"left": left, "right": right}
        original_with_spaces = token * left + entry["original"] + token * right
        if "ascii_half_space_edges" in entry:
            if entry["ascii_half_space_edges"] != edges or entry.get("original_with_half_spaces") != original_with_spaces:
                raise ValueError(f"ASCII half-space metadata differs: {entry['id']}")
            changed += 1
            continue
        entry["ascii_half_space_edges"] = edges
        entry["original_with_half_spaces"] = original_with_spaces
        translation = entry.get("translation", "")
        if translation and translation != "@keep":
            entry["translation"] = token * left + translation + token * right
        changed += 1
    return changed


def decode_file(source: Path, source_root: Path) -> tuple[dict, dict]:
    data = source.read_bytes()
    records = make_records(decode_ballade_mes(data))
    records, _ = merge_special_text(records)
    candidates = [
        record for record in records
        if record.get("type") == "text"
        and record.get("translation_candidate")
        and record.get("original", "").strip()
    ]
    info = {
        "format": "maria-adv98-script-info-v1",
        "language": "jpn",
        "source": source.relative_to(source_root).as_posix(),
        "source_size": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "structured_ascii": True,
        "warning": "Lexical extraction; review candidates before reinsertion.",
        "text_record_count": sum(record.get("type") == "text" for record in records),
        "translation_candidate_count": len(candidates),
        "gaiji_count": sum(record.get("type") == "gaiji" for record in records),
        "records": records,
    }
    lang = {
        "format": "maria-adv98-script-lang-v1",
        "source_info": f"{source.name}_info.json",
        "entries": [
            {
                "id": f"text:{record['offset']}",
                "offset": record["offset"],
                "original": record["original"],
                "translation": "",
                "status": "incomplete: untranslated",
            }
            for record in candidates
        ],
    }
    info, lang, _ = merge_inline_names(info, lang)
    promote_display_quotes(info, lang)
    annotate_speakers(info, lang)
    annotate_layout(info, lang)
    if source.suffix.upper() == ".MES":
        annotate_ascii_half_spaces(info, lang, data)
        title = graph_op_title(info["records"])
        if title is not None:
            offset, original, raw = title
            if data[offset:offset + len(raw)] != raw:
                raise ValueError(f"GRAPH_OP title source differs: {source}")
            lang["graph_op_title"] = {
                "offset": f"{offset:05X}", "original": original, "translation": "",
            }
    return info, lang


def write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--force", action="store_true", help="replace existing JSON pairs")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98"
    sources = sorted(
        path for path in (source_root / "MES").rglob("*")
        if path.is_file() and path.suffix.upper() in {".MES", ".MEC"}
    )
    if not sources:
        parser.error(f"no MES or MEC files found under {source_root / 'MES'}")

    output_root = workspace / "script-pc98"
    destinations = [
        output_root / source.relative_to(source_root).parent / f"{source.name}_{kind}.json"
        for source in sources for kind in ("info", "lang")
    ]
    if not args.force:
        existing = next((path for path in destinations if path.exists()), None)
        if existing:
            parser.error(f"output exists (use --force to replace it): {existing}")

    total_entries = 0
    for source in sources:
        info, lang = decode_file(source, source_root)
        directory = output_root / source.relative_to(source_root).parent
        write_json(directory / f"{source.name}_info.json", info)
        write_json(directory / f"{source.name}_lang.json", lang)
        total_entries += len(lang["entries"])
    annotate_directory(output_root / "MES")
    print(f"extracted {len(sources)} MES/MEC files, {total_entries} text entries into {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
