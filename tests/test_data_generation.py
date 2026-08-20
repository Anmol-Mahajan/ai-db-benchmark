from ai_db_benchmark.data.generator import generate_enterprise_dataset


def test_enterprise_dataset_is_deterministic() -> None:
    first = generate_enterprise_dataset(50, seed=123)
    second = generate_enterprise_dataset(50, seed=123)

    assert first.table_counts() == second.table_counts()
    assert first.stable_hash() == second.stable_hash()
    assert first.customers[0]["customer_name"] == "Customer 00001"


def test_enterprise_dataset_has_expected_tables() -> None:
    dataset = generate_enterprise_dataset(25, seed=42)

    counts = dataset.table_counts()
    assert counts["customers"] == 25
    assert counts["salespeople"] >= 5
    assert counts["contracts"] >= 25
    assert counts["invoices"] == 75
    assert "support_tickets" in counts
