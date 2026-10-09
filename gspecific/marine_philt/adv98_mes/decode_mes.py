#!/usr/bin/env python3
"""Decode Marine Philt ADV98 MES files into lossless Japanese JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from modules.adv_common.ascii import find_ascii_spans as _ascii_spans
from modules.adv_common.mes_decoder import (
    consume_selector_parameters as _consume_marine_parameters,
    decode_mes as decode_common_mes,
    make_records,
)


def decode_mes(data: bytes, *, structured_ascii: bool = True) -> list[dict[str, Any]]:
    """Lexically decode MES while preserving every source byte."""
    return decode_common_mes(
        data,
        structured_ascii=structured_ascii,
        parameter_controls=(0x08, 0x09, 0x0C, 0x0D, 0x19),
        transform_tokens=_consume_marine_parameters,
    )


def decode_document(source: Path, source_name: str) -> dict[str, Any]:
    data = source.read_bytes()
    tokens = decode_mes(data)
    records = make_records(tokens)
    candidates = [
        record
        for record in records
        if record["type"] == "text"
        and record["translation_candidate"]
        and record["original"].strip()
    ]
    return {
        "format": "marine-philt-adv98-mes-info-v1",
        "language": "jpn",
        "source": source_name,
        "source_size": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "warning": "Lossless lexical decode; keep control and gaiji records unchanged.",
        "text_record_count": sum(record["type"] == "text" for record in records),
        "translation_candidate_count": len(candidates),
        "gaiji_count": sum(record["type"] == "gaiji" for record in records),
        "records": records,
    }


def write_decoded(input_path: Path, output_path: Path, force: bool) -> int:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if input_path.is_file():
        sources = [(input_path, Path(input_path.name))]
    else:
        sources = [
            (path, path.relative_to(input_path))
            for path in sorted(input_path.rglob("*"))
            if path.is_file() and path.suffix.upper() == ".MES"
        ]
    if not sources:
        raise ValueError(f"no MES files found: {input_path}")

    totals = {"files_written": 0, "text_records": 0, "translation_candidates": 0, "gaiji": 0}
    for source, relative in sources:
        destination = (
            output_path
            if input_path.is_file() and output_path.suffix.lower() == ".json"
            else output_path / relative.parent / f"{relative.name}_info.json"
        )
        if destination.exists() and not force:
            raise FileExistsError(f"output exists; pass --force: {destination}")
        document = decode_document(source, relative.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        destination.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")
        totals["files_written"] += 1
        totals["text_records"] += document["text_record_count"]
        totals["translation_candidates"] += document["translation_candidate_count"]
        totals["gaiji"] += document["gaiji_count"]
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    return write_decoded(args.input, args.output, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
