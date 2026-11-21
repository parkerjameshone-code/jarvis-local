"""Model manager: decide whether a pull is safe, then pull."""
from __future__ import annotations

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


def pull(name: str, cfg, on_progress=None, client: OllamaClient | None = None) -> None:
    (client or OllamaClient(cfg.ollama_url)).pull(name, on_progress)
