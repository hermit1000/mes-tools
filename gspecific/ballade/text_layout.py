"""Preserve explicit line breaks and compare source/translation row usage."""

from __future__ import annotations

import math
import re
from .inline_names import GAIJI_TOKEN, INLINE_TOKEN, NAME_TOKEN, name_widths, prepare_name_moves

FORCED_DBCS_TOKEN = re.compile(r"\{([^{}])\}")
NOOP_TOKEN = re.compile(r"\{채움\}")
HALF_SPACE_TOKEN = re.compile(r"\{반각공백\}")
EXPLICIT_TOKEN = re.compile(FORCED_DBCS_TOKEN.pattern + "|" + NOOP_TOKEN.pattern + "|" + HALF_SPACE_TOKEN.pattern)
DISPLAY_TOKEN = re.compile(INLINE_TOKEN.pattern + "|" + EXPLICIT_TOKEN.pattern)


DEFAULT_LINE_COLUMNS = 28
VISIBLE_GAIJI_COLUMNS = {"{외자:EC6A}": 1, "{외자:EC6B}": 1}


def default_token_width(token: str) -> float:
    if token in VISIBLE_GAIJI_COLUMNS:
        return VISIBLE_GAIJI_COLUMNS[token]
    if HALF_SPACE_TOKEN.fullmatch(token):
        return 0.5
    return 1 if FORCED_DBCS_TOKEN.fullmatch(token) else 0


def display_columns(text: str, token_widths: dict[str, int] | None = None) -> float:
    widths = token_widths or {}
    count = sum(character != "」" for character in text)
    return count + sum(widths.get(match.group(), default_token_width(match.group())) - len(match.group()) for match in DISPLAY_TOKEN.finditer(text))


def strip_wrap_spaces(text: str, columns: int = DEFAULT_LINE_COLUMNS, start_column: int | None = 0,
                      token_widths: dict[str, int] | None = None,
                      unknown_tokens: set[str] | None = None) -> tuple[str, int | None]:
    """Drop spaces at automatic wrap boundaries, keeping internal spaces."""
    result = []
    column = start_column
    units = []
    cursor = 0
    for match in DISPLAY_TOKEN.finditer(text):
        units.extend((character, 0 if character == "」" else 1) for character in text[cursor:match.start()])
        token = match.group()
        width = None if token in (unknown_tokens or set()) or (GAIJI_TOKEN.fullmatch(token) and token not in VISIBLE_GAIJI_COLUMNS) else (token_widths or {}).get(token, default_token_width(token))
        units.append((match.group(), width))
        cursor = match.end()
    units.extend((character, 0 if character == "」" else 1) for character in text[cursor:])
    for character, width in units:
        if width is None:
            result.append(character)
            column = None
            continue
        if column is None:
            result.append(character)
            continue
        if character == "」":
            result.append(character)
            continue
        if column >= columns:
            if character in (" ", "\u3000"):
                continue
            column = 0
        result.append(character)
        total = column + width
        column = total - columns * math.ceil((total - columns) / columns) if total > columns else total
    return "".join(result), column


def translation_texts(info: dict, lang: dict) -> dict[str, str]:
    if not any("encoding_macros" in record for record in info["records"]):
        prepare_name_moves(info, lang, validate=False)
    entries = {entry["offset"]: entry for entry in lang["entries"]}
    texts = {}
    column = 0
    for record in info["records"]:
        if record["type"] != "text":
            column = 0
            continue
        entry = entries.get(record["offset"], {})
        translation = entry.get("translation", "")
        if not translation or translation == "@keep" or translation == record["original"]:
            if column is not None:
                if GAIJI_TOKEN.search(record["original"]):
                    column = None
                else:
                    total = column + display_columns(record["original"], name_widths(record, entries, False))
                    column = (total - 1) % DEFAULT_LINE_COLUMNS + 1 if total else 0
        elif "ascii" in record.get("encodings", []):
            texts[record["offset"]] = translation
            column = 0
        else:
            unknown = {part["token"] for part in record.get("preserved_text", []) if GAIJI_TOKEN.search(part["original"])}
            for macro in record.get("encoding_macros", record.get("inline_macros", [])):
                if GAIJI_TOKEN.search(macro["original_name"]) or GAIJI_TOKEN.search(macro["translated_name"]):
                    unknown.update((macro["token"], macro["original_token"]))
            texts[record["offset"]], column = strip_wrap_spaces(translation, start_column=column,
                                                              token_widths=name_widths(record, entries, True),
                                                              unknown_tokens=unknown)
    return texts


def line_breaks(records: list[dict]) -> list[dict]:
    pending = []
    known_start = False
    lines = []
    for record in records:
        if record["type"] in ("text", "gaiji"):
            pending.append(record)
        elif record.get("value") == "CONTROL_A5":
            if pending:
                lines.append({
                    "break_after": "A5", "break_offset": record["offset"],
                    "max_columns": DEFAULT_LINE_COLUMNS,
                    "line_offsets": [part["offset"] for part in pending],
                    "position_known": known_start,
                })
            pending = []
            known_start = True
        else:
            pending = []
            arguments = record.get("arguments", [])
            known_start = (
                record.get("opcode") == "BA" and bool(arguments)
                and arguments[0].get("value") == 19
            ) or record.get("name") == "F6_0B_AND_CURSOR_RESET"
    return lines


def reviewed_lines(info: dict, lang: dict) -> list[dict]:
    prepare_name_moves(info, lang, validate=False)
    entries = {entry["offset"]: entry for entry in lang["entries"]}
    records = {record["offset"]: record for record in info["records"]}
    effective = translation_texts(info, lang)
    result = []
    for line in line_breaks(info["records"]):
        original_columns = translated_columns = 0
        widths_known = True
        for offset in line["line_offsets"]:
            record = records[offset]
            if record["type"] == "gaiji" or "ascii" in record.get("encodings", []):
                widths_known = False
                continue
            if GAIJI_TOKEN.search(record["original"]):
                widths_known = False
            for macro in record.get("inline_macros", []):
                if GAIJI_TOKEN.search(macro["original_name"]) or GAIJI_TOKEN.search(macro["translated_name"]):
                    widths_known = False
            original_columns += display_columns(record["original"], name_widths(record, entries, False))
            translated_columns += display_columns(effective.get(offset, record["original"]), name_widths(record, entries, True))
            if any(match.group() not in name_widths(record, entries, True) for match in NAME_TOKEN.finditer(effective.get(offset, record["original"]))):
                widths_known = False
        original_rows = max(1, math.ceil(original_columns / line["max_columns"]))
        translated_rows = max(1, math.ceil(translated_columns / line["max_columns"]))
        known = line["position_known"] and widths_known
        status = "unknown_position" if not known else "overflow" if translated_rows > original_rows else "ok"
        result.append({**line, "original_columns": original_columns,
                       "translated_columns": translated_columns,
                       "original_rows": original_rows, "translated_rows": translated_rows,
                       "max_rows": original_rows if known else None, "check_status": status})
    return result


def annotate_layout(info: dict, lang: dict) -> None:
    entries = {entry["offset"]: entry for entry in lang["entries"]}
    for entry in entries.values():
        entry.pop("layout", None)
    lines = reviewed_lines(info, lang)
    info["line_breaks"] = line_breaks(info["records"])
    for record in info["records"]:
        if record.get("value") == "CONTROL_A5":
            record["display"] = "{줄바꿈:A5}"
    for line in lines:
        for offset in reversed(line["line_offsets"]):
            if offset in entries:
                entries[offset]["layout"] = dict(line)
                break
    for record in info["records"]:
        record.pop("encoding_macros", None)


def layout_issues(info: dict, lang: dict) -> list[dict]:
    return [line for line in reviewed_lines(info, lang) if line["check_status"] == "overflow"]


def validate_layout(info: dict, lang: dict, filename: str) -> None:
    issues = layout_issues(info, lang)
    if issues:
        issue = issues[0]
        raise ValueError(
            f'{filename}:{issue["line_offsets"][0]}: A5 row overflow '
            f'original {issue["original_rows"]} rows ({issue["original_columns"]} columns) -> '
            f'translation {issue["translated_rows"]} rows ({issue["translated_columns"]} columns) '
            f'at {issue["break_offset"]}'
        )
