#!/usr/bin/env python3
"""Encode all translated Dracula MES files in a workspace."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from modules.resources import default_font_table
from modules.adv_common.mes_batch import source_names, input_paths, missing_inputs, encode_command, selected_range, copy_dosbox_output


# Debug-only index range: 1-based and inclusive within the selected MES list.
# Leave both as None to encode the complete list.
DEBUG_INDEX_RANGE = (None, None)
# DEBUG_INDEX_RANGE = (4, 4)
# DEBUG_INDEX_RANGE = (4, 8)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="workspace containing jpn-pc98, script-pc98, kor-pc98, and kor-pc98-dosbox-x",
    )
    parser.add_argument("--files", nargs="+", metavar="MES")
    parser.add_argument(
        "--font-table",
        type=Path,
        default=default_font_table(),
        help="font table passed to encode_mes.py",
    )
    parser.add_argument("--no-dosbox-x", action="store_true")
    parser.add_argument("--manifest-dir", type=Path, help="write per-MES patch manifests")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    names = source_names(source_dir, {".MES"}, args.files)
    if not names:
        raise SystemExit(f"no MES files found: {source_dir}")

    indices = selected_range(len(names), DEBUG_INDEX_RANGE)

    font_table = args.font_table.resolve()
    failures = encoded = 0
    for index, name in enumerate(names, 1):
        if index not in indices:
            continue
        source, info, lang, output = input_paths(workspace, name)
        missing = missing_inputs(source, info, lang)
        if missing:
            print(f"{name}: missing {', '.join(missing)}", file=sys.stderr)
            failures += 1
            continue
        command = encode_command("gspecific.dracula.adv98_mes.encode_mes", (source, info, lang, output), font_table, args.manifest_dir)
        print(f"[{index}/{len(names)}] {name}")
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[3])
        if result.returncode:
            failures += 1
            print(f"{name}: failed (exit {result.returncode})", file=sys.stderr)
            continue
        if not args.no_dosbox_x:
            copy_dosbox_output(output, workspace)
        encoded += 1

    print(f"encoded: {encoded}; failed: {failures}; total: {len(names)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
