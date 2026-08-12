"""Fail-closed quality checks for external risk-annotation packs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

FORBIDDEN_CONTEXT_KEYS = {
    "source_labels",
    "unsafe",
    "safe",
    "expected_result",
    "attack_label",
    "vulnerability_type",
    "source_risk_label",
}


def _find_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_CONTEXT_KEYS:
                findings.append(child_path)
            findings.extend(_find_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_forbidden(child, f"{path}[{index}]"))
    return findings


def audit_external_annotation_pack(pack_dir: Path) -> dict[str, Any]:
    """Verify authorization freeze, context integrity, and source-label isolation."""
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("authorization_status") != "independently_reconstructed":
        raise ValueError("risk pack authorization is not independently reconstructed")
    contexts = [
        json.loads(line)
        for line in (pack_dir / "contexts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    case_ids = [context.get("case_id", "") for context in contexts]
    if not case_ids or len(set(case_ids)) != len(case_ids) or "" in case_ids:
        raise ValueError("contexts contain empty or duplicate case IDs")
    if len(contexts) != int(manifest.get("case_count", -1)):
        raise ValueError("manifest case count does not match contexts")
    errors: list[str] = []
    for context in contexts:
        case_id = context["case_id"]
        if forbidden := _find_forbidden(context):
            errors.append(f"{case_id}: forbidden keys {forbidden}")
        if not context.get("authorization_id"):
            errors.append(f"{case_id}: missing frozen authorization_id")
        authorization = context.get("authorization", {})
        if authorization.get("status") == "must_be_reconstructed_by_annotator":
            errors.append(f"{case_id}: authorization placeholder remains")
        call = context.get("call", {})
        for field in ("tool", "action", "resource", "sink", "arguments"):
            if field not in call or call[field] is None:
                errors.append(f"{case_id}: normalized call field {field} is missing")
    for labels_path in sorted(pack_dir.glob("labels-*.csv")):
        with labels_path.open(encoding="utf-8-sig", newline="") as handle:
            label_ids = [row.get("case_id", "") for row in csv.DictReader(handle)]
        if label_ids != case_ids:
            errors.append(f"{labels_path.name}: case order or IDs do not match contexts")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "status": "passed",
        "case_count": len(contexts),
        "scenario_count": len({context["scenario_group"] for context in contexts}),
        "forbidden_context_key_count": 0,
        "authorization_placeholder_count": 0,
        "label_sheet_count": len(list(pack_dir.glob("labels-*.csv"))),
    }
