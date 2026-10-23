"""Join inline name calls into editable text while preserving their bytes."""

from collections import Counter
from copy import deepcopy
from pathlib import Path
import re

from .speaker_groups import macro_id


NAME_TOKEN = re.compile(r"\{이름:([^{}]+)\}")
GAIJI_TOKEN = re.compile(r"\{외자:([0-9A-F]{4})\}")
RAW_TOKEN = re.compile(r"\{원문:([0-9A-F]{5})\}")
INLINE_TOKEN = re.compile(r"\{이름:[^{}]+\}|\{외자:[0-9A-F]{4}\}|\{원문:[0-9A-F]{5}\}")


def literal_name_catalog(documents: list[dict]) -> dict:
    catalog = {}
    for info in documents:
        source = Path(info.get("source", "")).name
        chapter = source.split("_", 1)[0].split(".", 1)[0]
        records = info["records"]
        for index, record in enumerate(records[:-3]):
            definition = macro_id(record, "B9")
            opening, name, closing = records[index + 1:index + 4]
            if definition is not None and opening.get("value") == "BOUNDARY_A2" and name.get("type") == "text" and not name.get("inline_macros") and closing.get("value") == "BOUNDARY_A3":
                catalog.setdefault(chapter, {}).setdefault(definition, []).append((source, name))
    return catalog


def merge_inline_names(info: dict, lang: dict, catalog: dict | None = None,
                       translations: dict | None = None) -> tuple[dict, dict, int]:
    info, lang = deepcopy(info), deepcopy(lang)
    catalog = catalog or literal_name_catalog([info])
    source_name = Path(info.get("source", "")).name
    chapter = source_name.split("_", 1)[0].split(".", 1)[0]
    names = catalog.get(chapter, {})
    entries = {entry["offset"]: entry for entry in lang["entries"]}
    records = info["records"]
    converted = 0
    for index, record in enumerate(records):
        call_id = macro_id(record, "BA")
        definitions = names.get(call_id, []) if call_id not in (18, 19) else []
        local_definitions = [(file, item) for file, item in definitions if file == source_name]
        definitions = local_definitions or definitions
        resolved = {item["original"] for _, item in definitions}
        following = records[index + 1] if index + 1 < len(records) else {}
        if len(resolved) != 1 or macro_id(following, "BA") == 19:
            continue
        arguments = record.get("arguments", [])
        raw = bytes.fromhex(record["opcode"]) + b"".join(bytes.fromhex(arg["raw_hex"]) for arg in arguments)
        start = int(record["offset"], 16)
        if len(arguments) != 1:
            continue
        definition_file, definition = next(((file, item) for file, item in definitions if file == source_name), definitions[0])
        name_entry = entries.get(definition["offset"], {}) if definition_file == source_name else {}
        name_translation = name_entry.get("translation", "")
        if translations is not None:
            name_translation = translations.get((definition_file, definition["offset"]), name_translation)
        translated_name = definition["original"] if name_translation in ("", "@keep") else name_translation
        original_label = definition["original"].strip() if definition["original"].strip() and not any(c in definition["original"] for c in "{}") else str(call_id)
        translated_label = translated_name.strip() if translated_name.strip() and not any(c in translated_name for c in "{}") else str(call_id)
        token = f"{{이름:{translated_label}}}"
        original_token = f"{{이름:{original_label}}}"
        macro = {"token": token, "id": call_id, "offset": record["offset"], "raw_hex": raw.hex(" ").upper(),
                 "original_token": original_token,
                 "definition_file": definition_file, "definition_offset": definition["offset"],
                 "original_name": definition["original"],
                 "translated_name": translated_name}
        records[index] = {"type": "text", "offset": record["offset"], "end": f"{start + len(raw) - 1:05X}",
                          "raw_hex": raw.hex(" ").upper(), "original": original_token,
                          "encodings": ["ballade-name-macro"], "translation_candidate": True, "inline_macros": [macro]}
        entries[record["offset"]] = {"id": f'text:{record["offset"]}', "offset": record["offset"],
                                     "original": original_token, "translation": token, "status": "translated"}
        converted += 1
    lang["entries"] = sorted(entries.values(), key=lambda entry: int(entry["offset"], 16))
    from .merge_special_text import migrate_pair

    info, lang, _ = migrate_pair(info, lang)
    return info, lang, converted


def refresh_inline_names(info: dict, lang: dict, script_root: Path) -> None:
    """Read current macro name translations without writing the JSON files."""
    import json

    if not any(record.get("inline_macros") for record in info["records"]):
        return
    source_name = Path(info["source"]).name
    documents = {source_name: lang}
    for record in info["records"]:
        for macro in record.get("inline_macros", []):
            filename = macro["definition_file"]
            if Path(filename).name != filename:
                raise ValueError(f"invalid name definition filename: {filename}")
            if filename not in documents:
                documents[filename] = json.loads((script_root / f"{filename}_lang.json").read_text(encoding="utf-8"))
            definition = next((entry for entry in documents[filename]["entries"] if entry["offset"] == macro["definition_offset"]), None)
            if definition is None or definition["original"] != macro["original_name"]:
                raise ValueError(f"name definition changed: {filename}:{macro['definition_offset']}")
            translation = definition.get("translation", "")
            if not isinstance(translation, str):
                raise ValueError(f"name translation is not text: {filename}:{macro['definition_offset']}")
            macro["translated_name"] = macro["original_name"] if translation in ("", "@keep") else translation


def encode_inline_names(text: str, record: dict, encode_text) -> bytes:
    macros = record.get("encoding_macros", record.get("inline_macros", []))
    expected = Counter(macro["token"] for macro in macros)
    matches = list(INLINE_TOKEN.finditer(text))
    preserved_parts = {part["token"]: part for part in record.get("preserved_text", [])}
    actual = Counter(match.group() for match in NAME_TOKEN.finditer(text))
    hidden_calls = set()
    for match in RAW_TOKEN.finditer(text):
        part = preserved_parts.get(match.group())
        if part is None:
            raise ValueError("unknown original-text token for this record")
        start = int(part["offset"], 16)
        end = start + len(bytes.fromhex(part["raw_hex"]))
        for macro in macros:
            if start <= int(macro["offset"], 16) < end:
                actual[macro["token"]] += 1
                hidden_calls.add(macro["offset"])
    if actual != expected:
        raise ValueError("inline name tokens missing, duplicated, or unknown")
    calls = {}
    preserved = {part["token"]: bytes.fromhex(part["raw_hex"]) for part in record.get("preserved_text", [])}
    for macro in macros:
        if macro["offset"] not in hidden_calls:
            calls.setdefault(macro["token"], []).append(bytes.fromhex(macro["raw_hex"]))
    result = bytearray()
    cursor = 0
    for match in matches:
        result.extend(encode_text(text[cursor:match.start()]))
        if RAW_TOKEN.fullmatch(match.group()):
            if match.group() not in preserved:
                raise ValueError("unknown original-text token for this record")
            result.extend(preserved[match.group()])
        elif GAIJI_TOKEN.fullmatch(match.group()):
            if match.group() not in record["original"]:
                raise ValueError("unknown gaiji token for this record")
            result.extend(bytes.fromhex(GAIJI_TOKEN.fullmatch(match.group()).group(1)))
        else:
            result.extend(calls[match.group()].pop(0))
        cursor = match.end()
    result.extend(encode_text(text[cursor:]))
    return bytes(result)


def name_widths(record: dict, entries: dict, translated: bool) -> dict[str, int]:
    widths = {}
    macros = record.get("encoding_macros", record.get("inline_macros", [])) if translated else record.get("inline_macros", [])
    for macro in macros:
        name = macro["original_name"]
        if translated:
            entry = entries.get(macro["definition_offset"])
            if entry is not None and entry.get("original") == name:
                value = entry.get("translation", "")
                name = name if value in ("", "@keep") else value
            else:
                name = macro["translated_name"]
        widths[macro["token"]] = sum(character != "」" for character in name)
        widths[macro["original_token"]] = sum(character != "」" for character in name)
    for part in record.get("preserved_text", []):
        value = part["original"]
        widths[part["token"]] = sum(character != "」" for character in value) + sum(
            widths.get(match.group(), 0) - len(match.group()) for match in INLINE_TOKEN.finditer(value)
        )
    return widths


def prepare_name_moves(info: dict, lang: dict, *, validate: bool = True, equivalent=None) -> None:
    """Allow name calls to move among text records separated only by A5.

    Source metadata stays intact; encoding_macros is an in-memory assignment.
    Commands, end markers and boundaries stop each movable span.
    """
    entries = {entry["offset"]: entry for entry in lang["entries"]}
    scopes = []
    pending = []
    for record in info["records"]:
        if record["type"] == "text" and "ascii" not in record.get("encodings", []):
            pending.append(record)
        elif record.get("value") != "CONTROL_A5":
            if pending:
                scopes.append(pending)
            pending = []
    if pending:
        scopes.append(pending)
    for scope in scopes:
        macros = [macro for record in scope for macro in record.get("inline_macros", [])]
        expected = Counter(macro["token"] for macro in macros)
        required = Counter(
            macro["token"] for macro in macros
            if macro.get("original_name") != "{외자:EBE9}" * 3
            or macro.get("translated_name") != "{외자:EBE9}" * 3
        )
        actual = Counter()
        held = set()
        changed = []
        for record in scope:
            value = entries.get(record["offset"], {}).get("translation", "")
            if not isinstance(value, str):
                raise ValueError(f'{record["offset"]}: translation is not text')
            keep = not value or value == "@keep" or value == record["original"] or (equivalent is not None and equivalent(record["original"], value))
            assigned = []
            if keep:
                assigned = record.get("inline_macros", [])[:]
            else:
                actual.update(match.group() for match in NAME_TOKEN.finditer(value))
                for match in RAW_TOKEN.finditer(value):
                    part = next((part for part in record.get("preserved_text", []) if part["token"] == match.group()), None)
                    if part is None:
                        continue  # Per-record token validation gives the detailed error.
                    start = int(part["offset"], 16)
                    end = start + len(bytes.fromhex(part["raw_hex"]))
                    assigned.extend(macro for macro in macros if start <= int(macro["offset"], 16) < end)
                changed.append((record, value))
            actual.update(macro["token"] for macro in assigned)
            held.update(macro["offset"] for macro in assigned)
            record["encoding_macros"] = assigned
        if validate and (any(actual[token] < count for token, count in required.items())
                         or any(count > expected[token] for token, count in actual.items())):
            raise ValueError(f'{scope[0]["offset"]}: inline name tokens missing, duplicated, or unknown in text/A5 span')
        available = {}
        for macro in macros:
            if macro["offset"] not in held:
                available.setdefault(macro["token"], []).append(macro)
        for record, value in changed:
            for match in NAME_TOKEN.finditer(value):
                candidates = available.get(match.group(), [])
                if candidates:
                    record["encoding_macros"].append(candidates.pop(0))
