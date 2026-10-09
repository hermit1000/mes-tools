"""Shared dialogue-dictionary operations for ADV98 MES adapters."""

from __future__ import annotations

import json
from pathlib import Path


def add_pair(dictionary: dict, original: object, translation: object, reference: str) -> None:
    """Record one source/translation pair without changing its first-seen order."""
    if not isinstance(original, str) or not original.strip() or not isinstance(translation, str):
        return
    entry = dictionary.setdefault(
        original,
        {"count": 0, "reference": 0, "translated": [], "references": []},
    )
    entry["reference"] += 1
    entry["references"].append(reference)
    if translation not in entry["translated"]:
        entry["translated"].append(translation)
        entry["count"] = len(entry["translated"])


def load_candidates(path: Path, *, ignore_empty: bool = False) -> dict[str, str]:
    """Return source strings with exactly one usable translation.

    Some games record an empty string as a competing candidate; others discard
    it before deciding whether a source has one translation.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    candidates: dict[str, str] = {}
    for original, entry in document.items():
        if not isinstance(original, str) or not isinstance(entry, dict):
            continue
        translations = entry.get("translated")
        if not isinstance(translations, list):
            continue
        unique = list(
            dict.fromkeys(
                value for value in translations
                if isinstance(value, str) and (not ignore_empty or value.strip())
            )
        )
        if len(unique) == 1 and unique[0].strip():
            candidates[original] = unique[0]
    return candidates


def collect_dialogue_dictionary(
    paths: list[Path], *, sections: tuple[str, ...] = ("dialogue_groups", "overlay_texts"),
    expected_format: str | None = None, skip_other_formats: bool = False,
) -> tuple[dict, int, int, int]:
    """Collect MES translations and progress counts from language documents."""
    dictionary: dict = {}
    entries = translated = skipped = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if expected_format and document.get("format") != expected_format:
            if skip_other_formats:
                skipped += 1
                continue
            raise ValueError(f"unexpected format: {path}")
        for section in sections:
            for entry in document.get(section, []):
                if not isinstance(entry, dict):
                    continue
                entries += 1
                value = entry.get("translation")
                if isinstance(value, str) and value.strip():
                    translated += 1
                add_pair(dictionary, entry.get("original"), value,
                         f"{path.name}:{entry.get('id', '')}")
    return dictionary, entries, translated, skipped


def ambiguous_translations(dictionary: dict) -> dict:
    return {
        key: {"translated": value["translated"]}
        for key, value in dictionary.items() if value["count"] > 1
    }
