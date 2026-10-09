from gspecific.necronomicon.adv98_mes.decode_mes import (
    make_lang, repair_condition_prefix, repair_menu_flag_prefix,
)


def test_condition_prefix_is_not_translatable_and_survives_lang_creation():
    text = "魚鱗亭"
    raw = b"\xe7\xa4" + text.encode("cp932")
    record = {
        "type": "text", "offset": "00001", "end": "00008",
        "raw_hex": raw.hex(" "), "original": "遉" + text,
        "translation_candidate": True,
    }
    repaired = repair_condition_prefix(record, b"\x0b" + raw)
    assert repaired["original"] == text
    assert repaired["offset"] == "00001"
    assert bytes.fromhex(repaired["raw_hex"]) == raw
    lang = make_lang("SAMPLE.MES_info.json", {"records": [repaired]})
    assert lang["overlay_texts"][0]["encoding_prefix_hex"] == "E7 A4"


def test_genuine_sjis_character_without_condition_context_is_unchanged():
    raw = "遉魚鱗亭".encode("cp932")
    record = {"type": "text", "offset": "00001", "raw_hex": raw.hex(), "original": "遉魚鱗亭"}
    assert "encoding_prefix_hex" not in repair_condition_prefix(record, b"\xa5" + raw)
    assert record["original"] == "遉魚鱗亭"


def test_menu_flag_operand_and_boundary_are_preserved():
    raw = bytes.fromhex("91 81 97 81 40 81 40 92 86 57 93 FC 77 81 40 81 40")
    record = {"type": "text", "offset": "00001", "end": "00011",
              "raw_hex": raw.hex(" "), "original": "早浴ご　中に入る　　",
              "translation_candidate": True}
    repaired = repair_menu_flag_prefix(record, b"\x09" + raw)
    assert repaired["original"] == "　　中に入る　　"
    assert repaired["encoding_prefix_hex"] == "91 81 97"
    assert repaired["offset"] == "00001"
    assert bytes.fromhex(repaired["raw_hex"]) == raw
    lang = make_lang("SAMPLE.MES_info.json", {"records": [repaired]})
    assert lang["overlay_texts"][0]["encoding_prefix_hex"] == "91 81 97"


def test_menu_prefix_is_not_stripped_without_verified_flag_context():
    raw = bytes.fromhex("91 81 97 81 40 81 40 92 86 57 93 FC 77 81 40 81 40")
    record = {"type": "text", "offset": "00001", "raw_hex": raw.hex(),
              "original": "早浴ご　中に入る　　"}
    repaired = repair_menu_flag_prefix(record, b"\xa5" + raw)
    assert "encoding_prefix_hex" not in repaired
    assert repaired["original"].startswith("早浴ご")
