"""Encode all translated DOB2 ADV98 MES/CAL files in a workspace."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from modules.resources import default_font_table
from modules.adv_common.mes_batch import source_names, input_paths, missing_inputs, encode_command, copy_dosbox_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, help="write per-script patch manifests")
    parser.add_argument(
        "workspace",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="workspace containing jpn-pc98, script-pc98, kor-pc98, and kor-pc98-dosbox-x",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        metavar="SCRIPT",
        help="encode only these MES/CAL filenames; by default encode every source MES/CAL",
    )
    parser.add_argument(
        "--font-table",
        type=Path,
        default=default_font_table(),
        help="font table passed to encode_mes.py",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    names = source_names(source_dir, {".MES", ".CAL"}, args.files)
    if not names:
        raise SystemExit(f"no MES/CAL files found: {source_dir}")

    font_table = args.font_table.resolve()
    failures = 0
    encoded = 0
    for name in names:
        source, info, lang, output = input_paths(workspace, name)
        missing = missing_inputs(source, info, lang)
        if missing:
            print(f"{name}: missing {', '.join(missing)}", file=sys.stderr)
            failures += 1
            continue
        command = encode_command("gspecific.dob2.adv98_mes.encode_mes", (source, info, lang, output), font_table, args.manifest_dir)
        print(f"[{encoded + failures + 1}/{len(names)}] {name}")
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[3])
        if result.returncode:
            failures += 1
            print(f"{name}: failed (exit {result.returncode})", file=sys.stderr)
            continue
        destination = copy_dosbox_output(output, workspace)
        print(f"  copied: {destination}")
        encoded += 1

    print(f"encoded: {encoded}; failed: {failures}; total: {len(names)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
