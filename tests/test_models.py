import sys
from types import SimpleNamespace

from jarvis_local import models, windows
from jarvis_local.catalog import RECOMMENDED, Rec
from jarvis_local.config import Config
from jarvis_local.hardware import Hardware
from jarvis_local.ollama import ModelInfo

GB = 1024 ** 3
REC = Rec("gemma3:4b", "deep", 3.3)


def hw(ram=16, disk=100):
    return Hardware(ram, ram / 2, disk, 8)


def test_catalog_small_and_valid():
    assert RECOMMENDED and all(r.approx_gb <= 4 and r.tier in {"fast", "balanced", "deep"} for r in RECOMMENDED)


def test_ok():
    ok, why = models.can_pull(REC, hw(), [], Config())
    assert ok, why


def test_refuses_low_disk_names_gb():
    ok, why = models.can_pull(REC, hw(disk=7), [], Config())
    assert not ok and "GB" in why and "7.0" in why


def test_refuses_budget():
    inst = [ModelInfo("big", int(18 * GB))]
    ok, why = models.can_pull(REC, hw(), inst, Config())
    assert not ok and "budget" in why and "20" in why


def test_refuses_ram():
    ok, why = models.can_pull(REC, hw(ram=4), [], Config())
    assert not ok and "RAM" in why and "4.0" in why


def test_refuses_already_installed():
    ok, _ = models.can_pull(REC, hw(), [ModelInfo("gemma3:4b", GB)], Config())
    assert not ok


def test_pull_uses_client():
    calls = []
    client = SimpleNamespace(pull=lambda n, cb: calls.append(n))
    models.pull("x:1b", Config(), client=client)
    assert calls == ["x:1b"]


def test_open_visible(monkeypatch):
    seen = {}
    monkeypatch.setattr(windows.subprocess, "Popen", lambda argv, **kw: seen.update(argv=argv, kw=kw) or "p")
    assert windows.open_visible("t", ["ollama", "list"]) == "p"
    if sys.platform == "win32":
        assert seen["kw"]["creationflags"] == windows.subprocess.CREATE_NEW_CONSOLE
