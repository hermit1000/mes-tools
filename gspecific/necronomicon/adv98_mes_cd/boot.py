"""Preserve floppy saves while updating the HDD startup files."""
from pathlib import Path
import struct

from .common import Paths


def build_boot(workspace, output=None):
    paths = Paths(Path(workspace).resolve())
    ROOT = paths.root
    SOURCE = paths.runtime / 'FD'
    IMAGE = Path(output).resolve() if output else paths.korean / 'FD/Necronomicon-CD-HDD.hdm'
    OUTPUT = IMAGE.parent
    OUTPUT.mkdir(parents=True, exist_ok=True)
    base = IMAGE if IMAGE.exists() else ROOT / 'cd' / 'Necronomicon (CD Boot disk) [installed].hdm'
    disk = bytearray(base.read_bytes())
    bps = struct.unpack_from('<H', disk, 11)[0]
    spc = disk[13]
    reserved = struct.unpack_from('<H', disk, 14)[0]
    fat_count = disk[16]
    root_count = struct.unpack_from('<H', disk, 17)[0]
    fat_sectors = struct.unpack_from('<H', disk, 22)[0]
    root_start = (reserved + fat_count * fat_sectors) * bps
    data_start = root_start + ((root_count * 32 + bps - 1) // bps) * bps
    cluster_size = bps * spc
    max_cluster = (len(disk) - data_start) // cluster_size + 1
    assert bps == 1024 and max_cluster < 4085, 'Expected the PC-98 FAT12 floppy'
    fat = bytearray(disk[reserved * bps:(reserved + fat_sectors) * bps])

    def fat_get(cluster):
        index = cluster + cluster // 2
        value = int.from_bytes(fat[index:index + 2], 'little')
        return value >> 4 if cluster % 2 else value & 0xfff

    def fat_set(cluster, value):
        index = cluster + cluster // 2
        old = int.from_bytes(fat[index:index + 2], 'little')
        new = (old & 0xf) | (value << 4) if cluster % 2 else (old & 0xf000) | value
        fat[index:index + 2] = new.to_bytes(2, 'little')

    def write_file(label, payload):
        slots = range(root_start, root_start + root_count * 32, 32)
        entry = next((o for o in slots if disk[o:o + 11] == label), None)
        chain = []
        if entry is None:
            entry = next(o for o in slots if disk[o] in (0, 229))
            disk[entry:entry + 32] = bytes(32)
            disk[entry:entry + 11] = label
            disk[entry + 11] = 0x20
        else:
            cluster = struct.unpack_from('<H', disk, entry + 26)[0]
            while 2 <= cluster < 0xff8:
                assert cluster <= max_cluster and cluster not in chain
                chain.append(cluster)
                cluster = fat_get(cluster)
        needed = (len(payload) + cluster_size - 1) // cluster_size
        while len(chain) < needed:
            cluster = next(c for c in range(2, max_cluster + 1) if fat_get(c) == 0)
            fat_set(cluster, 0xfff)
            chain.append(cluster)
        for index, cluster in enumerate(chain):
            fat_set(cluster, chain[index + 1] if index + 1 < len(chain) else 0xfff)
            start = data_start + (cluster - 2) * cluster_size
            chunk = payload[index * cluster_size:(index + 1) * cluster_size]
            disk[start:start + cluster_size] = chunk.ljust(cluster_size, b'\0')
        struct.pack_into('<H', disk, entry + 26, chain[0])
        struct.pack_into('<I', disk, entry + 28, len(payload))
        rebuilt = b''.join(disk[data_start + (c - 2) * cluster_size:
                               data_start + (c - 1) * cluster_size] for c in chain)
        assert rebuilt[:len(payload)] == payload

    files = [('AUTOEXEC.BAT', b'AUTOEXECBAT'),
             ('SHELL21.CNF', b'SHELL21 CNF')]
    for name, label in files:
        write_file(label, (SOURCE / name).read_bytes())
    for index in range(fat_count):
        start = (reserved + index * fat_sectors) * bps
        disk[start:start + len(fat)] = fat
    temporary = IMAGE.with_suffix('.hdm.tmp')
    temporary.write_bytes(disk)
    temporary.replace(IMAGE)
    for name, _ in files:
        (OUTPUT / name).write_bytes((SOURCE / name).read_bytes())
    return IMAGE
