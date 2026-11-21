"""Pick the best installed model for a kind of task, within this machine's RAM."""
from __future__ import annotations

from . import catalog

GB = 1024 ** 3
TIERS = {"fast", "balanced", "deep"}
_ORDER = ["fast", "balanced", "deep"]
TASK_TIER: dict[str, str] = {
    "classify": "fast", "extract": "fast",
    "draft": "balanced", "chat": "balanced",
    "plan": "deep", "check": "deep", "code": "deep",
}


class NoModel(Exception):
    pass


def tier_of(name: str, size_gb: float) -> str:
    rec = catalog.find(name)
    if rec:
        return rec.tier
    if size_gb < 1.5:
        return "fast"
    if size_gb < 2.4:
        return "balanced"
    return "deep"


def fits(size_gb: float, ram_total_gb: float) -> bool:
    return size_gb * 1.3 <= ram_total_gb * 0.8


def choose(task_kind: str, installed, hw) -> str:
    if task_kind not in TASK_TIER:
        raise ValueError(f"unknown task kind: {task_kind}")
    want = _ORDER.index(TASK_TIER[task_kind])
    cands = []
    for m in installed:
        if "embed" in m.name.lower():
            continue
        gb = m.size_bytes / GB
        if fits(gb, hw.ram_total_gb):
            cands.append((_ORDER.index(tier_of(m.name, gb)), gb, m.name))
    for t in range(want, -1, -1):
        in_tier = [c for c in cands if c[0] == t]
        if in_tier:
            return max(in_tier, key=lambda c: c[1])[2]
    raise NoModel(
        f"No installed model fits this machine ({hw.ram_total_gb:.1f} GB RAM; a model needs "
        f"size x1.3 <= {hw.ram_total_gb * 0.8:.1f} GB). Pull a smaller one.")
