#!/usr/bin/env python3
"""Encode one Necronomicon ADV98 MES from its info/lang JSON pair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from modules.adv_common.patches import apply_replacements, write_patch_manifest
from modules.adv_common.text import (
    encode_tokenized_translation,
    load_forced_dbcs_codes,
    load_font_codes,
    load_marine_remap,
)


KEEP_ORIGINAL = "@keep"
SECTIONS = ("dialogue_groups", "overlay_texts")
DISPLAY_LINE_CELLS = 32
FULLWIDTH_SPACE = b"\x81\x40"
MAX_MES_BYTES = 0x3000  # DS:9000 through BFFF; common-menu scratch starts at C006.
HALFWIDTH_SPACE = b"\x21\x20\x00"  # Original ADV98 inline ASCII-space output.


def encoded_text_half_cells(data: bytes) -> int:
    """Compact glyphs and DBCS glyphs both occupy two 8-pixel units."""
    index = width = 0
    while index < len(data):
        value = data[index]
        if 0x2D <= value <= 0x7F:
            index += 1
        elif (0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC) and index + 1 < len(data):
            index += 2
        else:
            raise ValueError("unsupported byte in centered menu label")
        width += 2
    return width


def center_menu_text(data: bytes, cells: int) -> bytes:
    if not isinstance(cells, int) or cells <= 0:
        raise ValueError("display_menu_width_cells must be a positive integer")
    unused = cells * 2 - encoded_text_half_cells(data)
    if unused < 0:
        raise ValueError(f"menu label exceeds {cells} display cells")
    left = unused // 2
    right = unused - left

    def padding(half_cells: int) -> bytes:
        return FULLWIDTH_SPACE * (half_cells // 2) + HALFWIDTH_SPACE * (half_cells % 2)

    return padding(left) + data + padding(right)


def menu_text_span(source: bytes, start: int, end: int) -> tuple[int, int]:
    """Include adjacent original padding, without consuming menu boundaries."""
    while True:
        if start >= 2 and source[start - 2:start] == FULLWIDTH_SPACE:
            start -= 2
        elif start >= 3 and source[start - 3:start] == HALFWIDTH_SPACE:
            start -= 3
        else:
            break
    while True:
        if source[end + 1:end + 3] == FULLWIDTH_SPACE:
            end += 2
        elif source[end + 1:end + 4] == HALFWIDTH_SPACE:
            end += 3
        else:
            break
    if source[start - 1:start] not in (b"\xA2", b"\xA4") or source[end + 1:end + 2] not in (b"\xA3", b"\xA4"):
        raise ValueError("centered menu row must be enclosed by ADV98 menu boundaries")
    return start, end


def validate_mes_size(data: bytes) -> None:
    if len(data) > MAX_MES_BYTES:
        raise ValueError(
            f"encoded MES is {len(data)} bytes; maximum is {MAX_MES_BYTES} bytes "
            "to avoid overwriting common-menu scratch memory"
        )


def encode_necro_text(
    text: str,
    codes: dict[str, str],
    *,
    forced_dbcs_codes: dict[str, str] | None = None,
    one_byte_codes: dict[str, int] | None = None,
) -> bytes:
    """Encode MES text, treating ``_`` as an explicit fullwidth-space token.

    ASCII spaces retain the existing compressed-space behavior.  The
    underscore token is reserved for layout padding in Necronomicon MES
    translations and is emitted directly as the original CP932 fullwidth
    space bytes ``81 40``.
    """
    return encode_tokenized_translation(
        text,
        codes,
        forced_dbcs_codes=forced_dbcs_codes,
        one_byte_codes=one_byte_codes,
    )


def translated_speaker_layout(value: str) -> tuple[str, int] | None:
    """Normalize a translated speaker line and return its content column."""
    if not value.startswith("「"):
        return None
    closing = value.find("」")
    if closing < 0:
        return None
    speaker = value[: closing + 1]
    content = value[closing + 1 :].lstrip(" \u3000")
    if content:
        normalized = speaker + " " + content
        return normalized, len(speaker) + 1
    return speaker, len(speaker)


def align_translated_display_groups(lang: dict) -> int:
    """Align continuation lines using the translated speaker's cell width."""
    entries = {
        entry.get("offset"): entry
        for section in SECTIONS
        for entry in lang.get(section, [])
        if isinstance(entry, dict) and entry.get("offset")
    }
    aligned = 0
    for group in lang.get("display_groups", []):
        speaker_offset = group.get("speaker_offset")
        speaker_entry = entries.get(speaker_offset)
        if not speaker_entry:
            continue
        speaker_translation = speaker_entry.get("translation")
        if not isinstance(speaker_translation, str) or not speaker_translation or speaker_translation == KEEP_ORIGINAL:
            continue
        layout = translated_speaker_layout(speaker_translation)
        if layout is None:
            continue
        normalized_speaker, content_column = layout
        stored_column = speaker_entry.get("display_translation_content_start_cells_strict")
        if not isinstance(stored_column, int) or stored_column < 0:
            stored_column = group.get("display_translation_content_start_cells_strict")
        if isinstance(stored_column, int) and stored_column >= 0:
            content_column = stored_column
        speaker_entry["translation"] = normalized_speaker
        speaker_entry["display_translation_speaker"] = normalized_speaker[: normalized_speaker.find("」") + 1]
        group["display_translation_speaker"] = speaker_entry["display_translation_speaker"]
        for line in group.get("lines", []):
            if line.get("role") != "continuation":
                continue
            entry = entries.get(line.get("offset"))
            if not entry:
                continue
            translation = entry.get("translation")
            if not isinstance(translation, str) or not translation or translation == KEEP_ORIGINAL:
                continue
            body = translation.lstrip(" \u3000")
            disabled = bool(
                group.get("display_disable_translation_indent")
                or entry.get("display_disable_translation_indent")
            )
            indent = 0 if disabled else content_column
            entry["translation"] = " " * indent + body
            aligned += 1
    return aligned


def wrap_display_text(value: str, *, initial_indent: int = 0, continuation_indent: int = 0) -> str:
    """Wrap one MES text record at 32 cells using the requested indent."""
    output: list[str] = []
    cells = 0
    if initial_indent:
        output.append(" " * initial_indent)
        cells = initial_indent

    units: list[tuple[str, int]] = []
    index = 0
    while index < len(value):
        if value.startswith("{ }", index):
            units.append(("{ }", 1))
            index += 3
        else:
            units.append((value[index], 1))
            index += 1

    for character, character_cells in units:
        if cells >= DISPLAY_LINE_CELLS:
            output.append(" " * (DISPLAY_LINE_CELLS - cells))
            output.append(" " * continuation_indent)
            cells = continuation_indent
            # A line break can leave one ordinary separator space at the
            # beginning of the next source line.  It is layout noise, not
            # part of the speaker alignment, so discard it here.
            if character in (" ", "\u3000", "{ }"):
                continue
        output.append(character)
        cells += character_cells
    return "".join(output)


def format_translated_display_groups(lang: dict) -> int:
    """Apply 32-cell wrapping and translated-speaker indentation in memory."""
    entries = {
        entry.get("offset"): entry
        for section in SECTIONS
        for entry in lang.get(section, [])
        if isinstance(entry, dict) and entry.get("offset")
    }
    formatted = 0
    for group in lang.get("display_groups", []):
        stored_group_column = group.get("display_translation_content_start_cells_strict")
        continuation_indent = (
            stored_group_column
            if isinstance(stored_group_column, int) and stored_group_column >= 0
            else 0
        )
        has_stored_group_column = isinstance(stored_group_column, int) and stored_group_column >= 0
        speaker_entry = entries.get(group.get("speaker_offset"))
        speaker_translation = (
            speaker_entry.get("translation")
            if isinstance(speaker_entry, dict)
            else None
        )
        has_translated_speaker = (
            isinstance(speaker_translation, str)
            and speaker_translation not in ("", KEEP_ORIGINAL)
            and translated_speaker_layout(speaker_translation) is not None
        )
        # A display group may consist of one long speaker record.  In that
        # case there is no continuation entry, but wrapping still needs to
        # use the translated speaker width on later physical lines.
        has_speaker = bool(group.get("display_translation_speaker")) or has_translated_speaker
        for line in group.get("lines", []):
            entry = entries.get(line.get("offset"))
            if not entry:
                continue
            translation = entry.get("translation")
            if not isinstance(translation, str) or not translation or translation == KEEP_ORIGINAL:
                continue
            disable_indent = bool(
                group.get("display_disable_translation_indent")
                or entry.get("display_disable_translation_indent")
            )
            if line.get("role") == "speaker" and has_speaker:
                layout = translated_speaker_layout(translation)
                if layout is None:
                    continue
                translation, content_column = layout
        # Only the strict field is authoritative. The ordinary field is
        # regenerated as diagnostic/output metadata.
                if not has_stored_group_column:
                    continuation_indent = content_column
            elif line.get("role") == "continuation" and has_speaker:
                translation = translation.lstrip(" \u3000")
            initial_indent = (
                0
                if disable_indent
                else continuation_indent
                if line.get("role") == "continuation" and has_speaker
                else 0
            )
            entry["translation"] = wrap_display_text(
                translation,
                initial_indent=initial_indent,
                continuation_indent=0 if disable_indent else continuation_indent if has_speaker else 0,
            )
            formatted += 1
    return formatted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-manifest", type=Path)
    parser.add_argument(
        "--compact-remap",
        "--marine-remap",
        dest="compact_remap",
        type=Path,
        help="map selected frequent characters to ADV98 one-byte compressed glyph codes",
    )
    parser.add_argument("source_mes", type=Path)
    parser.add_argument("info_json", type=Path)
    parser.add_argument("lang_json", type=Path)
    parser.add_argument("output_mes", type=Path)
    parser.add_argument(
        "font_table",
        type=Path,
        nargs="?",
        default=Path(__file__).resolve().parents[1] / "font_table-kor-jin-necro-compact.json",
    )
    args = parser.parse_args()

    source = args.source_mes.read_bytes()
    info = json.loads(args.info_json.read_text(encoding="utf-8"))
    lang = json.loads(args.lang_json.read_text(encoding="utf-8"))
    if info.get("format") != "necronomicon-adv98-mes-info-v1":
        raise ValueError("unexpected Necronomicon info JSON format")
    if lang.get("format") != "necronomicon-adv98-mes-lang-v1":
        raise ValueError("unexpected Necronomicon lang JSON format")
    if hashlib.sha256(source).hexdigest() != info["source_sha256"]:
        raise ValueError("source MES SHA-256 does not match info JSON")
    if lang.get("source_info") != args.info_json.name:
        raise ValueError("lang JSON refers to a different info JSON")

    align_translated_display_groups(lang)
    format_translated_display_groups(lang)

    records = {record["offset"]: record for record in info["records"]}
    codes = None
    one_byte_codes = None
    forced_dbcs_codes = None
    replacements: list[tuple[int, int, bytes]] = []
    for section in SECTIONS:
        for entry in lang.get(section, []):
            if not isinstance(entry, dict):
                continue
            record = records.get(entry.get("offset"))
            if not record or record.get("type") != "text":
                raise ValueError(f"unknown text record: {entry.get('offset')}")
            if entry.get("original") != record.get("original"):
                raise ValueError(f"original mismatch at {entry.get('offset')}")
            start = int(record["offset"], 16)
            end = int(record["end"], 16)
            expected = bytes.fromhex(record["raw_hex"])
            if source[start:end + 1] != expected:
                raise ValueError(f"source bytes mismatch at {start:05X}-{end:05X}")
            translation = entry.get("translation")
            if not translation:
                entry["status"] = "incomplete: untranslated"
                continue
            if translation == KEEP_ORIGINAL:
                entry["status"] = "passed"
                continue
            if codes is None:
                codes = load_font_codes(args.font_table)
                forced_dbcs_codes = load_forced_dbcs_codes(args.font_table)
                if args.compact_remap is not None:
                    one_byte_codes = load_marine_remap(args.compact_remap)
            display = translation
            prefix_hex = entry.get("encoding_prefix_hex")
            menu_cells = entry.get("display_menu_width_cells")
            if menu_cells is not None:
                if prefix_hex:
                    raise ValueError("centered menu text cannot have an encoding prefix")
                start, end = menu_text_span(source, start, end)
                encoded = center_menu_text(encode_necro_text(
                    display, codes, forced_dbcs_codes=forced_dbcs_codes,
                    one_byte_codes=one_byte_codes,
                ), menu_cells)
            elif isinstance(prefix_hex, str) and prefix_hex:
                prefix = bytes.fromhex(prefix_hex)
                if source[start : start + len(prefix)] != prefix:
                    raise ValueError(f"encoding prefix mismatch at {start:05X}")
                encoded = prefix + encode_necro_text(
                    display,
                    codes,
                    forced_dbcs_codes=forced_dbcs_codes,
                    one_byte_codes=one_byte_codes,
                )
            # Some overlay records begin with F3 followed by a Shift-JIS
            # display glyph.  F3 is a runtime marker and must be preserved,
            # while the following Japanese glyph is replaced by the
            # translation.  Retaining the whole raw record here would append
            # the translation after the original glyph and corrupt the next
            # boundary.
            elif (
                record.get("original", "").startswith(tuple(chr(value) for value in range(0xE000, 0xF900)))
                and expected[:1] == b"\xF3"
            ):
                encoded = expected[:1] + encode_necro_text(
                    display,
                    codes,
                    forced_dbcs_codes=forced_dbcs_codes,
                    one_byte_codes=one_byte_codes,
                )
            # MAIN.MES menu records may begin with a five-byte icon marker
            # (PUA glyph + selector bytes) before the visible label.
            elif record.get("original", "").startswith(tuple(chr(value) for value in range(0xE000, 0xF900))):
                    encoded = expected[:5] + encode_necro_text(
                        display,
                        codes,
                        forced_dbcs_codes=forced_dbcs_codes,
                        one_byte_codes=one_byte_codes,
                    )
            else:
                encoded = encode_necro_text(
                    display,
                    codes,
                    forced_dbcs_codes=forced_dbcs_codes,
                    one_byte_codes=one_byte_codes,
                )
            replacements.append((start, end, encoded))
            entry["status"] = "passed"

    replacements.sort()
    if any(previous[1] >= current[0] for previous, current in zip(replacements, replacements[1:])):
        raise ValueError("translation ranges overlap")
    rebuilt = apply_replacements(source, replacements)
    validate_mes_size(rebuilt)
    if args.patch_manifest:
        write_patch_manifest(args.patch_manifest, source, rebuilt, replacements)
    args.output_mes.parent.mkdir(parents=True, exist_ok=True)
    args.output_mes.write_bytes(rebuilt)
    # Keep the source translation JSON unchanged.  Display wrapping and
    # speaker alignment are encoding-only transformations performed in memory.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
