from __future__ import annotations

import importlib.util
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ai_db_benchmark.benchmark.system_monitor import command_version, disk_free_gb, disk_total_gb, machine_metadata
from ai_db_benchmark.config import project_path


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    required: bool = True


def run_doctor() -> List[DoctorCheck]:
    checks: List[DoctorCheck] = []
    py = sys.version_info
    checks.append(
        DoctorCheck(
            "Python version",
            py >= (3, 9),
            f"{platform.python_version()} detected; Python 3.11+ preferred for the full roadmap",
            required=True,
        )
    )
    checks.append(
        DoctorCheck(
            "Apple Silicon architecture",
            platform.machine() in {"arm64", "aarch64"},
            f"{platform.machine()} detected; Apple M1 target is arm64",
            required=False,
        )
    )

    meta = machine_metadata()
    total_ram = float(meta.get("total_ram_gb") or 0.0)
    checks.append(
        DoctorCheck(
            "Memory",
            total_ram == 0.0 or total_ram >= 8.0,
            f"{total_ram:.2f} GB detected" if total_ram else "psutil unavailable; install dev dependencies for RAM details",
            required=False,
        )
    )

    root = project_path()
    checks.append(
        DoctorCheck(
            "Disk space",
            disk_free_gb(root) >= 5.0,
            f"{disk_free_gb(root):.2f} GB free of {disk_total_gb(root):.2f} GB total",
            required=True,
        )
    )

    for directory in [project_path("data", "generated"), project_path("data", "results")]:
        checks.append(_writable_directory_check(directory))

    checks.append(
        DoctorCheck(
            "duckdb package",
            importlib.util.find_spec("duckdb") is not None,
            "installed" if importlib.util.find_spec("duckdb") is not None else "missing; run python3 -m pip install -e '.[dev]'",
            required=True,
        )
    )
    checks.append(
        DoctorCheck(
            "psutil package",
            importlib.util.find_spec("psutil") is not None,
            "installed" if importlib.util.find_spec("psutil") is not None else "missing; resource metrics will use fallback values",
            required=False,
        )
    )

    docker = command_version("docker")
    checks.append(DoctorCheck("Docker", docker is not None, docker or "not installed or not on PATH", required=False))

    ollama_path = _ollama_binary()
    if ollama_path:
        checks.append(DoctorCheck("Ollama binary", True, str(ollama_path), required=False))
        checks.append(_ollama_server_check(ollama_path))
    else:
        checks.append(DoctorCheck("Ollama binary", False, "not installed or not on PATH", required=False))

    return checks


def _writable_directory_check(path: Path) -> DoctorCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return DoctorCheck(f"Writable {path.relative_to(project_path())}", True, "ok")
    except OSError as exc:
        return DoctorCheck(f"Writable {path}", False, str(exc), required=True)


def _ollama_binary() -> Optional[Path]:
    from shutil import which

    resolved = which("ollama")
    if resolved:
        return Path(resolved)
    bundled = Path("/Applications/Ollama.app/Contents/Resources/ollama")
    return bundled if bundled.exists() else None


def _ollama_server_check(binary: Path) -> DoctorCheck:
    try:
        output = subprocess.run(
            [str(binary), "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck("Ollama server", False, f"could not query local server: {exc}", required=False)
    if output.returncode == 0:
        lines = [line for line in output.stdout.splitlines() if line.strip()]
        model_count = max(0, len(lines) - 1)
        return DoctorCheck("Ollama server", True, f"running; {model_count} model(s) installed", required=False)
    message = (output.stderr or output.stdout).strip()
    return DoctorCheck("Ollama server", False, message or "not running", required=False)
