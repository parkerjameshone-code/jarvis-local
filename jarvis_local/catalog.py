"""Recommended small models (1-4B). Names are verified against Ollama at pull time."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rec:
    name: str
    tier: str
    approx_gb: float


RECOMMENDED: list[Rec] = [
    Rec("llama3.2:1b", "fast", 1.3),
    Rec("qwen2.5:1.5b", "fast", 1.0),
    Rec("gemma2:2b", "fast", 1.6),
    Rec("llama3.2:3b", "balanced", 2.0),
    Rec("qwen2.5:3b", "balanced", 1.9),
    Rec("qwen3:4b", "deep", 2.6),
    Rec("gemma3:4b", "deep", 3.3),
]


def find(name: str) -> Rec | None:
    return next((r for r in RECOMMENDED if r.name == name), None)
