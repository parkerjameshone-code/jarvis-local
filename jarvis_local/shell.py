"""Terminal rules: classify commands as allow / ask / block, and run them."""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass

BLOCK = [
    r"\bformat(\.com)?\s+[a-z]:",
    r"\b(rd|rmdir)\b[^|;&]*\s/s\b",
    r"\b(del|erase)\b[^|;&]*\s/s\b",
    r"\bremove-item\b[^|;&]*-recurse",
    r"\bri\b[^|;&]*-recurse",
    r"\brm\s+-[a-z]*r",
    r"\breg(\.exe)?\s+(add|delete|import|load|unload|restore)\b",
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
_ENC = re.compile(r"(^|\s)-e(nc(odedcommand)?)?(\s|$)", re.I)
_SHELLS = re.compile(r"\b(powershell|pwsh)(\.exe)?\b", re.I)
_CHAIN = re.compile(r"[;&|`$<>\n]")


@dataclass
class Result:
    code: int
    out: str


def classify(cmd: str) -> str:
    c = (cmd or "").strip()
    if not c:
        return "ask"
    if any(p.search(c) for p in _BLOCK):
        return "block"
    if _SHELLS.search(c) and _ENC.search(c):
        return "block"
    if any(p.search(c) for p in _ALLOW) and not _CHAIN.search(c):
        return "allow"
    return "ask"


def run(cmd: str, approved: bool = False, visible: bool = True, timeout: int = 600) -> Result:
    verdict = classify(cmd)
    if verdict == "block":
        return Result(126, "refused: this command is blocked by the terminal rules")
    if verdict == "ask" and not approved:
        return Result(125, "refused: needs approval first")
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_CONSOLE if visible else subprocess.CREATE_NO_WINDOW
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, creationflags=flags)
    except subprocess.TimeoutExpired:
        return Result(124, "timed out")
    except OSError as e:
        return Result(127, f"could not run: {type(e).__name__}")
    return Result(p.returncode, (p.stdout or "") + (p.stderr or ""))
