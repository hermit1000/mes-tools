"""Encode CD MES, repack all containers, and optionally update the Neko HDD data."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gspecific.necronomicon.adv98_mes_cd.common import (
    DEFAULT_WORKSPACE, Paths, FONT_TABLE, COMPACT_REMAP, read_json, write_json, save_bytes, selected, sha)
from gspecific.necronomicon.adv98_mes_cd.containers import repack
from gspecific.necronomicon.adv98_mes_cd.boot import build_boot
from gspecific.necronomicon.adv98_mes_cd.runtime import deploy, check_neko_closed
from modules.adv_common.patches import verify_patch_manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path, nargs='?', default=DEFAULT_WORKSPACE)
    parser.add_argument('--files', nargs='+', metavar='MES')
    parser.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument('--font-table', type=Path, default=FONT_TABLE)
    parser.add_argument('--compact-remap', type=Path, default=COMPACT_REMAP)
    parser.add_argument('--no-compact-remap', dest='compact_remap', action='store_const', const=None)
    parser.add_argument('--no-dosbox-x', '--no-runtime', action='store_true',
                        help='Build the unpacked and packed outputs without deploying Neko data')
    args = parser.parse_args()
    if args.jobs < 1: parser.error('--jobs must be at least 1')
    paths = Paths(args.workspace.resolve())
    if not args.no_dosbox_x: check_neko_closed()
    manifest = read_json(paths.unpacked / 'container-manifest.json')
    lang_paths = sorted((paths.scripts / 'HD').rglob('*.MES_lang.json'))
    selected_lang = [(path, path.relative_to(paths.scripts).with_name(path.name.removesuffix('_lang.json')))
                     for path in lang_paths]
    selected_lang = [(path, rel) for path, rel in selected_lang if selected(rel, args.files)]
    if not selected_lang: parser.error('No matching CD MES language files')
    if args.files:
        for name in args.files:
            if not any(selected(rel, [name]) for path, rel in selected_lang):
                parser.error(f'MES not found: {name}')
    stage = paths.cache / 'builds' / uuid.uuid4().hex
    unpacked, packed = stage / 'unpacked', stage / 'packed'
    shutil.copytree(paths.unpacked / 'HD', unpacked / 'HD')
    if (paths.korean_unpacked / 'HD').is_dir():
        shutil.copytree(paths.korean_unpacked / 'HD', unpacked / 'HD', dirs_exist_ok=True)
    shutil.copytree(paths.original / 'FD', unpacked / 'FD')
    for root in (paths.korean / 'FD', paths.korean_unpacked / 'FD'):
        for source in root.glob('*'):
            if source.is_file() and source.suffix.lower() != '.hdm':
                save_bytes(unpacked / 'FD' / source.name, source.read_bytes())
    title = paths.root / 'kor-pc98/GPC/TITLE.GPC'
    title_target = unpacked / 'HD/NECRO/NECRO.09B/TITLE.GPC'
    existing_title = paths.korean_unpacked / 'HD/NECRO/NECRO.09B/TITLE.GPC'
    if title.is_file() and not existing_title.is_file(): save_bytes(title_target, title.read_bytes())
    tasks = []
    snapshots = {}
    for lang, relative in selected_lang:
        source = paths.unpacked / relative
        info = lang.with_name(relative.name + '_info.json')
        output = unpacked / relative
        patches = stage / 'patches' / relative.with_name(relative.name + '.patch.json')
        for required in (source, info, lang):
            if not required.is_file(): raise FileNotFoundError(required)
        command = [sys.executable, str(Path(__file__).with_name('encode_mes.py')), str(source),
                   str(info), str(lang), str(output), '--font-table', str(args.font_table),
                   '--patch-manifest', str(patches)]
        command += ['--compact-remap', str(args.compact_remap)] if args.compact_remap else ['--no-compact-remap']
        snapshots[relative.as_posix()] = sha(lang.read_bytes())
        tasks.append((lang, relative, source, output, patches, command))
    errors, results = [], []
    environment = dict(os.environ, PYTHONIOENCODING='utf-8')
    def encode(task):
        result = subprocess.run(task[-1], capture_output=True, text=True,
                                encoding='utf-8', errors='replace', env=environment)
        return task, result
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(tasks))) as executor:
        futures = [executor.submit(encode, task) for task in tasks]
        for index, future in enumerate(as_completed(futures), 1):
            task, result = future.result()
            lang, relative, source, output, patches, command = task
            if result.returncode:
                errors.append({'resource': relative.as_posix(), 'error': result.stderr or result.stdout})
            else:
                encoded = output.read_bytes()
                patch = read_json(patches)
                verify_patch_manifest(source.read_bytes(), encoded, patch)
                if sha(lang.read_bytes()) != snapshots[relative.as_posix()]:
                    raise ValueError(f'Translation changed while building: {lang}')
                results.append({'resource': relative.as_posix(), 'original_size': source.stat().st_size,
                                'encoded_size': len(encoded), 'replacements': len(patch['replacements']),
                                'sha256': sha(encoded), 'lang_sha256': snapshots[relative.as_posix()]})
            if index % 25 == 0 or index == len(tasks):
                print(f'Encoded {index}/{len(tasks)}; errors={len(errors)}', flush=True)
    report = {'files': len(tasks), 'successes': sorted(results, key=lambda row: row['resource']),
              'errors': errors, 'unpacked_root': str(paths.korean_unpacked), 'stage': str(stage)}
    write_json(stage / 'encoding-report.json', report)
    if errors:
        print(json.dumps(errors, ensure_ascii=False, indent=2))
        return 1
    container_report, generated = repack(paths.original, unpacked, packed, manifest)
    for root, target in ((unpacked, paths.korean_unpacked), (packed, paths.korean)):
        for source in root.rglob('*'):
            if source.is_file(): save_bytes(target / source.relative_to(root), source.read_bytes())
    generated['source_root'] = paths.korean.name
    write_json(paths.korean_unpacked / 'container-manifest.json', generated)
    write_json(paths.korean_unpacked / 'source-container-manifest.json', manifest)
    for path in (paths.scripts / 'encoding-report.json', paths.korean_unpacked / 'encoding-report.json'):
        write_json(path, report)
    for container in container_report['changed_containers']:
        for entry in container['entries']:
            entry['source'] = str(paths.korean_unpacked / Path(entry['source']).relative_to(unpacked))
    write_json(paths.korean / 'container-build-report.json', container_report)
    build_boot(paths.root)
    if not args.no_dosbox_x: deploy(paths.root)
    print(f"Built {len(results)} MES and {container_report['container_count']} containers; "
          f"runtime deployed={not args.no_dosbox_x}")
    return 0

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
