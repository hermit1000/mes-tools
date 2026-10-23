"""Rank current literal translation glyphs, excluding inline code tokens."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .encode_mes import DEFAULT_FONT_TABLE, DEFAULT_WORKSPACE, display_text, load_maria_font_codes, same_display_text
from .inline_names import INLINE_TOKEN, refresh_inline_names
from .text_layout import EXPLICIT_TOKEN, translation_texts


FIRST_CODE = 0x2D
SLOT_COUNT = 67
DEFAULT_OUTPUT = Path(__file__).with_name("maria_compact_font_mapping_top67.json")


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")


def rank_translations(workspace: Path, font_table: Path) -> tuple[dict, dict]:
    table = json.loads(font_table.read_text(encoding="utf-8"))
    codes = load_maria_font_codes(font_table)
    drawable = {}
    for code, character in table.items():
        if len(code) == 4 and isinstance(character, str) and len(character) == 1:
            normalized = " " if character == "_" else display_text(character)
            drawable.setdefault(normalized, code)
    frequencies = Counter()
    excluded = Counter()
    files = []
    for path in sorted((workspace / "script-pc98/MES").glob("*_lang.json")):
        lang_bytes = path.read_bytes()
        lang = json.loads(lang_bytes.decode("utf-8"))
        info = json.loads(path.with_name(lang["source_info"]).read_text(encoding="utf-8"))
        refresh_inline_names(info, lang, path.parent)
        records = {record["offset"]: record for record in info["records"] if record["type"] == "text"}
        effective = translation_texts(info, lang)
        local = Counter()
        for entry in lang["entries"]:
            translation = entry.get("translation", "")
            if not translation or translation == "@keep" or same_display_text(entry["original"], translation):
                continue
            record = records[entry["offset"]]
            if "ascii" in record.get("encodings", []):
                continue
            # Names emit call bytes, gaiji emit preserved pairs, and raw tokens
            # emit source bytes. Their labels do not consume font-map slots.
            literal = EXPLICIT_TOKEN.sub("", INLINE_TOKEN.sub("", effective.get(entry["offset"], translation)))
            for character in display_text(literal):
                if character in drawable and codes.get(character) == drawable[character]:
                    local[character] += 1
                else:
                    excluded[character] += 1
        frequencies.update(local)
        files.append({"file": Path(info["source"]).name,
                      "lang_sha256": hashlib.sha256(lang_bytes).hexdigest(),
                      "candidate_occurrences": sum(local.values())})
    ranking = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))
    selected = ranking[:SLOT_COUNT]
    entries = []
    for rank, (character, frequency) in enumerate(selected, 1):
        code = FIRST_CODE + rank - 1
        sjis = bytes((0x82, code + 0x72))
        entries.append({"rank": rank, "character": character, "code": f"{code:02X}",
                        "source_sjis": sjis.hex().upper(), "source_character": sjis.decode("cp932"),
                        "frequency": frequency, "estimated_saved_bytes": frequency})
    mapping = {"format": "maria-adv98-one-byte-font-remap-v1",
               "description": "67 most frequent drawable literal glyphs in all current Ballade translations; inline code tokens excluded.",
               "source_code_range": {"first": "2D", "last": "6F", "note": "ADV98 compressed codes; source SJIS glyphs 829F through 82E1."},
               "ranking_rule": "Character occurrence count descending; Unicode character ascending on ties.",
               "scope": "All current translations. Tokens and preserved/private glyphs are excluded. Requires matching font BMP and re-encoding.",
               "entries": entries}
    stats = {"format": "ballade-compact-glyph-stats-v2", "files": files,
             "character_counts": dict(ranking), "excluded_character_counts": dict(excluded),
             "selected_slots": len(entries), "estimated_saved_bytes": sum(item[1] for item in selected)}
    return mapping, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--font-table", type=Path, default=DEFAULT_FONT_TABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats-output", type=Path)
    args = parser.parse_args()
    mapping, stats = rank_translations(args.workspace.resolve(), args.font_table.resolve())
    stats_path = args.stats_output or args.workspace / "ballade_compact_glyph_stats.json"
    write_json(args.output, mapping)
    write_json(stats_path, stats)
    print(f"ranked {len(stats['files'])} files; wrote {len(mapping['entries'])} glyphs to {args.output}")
    for entry in mapping["entries"]:
        if entry["character"] == "…":
            print(f"ellipsis: rank {entry['rank']}, frequency {entry['frequency']}, code {entry['code']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
