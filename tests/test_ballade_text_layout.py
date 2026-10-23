from copy import deepcopy
import unittest

from gspecific.ballade.text_layout import annotate_layout, layout_issues, strip_wrap_spaces, validate_layout


def documents(original, translation, known=True):
    command = {"type": "command", "offset": "00000", "opcode": "BA", "arguments": [{"value": 19}]} if known else {"type": "control", "offset": "00000", "value": "CONTROL_F0"}
    info = {"records": [command, {"type": "text", "offset": "00003", "original": original, "encodings": ["shift_jis"]},
                        {"type": "control", "offset": "00020", "value": "CONTROL_A5"}]}
    lang = {"entries": [{"offset": "00003", "original": original, "translation": translation}]}
    return info, lang


class LayoutTests(unittest.TestCase):
    def test_one_row_source_does_not_allow_two_translation_rows(self):
        info, lang = documents("あ" * 27, "가" * 34)
        annotate_layout(info, lang)
        layout = lang["entries"][0]["layout"]
        self.assertEqual((layout["original_rows"], layout["translated_rows"]), (1, 2))
        with self.assertRaisesRegex(ValueError, "A5 row overflow"):
            validate_layout(info, lang, "TEST")

    def test_two_row_source_allows_two_rows(self):
        info, lang = documents("あ" * 40, "가" * 55)
        self.assertEqual(layout_issues(info, lang), [])

    def test_unknown_position_is_reported_without_blocking(self):
        info, lang = documents("あ" * 27, "가" * 34, known=False)
        annotate_layout(info, lang)
        self.assertEqual(lang["entries"][0]["layout"]["check_status"], "unknown_position")
        self.assertEqual(layout_issues(info, lang), [])

    def test_wrap_spaces_only_at_boundary(self):
        text = "가" * 28 + "   " + "나 다"
        self.assertEqual(strip_wrap_spaces(text)[0], "가" * 28 + "나 다")
        self.assertEqual(strip_wrap_spaces("가" * 27 + " 나")[0], "가" * 27 + " 나")
        self.assertEqual(strip_wrap_spaces("가" * 56 + " 나")[0], "가" * 56 + "나")

    def test_validation_does_not_change_translation(self):
        info, lang = documents("あ" * 40, "가" * 28 + " " + "나")
        before = deepcopy(lang)
        validate_layout(info, lang, "TEST")
        self.assertEqual(lang, before)

    def test_closing_quote_does_not_consume_a_column(self):
        info, lang = documents("あ" * 28 + "」", "가" * 28 + "」")
        annotate_layout(info, lang)
        self.assertEqual(lang["entries"][0]["layout"]["original_columns"], 28)
        self.assertEqual(lang["entries"][0]["layout"]["translated_rows"], 1)
        self.assertEqual(strip_wrap_spaces("가" * 28 + "」 나")[0], "가" * 28 + "」나")

    def test_space_before_50_is_removed_despite_later_unknown_quote(self):
        text = "정정할게.지금 사는 집 말고 본가 얘기야.방만 족히 50개에 수영장은 물론이고……{외자:EBE8}"
        updated, column = strip_wrap_spaces(text)
        self.assertEqual(updated, text.replace("족히 50", "족히50"))
        self.assertIsNone(column)

    def test_unknown_width_stops_only_subsequent_space_processing(self):
        text = "가" * 28 + " " + "{외자:EBE9}" + "나" * 28 + " 다"
        self.assertEqual(strip_wrap_spaces(text)[0], "가" * 28 + "{외자:EBE9}" + "나" * 28 + " 다")


if __name__ == "__main__":
    unittest.main()
