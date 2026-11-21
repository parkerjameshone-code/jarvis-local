from types import SimpleNamespace

from jarvis_local import cli
from jarvis_local.config import Config
from jarvis_local.ollama import ModelInfo, OllamaClient

GB = 1024 ** 3
HW = SimpleNamespace(ram_total_gb=16, ram_free_gb=8, disk_free_gb=100, cpus=8, gpu=None)


def test_status_ollama_down(dead_url, capsys, tmp_path):
    rc = cli.main(["status"], client=OllamaClient(dead_url), cfg=Config(data_dir=tmp_path), hw=HW)
    out = capsys.readouterr()
    assert rc == 1 and "Ollama isn't running" in out.out and "Traceback" not in out.out + out.err


def test_status_ok(capsys, tmp_path):
    class C:
        def available(self):
            return True

        def list(self):
            return [ModelInfo("llama3.2:3b", 2 * GB)]
    rc = cli.main(["status"], client=C(), cfg=Config(data_dir=tmp_path), hw=HW)
    assert rc == 0 and "llama3.2:3b" in capsys.readouterr().out


def test_shell_needs_approval(capsys, tmp_path):
    class C:
        def available(self):
            return True
    rc = cli.main(["shell", "pip", "install", "x"], client=C(), cfg=Config(data_dir=tmp_path),
                  yes=lambda p: False, hw=HW)
    assert rc == 0 and "Skipped" in capsys.readouterr().out


def test_unknown_subcommand_exits(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        cli.main(["bogus"], cfg=Config(data_dir=tmp_path))
