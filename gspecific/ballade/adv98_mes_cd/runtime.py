"""Build the Ballade CD boot floppy for HDD-hosted packed resources."""

import argparse
from pathlib import Path

from .boot import build_boot
from .common import Paths, save_bytes


OLD_START = b"\tEXE abios21.ovl adv21.ovl CD:\\maria.ini"
HDD_START = b"\tEXE abios21.ovl adv21.ovl /cd=C:\\MARIA21 C:\\MARIA21\\MARIA.INI"


def deploy(workspace: Path):
    paths = Paths(workspace.resolve())
    original_fd = paths.original / "FD"
    modified_fd = paths.korean_unpacked / "FD"
    modified_fd.mkdir(parents=True, exist_ok=True)
    source_config = (original_fd / "SHELL21.CNF").read_bytes()
    if source_config.count(OLD_START) != 1:
        raise ValueError("unexpected Ballade CD SHELL21.CNF startup command")
    save_bytes(modified_fd / "SHELL21.CNF", source_config.replace(OLD_START, HDD_START))
    save_bytes(modified_fd / "AUTOEXEC.BAT", (original_fd / "AUTOEXEC.BAT").read_bytes())
    image = build_boot(paths.root)
    for source in (paths.original / "HD").rglob("*"):
        if source.is_file():
            save_bytes(paths.runtime / source.relative_to(paths.original), source.read_bytes())
    for source in (paths.korean / "HD").rglob("*"):
        if source.is_file():
            save_bytes(paths.runtime / source.relative_to(paths.korean), source.read_bytes())
    for name in ("AUTOEXEC.BAT", "SHELL21.CNF"):
        save_bytes(paths.korean / "FD" / name, (modified_fd / name).read_bytes())
        save_bytes(paths.runtime / "FD" / name, (modified_fd / name).read_bytes())
    save_bytes(paths.runtime / "FD" / image.name, image.read_bytes())
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(deploy(args.workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
