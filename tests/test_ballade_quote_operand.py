from gspecific.ballade.decode_scripts import decode_ballade_mes


def test_quote_operand_does_not_hide_text_past_end_marker():
    tokens = decode_ballade_mes(bytes.fromhex("22 A6 28 08 FF FF 82 A0"))

    assert tokens[0]["value"] == "CONTROL_22"
    assert any(token["value"] == "END_FFFF" for token in tokens)
    assert any(token["type"] == "text" and token["value"] == "あ" for token in tokens)


def test_short_quoted_string_stays_quoted():
    tokens = decode_ballade_mes(b'"A"')

    assert len(tokens) == 1
    assert tokens[0]["type"] == "quoted"


def test_display_header_keeps_first_shift_jis_character_together():
    tokens = decode_ballade_mes(bytes.fromhex(
        "1A 00 0A 93 0A 0C 96 6C 5B 1A 00 0A 93 90 CC 5B"
    ))

    assert [token["value"] for token in tokens if token["type"] == "text"] == [
        "僕", "は", "昔", "は",
    ]


def test_a4_display_parameter_does_not_consume_first_character():
    tokens = decode_ballade_mes(bytes.fromhex("A4 0E 91 8E C0 5B"))

    assert [token["value"] for token in tokens if token["type"] == "text"] == [
        "実", "は",
    ]


def test_a2_display_parameter_preserves_first_character():
    tokens = decode_ballade_mes(bytes.fromhex("A2 0E 93 90 53 56 43"))

    assert next(token for token in tokens if token["offset"] == 1)["bytes"] == [0x0E, 0x93]
    assert [token["value"] for token in tokens if token["type"] == "text"] == [
        "心", "な", "し",
    ]


def test_control_10_operand_does_not_consume_first_shift_jis_byte():
    tokens = decode_ballade_mes(bytes.fromhex("10 2A 00 89 BD 7E 8D 6C"))

    assert tokens[1]["bytes"] == [0x2A, 0x00]
    assert [token["value"] for token in tokens if token["type"] == "text"] == [
        "何", "を", "考",
    ]


def test_control_10_before_hayashi_dialogue_preserves_first_character():
    tokens = decode_ballade_mes(bytes.fromhex("10 2A 00 90 E6 92 F6 74 76"))

    assert tokens[1]["bytes"] == [0x2A, 0x00]
    assert next(token for token in tokens if token["type"] == "text")["value"] == "先"


def test_control_0d_does_not_consume_first_shift_jis_character():
    tokens = decode_ballade_mes(bytes.fromhex("1A 00 0A 0D 8F EA 38 30"))

    assert next(token for token in tokens if token["offset"] == 3)["bytes"] == [0x0D]
    assert next(token for token in tokens if token["type"] == "text")["value"] == "場"


def test_control_10_preserves_compressed_first_character():
    tokens = decode_ballade_mes(bytes.fromhex("10 2A 00 54 57 37 3B"))

    assert tokens[1]["bytes"] == [0x2A, 0x00]
    assert next(token for token in tokens if token["type"] == "text")["value"] == "と"


def test_control_10_before_mada_keeps_ma_as_text():
    tokens = decode_ballade_mes(bytes.fromhex("10 2A 03 6A 4C 89 BD"))

    assert tokens[1]["bytes"] == [0x2A, 0x03]
    assert tokens[2]["offset"] == 3
    assert tokens[2]["bytes"] == [0x6A]


def test_control_0e_before_meryl_keeps_first_sjis_character():
    tokens = decode_ballade_mes(bytes.fromhex("A2 0E 2C 83 81 83 8A 83 8B"))

    assert tokens[1]["bytes"] == [0x0E, 0x2C]
    assert tokens[2]["offset"] == 3
    assert tokens[2]["bytes"] == [0x83, 0x81]


def test_control_10_before_ussura_keeps_u_as_text():
    tokens = decode_ballade_mes(bytes.fromhex("10 2A 00 32 4F 45 75"))

    assert tokens[1]["bytes"] == [0x2A, 0x00]
    assert tokens[2]["offset"] == 3
    assert tokens[2]["bytes"] == [0x32]
