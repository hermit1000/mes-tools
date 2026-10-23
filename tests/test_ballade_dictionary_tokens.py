import json

from gspecific.ballade.apply_dialogue_dictionary import plan_updates
from gspecific.ballade.make_dialogue_dictionary import build_dictionary


class FakeLangPath:
    def __init__(self, name: str, translation: str):
        self.name = name
        self.translation = translation

    def read_text(self, *, encoding: str) -> str:
        assert encoding == "utf-8"
        return json.dumps({
            "format": "maria-adv98-script-lang-v1",
            "entries": [{"id": "text:00001", "original": "未使用", "translation": self.translation}],
        }, ensure_ascii=False)


def test_byte_length_tokens_do_not_spread_from_mec_to_mes():
    mes = FakeLangPath("A.MES_lang.json", "미사용")
    mec = FakeLangPath("B.MEC_lang.json", "미사용{채움}")
    dictionary, *_ = build_dictionary([mes, mec])
    assert dictionary["未使用"]["translated"] == ["미사용"]
    updates, count = plan_updates([mes, mec], {"未使用": "미사용"})
    assert count == 0
    assert updates == []

    mes.translation = "미사용{채움}"
    updates, count = plan_updates([mes, mec], {"未使用": "미사용"})
    assert count == 1
    assert updates[0][0] is mes
    assert updates[0][1]["entries"][0]["translation"] == "미사용"


def test_forced_two_byte_glyph_is_shared_as_plain_text():
    mec = FakeLangPath("B.MEC_lang.json", "미{사}용")
    dictionary, *_ = build_dictionary([mec])
    assert dictionary["未使用"]["translated"] == ["미사용"]
    updates, count = plan_updates([mec], {"未使用": "미사용"})
    assert count == 0
    assert updates == []


def test_mes_forced_two_byte_glyph_survives_dictionary_apply():
    mes = FakeLangPath("A.MES_lang.json", "미{사}용")
    updates, count = plan_updates([mes], {"未使用": "미사용"})
    assert count == 0
    assert updates == []
