"""Render a Korean TITLE draft without AI image generation."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

from gspecific.necronomicon.decode_gpc import decode_necronomicon_gpc


def make_title(source: Image.Image, font_path: Path) -> Image.Image:
    """Use the original palette and red texture on newly rendered glyphs."""
    scale = 4
    font = ImageFont.truetype(str(font_path), 120 * scale)
    if font_path.name == "NotoSansKR-VF.ttf":
        font.set_variation_by_name("Black")
    glyphs = []
    for char in "네크로노미콘":
        glyph = Image.new("L", (180 * scale, 180 * scale))
        ImageDraw.Draw(glyph).text(
            (20 * scale, 0), char, font=font, fill=255,
            stroke_width=0, stroke_fill=255,
        )
        glyph = glyph.crop(glyph.getbbox()).resize(
            (85 * scale, 108 * scale), Image.Resampling.LANCZOS
        )
        glyphs.append(glyph)

    gap = 5 * scale
    width = sum(glyph.width for glyph in glyphs) + gap * (len(glyphs) - 1)
    height = max(glyph.height for glyph in glyphs)
    lettering = Image.new("L", (width, height))
    x = 0
    for glyph in glyphs:
        lettering.paste(glyph, (x, (height - glyph.height) // 2))
        x += glyph.width + gap
    lettering = lettering.resize((544, 108), Image.Resampling.LANCZOS)
    mask = Image.new("L", source.size)
    mask.paste(lettering, (48, 128))
    foreground = np.asarray(mask) >= 128

    rgb = np.asarray(source.convert("RGB"))
    red = (rgb[:, :, 0] > 0) & (rgb[:, :, 1] == 0) & (rgb[:, :, 2] == 0)
    # Extend existing texture into the old glyph gaps; no Japanese silhouette
    # remains in the result, and every foreground color is from the original.
    nearest = distance_transform_edt(~red, return_distances=False, return_indices=True)
    texture = rgb[nearest[0], nearest[1]]
    result = np.zeros_like(rgb)
    shadow = np.zeros_like(foreground)
    shadow[3:, 3:] = foreground[:-3, :-3]
    result[shadow] = (255, 255, 255)
    result[foreground] = texture[foreground]

    # Preserve exact indexed colors rather than introducing antialias shades.
    palette = source.getpalette()
    if source.mode != "P" or palette is None:
        raise ValueError("Expected the original indexed TITLE PNG")
    colors = np.asarray(palette, dtype=np.uint8).reshape(-1, 3)
    indices = np.zeros(source.size[::-1], dtype=np.uint8)
    for index, color in enumerate(colors[:16]):
        indices[np.all(result == color, axis=2)] = index
    output = Image.fromarray(indices).convert("P")
    output.putpalette(palette)
    assert np.array_equal(np.asarray(output.convert("RGB")), result)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--font", type=Path,
        default=Path(r"C:\Windows\Fonts\NotoSansKR-VF.ttf"),
    )
    args = parser.parse_args()
    folder = args.workspace / "binary_inputs-pc98"
    decoded = decode_necronomicon_gpc((folder / "TITLE.jpn.GPC").read_bytes())
    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette([channel for color in decoded.palette for channel in color])
    with Image.open(folder / "TITLE.jpn.png") as source:
        source = source.convert("RGB").quantize(palette=palette_image, dither=Image.Dither.NONE)
        title = make_title(source, args.font)
        background = Image.new("P", source.size, 0)
        background.putpalette(source.getpalette())
        background.save(folder / "TITLE.bg.png", optimize=True)
    output = folder / "TITLE.kor.png"
    title.save(output, optimize=True)
    print(f"wrote: {output}")


if __name__ == "__main__":
    main()
