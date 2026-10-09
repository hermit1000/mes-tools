from modules.adv_common.dictionary import ambiguous_translations, collect_dialogue_dictionary


class _Document:
    def __init__(self, name, text):
        self.name = name
        self.text = text

    def read_text(self, *, encoding):
        assert encoding == "utf-8"
        return self.text


def test_dictionary_collector_skips_other_resource_formats():
    paths = [
        _Document("A.MES_lang.json", '{"format":"mes","dialogue_groups":[{"id":"a","original":"同じ","translation":"하나"},{"id":"b","original":"同じ","translation":"둘"}]}'),
        _Document("SYSTEM.MEC_lang.json", '{"format":"mec","dialogue_groups":[{"original":"別","translation":"제외"}]}'),
    ]
    dictionary, entries, translated, skipped = collect_dialogue_dictionary(
        paths, expected_format="mes", skip_other_formats=True,
    )
    assert (entries, translated, skipped) == (2, 2, 1)
    assert dictionary["同じ"]["translated"] == ["하나", "둘"]
    assert ambiguous_translations(dictionary) == {"同じ": {"translated": ["하나", "둘"]}}
