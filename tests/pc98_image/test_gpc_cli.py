import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from modules.pc98_image import decode_gpc as cli


def test_dob1_preset_routes_graph_files_and_mes_mode(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "decode_gpc", "--preset", "dob1", "--workspace", ".", "--file", "A.GPC",
    ])
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    calls = []

    def collect(root, decoder, *, lexical):
        assert root == Path.cwd() / "jpn-pc98" / "MES"
        assert decoder.__module__ == "modules.adv_common.mes_lexer"
        assert lexical is True
        return {"A.GPC": Counter({0: 2})}

    def write(source, output, **options):
        calls.append((source, output, options))
        return SimpleNamespace(width=8, height=1, output_mode=0, compressed_size=4)

    monkeypatch.setattr(cli, "collect_output_modes", collect)
    monkeypatch.setattr(cli, "write_artifacts", write)
    assert cli.main() == 0
    source, output, options = calls[0]
    assert source == Path.cwd() / "jpn-pc98" / "GRAPH" / "A.GPC"
    assert output == Path.cwd() / "image-pc98" / "GRAPH" / "A.GPC"
    assert options["output_mode"] == 0
