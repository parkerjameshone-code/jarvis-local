"""Configuration. Private values live outside the repo, in ~/.jarvis/config.toml."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


def default_dir() -> Path:
    return Path.home() / ".jarvis"


@dataclass
class Config:
    ollama_url: str = "http://127.0.0.1:11434"
    data_dir: Path = field(default_factory=default_dir)
    model_budget_gb: float = 20
    disk_reserve_gb: float = 5
    email_daily_cap: int = 20
    postal_address: str = ""
    email_from: str = ""
    unsubscribe_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    project_dirs: list = field(default_factory=list)
    offers: list = field(default_factory=list)  # [[offers]] tables: id, name, description, link

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        p = Path(path) if path else default_dir() / "config.toml"
        cfg = cls()
        if not p.is_file():
            return cfg
        with p.open("rb") as f:
            raw = tomllib.load(f)
        for fld in fields(cls):
            if fld.name in raw:
                val = raw[fld.name]
                setattr(cfg, fld.name, Path(val) if fld.name == "data_dir" else val)
        return cfg
