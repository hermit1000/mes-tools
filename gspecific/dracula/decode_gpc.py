#!/usr/bin/env python3
"""Decode Dracula PC-98 GPC images into the workspace image artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from modules.adv_common.mes_lexer import decode_mes as decode_lexical_mes
from modules.pc98_image.adv98_artifacts import write_artifacts
from modules.pc98_image.gpc_usage import collect_output_modes, choose_output_mode
from modules.pc98_image.formats.adv98_gpc import (
    decode_gpc,
    decode_packed_palette_dac,
)


def decode_dracula_gpc(data: bytes, *, output_mode: int = 0):
    # The shared XOR routine matches ADVBIOS.OVL.dec 2787..27C2.
    return decode_gpc(
        data, output_mode=output_mode,
        palette_decoder=decode_packed_palette_dac,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="GPC filename; may be repeated (default: all GPC files)",
    )
    parser.add_argument(
        "--mode",
        type=int,
        choices=(0, 1),
        help="force one GPC output mode instead of inferring it from MES usage",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / "GPC"
    sources = sorted(source_root.glob("*.GPC"))
    if args.files:
        wanted = {name.upper() for name in args.files}
        sources = [source for source in sources if source.name.upper() in wanted]
    if not sources:
        raise FileNotFoundError(f"no requested GPC files found under {source_root}")

    observed = collect_output_modes(workspace / "jpn-pc98" / "MES", decode_lexical_mes, lexical=True)
    for source in sources:
        modes = observed.get(source.name.upper(), Counter())
        output_mode = choose_output_mode(modes, args.mode)
        output = workspace / "image-pc98" / "GPC" / source.name
        decoded = write_artifacts(
            source,
            output,
            output_mode=output_mode,
            observed_modes=dict(modes),
            decoder=decode_dracula_gpc,
            png_output=workspace / "image-pc98" / "png",
        )
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}, "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
