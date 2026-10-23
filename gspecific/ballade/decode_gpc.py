"""Decode Ballade GPC files from a workspace into image artifacts and PNGs."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

from modules.adv_common.mes_decoder import decode_mes as decode_structured_mes
from modules.adv_common.mes_lexer import decode_mes as decode_lexical_mes
from modules.pc98_image.adv98_artifacts import write_artifacts
from modules.pc98_image.formats.adv98_gpc import decode_gpc, decode_packed_palette_dac
from modules.pc98_image.gpc_usage import choose_output_mode, collect_output_modes


def decode_maria_gpc(data: bytes, *, output_mode: int):
    return decode_gpc(
        data,
        output_mode=output_mode,
        variant="necronomicon",
        palette_decoder=decode_packed_palette_dac,
        cumulative_xor=True,
    )


def collect_copy_modes(mes_root: Path) -> dict[str, Counter[int]]:
    """Read COPY filename and its immediately following CF output mode."""
    usage: dict[str, Counter[int]] = {}
    for source in sorted(mes_root.glob("*.MES")):
        tokens = decode_structured_mes(source.read_bytes(), structured_ascii=True)
        for index in range(len(tokens) - 4):
            command, _, quoted, apply, argument = tokens[index:index + 5]
            if (
                command.get("type") != "command" or command["bytes"][0] != 0xCD
                or quoted.get("type") != "quoted"
                or apply.get("type") != "command" or apply["bytes"][0] != 0xCF
                or argument.get("type") != "argument" or argument["value"] not in (0, 1)
            ):
                continue
            match = re.search(r"([A-Z0-9_]+\.GPC)", quoted["value"], re.IGNORECASE)
            if match and quoted["value"].upper().startswith("COPY "):
                name = match.group(1).upper()
                usage.setdefault(name, Counter())[argument["value"]] += 1
    return usage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--file", action="append", dest="files", help="GPC filename (repeatable)")
    parser.add_argument("--mode", type=int, choices=(0, 1), help="override MES output mode")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / "GPC"
    sources = sorted(source_root.glob("*.GPC"))
    if args.files:
        wanted = {name.upper() for name in args.files}
        sources = [source for source in sources if source.name.upper() in wanted]
        missing = wanted - {source.name.upper() for source in sources}
        if missing:
            parser.error(f"GPC file(s) not found: {', '.join(sorted(missing))}")
    if not sources:
        parser.error(f"no GPC files found under {source_root}")

    mes_root = workspace / "jpn-pc98" / "MES"
    observed = collect_output_modes(mes_root, decode_lexical_mes, lexical=True)
    for name, modes in collect_copy_modes(mes_root).items():
        observed.setdefault(name, modes)
    artifact_root = workspace / "image-pc98" / "GPC"
    png_root = workspace / "image-pc98" / "png"
    for source in sources:
        modes = observed.get(source.name.upper(), Counter())
        mode = choose_output_mode(modes, args.mode)
        decoded = write_artifacts(
            source,
            artifact_root / source.name,
            output_mode=mode,
            observed_modes=dict(modes),
            decoder=decode_maria_gpc,
            png_output=png_root,
        )
        print(f"{source.name}: {decoded.width}x{decoded.height}, mode={mode}")
    print(f"decoded {len(sources)} GPC files; PNGs: {png_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
