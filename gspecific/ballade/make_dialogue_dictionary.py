"""Build a reusable dictionary from translated Ballade MES/MEC lang entries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.adv_common.dictionary import add_pair, ambiguous_translations
from gspecific.ballade.text_layout import EXPLICIT_TOKEN, HALF_SPACE_TOKEN, NOOP_TOKEN


FORMAT = "maria-adv98-script-lang-v1"
DEFAULT_WORKSPACE = Path(r"C:\work_han\workspace4")


def semantic_translation(value: str) -> str:
    """Remove byte-layout tokens when sharing a translation between files."""
    return EXPLICIT_TOKEN.sub(
        lambda match: "" if NOOP_TOKEN.fullmatch(match.group()) else (match.group() if HALF_SPACE_TOKEN.fullmatch(match.group()) else match.group(1)), value
    )


def build_dictionary(paths: list[Path]) -> tuple[dict, int, int, int]:
    dictionary: dict = {}
    entries = translated = kept = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != FORMAT:
            raise ValueError(f"unexpected lang format: {path}")
        for entry in document["entries"]:
            entries += 1
            value = entry.get("translation")
            if not isinstance(value, str):
                continue
            if value.strip():
                translated += 1
                if value == "@keep":
                    kept += 1
            add_pair(dictionary, entry.get("original_with_half_spaces", entry.get("original")), semantic_translation(value), f"{path.name}:{entry['id']}")
    return dictionary, entries, translated, kept


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE, help=f"default: {DEFAULT_WORKSPACE}")
    parser.add_argument("--output-dir", type=Path, help="default: workspace root")
    parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="replace existing generated dictionaries (default: enabled)",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source = workspace / "script-pc98" / "MES"
    paths = sorted(source.glob("*_lang.json"))
    if not paths:
        parser.error(f"no *_lang.json files found: {source}")
    output = args.output_dir.resolve() if args.output_dir else workspace
    targets = (output / "dictionary.json", output / "annoying.json")
    if not args.force:
        existing = [str(path) for path in targets if path.exists()]
        if existing:
            parser.error(f"output already exists (--no-force): {', '.join(existing)}")

    dictionary, entries, translated, kept = build_dictionary(paths)
    conflicts = ambiguous_translations(dictionary)
    mixed = sum("" in entry["translated"] and entry["count"] > 1 for entry in dictionary.values())
    output.mkdir(parents=True, exist_ok=True)
    write_json(targets[0], dictionary)
    write_json(targets[1], conflicts)
    print(f"lang files: {len(paths)}; entries: {entries}; translated: {translated}; @keep: {kept}")
    print(f"dictionary keys: {len(dictionary)}; conflicting keys: {len(conflicts)}; mixed blank/translated: {mixed}")
    print(f"wrote {targets[0]} and {targets[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
