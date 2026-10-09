"""Shared file selection and command construction for MES batch encoders."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def source_names(source_dir: Path, extensions: set[str], selected: list[str] | None = None) -> list[str]:
    if selected:
        return selected
    return [
        path.name for path in sorted(source_dir.iterdir())
        if path.is_file() and path.suffix.upper() in extensions
    ]


def input_paths(workspace: Path, name: str) -> tuple[Path, Path, Path, Path]:
    return (
        workspace / "jpn-pc98" / "MES" / name,
        workspace / "script-pc98" / "MES" / f"{name}_info.json",
        workspace / "script-pc98" / "MES" / f"{name}_lang.json",
        workspace / "kor-pc98" / "MES" / name,
    )


def missing_inputs(source: Path, info: Path, lang: Path) -> list[str]:
    return [str(path) for path in (source, info, lang) if not path.is_file()]


def encode_command(module: str, paths: tuple[Path, Path, Path, Path], font_table: Path,
                   manifest_dir: Path | None = None) -> list[str]:
    command = [sys.executable, "-m", module, *(str(path) for path in paths), str(font_table.resolve())]
    if manifest_dir:
        command += ["--patch-manifest", str((manifest_dir / f"{paths[0].name}.patches.json").resolve())]
    return command


def selected_range(total: int, bounds: tuple[int | None, int | None]) -> range:
    start, end = bounds
    start = 1 if start is None else start
    end = total if end is None else end
    if not 1 <= start <= end <= total:
        raise ValueError(f"invalid index range {bounds}; expected 1 <= start <= end <= {total}")
    return range(start, end + 1)


def copy_dosbox_output(output: Path, workspace: Path) -> Path:
    destination = workspace / "kor-pc98-dosbox-x" / "MES" / output.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output, destination)
    return destination
