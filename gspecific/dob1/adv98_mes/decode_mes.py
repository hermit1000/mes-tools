#!/usr/bin/env python3
"""Decode one MES file or a directory tree into structured Japanese JSON.

With no output path, print a diagnostic lexical decode of one file. Unknown
commands are retained instead of being assigned guessed meanings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


from modules.adv_common.mes_lexer import COMMAND_NAMES, SPECIAL_SJIS, decode_mes, format_text, make_readable_records
from modules.adv_common.tokens import make_token, verify_tokens


def diagnostic_main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="MES file to decode")
    parser.add_argument("--structured-ascii", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--json", action="store_true", help="write structured JSON")
    parser.add_argument(
        "--readable-json",
        action="store_true",
        help="group adjacent text and command arguments for human inspection",
    )
    parser.add_argument(
        "--dialogue-json",
        action="store_true",
        help="write only multi-character translation candidates",
    )
    args = parser.parse_args()

    data = args.input.read_bytes()
    tokens = decode_mes(data, ascii_output=args.structured_ascii)
    readable_records = make_readable_records(tokens)
    if args.dialogue_json:
        candidates = [
            {
                "offset": item["offset"],
                "end": item["end"],
                "text": item["text"],
                "raw_hex": item["raw_hex"],
                "encodings": item["encodings"],
            }
            for item in readable_records
            if item["type"] == "text" and item["translation_candidate"]
        ]
        print(
            json.dumps(
                {
                    "source": str(args.input.resolve()),
                    "size": len(data),
                    "warning": (
                        "Candidate list only. Unknown command schemas can still cause false positives; "
                        "do not use this file for automatic reinsertion yet."
                    ),
                    "candidate_count": len(candidates),
                    "dialogue_candidates": candidates,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.readable_json:
        print(
            json.dumps(
                {
                    "source": str(args.input.resolve()),
                    "size": len(data),
                    "warning": (
                        "This is a provisional lexical decode. Unknown command schemas can still make "
                        "isolated text candidates false positives."
                    ),
                    "legend": {
                        "text": "Adjacent decoded characters; translation_candidate is only a heuristic.",
                        "command": "MES opcode followed by immediately adjacent recognized arguments.",
                        "boundary": "One-byte parser boundary A0-A4.",
                        "control": "Non-printing or not-yet-understood control token.",
                        "end": "FFFF or FFFE interpreter terminator.",
                    },
                    "records": readable_records,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.json:
        print(
            json.dumps(
                {"source": str(args.input.resolve()), "size": len(data), "tokens": tokens},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(format_text(tokens))
    return 0


PACKAGE_DIR = Path(__file__).resolve().parent


def load_definition(name: str) -> dict[str, Any]:
    return json.loads((PACKAGE_DIR / name).read_text(encoding="utf-8"))


def annotate_records(records: list[dict[str, Any]]) -> None:
    controls = load_definition("control_codes.json")["controls"]
    macros = load_definition("macro_catalog.json")["macros"]
    for record in records:
        if record["type"] == "text":
            record["original"] = record.pop("text")
        elif record["type"] == "control":
            definition = controls.get(record.get("raw_hex", "").replace(" ", ""))
            if definition:
                record["display"] = definition["display"]
                record["editable"] = definition["editable"]
        elif record["type"] == "command" and record["name"] == "CALL_BUILTIN":
            arguments = record["arguments"]
            if arguments and isinstance(arguments[0]["value"], int):
                slot = f'{arguments[0]["value"]:02X}'
                definition = macros.get(slot)
                record["macro_slot"] = slot
                if definition:
                    record["macro_name"] = definition["name"]
                    record["macro_category"] = definition["category"]
                    if "original" in definition:
                        record["macro_preview"] = definition["original"]


def decode_document(source: Path, source_name: str, *, structured_ascii: bool = True) -> dict[str, Any]:
    data = source.read_bytes()
    tokens = decode_mes(data, ascii_output=structured_ascii)
    verify_tokens(data, tokens)
    records = make_readable_records(tokens)
    annotate_records(records)
    return {
        "format": "dob1-adv98-mes-jpn-v1",
        "language": "jpn",
        "source": source_name,
        "source_size": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "structured_ascii": structured_ascii,
        "warning": "Provisional lexical decode; review translation candidates manually.",
        "text_record_count": sum(r["type"] == "text" for r in records),
        "translation_candidate_count": sum(
            r["type"] == "text" and r["translation_candidate"] for r in records
        ),
        "records": records,
    }


def write_decoded_json(input_path: Path, output_path: Path, force: bool, *, structured_ascii: bool = True) -> int:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if input_path.is_file():
        sources = [(input_path, Path(input_path.name))]
        destinations = [
            output_path
            if output_path.suffix.lower() == ".json"
            else output_path / f"{input_path.name}_jpn.json"
        ]
    else:
        sources = [
            (path, path.relative_to(input_path))
            for path in sorted(input_path.rglob("*"))
            if path.is_file() and path.suffix.upper() == ".MES"
        ]
        destinations = [
            output_path / relative.parent / f"{relative.name}_jpn.json"
            for _, relative in sources
        ]
    if not sources:
        raise ValueError(f"no MES files found: {input_path}")

    totals = {"files_written": 0, "text_records": 0, "translation_candidates": 0}
    for (source, relative), destination in zip(sources, destinations):
        if destination.exists() and not force:
            raise FileExistsError(f"output exists; pass --force: {destination}")
        document = decode_document(source, relative.as_posix(), structured_ascii=structured_ascii)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        totals["files_written"] += 1
        totals["text_records"] += document["text_record_count"]
        totals["translation_candidates"] += document["translation_candidate_count"]
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--structured-ascii", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--readable-json", action="store_true")
    parser.add_argument("--dialogue-json", action="store_true")
    args = parser.parse_args()
    if args.output is None:
        return diagnostic_main()
    return write_decoded_json(args.input, args.output, args.force, structured_ascii=args.structured_ascii)


if __name__ == "__main__":
    raise SystemExit(main())
