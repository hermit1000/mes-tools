"""Repack Ballade map/TEL GPA archives and OP6/TEL GPC images."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image

from modules.pc98_image.formats.adv98_gpc import (
    apply_output_mode,
    encode_gpc,
    indices_to_logical_rows,
    inverse_horizontal_xor,
    inverse_vertical_xor,
    pack_zero_masks,
    planar_rows_to_indices,
    undo_xor_delta,
    unpack_zero_masks,
)

from .build_map_inf_png import DEFAULT_WORKSPACE, FOLDERS
from .decode_gpc import decode_maria_gpc


SIGNATURE = b"PC98)GPAFILE   \0"
TITLE_COLORS = {
    (138, 0, 0, 255): 8,
    (186, 0, 0, 255): 9,
    (255, 0, 0, 255): 10,
}


def encode_title_gpc(source: bytes, folder: Path) -> bytes:
    decoded = decode_maria_gpc(source, output_mode=0)
    title_width, title_height, title_x = 539, 41, 2
    if (decoded.width, decoded.height, decoded.x, decoded.y) != (576, 269, 48, 110):
        raise ValueError("unexpected OP6.GPC geometry")

    indices = bytearray(decoded.indices)
    with Image.open(folder / "title.jpn.png") as original, Image.open(folder / "title.kor.png") as korean:
        if original.mode != "RGBA" or korean.mode != "RGBA":
            raise ValueError("OP6 title PNGs must be RGBA")
        if original.size != (title_width, title_height) or korean.size != original.size:
            raise ValueError("OP6 title PNG dimensions differ")
        for y in range(title_height):
            for x in range(title_width):
                offset = y * decoded.width + x + title_x
                old_index = indices[offset]
                expected = next((color for color, index in TITLE_COLORS.items() if index == old_index), (0, 0, 0, 0))
                if original.getpixel((x, y)) != expected:
                    raise ValueError(f"original OP6 title differs at {x},{y}")
                pixel = korean.getpixel((x, y))
                if pixel[3] == 0:
                    indices[offset] = 0
                elif pixel in TITLE_COLORS:
                    indices[offset] = TITLE_COLORS[pixel]
                else:
                    raise ValueError(f"unsupported OP6 title color at {x},{y}: {pixel}")

    encoded, _ = encode_gpc(
        source, bytes(indices), output_mode=0, variant="necronomicon"
    )
    if decode_maria_gpc(encoded, output_mode=0).indices != bytes(indices):
        raise ValueError("encoded OP6 title differs from Korean PNG")
    return encoded


def encode_tel_gpc(source: bytes, folder: Path) -> bytes:
    decoded = decode_maria_gpc(source, output_mode=1)
    size = (decoded.width, decoded.height)
    palette_indices = {color: index for index, color in enumerate(decoded.palette)}
    with Image.open(folder / "TEL.jpn.png") as original, Image.open(folder / "TEL.kor.png") as korean:
        if original.mode != "P" or original.size != size or korean.size != size:
            raise ValueError("TEL PNGs must match the indexed source geometry")
        if original.tobytes() != decoded.indices:
            raise ValueError("original TEL PNG differs from source GPC")
        if korean.convert("RGBA").getchannel("A").getextrema() != (255, 255):
            raise ValueError("TEL Korean PNG must be fully opaque")
        rgb = korean.convert("RGB")
        indices = bytearray(decoded.indices)
        for offset, (old_color, color) in enumerate(zip(original.convert("RGB").getdata(), rgb.getdata())):
            if color == old_color:
                continue
            if color not in palette_indices:
                raise ValueError(f"unsupported TEL color at pixel {offset}: {color}")
            indices[offset] = palette_indices[color]

    encoded, _ = encode_gpc(source, bytes(indices), output_mode=1, variant="necronomicon")
    restored = decode_maria_gpc(encoded, output_mode=1)
    if restored.indices != bytes(indices) or restored.palette != decoded.palette:
        raise ValueError("encoded TEL differs from Korean PNG")
    return encoded


def frame_offsets(data: bytes) -> list[int]:
    if data[:16] != SIGNATURE:
        raise ValueError("not an ADV98 GPA file")
    count = struct.unpack_from("<H", data, 16)[0]
    offsets = list(struct.unpack_from(f"<{count}I", data, 24))
    if not offsets or offsets[0] != 24 + count * 4 or offsets != sorted(set(offsets)):
        raise ValueError("invalid GPA frame table")
    if offsets[-1] >= len(data):
        raise ValueError("GPA frame points beyond file")
    return offsets


def decode_frame(block: bytes) -> tuple[int, int, bytes, bytes]:
    kind, x, y, width, height = struct.unpack_from("<HHHHH", block)
    if kind not in (1, 2) or width <= 0 or height <= 0:
        raise ValueError("invalid GPA frame descriptor")
    row_size = ((width + 7) // 8) * 4
    expanded, consumed = unpack_zero_masks(block[10:], (row_size + 1) * height)
    if any(block[10 + consumed:]):
        raise ValueError("GPA frame has nonzero trailing bytes")
    strides = expanded[::row_size + 1]
    rows = [
        undo_xor_delta(expanded[pos:pos + row_size + 1])
        for pos in range(0, (row_size + 1) * height, row_size + 1)
    ]
    logical_rows = apply_output_mode(rows, 0)
    return width, height, planar_rows_to_indices(logical_rows, width, height), strides


def encode_frame(source: bytes, indices: bytes) -> bytes:
    width, height, _, strides = decode_frame(source)
    if len(indices) != width * height or any(index > 15 for index in indices):
        raise ValueError("PNG dimensions or palette indices do not match the frame")
    rows = inverse_vertical_xor(indices_to_logical_rows(indices, width, height))
    expanded = b"".join(
        bytes((stride,)) + inverse_horizontal_xor(row, stride)
        for row, stride in zip(rows, strides)
    )
    expanded += bytes(-len(expanded) % 64)
    block = source[:10] + pack_zero_masks(expanded)
    return block + bytes(len(block) % 2)


def indexed_png(path: Path, width: int, height: int) -> bytes:
    with Image.open(path) as image:
        if image.mode != "P" or image.size != (width, height):
            raise ValueError(f"expected a {width}x{height} indexed PNG: {path}")
        return image.tobytes()


def encode_archive(
    source: bytes, folder: Path, *, selected: set[str] | None = None
) -> tuple[bytes, int]:
    offsets = frame_offsets(source)
    output = bytearray(source[:offsets[0]])
    changed = 0
    for index, offset in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(source)
        block = source[offset:end]
        width, height, original_indices, _ = decode_frame(block)
        stem = f"{offset:06X}"
        if selected is not None and stem not in selected:
            encoded = block
        else:
            original_png = indexed_png(folder / f"{stem}.jpn.png", width, height)
            if original_png != original_indices:
                raise ValueError(f"source PNG does not match GPA frame: {folder.name}/{stem}")
            korean_indices = indexed_png(folder / f"{stem}.kor.png", width, height)
            if korean_indices == original_indices:
                encoded = block
            else:
                encoded = encode_frame(block, korean_indices)
                changed += 1
        struct.pack_into("<I", output, 24 + index * 4, len(output))
        output.extend(encoded)

    result = bytes(output)
    new_offsets = frame_offsets(result)
    for index, (old_offset, new_offset) in enumerate(zip(offsets, new_offsets)):
        new_end = new_offsets[index + 1] if index + 1 < len(new_offsets) else len(result)
        width, height, actual, _ = decode_frame(result[new_offset:new_end])
        stem = f"{old_offset:06X}"
        if selected is not None and stem not in selected:
            old_end = offsets[index + 1] if index + 1 < len(offsets) else len(source)
            expected = decode_frame(source[old_offset:old_end])[2]
        else:
            expected = indexed_png(folder / f"{stem}.kor.png", width, height)
        if actual != expected:
            raise ValueError(f"encoded frame differs: {folder.name}/{old_offset:06X}")
    return result, changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    for name in FOLDERS:
        folder = workspace / "binary_inputs-pc98" / name
        source = (workspace / "jpn-pc98" / "GPA" / name).read_bytes()
        encoded, changed = encode_archive(source, folder)
        output = folder / name
        output.write_bytes(encoded)
        if output.read_bytes() != encoded:
            raise ValueError(f"saved GPA differs: {output}")
        print(f"{name}: {changed} frames encoded, {len(encoded)} bytes -> {output}")
    folder = workspace / "binary_inputs-pc98" / "OP6.GPC"
    source = (workspace / "jpn-pc98" / "GPC" / "OP6.GPC").read_bytes()
    encoded = encode_title_gpc(source, folder)
    output = folder / "OP6.GPC"
    output.write_bytes(encoded)
    if output.read_bytes() != encoded:
        raise ValueError(f"saved GPC differs: {output}")
    print(f"OP6.GPC: title encoded, {len(encoded)} bytes -> {output}")
    folder = workspace / "binary_inputs-pc98" / "TEL.GPC"
    source = (workspace / "jpn-pc98" / "GPC" / "TEL.GPC").read_bytes()
    encoded = encode_tel_gpc(source, folder)
    output = folder / "TEL.GPC"
    output.write_bytes(encoded)
    if output.read_bytes() != encoded:
        raise ValueError(f"saved GPC differs: {output}")
    print(f"TEL.GPC: buttons encoded, {len(encoded)} bytes -> {output}")
    folder = workspace / "binary_inputs-pc98" / "TEL.GPA"
    source = (workspace / "jpn-pc98" / "GPA" / "TEL.GPA").read_bytes()
    encoded, changed = encode_archive(
        source, folder, selected={"000A5C", "000B72", "00128E", "001346"}
    )
    output = folder / "TEL.GPA"
    output.write_bytes(encoded)
    if output.read_bytes() != encoded:
        raise ValueError(f"saved GPA differs: {output}")
    print(f"TEL.GPA: {changed} frames encoded, {len(encoded)} bytes -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
