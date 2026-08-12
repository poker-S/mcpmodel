"""Create blinded annotation packs and validate returned label sheets."""

from __future__ import annotations

import csv
import hashlib
import json
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
from sklearn.metrics import cohen_kappa_score

RISK_LEVELS = {"L0", "L1", "L2", "L3", "L4"}
ACTIONS = {"allow", "isolate", "rewrite", "approve", "deny"}
RISK_ORDER = ["L0", "L1", "L2", "L3", "L4"]
GAP_VALUES = {"0", "0.5", "1"}
GAP_FIELDS = [
    "tool_scope",
    "action_scope",
    "resource_scope",
    "sink_scope",
    "temporal_scope",
    "subject_scope",
]
OUTPUT_FIELDS = [
    "case_id",
    "annotator_id",
    "inherent_risk",
    "recommended_action",
    *GAP_FIELDS,
    "reason_codes",
    "note",
]


def _context(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "scenario_group": case["scenario_group"],
        "user_task": case["user_task"],
        "authorization": case["authorization"],
        "provenance": case["provenance"],
        "call": case["call"],
    }


def create_annotation_pack(
    cases: list[dict[str, Any]], output_dir: Path, annotators: tuple[str, ...] = ("A", "B", "C")
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    contexts = [_context(case) for case in cases]
    context_path = output_dir / "contexts.jsonl"
    context_path.write_text(
        "\n".join(json.dumps(context, ensure_ascii=False, sort_keys=True) for context in contexts)
        + "\n",
        encoding="utf-8",
    )
    for annotator in annotators:
        with (output_dir / f"labels-{annotator}.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            for case in cases:
                writer.writerow({"case_id": case["case_id"], "annotator_id": annotator})
    digest = hashlib.sha256(context_path.read_bytes()).hexdigest()
    result = {
        "case_count": len(cases),
        "annotators": list(annotators),
        "contexts_sha256": digest,
        "labels_hidden": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def validate_annotation_sheet(path: Path, expected_ids: set[str]) -> list[str]:
    errors: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row.get("case_id", "") for row in rows]
    if set(ids) != expected_ids or len(ids) != len(expected_ids):
        errors.append("case_id set, duplication, or row count mismatch")
    for line_number, row in enumerate(rows, start=2):
        if row.get("inherent_risk") not in RISK_LEVELS:
            errors.append(f"line {line_number}: invalid inherent_risk")
        if row.get("recommended_action") not in ACTIONS:
            errors.append(f"line {line_number}: invalid recommended_action")
        for field in GAP_FIELDS:
            if row.get(field) not in GAP_VALUES:
                errors.append(f"line {line_number}: invalid {field}")
    return errors


def read_annotation_sheet(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_annotation_sheets(paths: list[Path]) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    if len(paths) < 2:
        return set(), ["at least two annotation sheets are required"]
    first_rows = read_annotation_sheet(paths[0])
    expected_ids = {row.get("case_id", "") for row in first_rows}
    seen_annotators: set[str] = set()
    for path in paths:
        sheet_errors = validate_annotation_sheet(path, expected_ids)
        errors.extend(f"{path}: {error}" for error in sheet_errors)
        annotators = {row.get("annotator_id", "") for row in read_annotation_sheet(path)}
        if len(annotators) != 1 or "" in annotators:
            errors.append(f"{path}: exactly one non-empty annotator_id is required")
        else:
            annotator = next(iter(annotators))
            if annotator in seen_annotators:
                errors.append(f"{path}: duplicate annotator_id {annotator}")
            seen_annotators.add(annotator)
    return expected_ids, errors


def _index_rows(paths: list[Path]) -> tuple[list[str], dict[str, dict[str, dict[str, str]]]]:
    by_annotator: dict[str, dict[str, dict[str, str]]] = {}
    for path in paths:
        rows = read_annotation_sheet(path)
        annotator = rows[0]["annotator_id"]
        by_annotator[annotator] = {row["case_id"]: row for row in rows}
    case_ids = sorted(next(iter(by_annotator.values())))
    return case_ids, by_annotator


def _fleiss_kappa(values: list[list[str]], categories: list[str]) -> float | None:
    if not values:
        return None
    counts = np.array(
        [[sum(value == category for value in row) for category in categories] for row in values],
        dtype=float,
    )
    ratings = counts.sum(axis=1)
    if np.any(ratings != ratings[0]) or ratings[0] < 2:
        raise ValueError("each item must have the same number of ratings")
    n = ratings[0]
    observed = np.mean((np.sum(counts**2, axis=1) - n) / (n * (n - 1)))
    proportions = counts.sum(axis=0) / counts.sum()
    expected = float(np.sum(proportions**2))
    if expected == 1.0:
        return 1.0
    return float((observed - expected) / (1.0 - expected))


def agreement_report(paths: list[Path]) -> dict[str, Any]:
    _, errors = validate_annotation_sheets(paths)
    if errors:
        raise ValueError("; ".join(errors))
    case_ids, indexed = _index_rows(paths)
    annotators = sorted(indexed)

    risk_rows = [
        [indexed[annotator][case_id]["inherent_risk"] for annotator in annotators]
        for case_id in case_ids
    ]
    action_rows = [
        [indexed[annotator][case_id]["recommended_action"] for annotator in annotators]
        for case_id in case_ids
    ]
    pairwise = []
    for left, right in combinations(annotators, 2):
        left_risk = [indexed[left][case_id]["inherent_risk"] for case_id in case_ids]
        right_risk = [indexed[right][case_id]["inherent_risk"] for case_id in case_ids]
        pairwise.append(
            {
                "annotators": [left, right],
                "risk_quadratic_weighted_kappa": float(
                    cohen_kappa_score(
                        left_risk, right_risk, labels=RISK_ORDER, weights="quadratic"
                    )
                ),
                "risk_exact_agreement": mean(
                    a == b for a, b in zip(left_risk, right_risk, strict=True)
                ),
            }
        )

    disagreements = []
    for case_id, risks, actions in zip(case_ids, risk_rows, action_rows, strict=True):
        if len(set(risks)) > 1 or len(set(actions)) > 1:
            disagreements.append(
                {
                    "case_id": case_id,
                    "risks": dict(zip(annotators, risks, strict=True)),
                    "actions": dict(zip(annotators, actions, strict=True)),
                }
            )
    return {
        "status": "human_annotation_agreement",
        "case_count": len(case_ids),
        "annotators": annotators,
        "risk_fleiss_kappa_unweighted": _fleiss_kappa(risk_rows, RISK_ORDER),
        "action_fleiss_kappa_unweighted": _fleiss_kappa(action_rows, sorted(ACTIONS)),
        "risk_unanimous_rate": mean(len(set(row)) == 1 for row in risk_rows),
        "action_unanimous_rate": mean(len(set(row)) == 1 for row in action_rows),
        "pairwise": pairwise,
        "risk_pairwise_qwk_mean": mean(
            item["risk_quadratic_weighted_kappa"] for item in pairwise
        ),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }


def write_adjudication_queue(path: Path, report: dict[str, Any]) -> None:
    fields = [
        "case_id",
        "annotator_risks",
        "annotator_actions",
        "adjudicated_risk",
        "adjudicated_action",
        "reason_codes",
        "adjudicator_id",
        "adjudication_note",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in report["disagreements"]:
            writer.writerow(
                {
                    "case_id": item["case_id"],
                    "annotator_risks": json.dumps(item["risks"], ensure_ascii=False),
                    "annotator_actions": json.dumps(item["actions"], ensure_ascii=False),
                }
            )


def finalize_human_labels(
    sheets: list[Path], adjudication_path: Path, output_path: Path
) -> dict[str, Any]:
    report = agreement_report(sheets)
    case_ids, indexed = _index_rows(sheets)
    annotators = sorted(indexed)
    with adjudication_path.open(encoding="utf-8-sig", newline="") as handle:
        adjudications = {row["case_id"]: row for row in csv.DictReader(handle)}
    expected = {item["case_id"] for item in report["disagreements"]}
    if set(adjudications) != expected or len(adjudications) != len(expected):
        raise ValueError("adjudication case IDs must exactly match the disagreement queue")

    output_rows: list[dict[str, str]] = []
    for case_id in case_ids:
        risks = [indexed[annotator][case_id]["inherent_risk"] for annotator in annotators]
        actions = [
            indexed[annotator][case_id]["recommended_action"] for annotator in annotators
        ]
        if len(set(risks)) == 1 and len(set(actions)) == 1:
            risk, action = risks[0], actions[0]
            source, adjudicator, reasons, note = "unanimous", "", "", ""
        else:
            row = adjudications[case_id]
            risk, action = row.get("adjudicated_risk", ""), row.get(
                "adjudicated_action", ""
            )
            adjudicator = row.get("adjudicator_id", "").strip()
            reasons = row.get("reason_codes", "").strip()
            note = row.get("adjudication_note", "").strip()
            if risk not in RISK_LEVELS or action not in ACTIONS:
                raise ValueError(f"{case_id}: invalid adjudicated risk/action")
            if not adjudicator or not note:
                raise ValueError(f"{case_id}: adjudicator_id and adjudication_note are required")
            source = "adjudicated"
        output_rows.append(
            {
                "case_id": case_id,
                "inherent_risk": risk,
                "recommended_action": action,
                "label_source": source,
                "reason_codes": reasons,
                "adjudicator_id": adjudicator,
                "adjudication_note": note,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return {
        "case_count": len(output_rows),
        "unanimous_count": sum(row["label_source"] == "unanimous" for row in output_rows),
        "adjudicated_count": sum(row["label_source"] == "adjudicated" for row in output_rows),
        "output_sha256": digest,
    }
