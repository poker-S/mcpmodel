"""P1 rule and cost-sensitive multinomial logistic baselines."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mcpmodel.features import extract_features
from mcpmodel.rules import RISK_ORDINAL, HardRuleEngine

LABELS = ["L0", "L1", "L2", "L3", "L4"]
CATEGORICAL = ["tool_family", "action", "normalization_status", "resource_tag"]
NUMERIC = [
    "execution_capability",
    "side_effect",
    "source_untrust",
    "taint_confidence",
    "sink_external",
    "recursive",
    "obfuscation",
    "blast_radius",
    "redaction_available",
    "scope_rewrite_available",
    "confidentiality",
    "integrity",
    "availability",
    "tool_gap",
    "action_gap",
    "resource_gap",
    "sink_gap",
    "temporal_gap",
    "cardinality_gap",
    "subject_gap",
]


def feature_rows(cases: list[dict[str, Any]], config_dir: Path) -> list[dict[str, Any]]:
    return [extract_features(case, config_dir=config_dir) for case in cases]


def _records(rows: list[dict[str, Any]]) -> list[list[Any]]:
    return [[row[name] for name in CATEGORICAL + NUMERIC] for row in rows]


def train_logistic(cases: list[dict[str, Any]], config_dir: Path, seed: int) -> Pipeline:
    rows = feature_rows(cases, config_dir)
    transformer = ColumnTransformer(
        [
            ("categorical", OneHotEncoder(handle_unknown="ignore"), list(range(len(CATEGORICAL)))),
            (
                "numeric",
                StandardScaler(),
                list(range(len(CATEGORICAL), len(CATEGORICAL) + len(NUMERIC))),
            ),
        ]
    )
    model = LogisticRegression(
        class_weight="balanced", max_iter=2000, random_state=seed, solver="lbfgs"
    )
    pipeline = Pipeline([("features", transformer), ("model", model)])
    labels = [case["labels"]["inherent_risk"] for case in cases]
    pipeline.fit(_records(rows), labels)
    return pipeline


def predict_logistic(model: Pipeline, cases: list[dict[str, Any]], config_dir: Path) -> list[str]:
    return list(model.predict(_records(feature_rows(cases, config_dir))))


def predict_rules(cases: list[dict[str, Any]], config_dir: Path) -> list[str]:
    engine = HardRuleEngine(config_dir / "hard_rules.yaml")
    return [engine.evaluate(row).risk_floor for row in feature_rows(cases, config_dir)]


def metrics(cases: list[dict[str, Any]], predictions: list[str]) -> dict[str, Any]:
    truth = [case["labels"]["inherent_risk"] for case in cases]
    severe_truth = [label in {"L3", "L4"} for label in truth]
    severe_pred = [label in {"L3", "L4"} for label in predictions]
    severe_recall = recall_score(severe_truth, severe_pred, zero_division=0)
    ordinal_errors = [
        abs(RISK_ORDINAL[a] - RISK_ORDINAL[b])
        for a, b in zip(truth, predictions, strict=True)
    ]
    return {
        "case_count": len(cases),
        "accuracy": accuracy_score(truth, predictions),
        "macro_f1": f1_score(truth, predictions, labels=LABELS, average="macro", zero_division=0),
        "weighted_f1": f1_score(
            truth, predictions, labels=LABELS, average="weighted", zero_division=0
        ),
        "ordinal_mae": float(np.mean(ordinal_errors)),
        "severe_recall": severe_recall,
        "severe_miss_rate": 1.0 - severe_recall,
        "true_distribution": dict(sorted(Counter(truth).items())),
        "predicted_distribution": dict(sorted(Counter(predictions).items())),
        "confusion_matrix": confusion_matrix(truth, predictions, labels=LABELS).tolist(),
    }


def write_predictions(
    path: Path,
    cases: list[dict[str, Any]],
    rule_predictions: list[str],
    model_predictions: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "scenario_group",
                "truth",
                "rule_prediction",
                "logistic_prediction",
            ],
        )
        writer.writeheader()
        for case, rule_prediction, model_prediction in zip(
            cases, rule_predictions, model_predictions, strict=True
        ):
            writer.writerow(
                {
                    "case_id": case["case_id"],
                    "scenario_group": case["scenario_group"],
                    "truth": case["labels"]["inherent_risk"],
                    "rule_prediction": rule_prediction,
                    "logistic_prediction": model_prediction,
                }
            )


def write_run(
    output_dir: Path,
    train_cases: list[dict[str, Any]],
    evaluation_cases: dict[str, list[dict[str, Any]]],
    config_dir: Path,
    seed: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    model = train_logistic(train_cases, config_dir, seed)
    joblib.dump(model, output_dir / "logistic.joblib")
    report: dict[str, Any] = {
        "status": "pipeline_smoke_test_not_independent_evidence",
        "seed": seed,
        "train_case_count": len(train_cases),
        "splits": {},
    }
    for split_name, cases in evaluation_cases.items():
        rule_predictions = predict_rules(cases, config_dir)
        model_predictions = predict_logistic(model, cases, config_dir)
        report["splits"][split_name] = {
            "rule": metrics(cases, rule_predictions),
            "logistic": metrics(cases, model_predictions),
        }
        write_predictions(
            output_dir / f"predictions-{split_name}.csv",
            cases,
            rule_predictions,
            model_predictions,
        )
    (output_dir / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
