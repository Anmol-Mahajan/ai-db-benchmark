from __future__ import annotations

import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ResourceSnapshot:
    wall_time: float
    process_time: float
    rss_mb: float
    system_memory_percent: float


@dataclass(frozen=True)
class ResourceUsage:
    duration_seconds: float
    cpu_percent: float
    peak_process_memory_mb: float
    peak_system_memory_percent: float


def _psutil():  # type: ignore[no-untyped-def]
    try:
        import psutil
    except ImportError:
        return None
    return psutil


def current_rss_mb() -> float:
    psutil = _psutil()
    if psutil:
        return float(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return float(usage / (1024 * 1024))
    return float(usage / 1024)


def system_memory_percent() -> float:
    psutil = _psutil()
    if psutil:
        return float(psutil.virtual_memory().percent)
    return 0.0


def snapshot() -> ResourceSnapshot:
    return ResourceSnapshot(
        wall_time=time.perf_counter(),
        process_time=time.process_time(),
        rss_mb=current_rss_mb(),
        system_memory_percent=system_memory_percent(),
    )


def usage_between(before: ResourceSnapshot, after: ResourceSnapshot) -> ResourceUsage:
    duration = max(after.wall_time - before.wall_time, 1e-9)
    cpu_count = os.cpu_count() or 1
    cpu_percent = ((after.process_time - before.process_time) / duration) * 100.0 / cpu_count
    return ResourceUsage(
        duration_seconds=duration,
        cpu_percent=cpu_percent,
        peak_process_memory_mb=max(before.rss_mb, after.rss_mb),
        peak_system_memory_percent=max(before.system_memory_percent, after.system_memory_percent),
    )


def disk_free_gb(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024**3)


def disk_total_gb(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.total / (1024**3)


def command_version(command: str, args: Optional[List[str]] = None) -> Optional[str]:
    resolved = shutil.which(command)
    if not resolved:
        return None
    try:
        output = subprocess.run(
            [resolved] + (args or ["--version"]),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "available"
    text = (output.stdout or output.stderr).strip().splitlines()
    return text[0] if text else "available"


def machine_metadata() -> Dict[str, object]:
    psutil = _psutil()
    total_ram = psutil.virtual_memory().total / (1024**3) if psutil else 0.0
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "total_ram_gb": round(total_ram, 2),
        "python_version": platform.python_version(),
        "docker_version": command_version("docker"),
        "ollama_version": command_version("ollama"),
    }
