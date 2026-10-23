"""Treat Ballade's identified dialogue gaiji as inline text."""

from __future__ import annotations

from copy import deepcopy


SPECIAL_TEXT_CODES = {"EC65": "～", "EC67": "」", "EC68": "‥", "EBE9": "{외자:EBE9}"}


def gaiji_text(code: str) -> str:
    return SPECIAL_TEXT_CODES.get(code, f"{{외자:{code}}}")


def merge_special_text(records: list[dict], protected_offsets: set[str] | None = None) -> tuple[list[dict], dict[str, list[dict]]]:
    """Merge contiguous editable text without crossing commands or unknown gaiji.

    Return the old records contributing to each changed text record so existing
    translations can be migrated without guessing their new offsets.
    """
    result = []
    protected_offsets = protected_offsets or set()
    sources: dict[str, list[dict]] = {}
    for original in records:
        record = deepcopy(original)
        code = record.get("raw_hex", "").replace(" ", "").upper()
        if record.get("type") == "gaiji":
            character = gaiji_text(code)
            record = {
                "type": "text", "offset": record["offset"],
                "end": f'{int(record["offset"], 16) + 1:05X}',
                "raw_hex": record["raw_hex"], "encodings": ["ballade-special-glyph"],
                "translation_candidate": True, "original": character,
            }
            sources[record["offset"]] = [original]
        editable = record.get("type") == "text" and "ascii" not in record.get("encodings", [])
        if editable and record.get("original", "").strip():
            record["translation_candidate"] = True
        previous = result[-1] if result else {}
        previous_editable = previous.get("type") == "text" and previous.get("translation_candidate") and "ascii" not in previous.get("encodings", [])
        special_encodings = {"ballade-special-glyph", "ballade-name-macro"}
        special = bool(special_encodings.intersection(record.get("encodings", []) + previous.get("encodings", [])))
        protected = record["offset"] in protected_offsets or previous.get("offset") in protected_offsets
        if editable and previous_editable and special and not protected and int(previous["end"], 16) + 1 == int(record["offset"], 16):
            sources.setdefault(previous["offset"], [previous.copy()])
            sources[previous["offset"]].extend(sources.pop(record["offset"], [original]))
            previous["end"] = record["end"]
            previous["raw_hex"] += " " + record["raw_hex"]
            previous["original"] += record["original"]
            previous["encodings"] = sorted(set(previous["encodings"] + record["encodings"]))
            if record.get("inline_macros"):
                previous["inline_macros"] = previous.get("inline_macros", []) + record["inline_macros"]
            if record.get("preserved_text"):
                previous["preserved_text"] = previous.get("preserved_text", []) + record["preserved_text"]
        else:
            result.append(record)
    return result, sources
