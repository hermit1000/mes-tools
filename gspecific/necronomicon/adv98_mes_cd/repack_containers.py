"""Repack already encoded CD resources, with an optional runtime deployment."""
from pathlib import Path
import argparse
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gspecific.necronomicon.adv98_mes_cd.common import DEFAULT_WORKSPACE, Paths, read_json, write_json
from gspecific.necronomicon.adv98_mes_cd.containers import repack
from gspecific.necronomicon.adv98_mes_cd.runtime import deploy

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path, nargs='?', default=DEFAULT_WORKSPACE)
    parser.add_argument('--modified', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--deploy', action='store_true')
    args = parser.parse_args()
    paths = Paths(args.workspace.resolve())
    modified = args.modified or paths.korean_unpacked
    output = args.output or paths.korean
    report, generated = repack(paths.original, modified, output,
                              read_json(paths.unpacked / 'container-manifest.json'))
    write_json(Path(modified) / 'container-manifest.json', generated)
    if args.deploy: deploy(paths.root)
    print(f"Repacked {report['container_count']} containers; changed={len(report['changed_containers'])}")
    return 0

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())

