#!/usr/bin/env python3
"""Build a reusable dictionary from Dracula MES language JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.adv_common.dictionary import collect_dialogue_dictionary, ambiguous_translations


SECTIONS = ("dialogue_groups", "overlay_texts")
FORMAT = "dracula-adv98-mes-lang-v1"


def write_json(path: Path, value: dict) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path.cwd())
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    mes_dir = workspace / "script-pc98" / "MES"
    paths = sorted(mes_dir.glob("*_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {mes_dir}")

    dictionary, entries, translated, _ = collect_dialogue_dictionary(paths, sections=SECTIONS, expected_format=FORMAT)
    annoying = ambiguous_translations(dictionary)
    write_json(workspace / "dictionary.json", dictionary)
    write_json(workspace / "annoying.json", annoying)
    percent = translated / entries * 100 if entries else 100.0
    print(f"MES files: {len(paths)}, entries: {entries}")
    print(f"Translation progress: {translated}/{entries} ({percent:.2f}%)")
    print(f"dictionary.json: {len(dictionary)} source keys")
    print(f"annoying.json: {len(annoying)} ambiguous source keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
