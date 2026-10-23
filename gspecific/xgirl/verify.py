"""Verify untranslated X-Girl extraction and byte-identical working copies."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def verify(workspace: Path) -> None:
    manifest = json.loads((workspace / 'source_manifest.json').read_text(encoding='utf-8'))
    for root in ['jpn-pc98', 'kor-pc98', 'kor-pc98-dosbox-x']:
        for entry in manifest:
            actual = hashlib.sha256((workspace / root / entry['path']).read_bytes()).hexdigest()
            if actual != entry['sha256']:
                raise ValueError(f'hash mismatch: {root}/{entry["path"]}')
    count = entries = 0
    for path in sorted((workspace / 'script-pc98').rglob('*_info.json')):
        info = json.loads(path.read_text(encoding='utf-8'))
        source = (workspace / 'jpn-pc98' / info['source']).read_bytes()
        if hashlib.sha256(source).hexdigest() != info['source_sha256']:
            raise ValueError(f'source hash mismatch: {path}')
        if b''.join(bytes(t['bytes']) for t in info['tokens']) != source:
            raise ValueError(f'token round-trip mismatch: {path}')
        lang = json.loads(path.with_name(path.name.replace('_info.json', '_lang.json')).read_text(encoding='utf-8'))
        originals = {r['offset']: r.get('original') for r in info['records']}
        for entry in lang['entries']:
            if entry['translation'] or entry['original'] != originals[entry['offset']]:
                raise ValueError(f'not an unchanged untranslated entry: {path}:{entry["offset"]}')
        count += 1
        entries += len(lang['entries'])
    images = list((workspace / 'image-pc98').rglob('*.jpn.GPC'))
    expected = [e for e in manifest if Path(e['path']).suffix.upper() == '.GPC']
    if len(images) != len(expected):
        raise ValueError(f'image coverage mismatch: {len(images)} != {len(expected)}')
    for entry in expected:
        rel = Path(entry['path'])
        folder = workspace / 'image-pc98' / rel.parent / rel.name
        if (folder / (rel.stem + '.jpn' + rel.suffix)).read_bytes() != (workspace / 'jpn-pc98' / rel).read_bytes():
            raise ValueError(f'image original mismatch: {rel}')
        metadata = json.loads((folder / (rel.stem + '.meta.json')).read_text(encoding='utf-8'))
        if len((folder / (rel.stem + '.idx.jpn.bin')).read_bytes()) != metadata['width'] * metadata['height']:
            raise ValueError(f'image dimensions mismatch: {rel}')
        png_root = workspace / 'image-pc98/png'
        if rel.parent != Path('GPC'):
            png_root /= rel.parent
        with Image.open(png_root / (rel.stem + '.jpn.png')) as image:
            if image.size != (metadata['width'], metadata['height']) or image.mode != 'P' or image.tobytes() != (folder / (rel.stem + '.idx.jpn.bin')).read_bytes():
                raise ValueError(f'PNG pixel mismatch: {rel}')
    print(f'verified {len(manifest)} source files and both working copies; {count} scripts, {entries} untranslated entries, {len(images)} GPC images')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    verify(parser.parse_args().workspace.resolve())


if __name__ == '__main__':
    main()
