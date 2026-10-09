"""Decode Marine Philt PC-98 GPC images into one artifact directory."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import partial
from pathlib import Path

from modules.pc98_image.adv98_artifacts import write_artifacts
from modules.pc98_image.gpc_usage import collect_output_modes as collect_mes_output_modes, choose_output_mode
from modules.adv_common.mes_decoder import decode_mes, consume_selector_parameters


def collect_output_modes(mes_root: Path) -> dict[str, Counter[int]]:
    decoder = partial(
        decode_mes,
        structured_ascii=True,
        parameter_controls=(0x08, 0x09, 0x0C, 0x0D, 0x19),
        transform_tokens=consume_selector_parameters,
    )
    return collect_mes_output_modes(mes_root, decoder)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="GRAPH-relative GPC filename; may be repeated (default: all)",
    )
    parser.add_argument("--mode", type=int, choices=(0, 1))
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    source_root = workspace / "jpn-pc98" / "GRAPH"
    output = workspace / "image-pc98" / "GPC"
    names = args.files or [path.name for path in sorted(source_root.glob("*.GPC"))]
    if not names:
        raise FileNotFoundError(f"no GPC files found under {source_root}")

    observed = collect_output_modes(workspace / "jpn-pc98" / "MES")
    decoded_count = 0
    for name in names:
        source = source_root / name
        if not source.is_file():
            raise FileNotFoundError(source)
        file_output = output / source.name
        modes = observed.get(source.name.upper(), Counter())
        output_mode = choose_output_mode(modes, args.mode)
        decoded = write_artifacts(
            source,
            file_output,
            output_mode=output_mode,
            observed_modes=dict(modes),
        )
        decoded_count += 1
        print(
            f"{source.name}: {decoded.width}x{decoded.height}, "
            f"mode={decoded.output_mode}, compressed={decoded.compressed_size}"
        )
    print(f"decoded {decoded_count} GPC files into {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
