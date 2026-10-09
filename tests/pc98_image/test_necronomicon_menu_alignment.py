import pytest

from gspecific.necronomicon.adv98_mes.encode_mes import (
    FULLWIDTH_SPACE, HALFWIDTH_SPACE, center_menu_text,
    encoded_text_half_cells, menu_text_span,
)


@pytest.mark.parametrize("label", [b"\x41", b"\x81\x40", b"\x41\x90\xbb\x5c"])
def test_compact_and_dbcs_have_equal_display_width(label):
    glyphs = 3 if len(label) == 4 else 1
    assert encoded_text_half_cells(label) == glyphs * 2


@pytest.mark.parametrize("length", range(1, 9))
def test_centering_fills_eight_cells_using_actual_display_width(length):
    compact = b"\x41" * length
    dbcs = b"\x90\xbb" * length
    left_half_cells = 8 - length
    expected_padding = (FULLWIDTH_SPACE * (left_half_cells // 2)
                        + HALFWIDTH_SPACE * (left_half_cells % 2))
    assert center_menu_text(compact, 8) == expected_padding + compact + expected_padding
    assert center_menu_text(dbcs, 8) == expected_padding + dbcs + expected_padding
    assert left_half_cells * 2 + length * 2 == 16


def test_old_external_fullwidth_and_ascii_padding_is_replaced_together():
    prefix = FULLWIDTH_SPACE * 2 + HALFWIDTH_SPACE
    suffix = HALFWIDTH_SPACE + FULLWIDTH_SPACE * 2
    label = b"\x90\xbb\x41"
    source = b"\xa4" + prefix + label + suffix + b"\xa4"
    start = 1 + len(prefix)
    end = start + len(label) - 1
    assert menu_text_span(source, start, end) == (1, len(source) - 2)


def test_menu_padding_does_not_consume_commands():
    source = b"\xba\x23\x90\xbb\xa4"
    with pytest.raises(ValueError, match="menu boundaries"):
        menu_text_span(source, 2, 3)


def test_label_that_exceeds_menu_width_is_rejected():
    with pytest.raises(ValueError, match="exceeds"):
        center_menu_text(b"\x41" * 9, 8)


def test_truncated_dbcs_is_rejected():
    with pytest.raises(ValueError, match="unsupported byte"):
        encoded_text_half_cells(b"\x90")
