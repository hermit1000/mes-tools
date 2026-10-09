import subprocess
import sys
from pathlib import Path

from gspecific.marine_philt.adv98_mes import encode_mes_batch


def test_default_batch_processes_every_selected_file(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "encode_mes_batch", "--files", "A.MES", "B.MES", "--no-dosbox-x",
    ])
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    commands = []

    def run(command, **options):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(encode_mes_batch.subprocess, "run", run)
    assert encode_mes_batch.main() == 0
    assert [Path(command[3]).name for command in commands] == ["A.MES", "B.MES"]
