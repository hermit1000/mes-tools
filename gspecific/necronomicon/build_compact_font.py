"""Extend the existing Necronomicon compact font to 50 glyphs."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from modules.adv_common.font_tiles import roi_2byte


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_bmp", type=Path)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("output_bmp", type=Path)
    parser.add_argument("output_table", type=Path)
    parser.add_argument("--mapping", type=Path, default=Path(__file__).with_name("necro_compact_font_mapping_top50.json"))
    args = parser.parse_args()
    table = json.loads(args.source_table.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["entries"]
    with Image.open(args.source_bmp) as bitmap:
        if bitmap.mode != "1" or bitmap.size != (2048, 2048):
            raise ValueError("expected a 2048x2048 monochrome Anex86 font")
        source = np.array(bitmap)
    output = source.copy()
    # Existing compact glyphs are copied directly, preserving their appearance.
    for item in mapping:
        compact = item["code"]
        character = item["character"]
        y1, y2, x1, x2 = roi_2byte(item["source_sjis"])
        if compact in table:
            if table[compact] != character:
                raise ValueError(f"existing compact mapping differs at {compact}")
            glyph = source[y1:y2, x1:x2]
        else:
            code = next((code for code, char in table.items()
                         if len(code) == 4 and char == character), None)
            if code is None:
                raise ValueError(f"missing source glyph for {character!r}")
            sy1, sy2, sx1, sx2 = roi_2byte(code)
            glyph = source[sy1:sy2, sx1:sx2]
        if glyph.shape != (16, 16):
            raise ValueError("invalid glyph tile")
        output[y1:y2, x1:x2] = glyph
        table[compact] = character
        table[item["source_sjis"]] = character
    args.output_bmp.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output).save(args.output_bmp, format="BMP")
    args.output_table.parent.mkdir(parents=True, exist_ok=True)
    args.output_table.write_text(
        json.dumps(dict(sorted(table.items())), ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n",
        encoding="utf-8", newline="")
    with Image.open(args.output_bmp) as bitmap:
        assert bitmap.mode == "1" and np.array_equal(np.array(bitmap), output)
    print(f"Built and verified {len(mapping)} compact glyphs: {args.output_bmp}")


if __name__ == "__main__":
    main()
