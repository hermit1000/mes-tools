"""Render Korean Clear/Off button frames for Ballade's TEL.GPA."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from .build_map_inf_png import DEFAULT_WORKSPACE
from .decode_gpc import decode_maria_gpc
from .encode_map_inf_gpa import decode_frame, encode_tel_gpc, frame_offsets


BUTTONS = {10: ("지움", 11), 11: ("종료", 5), 22: ("지움", 10), 23: ("종료", 12)}


def replace_interlaced_button(image: Image.Image, number: int, japanese, korean) -> Image.Image:
    result = image.copy()
    left = 32 if number == 10 else 112
    for y in range(24):
        stored_y = y // 2 + (12 if y % 2 else 0)
        for x in range(32):
            source_offset = (264 + y) * japanese.width + left + x
            if image.getpixel((x, stored_y)) != japanese.indices[source_offset]:
                raise ValueError(f"TEL.GPA frame {number} does not match TEL.GPC")
            result.putpixel((x, stored_y), korean.indices[source_offset])
    return result


def gpc_label_mask(phone: Image.Image, number: int) -> Image.Image:
    left, ink = (36, (207, 101, 101)) if number in (10, 22) else (116, (101, 117, 85))
    mask = Image.new("L", (23, 14))
    for y in range(14):
        for x in range(23):
            if phone.getpixel((left + x, 268 + y)) == ink:
                mask.putpixel((x, y), 255)
    if mask.getbbox() is None:
        raise ValueError("TEL.kor.png has no Korean button glyphs")
    return mask


def replace_button(image: Image.Image, mask: Image.Image, ink: int) -> Image.Image:
    result = image.copy()
    for y in range(6, 20):
        for x in range(4, 28):
            result.putpixel((x, y), 15)
    for y in range(14):
        for x in range(23):
            if mask.getpixel((x, y)):
                result.putpixel((4 + x, 6 + y), ink)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    data = (workspace / "jpn-pc98" / "GPA" / "TEL.GPA").read_bytes()
    offsets = frame_offsets(data)
    source_gpc = (workspace / "jpn-pc98" / "GPC" / "TEL.GPC").read_bytes()
    japanese = decode_maria_gpc(source_gpc, output_mode=1)
    korean = decode_maria_gpc(
        encode_tel_gpc(source_gpc, workspace / "binary_inputs-pc98" / "TEL.GPC"),
        output_mode=1,
    )
    palette = japanese.palette
    folder = workspace / "binary_inputs-pc98" / "TEL.GPA"
    folder.mkdir(parents=True, exist_ok=True)
    with Image.open(workspace / "binary_inputs-pc98" / "TEL.GPC" / "TEL.kor.png") as image:
        phone = image.convert("RGB")
    for number, (text, ink) in BUTTONS.items():
        offset = offsets[number]
        end = offsets[number + 1] if number + 1 < len(offsets) else len(data)
        width, height, indices, _ = decode_frame(data[offset:end])
        original = Image.frombytes("P", (width, height), indices)
        original.putpalette([channel for color in palette for channel in color])
        stem = f"{offset:06X}"
        original.save(folder / f"{stem}.jpn.png")
        if number in (10, 11):
            translated = replace_interlaced_button(original, number, japanese, korean)
        else:
            mask = gpc_label_mask(phone, number)
            translated = replace_button(original, mask, ink)
        translated.save(folder / f"{stem}.kor.png")
        print(f"{stem}: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
