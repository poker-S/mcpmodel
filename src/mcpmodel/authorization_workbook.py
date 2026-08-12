"""Import the human-friendly authorization workbook into canonical review CSV."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mcpmodel.authorization_reconstruction import (
    ADJUDICATION_FIELDS,
    BASIS_VALUES,
    REVIEW_FIELDS,
)
from mcpmodel.xlsx_reader import read_xlsx_values

BASIS_MAP = {
    "原文明确(task_explicit)": "task_explicit",
    "合理必需(task_implied)": "task_implied",
    "最小权限默认(policy_defaulted)": "policy_defaulted",
}
DECISION_MAP = {"纳入": "include", "排除": "exclude"}
KNOWN_TOOLS = {"filesystem", "shell", "http", "memory", "git", "secrets", "ci_deployment"}
KNOWN_ACTIONS = {
    "read",
    "write",
    "delete",
    "execute",
    "upload",
    "push",
    "deploy",
    "manage",
    "authenticate",
}
TASK_TIME_RE = re.compile(
    r"\[(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+GMT([+-]\d{1,2})\]"
)


def _value(matrix: list[list[object]], row: int, column: int) -> str:
    if row >= len(matrix) or column >= len(matrix[row]):
        return ""
    value = matrix[row][column]
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _load_drafts(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _split_values(value: str, *, none_alias: bool = False) -> list[str]:
    normalized = value.strip()
    if none_alias and normalized.lower() in {"无外发", "无", "none", "<none>"}:
        return ["<none>"]
    parts = [item.strip() for item in re.split(r"[,，;；\n]+", normalized) if item.strip()]
    return sorted(set(parts))


def _json_array(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _reference_time(task: str, fallback: datetime) -> datetime:
    match = TASK_TIME_RE.search(task)
    if not match:
        return fallback
    offset_hours = int(match.group(3))
    local = datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}:00").replace(
        tzinfo=UTC
    )
    return local - timedelta(hours=offset_hours)


def _rfc3339(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_internal_mapping(
    internal: list[list[object]], drafts: list[dict[str, Any]]
) -> None:
    for offset, draft in enumerate(drafts, start=4):
        row = offset - 1
        expected = [
            f"场景{offset - 3}",
            draft["draft_id"],
            draft["scenario_group"],
            draft["task_evidence"]["sha256"],
            str(draft["candidate_count"]),
        ]
        actual = [_value(internal, row, column) for column in range(5)]
        if actual != expected:
            raise ValueError(f"workbook internal mapping mismatch at 场景{offset - 3}")


def import_easy_authorization_workbook(
    workbook_path: Path,
    drafts_path: Path,
    output_csv: Path,
    *,
    expected_reviewer: str,
    fallback_reference_time: datetime = datetime(2026, 8, 12, tzinfo=UTC),
) -> dict[str, Any]:
    """Validate one A/B workbook and convert it to the canonical review CSV."""
    sheets = read_xlsx_values(workbook_path)
    required = {"填写说明", "授权内容", "证据依据", "内部校验（勿改）"}
    if missing := required - set(sheets):
        raise ValueError(f"workbook missing required sheets: {sorted(missing)}")
    drafts = _load_drafts(drafts_path)
    _validate_internal_mapping(sheets["内部校验（勿改）"], drafts)
    reviewer_id = _value(sheets["填写说明"], 3, 1)
    if not reviewer_id:
        raise ValueError("填写说明!B4 复核员代号不能为空")
    if reviewer_id.lower() in {"a", "b", "reviewer_a", "reviewer_b"}:
        raise ValueError("复核员代号必须能区分真实复核者，不能只填 A/B")

    content = sheets["授权内容"]
    evidence = sheets["证据依据"]
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    for index, draft in enumerate(drafts, start=1):
        row_number = index + 3
        row = row_number - 1
        scene = f"场景{index}"
        decision_text = _value(content, row, 2)
        decision = DECISION_MAP.get(decision_text, "")
        notes = _value(content, row, 11)
        canonical: dict[str, Any] = {
            "draft_id": draft["draft_id"],
            "scenario_group": draft["scenario_group"],
            "task_sha256": draft["task_evidence"]["sha256"],
            "candidate_count": draft["candidate_count"],
            "user_task": draft["task_evidence"]["user_task"],
            "reviewer_id": reviewer_id,
            "decision": decision,
            "notes": notes,
        }
        if not decision:
            errors.append(f"{scene}: 结论必须选择纳入或排除")
            rows.append(canonical)
            continue
        if decision == "exclude":
            if not notes:
                errors.append(f"{scene}: 排除时必须填写排除理由")
            rows.append(canonical)
            continue

        subject = _value(content, row, 3)
        tools = _split_values(_value(content, row, 4))
        actions = _split_values(_value(content, row, 5))
        resources = _split_values(_value(content, row, 6))
        sinks = _split_values(_value(content, row, 7), none_alias=True)
        quote = _value(content, row, 10)
        if unknown := set(tools) - KNOWN_TOOLS:
            errors.append(f"{scene}: 未知工具 {sorted(unknown)}")
        if unknown := set(actions) - KNOWN_ACTIONS:
            errors.append(f"{scene}: 未知动作 {sorted(unknown)}")
        if not subject or not tools or not actions or not resources or not sinks:
            errors.append(f"{scene}: 纳入时主体、工具、动作、对象和去向均不能为空")
        if not quote or quote not in draft["task_evidence"]["user_task"]:
            errors.append(f"{scene}: 任务原文依据必须逐字出现在用户任务中")
        if not notes:
            errors.append(f"{scene}: 纳入时必须填写限制条件")
        try:
            duration = int(float(_value(content, row, 8)))
            max_calls = int(float(_value(content, row, 9)))
            if duration < 1 or max_calls < 1:
                raise ValueError
        except ValueError:
            errors.append(f"{scene}: 授权时长和最多调用次数必须为正整数")
            duration, max_calls = 0, 0
        basis_names = (
            "subject",
            "tools",
            "actions",
            "resources",
            "sinks",
            "temporal",
            "cardinality",
        )
        basis: dict[str, str] = {}
        for column, name in enumerate(basis_names, start=1):
            basis[name] = BASIS_MAP.get(_value(evidence, row, column), "")
        if set(basis.values()) - BASIS_VALUES or "" in basis.values():
            errors.append(f"{scene}: 证据依据的 7 个下拉框必须全部填写")
        start = _reference_time(draft["task_evidence"]["user_task"], fallback_reference_time)
        canonical.update(
            {
                "subject": subject,
                "tools_json": _json_array(tools),
                "actions_json": _json_array(actions),
                "resources_json": _json_array(resources),
                "sinks_json": _json_array(sinks),
                "valid_from": _rfc3339(start),
                "valid_until": _rfc3339(start + timedelta(minutes=duration)),
                "max_calls": max_calls,
                "subject_basis": basis["subject"],
                "tools_basis": basis["tools"],
                "actions_basis": basis["actions"],
                "resources_basis": basis["resources"],
                "sinks_basis": basis["sinks"],
                "temporal_basis": basis["temporal"],
                "cardinality_basis": basis["cardinality"],
                "task_evidence_quote": quote,
            }
        )
        rows.append(canonical)
    if expected_reviewer not in {"A", "B"}:
        raise ValueError("expected_reviewer must be A or B")
    title = _value(sheets["填写说明"], 0, 0)
    if f"授权复核 {expected_reviewer}" not in title:
        raise ValueError(f"workbook is not the reviewer {expected_reviewer} template")
    if errors:
        raise ValueError("; ".join(errors))
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "reviewer_slot": expected_reviewer,
        "reviewer_id": reviewer_id,
        "scenario_count": len(rows),
        "included_count": sum(row["decision"] == "include" for row in rows),
        "excluded_count": sum(row["decision"] == "exclude" for row in rows),
        "output_sha256": hashlib.sha256(output_csv.read_bytes()).hexdigest(),
    }


AUTH_COMPARE_FIELDS = [
    "subject",
    "tools_json",
    "actions_json",
    "resources_json",
    "sinks_json",
    "valid_from",
    "valid_until",
    "max_calls",
    "subject_basis",
    "tools_basis",
    "actions_basis",
    "resources_basis",
    "sinks_basis",
    "temporal_basis",
    "cardinality_basis",
]


def _read_reviews(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    indexed = {row["scenario_group"]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"duplicate scenario_group in {path.name}")
    return indexed


def compare_authorization_reviews(
    review_a: Path, review_b: Path, adjudication_path: Path
) -> dict[str, Any]:
    """Compare independent reviews and create a canonical adjudication queue."""
    rows_a, rows_b = _read_reviews(review_a), _read_reviews(review_b)
    if set(rows_a) != set(rows_b):
        raise ValueError("review A/B scenario groups do not match")
    reviewers_a = {row["reviewer_id"] for row in rows_a.values()}
    reviewers_b = {row["reviewer_id"] for row in rows_b.values()}
    if len(reviewers_a) != 1 or len(reviewers_b) != 1:
        raise ValueError("each workbook must contain exactly one reviewer ID")
    if reviewers_a == reviewers_b:
        raise ValueError("reviewer A and B must be different people")

    results: list[dict[str, Any]] = []
    adjudication_rows: list[dict[str, str]] = []
    for group in sorted(rows_a):
        left, right = rows_a[group], rows_b[group]
        if left["draft_id"] != right["draft_id"] or left["task_sha256"] != right["task_sha256"]:
            raise ValueError(f"review provenance mismatch for {group}")
        decisions = [left["decision"], right["decision"]]
        if decisions == ["exclude", "exclude"]:
            status = "agreed_exclude"
        elif decisions != ["include", "include"]:
            status = "decision_disagreement"
        elif all(left[field] == right[field] for field in AUTH_COMPARE_FIELDS):
            status = "agreed_include"
        else:
            status = "authorization_disagreement"
        item = {
            "scenario_group": group,
            "draft_id": left["draft_id"],
            "reviewer_a_decision": left["decision"],
            "reviewer_b_decision": right["decision"],
            "status": status,
        }
        results.append(item)
        if "disagreement" in status:
            adjudication_rows.append(
                {
                    "draft_id": left["draft_id"],
                    "scenario_group": group,
                    "task_sha256": left["task_sha256"],
                }
            )
    adjudication_path.parent.mkdir(parents=True, exist_ok=True)
    with adjudication_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ADJUDICATION_FIELDS)
        writer.writeheader()
        writer.writerows(adjudication_rows)
    return {
        "scenario_count": len(results),
        "agreement_count": sum("agreed" in item["status"] for item in results),
        "disagreement_count": len(adjudication_rows),
        "adjudication_required": bool(adjudication_rows),
        "items": results,
    }
