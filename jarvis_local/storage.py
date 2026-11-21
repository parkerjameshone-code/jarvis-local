"""Disk usage report, known caches, and guarded deletion (Recycle Bin only)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from send2trash import send2trash as _send2trash
except ImportError:  # pragma: no cover
    _send2trash = None

GB = 1024 ** 3
PROTECTED_NAMES = {"documents", "desktop", "windows", "program files", "program files (x86)"}


@dataclass
class CacheDir:
    path: Path
    gb: float
    how_to_clear: str


def _size(p: Path) -> int:
    total = 0
    try:
        if p.is_symlink():
            return 0
        if p.is_file():
            return p.stat().st_size
        for dirpath, _dirnames, files in os.walk(p, followlinks=False):
            for f in files:
                try:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        pass
    return total


def report(root, top: int = 15) -> list[tuple[Path, float]]:
    """Biggest direct children of root, as (path, GB), largest first."""
    root = Path(root)
    try:
        kids = list(root.iterdir())
    except OSError:
        return []
    rows = [(k, _size(k) / GB) for k in kids]
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows[:top]


def known_caches() -> list[CacheDir]:
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    cands = [
        (local / "pip" / "Cache", "pip cache purge"),
        (local / "npm-cache", "npm cache clean --force"),
        (local / "Temp", "Windows Settings > Storage > Temporary files"),
        (home / ".cache", "Delete the folders you no longer need (they are re-created)"),
    ]
    return [CacheDir(p, _size(p) / GB, how) for p, how in cands if p.is_dir()]


def _is_protected(path: Path, protected: list[Path]) -> bool:
    try:
        rp = path.resolve()
    except OSError:
        return True
    home = Path.home().resolve()
    if rp == home or rp == Path(rp.anchor):
        return True
    for part in rp.parts[:2]:
        if part.lower() in PROTECTED_NAMES:
            return True
    if rp.parent == home and rp.name.lower() in PROTECTED_NAMES:
        return True
    try:
        rel = rp.relative_to(home)
        if rel.parts and rel.parts[0].lower() in PROTECTED_NAMES:
            return True
    except ValueError:
        pass
    for pr in protected:
        try:
            prr = Path(pr).resolve()
        except OSError:
            continue
        if rp == prr or prr in rp.parents or rp in prr.parents:
            return True
    return False


def trash(paths, approved: bool, protected=()) -> list[str]:
    """Send paths to the Recycle Bin. Returns one result line per path."""
    paths = [Path(p) for p in paths]
    if not approved:
        return [f"refused (needs approval): {p}" for p in paths]
    prot = [Path(x) for x in protected]
    results = []
    for p in paths:
        if _is_protected(p, prot):
            results.append(f"refused (protected): {p}")
        elif not p.exists():
            results.append(f"skipped (not found): {p}")
        else:
            try:
                _send2trash(str(p))
                results.append(f"trashed: {p}")
            except Exception as e:  # noqa: BLE001
                results.append(f"failed: {p} ({type(e).__name__})")
    return results
