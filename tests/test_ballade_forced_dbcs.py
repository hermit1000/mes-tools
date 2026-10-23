import unittest

from modules.adv_common.text import load_marine_remap
from gspecific.ballade.encode_mes import encode_ballade_text, load_maria_font_codes, pad_mec_text
from gspecific.ballade.encode_batch import DEFAULT_COMPACT_REMAP
from gspecific.ballade.encode_mes import DEFAULT_FONT_TABLE
from gspecific.ballade.text_layout import display_columns, strip_wrap_spaces


class ForcedDbcsTests(unittest.TestCase):
    def test_forced_character_restores_one_byte_without_changing_display_width(self):
        codes = load_maria_font_codes(DEFAULT_FONT_TABLE)
        compact = load_marine_remap(DEFAULT_COMPACT_REMAP)
        self.assertEqual(len(encode_ballade_text("미사용", codes, compact)), 5)
        self.assertEqual(len(encode_ballade_text("미{사}용", codes, compact)), 6)
        self.assertEqual(display_columns("미{사}용"), 3)

    def test_noop_token_fills_one_byte_without_display_column(self):
        codes = load_maria_font_codes(DEFAULT_FONT_TABLE)
        compact = load_marine_remap(DEFAULT_COMPACT_REMAP)
        encoded = encode_ballade_text("미사용{채움}", codes, compact)
        self.assertEqual(encoded[-1], 0xD6)
        self.assertEqual(len(encoded), 6)
        self.assertEqual(display_columns("미사용{채움}"), 3)

    def test_half_space_token_emits_ascii_print_command(self):
        codes = load_maria_font_codes(DEFAULT_FONT_TABLE)
        compact = load_marine_remap(DEFAULT_COMPACT_REMAP)
        self.assertEqual(encode_ballade_text("{반각공백}", codes, compact), b"\x21\x20\x00")
        self.assertEqual(display_columns("보{반각공백}기"), 2.5)
        self.assertEqual(strip_wrap_spaces("보{반각공백}기")[1], 2.5)

    def test_mec_auto_padding_only_fills_shorter_records(self):
        self.assertEqual(pad_mec_text(b"AB", 4), b"AB\xD6\xD6")
        self.assertEqual(pad_mec_text(b"AB", 2), b"AB")
        with self.assertRaisesRegex(ValueError, "MEC text length 1 -> 2"):
            pad_mec_text(b"AB", 1)

    def test_forced_character_counts_once_at_wrap_boundary(self):
        self.assertEqual(strip_wrap_spaces("가" * 27 + "{사} 나")[0], "가" * 27 + "{사}나")


if __name__ == "__main__":
    unittest.main()
