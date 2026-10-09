"""Decode ADV98 GPC files and write indexed image artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from importlib import import_module
from pathlib import Path

from .adv98_artifacts import write_artifacts
from .gpc_usage import choose_output_mode, collect_output_modes


PRESETS = {
    "dob1": ("GRAPH", "GRAPH", "modules.adv_common.mes_lexer", True),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--preset", choices=sorted(PRESETS))
    parser.add_argument("--source-dir", help="directory below jpn-pc98 containing GPC files")
    parser.add_argument("--output-dir", help="directory below image-pc98 for artifacts")
    parser.add_argument("--mes-decoder", help="Python module exposing decode_mes(bytes)")
    parser.add_argument("--lexical-mes", action="store_true", help="read C9/CF operands from lexical MES bytes")
    parser.add_argument("--file", action="append", dest="files", help="GPC filename; may be repeated")
    parser.add_argument("--mode", type=int, choices=(0, 1), help="override the MES output mode")
    args = parser.parse_args()

    source_dir, output_dir, mes_decoder, lexical = PRESETS.get(
        args.preset, ("GPC", "GPC", None, False),
    )
    source_dir = args.source_dir or source_dir
    output_dir = args.output_dir or output_dir
    mes_decoder = args.mes_decoder or mes_decoder
    lexical = args.lexical_mes or lexical
    for label, value in (("--source-dir", source_dir), ("--output-dir", output_dir)):
        directory = Path(value)
        if directory.is_absolute() or ".." in directory.parts:
            parser.error(f"{label} must stay below its workspace image directory")

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / source_dir
    names = args.files or [path.name for path in sorted(source_root.glob("*.GPC"))]
    if not names:
        raise FileNotFoundError(f"no GPC files found under {source_root}")

    observed = {}
    if mes_decoder:
        decoder = getattr(import_module(mes_decoder), "decode_mes")
        observed = collect_output_modes(workspace / "jpn-pc98" / "MES", decoder, lexical=lexical)

    for name in names:
        source = source_root / name
        if not source.is_file():
            raise FileNotFoundError(source)
        output = workspace / "image-pc98" / output_dir / source.name
        modes = observed.get(source.name.upper(), Counter())
        decoded = write_artifacts(
            source,
            output,
            output_mode=choose_output_mode(modes, args.mode),
            observed_modes=dict(modes),
        )
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}, "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
