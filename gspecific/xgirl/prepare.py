"""Prepare a non-CD X-Girl workspace without translating or patching binaries."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

from modules.adv_common.mes_decoder import decode_mes, make_records
from modules.adv_common.mes_lexer import decode_mes as lexical_mes
from modules.pc98_image.adv98_artifacts import write_artifacts
from modules.pc98_image.formats.adv98_gpc import decode_gpc
from modules.pc98_image.gpc_usage import collect_output_modes, choose_output_mode


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_image(data: bytes, *, output_mode: int):
    return decode_gpc(data, output_mode=output_mode, variant='necronomicon', cumulative_xor=True)


def prepare(workspace: Path) -> dict:
    source_root = workspace / 'jpn-pc98'
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    # Never overwrite existing extraction or working binaries.
    outputs = ['script-pc98', 'image-pc98', 'kor-pc98', 'kor-pc98-dosbox-x', 'preparation_report.json', 'source_manifest.json', 'script-review']
    for name in outputs:
        if (workspace / name).exists():
            raise FileExistsError(f'output already exists: {workspace / name}')
    manifest = []
    for source in sorted(source_root.rglob('*')):
        if source.is_file():
            data = source.read_bytes()
            manifest.append({'path': source.relative_to(source_root).as_posix(), 'size': len(data), 'sha256': digest(data)})
    write_json(workspace / 'source_manifest.json', manifest)
    for name in ['kor-pc98', 'kor-pc98-dosbox-x']:
        shutil.copytree(source_root, workspace / name)
    report = {'translation_performed': False, 'cd_work_performed': False, 'scripts': [], 'images': [], 'errors': []}
    scripts = sorted(p for p in source_root.rglob('*') if p.is_file() and (p.suffix.upper() in {'.MES', '.MEC'} or p.name.upper() == 'XGIRL.INI'))
    for source in scripts:
        relative = source.relative_to(source_root)
        data = source.read_bytes()
        try:
            tokens = decode_mes(data, structured_ascii=True)
            cursor = 0
            for token in tokens:
                raw = bytes(token['bytes'])
                if token['offset'] != cursor or token['size'] != len(raw) or data[cursor:cursor + len(raw)] != raw:
                    raise ValueError(f'token coverage mismatch at {cursor:05X}')
                cursor += len(raw)
            rebuilt = b''.join(bytes(t['bytes']) for t in tokens)
            if rebuilt != data:
                raise ValueError('raw token round-trip mismatch')
            records = make_records(tokens)
            entries = [{'id': f"text:{r['offset']}", 'offset': r['offset'], 'original': r['original'], 'translation': '', 'status': 'incomplete: untranslated'} for r in records if r.get('translation_candidate') and r.get('original', '').strip()]
            info = {'format': 'xgirl-adv98-script-info-v1', 'source': relative.as_posix(), 'source_size': len(data), 'source_sha256': digest(data), 'structured_ascii': True, 'warning': 'Lexical extraction only. Command semantics, speakers, gaiji and reinsertion need X-Girl-specific verification.', 'raw_roundtrip_verified': True, 'records': records, 'tokens': tokens}
            lang = {'format': 'xgirl-adv98-script-lang-v1', 'source_info': source.name + '_info.json', 'entries': entries}
            out = workspace / 'script-pc98' / relative.parent
            write_json(out / (source.name + '_info.json'), info)
            write_json(out / (source.name + '_lang.json'), lang)
            review = workspace / 'script-review' / relative.with_suffix(relative.suffix + '.txt')
            review.parent.mkdir(parents=True, exist_ok=True)
            review.write_text('\n\n'.join(f"[{relative.as_posix()}:{e['offset']}]\n{e['original']}" for e in entries) + '\n', encoding='utf-8')
            report['scripts'].append({'source': relative.as_posix(), 'entries': len(entries), 'roundtrip': True, 'token_types': dict(Counter(t['type'] for t in tokens))})
        except Exception as error:
            report['errors'].append({'source': relative.as_posix(), 'error': str(error)})
    modes = collect_output_modes(source_root / 'MES', lexical_mes, lexical=True)
    for source in sorted(p for p in source_root.rglob('*') if p.is_file() and p.suffix.upper() == '.GPC'):
        observed = modes.get(source.name.upper(), Counter())
        # Only the two modes implemented in the shared codec are selected.
        supported = Counter({k: v for k, v in observed.items() if k in (0, 1)})
        try:
            category = source.parent.relative_to(source_root)
            png_root = workspace / 'image-pc98' / 'png'
            if category != Path('GPC'):
                png_root /= category
            image = write_artifacts(source, workspace / 'image-pc98' / category / source.name, output_mode=choose_output_mode(supported, None), observed_modes=dict(observed), decoder=decode_image, png_output=png_root)
            report['images'].append({'source': source.relative_to(source_root).as_posix(), 'width': image.width, 'height': image.height, 'mode': image.output_mode, 'mode_inferred': bool(supported), 'compressed_padding': image.compressed_padding_size})
        except Exception as error:
            report['errors'].append({'source': source.relative_to(source_root).as_posix(), 'error': str(error)})
    for name in ['kor-pc98', 'kor-pc98-dosbox-x']:
        for entry in manifest:
            if digest((workspace / name / entry['path']).read_bytes()) != entry['sha256']:
                raise ValueError(f'working copy mismatch: {name}/{entry["path"]}')
    report['working_copies_verified'] = True
    report['source_preserved'] = all(digest((source_root / e['path']).read_bytes()) == e['sha256'] for e in manifest)
    report['asset_extensions'] = dict(Counter(Path(e['path']).suffix.upper() or '(none)' for e in manifest))
    report['pending'] = ['X-Girl command/speaker/gaiji validation', 'Non-GPC assets (CLM, TCM, USO, GPA, DPB, ICON) catalogued and preserved; specialized decoding not yet implemented', 'Runtime emulator verification', 'Translation, font remapping and translated reinsertion deferred']
    write_json(workspace / 'preparation_report.json', report)
    print(f"scripts={len(report['scripts'])}, entries={sum(s['entries'] for s in report['scripts'])}, images={len(report['images'])}, errors={len(report['errors'])}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.workspace.resolve())
    return int(bool(report['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
