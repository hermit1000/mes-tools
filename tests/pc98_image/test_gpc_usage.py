from collections import Counter

from modules.pc98_image.gpc_usage import choose_output_mode, collect_output_modes


class _File:
    def read_bytes(self):
        return b'\xc9"GRAPH\\TITLE.GPC"\xcf\x24'


class _Root:
    def glob(self, pattern):
        assert pattern == "*.MES"
        return [_File()]


def test_lexical_and_structured_mes_refer_to_same_gpc():
    lexical = lambda data: [
        {"type": "command", "bytes": [0xC9], "offset": 0},
        {"type": "command", "bytes": [0xCF], "offset": 18},
    ]
    structured = lambda data: [
        {"type": "command", "bytes": [0xC9]},
        {"type": "quoted", "value": "GRAPH\\TITLE.GPC"},
        {"type": "command", "bytes": [0xCF]},
        {"type": "argument", "value": 1},
    ]
    assert collect_output_modes(_Root(), lexical, lexical=True) == {"TITLE.GPC": Counter({1: 1})}
    assert collect_output_modes(_Root(), structured) == {"TITLE.GPC": Counter({1: 1})}
    assert choose_output_mode(Counter({0: 3, 1: 1}), None) == 0
    assert choose_output_mode(Counter({0: 3}), 1) == 1
