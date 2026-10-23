"""Locate save-location titles in GRAPH_OP @0 quoted arguments."""

from __future__ import annotations

import re


TITLE_VALUE = re.compile(r"@0='([^']*)'")


def graph_op_title(records: list[dict]) -> tuple[int, str, bytes] | None:
    for record in records:
        if record.get("name") != "GRAPH_OP":
            continue
        for argument in record.get("arguments", []):
            if argument.get("type") != "quoted":
                continue
            match = TITLE_VALUE.fullmatch(argument.get("value", ""))
            if not match:
                continue
            raw = bytes.fromhex(argument["raw_hex"])
            if not raw.startswith(b"\x22@0='") or not raw.endswith(b"'\x22"):
                raise ValueError(f"GRAPH_OP title bytes differ: {argument['offset']}")
            title = raw[5:-2]
            if title.decode("cp932") != match.group(1):
                raise ValueError(f"GRAPH_OP title text differs: {argument['offset']}")
            return int(argument["offset"], 16) + 5, match.group(1), title
    return None
