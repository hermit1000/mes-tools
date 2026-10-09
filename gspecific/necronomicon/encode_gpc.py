"""Encode an edited PNG using the shared GPC codec and verify it before saving."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from gspecific.necronomicon.decode_gpc import decode_necronomicon_gpc
from modules.pc98_image.adv98_artifacts import normalize_indexed
from modules.pc98_image.formats.adv98_gpc import encode_gpc


def encode_image(source: bytes, image: Image.Image, *, output_mode: int = 0) -> bytes:
    decoded = decode_necronomicon_gpc(source, output_mode=output_mode)
    if image.size != (decoded.width, decoded.height):
        raise ValueError(f"PNG must be {decoded.width}x{decoded.height}")
    if image.convert("RGBA").getchannel("A").getextrema() != (255, 255):
        raise ValueError("PNG must be fully opaque")
    reference = Image.new("P", image.size)
    reference.putpalette([channel for color in decoded.palette for channel in color])
    # Map even P-mode images by RGB: an edited PNG may reorder its palette.
    rgb = image.convert("RGB")
    indexed = normalize_indexed(rgb, reference)
    encoded, _ = encode_gpc(
        source, indexed.tobytes(), output_mode=output_mode,
        variant="necronomicon", cumulative_xor=output_mode == 0,
    )
    restored = decode_necronomicon_gpc(encoded, output_mode=output_mode)
    if restored.indices != indexed.tobytes() or restored.palette != decoded.palette:
        raise ValueError("GPC roundtrip changed indices or palette")
    preview = Image.frombytes("P", image.size, restored.indices)
    preview.putpalette(reference.getpalette())
    if preview.convert("RGB").tobytes() != rgb.tobytes():
        raise ValueError("GPC roundtrip changed PNG pixels")
    return encoded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, help="original GPC (default: TITLE.jpn.GPC)")
    parser.add_argument("--png", type=Path, help="edited PNG (default: TITLE.kor.png)")
    parser.add_argument("--output", type=Path, help="encoded GPC (default: TITLE.kor.GPC)")
    parser.add_argument("--output-mode", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()
    folder = args.workspace / "binary_inputs-pc98"
    source = args.source or folder / "TITLE.jpn.GPC"
    png = args.png or folder / "TITLE.kor.png"
    output = args.output or folder / "TITLE.kor.GPC"
    if output.resolve() in (source.resolve(), png.resolve()):
        raise ValueError("Output must not overwrite the source GPC or PNG")
    with Image.open(png) as image:
        encoded = encode_image(source.read_bytes(), image, output_mode=args.output_mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    print(f"wrote: {output} ({len(encoded)} bytes)")
    print("roundtrip: exact indices, palette, and RGB pixels")


if __name__ == "__main__":
    main()
