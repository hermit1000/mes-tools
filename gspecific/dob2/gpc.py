"""Decode Dead of the Brain 2 PC-98 GPC images."""

from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path

from modules.pc98_image.adv98_artifacts import write_artifacts
from modules.pc98_image.gpc_usage import collect_output_modes as collect_mes_output_modes, choose_output_mode
from modules.adv_common.mes_decoder import decode_mes


def collect_output_modes(mes_root: Path) -> dict[str, Counter[int]]:
    return collect_mes_output_modes(mes_root, decode_mes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="GPC-relative filename; may be repeated (default: all GPC files)",
    )
    parser.add_argument("--mode", type=int, choices=(0, 1))
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / "GPC"
    names = args.files or [path.name for path in sorted(source_root.glob("*.GPC"))]
    if not names:
        raise FileNotFoundError(f"no GPC files found under {source_root}")
    observed = collect_output_modes(workspace / "jpn-pc98" / "MES")
    png_output = workspace / "image-pc98" / "GPC" / "_png"
    png_output.mkdir(parents=True, exist_ok=True)

    for name in names:
        source = source_root / name
        if not source.is_file():
            raise FileNotFoundError(source)
        modes = observed.get(source.name.upper(), Counter())
        output_mode = choose_output_mode(modes, args.mode)
        output = workspace / "image-pc98" / "GPC" / source.name
        decoded = write_artifacts(
            source,
            output,
            output_mode=output_mode,
            observed_modes=dict(modes),
        )
        shutil.copy2(
            output / f"{source.stem}.jpn.png",
            png_output / f"{source.stem}.jpn.png",
        )
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}, "
            f"output={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
