"""Verify reusable JSON translations against the currently encoded Korean MES."""
from difflib import SequenceMatcher
from pathlib import Path

from .common import read_json, write_json, sha, FONT_TABLE, COMPACT_REMAP
from .encode_mes import encode_file

def decode_korean(raw, table):
    output = []
    index = 0
    while index < len(raw):
        if raw[index:index + 3] == b'\x21\x20\x00':
            output.append(' '); index += 3; continue
        pair = raw[index:index + 2].hex().upper()
        if index + 1 < len(raw) and pair in table:
            output.append(table[pair]); index += 2; continue
        key = f'{raw[index]:02X}'
        if key not in table:
            raise ValueError(f'Unknown text/control byte {key}')
        output.append(table[key]); index += 1
    return ''.join(output)

def mapped_offset(position, operations):
    for kind, a, b, c, d in operations:
        if a <= position <= b:
            if kind == 'equal': return c + position - a
            if position == a: return c
            if position == b: return d
    raise ValueError('The text span boundary cannot be aligned')

def audit_translations(paths, font=FONT_TABLE, remap=COMPACT_REMAP):
    directory = paths.cache / 'baseline-audit'
    directory.mkdir(parents=True, exist_ok=True)
    table = read_json(font)
    results = []
    recoveries = []
    for lang in sorted((paths.root / 'script-pc98/MES').glob('*.MES_lang.json')):
        name = lang.name.removesuffix('_lang.json')
        source = paths.root / 'jpn-pc98/MES' / name
        actual_path = paths.root / 'kor-pc98/MES' / name
        info = lang.with_name(name + '_info.json')
        row = {'name': name, 'lang_json_sha256': sha(lang.read_bytes())}
        if not all(path.is_file() for path in (source, actual_path, info)):
            row['result'] = 'missing_source'; results.append(row); continue
        actual = actual_path.read_bytes()
        row['actual_sha256'] = sha(actual)
        expected_path = directory / name
        patch_path = directory / (name + '.patch.json')
        try:
            encode_file(source, info, lang, expected_path, font, remap, patch_path)
            expected = expected_path.read_bytes()
            row['expected_sha256'] = sha(expected)
            row['result'] = 'matches_korean_mes' if expected == actual else 'differs_from_korean_mes'
            checks = []
            matcher = SequenceMatcher(None, expected, actual, autojunk=False) if expected != actual else None
            blocks = matcher.get_matching_blocks() if matcher else []
            operations = matcher.get_opcodes() if matcher else []
            cursor = out_cursor = 0
            for patch in read_json(patch_path)['replacements']:
                begin = out_cursor + patch['start'] - cursor
                end = begin + len(bytes.fromhex(patch['replacement_hex']))
                verified = not matcher or any(block.a <= begin and end <= block.a + block.size for block in blocks)
                check = {'source_start': patch['start'], 'source_end': patch['end'],
                         'output_start': begin, 'output_end': end, 'binary_verified': verified}
                checks.append(check)
                if not verified:
                    try:
                        actual_begin = mapped_offset(begin, operations)
                        actual_end = mapped_offset(end, operations)
                        payload = actual[actual_begin:actual_end]
                        translation = decode_korean(payload, table)
                        recoveries.append({'mes': name, 'source_start': patch['start'],
                                           'source_end': patch['end'], 'actual_start': actual_begin,
                                           'actual_end': actual_end, 'actual_hex': payload.hex(),
                                           'translation': translation, 'korean_mes_sha256': sha(actual)})
                    except (KeyError, ValueError):
                        pass
                cursor, out_cursor = patch['end'] + 1, end
            row['entry_checks'] = checks
        except Exception as error:
            row.update(result='encoder_error', error=str(error))
        results.append(row)
    write_json(directory / 'audit.json', results)
    write_json(paths.scripts / 'actual-mes-translations.json', recoveries)
    return {row['name'].casefold(): row for row in results}, recoveries
