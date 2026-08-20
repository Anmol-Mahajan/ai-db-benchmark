from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BenchmarkConfig:
    dataset_size: str = "smoke"
    seed: int = 42
    warmup_iterations: int = 2
    measured_iterations: int = 5
    batch_size: int = 100
    top_k: int = 10
    vector_dimension: int = 64
    store_raw_samples: bool = True
    dataset_sizes: Dict[str, int] = None  # type: ignore[assignment]
    vector_dataset_sizes: Dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.dataset_sizes is None:
            object.__setattr__(
                self,
                "dataset_sizes",
                {"smoke": 1000, "small": 10000, "medium": 100000, "million": 120660, "large": 500000},
            )
        if self.vector_dataset_sizes is None:
            object.__setattr__(
                self,
                "vector_dataset_sizes",
                {"smoke": 1000, "small": 10000, "medium": 50000, "large": 100000},
            )
        if self.warmup_iterations < 0:
            raise ValueError("warmup_iterations must be >= 0")
        if self.measured_iterations < 1:
            raise ValueError("measured_iterations must be >= 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if self.vector_dimension < 2:
            raise ValueError("vector_dimension must be >= 2")
        if self.dataset_size not in self.dataset_sizes:
            known = ", ".join(sorted(self.dataset_sizes))
            raise ValueError(f"Unknown dataset_size {self.dataset_size!r}; expected one of {known}")

    @property
    def customer_count(self) -> int:
        return self.dataset_sizes[self.dataset_size]

    @property
    def vector_count(self) -> int:
        return self.vector_dataset_sizes.get(self.dataset_size, self.customer_count)


def project_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "null":
        return None
    if value in {"true", "false"}:
        return value == "true"
    try:
        return int(value)
    except ValueError:
        return value.strip("\"'")


def load_simple_yaml(path: Path) -> Dict[str, Any]:
    """Parse the small config YAML shape used by this project.

    This intentionally supports only top-level scalars and one-level mappings,
    which keeps the bootstrap free of a mandatory YAML parser dependency.
    """
    data: Dict[str, Any] = {}
    current_map: Optional[str] = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not raw_line.startswith(" ") and line.endswith(":"):
            current_map = line[:-1].strip()
            data[current_map] = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if raw_line.startswith(" ") and current_map:
            data[current_map][key] = _parse_scalar(value)
        else:
            current_map = None
            data[key] = _parse_scalar(value)
    return data


def load_benchmark_config(path: Optional[Path] = None) -> BenchmarkConfig:
    config_path = path or project_path("config", "benchmark.yaml")
    raw = load_simple_yaml(config_path)
    return BenchmarkConfig(
        dataset_size=str(raw.get("dataset_size", "smoke")),
        seed=int(raw.get("seed", 42)),
        warmup_iterations=int(raw.get("warmup_iterations", 2)),
        measured_iterations=int(raw.get("measured_iterations", 5)),
        batch_size=int(raw.get("batch_size", 100)),
        top_k=int(raw.get("top_k", 10)),
        vector_dimension=int(raw.get("vector_dimension", 64)),
        store_raw_samples=bool(raw.get("store_raw_samples", True)),
        dataset_sizes=dict(raw.get("dataset_sizes", {})) or None,  # type: ignore[arg-type]
        vector_dataset_sizes=dict(raw.get("vector_dataset_sizes", {})) or None,  # type: ignore[arg-type]
    )
