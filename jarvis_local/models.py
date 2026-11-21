"""Model manager: decide whether a pull is safe, then pull."""
from __future__ import annotations

from .catalog import Rec
from .ollama import OllamaClient
from .router import fits

GB = 1024 ** 3


def can_pull(rec, hw, installed, cfg) -> tuple[bool, str]:
    gb = rec.approx_gb
    if any(m.name == rec.name for m in installed):
        return False, f"{rec.name} is already installed."
    left = hw.disk_free_gb - gb
    if left < cfg.disk_reserve_gb:
        return False, (f"Not enough disk: {hw.disk_free_gb:.1f} GB free, {rec.name} needs ~{gb:.1f} GB, "
                       f"and {cfg.disk_reserve_gb:.0f} GB must stay free (would leave {left:.1f} GB).")
    used = sum(m.size_bytes for m in installed) / GB
    if used + gb > cfg.model_budget_gb:
        return False, (f"Over the model budget: {used:.1f} GB installed + {gb:.1f} GB = "
                       f"{used + gb:.1f} GB, limit {cfg.model_budget_gb:.0f} GB.")
    if not fits(gb, hw.ram_total_gb):
        return False, (f"Too big for this machine's RAM: {rec.name} needs ~{gb * 1.3:.1f} GB, "
                       f"limit is {hw.ram_total_gb * 0.8:.1f} GB of {hw.ram_total_gb:.1f} GB.")
    return True, f"OK: ~{gb:.1f} GB, {left:.1f} GB disk left after."


class PullTooBig(Exception):
    """The real download size (reported by Ollama) is over the disk or model budget."""


def pull(name: str, cfg, on_progress=None, client: OllamaClient | None = None,
         hw=None, installed=None) -> None:
    """Pull with visible progress. If hw/installed are given, the download size Ollama reports
    is checked against the same limits as can_pull, and the pull is aborted if it is over."""
    state = {"checked": False, "last": -1}

    def progress(msg: dict) -> None:
        total = msg.get("total")
        if total and not state["checked"] and hw is not None:
            state["checked"] = True
            ok, why = can_pull(Rec(name, "", total / GB), hw, installed or [], cfg)
            if not ok:
                raise PullTooBig(why)
        if total and msg.get("completed") is not None:
            pct = int(100 * msg["completed"] / total) // 10 * 10
            if pct != state["last"]:
                state["last"] = pct
                print(f"pulling {name}: {pct}%", flush=True)
        if on_progress:
            on_progress(msg)

    (client or OllamaClient(cfg.ollama_url)).pull(name, progress)
