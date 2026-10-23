"""Paths and safe file helpers for the Ballade CD build."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def original(self): return self.root / "jpn-pc98-cd"

    @property
    def unpacked(self): return self.root / "jpn-pc98-cd-unpacked"

    @property
    def scripts(self): return self.root / "script-pc98-cd"

    @property
    def korean_unpacked(self): return self.root / "kor-pc98-cd-unpacked"

    @property
    def korean(self): return self.root / "kor-pc98-cd"

    @property
    def runtime(self): return self.root / "kor-pc98-dosbox-x-cd"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\r\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == data:
        return
    temporary = path.with_name(path.name + ".build-tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def selected(relative, names):
    if not names:
        return True
    key = relative.as_posix().casefold()
    return any(key == name.replace("\\", "/").casefold()
               or relative.name.casefold() == name.casefold() for name in names)
