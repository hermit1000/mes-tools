#!/usr/bin/env python3
"""Build a reusable translation dictionary from Necronomicon MES JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.adv_common.dictionary import collect_dialogue_dictionary, ambiguous_translations


FORMAT = "necronomicon-adv98-mes-lang-v1"
SECTIONS = ("dialogue_groups", "overlay_texts")


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path.cwd())
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    # Dialogue dictionaries are only for MES resources.  SYSTEM.MEC has a
    # different lang format even though it lives in the same directory.
    paths = sorted((workspace / "script-pc98" / "MES").glob("*.MES_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {workspace / 'script-pc98' / 'MES'}")
    dictionary, entries, translated, skipped = collect_dialogue_dictionary(
        paths, sections=SECTIONS, expected_format=FORMAT, skip_other_formats=True,
    )
    annoying = ambiguous_translations(dictionary)
    write_json(workspace / "dictionary.json", dictionary)
    write_json(workspace / "annoying.json", annoying)
    percent = translated / entries * 100 if entries else 100.0
    print(f"MES files: {len(paths)}, entries: {entries}")
    if skipped:
        print(f"Non-MES lang files skipped: {skipped}")
    print(f"Translation progress: {translated}/{entries} ({percent:.2f}%)")
    print(f"dictionary.json: {len(dictionary)} source keys")
    print(f"annoying.json: {len(annoying)} ambiguous source keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
