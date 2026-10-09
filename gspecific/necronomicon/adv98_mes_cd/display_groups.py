#!/usr/bin/env python3
"""Annotate Necronomicon MES language JSON with display-line relationships."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORMAT = "necronomicon-adv98-mes-lang-v1"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_a5(record: dict[str, Any]) -> bool:
    return record.get("type") == "control" and record.get("raw_hex", "").replace(" ", "").upper() == "A5"


def is_display_continuation_control(record: dict[str, Any]) -> bool:
    """Return whether a control keeps the next text on the same dialogue display."""
    return is_a5(record) or record.get("name") == "CMD_A7"


def leading_cells(text: str) -> int:
    count = 0
    for character in text:
        if character in (" ", "\u3000"):
            count += 1
        else:
            break
    return count


def speaker_info(text: str) -> tuple[str | None, int | None]:
    if not text.startswith("「"):
        return None, None
    closing = text.find("」")
    if closing < 0:
        return None, None
    speaker = text[: closing + 1]
    content_start = closing + 1
    while content_start < len(text) and text[content_start] in (" ", "\u3000"):
        content_start += 1
    return speaker, content_start


def build_groups(info: dict[str, Any], lang: dict[str, Any]) -> list[dict[str, Any]]:
    entries = {
        entry.get("offset"): entry
        for section in ("dialogue_groups", "overlay_texts")
        for entry in lang.get(section, [])
        if isinstance(entry, dict) and entry.get("offset")
    }
    records = info.get("records", [])
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    previous_was_continuation_control = False

    for record in records:
        if record.get("type") == "control" or record.get("name") == "CMD_A7":
            previous_was_continuation_control = is_display_continuation_control(record)
            continue
        if record.get("type") != "text":
            previous_was_continuation_control = False
            continue

        offset = record.get("offset")
        entry = entries.get(offset)
        if entry is None:
            previous_was_continuation_control = False
            continue

        original = entry.get("original", "")
        speaker, speaker_content_start = speaker_info(original)
        continuation = current is not None and previous_was_continuation_control
        if not continuation:
            current = {
                "id": f"display:{offset}",
                "start_offset": offset,
                "end_offset": offset,
                "speaker": speaker,
                "speaker_offset": offset if speaker else None,
                "lines": [],
            }
            groups.append(current)

        assert current is not None
        line = {
            "offset": offset,
            "role": "continuation" if continuation else ("speaker" if speaker else "text"),
            "line_index": len(current["lines"]),
            "leading_cells": leading_cells(original),
        }
        if speaker is not None:
            line["speaker"] = speaker
            line["speaker_content_start_cells"] = speaker_content_start
        current["lines"].append(line)
        current["end_offset"] = record.get("end", offset)
        previous_was_continuation_control = False

    for group in groups:
        group["line_count"] = len(group["lines"])
        group["has_continuation"] = len(group["lines"]) > 1
        for line in group["lines"]:
            entry = entries.get(line["offset"])
            if entry is None:
                continue
            entry["display_group"] = group["id"]
            entry["display_role"] = line["role"]
            entry["display_line_index"] = line["line_index"]
            entry["display_leading_cells"] = line["leading_cells"]
            if group.get("speaker"):
                entry["display_speaker"] = group["speaker"]
            if "speaker_content_start_cells" in line:
                entry["display_speaker_content_start_cells"] = line["speaker_content_start_cells"]
    return groups


