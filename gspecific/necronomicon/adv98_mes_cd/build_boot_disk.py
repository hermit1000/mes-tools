"""Update the two startup files inside the CD/HDD boot floppy."""
from pathlib import Path
import argparse
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gspecific.necronomicon.adv98_mes_cd.common import DEFAULT_WORKSPACE
from gspecific.necronomicon.adv98_mes_cd.boot import build_boot
from gspecific.necronomicon.adv98_mes_cd.runtime import check_neko_closed

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path, nargs='?', default=DEFAULT_WORKSPACE)
    parser.add_argument('--output', type=Path, help='Default: kor-pc98-cd/FD/Necronomicon-CD-HDD.hdm')
    args = parser.parse_args()
    check_neko_closed()
    print(build_boot(args.workspace, args.output))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

