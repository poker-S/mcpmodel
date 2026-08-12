"""End-to-end ordinal, calibrated and selective-governance smoke pipeline."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import cohen_kappa_score, f1_score, recall_score

from mcpmodel.baseline import LABELS
from mcpmodel.calibration import fit_temperature
from mcpmodel.conformal import fit_conformal
from mcpmodel.decision import GovernanceDecision, decide
from mcpmodel.ordinal import predict_ordinal_proba, probability_labels, train_ordinal
from mcpmodel.reproducibility import atomic_run_directory, write_reproduction_manifest


def _assert_role_isolation(roles: dict[str, list[dict[str, Any]]]) -> None:
    ids_by_role = {
        role: {str(case["case_id"]) for case in cases} for role, cases in roles.items()
    }
    groups_by_role = {
        role: {str(case["scenario_group"]) for case in cases} for role, cases in roles.items()
    }
    for left, left_ids in ids_by_role.items():
        for right, right_ids in ids_by_role.items():
            if left >= right:
                continue
            overlap = left_ids & right_ids
            if overlap:
                raise ValueError(f"case leakage between {left} and {right}: {sorted(overlap)}")
            group_overlap = groups_by_role[left] & groups_by_role[right]
            if group_overlap:
                raise ValueError(
                    f"scenario_group leakage between {left} and {right}: {sorted(group_overlap)}"
                )


def split_validation_roles(
    validation_cases: list[dict[str, Any]],
    *,
    probability_calibration_groups: list[str],
    conformal_calibration_groups: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    probability_groups = set(probability_calibration_groups)
    conformal_groups = set(conformal_calibration_groups)
    if not probability_groups or not conformal_groups:
        raise ValueError("both calibration roles need at least one scenario group")
    if probability_groups & conformal_groups:
        raise ValueError("probability and conformal calibration groups must be disjoint")
    actual_groups = {str(case["scenario_group"]) for case in validation_cases}
    configured_groups = probability_groups | conformal_groups
    if actual_groups != configured_groups:
        raise ValueError(
            "calibration group configuration must partition validation groups exactly; "
            f"actual={sorted(actual_groups)} configured={sorted(configured_groups)}"
        )
    probability_cases = [
        case for case in validation_cases if case["scenario_group"] in probability_groups
    ]
    conformal_cases = [
        case for case in validation_cases if case["scenario_group"] in conformal_groups
    ]
    return probability_cases, conformal_cases


def probability_metrics(cases: list[dict[str, Any]], probabilities: np.ndarray) -> dict[str, Any]:
    labels = {label: index for index, label in enumerate(LABELS)}
    truth = np.asarray([labels[case["labels"]["inherent_risk"]] for case in cases], dtype=int)
    predicted = np.argmax(probabilities, axis=1)
    one_hot = np.eye(len(LABELS))[truth]
    confidence = probabilities.max(axis=1)
    correctness = (predicted == truth).astype(float)
    bins = np.linspace(0.0, 1.0, 11)
    ece = 0.0
    for lower, upper in zip(bins[:-1], bins[1:], strict=True):
        selected = (confidence > lower) & (confidence <= upper)
        if np.any(selected):
            ece += float(selected.mean()) * abs(
                float(correctness[selected].mean()) - float(confidence[selected].mean())
            )
    severe_truth = truth >= 3
    severe_prediction = predicted >= 3
    kappa = float(cohen_kappa_score(truth, predicted, weights="quadratic"))
    return {
        "case_count": len(cases),
        "macro_f1": float(
            f1_score(
                truth,
                predicted,
                labels=list(range(len(LABELS))),
                average="macro",
                zero_division=0,
            )
        ),
        "ordinal_mae": float(np.abs(truth - predicted).mean()),
        "quadratic_weighted_kappa": kappa if np.isfinite(kappa) else None,
        "severe_recall": float(recall_score(severe_truth, severe_prediction, zero_division=0)),
        "brier_multiclass": float(np.square(probabilities - one_hot).sum(axis=1).mean()),
        "negative_log_likelihood": float(
            -np.log(np.clip(probabilities[np.arange(len(truth)), truth], 1e-12, 1.0)).mean()
        ),
        "ece_10_bin": ece,
        "true_distribution": dict(
            sorted(Counter(case["labels"]["inherent_risk"] for case in cases).items())
        ),
        "predicted_distribution": dict(sorted(Counter(probability_labels(probabilities)).items())),
    }


def selective_metrics(
    cases: list[dict[str, Any]],
    risk_sets: list[tuple[str, ...]],
    decisions: list[GovernanceDecision],
) -> dict[str, Any]:
    truth = [case["labels"]["inherent_risk"] for case in cases]
    covered = [label in risk_set for label, risk_set in zip(truth, risk_sets, strict=True)]
    severe_indices = [index for index, label in enumerate(truth) if label in {"L3", "L4"}]
    benign_indices = [index for index, label in enumerate(truth) if label in {"L0", "L1"}]
    severe_misses = sum(decisions[index].action == "allow" for index in severe_indices)
    benign_blocks = sum(decisions[index].action in {"approve", "deny"} for index in benign_indices)
    actions = [decision.action for decision in decisions]
    return {
        "empirical_coverage": float(np.mean(covered)),
        "mean_set_size": float(np.mean([len(risk_set) for risk_set in risk_sets])),
        "approval_rate": actions.count("approve") / len(actions),
        "deny_rate": actions.count("deny") / len(actions),
        "automatic_action_rate": sum(
            action in {"allow", "isolate", "rewrite"} for action in actions
        )
        / len(actions),
        "severe_miss_rate": severe_misses / len(severe_indices) if severe_indices else 0.0,
        "benign_block_rate": benign_blocks / len(benign_indices) if benign_indices else 0.0,
        "action_distribution": dict(sorted(Counter(actions).items())),
    }


def _write_predictions(
    path: Path,
    cases: list[dict[str, Any]],
    raw: np.ndarray,
    calibrated: np.ndarray,
    risk_sets: list[tuple[str, ...]],
    decisions: list[GovernanceDecision],
) -> None:
    probability_fields = [f"p_{label}" for label in LABELS]
    raw_probability_fields = [f"raw_p_{label}" for label in LABELS]
    fields = [
        "case_id",
        "scenario_group",
        "truth",
        "recommended_action",
        *probability_fields,
        *raw_probability_fields,
        "predicted_risk",
        "risk_set",
        "governance_action",
        "hard_risk_floor",
        "matched_rules",
        "reason_codes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case, raw_row, calibrated_row, risk_set, decision in zip(
            cases, raw, calibrated, risk_sets, decisions, strict=True
        ):
            row: dict[str, Any] = {
                "case_id": case["case_id"],
                "scenario_group": case["scenario_group"],
                "truth": case["labels"]["inherent_risk"],
                "recommended_action": case["labels"]["recommended_action"],
                "predicted_risk": decision.predicted_risk,
                "risk_set": "|".join(risk_set),
                "governance_action": decision.action,
                "hard_risk_floor": decision.hard_risk_floor,
                "matched_rules": "|".join(decision.matched_rules),
                "reason_codes": "|".join(decision.reason_codes),
            }
            for label, raw_value, calibrated_value in zip(
                LABELS, raw_row, calibrated_row, strict=True
            ):
                row[f"p_{label}"] = f"{calibrated_value:.12f}"
                row[f"raw_p_{label}"] = f"{raw_value:.12f}"
            writer.writerow(row)


def write_selective_run(
    output_dir: Path,
    *,
    train_cases: list[dict[str, Any]],
    probability_calibration_cases: list[dict[str, Any]],
    conformal_calibration_cases: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
    config_dir: Path,
    seed: int,
    alpha: float,
    repository_root: Path | None = None,
    input_artifacts: dict[str, Path] | None = None,
    config_artifacts: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Run a fixed smoke pipeline without using test cases for fitting or calibration."""
    roles = {
        "train": train_cases,
        "probability_calibration": probability_calibration_cases,
        "conformal_calibration": conformal_calibration_cases,
        "test": test_cases,
    }
    if any(not cases for cases in roles.values()):
        raise ValueError("every data role must be non-empty")
    _assert_role_isolation(roles)
    model = train_ordinal(train_cases, config_dir, seed)
    probability_raw = predict_ordinal_proba(model, probability_calibration_cases, config_dir)
    calibrator = fit_temperature(probability_raw, probability_calibration_cases)
    conformal_raw = predict_ordinal_proba(model, conformal_calibration_cases, config_dir)
    conformal_probabilities = calibrator.transform(conformal_raw)
    conformal = fit_conformal(
        conformal_probabilities, conformal_calibration_cases, alpha=alpha
    )
    limitations = [
        "synthetic_scenario_design_labels_are_not_independent_human_ground_truth",
    ]
    if len(probability_calibration_cases) < 30:
        limitations.append("probability_calibration_sample_is_too_small_for_research_claims")
    if len(conformal_calibration_cases) < 30:
        limitations.append("conformal_calibration_sample_is_too_small_for_research_claims")
    temperature_at_boundary = (
        calibrator.temperature <= np.exp(-3.0) * 1.001
        or calibrator.temperature >= np.exp(3.0) / 1.001
    )
    if temperature_at_boundary:
        limitations.append("temperature_optimizer_reached_configured_search_boundary")
    if conformal.score_quantile >= 1.0 - 1e-12:
        limitations.append("conformal_risk_sets_are_trivial_full_label_sets")

    report: dict[str, Any] = {
        "status": "pipeline_smoke_test_not_independent_evidence",
        "formal_research_use_allowed": False,
        "test_usage": "evaluation_only_not_used_for_fit_calibration_or_thresholds",
        "limitations": limitations,
        "seed": seed,
        "alpha": alpha,
        "temperature": calibrator.temperature,
        "conformal_score_quantile": conformal.score_quantile,
        "roles": {
            role: {
                "case_ids": [case["case_id"] for case in cases],
                "scenario_groups": sorted({case["scenario_group"] for case in cases}),
            }
            for role, cases in roles.items()
        },
        "splits": {},
    }
    with atomic_run_directory(output_dir) as working_dir:
        joblib.dump(
            {"model": model, "calibrator": calibrator, "conformal": conformal},
            working_dir / "selective-model.joblib",
        )
        for role, cases in roles.items():
            raw = predict_ordinal_proba(model, cases, config_dir)
            calibrated = calibrator.transform(raw)
            risk_sets = conformal.predict(calibrated)
            decisions = [
                decide(case, row, risk_set, config_dir=config_dir)
                for case, row, risk_set in zip(cases, calibrated, risk_sets, strict=True)
            ]
            report["splits"][role] = {
                "probability": probability_metrics(cases, calibrated),
                "selective": selective_metrics(cases, risk_sets, decisions),
            }
            _write_predictions(
                working_dir / f"predictions-{role}.csv",
                cases,
                raw,
                calibrated,
                risk_sets,
                decisions,
            )

        (working_dir / "metrics.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        manifest_arguments = (repository_root, input_artifacts, config_artifacts)
        if any(argument is not None for argument in manifest_arguments):
            if any(argument is None for argument in manifest_arguments):
                raise ValueError("all reproduction manifest arguments must be supplied together")
            write_reproduction_manifest(
                working_dir,
                repository_root=repository_root,
                input_artifacts=input_artifacts,
                config_artifacts=config_artifacts,
            )
    return report
