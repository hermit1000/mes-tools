"""Render Korean text into the Ballade map INF speech bubbles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from modules.adv_common.font_tiles import roi_2byte


DEFAULT_WORKSPACE = Path(r"C:\work_han\workspace4")
DEFAULT_TABLE = Path(__file__).resolve().parents[2] / "font_table" / "font_table-kor-jin.json"
FOLDERS = ("MAP0INF.GPA", "MAP1INF.GPA", "MAP2INF.GPA")
TITLE_TEXT = "마리아에게 바치는 발라드"
TITLE_FONT = Path(r"C:\work_han\font_graph\ext\나눔\NanumGothicExtraBold.ttf")
TITLE_LETTER_SPACING = 4


def render_title(root: Path) -> Path:
    source = root / "OP6.GPC" / "title.jpn.png"
    destination = root / "OP6.GPC" / "title.kor.png"
    with Image.open(source) as original:
        size = original.size
    font = ImageFont.truetype(str(TITLE_FONT), 43)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    bounds = draw.textbbox((0, 0), TITLE_TEXT, font=font)
    advances = [font.getlength(character) for character in TITLE_TEXT]
    gaps = [
        TITLE_LETTER_SPACING if left != " " and right != " " else 0
        for left, right in zip(TITLE_TEXT, TITLE_TEXT[1:])
    ]
    width = round(sum(advances) + sum(gaps))
    height = bounds[3] - bounds[1]
    if width > size[0] or height > size[1]:
        raise ValueError(f"Korean title exceeds OP6 title area: {width}x{height} > {size}")
    x = (size[0] - width) // 2
    y = (size[1] - height) // 2 - bounds[1]
    for index, character in enumerate(TITLE_TEXT):
        draw.text((round(x), y), character, font=font, fill=255)
        x += advances[index]
        if index < len(gaps):
            x += gaps[index]
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    levels = ((138, 0, 0, 255), (186, 0, 0, 255), (255, 0, 0, 255))
    for y in range(size[1]):
        for x in range(size[0]):
            value = mask.getpixel((x, y))
            if value:
                image.putpixel((x, y), levels[min((value - 1) // 85, 2)])
    image.save(destination)
    return destination


def load_glyphs(font_bmp: Path, font_table: Path, characters: set[str]) -> dict[str, Image.Image]:
    table = json.loads(font_table.read_text(encoding="utf-8"))
    codes = {character: code for code, character in table.items() if len(code) == 4}
    missing = characters - codes.keys() - {" "}
    if missing:
        raise ValueError(f"font glyphs missing: {''.join(sorted(missing))}")
    with Image.open(font_bmp) as bitmap:
        if bitmap.mode != "1" or bitmap.size != (2048, 2048):
            raise ValueError("expected a 2048x2048 monochrome font BMP")
        glyphs = {}
        for character in characters - {" "}:
            y0, y1, x0, x1 = roi_2byte(codes[character])
            glyphs[character] = bitmap.crop((x0, y0, x1, y1))
    return glyphs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--font-bmp", type=Path)
    parser.add_argument("--font-table", type=Path, default=DEFAULT_TABLE)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    root = workspace / "binary_inputs-pc98"
    entries = []
    for folder_name in FOLDERS:
        folder = root / folder_name
        lines = (folder / "labels.txt").read_text(encoding="utf-8").splitlines()
        if lines[0] != "주소\t일본어\t한국어":
            raise ValueError(f"unexpected label header: {folder}")
        for line in lines[1:]:
            address, japanese, korean = line.split("\t")
            if not korean:
                raise ValueError(f"empty translation: {folder_name}/{address}")
            entries.append((folder, address, japanese, korean))

    glyphs = load_glyphs(
        args.font_bmp or workspace / "ThinDungGeunMo.bmp",
        args.font_table,
        set("".join(korean for _, _, _, korean in entries if not korean.isascii())),
    )
    rendered = copied = 0
    for folder, address, japanese, korean in entries:
        source = folder / f"{address}.jpn.png"
        background = folder / f"{address}.bg.png"
        destination = folder / f"{address}.kor.png"
        if korean.isascii():
            if background.exists():
                raise ValueError(f"English-only entry has a background: {background}")
            with Image.open(source) as original:
                image = original.copy()
            copied += 1
        else:
            with Image.open(background) as original:
                image = original.copy()
            if image.mode != "P" or image.height != 32:
                raise ValueError(f"unexpected background format: {background}")
            text_width = sum(8 if character == " " else 16 for character in korean)
            if text_width > image.width - 16:
                raise ValueError(f"text exceeds bubble: {folder.name}/{address}: {korean}")
            x = (image.width - text_width) // 2
            y = 4
            pixels = image.load()
            for character in korean:
                if character == " ":
                    x += 8
                    continue
                glyph = glyphs[character]
                for gy in range(16):
                    for gx in range(16):
                        if glyph.getpixel((gx, gy)) == 0:
                            if pixels[x + gx, y + gy] != 15:
                                raise ValueError(f"glyph overlaps decoration: {folder.name}/{address} at {x + gx},{y + gy}")
                            pixels[x + gx, y + gy] = 1
                x += 16
            rendered += 1
        image.save(destination)
        with Image.open(destination) as check:
            if check.mode != "P" or check.size != image.size or check.tobytes() != image.tobytes():
                raise ValueError(f"saved image differs: {destination}")
    title = render_title(root)
    print(f"Rendered {rendered} Korean images; copied {copied} English-only images; title: {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
