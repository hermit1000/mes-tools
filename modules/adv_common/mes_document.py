"""Shared construction of editable MES records from lexical tokens."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def make_editable_records(
    tokens: list[dict[str, Any]],
    make_readable_records: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    records = make_readable_records(tokens)
    display_offsets = {
        f'{token["offset"]:05X}' for token in tokens if token.get("display_text")
    }
    for record in records:
        if record["type"] == "text":
            record["original"] = record.pop("text")
            if record["offset"] in display_offsets:
                record["translation_candidate"] = True
        elif record["type"] == "gaiji":
            record["editable"] = False
    return records
