import subprocess
import sys
import threading
from pathlib import Path

import pytest

from gspecific.necronomicon.adv98_mes import encode_mes_batch as batch


def prepare_arguments(monkeypatch, *extra):
    monkeypatch.setattr(sys, "argv", [
        "encode_mes_batch", "--files", "A.MES", "B.MES", "--no-dosbox-x", *extra,
    ])
    monkeypatch.setattr(Path, "is_file", lambda self: True)


def test_two_encoders_run_concurrently(monkeypatch, capsys):
    prepare_arguments(monkeypatch, "--jobs", "2")
    barrier = threading.Barrier(2)

    def encode(command, root):
        barrier.wait(timeout=5)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(batch, "run_encoder", encode)
    assert batch.main() == 0
    assert "encoded: 2; failed: 0" in capsys.readouterr().out


def test_failed_encoder_does_not_stop_other_files(monkeypatch, capsys):
    prepare_arguments(monkeypatch, "--jobs", "1")
    results = iter([1, 0])
    monkeypatch.setattr(batch, "run_encoder", lambda command, root:
                        subprocess.CompletedProcess(command, next(results), "", ""))
    assert batch.main() == 1
    assert "encoded: 1; failed: 1" in capsys.readouterr().out


def test_jobs_must_be_positive(monkeypatch):
    prepare_arguments(monkeypatch, "--jobs", "0")
    with pytest.raises(SystemExit) as error:
        batch.main()
    assert error.value.code == 2


def test_case_insensitive_duplicate_files_are_rejected(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["encode_mes_batch", "--files", "A.MES", "a.mes"])
    with pytest.raises(SystemExit) as error:
        batch.main()
    assert error.value.code == 2


def test_subprocess_output_uses_utf8(monkeypatch):
    def run(command, **options):
        assert options["capture_output"] is True
        assert options["encoding"] == "utf-8"
        assert options["env"]["PYTHONIOENCODING"] == "utf-8"
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(batch.subprocess, "run", run)
    assert batch.run_encoder([sys.executable], Path.cwd()).returncode == 0
