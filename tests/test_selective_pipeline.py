import json
from pathlib import Path

import numpy as np
import pytest

from mcpmodel.calibration import fit_temperature
from mcpmodel.conformal import fit_conformal
from mcpmodel.decision import decide
from mcpmodel.ordinal import predict_ordinal_proba, probability_labels, train_ordinal
from mcpmodel.selective import (
    _assert_role_isolation,
    split_validation_roles,
    write_selective_run,
)

ROOT = Path(__file__).resolve().parents[1]


def _cases_and_splits() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    cases = {
        case["case_id"]: case
        for case in map(
            json.loads,
            (ROOT / "data" / "pilot" / "pilot-0.1.jsonl")
            .read_text(encoding="utf-8")
            .splitlines(),
        )
    }
    manifest = json.loads(
        (ROOT / "data" / "splits" / "pilot-0.1.json").read_text(encoding="utf-8")
    )
    splits = {
        name: [cases[case_id] for case_id in details["case_ids"]]
        for name, details in manifest["splits"].items()
    }
    return cases, splits


def test_ordinal_probabilities_are_valid_and_deterministic() -> None:
    _, splits = _cases_and_splits()
    first = train_ordinal(splits["train"], ROOT / "configs", 20260812)
    second = train_ordinal(splits["train"], ROOT / "configs", 20260812)
    first_probabilities = predict_ordinal_proba(first, splits["validation"], ROOT / "configs")
    second_probabilities = predict_ordinal_proba(second, splits["validation"], ROOT / "configs")
    assert first_probabilities.shape == (6, 5)
    assert np.all(first_probabilities >= 0.0)
    assert np.allclose(first_probabilities.sum(axis=1), 1.0)
    assert np.allclose(first_probabilities, second_probabilities)
    assert len(probability_labels(first_probabilities)) == 6


def test_calibration_roles_and_artifacts_are_isolated(tmp_path: Path) -> None:
    _, splits = _cases_and_splits()
    probability_cases, conformal_cases = split_validation_roles(
        splits["validation"],
        probability_calibration_groups=["action_scope"],
        conformal_calibration_groups=["time_window", "workspace_delete"],
    )
    output = tmp_path / "selective-run"
    report = write_selective_run(
        output,
        train_cases=splits["train"],
        probability_calibration_cases=probability_cases,
        conformal_calibration_cases=conformal_cases,
        test_cases=splits["test"],
        config_dir=ROOT / "configs",
        seed=20260812,
        alpha=0.2,
        repository_root=ROOT,
        input_artifacts={
            "data": ROOT / "data" / "pilot" / "pilot-0.1.jsonl",
            "split": ROOT / "data" / "splits" / "pilot-0.1.json",
        },
        config_artifacts={
            "selective_pipeline.yaml": ROOT / "configs" / "selective_pipeline.yaml"
        },
    )
    assert report["status"] == "pipeline_smoke_test_not_independent_evidence"
    assert report["formal_research_use_allowed"] is False
    assert "conformal_risk_sets_are_trivial_full_label_sets" in report["limitations"]
    assert report["test_usage"] == "evaluation_only_not_used_for_fit_calibration_or_thresholds"
    assert set(report["roles"]["test"]["case_ids"]) == {
        case["case_id"] for case in splits["test"]
    }
    assert (output / "selective-model.joblib").is_file()
    assert (output / "predictions-test.csv").is_file()
    assert (output / "metrics.json").is_file()
    assert (output / "reproduction-manifest.json").is_file()
    assert (output / "config-snapshot" / "selective_pipeline.yaml").is_file()


def test_role_isolation_rejects_scenario_group_leakage() -> None:
    _, splits = _cases_and_splits()
    with pytest.raises(ValueError, match="scenario_group leakage"):
        _assert_role_isolation(
            {
                "train": [splits["train"][0]],
                "test": [splits["train"][1]],
            }
        )


def test_conformal_set_is_nonempty_and_records_fit_cases() -> None:
    _, splits = _cases_and_splits()
    model = train_ordinal(splits["train"], ROOT / "configs", 20260812)
    probability_cases, conformal_cases = split_validation_roles(
        splits["validation"],
        probability_calibration_groups=["action_scope"],
        conformal_calibration_groups=["time_window", "workspace_delete"],
    )
    probability_raw = predict_ordinal_proba(model, probability_cases, ROOT / "configs")
    calibrator = fit_temperature(probability_raw, probability_cases)
    conformal_probabilities = calibrator.transform(
        predict_ordinal_proba(model, conformal_cases, ROOT / "configs")
    )
    conformal = fit_conformal(conformal_probabilities, conformal_cases, alpha=0.2)
    test_sets = conformal.predict(
        calibrator.transform(predict_ordinal_proba(model, splits["test"], ROOT / "configs"))
    )
    assert calibrator.fitted_case_ids == tuple(case["case_id"] for case in probability_cases)
    assert conformal.fitted_case_ids == tuple(case["case_id"] for case in conformal_cases)
    assert all(risk_set for risk_set in test_sets)


def test_only_hard_rule_can_automatically_deny() -> None:
    cases, splits = _cases_and_splits()
    delete_case = cases["pilot_006"]
    hard_deny = decide(
        delete_case,
        np.asarray([0.0, 0.0, 0.0, 0.0, 1.0]),
        ("L4",),
        config_dir=ROOT / "configs",
    )
    assert hard_deny.action == "deny"
    assert "HARD_RULE_DENY" in hard_deny.reason_codes

    no_deny_rule = splits["test"][0]
    statistical_high_risk = decide(
        no_deny_rule,
        np.asarray([0.0, 0.0, 0.0, 0.0, 1.0]),
        ("L4",),
        config_dir=ROOT / "configs",
    )
    assert statistical_high_risk.action == "approve"
