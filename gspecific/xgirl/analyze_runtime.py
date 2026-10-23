"""Unwrap X-Girl OVL's final RETF wrapper and save entry disassemblies."""

import argparse
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_16
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.x86_const import UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_DS, UC_X86_REG_ES


def unpack_ovl(source: Path, output: Path) -> dict:
    data = source.read_bytes()
    word = lambda offset: struct.unpack_from('<H', data, offset)[0]
    image = data[word(8) * 16:]
    tail = b'\x33\xff\x33\xf6\x33\xd2\x33\xc9\x33\xdb\x33\xc0\xcb'
    entry = word(0x16) * 16 + word(0x14)
    finish = image.find(tail, entry)
    if finish < 0 or image.find(tail, finish + 1) >= 0:
        raise ValueError('expected unique X-Girl OVL RETF wrapper')
    stop = 0x20000 + finish + len(tail) - 1
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 0x100000)
    uc.mem_write(0x20000, image)
    for register, value in [(UC_X86_REG_CS, 0x2000 + word(0x16)), (UC_X86_REG_IP, word(0x14)), (UC_X86_REG_SS, 0x2000 + word(0x0e)), (UC_X86_REG_SP, word(0x10)), (UC_X86_REG_DS, 0x1ff0), (UC_X86_REG_ES, 0x1ff0)]:
        uc.reg_write(register, value)
    result = {}
    def hook(machine, address, size, _):
        if address == stop:
            stack = (machine.reg_read(UC_X86_REG_SS) << 4) + machine.reg_read(UC_X86_REG_SP)
            ip, cs = struct.unpack('<HH', bytes(machine.mem_read(stack, 4)))
            result.update(entry_after_unpack=f'{cs - 0x2000:04X}:{ip:04X}', raw_size=65536)
            machine.emu_stop()
    def interrupt(machine, number, _):
        raise RuntimeError(f'unexpected interrupt {number:02X}')
    uc.hook_add(UC_HOOK_CODE, hook)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    uc.emu_start(0x20000 + entry, 0, count=2000000)
    if not result:
        raise ValueError('OVL wrapper did not reach expected RETF')
    output.write_bytes(bytes(uc.mem_read(0x20000, 65536)))
    output.with_suffix('.raw.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    workspace = parser.parse_args().workspace.resolve()
    reverse = workspace / 'reverse'
    result = unpack_ovl(reverse / 'XGIRL.OVL.dec', reverse / 'XGIRL.OVL.raw')
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    targets = [('XGIRL.COM', (workspace / 'jpn-pc98/XGIRL.COM').read_bytes(), 0, 0x100)]
    for name in ['XGIRL.OV1', 'XGIRL.OVL']:
        info = json.loads((reverse / (name + '.raw.json')).read_text(encoding='utf-8'))
        cs, ip = [int(value, 16) for value in info['entry_after_unpack'].split(':')]
        targets.append((name, (reverse / (name + '.raw')).read_bytes(), cs * 16 + ip, cs * 16 + ip))
    for name, raw, start, address in targets:
        text = '\n'.join(f'{i.address:05X}  {i.bytes.hex(" ").upper():<30} {i.mnemonic:<8} {i.op_str}' for i in md.disasm(raw[start:start + 0x800], address))
        (reverse / (name + '.entry.asm')).write_text(text + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
