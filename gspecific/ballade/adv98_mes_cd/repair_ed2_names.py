"""Resolve Ballade CD ED2 name calls using the ED3 definitions beside it."""

import argparse
from collections import defaultdict
from pathlib import Path

from gspecific.ballade.inline_names import literal_name_catalog, merge_inline_names
from gspecific.ballade.speaker_groups import macro_id

from .common import Paths, read_json, write_json


def repair(workspace: Path):
    paths = Paths(workspace.resolve())
    directory = paths.scripts / "HD/MARIA21/MARIA.045"
    ed2_info_path = directory / "ED2.MES_info.json"
    ed2_lang_path = directory / "ED2.MES_lang.json"
    ed3_info_path = directory / "ED3.MES_info.json"
    ed3_lang_path = directory / "ED3.MES_lang.json"
    if not all(path.is_file() for path in (ed2_info_path, ed2_lang_path,
                                          ed3_info_path, ed3_lang_path)):
        return 0, 0
    info, lang = read_json(ed2_info_path), read_json(ed2_lang_path)
    unresolved = {macro_id(record, "BA") for record in info["records"]
                  if record.get("type") == "command"}
    if not unresolved.intersection({12, 13}):
        return 0, 0
    ed3_info, ed3_lang = read_json(ed3_info_path), read_json(ed3_lang_path)
    catalog = literal_name_catalog([ed3_info])
    catalog["ED2"] = catalog["ED3"]
    translations = {("ED3.MES", entry["offset"]): entry.get("translation", "")
                    for entry in ed3_lang["entries"]}
    info, lang, converted = merge_inline_names(info, lang, catalog, translations)

    hd_root = paths.root / "script-pc98/MES"
    hd_info, hd_lang = (read_json(hd_root / "ED2.MES_info.json"),
                        read_json(hd_root / "ED2.MES_lang.json"))
    hd_records = {record["offset"]: record for record in hd_info["records"]
                  if record.get("type") == "text"}
    cd_records = {record["offset"]: record for record in info["records"]
                  if record.get("type") == "text"}
    donors = defaultdict(set)
    for entry in hd_lang["entries"]:
        translation = entry.get("translation", "")
        if translation and translation != "@keep":
            donors[(entry["original"], hd_records[entry["offset"]]["raw_hex"])].add(translation)
    imported = 0
    for entry in lang["entries"]:
        if entry.get("translation") and not entry.get("status", "").startswith("incomplete:"):
            continue
        choices = donors.get((entry["original"], cd_records[entry["offset"]]["raw_hex"]), set())
        if len(choices) == 1:
            entry["translation"] = next(iter(choices))
            entry["status"] = "translated"
            imported += 1
    if converted or imported:
        write_json(ed2_info_path, info)
        write_json(ed2_lang_path, lang)
    return converted, imported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    converted, imported = repair(args.workspace)
    from .annotate_hd_matches import annotate
    annotate(args.workspace)
    print(f"ED2 name calls: {converted}; HD translations imported: {imported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
