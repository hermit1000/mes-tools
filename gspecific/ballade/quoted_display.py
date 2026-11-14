"""Expose displayed quoted strings as ordinary editable text records."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

from modules.adv_common.mes_lexer import decode_mes
from .inline_names import GAIJI_TOKEN


NAME = re.compile(r"\{이름:([^{}]+)\}|\{대사끝\}")
INLINE = re.compile(NAME.pattern + "|" + GAIJI_TOKEN.pattern)


def promote_display_quotes(info: dict, lang: dict) -> None:
    names = {}
    for record in info["records"]:
        for macro in record.get("inline_macros", []):
            names.setdefault(macro["id"], macro)
    entries = lang["entries"]
    promoted = 0
    expanded = {}
    for index, record in enumerate(info["records"]):
        if record.get("type") != "quoted" or index == 0 or info["records"][index - 1].get("value") != "CONTROL_09":
            continue
        raw = bytes.fromhex(record["raw_hex"])
        if not raw.startswith(b'\x22') or not raw.endswith(b'\x0d\x22') or b'\x00' in raw:
            continue
        tokens = decode_mes(raw[1:-2])
        original = []
        macros = []
        valid = True
        for token_index, token in enumerate(tokens):
            if token["type"] == "argument":
                continue
            if token["type"] == "text":
                original.append(token["value"])
            elif token["type"] == "command" and bytes(token["bytes"]) == b'\xba' and token_index + 1 < len(tokens):
                argument = tokens[token_index + 1]
                if argument["type"] != "argument" or bytes(argument["bytes"])[:1] != b'\x28' or len(argument["bytes"]) != 2:
                    valid = False
                    break
                macro_id = argument["bytes"][1]
                known = names.get(macro_id)
                original_label = "{대사끝}" if macro_id == 18 else known["original_token"] if known else f"{{이름:{macro_id}}}"
                translated_label = "{대사끝}" if macro_id == 18 else known["token"] if known else original_label
                original.append(original_label)
                macros.append({"id": macro_id, "original_token": original_label,
                               "token": translated_label, "raw_hex": f"BA 28 {macro_id:02X}",
                               "width": len(known["translated_name"]) if known else 0})
            else:
                valid = False
                break
        if not valid:
            continue
        offset = record["offset"]
        if any(macro["id"] == 18 for macro in macros):
            body = raw[1:-2]
            pieces = body.split(b'\xba\x28\x12')
            originals = "".join(original).split("{대사끝}")
            if len(pieces) != len(originals):
                continue
            replacement = [{"type": "boundary", "offset": offset, "value": "QUOTED_OPEN", "raw_hex": "22"}]
            position = int(offset, 16) + 1
            macro_groups = []
            group = []
            for macro in macros:
                if macro["id"] == 18:
                    macro_groups.append(group)
                    group = []
                else:
                    group.append(macro)
            macro_groups.append(group)
            for part_index, (piece, original_text, part_macros) in enumerate(zip(pieces, originals, macro_groups)):
                part_offset = f"{position:05X}"
                replacement.append({"type": "text", "offset": part_offset,
                                    "end": f"{position + len(piece) - 1:05X}",
                                    "raw_hex": piece.hex(" ").upper(), "original": original_text,
                                    "encodings": ["quoted-display"], "translation_candidate": True,
                                    "quoted_part": True, "quoted_macros": part_macros})
                entries.append({"id": f"text:{part_offset}", "offset": part_offset,
                                "original": original_text, "translation": "",
                                "status": "incomplete: untranslated"})
                promoted += 1
                position += len(piece)
                if part_index < len(pieces) - 1:
                    replacement.append({"type": "boundary", "offset": f"{position:05X}",
                                        "value": "QUOTED_DIALOGUE_END", "raw_hex": "BA 28 12"})
                    position += 3
            replacement.append({"type": "boundary", "offset": f"{position:05X}",
                                "value": "QUOTED_CLOSE", "raw_hex": "0D 22"})
            expanded[index] = replacement
            continue
        if (Path(info["source"]).name.upper() == "512_18.MES" and offset == "01B60"
                and raw.startswith(b"\x22\x96\x6c\x38")):
            # The opening 22 is an 09 branch operand; only its body is display text.
            body_offset = int(offset, 16) + 1
            body = raw[1:-2]
            expanded[index] = [
                {"type": "argument", "offset": offset, "value": 0x22, "raw_hex": "22"},
                {"type": "text", "offset": f"{body_offset:05X}",
                 "end": f"{body_offset + len(body) - 1:05X}",
                 "raw_hex": body.hex(" ").upper(), "original": "".join(original),
                 "encodings": ["quoted-display"], "translation_candidate": True,
                 "quoted_part": True, "quoted_macros": macros},
                {"type": "control", "offset": f"{body_offset + len(body):05X}",
                 "value": "CONTROL_0D", "raw_hex": "0D 22"},
            ]
            entries.append({"id": f"text:{body_offset:05X}", "offset": f"{body_offset:05X}",
                            "original": "".join(original), "translation": "",
                            "status": "incomplete: untranslated"})
            promoted += 1
            continue
        record.update({"type": "text", "end": f"{int(offset, 16) + len(raw) - 1:05X}",
                       "original": "".join(original), "encodings": ["quoted-display"],
                       "translation_candidate": True, "quoted_macros": macros})
        record.pop("value", None)
        entries.append({"id": f"text:{offset}", "offset": offset, "original": record["original"],
                        "translation": "", "status": "incomplete: untranslated"})
        promoted += 1
    if expanded:
        info["records"] = [part for index, record in enumerate(info["records"])
                           for part in expanded.get(index, [record])]
    entries.sort(key=lambda entry: int(entry["offset"], 16))
    info["text_record_count"] += promoted
    info["translation_candidate_count"] += promoted


def encode_display_quote(text: str, record: dict, encode_text) -> bytes:
    macros = record["quoted_macros"]
    expected = Counter(macro["token"] for macro in macros)
    actual = Counter(match.group() for match in NAME.finditer(text))
    if any(actual[token] > expected[token] for token in actual):
        raise ValueError("quoted name tokens duplicated or unknown")
    calls = {}
    for macro in macros:
        calls.setdefault(macro["token"], []).append(bytes.fromhex(macro["raw_hex"]))
    parts = []
    cursor = 0
    for match in INLINE.finditer(text):
        literal = encode_text(text[cursor:match.start()])
        if any(byte in literal for byte in (0x00, 0x0D, 0x22)):
            raise ValueError("quoted translation contains delimiter")
        parts.append(literal)
        gaiji = GAIJI_TOKEN.fullmatch(match.group())
        if gaiji:
            if match.group() not in record["original"]:
                raise ValueError("unknown gaiji token for this record")
            parts.append(bytes.fromhex(gaiji.group(1)))
        else:
            parts.append(calls[match.group()].pop(0))
        cursor = match.end()
    literal = encode_text(text[cursor:])
    if any(byte in literal for byte in (0x00, 0x0D, 0x22)):
        raise ValueError("quoted translation contains delimiter")
    parts.append(literal)
    encoded = b''.join(parts)
    return encoded if record.get("quoted_part") else b'\x22' + encoded + b'\x0d\x22'


def refresh_quoted_names(info: dict, lang: dict, script_root: Path) -> None:
    definitions = {macro["id"]: macro for record in info["records"]
                   for macro in record.get("inline_macros", [])}
    documents = {Path(info["source"]).name: lang}
    for record in info["records"]:
        for macro in record.get("quoted_macros", []):
            if macro.get("fixed_token"):
                continue
            definition = definitions.get(macro["id"])
            if definition is None:
                continue
            filename = definition["definition_file"]
            if filename not in documents:
                documents[filename] = json.loads((script_root / f"{filename}_lang.json").read_text(encoding="utf-8"))
            entry = next(item for item in documents[filename]["entries"]
                         if item["offset"] == definition["definition_offset"])
            name = entry["translation"] if entry["translation"] not in ("", "@keep") else definition["original_name"]
            macro["token"] = f"{{이름:{name.strip()}}}"
            macro["width"] = len(name.strip())
