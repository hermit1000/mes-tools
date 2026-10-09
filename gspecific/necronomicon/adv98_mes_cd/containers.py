"""Read and rebuild the CD name/offset/metadata container format."""
from pathlib import Path
import struct

from .common import read_json, write_json, save_bytes, sha

def parse_container(data):
    entries = []
    position = 0
    while position + 16 <= len(data):
        name_bytes = data[position:position + 12].split(b'\0')[0]
        if not name_bytes:
            break
        name = name_bytes.decode('cp932')
        if any(character in name for character in '/\\:<>"|?*'):
            raise ValueError(f'Unsafe resource name: {name!r}')
        entries.append({'entry_index': len(entries), 'name': name, 'name_hex': name_bytes.hex(),
                        'offset': struct.unpack_from('<I', data, position + 12)[0]})
        position += 16
    if not entries or position + 16 > len(data):
        raise ValueError('Invalid container directory')
    if struct.unpack_from('<I', data, position + 12)[0] != len(data):
        raise ValueError('Container end offset does not match its size')
    first = entries[0]['offset']
    if first != 20 * len(entries) + 16:
        raise ValueError('Unexpected container metadata layout')
    for index, entry in enumerate(entries):
        end = entries[index + 1]['offset'] if index + 1 < len(entries) else len(data)
        if not first <= entry['offset'] <= end <= len(data):
            raise ValueError('Invalid resource offset')
        entry['size'] = end - entry['offset']
        entry['sha256'] = sha(data[entry['offset']:end])
    return entries, first, position

def extract(original, output):
    original, output = Path(original), Path(output)
    containers = []
    for path in sorted((original / 'HD').rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(original)
        if path.suffix.upper() in ('.INI', '.TXT'):
            save_bytes(output / relative, path.read_bytes())
            continue
        data = path.read_bytes()
        entries, first, terminator = parse_container(data)
        seen = set()
        for entry in entries:
            folder = relative
            if entry['name'].casefold() in seen:
                folder = folder / '_duplicates' / f"{entry['entry_index']:04d}"
            seen.add(entry['name'].casefold())
            target = folder / entry['name'].upper()
            entry['unpacked_path'] = target.as_posix()
            save_bytes(output / target, data[entry['offset']:entry['offset'] + entry['size']])
        containers.append({'container_path': relative.as_posix(), 'size': len(data),
                           'sha256': sha(data), 'first_data_offset': first,
                           'table_terminator_offset': terminator, 'entries': entries})
    for path in (original / 'FD').glob('*'):
        if path.is_file(): save_bytes(output / 'FD' / path.name, path.read_bytes())
    manifest = {'format': 'necronomicon-cd-container-manifest-v1',
                'source_root': original.name, 'containers': containers}
    write_json(output / 'container-manifest.json', manifest)
    return manifest

def repack(original, modified, output, manifest):
    original, modified, output = Path(original), Path(modified), Path(output)
    changed = []
    generated = []
    paths = {container['container_path'] for container in manifest['containers']}
    for path in (original / 'HD').rglob('*'):
        if not path.is_file(): continue
        relative = path.relative_to(original)
        if relative.as_posix() not in paths:
            override = modified / relative
            save_bytes(output / relative, (override if override.is_file() else path).read_bytes())
    for container in manifest['containers']:
        relative = Path(container['container_path'])
        data = (original / relative).read_bytes()
        if sha(data) != container['sha256']:
            raise ValueError(f'Original container changed: {relative}')
        records, first, terminator = parse_container(data)
        if len(records) != len(container['entries']):
            raise ValueError(f'Manifest entry count changed: {relative}')
        header = bytearray(data[:first])
        payloads = []
        modifications = []
        position = first
        new_records = []
        for entry, record in zip(container['entries'], records):
            if entry['offset'] != record['offset'] or entry['name_hex'] != record['name_hex']:
                raise ValueError(f'Manifest no longer matches {relative}')
            old = data[entry['offset']:entry['offset'] + entry['size']]
            if sha(old) != entry['sha256']:
                raise ValueError(f'Manifest resource changed: {relative}/{entry["name"]}')
            override = modified / entry['unpacked_path']
            payload = override.read_bytes() if override.is_file() else old
            struct.pack_into('<I', header, entry['entry_index'] * 16 + 12, position)
            new_records.append(dict(entry, offset=position, size=len(payload), sha256=sha(payload)))
            position += len(payload)
            payloads.append(payload)
            if payload != old:
                modifications.append({'name': entry['name'], 'entry_index': entry['entry_index'],
                                      'original_size': len(old), 'new_size': len(payload),
                                      'source': str(override)})
        struct.pack_into('<I', header, terminator + 12, position)
        rebuilt = bytes(header) + b''.join(payloads)
        assert len(rebuilt) == position
        assert rebuilt[terminator + 16:first] == data[terminator + 16:first]
        restored, _, _ = parse_container(rebuilt)
        for entry, payload in zip(restored, payloads):
            assert rebuilt[entry['offset']:entry['offset'] + entry['size']] == payload
        save_bytes(output / relative, rebuilt)
        generated.append(dict(container, size=len(rebuilt), sha256=sha(rebuilt), entries=new_records))
        if modifications:
            changed.append({'container': relative.as_posix(), 'original_size': len(data),
                            'new_size': len(rebuilt), 'entries': modifications, 'sha256': sha(rebuilt)})
        else:
            assert rebuilt == data
    for path in (modified / 'FD').glob('*'):
        if path.is_file(): save_bytes(output / 'FD' / path.name, path.read_bytes())
    report = {'container_count': len(generated), 'changed_containers': changed}
    write_json(output / 'container-build-report.json', report)
    return report, {'format': manifest['format'], 'source_root': output.name, 'containers': generated}
