"""Hardware snapshot: RAM, free disk, CPUs, optional GPU name."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psutil

GB = 1024 ** 3


@dataclass(frozen=True)
class Hardware:
    ram_total_gb: float
    ram_free_gb: float
    disk_free_gb: float
    cpus: int
    gpu: str | None = None


def _gpu() -> str | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        name = out.stdout.strip().splitlines()
        return name[0].strip() if out.returncode == 0 and name else None
    except Exception:
        return None


def snapshot(path: str | Path | None = None) -> Hardware:
    vm = psutil.virtual_memory()
    target = str(path or Path.home())
    return Hardware(
        ram_total_gb=round(vm.total / GB, 2),
        ram_free_gb=round(vm.available / GB, 2),
        disk_free_gb=round(shutil.disk_usage(target).free / GB, 2),
        cpus=os.cpu_count() or 1,
        gpu=_gpu(),
    )
