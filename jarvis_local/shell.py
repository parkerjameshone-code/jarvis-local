"""Terminal rules: classify commands as allow / ask / block, and run them."""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass

from . import log, windows

BLOCK = [
    r"\bformat(\.com)?\s+[a-z]:",
    r"\b(rd|rmdir|del|erase)\b[^|;&]*/s\b",
    r"\b(remove-item|ri|rm|rmdir|rd|del|erase)\b[^|;&]*\s-r(e(c(u(r(s(e)?)?)?)?)?)?\b",
    r"\brm\b[^|;&]*\s(--recursive|-(?!force\b)[a-z]*r[a-z]*)\b",
    r"\brm\s+-[a-z]*r",
    r"-r[a-z]*\b[^;&]*\|\s*(remove-item|ri|rm|del|erase)\b",
    r"\b(format-volume|clear-disk|initialize-disk|remove-partition)\b",
    r"\breg(\.exe)?\s+(add|delete|import|load|unload|restore|copy)\b",
    r"\bregedit(\.exe)?\b",
    r"\b(set|new|remove|rename|clear)-item(property)?\b[^|;&]*\b(hklm|hkcu|hkcr|hku|hkcc|registry)::?",
    r"\b(new|set|remove|disable|enable)-netfirewall\w*\b",
    r"\b(sc(\.exe)?|stop-service|set-service|remove-service)\b[^|;&]*"
    r"\b(windefend|wdnissvc|sense|mpssvc|securityhealthservice)\b",
    r"\bmpcmdrun\b",
    r"\b(vssadmin|wbadmin)\b[^|;&]*\bdelete\b",
    r"\bwmic\b[^|;&]*\bshadowcopy\b[^|;&]*\bdelete\b",
    r"\|\s*&",
    r"\bnetsh\b",
    r"\b(set|add|remove)-mppreference\b",
    r"\bbcdedit\b",
    r"\bshutdown(\.exe)?\b",
    r"\b(restart|stop)-computer\b",
    r"\bdiskpart\b",
    r"\bcipher\s+/w",
    r"\bset-executionpolicy\b",
    r"\|\s*(iex|invoke-expression|sh|bash|cmd|powershell|pwsh)\b",
    r"\b(iex|invoke-expression)\b",
]
ALLOW = [
    r"^ollama\s+(list|ps|show|--version|-v)\b",
    r"^git\s+(status|log|diff|branch|show)\b",
    r"^(dir|ls|pwd|whoami|hostname|echo|type|cat|where|which)\b",
]
_BLOCK = [re.compile(p, re.I) for p in BLOCK]
_ALLOW = [re.compile(p, re.I) for p in ALLOW]
_ENC = re.compile(r"(^|\s)[-/](e|ec|en[a-z]*)(\s|$)", re.I)
_SHELLS = re.compile(r"\b(powershell|pwsh)(\.exe)?\b", re.I)
_CHAIN = re.compile(r"[;&|`$<>\n]")
_OBFUSCATED = re.compile(r"[\^`]|%[^%\s]*:~")
_ALLOW_UNSAFE = re.compile(r"\s-[dDmMcC]\b|--output|--delete|--force|\s-f\b")
_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")


@dataclass
class Result:
    code: int
    out: str


def _normalize(c: str) -> str:
    return re.sub(r"[\"']", "", c.translate(_DASHES))


def classify(cmd: str) -> str:
    c = (cmd or "").strip()
    if not c:
        return "ask"
    if _OBFUSCATED.search(c):
        return "block"
    n = _normalize(c)
    for text in (c, n):
        if any(p.search(text) for p in _BLOCK):
            return "block"
    if _SHELLS.search(n) and _ENC.search(n):
        return "block"
    if (any(p.search(c) for p in _ALLOW) and not _CHAIN.search(c)
            and not _ALLOW_UNSAFE.search(c)):
        return "allow"
    return "ask"


def run(cmd: str, approved: bool = False, visible: bool = True, timeout: int = 600, cfg=None) -> Result:
    verdict = classify(cmd)

    visible = visible and verdict != "allow"

    def done(code: int, out: str) -> Result:
        log.event("shell", cfg=cfg, cmd=cmd[:2000], verdict=verdict, approved=approved,
                  visible=visible, code=code)
        return Result(code, out)

    if verdict == "block":
        return done(126, "refused: this command is blocked by the terminal rules")
    if verdict == "ask" and not approved:
        return done(125, "refused: needs approval first")
    if visible:
        # Run in its own console so the owner can watch; output is not captured.
        # (Read-only allow-listed commands are captured so the answer can use them.)
        argv = ["cmd", "/k", cmd] if sys.platform == "win32" else ["sh", "-c", cmd]
        try:
            windows.open_visible("JARVIS", argv)
        except OSError as e:
            return done(127, f"could not run: {type(e).__name__}")
        return done(0, "opened in a window")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, creationflags=flags)
    except subprocess.TimeoutExpired:
        return done(124, "timed out")
    except OSError as e:
        return done(127, f"could not run: {type(e).__name__}")
    return done(p.returncode, (p.stdout or "") + (p.stderr or ""))
