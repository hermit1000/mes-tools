"""Migrate existing Ballade info/lang pairs without discarding translations."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .speaker_groups import annotate_speakers, chapter_macros
from .special_text import SPECIAL_TEXT_CODES, gaiji_text, merge_special_text
from .text_layout import annotate_layout
from .inline_names import GAIJI_TOKEN, NAME_TOKEN, RAW_TOKEN, literal_name_catalog, merge_inline_names


def migrate_pair(info: dict, lang: dict) -> tuple[dict, dict, int]:
    special_characters = {value for value in SPECIAL_TEXT_CODES.values() if len(value) == 1}
    def only_special(text: str) -> bool:
        return set(NAME_TOKEN.sub("", GAIJI_TOKEN.sub("", text))).issubset(special_characters)
    records, sources = merge_special_text(info["records"])
    info, lang = deepcopy(info), deepcopy(lang)
    old_entries = {entry["offset"]: entry for entry in lang["entries"]}
    consumed = {part["offset"] for parts in sources.values() for part in parts}
    entries = {offset: entry for offset, entry in old_entries.items() if offset not in consumed}
    for record in records:
        parts = sources.get(record["offset"])
        if parts is None:
            continue
        translations = []
        changed = any(
            part["type"] == "text" and old_entries.get(part["offset"], {}).get("translation", "")
            not in ("", "@keep", part["original"])
            for part in parts
        )
        for part in parts:
            if part["type"] == "gaiji":
                translations.append(gaiji_text(part["raw_hex"].replace(" ", "").upper()))
                continue
            entry = old_entries.get(part["offset"])
            translation = entry.get("translation", "") if entry is not None else ""
            keep = translation in ("", "@keep", part["original"])
            if changed and keep and not only_special(part["original"]):
                token = f'{{원문:{part["offset"]}}}'
                record.setdefault("preserved_text", []).append({"token": token, "offset": part["offset"],
                                                               "original": part["original"], "raw_hex": part["raw_hex"]})
                translations.append(token)
            else:
                translations.append(part["original"] if keep else translation)
        existing = next((old_entries[part["offset"]] for part in parts if part["offset"] in old_entries), {})
        entry = {key: value for key, value in existing.items() if key != "speaker_group"}
        untranslated = any(part["type"] == "text" and not only_special(part["original"])
                           and old_entries.get(part["offset"], {}).get("translation", "") == ""
                           for part in parts)
        entry.update(id=f'text:{record["offset"]}', offset=record["offset"], original=record["original"],
                     translation="".join(translations) if changed else "" if untranslated else "@keep",
                     status="translated" if changed else "incomplete: untranslated" if untranslated else "passed")
        first_edges = old_entries.get(parts[0]["offset"], {}).get("ascii_half_space_edges", {})
        last_edges = old_entries.get(parts[-1]["offset"], {}).get("ascii_half_space_edges", {})
        if first_edges or last_edges:
            left, right = first_edges.get("left", 0), last_edges.get("right", 0)
            entry["ascii_half_space_edges"] = {"left": left, "right": right}
            token = "{반각공백}"
            entry["original_with_half_spaces"] = token * left + record["original"] + token * right
        if RAW_TOKEN.search(entry["translation"]):
            entry["status"] = "incomplete: original text preserved"
        entries[record["offset"]] = entry
    for record in records:
        if record["type"] == "text" and record.get("translation_candidate") and record["original"].strip() and record["offset"] not in entries:
            entries[record["offset"]] = {"id": f'text:{record["offset"]}', "offset": record["offset"],
                                         "original": record["original"], "translation": "",
                                         "status": "incomplete: untranslated"}
    info["records"] = records
    info["text_record_count"] = sum(record["type"] == "text" for record in records)
    info["translation_candidate_count"] = sum(record["type"] == "text" and record.get("translation_candidate", False) and bool(record["original"].strip()) for record in records)
    info["gaiji_count"] = sum(record["type"] == "gaiji" for record in records)
    lang["entries"] = sorted(entries.values(), key=lambda entry: int(entry["offset"], 16))
    annotate_layout(info, lang)
    return info, lang, len(sources)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="write; default: review only")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    root = workspace / "script-pc98/MES"
    documents = {}
    planned = []
    pairs = []
    for info_path in sorted(root.glob("*_info.json")):
        lang_path = info_path.with_name(info_path.name.replace("_info.json", "_lang.json"))
        info = json.loads(info_path.read_text(encoding="utf-8"))
        lang = json.loads(lang_path.read_text(encoding="utf-8"))
        source = (workspace / "jpn-pc98" / info["source"]).read_bytes()
        if hashlib.sha256(source).hexdigest() != info["source_sha256"]:
            raise ValueError(f"source hash mismatch: {info_path}")
        updated_info, updated_lang, count = migrate_pair(info, lang)
        for record in updated_info["records"]:
            if record["type"] == "text":
                start, end = int(record["offset"], 16), int(record["end"], 16) + 1
                if source[start:end] != bytes.fromhex(record["raw_hex"]):
                    raise ValueError(f"record bytes mismatch: {info_path}:{start:05X}")
        documents[info_path.name] = updated_info
        pairs.append((info_path, lang_path, updated_info, updated_lang, count, info, lang))
    catalog = chapter_macros(list(documents.values()))
    name_catalog = literal_name_catalog(list(documents.values()))
    translations = {(Path(info["source"]).name, entry["offset"]): entry.get("translation", "")
                    for _, _, info, lang, _, _, _ in pairs for entry in lang["entries"]}
    name_count = 0
    restored_pairs = []
    for info_path, lang_path, info, lang, count, original_info, original_lang in pairs:
        info, lang, joined = merge_inline_names(info, lang, name_catalog, translations)
        name_count += joined
        restored_pairs.append((info_path, lang_path, info, lang, count, original_info, original_lang))
    catalog = chapter_macros([info for _, _, info, _, _, _, _ in restored_pairs])
    for info_path, lang_path, info, lang, count, original_info, original_lang in restored_pairs:
        annotate_speakers(info, lang, catalog)
        annotate_layout(info, lang)
        source = (workspace / "jpn-pc98" / info["source"]).read_bytes()
        for record in info["records"]:
            if record["type"] == "text":
                start, end = int(record["offset"], 16), int(record["end"], 16) + 1
                if source[start:end] != bytes.fromhex(record["raw_hex"]):
                    raise ValueError(f"merged bytes mismatch: {info_path}:{start:05X}")
        if info != original_info or lang != original_lang:
            planned.append((info_path, lang_path, info, lang, count))
    print(f'{len(planned)} files, {sum(item[4] for item in planned)} special-text runs, {name_count} inline name calls')
    if args.apply:
        for info_path, lang_path, info, lang, _ in planned:
            for path, document in ((info_path, info), (lang_path, lang)):
                path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
