"""Extract Ballade CD containers and make separate CD info/lang JSON files."""

import argparse
from collections import defaultdict
from pathlib import Path
import re

from gspecific.ballade.decode_scripts import decode_file, write_json
from gspecific.ballade.speaker_groups import annotate_directory

from .common import Paths, read_json, selected
from .containers import extract


RAW_TOKEN = re.compile(r"\{원문:[0-9A-F]{5}\}")
NAME_TOKEN = re.compile(r"\{이름:[^{}]+\}")
GAIJI_TOKEN = re.compile(r"\{외자:[0-9A-F]{4}\}")


def decode_cd(workspace: Path, names=None, refresh_unpacked=False, force=False):
    paths = Paths(workspace.resolve())
    if refresh_unpacked or not (paths.unpacked / "container-manifest.json").is_file():
        extract(paths.original, paths.unpacked)
    manifest = read_json(paths.unpacked / "container-manifest.json")
    resources = [Path(entry["unpacked_path"])
                 for container in manifest["containers"] for entry in container["entries"]
                 if Path(entry["name"]).suffix.upper() in {".MES", ".MEC"}]
    resources = [relative for relative in resources if selected(relative, names)]
    if not resources:
        raise ValueError("no matching CD MES/MEC resources")

    directories = set()
    count = 0
    for relative in resources:
        source = paths.unpacked / relative
        info_path = paths.scripts / relative.parent / f"{relative.name}_info.json"
        lang_path = paths.scripts / relative.parent / f"{relative.name}_lang.json"
        if not force and (info_path.exists() or lang_path.exists()):
            # Existing CD translation is user data. Never overwrite it implicitly.
            if not (info_path.exists() and lang_path.exists()):
                raise ValueError(f"incomplete JSON pair: {relative}")
            continue
        info, lang = decode_file(source, paths.unpacked)
        write_json(info_path, info)
        write_json(lang_path, lang)
        directories.add(lang_path.parent)
        count += 1

    # The chapter/name catalogue is local to each packed container.
    for directory in sorted(directories):
        annotate_directory(directory)
    from .repair_ed2_names import repair as repair_ed2_names
    repair_ed2_names(paths.root)
    reuse_hd_translations(paths, resources)
    from .repair_reuse import repair
    repair(paths.root)
    from .annotate_hd_matches import annotate
    annotate(paths.root)
    return count, len(resources)


def reuse_hd_translations(paths: Paths, resources: list[Path]):
    """Copy only unambiguous text with identical source bytes from the HD edition."""
    hd_root = paths.root / "script-pc98" / "MES"
    for relative in resources:
        hd_path = hd_root / f"{relative.name}_lang.json"
        cd_path = paths.scripts / relative.parent / f"{relative.name}_lang.json"
        if not hd_path.is_file() or not cd_path.is_file():
            continue
        hd = read_json(hd_path)
        cd = read_json(cd_path)
        hd_info = read_json(hd_root / f"{relative.name}_info.json")
        cd_info_path = paths.scripts / relative.parent / f"{relative.name}_info.json"
        cd_info = read_json(cd_info_path)
        hd_records = {record["offset"]: record for record in hd_info["records"]
                      if record.get("type") == "text"}
        cd_records = {record["offset"]: record for record in cd_info["records"]
                      if record.get("type") == "text"}
        donors = defaultdict(set)
        for entry in hd["entries"]:
            translation = entry.get("translation", "")
            if translation and translation != "@keep":
                record = hd_records[entry["offset"]]
                donors[(entry["original"], record["raw_hex"])].add(translation)
        changed = False
        for entry in cd["entries"]:
            if entry.get("translation"):
                continue
            record = cd_records[entry["offset"]]
            choices = donors.get((entry["original"], record["raw_hex"]), set())
            if len(choices) == 1:
                translation = next(iter(choices))
                allowed_raw = {part["token"] for part in record.get("preserved_text", [])}
                if any(token not in allowed_raw for token in RAW_TOKEN.findall(translation)):
                    continue
                allowed_names = {macro["token"] for macro in record.get("inline_macros", [])}
                allowed_names.update(
                    f"{{이름:{definition.get('translation', '').strip()}}}"
                    for macro in record.get("inline_macros", [])
                    if macro["definition_file"] == relative.name
                    for definition in cd["entries"]
                    if definition["offset"] == macro["definition_offset"]
                    and definition.get("translation")
                )
                if any(token not in allowed_names for token in NAME_TOKEN.findall(translation)):
                    continue
                allowed_gaiji = set(GAIJI_TOKEN.findall(entry["original"]))
                if any(token not in allowed_gaiji for token in GAIJI_TOKEN.findall(translation)):
                    continue
                entry["translation"] = translation
                entry["status"] = "translated"
                changed = True
        if changed:
            definitions = {entry["offset"]: entry for entry in cd["entries"]}
            for record in cd_info["records"]:
                for macro in record.get("inline_macros", []):
                    if macro["definition_file"] != relative.name:
                        continue
                    definition = definitions.get(macro["definition_offset"])
                    if definition is None:
                        continue
                    name = definition.get("translation") or macro["original_name"]
                    if name != macro["original_name"]:
                        macro["translated_name"] = name
                        macro["token"] = f"{{이름:{name.strip()}}}"
            write_json(cd_info_path, cd_info)
            write_json(cd_path, cd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--files", nargs="+", help="MES/MEC basenames or container-relative paths")
    parser.add_argument("--refresh-unpacked", action="store_true")
    parser.add_argument("--force", action="store_true", help="regenerate CD JSON; overwrites CD translations")
    args = parser.parse_args()
    created, found = decode_cd(args.workspace, args.files, args.refresh_unpacked, args.force)
    print(f"CD scripts: {found} selected, {created} new JSON pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
