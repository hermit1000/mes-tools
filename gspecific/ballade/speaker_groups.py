"""Link Ballade dialogue text to separately stored speaker names."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def macro_id(record: dict, opcode: str) -> int | None:
    if record.get("opcode") != opcode:
        return None
    arguments = record.get("arguments", [])
    if arguments and isinstance(arguments[0].get("value"), int):
        return arguments[0]["value"]
    return None


def speaker_text(record: dict) -> str:
    text = record["original"]
    for macro in record.get("inline_macros", []):
        text = text.replace(macro["original_token"], macro["original_name"])
    return text.strip()


def chapter_macros(documents: list[dict]) -> dict[str, dict[int, list[tuple[str, dict]]]]:
    catalog: dict[str, dict[int, list[tuple[str, dict]]]] = {}
    for info in documents:
        source_name = Path(info["source"]).name
        chapter = source_name.split("_", 1)[0].split(".", 1)[0]
        records = info["records"]
        for index, record in enumerate(records):
            definition = macro_id(record, "B9")
            if definition is None:
                continue
            name = next(
                (item for item in records[index + 1:index + 3] if item.get("type") == "text"),
                None,
            )
            if name is not None:
                catalog.setdefault(chapter, {}).setdefault(definition, []).append((source_name, name))
    return catalog


def annotate_speakers(
    info: dict, lang: dict,
    catalog: dict[str, dict[int, list[tuple[str, dict]]]] | None = None,
) -> int:
    """Group text between BA 19 (speaker/body separator) and BA 18."""
    records = info["records"]
    entries = {entry["offset"]: entry for entry in lang["entries"]}
    for entry in entries.values():
        entry.pop("speaker_group", None)
    macros: dict[int, dict] = {}
    groups = []

    for index, record in enumerate(records):
        definition = macro_id(record, "B9")
        if definition is not None:
            name = next(
                (item for item in records[index + 1:index + 3] if item.get("type") == "text"),
                None,
            )
            if name is not None:
                macros[definition] = name

        if macro_id(record, "BA") != 19:
            continue
        previous = records[index - 1] if index else {}
        speaker_id = macro_id(previous, "BA")
        if speaker_id is not None:
            name = macros.get(speaker_id)
            speaker_source = "macro"
            source_file = None
            if name is None and catalog is not None and info["source"].upper().endswith(".MEC"):
                chapter = Path(info["source"]).name.split("_", 1)[0]
                definitions = catalog.get(chapter, {}).get(speaker_id, [])
                if len({speaker_text(item) for _, item in definitions}) == 1:
                    source_file, name = definitions[0]
                    speaker_source = "chapter_macro"
        elif previous.get("type") == "text":
            name = previous
            speaker_source = "literal"
            source_file = None
        else:
            name = None
            speaker_source = "unknown"
            source_file = None

        body_offsets = []
        for item in records[index + 1:]:
            called = macro_id(item, "BA")
            if item.get("opcode") == "A6" or called in (18, 19):
                break
            if item.get("type") == "text" and item.get("original", "").strip():
                body_offsets.append(item["offset"])

        group_id = f'dialogue:{record["offset"]}'
        speaker = speaker_text(name) if name else None
        group = {
            "id": group_id,
            "speaker": speaker,
            "speaker_source": speaker_source,
            "speaker_offset": name["offset"] if name else None,
            "body_offsets": body_offsets,
            "opening_quote": {"text": "「", "source": "BA19", "offset": record["offset"]},
        }
        record["display_prefix"] = "「"
        if speaker_id is not None:
            group["speaker_macro_id"] = speaker_id
        if source_file is not None:
            group["speaker_file"] = source_file
        groups.append(group)
        for offset in body_offsets:
            if offset in entries:
                entries[offset]["speaker_group"] = group_id

    lang["speaker_groups"] = groups
    return len(groups)


def annotate_directory(root: Path) -> tuple[int, int]:
    paths = sorted(root.glob("*_lang.json"))
    if not paths:
        raise FileNotFoundError(f"no lang JSON files found under {root}")

    documents = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("*_info.json"))
    }
    catalog = chapter_macros(list(documents.values()))
    from .inline_names import literal_name_catalog, merge_inline_names
    from .text_layout import annotate_layout

    name_catalog = literal_name_catalog(list(documents.values()))
    count = 0
    for path in paths:
        lang = json.loads(path.read_text(encoding="utf-8"))
        if lang.get("format") != "maria-adv98-script-lang-v1":
            raise ValueError(f"unexpected lang format: {path}")
        info_path = path.with_name(lang["source_info"])
        info = documents[info_path.name]
        info, lang, _ = merge_inline_names(info, lang, name_catalog)
        count += annotate_speakers(info, lang, catalog)
        annotate_layout(info, lang)
        info_path.write_text(
            json.dumps(info, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\r\n",
        )
        path.write_text(
            json.dumps(lang, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\r\n",
        )
    return count, len(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    root = args.workspace.resolve() / "script-pc98" / "MES"
    count, files = annotate_directory(root)
    print(f"annotated {count} speaker groups in {files} lang files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
