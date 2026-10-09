"""CD JSON preparation with verified translation reuse and preserved user edits."""
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import hashlib

from gspecific.necronomicon.adv98_mes.decode_mes import make_lang
from .codec import decode_document
from .display_groups import build_groups
from .common import Paths, read_json, write_json, selected as matches_selection
from .audit import audit_translations


def make_split_recipes(paths):
    baseline = paths.root / 'script-pc98/MES/NM_01B.MES_lang.json'
    sources = list((paths.unpacked / 'HD').rglob('NM_01B.MES'))
    result = []
    if baseline.is_file() and len(sources) == 1:
        info = decode_document(sources[0], 'NM_01B.MES')
        lang = make_lang('NM_01B.MES_info.json', info)
        entries = {entry['id']: entry for entry in lang['overlay_texts']}
        if all(key in entries for key in ('overlay:01560', 'overlay:0157E')):
            first, second = entries['overlay:01560'], entries['overlay:0157E']
            combined = (first['original'] + second['original']).replace('だけのよう', 'だけよう')
            original = read_json(baseline)
            donors = [entry for group in ('dialogue_groups', 'overlay_texts') for entry in original[group]
                      if entry['original'] == combined and ',' in entry.get('translation', '')]
            if len(donors) == 1:
                donor = donors[0]
                cut = donor['translation'].index(',') + 1
                binary = paths.root / 'kor-pc98/MES/NM_01B.MES'
                relative = sources[0].relative_to(paths.unpacked).with_name('NM_01B.MES_lang.json')
                for entry, begin, end in [(first, 0, cut), (second, cut, len(donor['translation']))]:
                    result.append({'target_lang': relative.as_posix(), 'target_id': entry['id'],
                                   'target_original': entry['original'], 'source_json': baseline.relative_to(paths.root).as_posix(),
                                   'source_json_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
                                   'source_id': donor['id'], 'slice_start': begin, 'slice_end': end,
                                   'korean_mes': binary.relative_to(paths.root).as_posix(),
                                   'korean_mes_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()})
    write_json(paths.scripts / 'verified-split-reuse.json', result)
    return {(row['target_lang'], row['target_id']): row for row in result}


def prepare(workspace, *, output=None, names=None, reuse=True):
    paths = Paths(Path(workspace).resolve())
    ROOT = paths.root
    DEST = Path(output).resolve() if output else paths.scripts
    DEST.mkdir(parents=True, exist_ok=True)
    audit_path = paths.cache / "baseline-audit/audit.json"
    audit, actual_translations = audit_translations(paths) if reuse else ({}, [])
    split_recipes = make_split_recipes(paths) if reuse else {}
    local_exact = defaultdict(lambda: defaultdict(list))
    local_raw = defaultdict(lambda: defaultdict(list))
    global_exact = defaultdict(list)
    local_trimmed = defaultdict(lambda: defaultdict(list))
    global_trimmed = defaultdict(list)
    excluded = []
    donor_count = 0
    recovered_from_mes = []

    for path in (sorted((ROOT / 'script-pc98' / 'MES').glob('*.MES_lang.json')) if reuse else []):
        name = path.name[:-10]
        state = audit[name.casefold()]
        if state['result'] not in ('matches_korean_mes', 'differs_from_korean_mes'):
            excluded.append({'source': path.relative_to(ROOT).as_posix(), 'reason': state.get('error', state['result'])})
            continue
        assert hashlib.sha256(path.read_bytes()).hexdigest() == state['lang_json_sha256'], \
            'Baseline translation JSON changed; refresh the Korean MES audit before transfer.'
        binary = ROOT / 'kor-pc98' / 'MES' / name
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == state['actual_sha256']
        document = read_json(path)
        source_info = read_json(path.with_name(name + '_info.json'))
        source_records = {entry['offset']: entry for entry in source_info['records']
                          if entry.get('type') == 'text'}
        for section in ('dialogue_groups', 'overlay_texts'):
            for entry in document.get(section, []):
                original = entry.get('original', '')
                translation = entry.get('translation', '')
                if not original.strip() or not translation.strip():
                    continue
                verification = 'whole_korean_mes'
                if state['result'] != 'matches_korean_mes':
                    offset = int(entry['offset'], 16)
                    patch = next((p for p in state.get('entry_checks', []) if p['source_start'] <= offset <= p['source_end']), None)
                    if translation != '@keep' and (patch is None or not patch['binary_verified']):
                        recovery = next((row for row in actual_translations
                                         if row['mes'].casefold() == name.casefold()
                                         and row['source_start'] <= offset <= row['source_end']), None)
                        if recovery is None:
                            excluded.append({'source': str(path.relative_to(ROOT)), 'id': entry['id'],
                                             'original': original, 'translation': translation,
                                             'reason': 'translation bytes do not match the current Korean MES'})
                            continue
                        actual = binary.read_bytes()
                        assert hashlib.sha256(actual).hexdigest() == recovery['korean_mes_sha256']
                        assert actual[recovery['actual_start']:recovery['actual_end']] == bytes.fromhex(recovery['actual_hex'])
                        recovered_from_mes.append({'source': path.relative_to(ROOT).as_posix(),
                                                   'id': entry['id'], 'json_translation': translation,
                                                   'actual_mes_translation': recovery['translation']})
                        translation = recovery['translation']
                        verification = 'actual_korean_mes_text_span'
                    else:
                        verification = 'equal_translated_span' if patch else 'keep_original'
                donor = {'original': original, 'translation': translation,
                         'json_path': path.relative_to(ROOT).as_posix(), 'id': entry['id'],
                         'korean_mes': binary.relative_to(ROOT).as_posix(),
                         'korean_mes_sha256': state['actual_sha256'], 'verification': verification}
                local_exact[name.casefold()][original].append(donor)
                raw = bytes.fromhex(source_records[entry['offset']]['raw_hex'])
                local_raw[name.casefold()][raw].append(donor)
                global_exact[original].append(donor)
                trimmed = original.strip(' \u3000\t\r\n')
                local_trimmed[name.casefold()][trimmed].append(donor)
                global_trimmed[trimmed].append(donor)
                donor_count += 1

    def choose(candidates):
        translations = {entry['translation'] for entry in candidates}
        return candidates[0] if len(translations) == 1 else None

    manifest = read_json(ROOT / 'jpn-pc98-cd-unpacked' / 'container-manifest.json')
    files = []
    unresolved = []
    counts = Counter()
    matches = Counter()
    cd_audio_selectors = 0
    current_counts = Counter()
    backup_root = paths.cache / 'existing-json-backup'
    for container in manifest['containers']:
        for resource in container['entries']:
            if not resource['name'].lower().endswith('.mes'):
                continue
            relative = Path(resource['unpacked_path'])
            if not matches_selection(relative, names):
                continue
            source = ROOT / 'jpn-pc98-cd-unpacked' / relative
            source_bytes = source.read_bytes()
            assert hashlib.sha256(source_bytes).hexdigest() == resource['sha256']
            info_path = DEST / relative.parent / (relative.name + '_info.json')
            lang_path = DEST / relative.parent / (relative.name + '_lang.json')
            info = decode_document(source, relative.name)
            cd_audio_selectors += info['cd_audio_selector_count']
            info['cd_container'] = container['container_path']
            info['cd_container_entry_index'] = resource['entry_index']
            info['cd_container_offset'] = resource['offset']
            document = make_lang(info_path.name, info)
            cd_records = {record['offset']: record for record in info['records']
                          if record.get('type') == 'text'}
            existing = {}
            if lang_path.exists():
                old_info = read_json(info_path)
                assert old_info['source_sha256'] == info['source_sha256']
                old = read_json(lang_path)
                existing = {entry['id']: entry for section in ('dialogue_groups', 'overlay_texts')
                            for entry in old.get(section, [])}
                for path in (info_path, lang_path):
                    backup = backup_root / path.relative_to(DEST)
                    if not backup.exists():
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        backup.write_bytes(path.read_bytes())
            filename = relative.name.casefold()
            base_filename = filename[:-4].rstrip("'") + '.mes'
            file_counts = Counter()
            for section in ('dialogue_groups', 'overlay_texts'):
                for entry in document[section]:
                    previous = existing.get(entry['id'])
                    if previous and previous.get('translation', '').strip():
                        assert previous['original'] == entry['original']
                        assert previous['offset'] == entry['offset']
                        entry.clear()
                        entry.update(deepcopy(previous))
                        counts['preserved_existing'] += 1
                        file_counts['preserved_existing'] += 1
                        continue
                    original = entry['original']
                    recipe = split_recipes.get((lang_path.relative_to(DEST).as_posix(), entry['id']))
                    if recipe:
                        assert original == recipe['target_original']
                        donor_path = ROOT / recipe['source_json']
                        assert hashlib.sha256(donor_path.read_bytes()).hexdigest() == recipe['source_json_sha256']
                        assert hashlib.sha256((ROOT / recipe['korean_mes']).read_bytes()).hexdigest() == recipe['korean_mes_sha256']
                        donor_doc = read_json(donor_path)
                        donor_entry = next(row for group in ('dialogue_groups', 'overlay_texts')
                                           for row in donor_doc[group] if row['id'] == recipe['source_id'])
                        entry['translation'] = donor_entry['translation'][recipe['slice_start']:recipe['slice_end']]
                        entry['status'] = 'pending: existing translation split for CD layout'
                        entry['translation_source'] = {'json_path': recipe['source_json'], 'id': recipe['source_id'],
                                                       'korean_mes': recipe['korean_mes'],
                                                       'korean_mes_sha256': recipe['korean_mes_sha256'],
                                                       'verification': 'whole_korean_mes',
                                                       'match': 'same_file_split_sentence',
                                                       'character_slice': [recipe['slice_start'], recipe['slice_end']]}
                        counts['reused_translation'] += 1
                        file_counts['reused_translation'] += 1
                        matches['same_file_split_sentence'] += 1
                        continue
                    trimmed = original.strip(' \u3000\t\r\n')
                    candidate_sets = [('same_file_exact', local_exact[base_filename].get(original, [])),
                                      ('same_file_identical_source_bytes', local_raw[base_filename].get(
                                          bytes.fromhex(cd_records[entry['offset']]['raw_hex']), [])),
                                      ('same_file_outer_whitespace', local_trimmed[base_filename].get(trimmed, [])),
                                      ('global_exact', global_exact.get(original, [])),
                                      ('global_outer_whitespace', global_trimmed.get(trimmed, []))]
                    ambiguous = False
                    selected = None
                    match = None
                    for match_kind, candidates in candidate_sets:
                        if not candidates:
                            continue
                        selected = choose(candidates)
                        if selected is None:
                            ambiguous = True
                            break
                        match = match_kind
                        break
                    if selected:
                        entry['translation'] = selected['translation']
                        entry['status'] = 'passed' if selected['translation'] == '@keep' else 'pending: reused translation; review CD context'
                        entry['translation_source'] = {key: selected[key] for key in
                            ('json_path', 'id', 'korean_mes', 'korean_mes_sha256', 'verification')}
                        entry['translation_source']['match'] = match
                        category = 'kept_original' if selected['translation'] == '@keep' else 'reused_translation'
                        counts[category] += 1
                        file_counts[category] += 1
                        matches[match] += 1
                    else:
                        category = 'ambiguous' if ambiguous else 'no_match'
                        counts[category] += 1
                        file_counts[category] += 1
                        unresolved.append({'path': lang_path.relative_to(DEST).as_posix(),
                                           'id': entry['id'], 'offset': entry['offset'],
                                           'original': original, 'reason': category})
            entries = [entry for section in ('dialogue_groups', 'overlay_texts') for entry in document[section]]
            for entry in entries:
                translation = entry.get('translation', '')
                current_counts['kept_original' if translation == '@keep' else
                               'translated' if translation.strip() else 'untranslated'] += 1
            assert len({entry['offset'] for entry in entries}) == len(entries), str(source)
            records = {record['offset']: record for record in info['records'] if record.get('type') == 'text'}
            for entry in entries:
                record = records[entry['offset']]
                assert record['original'] == entry['original']
                start, end = int(record['offset'], 16), int(record['end'], 16)
                assert source_bytes[start:end + 1] == bytes.fromhex(record['raw_hex'])
            groups = build_groups(info, document)
            document['display_groups'] = groups
            write_json(info_path, info)
            write_json(lang_path, document)
            files.append({'source': relative.as_posix(), 'info': info_path.relative_to(DEST).as_posix(),
                          'lang': lang_path.relative_to(DEST).as_posix(),
                          'entry_count': len(entries), 'counts': dict(file_counts),
                          'baseline_mes': base_filename if base_filename in audit else None})

    for category in ('translated', 'untranslated', 'kept_original'):
        current_counts.setdefault(category, 0)
    report = {'mes_files': len(files), 'json_files': len(files) * 2,
              'donor_translation_entries': donor_count, 'entry_counts': dict(counts),
              'match_counts': dict(matches), 'baseline_audit': str(audit_path.relative_to(ROOT)),
              'excluded_donors': excluded, 'cd_audio_selector_count': cd_audio_selectors,
              'recovered_current_korean_mes': recovered_from_mes,
              'current_entry_counts': dict(current_counts), 'files': files}
    write_json(DEST / 'translation-transfer-report.json', report)
    write_json(DEST / 'translation-review.json', unresolved)
    return report
