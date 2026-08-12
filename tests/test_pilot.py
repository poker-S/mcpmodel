from mcpmodel.pilot import canonical_hash, generate_pilot, manifest


def test_pilot_is_deterministic_and_balanced_enough_for_smoke_test() -> None:
    first = generate_pilot()
    second = generate_pilot()
    assert len(first) == 30
    assert len({case["scenario_group"] for case in first}) == 15
    assert canonical_hash(first) == canonical_hash(second)
    summary = manifest(first)
    assert all(level in summary["risk_distribution"] for level in ("L0", "L1", "L2", "L3", "L4"))
    assert summary["label_status"] == "scenario_design_not_human_adjudicated"
