"""Deploy packed HDD data without changing the original-CD-only default profile."""
import re
import subprocess
from pathlib import Path

from .common import Paths, save_bytes
from .boot import build_boot

def check_neko_closed():
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        "Get-Process | Where-Object { $_.ProcessName -match '^np21|^np2.*w$' } | Select-Object -ExpandProperty Id"],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError('Could not inspect Neko processes; close Neko before deployment')
    if result.stdout.strip():
        raise RuntimeError('Neko is running. Close it or build with --no-dosbox-x.')

def deploy(workspace):
    paths = Paths(Path(workspace).resolve())
    check_neko_closed()
    for source in (paths.korean / 'HD').rglob('*'):
        if source.is_file():
            save_bytes(paths.runtime / source.relative_to(paths.korean), source.read_bytes())
    build_boot(paths.root, paths.runtime / 'FD/Necronomicon-CD-HDD.hdm')
    korean_profile = paths.emulator / 'korean-hdd.ini'
    if korean_profile.is_file():
        text = korean_profile.read_text(encoding='utf-16')
        changes = {'hdrvroot': str(paths.runtime / 'HD'), 'use_hdrv': 'true', 'hdrv_acc': '1',
                   'SVFDFILE': 'true', 'SVCDFILE': 'true',
                   'FDD1FILE': str(paths.runtime / 'FD/Necronomicon-CD-HDD.hdm'),
                   'CD3_FILE': str(paths.root / 'cd/Necronomicon.ccd'),
                   'fontfile': str(paths.emulator / 'FONT/necro-ThinDungGeunMo.bmp')}
        for key, value in changes.items():
            text, count = re.subn(r'(?m)^' + key + r'=[^\r\n]*', lambda m: key + '=' + value, text, count=1)
            if count != 1: raise ValueError(f'Missing Neko option: {key}')
        korean_profile.write_text(text, encoding='utf-16')
    font = paths.root / 'necro-ThinDungGeunMo.bmp'
    if font.is_file(): save_bytes(paths.emulator / 'FONT' / font.name, font.read_bytes())
    return paths.runtime

