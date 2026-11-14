"""Show MEC dialogue records whose encoded translation length differs from the source."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from modules.adv_common.text import load_marine_remap

from .encode_mes import DEFAULT_FONT_TABLE, DEFAULT_WORKSPACE, encode_ballade_text, load_maria_font_codes, same_display_text
from .inline_names import encode_inline_names, prepare_name_moves, refresh_inline_names
from .text_layout import translation_texts


DEFAULT_MAPPING = Path(__file__).with_name("maria_compact_font_mapping_top67.json")


def mec_name(value: str) -> str:
    name = Path(value).name
    if name != value:
        raise ValueError(f"enter only a filename: {value}")
    if name.upper().endswith(".MEC_LANG.JSON"):
        name = name[:-10]
    if not name.upper().endswith(".MEC"):
        raise ValueError(f"expected .MEC or .MEC_lang.json: {value}")
    return name


def check_file(workspace: Path, name: str, codes: dict[str, str], compact: dict[str, str]) -> tuple[Counter[str], list[dict]]:
    base = workspace / "script-pc98" / "MES"
    info_path = base / f"{name}_info.json"
    lang_path = base / f"{name}_lang.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    lang = json.loads(lang_path.read_text(encoding="utf-8"))
    refresh_inline_names(info, lang, base)
    prepare_name_moves(info, lang, equivalent=same_display_text)
    effective = translation_texts(info, lang)
    records = {record["offset"]: record for record in info["records"] if record.get("type") == "text"}
    counts: Counter[str] = Counter(entries=len(lang["entries"]))
    mismatches = []
    for entry in lang["entries"]:
        translation = entry.get("translation", "")
        if not translation or translation == "@keep" or same_display_text(entry["original"], translation):
            continue
        record = records[entry["offset"]]
        if "ascii" in record.get("encodings", []):
            continue
        original_size = len(bytes.fromhex(record["raw_hex"]))
        if non_display := entry.get("leading_non_display_bytes"):
            original_size -= len(bytes.fromhex(non_display))
        try:
            encoded = encode_inline_names(
                effective.get(entry["offset"], translation), record,
                lambda text: encode_ballade_text(text, codes, compact),
            )
        except ValueError as error:
            raise ValueError(f"{lang_path.name}:{entry['offset']}: {error}") from error
        encoded_size = len(encoded)
        counts["translated"] += 1
        if encoded_size == original_size:
            counts["exact"] += 1
            continue
        direction = "shorter" if encoded_size < original_size else "longer"
        counts[direction] += 1
        if direction == "shorter":
            counts["padding_bytes"] += original_size - encoded_size
        mismatches.append({
            "file": name,
            "id": entry["id"],
            "offset": entry["offset"],
            "original": entry["original"],
            "translation": translation,
            "original_bytes": original_size,
            "encoded_bytes": encoded_size,
            "difference": encoded_size - original_size,
            "direction": direction,
            "padding_bytes": max(0, original_size - encoded_size),
            "final_bytes": original_size,
            "result": "auto_padded" if direction == "shorter" else "kept_original",
        })
    return counts, mismatches


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="MEC filename or MEC_lang.json filename; default: failed MEC files from report")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--font-table", type=Path, default=DEFAULT_FONT_TABLE)
    parser.add_argument("--compact-remap", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--report", type=Path, help="batch encode report used when filenames are omitted")
    parser.add_argument("--output", type=Path, help="optional JSON result path")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if args.files:
        try:
            names = list(dict.fromkeys(mec_name(value) for value in args.files))
        except ValueError as error:
            parser.error(str(error))
    else:
        report_path = args.report or workspace / "kor-pc98" / "encode_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if Path(report["compact_remap"]).resolve() != args.compact_remap.resolve():
            raise ValueError(f"report uses a different compact remap: {report_path}")
        error_path = report_path.with_name(
            "encode_errors.json" if report_path.name == "encode_report.json"
            else f"{report_path.stem}_errors{report_path.suffix}"
        )
        fallback_files = []
        if error_path.exists():
            errors = json.loads(error_path.read_text(encoding="utf-8"))
            if errors.get("compact_remap") != report["compact_remap"]:
                raise ValueError(f"error report uses a different compact remap: {error_path}")
            fallback_files = [item["file"] for item in errors["files"]]
        names = list(dict.fromkeys(
            [item["file"] for item in report["files"]
             if item.get("category") == "mec_text_length" or item.get("mec_original_fallbacks")]
            + fallback_files
        ))

    codes = load_maria_font_codes(args.font_table)
    compact = load_marine_remap(args.compact_remap)
    summary: Counter[str] = Counter()
    by_file = {}
    mismatches = []
    for name in names:
        counts, file_mismatches = check_file(workspace, name, codes, compact)
        summary.update(counts)
        by_file[name] = dict(counts)
        mismatches.extend(file_mismatches)
        print(f"{name}: {counts['translated']} translated, {counts['exact']} exact, "
              f"{counts['shorter']} auto-padded ({counts['padding_bytes']} bytes), "
              f"{counts['longer']} kept original (too long)")
        for item in file_mismatches:
            print(f"  {item['id']} ({item['offset']}): {item['original_bytes']} -> "
                  f"{item['encoded_bytes']} bytes ({item['difference']:+d}; {item['result']})")
            print(f"    원문: {item['original']}")
            print(f"    번역: {item['translation']}")
    if args.output or not args.files:
        result = {
            "format": "ballade-mec-length-review-v1",
            "compact_remap": str(args.compact_remap.resolve()),
            "checked_files": len(names),
            "summary": dict(summary),
            "by_file": by_file,
            "mismatches": mismatches,
        }
        output = args.output or workspace / "ballade_mec_length_review_top67.json"
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
