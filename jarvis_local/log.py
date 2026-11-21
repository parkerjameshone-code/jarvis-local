"""Append-only JSONL audit log. Never raises."""
from __future__ import annotations

import json
import time

from .config import Config


def event(kind: str, cfg: Config | None = None, **data) -> None:
    try:
        cfg = cfg or Config.load()
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, **data}
        with (cfg.data_dir / "audit.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=True, default=str) + "\n")
    except Exception:
        pass
