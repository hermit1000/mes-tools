"""Apply unique dictionary candidates to Ballade lang entries, including existing translations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.adv_common.dictionary import load_candidates

from gspecific.ballade.text_layout import FORCED_DBCS_TOKEN

from gspecific.ballade.make_dialogue_dictionary import (
    DEFAULT_WORKSPACE,
    FORMAT,
    semantic_translation,
    write_json,
)


def plan_updates(
    paths: list[Path], candidates: dict[str, str]
) -> tuple[list[tuple[Path, dict, list[str]]], int]:
    updates = []
    total = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != FORMAT:
            raise ValueError(f"unexpected lang format: {path}")
        changed_ids = []
        for entry in document["entries"]:
            current = entry.get("translation")
            candidate = candidates.get(entry.get("original_with_half_spaces", entry.get("original")))
            if candidate is None:
                continue
            candidate = semantic_translation(candidate)
            if current == candidate:
                continue
            if isinstance(current, str) and semantic_translation(current) == candidate:
                if path.name.upper().endswith(".MEC_LANG.JSON") or FORCED_DBCS_TOKEN.search(current):
                    continue  # Preserve record-specific byte-length choices.
            entry["translation"] = candidate
            entry["status"] = "passed" if candidate == "@keep" else "translated"
            changed_ids.append(entry["id"])
        if changed_ids:
            updates.append((path, document, changed_ids))
            total += len(changed_ids)
    return updates, total


def plan_bundle_updates(
    bundle_dir: Path, updates: list[tuple[Path, dict, list[str]]]
) -> tuple[list[tuple[Path, dict]], int]:
    if not bundle_dir.is_dir():
        return [], 0
    targets = {
        (path.name, entry["id"]): entry
        for path, document, changed_ids in updates
        for entry in document["entries"]
        if entry["id"] in changed_ids
    }
    bundle_updates = []
    seen = set()
    total = 0
    for path in sorted(bundle_dir.glob("bundle_*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for file in bundle["files"]:
            for item in file["items"]:
                for segment in item["segments"]:
                    key = (file["source_file"], segment["id"])
                    target = targets.get(key)
                    if target is None:
                        continue
                    if key in seen or (segment["offset"], segment["original"]) != (
                        target["offset"],
                        target["original"],
                    ):
                        raise ValueError(f"bundle entry changed or duplicated: {key}")
                    seen.add(key)
                    current = segment.get("translation", "")
                    if current != target["translation"]:
                        segment["translation"] = target["translation"]
                        total += 1
                        changed = True
        if changed:
            bundle_updates.append((path, bundle))
    if seen != set(targets):
        raise ValueError(
            f"missing bundle entries for {len(set(targets) - seen)} lang updates"
        )
    return bundle_updates, total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help=f"default: {DEFAULT_WORKSPACE}",
    )
    parser.add_argument(
        "--dictionary", type=Path, help="default: workspace/annoying.json"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only; default is to write updates")
    mode.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source = workspace / "script-pc98" / "MES"
    paths = sorted(source.glob("*_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {source}")
    dictionary_path = (
        args.dictionary.resolve() if args.dictionary else workspace / "annoying.json"
    )
    if not dictionary_path.is_file():
        parser.error(f"dictionary not found: {dictionary_path}")
    candidates = load_candidates(dictionary_path, ignore_empty=True)
    updates, total = plan_updates(paths, candidates)
    bundle_updates, bundle_total = plan_bundle_updates(
        workspace / "translation_bundles", updates
    )
    if not args.dry_run:
        for path, document, _ in updates:
            write_json(path, document)
        for path, bundle in bundle_updates:
            write_json(path, bundle)
    action = "would update" if args.dry_run else "updated"
    print(
        f"{action} {total} entries in {len(updates)} lang files and "
        f"{bundle_total} segments in {len(bundle_updates)} bundles; usable dictionary keys: {len(candidates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
