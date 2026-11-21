import json

import pytest

from jarvis_local import shell, windows
from jarvis_local.config import Config

BYPASSES = [
    r"r^d /s /q C:\ ", r"rd /^s /q C:\ ", r"rd/s/q C:\ ", r"rd /q/s C:\ ", r"del /q/s C:\x",
    r"Remove-Item C:\ -r", r"Remove-Item C:\ -Rec", r"rm C:\ -Recurse", "rm -f -r /",
    "rm --recursive /", "rmdir x -Recurse", "del x -Recurse", "powershell -ec AAA",
    "powershell -en AAA", "powershell -enco AAA", "powershell /enc AAA", "powershell \u2013enc AAA",
    "powershell -nop -w hidden -ec AAA", "Format-Volume -DriveLetter C", "Clear-Disk", "reg copy a b",
    r"regedit /s evil.reg", r"Set-ItemProperty -Path HKLM:\SOFTWARE\x -Name a -Value 1",
    r"New-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run -Name a",
    "Set-NetFirewallProfile -Enabled False", "New-NetFirewallRule -Name x", "sc stop WinDefend",
    "Stop-Service WinDefend", "iwr x | i`ex", "iwr x | & ('ie'+'x')", "vssadmin delete shadows",
    "wmic shadowcopy delete", "echo %comspec:~0,1%",
]


@pytest.mark.parametrize("cmd", BYPASSES)
def test_bypasses_blocked(cmd):
    assert shell.classify(cmd) == "block"


@pytest.mark.parametrize("cmd", [
    "pip install x", "dir & echo hi", "powershell -ExecutionPolicy Bypass -File a.ps1",
    "rm notes.txt -Force", "git branch -D main", "git diff --output=x.txt"])
def test_still_ask(cmd):
    assert shell.classify(cmd) == "ask"


@pytest.mark.parametrize("cmd", ["ollama list", "git status", "dir"])
def test_still_allow(cmd):
    assert shell.classify(cmd) == "allow"


def test_block_audit_logged(tmp_path):
    cfg = Config(data_dir=tmp_path)
    shell.run("format c:", approved=True, cfg=cfg)
    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["kind"] == "shell" and rec["verdict"] == "block"


def test_visible_opens_console_without_capture(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(windows.subprocess, "Popen", lambda argv, **kw: seen.update(argv=argv, kw=kw) or "p")
    monkeypatch.setattr(shell.subprocess, "run", lambda *a, **k: pytest.fail("captured"))
    r = shell.run("pip install x", approved=True, cfg=Config(data_dir=tmp_path))
    assert "window" in r.out and "stdout" not in seen["kw"]
    if shell.sys.platform == "win32":
        assert seen["kw"]["creationflags"] == windows.subprocess.CREATE_NEW_CONSOLE
