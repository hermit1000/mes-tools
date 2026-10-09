"""Migrate a game MES translation after a decoder update."""

import argparse
import json
from pathlib import Path

from modules.tools.migrate_ascii import prepare_migration


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=("dob1", "dob2"))
    parser.add_argument("source_mes", type=Path)
    parser.add_argument("info_json", type=Path)
    parser.add_argument("lang_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    old_info = json.loads(args.info_json.read_text(encoding="utf-8"))
    old_lang = json.loads(args.lang_json.read_text(encoding="utf-8"))
    if old_lang.get("source_info") != args.info_json.name:
        raise ValueError("lang references a different info file")
    if not all(str(d.get("format", "")).startswith(args.game + "-") for d in (old_info, old_lang)):
        raise ValueError("game and document formats differ")
    if args.game == "dob1":
        from gspecific.dob1.adv98_mes.decode_mes import decode_document
    else:
        from gspecific.dob2.adv98_mes.decode_mes import decode_document
    new_info = decode_document(args.source_mes, old_info["source"], structured_ascii=True)
    new_info["format"] = old_info["format"]
    info, lang, report = prepare_migration(args.source_mes.read_bytes(), old_info, old_lang, new_info)
    outputs = {"migration_report.json": report}
    if report["safe_to_write"]:
        outputs.update({args.info_json.name: info, args.lang_json.name: lang})
    if len({args.info_json.name, args.lang_json.name, "migration_report.json"}) != 3:
        raise ValueError("output filenames collide")
    if args.output_dir.resolve() in {args.info_json.resolve().parent, args.lang_json.resolve().parent}:
        raise ValueError("migration requires a separate output directory")
    for name in outputs:
        if (args.output_dir / name).exists():
            raise FileExistsError(args.output_dir / name)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, document in outputs.items():
        (args.output_dir / name).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"safe_to_write": report["safe_to_write"], "changed_ranges": len(report["changes"]),
                      "preserved": len(report["preserved"]), "review_required": len(report["review_required"])}))
    return 0 if report["safe_to_write"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
