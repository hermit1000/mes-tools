"""Copy Ballade's 67 compact glyphs within the original Anex86 font bitmap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops

from modules.adv_common.font_tiles import roi_2byte


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = Path(r"C:\work_han\workspace4")
DEFAULT_MAPPING = Path(__file__).with_name("maria_compact_font_mapping_top67.json")
DEFAULT_TABLE = ROOT / "font_table" / "font_table-kor-jin.json"
DEFAULT_OUTPUT_TABLE = Path(__file__).with_name("font_table-kor-jin-ballade-compact-top67.json")


def glyph_code(table: dict[str, str], character: str) -> str:
    # This font table names the blank fullwidth glyph at 8140 "_".
    name = "_" if character == " " else character
    for code, value in table.items():
        if len(code) == 4 and value == name:
            return code
    raise ValueError(f"no source glyph for {character!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-bmp", type=Path, default=DEFAULT_WORKSPACE / "ThinDungGeunMo.bmp")
    parser.add_argument("--output-bmp", type=Path, default=DEFAULT_WORKSPACE / "ballade-ThinDungGeunMo.bmp")
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--font-table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--output-table", type=Path, default=DEFAULT_OUTPUT_TABLE)
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["entries"]
    if len(mapping) != 67 or [entry["code"] for entry in mapping] != [f"{code:02X}" for code in range(0x2D, 0x70)]:
        raise ValueError("expected the Ballade top67 mapping in codes 2D through 6F")
    table = json.loads(args.font_table.read_text(encoding="utf-8"))
    with Image.open(args.source_bmp) as bitmap:
        if bitmap.mode != "1" or bitmap.size != (2048, 2048):
            raise ValueError("expected a 2048x2048 1-bit Anex86 BMP")
        source = bitmap.copy()
    output = source.copy()
    output_table = dict(table)

    for entry in mapping:
        character = entry["character"]
        source_code = glyph_code(table, character)
        sy1, sy2, sx1, sx2 = roi_2byte(source_code)
        dy1, dy2, dx1, dx2 = roi_2byte(entry["source_sjis"])
        tile = source.crop((sx1, sy1, sx2, sy2))
        output.paste(tile, (dx1, dy1))
        output_table[entry["code"]] = character
        output_table[entry["source_sjis"]] = character

    args.output_bmp.parent.mkdir(parents=True, exist_ok=True)
    output.save(args.output_bmp, format="BMP")
    args.output_table.parent.mkdir(parents=True, exist_ok=True)
    args.output_table.write_text(
        json.dumps(dict(sorted(output_table.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\r\n",
    )

    with Image.open(args.output_bmp) as saved:
        if saved.mode != "1" or saved.size != source.size:
            raise ValueError("output BMP lost its 1-bit 2048x2048 format")
        for entry in mapping:
            sy1, sy2, sx1, sx2 = roi_2byte(glyph_code(table, entry["character"]))
            dy1, dy2, dx1, dx2 = roi_2byte(entry["source_sjis"])
            if ImageChops.difference(
                saved.crop((dx1, dy1, dx2, dy2)), source.crop((sx1, sy1, sx2, sy2)),
            ).getbbox():
                raise ValueError(f"glyph mismatch at {entry['code']}")
    print(f"built and verified {len(mapping)} glyphs: {args.output_bmp}")
    print(f"compact font table: {args.output_table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
