#!/usr/bin/env python3
"""Encode all translated Necronomicon MES files in a workspace."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from modules.adv_common.mes_batch import source_names, input_paths, missing_inputs, encode_command, copy_dosbox_output


# Debug-only index range: 1-based and inclusive within the selected MES list.
# Examples: (4, 4) encodes only the 4th item; (4, 8) encodes items 4 through 8.
# Leave both as None to encode the complete list.
DEBUG_INDEX_RANGE = (None, None)


def run_encoder(command: list[str], repo_root: Path) -> subprocess.CompletedProcess:
    """Each task runs in its own Python process; threads only supervise it."""
    environment = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        command,
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--files", nargs="+", metavar="MES")
    parser.add_argument(
        "--font-table",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "font_table-kor-jin-necro-compact.json",
    )
    parser.add_argument(
        "--compact-remap",
        "--marine-remap",
        dest="compact_remap",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "necro_compact_font_mapping_top50.json",
        help="map selected frequent characters to ADV98 one-byte compressed glyph codes",
    )
    parser.add_argument(
        "--no-compact-remap",
        dest="compact_remap",
        action="store_const",
        const=None,
        help="disable the default Necronomicon compact character remap",
    )
    parser.add_argument("--no-dosbox-x", action="store_true")
    parser.add_argument("--manifest-dir", type=Path)
    parser.add_argument(
        "--jobs",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="number of concurrent encoder processes (default: up to 4; 1 for sequential)",
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")

    workspace = args.workspace.resolve()
    source_dir = workspace / "jpn-pc98" / "MES"
    names = source_names(source_dir, {".MES"}, args.files)
    if not names:
        raise SystemExit(f"no MES files found: {source_dir}")
    if len({name.casefold() for name in names}) != len(names):
        parser.error("duplicate MES names would write the same output concurrently")

    debug_start, debug_end = DEBUG_INDEX_RANGE
    # debug_start, debug_end = (13, 14)
    # debug_start, debug_end = (4, 4)
    # debug_start, debug_end = (204, 205)
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

    failures = encoded = 0
    module = "gspecific.necronomicon.adv98_mes.encode_mes"
    repo_root = Path(__file__).resolve().parents[3]
    jobs = []
    for index, name in enumerate(names, 1):
        if not start <= index <= end:
            continue
        source, info, lang, output = input_paths(workspace, name)
        missing = missing_inputs(source, info, lang)
        if missing:
            print(f"{name}: missing {', '.join(missing)}", file=sys.stderr)
            failures += 1
            continue
        command = encode_command(module, (source, info, lang, output), args.font_table)
        if args.compact_remap:
            command += ["--compact-remap", str(args.compact_remap.resolve())]
        if args.manifest_dir:
            command += ["--patch-manifest", str((args.manifest_dir / f"{name}.patches.json").resolve())]
        jobs.append((index, name, output, command))
    if jobs:
        workers = min(args.jobs, len(jobs))
        print(f"encoder processes: {workers}")
        # The encoder already runs as a subprocess. A thread pool avoids an
        # extra process-pool layer and Windows spawn/import overhead.
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_encoder, command, repo_root): (index, name, output)
                for index, name, output, command in jobs
            }
            for future in as_completed(futures):
                index, name, output = futures[future]
                print(f"[{index}/{len(names)}] {name}")
                try:
                    result = future.result()
                    if result.stdout:
                        print(result.stdout, end="")
                    if result.stderr:
                        print(result.stderr, end="", file=sys.stderr)
                    if result.returncode:
                        failures += 1
                        print(f"{name}: failed (exit {result.returncode})", file=sys.stderr)
                        continue
                    if not args.no_dosbox_x:
                        copy_dosbox_output(output, workspace)
                    encoded += 1
                except OSError as error:
                    failures += 1
                    print(f"{name}: failed ({error})", file=sys.stderr)
    print(f"encoded: {encoded}; failed: {failures}; total: {len(names)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
