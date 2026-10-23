import unittest
from pathlib import Path
import modules.adv_common.text as shared_text

from gspecific.ballade.merge_special_text import migrate_pair
from gspecific.ballade.special_text import merge_special_text
from gspecific.ballade.encode_mes import load_maria_font_codes
from modules.adv_common.text import encode_translation


def text(offset, original, raw):
    return dict(type="text", offset=f"{offset:05X}", end=f"{offset + len(bytes.fromhex(raw)) - 1:05X}",
                original=original, raw_hex=raw, encodings=["shift_jis"], translation_candidate=True)


def gaiji(offset, code="EC68"):
    return dict(type="gaiji", offset=f"{offset:05X}", raw_hex=f"{code[:2]} {code[2:]}", value=f"GAIJI_{code}", editable=False)


class SpecialTextTests(unittest.TestCase):
    def test_merges_and_preserves_translation(self):
        records = [text(0, "前", "91 4F"), gaiji(2), gaiji(4), text(6, "後", "8C E3")]
        entries = [dict(id=f'text:{r["offset"]}', offset=r["offset"], original=r["original"], translation=t, status="translated")
                   for r, t in ((records[0], "앞"), (records[3], "뒤"))]
        info, lang, count = migrate_pair({"records": records}, {"entries": entries})
        self.assertEqual(count, 1)
        self.assertEqual(info["records"][0]["original"], "前‥‥後")
        self.assertEqual(info["records"][0]["raw_hex"], "91 4F EC 68 EC 68 8C E3")
        self.assertEqual(lang["entries"][0]["translation"], "앞‥‥뒤")
        self.assertEqual(len(entries), 2)
        self.assertEqual(migrate_pair(info, lang)[2], 0)

    def test_boundaries_and_unknown_gaiji(self):
        records = [gaiji(0), gaiji(2, "EC66"), text(4, "前", "91 4F"),
                   dict(type="control", offset="00006", raw_hex="F0", value="CONTROL_F0"), gaiji(7)]
        merged, _ = merge_special_text(records)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]["original"], "‥{외자:EC66}前")
        self.assertEqual(merged[1]["type"], "control")
        self.assertEqual(merged[2]["original"], "‥")

    def test_non_candidate_text_is_preserved(self):
        single = text(0, "あ", "2D")
        single["translation_candidate"] = False
        merged, _ = merge_special_text([single, gaiji(1), text(3, "前", "91 4F")])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["original"], "あ‥前")
        self.assertTrue(merged[0]["translation_candidate"])

    def test_ellipsis_encodes_to_game_glyph(self):
        codes = load_maria_font_codes(Path(shared_text.__file__).resolve().parents[2] / "font_table/font_table-kor-jin.json")
        self.assertEqual(encode_translation("‥…", codes), bytes.fromhex("EC688163"))

    def test_wave_and_closing_quote(self):
        records = [text(0, "な", "56"), gaiji(1, "EC65"), text(3, "んてね。", "7F 52 59 81 42"), gaiji(8, "EC67")]
        entries = [dict(id="text:00000", offset="00000", original="な", translation="농"),
                   dict(id="text:00003", offset="00003", original="んてね。", translation="담이야.")]
        info, lang, _ = migrate_pair({"records": records}, {"entries": entries})
        self.assertEqual(info["records"][0]["original"], "な～んてね。」")
        self.assertEqual(lang["entries"][0]["translation"], "농～담이야.」")
        codes = load_maria_font_codes(Path(shared_text.__file__).resolve().parents[2] / "font_table/font_table-kor-jin.json")
        self.assertEqual(encode_translation("～~」", codes), bytes.fromhex("EC65EC65EC67"))

    def test_merging_menu_parts_keeps_both_half_space_edges(self):
        left = text(0, "　", "81 40")
        right = text(2, "{이름:グロリア}の事　", "BA 28 0F 5A 8E 96 81 40")
        right["encodings"].append("ballade-name-macro")
        entries = [
            dict(id="text:00000", offset="00000", original=left["original"],
                 translation="{반각공백}", ascii_half_space_edges={"left": 1, "right": 0}),
            dict(id="text:00002", offset="00002", original=right["original"],
                 translation="{이름:글로리아}의 일", ascii_half_space_edges={"left": 0, "right": 1}),
        ]
        _, lang, count = migrate_pair({"records": [left, right]}, {"entries": entries})
        merged = lang["entries"][0]
        self.assertEqual(count, 1)
        self.assertEqual(merged["ascii_half_space_edges"], {"left": 1, "right": 1})
        self.assertEqual(merged["original_with_half_spaces"],
                         "{반각공백}　{이름:グロリア}の事　{반각공백}")


if __name__ == "__main__":
    unittest.main()
