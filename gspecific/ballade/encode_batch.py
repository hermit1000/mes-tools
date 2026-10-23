"""Encode Ballade MES/MEC files from the workspace into an output directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.adv_common.text import load_marine_remap
from gspecific.ballade.analyze_mec_lengths import check_file
from gspecific.ballade.encode_mes import (
    DEFAULT_FONT_TABLE,
    DEFAULT_WORKSPACE,
    encode_file,
    load_maria_font_codes,
)


DEFAULT_COMPACT_REMAP = Path(__file__).with_name(
    "maria_compact_font_mapping_top67.json"
)
DEFAULT_FILES = []  # Empty: all files. Example: ["001.MES", "SAVE.MEC"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--font-table", type=Path, default=DEFAULT_FONT_TABLE)
    parser.add_argument(
        "--compact-remap",
        type=Path,
        default=DEFAULT_COMPACT_REMAP,
        help=f"one-byte font remap JSON; default: {DEFAULT_COMPACT_REMAP}",
    )
    parser.add_argument(
        "--files", nargs="+", help="MES/MEC filenames; overrides DEFAULT_FILES"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="validate without writing output files"
    )
    parser.add_argument(
        "--allow-partial",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="write valid files even if others fail (default: enabled)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="custom single output; default: both kor-pc98/MES and kor-pc98-dosbox-x/MES",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="write per-file validation and capacity results as JSON",
    )
    parser.add_argument("--manifest-dir", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    names = args.files if args.files is not None else list(DEFAULT_FILES)
    if not names:
        names = sorted(
            path.name
            for path in source_dir.iterdir()
            if path.is_file() and path.suffix.upper() in {".MES", ".MEC"}
        )
    if any(
        Path(name).name != name or Path(name).suffix.upper() not in {".MES", ".MEC"}
        for name in names
    ):
        parser.error("file list accepts only MES/MEC filenames")
    if len({name.casefold() for name in names}) != len(names):
        parser.error("duplicate file names")
    successes = failures = replacements = 0
    results = []
    valid_names = []
    mec_codes = mec_compact = None
    for name in names:
        source = source_dir / name
        info = workspace / "script-pc98" / "MES" / f"{name}_info.json"
        lang = workspace / "script-pc98" / "MES" / f"{name}_lang.json"
        result = {
            "file": name,
            "source_size": source.stat().st_size if source.is_file() else None,
        }
        mec_original_fallbacks = []
        try:
            count, size = encode_file(
                source,
                info,
                lang,
                None,
                args.font_table,
                compact_remap=args.compact_remap,
                mec_original_fallbacks=mec_original_fallbacks,
            )
        except (OSError, ValueError, KeyError) as error:
            failures += 1
            message = str(error)
            if "MES exceeds" in message:
                category = "mes_size"
                match = re.search(r"exceeds (\d+) bytes: .* -> (\d+) bytes", message)
                if match:
                    result["capacity_limit"] = int(match.group(1))
                    result["encoded_size"] = int(match.group(2))
                    result["over_by"] = (
                        result["encoded_size"] - result["capacity_limit"]
                    )
            elif "A5 row overflow" in message:
                category = "a5_row_overflow"
            elif "absent from the selected font table" in message:
                category = "missing_glyph"
            elif "ASCII output record" in message:
                category = "ascii_output"
            else:
                category = "other"
            result.update(status="failed", category=category, error=message)
            print(f"FAIL {name}: {message}", file=sys.stderr)
            results.append(result)
            continue
        successes += 1
        replacements += count
        valid_names.append(name)
        result.update(status="validated", replacements=count, encoded_size=size)
        if mec_original_fallbacks:
            if mec_codes is None:
                mec_codes = load_maria_font_codes(args.font_table)
                mec_compact = load_marine_remap(args.compact_remap)
            _, differences = check_file(workspace, name, mec_codes, mec_compact)
            oversized = [item for item in differences if item["direction"] == "longer"]
            assert {item["offset"] for item in oversized} == {
                item["offset"] for item in mec_original_fallbacks
            }
            result["mec_original_fallbacks"] = oversized
        results.append(result)
        print(
            f"OK {name}: {count} replacements, {size} bytes"
            + (
                f"; {len(mec_original_fallbacks)} records kept original"
                if mec_original_fallbacks
                else ""
            )
        )
    print(
        f"validated: {successes}; failed: {failures}; replacements: {replacements}; total: {len(names)}"
    )
    output_dir = args.output_dir or workspace / "kor-pc98" / "MES"
    secondary_dir = None if args.output_dir else workspace / "kor-pc98-dosbox-x" / "MES"
    if not args.dry_run and (not failures or args.allow_partial):
        for name in valid_names:
            source = source_dir / name
            info = workspace / "script-pc98" / "MES" / f"{name}_info.json"
            lang = workspace / "script-pc98" / "MES" / f"{name}_lang.json"
            output = output_dir / name
            secondary = secondary_dir / name if secondary_dir else None
            manifest = (
                args.manifest_dir / f"{name}.patch.json" if args.manifest_dir else None
            )
            encode_file(
                source,
                info,
                lang,
                output,
                args.font_table,
                compact_remap=args.compact_remap,
                patch_manifest=manifest,
                secondary_output=secondary,
            )
        for result in results:
            if result["status"] == "validated":
                result["status"] = "encoded"
        destinations = f"{output_dir}" + (
            f" and {secondary_dir}" if secondary_dir else ""
        )
        print(f"encoded: {len(valid_names)} into {destinations}")
    report_path = args.report
    if report_path is None and not args.output_dir and not args.dry_run:
        report_path = workspace / "kor-pc98" / "encode_report.json"
    if report_path:
        report = {
            "format": "maria-encode-batch-report-v1",
            "compact_remap": str(args.compact_remap.resolve())
            if args.compact_remap
            else None,
            "output_dir": str(output_dir.resolve()),
            "secondary_output_dir": str(secondary_dir.resolve())
            if secondary_dir
            else None,
            "dry_run": args.dry_run,
            "validated": successes,
            "failed": failures,
            "encoded": sum(result["status"] == "encoded" for result in results),
            "files": [
                {
                    key: value
                    for key, value in result.items()
                    if key != "mec_original_fallbacks"
                }
                for result in results
            ],
        }
        error_path = report_path.with_name(
            "encode_errors.json"
            if report_path.name == "encode_report.json"
            else f"{report_path.stem}_errors{report_path.suffix}"
        )
        error_report = {
            "format": "maria-encode-batch-errors-v1",
            "source_report": report_path.name,
            "compact_remap": report["compact_remap"],
            "mec_original_fallbacks": sum(
                len(result.get("mec_original_fallbacks", [])) for result in results
            ),
            "files": [
                {
                    "file": result["file"],
                    "mec_original_fallbacks": result["mec_original_fallbacks"],
                }
                for result in results
                if result.get("mec_original_fallbacks")
            ],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
        error_path.write_text(
            json.dumps(error_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\r\n",
        )
        print(f"reports: {report_path} and {error_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
