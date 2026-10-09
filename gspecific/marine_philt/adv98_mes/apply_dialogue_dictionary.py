"""Apply unambiguous dictionary translations to Marine Philt MES files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from modules.adv_common.dictionary import load_candidates

if __package__:
    from .make_dialogue_dictionary import FORMAT, SECTIONS, write_json
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from make_dialogue_dictionary import FORMAT, SECTIONS, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--dictionary", type=Path)
    parser.add_argument("--only-empty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    dictionary_path = (args.dictionary or workspace / "annoying.json").resolve()
    if not dictionary_path.is_file():
        parser.error(f"dictionary not found: {dictionary_path}")
    paths = sorted((workspace / "script-pc98" / "MES").glob("*_lang.json"))
    candidates = load_candidates(dictionary_path, ignore_empty=True)
    changed_files = changed_entries = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != FORMAT:
            parser.error(f"unexpected format: {path}")
        changes = 0
        for section in SECTIONS:
            for item in document.get(section, []):
                key = item.get("combined_original") or item.get("original")
                candidate = candidates.get(key)
                current = item.get("translation")
                if candidate is None or candidate == current:
                    continue
                if args.only_empty and isinstance(current, str) and current.strip():
                    continue
                item["translation"] = candidate
                item["status"] = "passed" if candidate == "@keep" else "pending"
                changes += 1
        if changes:
            changed_files += 1
            changed_entries += changes
            print(f"{path.name}: {changes}")
            if not args.dry_run:
                write_json(path, document)
    print(f"{'preview' if args.dry_run else 'written'}: {changed_entries} entries in {changed_files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

