from pathlib import Path

import pytest

from ai_db_benchmark.config import BenchmarkConfig, load_benchmark_config


def test_config_validates_iterations() -> None:
    with pytest.raises(ValueError):
        BenchmarkConfig(measured_iterations=0)


def test_million_preset_targets_one_million_total_rows() -> None:
    config = BenchmarkConfig(dataset_size="million")

    assert config.customer_count == 120660


def test_load_simple_benchmark_config(tmp_path: Path) -> None:
    config_file = tmp_path / "benchmark.yaml"
    config_file.write_text(
        "\n".join(
            [
                "dataset_size: smoke",
                "seed: 7",
                "warmup_iterations: 1",
                "measured_iterations: 2",
                "batch_size: 5",
                "store_raw_samples: true",
                "dataset_sizes:",
                "  smoke: 12",
            ]
        ),
        encoding="utf-8",
    )

    config = load_benchmark_config(config_file)

    assert config.seed == 7
    assert config.customer_count == 12
