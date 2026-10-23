"""Index X-Girl speakers using literal name lines and file-local name macros."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from .prepare import write_json


NAME_LINE = re.compile(r'「([^」\r\n]{1,24})」')


def argument(record: dict, opcode: str) -> int | None:
    args = record.get('arguments', [])
    if record.get('opcode') == opcode and len(args) == 1 and isinstance(args[0].get('value'), int):
        return args[0]['value']
    return None


def definitions(records: list[dict]) -> tuple[list[dict], set[int]]:
    catalog, excluded = [], set()
    for index, record in enumerate(records):
        number = argument(record, 'B9')
        if number is None or index + 1 >= len(records) or records[index + 1].get('value') != 'BOUNDARY_A2':
            continue
        depth, end = 0, None
        for j in range(index + 1, len(records)):
            boundary = records[j].get('value')
            if boundary == 'BOUNDARY_A2':
                depth += 1
            elif boundary == 'BOUNDARY_A3':
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:
            continue
        excluded.update(range(index, end + 1))
        body = records[index + 2:end]
        name = None
        if len(body) == 2 and body[0].get('type') == 'text' and body[1].get('value') == 'CONTROL_A5':
            match = NAME_LINE.fullmatch(body[0]['original'])
            if match:
                name = match[1]
        catalog.append({'macro_id': number, 'definition_offset': record['offset'], 'end_offset': records[end]['offset'], 'kind': 'name_line' if name else 'other', 'speaker': name, 'index': index, 'end_index': end, 'name_offset': body[0]['offset'] if name else None})
    return catalog, excluded


def analyze_document(info: dict, lang: dict) -> dict:
    records = info['records']
    macros, excluded = definitions(records)
    entries = {e['offset']: e for e in lang['entries']}
    groups, unresolved = [], []
    covered, labels = set(), set()
    for i, record in enumerate(records):
        if i in excluded:
            continue
        name = None
        method = None
        definition = None
        start = None
        match = NAME_LINE.fullmatch(record.get('original', ''))
        if match and i + 1 < len(records) and records[i + 1].get('value') == 'CONTROL_A5':
            name, method, start = match[1], 'literal_name_line', i + 2
            labels.add(record['offset'])
        called = argument(record, 'BA')
        if called is not None:
            prior = [m for m in macros if m['macro_id'] == called and m['end_index'] < i]
            if prior:
                definition = prior[-1]
                if definition['kind'] == 'name_line':
                    name, method, start = definition['speaker'], 'file_local_name_macro', i + 1
        if name is None:
            continue
        parts, intervening, terminated = [], [], None
        for j in range(start, len(records)):
            item = records[j]
            if j in excluded:
                terminated = 'macro_definition'
                break
            if item.get('opcode') in {'AB', 'AA', 'A6', 'B1'} or item.get('type') == 'end':
                terminated = item.get('opcode', item.get('value'))
                break
            if NAME_LINE.fullmatch(item.get('original', '')) and j + 1 < len(records) and records[j + 1].get('value') == 'CONTROL_A5':
                terminated = 'next_name_line'
                break
            next_call = argument(item, 'BA')
            if next_call is not None:
                next_defs = [m for m in macros if m['macro_id'] == next_call and m['end_index'] < j]
                if next_defs and next_defs[-1]['kind'] == 'name_line':
                    terminated = 'next_name_macro'
                    break
            if item.get('type') == 'boundary' or str(item.get('value', '')).startswith('BOUNDARY_') or item.get('value') in {'CONTROL_FULLWIDTH_AT', 'BLOCK_OPEN', 'BLOCK_CLOSE'}:
                terminated = 'flow_boundary'
                break
            if item.get('type') == 'text' and item['offset'] in entries:
                parts.append({'offset': item['offset'], 'original': item['original']})
            else:
                intervening.append({'offset': item['offset'], 'kind': item.get('opcode', item.get('value', item['type']))})
        if not parts:
            unresolved.append({'offset': record['offset'], 'speaker': name, 'reason': 'name marker without directly reachable body', 'termination': terminated, 'method': method})
            continue
        group = {'id': f"{info['source']}:{record['offset']}", 'source': info['source'], 'speaker': name, 'method': method, 'confidence': 'structural' if method == 'literal_name_line' else 'structural_local_macro', 'speaker_offset': record['offset'], 'body': parts, 'intervening': intervening, 'termination': terminated, 'runtime_verified': False}
        if method == 'file_local_name_macro':
            group.update(macro_id=called, definition_offset=definition['definition_offset'], name_offset=definition['name_offset'], caveat='Nearest preceding textual definition; branch execution not simulated.')
        for part in parts:
            if part['offset'] in covered:
                raise ValueError(f"overlapping speaker assignment: {info['source']}:{part['offset']}")
            covered.add(part['offset'])
        groups.append(group)
    definition_offsets = {records[i]['offset'] for i in excluded if records[i].get('type') == 'text'}
    unassigned = [{'offset': e['offset'], 'original': e['original'], 'classification': 'macro_definition' if e['offset'] in definition_offsets else 'speaker_label' if e['offset'] in labels else 'unassigned_text'} for e in lang['entries'] if e['offset'] not in covered]
    return {'source': info['source'], 'source_sha256': info['source_sha256'], 'groups': groups, 'unresolved_markers': unresolved, 'macro_definitions': [{k: v for k, v in m.items() if k not in {'index', 'end_index'}} for m in macros], 'unassigned': unassigned}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    output = workspace / 'speaker-analysis'
    if output.exists():
        raise FileExistsError(output)
    all_groups, documents = [], []
    source_hashes = {}
    for info_path in sorted((workspace / 'script-pc98').rglob('*_info.json')):
        lang_path = info_path.with_name(info_path.name.replace('_info.json', '_lang.json'))
        source_hashes[str(info_path)] = hashlib.sha256(info_path.read_bytes()).hexdigest()
        source_hashes[str(lang_path)] = hashlib.sha256(lang_path.read_bytes()).hexdigest()
        info = json.loads(info_path.read_text(encoding='utf-8'))
        lang = json.loads(lang_path.read_text(encoding='utf-8'))
        document = analyze_document(info, lang)
        documents.append(document)
        all_groups.extend(document['groups'])
        write_json(output / 'files' / (info['source'] + '.json'), document)
        lines = []
        for group in document['groups']:
            lines.append(f"[{group['source']}:{group['speaker_offset']}] {group['speaker']} ({group['method']})\n" + '\n'.join(f"{p['offset']}: {p['original']}" for p in group['body']))
        target = output / 'dialogues-by-file' / (info['source'] + '.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('\n\n'.join(lines) + '\n', encoding='utf-8')
    speakers = defaultdict(list)
    for group in all_groups:
        speakers[group['speaker']].append(group)
    catalog = []
    for number, (name, groups) in enumerate(sorted(speakers.items(), key=lambda item: (-len(item[1]), item[0])), 1):
        target = f'{number:02d}.txt'
        catalog.append({'speaker': name, 'group_count': len(groups), 'body_record_count': sum(len(g['body']) for g in groups), 'methods': dict(Counter(g['method'] for g in groups)), 'files': sorted({g['source'] for g in groups}), 'dialogue_file': target})
        root = output / 'dialogues-by-speaker'
        root.mkdir(parents=True, exist_ok=True)
        (root / target).write_text(name + '\n\n' + '\n\n'.join(f"[{g['source']}:{g['speaker_offset']}]\n" + '\n'.join(p['original'] for p in g['body']) for g in groups) + '\n', encoding='utf-8')
    summary = {'speaker_count': len(catalog), 'group_count': len(all_groups), 'body_record_count': sum(len(g['body']) for g in all_groups), 'file_count': len(documents), 'unresolved_marker_count': sum(len(d['unresolved_markers']) for d in documents), 'unassigned_classes': dict(Counter(e['classification'] for d in documents for e in d['unassigned'])), 'methods': dict(Counter(g['method'] for g in all_groups)), 'speakers': catalog, 'translation_modified': False, 'notes': ['Groups are structural links, not proof of runtime branch execution.', 'BA19 is not a universal dialogue opener in X-Girl.', 'No global macro ID to name map is used.', 'Unassigned includes narration, UI, commands misread by the generic lexer, and unresolved dialogue.']}
    write_json(output / 'summary.json', summary)
    write_json(output / 'groups.json', all_groups)
    write_json(output / 'unassigned.json', [{'source': d['source'], **e} for d in documents for e in d['unassigned']])
    for path, expected in source_hashes.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError(f'input changed: {path}')
    print(json.dumps({k: v for k, v in summary.items() if k not in {'speakers', 'notes'}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
