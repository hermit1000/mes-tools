"""Find GPC output modes requested by ADV98 MES scripts."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any


def collect_output_modes(
    mes_root: Path,
    decode_mes: Callable[[bytes], list[dict[str, Any]]],
    *,
    lexical: bool = False,
) -> dict[str, Counter[int]]:
    """Read C9/CF pairs; DOB1's lexical tokens use raw byte operands."""
    usage: defaultdict[str, Counter[int]] = defaultdict(Counter)
    for path in sorted(mes_root.glob("*.MES")):
        data = path.read_bytes()
        tokens = decode_mes(data)
        current_name: str | None = None
        for index, token in enumerate(tokens):
            if token.get("type") != "command":
                continue
            opcode = token["bytes"][0]
            if lexical:
                offset = token["offset"]
                if opcode == 0xC9 and offset + 1 < len(data) and data[offset + 1] == 0x22:
                    end = data.find(b'"', offset + 2)
                    if end >= 0:
                        current_name = data[offset + 2:end].decode("ascii", errors="replace")
                elif opcode == 0xCF and current_name and offset + 1 < len(data):
                    encoded = data[offset + 1]
                    if 0x23 <= encoded <= 0x27:
                        usage[_basename(current_name)][encoded - 0x23] += 1
                continue
            if opcode == 0xC9:
                for following in tokens[index + 1:index + 3]:
                    if following.get("type") == "quoted":
                        current_name = str(following["value"])
                        break
            elif opcode == 0xCF and current_name and index + 1 < len(tokens):
                argument = tokens[index + 1]
                if argument.get("type") == "argument" and argument["value"] in (0, 1):
                    usage[_basename(current_name)][argument["value"]] += 1
    return dict(usage)


def _basename(value: str) -> str:
    return value.replace("\\", "/").rsplit("/", 1)[-1].upper()


def choose_output_mode(modes: Counter[int], requested: int | None, default: int = 1) -> int:
    return requested if requested is not None else (modes.most_common(1)[0][0] if modes else default)
