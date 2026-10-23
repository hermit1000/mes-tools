"""Recover HD translations whose inline-token metadata was absent in CD JSON."""

import argparse
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import re

from gspecific.ballade.encode_mes import DEFAULT_FONT_TABLE, encode_file

from .common import Paths, read_json, write_json


RAW_TOKEN = re.compile(r"\{원문:[0-9A-F]{5}\}")
NAME_TOKEN = re.compile(r"\{이름:[^{}]+\}")
GAIJI_TOKEN = re.compile(r"\{외자:[0-9A-F]{4}\}")
COMPACT_REMAP = Path(__file__).resolve().parents[1] / "maria_compact_font_mapping_top67.json"


def repair(workspace: Path):
    paths = Paths(workspace.resolve())
    hd_root = paths.root / "script-pc98/MES"
    repaired = []
    skipped = []
    for lang_path in sorted(paths.scripts.rglob("*_lang.json")):
        name = lang_path.name[:-10]
        info_path = lang_path.with_name(name + "_info.json")
        hd_lang_path = hd_root / lang_path.name
        hd_info_path = hd_root / info_path.name
        if not hd_lang_path.is_file():
            continue
        lang = read_json(lang_path)
        info = read_json(info_path)
        hd_lang = read_json(hd_lang_path)
        hd_info = read_json(hd_info_path)
        source = paths.unpacked / info["source"]
        source_bytes = source.read_bytes()
        records = {record["offset"]: record for record in info["records"]
                   if record.get("type") == "text"}
        hd_records = {record["offset"]: record for record in hd_info["records"]
                      if record.get("type") == "text"}
        donors = defaultdict(list)
        for entry in hd_lang["entries"]:
            translation = entry.get("translation", "")
            if translation and translation != "@keep":
                record = hd_records[entry["offset"]]
                donors[(entry["original"], record["raw_hex"])].append((translation, record))
        for entry in lang["entries"]:
            if entry.get("translation"):
                continue
            record = records[entry["offset"]]
            candidates = donors.get((entry["original"], record["raw_hex"]), [])
            if len({text for text, _ in candidates}) != 1:
                continue
            translation, hd_record = candidates[0]
            needed_raw = set(RAW_TOKEN.findall(translation))
            needed_names = set(NAME_TOKEN.findall(translation))
            if not needed_raw and not needed_names:
                continue
            if any(token not in set(GAIJI_TOKEN.findall(entry["original"]))
                   for token in GAIJI_TOKEN.findall(translation)):
                continue
            old_entry = deepcopy(entry)
            old_record = deepcopy(record)
            try:
                preserved = {part["token"]: part for part in record.get("preserved_text", [])}
                for part in hd_record.get("preserved_text", []):
                    if part["token"] not in needed_raw or part["token"] in preserved:
                        continue
                    start = int(part["offset"], 16)
                    raw = bytes.fromhex(part["raw_hex"])
                    if not int(record["offset"], 16) <= start or start + len(raw) > int(record["end"], 16) + 1:
                        raise ValueError("preserved text lies outside CD record")
                    if source_bytes[start:start + len(raw)] != raw:
                        raise ValueError("preserved text bytes differ")
                    preserved[part["token"]] = part
                if not needed_raw.issubset(preserved):
                    raise ValueError("original-text token has no verified bytes")
                if preserved:
                    record["preserved_text"] = list(preserved.values())

                cd_macros = record.get("inline_macros", [])
                hd_macros = hd_record.get("inline_macros", [])
                if len(cd_macros) != len(hd_macros) or any(
                    (cd["id"], cd["offset"], cd["raw_hex"], cd["original_name"])
                    != (hd["id"], hd["offset"], hd["raw_hex"], hd["original_name"])
                    for cd, hd in zip(cd_macros, hd_macros)
                ):
                    raise ValueError("name call bytes or identity differ")
                for cd_macro, hd_macro in zip(cd_macros, hd_macros):
                    if hd_macro["token"] not in needed_names:
                        continue
                    definition_path = lang_path.with_name(cd_macro["definition_file"] + "_lang.json")
                    definition_lang = read_json(definition_path)
                    definition = next((item for item in definition_lang["entries"]
                                       if item["offset"] == cd_macro["definition_offset"]), None)
                    if definition is None or definition["original"] != cd_macro["original_name"]:
                        raise ValueError("CD name definition differs")
                    translated_name = definition.get("translation") or cd_macro["original_name"]
                    if translated_name.strip() != hd_macro["translated_name"].strip():
                        raise ValueError("CD name translation differs")
                    cd_macro["token"] = hd_macro["token"]
                    cd_macro["translated_name"] = translated_name
                if not needed_names.issubset({macro["token"] for macro in cd_macros}):
                    raise ValueError("name token has no verified call")

                entry["translation"] = translation
                entry["status"] = "translated"
                write_json(info_path, info)
                write_json(lang_path, lang)
                encode_file(source, info_path, lang_path, None, DEFAULT_FONT_TABLE,
                            compact_remap=COMPACT_REMAP)
            except (OSError, ValueError, KeyError) as error:
                entry.clear()
                entry.update(old_entry)
                record.clear()
                record.update(old_record)
                write_json(info_path, info)
                write_json(lang_path, lang)
                skipped.append({"file": info["source"], "id": entry["id"], "reason": str(error)})
                continue
            repaired.append({"file": info["source"], "id": entry["id"],
                             "tokens": sorted(needed_raw | needed_names)})
    report = {"format": "ballade-cd-token-reuse-repair-v1",
              "repaired": repaired, "skipped": skipped}
    write_json(paths.scripts / "token_reuse_repair_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = repair(args.workspace)
    print(f"repaired {len(report['repaired'])}; skipped {len(report['skipped'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
