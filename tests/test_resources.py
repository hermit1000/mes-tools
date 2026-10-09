import pickle
import sys
import types
from unittest.mock import patch

from modules.adv_common.text import load_font_codes, load_forced_dbcs_codes
from modules.resources import default_font_table


def test_packaged_font_table_is_available():
    assert default_font_table().is_file()
    assert load_font_codes(default_font_table())


def test_legacy_font_cache_loads_without_external_module():
    package = types.ModuleType("module")
    package.__path__ = []
    font_module = types.ModuleType("module.font_table")
    font_table_type = type("FontTable", (), {"__module__": "module.font_table"})
    font_module.FontTable = font_table_type
    package.font_table = font_module
    table = font_table_type()
    table.char2code = {"가": "8140", " ": "20"}
    with patch.dict(sys.modules, {"module": package, "module.font_table": font_module}):
        payload = pickle.dumps(table)

    class Cache:
        suffix = ".pkl"

        def read_bytes(self):
            return payload

    assert load_font_codes(Cache()) == table.char2code
    assert load_forced_dbcs_codes(Cache()) == {"가": "8140"}
