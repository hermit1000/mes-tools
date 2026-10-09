"""Recognize Necronomicon CD audio selectors before readable text grouping."""
import hashlib
from pathlib import Path

from gspecific.necronomicon.adv98_mes import decode_mes as base
from modules.adv_common.tokens import make_token, verify_tokens

def decode_tokens(data, *, structured_ascii=True):
    tokens = base.decode_tokens(data, structured_ascii=structured_ascii)
    result = []
    index = 0
    while index < len(tokens):
        current = tokens[index]
        previous = result[-1] if result else None
        offset = current['offset']
        # In the verified 10 18 <byte> D0 cd pattern, the shared lexer can
        # consume D0 as an 08/0C/0D parameter. Restore the audio boundary,
        # retaining the preceding byte without guessing its meaning.
        if (previous and previous['type'] == 'control'
                and len(previous['bytes']) == 2
                and previous['bytes'][0] in (0x08, 0x0C, 0x0D)
                and previous['bytes'][1] == 0xD0
                and data[offset - 4:offset - 2] == b'\x10\x18'
                and previous['offset'] + previous['size'] == offset
                and data[offset:offset + 2].lower() == b'cd'
                and index + 1 < len(tokens)
                and current['type'] == 'text' and current['size'] == 1
                and tokens[index + 1]['type'] == 'text'
                and tokens[index + 1]['size'] == 1
                and tokens[index + 1]['offset'] == offset + 1):
            result.pop()
            preceding_byte = previous['bytes'][0]
            result.append(make_token(previous['offset'], 1, bytes([preceding_byte]), 'control',
                                     f'CONTROL_{preceding_byte:02X}',
                                     syntax='before-confirmed-cd-audio-command'))
            result.append(make_token(offset - 1, 1, b'\xD0', 'command', 'AUDIO'))
            previous = result[-1]
        if (previous and previous['type'] == 'command'
                and previous['bytes'] == [0xD0]
                and previous['offset'] + previous['size'] == offset
                and data[offset:offset + 2].lower() == b'cd'
                and index + 1 < len(tokens)
                and current['type'] == 'text' and current['size'] == 1
                and tokens[index + 1]['type'] == 'text'
                and tokens[index + 1]['size'] == 1
                and tokens[index + 1]['offset'] == offset + 1):
            result.append(make_token(offset, 2, data[offset:offset + 2], 'keyword', 'cd'))
            index += 2
        else:
            result.append(current)
            index += 1
    verify_tokens(data, result)
    return result

def decode_document(source: Path, source_name: str, *, structured_ascii=True):
    data = source.read_bytes()
    tokens = decode_tokens(data, structured_ascii=structured_ascii)
    records = [base.repair_menu_flag_prefix(
        base.repair_condition_prefix(base.repair_speaker_boundary(record), data), data)
        for record in base.make_records(tokens)]
    if source_name.upper() == 'ND_04B.MES':
        for record in records:
            if record.get('type') != 'text':
                continue
            raw = bytes.fromhex(record['raw_hex'])
            start = int(record['offset'], 16)
            if raw.startswith(b'\x9B\x81\x97') and start > 0 and data[start - 1] == 0x0E:
                # This identical source span already has a verified prefix
                # in the non-CD metadata. Keep the parameter and delimiter.
                record['encoding_prefix_hex'] = '9B 81 97'
                record['original'] = base.decode_adv98_bytes(raw[3:])
    candidates = [record for record in records if record.get('type') == 'text'
                  and record.get('translation_candidate') and record.get('original', '').strip()]
    selectors = [argument for record in records if record.get('opcode') == 'D0'
                 for argument in record['arguments']
                 if argument['type'] == 'keyword' and argument['value'] == 'cd']
    return {'format': 'necronomicon-adv98-mes-info-v1', 'language': 'jpn',
            'source': source_name, 'source_size': len(data),
            'source_sha256': hashlib.sha256(data).hexdigest(),
            'structured_ascii': structured_ascii,
            'warning': 'CD-aware lexical decode; review unknown command operands before translation.',
            'text_record_count': sum(record.get('type') == 'text' for record in records),
            'translation_candidate_count': len(candidates),
            'gaiji_count': sum(record.get('type') == 'gaiji' for record in records),
            'cd_audio_selector_count': len(selectors), 'records': records}
