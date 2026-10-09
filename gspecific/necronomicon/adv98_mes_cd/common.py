"""Paths and shared validation for the CD-specific tools."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from . import CORE_ROOT

DEFAULT_WORKSPACE = Path.cwd()
FONT_TABLE = CORE_ROOT / 'gspecific/necronomicon/font_table-kor-jin-necro-compact.json'
COMPACT_REMAP = FONT_TABLE.with_name('necro_compact_font_mapping_top50.json')

@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def original(self): return self.root / 'jpn-pc98-cd'
    @property
    def unpacked(self): return self.root / 'jpn-pc98-cd-unpacked'
    @property
    def scripts(self): return self.root / 'script-pc98-cd'
    @property
    def korean_unpacked(self): return self.root / 'kor-pc98-cd-unpacked'
    @property
    def korean(self): return self.root / 'kor-pc98-cd'
    @property
    def runtime(self): return self.root / 'kor-pc98-dosbox-x-cd'
    @property
    def emulator(self): return self.root / 'necronomicon-pc98-cd-runtime'
    @property
    def cache(self): return self.root / '.tmp/adv98_mes_cd'

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(data): return hashlib.sha256(data).hexdigest()

def save_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == data:
        return
    temporary = path.with_name(path.name + '.build-tmp')
    temporary.write_bytes(data)
    temporary.replace(path)

def selected(relative, names):
    if not names:
        return True
    key = relative.as_posix().casefold()
    return any(key == name.replace('\\', '/').casefold() or
               relative.name.casefold() == name.casefold() for name in names)
