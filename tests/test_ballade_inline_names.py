import unittest
from copy import deepcopy

from gspecific.ballade.inline_names import encode_inline_names, literal_name_catalog, merge_inline_names, name_widths, prepare_name_moves
from gspecific.ballade.merge_special_text import migrate_pair
from gspecific.ballade.text_layout import display_columns, strip_wrap_spaces


def text(offset, original, raw):
    return {"type": "text", "offset": f"{offset:05X}", "end": f"{offset + len(bytes.fromhex(raw)) - 1:05X}",
            "original": original, "raw_hex": raw, "encodings": ["shift_jis"], "translation_candidate": True}


class InlineTests(unittest.TestCase):
    def documents(self):
        records = [{"type": "command", "offset": "00000", "opcode": "B9", "arguments": [{"value": 14, "raw_hex": "28 0E"}]},
                   {"type": "boundary", "offset": "00003", "value": "BOUNDARY_A2"}, text(4, "パトリシア", "83 70 83 67 83 8A 83 56 83 41"),
                   {"type": "boundary", "offset": "0000E", "value": "BOUNDARY_A3"},
                   text(15, "私は", "96 84 5B"),
                   {"type": "command", "offset": "00012", "opcode": "BA", "arguments": [{"value": 14, "raw_hex": "28 0E"}]},
                   text(21, "です。", "53 45 81 42")]
        entries = [{"id": f'text:{record["offset"]}', "offset": record["offset"], "original": record["original"], "translation": value}
                   for record, value in ((records[2], "패트리샤"), (records[4], "저는"), (records[6], "예요."))]
        return {"source": "MES/001.MES", "records": records}, {"entries": entries}

    def test_readable_token_round_trip(self):
        info, lang = self.documents()
        original = deepcopy(lang)
        info, lang, count = merge_inline_names(info, lang)
        self.assertEqual(count, 1)
        entry = lang["entries"][-1]
        self.assertEqual(entry["original"], "私は{이름:パトリシア}です。")
        self.assertEqual(entry["translation"], "저는{이름:패트리샤}예요.")
        encoded = encode_inline_names(entry["translation"], info["records"][-1], lambda value: value.encode("utf-8"))
        self.assertEqual(encoded, "저는".encode() + bytes.fromhex("BA280E") + "예요.".encode())
        self.assertEqual(original["entries"][-1]["translation"], "예요.")

    def test_tokens_cannot_silently_drop_or_change_name_calls(self):
        info, lang = self.documents()
        info, lang, _ = merge_inline_names(info, lang)
        record = info["records"][-1]
        for value in ("저는예요.", "저는{이름:다른사람}예요.", "{이름:패트리샤}{이름:패트리샤}"):
            with self.assertRaises(ValueError):
                encode_inline_names(value, record, lambda text: text.encode())

    def test_width_uses_current_name_not_token_label(self):
        info, lang = self.documents()
        info, lang, _ = merge_inline_names(info, lang)
        lang["entries"][0]["translation"] = "패티"
        widths = name_widths(info["records"][-1], {entry["offset"]: entry for entry in lang["entries"]}, True)
        self.assertEqual(display_columns("가" * 26 + "{이름:패트리샤}", widths), 28)
        self.assertEqual(strip_wrap_spaces("가" * 26 + "{이름:패트리샤} 나", token_widths=widths)[0], "가" * 26 + "{이름:패트리샤}나")

    def test_unknown_gaiji_round_trip(self):
        record = {"original": "前{외자:EBE9}{외자:EC66}後"}
        encoded = encode_inline_names("앞{외자:EBE9}{외자:EC66}뒤", record, lambda text: text.encode())
        self.assertEqual(encoded, "앞".encode() + bytes.fromhex("EBE9EC66") + "뒤".encode())

    def test_missing_single_character_is_restored_and_preserved(self):
        single = text(0, "ハ", "83 6E")
        single["translation_candidate"] = False
        info = {"records": [single, text(2, "～イ", "EC 65 83 43")]}
        info["records"][1]["encodings"].append("ballade-special-glyph")
        lang = {"entries": [{"id": "text:00002", "offset": "00002", "original": "～イ", "translation": "～이"}]}
        info, lang, _ = migrate_pair(info, lang)
        self.assertEqual(lang["entries"][0]["original"], "ハ～イ")
        self.assertEqual(lang["entries"][0]["translation"], "{원문:00000}～이")
        result = encode_inline_names(lang["entries"][0]["translation"], info["records"][0], lambda text: text.encode())
        self.assertEqual(result, bytes.fromhex("836E") + "～이".encode())

    def test_name_at_start_of_body_is_restored(self):
        info, lang = self.documents()
        info["records"].pop(4)
        lang["entries"].pop(1)
        info, lang, count = merge_inline_names(info, lang)
        self.assertEqual(count, 1)
        self.assertEqual(lang["entries"][-1]["translation"], "{이름:패트리샤}예요.")

    def test_fresh_untranslated_body_stays_untranslated(self):
        info, lang = self.documents()
        for entry in lang["entries"]:
            entry["translation"] = ""
        info, lang, _ = merge_inline_names(info, lang)
        self.assertEqual(lang["entries"][-1]["translation"], "")

    def test_current_name_padding_is_counted_but_not_in_label(self):
        info, lang = self.documents()
        lang["entries"][0]["translation"] = "패트리샤 "
        info, lang, _ = merge_inline_names(info, lang)
        record = info["records"][-1]
        self.assertEqual(record["inline_macros"][0]["token"], "{이름:패트리샤}")
        widths = name_widths(record, {entry["offset"]: entry for entry in lang["entries"]}, True)
        self.assertEqual(widths["{이름:패트리샤}"], 5)

    def test_compound_definition_is_not_reclassified_as_literal_name(self):
        info, lang = self.documents()
        info["records"][2]["inline_macros"] = [{"token": "{이름:다른이름}"}]
        self.assertEqual(literal_name_catalog([info]), {})

    def test_name_can_move_across_a5_within_the_same_text_span(self):
        info, lang = self.documents()
        info, lang, _ = merge_inline_names(info, lang)
        left = info["records"][-1]
        left_entry = lang["entries"][-1]
        right = text(26, "次。", "8E 9F 81 42")
        info["records"].extend([{"type": "control", "offset": "00019", "value": "CONTROL_A5"}, right])
        left_entry["translation"] = "저는"
        lang["entries"].append({"offset": "0001A", "original": "次。", "translation": "{이름:패트리샤}예요."})
        prepare_name_moves(info, lang)
        self.assertEqual(encode_inline_names("저는", left, lambda text: text.encode()), "저는".encode())
        self.assertEqual(encode_inline_names("{이름:패트리샤}예요.", right, lambda text: text.encode()), bytes.fromhex("BA280E") + "예요.".encode())
        self.assertEqual(name_widths(right, {entry["offset"]: entry for entry in lang["entries"]}, True)["{이름:패트리샤}"], 4)
        self.assertEqual(len(left["inline_macros"]), 1)

    def test_ellipsis_macro_can_be_replaced_by_text(self):
        macro = {
            "token": "{이름:15}", "offset": "00011", "raw_hex": "BA 28 0F",
            "original_name": "{외자:EBE9}" * 3,
            "translated_name": "{외자:EBE9}" * 3,
        }
        record = {"type": "text", "offset": "00010", "original": "原{이름:15}",
                  "inline_macros": [macro]}
        info = {"records": [record]}
        lang = {"entries": [{"offset": "00010", "translation": "번역…"}]}
        prepare_name_moves(info, lang)
        self.assertEqual(record["encoding_macros"], [])
        self.assertEqual(encode_inline_names("번역…", record, lambda value: value.encode("utf-8")),
                         "번역…".encode("utf-8"))

    def test_name_cannot_move_across_dialogue_end(self):
        info, lang = self.documents()
        info, lang, _ = merge_inline_names(info, lang)
        lang["entries"][-1]["translation"] = "저는"
        info["records"].extend([{"type": "end", "offset": "00019", "value": "END_FFFF"}, text(26, "次。", "8E 9F 81 42")])
        lang["entries"].append({"offset": "0001A", "original": "次。", "translation": "{이름:패트리샤}예요."})
        with self.assertRaises(ValueError):
            prepare_name_moves(info, lang)


if __name__ == "__main__":
    unittest.main()
