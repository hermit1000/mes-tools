"""Encode a Ballade MES or MEC using two-byte Korean font codes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.adv_common.patches import apply_replacements, write_patch_manifest
from modules.adv_common.text import encode_translation, load_font_codes, load_marine_remap
from gspecific.ballade.special_text import SPECIAL_TEXT_CODES
from gspecific.ballade.graph_titles import graph_op_title
from gspecific.ballade.text_layout import EXPLICIT_TOKEN, HALF_SPACE_TOKEN, NOOP_TOKEN, translation_texts, validate_layout
from gspecific.ballade.inline_names import encode_inline_names, prepare_name_moves, refresh_inline_names


DEFAULT_WORKSPACE = Path(r"C:\work_han\workspace4")
DEFAULT_FONT_TABLE = Path(__file__).resolve().parents[2] / "font_table" / "font_table-kor-jin.json"
MAX_MES_SIZE = 0x3000


def display_text(value: str) -> str:
    return "".join(
        " " if char == "\u3000" else chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char
        for char in value
    )


def same_display_text(original: str, translation: str) -> bool:
    return display_text(original) == display_text(translation)


def load_maria_font_codes(font_table: Path) -> dict[str, str]:
    codes = load_font_codes(font_table)
    codes.update({character: code for code, character in SPECIAL_TEXT_CODES.items() if len(character) == 1})
    codes.update({display_text(character): code for code, character in SPECIAL_TEXT_CODES.items() if len(character) == 1})
    codes["\u3000"] = "8140"
    for translation, glyph in (("=", "＝"), ("-", "－"), ("—", "―")):
        if glyph in codes:
            codes.setdefault(translation, codes[glyph])
    return codes


def encode_ballade_text(text: str, codes: dict[str, str], one_byte_codes: dict[str, int]) -> bytes:
    """Encode explicit two-byte glyphs and the verified D6 no-op token."""
    display = display_text(text)
    result = bytearray()
    cursor = 0
    for match in EXPLICIT_TOKEN.finditer(display):
        result.extend(encode_translation(display[cursor:match.start()], codes, one_byte_codes=one_byte_codes))
        if NOOP_TOKEN.fullmatch(match.group()):
            result.append(0xD6)
        elif HALF_SPACE_TOKEN.fullmatch(match.group()):
            result.extend(b"\x21\x20\x00")
        else:
            result.extend(encode_translation(match.group(1), codes))
        cursor = match.end()
    result.extend(encode_translation(display[cursor:], codes, one_byte_codes=one_byte_codes))
    return bytes(result)


def pad_mec_text(encoded: bytes, original_size: int) -> bytes:
    """Keep MEC record addresses fixed with the verified one-byte D6 no-op."""
    if len(encoded) > original_size:
        raise ValueError(f"MEC text length {original_size} -> {len(encoded)} bytes")
    return encoded + bytes((0xD6,)) * (original_size - len(encoded))


def encode_file(
    source_path: Path,
    info_path: Path,
    lang_path: Path,
    output_path: Path | None,
    font_table: Path = DEFAULT_FONT_TABLE,
    *,
    compact_remap: Path | None = None,
    patch_manifest: Path | None = None,
    secondary_output: Path | None = None,
    mec_original_fallbacks: list[dict] | None = None,
) -> tuple[int, int]:
    source = source_path.read_bytes()
    info = json.loads(info_path.read_text(encoding="utf-8"))
    lang = json.loads(lang_path.read_text(encoding="utf-8"))
    if info.get("format") != "maria-adv98-script-info-v1":
        raise ValueError(f"unexpected info format: {info_path}")
    if lang.get("format") != "maria-adv98-script-lang-v1" or lang.get("source_info") != info_path.name:
        raise ValueError(f"lang/info pair mismatch: {lang_path}")
    if info.get("source_size") != len(source) or info.get("source_sha256") != hashlib.sha256(source).hexdigest():
        raise ValueError(f"source differs from extraction input: {source_path}")
    refresh_inline_names(info, lang, lang_path.parent)
    try:
        prepare_name_moves(info, lang, equivalent=same_display_text)
    except ValueError as error:
        raise ValueError(f"{lang_path.name}:{error}") from error

    records = {record["offset"]: record for record in info["records"] if record.get("type") == "text"}
    codes = load_maria_font_codes(font_table)
    one_byte_codes = load_marine_remap(compact_remap)
    effective_texts = translation_texts(info, lang)
    replacements: list[tuple[int, int, bytes]] = []
    seen = set()
    for entry in lang["entries"]:
        offset = entry.get("offset")
        record = records.get(offset)
        if offset in seen or record is None or not record.get("translation_candidate"):
            raise ValueError(f"unknown or duplicate text record: {lang_path.name}:{offset}")
        seen.add(offset)
        start, end = int(offset, 16), int(record["end"], 16)
        center_bytes = bytes.fromhex(record["raw_hex"])
        if source[start:end + 1] != center_bytes:
            raise ValueError(f"source bytes mismatch: {lang_path.name}:{offset}")
        edges = entry.get("ascii_half_space_edges", {})
        if not isinstance(edges, dict):
            raise ValueError(f"invalid ASCII space edges: {lang_path.name}:{offset}")
        left, right = edges.get("left", 0), edges.get("right", 0)
        if any(type(count) is not int or count < 0 for count in (left, right)):
            raise ValueError(f"invalid ASCII space edges: {lang_path.name}:{offset}")
        token = "{반각공백}"
        expected_with_spaces = token * left + record["original"] + token * right
        if entry.get("id") != f"text:{offset}" or entry.get("original") != record["original"]:
            raise ValueError(f"entry identity mismatch: {lang_path.name}:{offset}")
        if edges and entry.get("original_with_half_spaces") != expected_with_spaces:
            raise ValueError(f"ASCII space display mismatch: {lang_path.name}:{offset}")
        span_start, span_end = start - 3 * left, end + 3 * right
        prefix, suffix = b"\x21\x20\x00" * left, b"\x21\x20\x00" * right
        if span_start < 0 or source[span_start:span_end + 1] != prefix + center_bytes + suffix:
            raise ValueError(f"ASCII space edges differ from source: {lang_path.name}:{offset}")
        start, end = span_start, span_end
        original_bytes = source[start:end + 1]
        translation = entry.get("translation", "")
        if not isinstance(translation, str):
            raise ValueError(f"translation is not text: {lang_path.name}:{offset}")
        if not translation or translation == "@keep" or same_display_text(expected_with_spaces, translation):
            continue
        if "ascii" in record.get("encodings", []):
            raise ValueError(f"{lang_path.name}:{offset}: ASCII output record needs original bytes or @keep")
        # The table stores fullwidth Latin letters and digits under their ASCII names.
        display = effective_texts.get(offset, translation)
        try:
            encoded = encode_inline_names(
                display, record,
                lambda text: encode_ballade_text(text, codes, one_byte_codes),
            )
        except ValueError as error:
            raise ValueError(f"{lang_path.name}:{offset}: {error}") from error
        if source_path.suffix.upper() == ".MEC":
            if len(encoded) > len(original_bytes):
                if mec_original_fallbacks is not None:
                    mec_original_fallbacks.append({
                        "id": entry["id"], "offset": offset,
                        "original_bytes": len(original_bytes),
                        "encoded_bytes": len(encoded),
                    })
                continue
            encoded = pad_mec_text(encoded, len(original_bytes))
        replacements.append((start, end, encoded))

    title = graph_op_title(info["records"]) if source_path.suffix.upper() == ".MES" else None
    title_entry = lang.get("graph_op_title")
    if title_entry is not None:
        if title is None or not isinstance(title_entry, dict):
            raise ValueError(f"unexpected GRAPH_OP title: {lang_path.name}")
        offset, original, original_bytes = title
        if title_entry.get("offset") != f"{offset:05X}" or title_entry.get("original") != original:
            raise ValueError(f"GRAPH_OP title identity mismatch: {lang_path.name}")
        if source[offset:offset + len(original_bytes)] != original_bytes:
            raise ValueError(f"GRAPH_OP title source differs: {source_path.name}")
        translation = title_entry.get("translation", "")
        if not isinstance(translation, str):
            raise ValueError(f"GRAPH_OP title translation is not text: {lang_path.name}")
        if translation and translation != "@keep" and translation != original:
            encoded = encode_translation(display_text(translation), codes)
            if any(byte in encoded for byte in (0x00, 0x22, 0x27)):
                raise ValueError(f"GRAPH_OP title contains a delimiter byte: {lang_path.name}")
            if len(encoded) > len(original_bytes):
                raise ValueError(f"GRAPH_OP title length {len(original_bytes)} -> {len(encoded)} bytes: {lang_path.name}")
            replacements.append((offset, offset + len(original_bytes) - 1, encoded))
    validate_layout(info, lang, lang_path.name)
    rebuilt = apply_replacements(source, replacements)
    if source_path.suffix.upper() == ".MEC":
        if len(rebuilt) != len(source):
            raise ValueError(f"MEC file size changed: {source_path.name}")
    elif source_path.suffix.upper() == ".MES":
        if len(rebuilt) > MAX_MES_SIZE:
            raise ValueError(f"MES exceeds {MAX_MES_SIZE} bytes: {source_path.name} -> {len(rebuilt)} bytes")
    else:
        raise ValueError(f"expected .MES or .MEC: {source_path}")
    if patch_manifest is not None:
        write_patch_manifest(patch_manifest, source, rebuilt, replacements)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(rebuilt)
    if secondary_output is not None:
        secondary_output.parent.mkdir(parents=True, exist_ok=True)
        secondary_output.write_bytes(rebuilt)
    return len(replacements), len(rebuilt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="MES or MEC filename under jpn-pc98/MES")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--font-table", type=Path, default=DEFAULT_FONT_TABLE)
    parser.add_argument("--compact-remap", type=Path, help="optional one-byte font remap JSON")
    parser.add_argument("--output", type=Path, help="custom single output; default: both kor-pc98/MES and kor-pc98-dosbox-x/MES")
    parser.add_argument("--patch-manifest", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="validate and calculate without writing")
    args = parser.parse_args()
    name = args.file
    if Path(name).name != name or Path(name).suffix.upper() not in {".MES", ".MEC"}:
        parser.error("file must be a .MES or .MEC filename")
    workspace = args.workspace.resolve()
    source = workspace / "jpn-pc98" / "MES" / name
    info = workspace / "script-pc98" / "MES" / f"{name}_info.json"
    lang = workspace / "script-pc98" / "MES" / f"{name}_lang.json"
    output = args.output or workspace / "kor-pc98" / "MES" / name
    secondary = None if args.output else workspace / "kor-pc98-dosbox-x" / "MES" / name
    mec_original_fallbacks = []
    patches, size = encode_file(
        source, info, lang, None if args.dry_run else output, args.font_table,
        compact_remap=args.compact_remap,
        patch_manifest=None if args.dry_run else args.patch_manifest,
        secondary_output=None if args.dry_run else secondary,
        mec_original_fallbacks=mec_original_fallbacks,
    )
    destinations = f" -> {output}" + (f", {secondary}" if secondary else "")
    print(f"{name}: {patches} replacements, {size} bytes"
          + (f"; {len(mec_original_fallbacks)} MEC records kept original" if mec_original_fallbacks else "")
          + (" (dry run)" if args.dry_run else destinations))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
