"""Extract Ballade MES and MEC text into paired info/lang JSON files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from modules.adv_common.mes_decoder import make_records
from modules.adv_common.mes_lexer import decode_mes as decode_lexical_mes
from modules.adv_common.ascii import resolve_ascii_and_gaiji
from modules.adv_common.tokens import make_token
from .speaker_groups import annotate_directory, annotate_speakers
from .special_text import merge_special_text
from .text_layout import annotate_layout
from .inline_names import merge_inline_names
from .graph_titles import graph_op_title


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
    marker = b"\x1a\x00\x0a\x0d\x8f\xea"
    start = 0
    while (start := data.find(marker, start)) >= 0:
        offset = start + 3
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
    for marker in (b"\xa4\x0e\x91", b"\xa2\x0e\x93\x90\x53"):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + 1
            display_parameters.add(offset)
            probe[offset] = 0x08
            start = offset + 2
    for marker in (b"\x10\x2a\x00\x89\xbd\x7e", b"\x10\x2a\x00\x90\xe6",
                   b"\x10\x2a\x00\x54\x57\x37"):
        start = 0
        while (start := data.find(marker, start)) >= 0:
            offset = start + 1
            display_parameters.add(offset)
            probe[offset] = 0x08
            start = offset + 2
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
