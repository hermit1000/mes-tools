"""Shared ADV98 MES lexical decoder and readable records."""

from __future__ import annotations

import json
from typing import Any

COMMAND_NAMES = {
    0xA6: "SET_RECT",
    0xAA: "F6_0B_AND_CURSOR_RESET",
    0xB7: "DISPLAY_CONFIG",
    0xB9: "DEFINE_MACRO",
    0xBA: "CALL_BUILTIN",
    0xBB: "REPEAT_BLOCK",
    0xC9: "LOAD_GPC",
    0xCD: "GRAPH_OP",
    0xCF: "APPLY_GPC_OPTIONS",
    0xD0: "AUDIO",
    0xD1: "F3_STATE",
}

SPECIAL_SJIS = {
    0x8197: "CONTROL_FULLWIDTH_AT",
    0x8190: "CONTROL_FULLWIDTH_DOLLAR",
    0x816F: "BLOCK_OPEN",
    0x8170: "BLOCK_CLOSE",
}


from modules.adv_common.tokens import (
    is_sjis_lead, is_sjis_trail, decode_pair, make_token,
)


def decode_mes(
    data: bytes,
    parameter_controls: tuple[int, ...] = (0x08, 0x0C, 0x0D, 0x19),
    *, ascii_output: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0

    while offset < len(data):
        first = data[offset]
        second = data[offset + 1] if offset + 1 < len(data) else None

        # Opt-in for games with confirmed 21 <printable ASCII> 00 output.
        # Interpret at a lexical boundary, never by searching inside operands.
        if ascii_output and first == 0x21:
            end = data.find(b"\x00", offset + 1)
            if end >= 0 and all(0x20 <= value <= 0x7E for value in data[offset + 1:end]):
                result.append(make_token(offset, 1, data[offset:offset + 1], "control", "CONTROL_21"))
                if end > offset + 1:
                    raw = data[offset + 1:end]
                    result.append(make_token(offset + 1, len(raw), raw, "text", raw.decode("ascii"),
                                             encoding="ascii", display_text=True,
                                             syntax="ascii-output-nul"))
                result.append(make_token(end, 1, data[end:end + 1], "control", "CONTROL_00"))
                offset = end + 1
                continue

        previous = result[-1] if result else None
        if (
            previous
            and previous["type"] == "command"
            and previous["value"] == "AUDIO"
            and second is not None
            and (first | 0x20) == 0x73
            and (second | 0x20) == 0x65
        ):
            result.append(make_token(offset, 2, data[offset : offset + 2], "keyword", "se"))
            offset += 2
            continue

        if second is not None and first == 0xFF and second in (0xFE, 0xFF):
            name = "END_FFFF" if second == 0xFF else "END_FFFE"
            result.append(make_token(offset, 2, data[offset : offset + 2], "end", name))
            offset += 2
            continue

        if first == 0x22:
            end = data.find(b'"', offset + 1)
            closed = end >= 0
            if not closed:
                end = len(data)
            size = end - offset + (1 if closed else 0)
            content = data[offset + 1 : end].decode("cp932", errors="replace")
            result.append(
                make_token(
                    offset,
                    size,
                    data[offset : offset + size],
                    "quoted",
                    content,
                    closed=closed,
                )
            )
            offset += size
            continue

        if second is not None and is_sjis_lead(first) and is_sjis_trail(second):
            word = first << 8 | second
            text = decode_pair(first, second)
            if word in SPECIAL_SJIS:
                result.append(
                    make_token(
                        offset,
                        2,
                        data[offset : offset + 2],
                        "control",
                        SPECIAL_SJIS[word],
                        text=text,
                    )
                )
            else:
                result.append(
                    make_token(
                        offset,
                        2,
                        data[offset : offset + 2],
                        "text",
                        text,
                        encoding="shift_jis",
                    )
                )
            offset += 2
            continue

        if 0x2D <= first <= 0x7F:
            expanded = bytes((0x82, (first + 0x72) & 0xFF))
            result.append(
                make_token(
                    offset,
                    1,
                    data[offset : offset + 1],
                    "text",
                    expanded.decode("cp932", errors="replace"),
                    encoding="adv98-compressed-sjis",
                    expandedBytes=list(expanded),
                )
            )
            offset += 1
            continue

        if 0xA6 <= first <= 0xD8:
            result.append(
                make_token(
                    offset,
                    1,
                    data[offset : offset + 1],
                    "command",
                    COMMAND_NAMES.get(first, f"CMD_{first:02X}"),
                )
            )
            offset += 1
            continue

        if 0xA0 <= first <= 0xA4:
            result.append(
                make_token(offset, 1, data[offset : offset + 1], "boundary", f"BOUNDARY_{first:02X}")
            )
            offset += 1
            continue

        if first == 0xA5:
            result.append(make_token(offset, 1, data[offset : offset + 1], "control", "CONTROL_A5"))
            offset += 1
            continue

        # ADV98 message streams use 0x08/0x0C/0x0D/0x19 followed by a one-byte parameter
        # for internal display/control operations.  The parameter often falls
        # in the compressed-SJIS printable range; treating it as text produces
        # bogus trailing kana such as ``ぁ`` or ``っ`` after a sentence.
        if first in parameter_controls and second is not None:
            result.append(
                make_token(
                    offset,
                    2,
                    data[offset : offset + 2],
                    "control",
                    f"CONTROL_{first:02X}",
                    parameter=second,
                )
            )
            offset += 2
            continue

        if 0x23 <= first <= 0x27:
            result.append(
                make_token(
                    offset,
                    1,
                    data[offset : offset + 1],
                    "argument",
                    first - 0x23,
                    form="small-constant",
                )
            )
            offset += 1
            continue

        if first == 0x28 and second is not None:
            result.append(
                make_token(
                    offset,
                    2,
                    data[offset : offset + 2],
                    "argument",
                    second,
                    form="byte-constant",
                )
            )
            offset += 2
            continue

        if 0x29 <= first <= 0x2C and offset + 2 < len(data):
            packed = data[offset + 1] << 8 | data[offset + 2]
            kind = first - 0x29
            value = kind << 14 | packed >> 1
            result.append(
                make_token(
                    offset,
                    3,
                    data[offset : offset + 3],
                    "argument",
                    value,
                    form="tagged-reference",
                    kind=kind,
                    packed=packed,
                )
            )
            offset += 3
            continue

        name = "CONTROL_21" if first == 0x21 else f"CONTROL_{first:02X}"
        result.append(make_token(offset, 1, data[offset : offset + 1], "control", name))
        offset += 1

    return result


def format_text(tokens: list[dict[str, Any]]) -> str:
    lines = []
    for item in tokens:
        offset = f'{item["offset"]:05X}'
        raw = " ".join(f"{value:02X}" for value in item["bytes"]).ljust(12)
        value = item["value"]
        rendered = f"0x{value:04X}" if isinstance(value, int) else json.dumps(value, ensure_ascii=False)
        lines.append(f'{offset}  {raw}  {item["type"]:<9}  {rendered}')
    return "\n".join(lines)


def make_readable_records(tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    index = 0

    while index < len(tokens):
        current = tokens[index]

        if current["type"] == "text":
            group = [current]
            end = current["offset"] + current["size"]
            index += 1
            while index < len(tokens):
                candidate = tokens[index]
                if candidate["type"] != "text" or candidate["offset"] != end:
                    break
                group.append(candidate)
                end += candidate["size"]
                index += 1
            raw = [byte for item in group for byte in item["bytes"]]
            records.append(
                {
                    "type": "text",
                    "offset": f'{group[0]["offset"]:05X}',
                    "end": f"{end - 1:05X}",
                    "text": "".join(str(item["value"]) for item in group),
                    "raw_hex": " ".join(f"{byte:02X}" for byte in raw),
                    "encodings": sorted({item.get("encoding", "unknown") for item in group}),
                    "translation_candidate": len(group) >= 2 or any(item.get("display_text") for item in group),
                }
            )
            continue

        if current["type"] == "command":
            arguments = []
            cursor = index + 1
            while cursor < len(tokens) and tokens[cursor]["type"] in {
                "argument",
                "quoted",
                "keyword",
            }:
                argument = tokens[cursor]
                arguments.append(
                    {
                        "offset": f'{argument["offset"]:05X}',
                        "type": argument["type"],
                        "value": argument["value"],
                        "raw_hex": " ".join(f"{byte:02X}" for byte in argument["bytes"]),
                    }
                )
                cursor += 1
            records.append(
                {
                    "type": "command",
                    "offset": f'{current["offset"]:05X}',
                    "opcode": f'{current["bytes"][0]:02X}',
                    "name": current["value"],
                    "arguments": arguments,
                }
            )
            index = cursor
            continue

        records.append(
            {
                "type": current["type"],
                "offset": f'{current["offset"]:05X}',
                "value": current["value"],
                "raw_hex": " ".join(f"{byte:02X}" for byte in current["bytes"]),
            }
        )
        index += 1

    return records


