"""Encode one CD MES using the existing, verified ADV98 text encoder."""
from pathlib import Path
import argparse
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gspecific.necronomicon.adv98_mes_cd.common import FONT_TABLE, COMPACT_REMAP, sha, read_json
from gspecific.necronomicon.adv98_mes.encode_mes import main as core_encode
from modules.adv_common.patches import verify_patch_manifest

def encode_file(source, info, lang, output, font_table=FONT_TABLE,
                compact_remap=COMPACT_REMAP, manifest=None):
    before = sha(Path(lang).read_bytes())
    manifest = Path(manifest) if manifest else Path(output).with_suffix('.MES.patch.json')
    arguments = ['encode_mes', str(source), str(info), str(lang), str(output), str(font_table),
                 '--patch-manifest', str(manifest)]
    if compact_remap:
        arguments += ['--compact-remap', str(compact_remap)]
    saved = sys.argv
    try:
        sys.argv = arguments
        if core_encode() != 0:
            raise ValueError('The core MES encoder failed')
    finally:
        sys.argv = saved
    encoded = Path(output).read_bytes()
    patches = read_json(manifest)
    verify_patch_manifest(Path(source).read_bytes(), encoded, patches)
    if sha(Path(lang).read_bytes()) != before:
        raise ValueError('Translation JSON changed during encoding')
    return {'original_size': Path(source).stat().st_size, 'encoded_size': len(encoded),
            'replacements': len(patches['replacements']), 'sha256': sha(encoded),
            'lang_sha256': before}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('info', type=Path)
    parser.add_argument('lang', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--font-table', type=Path, default=FONT_TABLE)
    parser.add_argument('--compact-remap', type=Path, default=COMPACT_REMAP)
    parser.add_argument('--no-compact-remap', dest='compact_remap', action='store_const', const=None)
    parser.add_argument('--patch-manifest', type=Path)
    args = parser.parse_args()
    encode_file(args.source, args.info, args.lang, args.output, args.font_table,
                args.compact_remap, args.patch_manifest)
    return 0

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())

