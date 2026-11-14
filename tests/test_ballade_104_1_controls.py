from gspecific.ballade.decode_scripts import decode_ballade_mes


def test_104_1_display_parameters_do_not_swallow_anna_text():
    first = decode_ballade_mes(bytes.fromhex("1A 01 0A 8E 83 41 83 93 83 69"))
    second = decode_ballade_mes(bytes.fromhex("0E 8E A4 83 41 83 93 83 69"))

    assert next(token for token in first if token["offset"] == 2)["bytes"] == [0x0A, 0x8E]
    assert next(token for token in second if token["offset"] == 0)["bytes"] == [0x0E, 0x8E]
    assert next(token for token in first if token["type"] == "text")["offset"] == 4
    assert next(token for token in second if token["type"] == "text")["offset"] == 3
