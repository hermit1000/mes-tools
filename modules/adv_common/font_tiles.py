"""Locate 16×16 two-byte glyphs in a 2048×2048 Anex86 font bitmap."""


def roi_2byte(code: str) -> tuple[int, int, int, int]:
    value = int(code, 16)
    lead = (value >> 8) & 0xFF
    trail = value & 0xFF
    col = (lead - 0x81) * 2 + 1
    col += trail >= 0x9F
    if trail >= 0x9F:
        row = 33 + trail - 0x9F
    else:
        row = 33 + trail - 0x40
        if trail >= 0x80:
            row -= 1
    return row * 16, row * 16 + 16, col * 16, col * 16 + 16
