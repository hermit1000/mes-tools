from gspecific.xgirl.analyze_speakers import analyze_document


def text(offset, value):
    return {'offset': f'{offset:05X}', 'type': 'text', 'original': value}


def control(offset, value):
    return {'offset': f'{offset:05X}', 'type': 'control', 'value': value}


def command(offset, opcode, value=None):
    return {'offset': f'{offset:05X}', 'type': 'command', 'opcode': opcode, 'arguments': [] if value is None else [{'value': value}]}


def analyze(records):
    info = {'source': 'MES/sample.MES', 'source_sha256': 'test', 'records': records}
    lang = {'entries': [{'offset': r['offset'], 'original': r['original'], 'translation': ''} for r in records if r['type'] == 'text']}
    return analyze_document(info, lang)


def definition(offset, number, name):
    return [command(offset, 'B9', number), control(offset + 1, 'BOUNDARY_A2'), text(offset + 2, f'「{name}」'), control(offset + 3, 'CONTROL_A5'), control(offset + 4, 'BOUNDARY_A3')]


def test_literal_speaker_stops_before_narration():
    result = analyze([text(0, '「アンナ」'), control(1, 'CONTROL_A5'), text(2, '会話。'), command(3, 'AB'), command(4, 'AA'), text(5, '地の文。')])
    assert result['groups'][0]['body'] == [{'offset': '00002', 'original': '会話。'}]
    assert any(r['original'] == '地の文。' for r in result['unassigned'])


def test_name_definition_is_not_executed_dialogue():
    assert not analyze(definition(0, 17, 'キヨミ'))['groups']


def test_macro_redefinition_changes_name_and_group_boundary():
    records = definition(0, 17, 'キヨミ') + [command(5, 'BA', 17), text(6, '最初。'), command(7, 'AB')]
    records += definition(8, 17, 'アンナ') + [command(13, 'BA', 17), text(14, '次。'), command(15, 'AB')]
    result = analyze(records)
    assert [g['speaker'] for g in result['groups']] == ['キヨミ', 'アンナ']


def test_macro_numbers_do_not_leak_between_files():
    analyze(definition(0, 19, 'キヨミ'))
    result = analyze([command(0, 'BA', 19), text(1, '本文。'), command(2, 'AB')])
    assert not result['groups']


def test_branch_boundary_prevents_speaker_carryover():
    result = analyze([text(0, '「キヨミ」'), control(1, 'CONTROL_A5'), text(2, '本文。'), control(3, 'BOUNDARY_A4'), text(4, '別枝。')])
    assert len(result['groups'][0]['body']) == 1
    assert result['groups'][0]['termination'] == 'flow_boundary'


def test_quoted_word_without_name_line_break_is_not_speaker():
    assert not analyze([text(0, '「秘密」'), text(1, 'という言葉。')])['groups']
