import json
from pathlib import Path

import pytest
import gspecific.necronomicon

from gspecific.necronomicon.adv98_mes.encode_mes import validate_mes_size
from gspecific.necronomicon.system_mec import encode_menu_text

GAME = Path(gspecific.necronomicon.__file__).resolve().parent


def test_mapping_preserves_existing_twenty():
    old = json.loads((GAME / "necro_compact_font_mapping_top20.json").read_text(encoding="utf-8"))
    new = json.loads((GAME / "necro_compact_font_mapping_top50.json").read_text(encoding="utf-8"))
    assert new["entries"][:20] == old["entries"]
    assert len(new["entries"]) == 50
    assert len({item["character"] for item in new["entries"]}) == 50
    assert [int(item["code"], 16) for item in new["entries"]] == list(range(0x2D, 0x5F))
    for item in new["entries"]:
        assert int(item["source_sjis"], 16) == 0x8200 + int(item["code"], 16) + 0x72


def test_new_compact_glyph_can_be_forced_to_dbcs():
    font = GAME / "font_table-kor-jin-necro-compact.json"
    mapping = GAME / "necro_compact_font_mapping_top50.json"
    compact = encode_menu_text("갑니다.", font, mapping)
    forced = encode_menu_text("갑{니}다.", font, mapping)
    assert len(forced) == len(compact) + 1
    assert b"\x54" in compact


def test_mes_size_limit():
    validate_mes_size(bytes(0x3000))
    with pytest.raises(ValueError, match="common-menu scratch"):
        validate_mes_size(bytes(0x3001))
