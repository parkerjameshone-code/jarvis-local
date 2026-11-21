"""Open a command in its own visible console window (so the user can watch it)."""
from __future__ import annotations

import subprocess
import sys


def open_visible(title: str, argv: list[str]) -> subprocess.Popen:
    # title is informational: a Windows console shows the program's own title.
    if sys.platform == "win32":
        return subprocess.Popen(argv, creationflags=subprocess.CREATE_NEW_CONSOLE)
    return subprocess.Popen(argv)
