#!/usr/bin/env python3
"""Decode Necronomicon ADV98 MES files into translation JSON files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from modules.adv_common.mes_decoder import decode_mes as decode_tokens, make_records
from gspecific.necronomicon.system_mec import decode_adv98_bytes


SPEAKER_RE = re.compile(r"^「[^」]+」")


def repair_speaker_boundary(record: dict[str, Any]) -> dict[str, Any]:
    """Remove a stray SJIS character immediately before a speaker marker.

    Some MES records contain one decoded Japanese character before ``「`` even
    though the byte sequence is a boundary/control artifact.  Keeping that
    character in ``original`` causes translators to copy it into ``translation``
    and later makes font encoding fail.  Only repair it when the raw bytes begin
    with the same character encoded as Shift-JIS.
    """
    if record.get("type") != "text":
        return record
    original = record.get("original")
    raw_hex = record.get("raw_hex")
    if not isinstance(original, str) or not isinstance(raw_hex, str):
        return record
    match = re.match(r"^([^「\s])(?=「)", original)
    if not match:
        return record
    prefix = match.group(1)
    try:
        prefix_bytes = prefix.encode("cp932")
        raw = bytes.fromhex(raw_hex)
    except (UnicodeEncodeError, ValueError):
        return record
    if len(prefix_bytes) != 2 or not raw.startswith(prefix_bytes):
        return record
    record["offset"] = f"{int(record['offset'], 16) + len(prefix_bytes):05X}"
    record["raw_hex"] = " ".join(f"{byte:02X}" for byte in raw[len(prefix_bytes):])
    record["original"] = original[len(prefix):]
    return record


def repair_condition_prefix(record: dict[str, Any], data: bytes) -> dict[str, Any]:
    """Preserve the verified NA_05E condition tail misread as SJIS '遉'.

    Keep the original byte range for encoder compatibility, but mark the
    operand/boundary prefix as non-translatable. Do not strip a genuine 遉.
    """
    if record.get("type") != "text":
        return record
    start = int(record["offset"], 16)
    if (
        start > 0 and data[start - 1:start + 2] == b"\x0b\xe7\xa4"
        and bytes.fromhex(record.get("raw_hex", "")).startswith(b"\xe7\xa4")
        and record.get("original", "").startswith("遉")
    ):
        record["encoding_prefix_hex"] = "E7 A4"
        record["original"] = record["original"][1:]
    return record


def repair_menu_flag_prefix(record: dict[str, Any], data: bytes) -> dict[str, Any]:
    """Preserve NG_05A's 09/91 flag operation and following 8197 boundary.

    The lexical decoder misreads the operand and boundary as '早浴ご'.
    Preserve the source range, but decode the visible text at the true boundary.
    """
    if record.get("type") != "text":
        return record
    start = int(record["offset"], 16)
    raw = bytes.fromhex(record.get("raw_hex", ""))
    if (
        start > 0 and data[start - 1:start + 3] == b"\x09\x91\x81\x97"
        and raw.startswith(b"\x91\x81\x97")
        and record.get("original", "").startswith("早浴ご")
    ):
        record["encoding_prefix_hex"] = "91 81 97"
        record["original"] = decode_adv98_bytes(raw[3:])
    return record


def decode_document(source: Path, source_name: str, *, structured_ascii: bool = True) -> dict[str, Any]:
    data = source.read_bytes()
    records = [repair_menu_flag_prefix(repair_condition_prefix(repair_speaker_boundary(record), data), data)
               for record in make_records(decode_tokens(data, structured_ascii=structured_ascii))]
    candidates = [
        record for record in records
        if record.get("type") == "text"
        and record.get("translation_candidate")
        and record.get("original", "").strip()
    ]
    return {
        "format": "necronomicon-adv98-mes-info-v1",
        "language": "jpn",
        "source": source_name,
        "source_size": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "structured_ascii": structured_ascii,
        "warning": "ADV98 lexical decode; review candidates before reinsertion.",
        "text_record_count": sum(record.get("type") == "text" for record in records),
        "translation_candidate_count": len(candidates),
        "gaiji_count": sum(record.get("type") == "gaiji" for record in records),
        "records": records,
    }


def make_lang(info_name: str, document: dict[str, Any]) -> dict[str, Any]:
    dialogues = []
    overlays = []
    for record in document["records"]:
        if (
            record.get("type") != "text"
            or not record.get("translation_candidate")
            or not record.get("original", "").strip()
        ):
            continue
        dialogue = SPEAKER_RE.match(record["original"]) is not None
        entries = dialogues if dialogue else overlays
        entries.append({
            "id": f'{"dialogue" if dialogue else "overlay"}:{record["offset"]}',
            "offset": record["offset"],
            "original": record["original"],
            "translation": "",
            "status": f'incomplete: untranslated {"dialogue" if dialogue else "overlay"}',
        })
        if record.get("encoding_prefix_hex"):
            entries[-1]["encoding_prefix_hex"] = record["encoding_prefix_hex"]
    return {
        "format": "necronomicon-adv98-mes-lang-v1",
        "source_info": info_name,
        "dialogue_groups": dialogues,
        "overlay_texts": overlays,
    }


def _sources(input_path: Path) -> list[tuple[Path, Path]]:
    if input_path.is_file():
        return [(input_path, Path(input_path.name))]
    return [
        (path, path.relative_to(input_path))
        for path in sorted(input_path.rglob("*.MES"))
        if path.is_file()
    ]


def write_decoded(input_path: Path, output_path: Path, force: bool, *, structured_ascii: bool = True) -> int:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    sources = _sources(input_path)
    if not sources:
        raise ValueError(f"no MES files found: {input_path}")

    totals = {"files_written": 0, "translation_entries": 0, "text_records": 0,
              "translation_candidates": 0, "gaiji": 0}
    for source, relative in sources:
        info_path = (
            output_path if input_path.is_file() and output_path.suffix.lower() == ".json"
            else output_path / relative.parent / f"{relative.name}_info.json"
        )
        lang_path = info_path.with_name(info_path.name.replace("_info.json", "_lang.json"))
        if not force and (info_path.exists() or lang_path.exists()):
            raise FileExistsError(f"output exists; pass --force: {info_path} / {lang_path}")
        document = decode_document(source, relative.as_posix(), structured_ascii=structured_ascii)
        lang = make_lang(info_path.name, document)
        info_path.parent.mkdir(parents=True, exist_ok=True)
        info_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lang_path.write_text(json.dumps(lang, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        totals["files_written"] += 1
        totals["translation_entries"] += len(lang["dialogue_groups"]) + len(lang["overlay_texts"])
        totals["text_records"] += document["text_record_count"]
        totals["translation_candidates"] += document["translation_candidate_count"]
        totals["gaiji"] += document["gaiji_count"]
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?", default=Path.cwd() / 'jpn-pc98' / 'MES')
    parser.add_argument("output", type=Path, nargs="?", default=Path.cwd() / 'script-pc98' / 'MES')
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--structured-ascii", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    return write_decoded(args.input, args.output, args.force, structured_ascii=args.structured_ascii)


if __name__ == "__main__":
    raise SystemExit(main())
