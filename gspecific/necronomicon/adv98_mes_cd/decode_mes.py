"""Extract CD containers as needed, then create info/lang JSON and reuse translations."""
from pathlib import Path
import argparse
import json
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gspecific.necronomicon.adv98_mes_cd.common import DEFAULT_WORKSPACE, Paths, read_json
from gspecific.necronomicon.adv98_mes_cd.containers import extract
from gspecific.necronomicon.adv98_mes_cd.prepare import prepare

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path, nargs='?', default=DEFAULT_WORKSPACE)
    parser.add_argument('--output', type=Path, help='JSON root; defaults to script-pc98-cd')
    parser.add_argument('--files', nargs='+', metavar='MES', help='Basenames or HD-relative resource paths')
    parser.add_argument('--no-reuse', action='store_true', help='Do not import existing non-CD translations')
    parser.add_argument('--refresh-unpacked', action='store_true', help='Re-extract original containers')
    args = parser.parse_args()
    paths = Paths(args.workspace.resolve())
    if args.refresh_unpacked or not (paths.unpacked / 'container-manifest.json').is_file():
        extract(paths.original, paths.unpacked)
    manifest = read_json(paths.unpacked / 'container-manifest.json')
    available = [Path(entry['unpacked_path']) for container in manifest['containers']
                 for entry in container['entries'] if entry['name'].lower().endswith('.mes')]
    if args.files:
        for name in args.files:
            if not any(path.name.casefold() == name.casefold() or
                       path.as_posix().casefold() == name.replace('\\', '/').casefold() for path in available):
                parser.error(f'MES not found: {name}')
    report = prepare(paths.root, output=args.output, names=args.files, reuse=not args.no_reuse)
    print(json.dumps({key: value for key, value in report.items() if key != 'files'},
                     ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
