"""Create X-Girl emulator configuration from an existing non-CD workspace."""

import argparse
from pathlib import Path
import re
import shutil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    args = parser.parse_args()
    workspace, reference = args.workspace.resolve(), args.reference.resolve()
    template = (reference / 'ballade-pc98.conf').read_text(encoding='utf-8')
    template = re.sub(r'(?m)^(pc-98 anex86 font\s*=).*$', r'\1 anex86.bmp', template)
    template = template[:template.index('[autoexec]')] + '[autoexec]\n@echo off\nmount c kor-pc98-dosbox-x\nc:\nXGIRL.COM\n'
    outputs = {
        'xgirl-pc98.conf': template,
        'xgirl-jpn-pc98.conf': template.replace('mount c kor-pc98-dosbox-x', 'mount c jpn-pc98'),
        'xgirl-pc98.bat': '@echo off\r\ncd /d "%~dp0"\r\nstart "" DOSBox-x -noconsole -conf "xgirl-pc98.conf"\r\n',
        'xgirl-jpn-pc98.bat': '@echo off\r\ncd /d "%~dp0"\r\nstart "" DOSBox-x -noconsole -conf "xgirl-jpn-pc98.conf"\r\n',
    }
    for name in outputs:
        if (workspace / name).exists():
            raise FileExistsError(workspace / name)
    for name in ['anex86.bmp', 'ThinDungGeunMo.bmp']:
        target = workspace / name
        if not target.exists():
            shutil.copy2(reference / name, target)
    for name, value in outputs.items():
        (workspace / name).write_text(value, encoding='utf-8', newline='')
    (workspace / 'capture').mkdir(exist_ok=True)
    print('Created original and working-copy launchers. Using Japanese font until translation/font remapping is authorized.')


if __name__ == '__main__':
    main()
