"""Encode all translated Marine Philt MES files in a workspace."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from modules.resources import default_font_table
from modules.adv_common.mes_batch import source_names, input_paths, missing_inputs, encode_command, copy_dosbox_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--files", nargs="+", metavar="MES")
    parser.add_argument("--font-table", type=Path, default=default_font_table())
    parser.add_argument(
        "--marine-remap",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "marine_compact_font_mapping_top20.json",
        help="Marine compressed glyph remap table (enabled by default)",
    )
    parser.add_argument("--no-dosbox-x", action="store_true")
    parser.add_argument(
        "--allow-oversize-segments",
        action="store_true",
        help="warn instead of stopping for {next} segments over 81 cells",
    )
    parser.add_argument("--manifest-dir", type=Path, help="write per-MES patch manifests")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    names = source_names(source_dir, {".MES"}, args.files)
    failures = encoded = 0

    # Debug-only index range: 1-based and inclusive, matching the loop display.
    # Examples: (4, 4) encodes only the 4th item; (4, 8) encodes items 4 through 8.
    # Leave both as None to encode the complete list.
    DEBUG_INDEX_RANGE = (None, None)
    # DEBUG_INDEX_RANGE = (99, 99)
    # The default batch processes every MES file.
    debug_start, debug_end = DEBUG_INDEX_RANGE
    if debug_start is not None or debug_end is not None:
        start = 1 if debug_start is None else debug_start
        end = len(names) if debug_end is None else debug_end
        if start < 1 or start > end or end > len(names):
            raise ValueError(
                f"invalid DEBUG_INDEX_RANGE={DEBUG_INDEX_RANGE}; expected 1 <= start <= end <= {len(names)}"
            )
    else:
        start = 1
        end = len(names)

    for index, name in enumerate(names, 1):
        if not start <= index <= end:
            continue
        source, info, lang, output = input_paths(workspace, name)
        missing = missing_inputs(source, info, lang)
        if missing:
            print(f"{name}: missing {', '.join(missing)}", file=sys.stderr)
            print("stopped: batch encoding aborted", file=sys.stderr)
            return 1
        command = encode_command("gspecific.marine_philt.adv98_mes.encode_mes", (source, info, lang, output), args.font_table)
        command += ["--marine-remap", str(args.marine_remap.resolve())]
        if args.allow_oversize_segments:
            command.append("--allow-oversize-segments")
        if args.manifest_dir:
            command += ["--patch-manifest", str((args.manifest_dir / f"{name}.patches.json").resolve())]
        print(f"[{index}/{len(names)}] {name}")
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[3])
        if result.returncode:
            print(f"stopped: batch encoding aborted at {name}", file=sys.stderr)
            return 1
        if not args.no_dosbox_x:
            copy_dosbox_output(output, workspace)
        encoded += 1
    print(f"encoded: {encoded}; failed: {failures}; total: {len(names)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
