import json

from modules.adv_common.dictionary import add_pair, load_candidates


def test_add_pair_preserves_reference_count_and_unique_translation_order():
    dictionary = {}
    add_pair(dictionary, "원문", "번역", "a:1")
    add_pair(dictionary, "원문", "번역", "b:2")
    add_pair(dictionary, "원문", "다른 번역", "c:3")
    add_pair(dictionary, "", "무시", "d:4")
    assert dictionary == {
        "원문": {
            "count": 2,
            "reference": 3,
            "translated": ["번역", "다른 번역"],
            "references": ["a:1", "b:2", "c:3"],
        }
    }


def test_candidate_rules_keep_game_specific_empty_handling():
    class JsonSource:
        def read_text(self, encoding):
            assert encoding == "utf-8"
            return json.dumps({
            "one": {"translated": ["", "번역"]},
            "two": {"translated": ["번역", "번역"]},
            "three": {"translated": ["번역", "다른 번역"]},
            "bad": {"translated": "번역"},
            }, ensure_ascii=False)

    path = JsonSource()
    assert load_candidates(path) == {"two": "번역"}
    assert load_candidates(path, ignore_empty=True) == {"one": "번역", "two": "번역"}
