"""Create blinded annotation packs and validate returned label sheets."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

RISK_LEVELS = {"L0", "L1", "L2", "L3", "L4"}
ACTIONS = {"allow", "isolate", "rewrite", "approve", "deny"}
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
