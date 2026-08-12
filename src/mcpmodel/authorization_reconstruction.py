"""Task-only, independently reviewed reconstruction of missing authorization context."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcpmodel.normalizer import ToolNormalizer
from mcpmodel.validator import load_validator

REVIEW_FIELDS = [
    "draft_id",
    "scenario_group",
    "task_sha256",
    "candidate_count",
    "user_task",
    "reviewer_id",
    "decision",
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
    "task_evidence_quote",
    "notes",
]

ADJUDICATION_FIELDS = [
    "draft_id",
    "scenario_group",
    "task_sha256",
    "adjudicator",
    "decision",
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
    "task_evidence_quote",
    "resolution_reason",
]

BASIS_VALUES = {"task_explicit", "task_implied", "policy_defaulted"}
URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)


@dataclass(frozen=True)
class ObservedScope:
    tool: str
    action: str
    resource: str
    sink: str
    status: str


def _task_hash(task: str) -> str:
    return hashlib.sha256(task.encode("utf-8")).hexdigest()


def _host_sink(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}" if parsed.netloc else "<none>"


def _command_resource(command: str) -> str:
    token = re.split(r"[\s;&|]+", command.strip(), maxsplit=1)[0] if command.strip() else "unknown"
    token = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return f"command:{token}"


def _raw_action(tool: str, arguments: dict[str, Any]) -> str:
    if tool in {"exec", "shell"}:
        return "execute"
    if tool == "process":
        return "read" if str(arguments.get("action", "")).lower() in {"poll", "log"} else "manage"
    if tool in {"read", "memory_search", "web_fetch", "web_search"}:
        return "read"
    if tool == "write":
        return "write"
    if tool == "browser":
        return "read" if str(arguments.get("action", "")).lower() in {"open", "get"} else "manage"
    return str(arguments.get("action") or "unknown")


def normalize_observed_call(
    tool: str, arguments: dict[str, Any], normalizer: ToolNormalizer
) -> ObservedScope:
    raw_tool = tool.strip().lower()
    normalized = normalizer.normalize(raw_tool, _raw_action(raw_tool, arguments))
    resource = "unknown"
    sink = "<none>"
    if raw_tool in {"read", "write"}:
        resource = str(arguments.get("file_path") or arguments.get("path") or "unknown")
    elif raw_tool in {"exec", "shell"}:
        command = str(arguments.get("command") or "")
        resource = _command_resource(command)
        urls = URL_RE.findall(command)
        if urls:
            sink = _host_sink(urls[0].rstrip(").,;"))
    elif raw_tool == "process":
        resource = f"process:{arguments.get('sessionId', 'unknown')}"
    elif raw_tool in {"web_fetch", "browser"}:
        url = str(arguments.get("url") or "unknown")
        resource = url
        sink = _host_sink(url)
    elif raw_tool == "web_search":
        resource = f"search:{arguments.get('query', 'unknown')}"
        sink = "web:search-provider"
    elif raw_tool == "memory_search":
        resource = f"memory:{arguments.get('query', 'unknown')}"
    return ObservedScope(
        tool=normalized.tool_family,
        action=normalized.action,
        resource=resource,
        sink=sink,
        status=normalized.status,
    )


def _provenance(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    unique = {
        (record["source_id"], record["source_file"], record["source_file_sha256"])
        for record in records
    }
    return [
        {"source_id": source_id, "source_file": source_file, "source_file_sha256": digest}
        for source_id, source_file, digest in sorted(unique)
    ]


def _task_explicit_values(task: str, scopes: list[ObservedScope]) -> dict[str, list[str]]:
    """Return only literal values present in task text; never infer from observed behavior."""
    lowered_task = task.lower()
    resources = sorted(
        {
            scope.resource
            for scope in scopes
            if scope.resource != "unknown" and scope.resource.lower() in lowered_task
        }
    )
    sinks = sorted(
        {
            scope.sink
            for scope in scopes
            if scope.sink not in {"<none>", "web:search-provider"}
            and scope.sink.lower() in lowered_task
        }
    )
    return {"resources": resources, "sinks": sinks}


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def create_authorization_reconstruction_pack(
    records: list[dict[str, Any]], output_dir: Path, normalizer: ToolNormalizer
) -> dict[str, Any]:
    """Create group-level drafts and two independent blank review forms."""
    candidates = [record for record in records if record["usage_role"] == "candidate_tool_call"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in candidates:
        grouped[record["scenario_group"]].append(record)
    output_dir.mkdir(parents=True, exist_ok=False)

    drafts: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    unknown_normalizations = 0
    for group in sorted(grouped):
        group_records = sorted(
            grouped[group],
            key=lambda item: (item["payload"].get("call_index", 0), item["record_id"]),
        )
        tasks = {str(item["payload"].get("user_task", "")) for item in group_records}
        if len(tasks) != 1 or not next(iter(tasks)):
            raise ValueError(f"scenario group {group} must have exactly one non-empty user task")
        task = next(iter(tasks))
        scopes: list[ObservedScope] = []
        for record in group_records:
            payload = record["payload"]
            arguments = payload.get("arguments") or {}
            scope = normalize_observed_call(
                str(payload.get("tool", "unknown")), arguments, normalizer
            )
            scopes.append(scope)
            unknown_normalizations += int(scope.status == "unknown")
            inventory.append(
                {
                    "record_id": record["record_id"],
                    "scenario_group": group,
                    "call_index": payload.get("call_index"),
                    "timestamp": payload.get("timestamp") or "",
                    "raw_tool": payload.get("tool", "unknown"),
                    "normalized_tool": scope.tool,
                    "normalized_action": scope.action,
                    "normalized_resource": scope.resource,
                    "normalized_sink": scope.sink,
                    "normalization_status": scope.status,
                    "arguments_json": json.dumps(arguments, ensure_ascii=False, sort_keys=True),
                    "source_file": record["source_file"],
                    "source_locator": record["source_locator"],
                }
            )
        digest = _task_hash(task)
        explicit = _task_explicit_values(task, scopes)
        draft_id = f"authdraft_{hashlib.sha256((group + digest).encode()).hexdigest()[:16]}"
        draft = {
            "schema_version": "0.1.0",
            "draft_id": draft_id,
            "scenario_group": group,
            "case_ids": [item["record_id"] for item in group_records],
            "task_evidence": {"user_task": task, "sha256": digest},
            "candidate_count": len(group_records),
            "machine_proposal": {
                "subject": "unknown_external_agent",
                "tools": [],
                "actions": [],
                "resources": explicit["resources"],
                "sinks": explicit["sinks"],
                "valid_from": None,
                "valid_until": None,
                "max_calls": None,
            },
            "proposal_basis": {
                "subject": "task_implied",
                "tools": "not_evidenced",
                "actions": "not_evidenced",
                "resources": "task_explicit" if explicit["resources"] else "not_evidenced",
                "sinks": "task_explicit" if explicit["sinks"] else "not_evidenced",
                "temporal": "not_evidenced",
                "cardinality": "not_evidenced",
            },
            "provenance": _provenance(group_records),
            "review_status": "pending_independent_human_review",
        }
        drafts.append(draft)
        review_rows.append(
            {
                "draft_id": draft_id,
                "scenario_group": group,
                "task_sha256": digest,
                "candidate_count": len(group_records),
                "user_task": task,
            }
        )

    drafts_path = output_dir / "authorization-drafts.jsonl"
    drafts_path.write_text(
        "\n".join(json.dumps(draft, ensure_ascii=False, sort_keys=True) for draft in drafts) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        output_dir / "call-inventory.csv",
        [
            "record_id",
            "scenario_group",
            "call_index",
            "timestamp",
            "raw_tool",
            "normalized_tool",
            "normalized_action",
            "normalized_resource",
            "normalized_sink",
            "normalization_status",
            "arguments_json",
            "source_file",
            "source_locator",
        ],
        inventory,
    )
    _write_csv(output_dir / "authorization-review-A.csv", REVIEW_FIELDS, review_rows)
    _write_csv(output_dir / "authorization-review-B.csv", REVIEW_FIELDS, review_rows)
    _write_csv(
        output_dir / "authorization-adjudication.csv",
        ADJUDICATION_FIELDS,
        [
            {
                "draft_id": row["draft_id"],
                "scenario_group": row["scenario_group"],
                "task_sha256": row["task_sha256"],
            }
            for row in review_rows
        ],
    )
    manifest = {
        "schema_version": "0.1.0",
        "scenario_count": len(drafts),
        "candidate_count": len(candidates),
        "unknown_normalizations": unknown_normalizations,
        "review_design": "two_independent_task_only_reviewers_then_adjudication",
        "machine_proposal_is_authoritative": False,
        "attack_labels_in_pack": False,
        "drafts_sha256": hashlib.sha256(drafts_path.read_bytes()).hexdigest(),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _parse_array(value: str, field: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} must be a JSON array") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError(f"{field} must be a JSON array of strings")
    return sorted(set(parsed))


def _review_authorization(row: dict[str, str]) -> dict[str, Any]:
    basis = {
        name: row[f"{name}_basis"]
        for name in ("subject", "tools", "actions", "resources", "sinks", "temporal", "cardinality")
    }
    if set(basis.values()) - BASIS_VALUES:
        raise ValueError("all evidence basis fields must use the documented vocabulary")
    valid_from = row["valid_from"]
    valid_until = row["valid_until"]
    try:
        start = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
        end = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("valid_from and valid_until must be RFC 3339 date-time values") from exc
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError("valid_until must be later than valid_from and both need time zones")
    subject = row["subject"].strip()
    if not subject:
        raise ValueError("subject must be non-empty")
    return {
        "subject": subject,
        "tools": _parse_array(row["tools_json"], "tools_json"),
        "actions": _parse_array(row["actions_json"], "actions_json"),
        "resources": _parse_array(row["resources_json"], "resources_json"),
        "sinks": _parse_array(row["sinks_json"], "sinks_json"),
        "valid_from": valid_from,
        "valid_until": valid_until,
        "max_calls": int(row["max_calls"]),
        "evidence_basis": basis,
    }


def _read_indexed(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if any(not row.get("scenario_group") for row in rows):
        raise ValueError(f"{path.name} contains a row without scenario_group")
    indexed = {row["scenario_group"]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"{path.name} contains duplicate scenario_group values")
    return indexed


def finalize_authorization_reviews(
    pack_dir: Path, output_path: Path, schema_root: Path
) -> dict[str, Any]:
    """Finalize only double-reviewed groups; disagreements require explicit adjudication."""
    drafts = {
        item["scenario_group"]: item
        for item in (
            json.loads(line)
            for line in (pack_dir / "authorization-drafts.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        )
    }
    reviews_a = _read_indexed(pack_dir / "authorization-review-A.csv")
    reviews_b = _read_indexed(pack_dir / "authorization-review-B.csv")
    adjudications = _read_indexed(pack_dir / "authorization-adjudication.csv")
    if set(drafts) != set(reviews_a) or set(drafts) != set(reviews_b):
        raise ValueError("review rows must exactly match authorization drafts")

    validator = load_validator("reconstructed_authorization", schema_root)
    finalized: list[dict[str, Any]] = []
    excluded: list[str] = []
    for group in sorted(drafts):
        draft = drafts[group]
        row_a, row_b = reviews_a[group], reviews_b[group]
        if row_a["task_sha256"] != draft["task_evidence"]["sha256"]:
            raise ValueError(f"task hash mismatch in reviewer A row for {group}")
        if row_b["task_sha256"] != draft["task_evidence"]["sha256"]:
            raise ValueError(f"task hash mismatch in reviewer B row for {group}")
        reviewers = [row_a["reviewer_id"].strip(), row_b["reviewer_id"].strip()]
        if not all(reviewers) or len(set(reviewers)) != 2:
            raise ValueError(f"{group} requires two different reviewer IDs")
        decisions = [row_a["decision"].strip(), row_b["decision"].strip()]
        if any(decision not in {"include", "exclude"} for decision in decisions):
            raise ValueError(f"{group} has an invalid reviewer decision")
        if decisions == ["exclude", "exclude"]:
            excluded.append(group)
            continue
        adjudication = adjudications.get(group)
        if decisions[0] != decisions[1]:
            if adjudication is None or adjudication["decision"].strip() not in {
                "include",
                "exclude",
            }:
                raise ValueError(f"{group} decision disagreement requires completed adjudication")
            adjudicator = adjudication["adjudicator"].strip()
            reason = adjudication["resolution_reason"].strip()
            if not adjudicator or adjudicator in reviewers or not reason:
                raise ValueError(f"{group} requires an independent adjudicator and reason")
            if adjudication["decision"].strip() == "exclude":
                excluded.append(group)
                continue
            adjudication_quote = adjudication["task_evidence_quote"].strip()
            include_row = row_a if row_a["decision"] == "include" else row_b
            include_quote = include_row["task_evidence_quote"].strip()
            if not include_quote or not adjudication_quote:
                raise ValueError(f"{group} requires reviewer and adjudicator task evidence")
            authorization = _review_authorization(adjudication)
            quotes = [include_quote, adjudication_quote]
            resolution = "adjudicated"
        else:
            quotes = [row_a["task_evidence_quote"].strip(), row_b["task_evidence_quote"].strip()]
            if not all(quotes):
                raise ValueError(f"{group} requires a task-evidence quote from both reviewers")
            auth_a, auth_b = _review_authorization(row_a), _review_authorization(row_b)
            resolution = "agreement"
            adjudicator = None
            reason = "independent reviewer fields match exactly"
            authorization = auth_a
            if auth_a != auth_b:
                if adjudication is None or adjudication["decision"].strip() != "include":
                    raise ValueError(f"{group} disagreement requires completed adjudication")
                adjudicator = adjudication["adjudicator"].strip()
                reason = adjudication["resolution_reason"].strip()
                if not adjudicator or adjudicator in reviewers or not reason:
                    raise ValueError(f"{group} requires an independent adjudicator and reason")
                authorization = _review_authorization(adjudication)
                resolution = "adjudicated"
        authorization_digest = hashlib.sha256(
            (group + json.dumps(authorization, sort_keys=True)).encode()
        ).hexdigest()[:16]
        authorization_id = f"auth_{authorization_digest}"
        item = {
            "schema_version": "0.1.0",
            "authorization_id": authorization_id,
            "scenario_group": group,
            "case_ids": draft["case_ids"],
            "task_sha256": draft["task_evidence"]["sha256"],
            "authorization": authorization,
            "review": {
                "reviewer_ids": reviewers,
                "resolution": resolution,
                "adjudicator": adjudicator,
                "resolution_reason": reason,
                "task_evidence_quotes": quotes,
                "machine_proposal_not_authoritative": True,
            },
        }
        errors = sorted(validator.iter_errors(item), key=lambda error: list(error.path))
        if errors:
            raise ValueError(
                f"invalid reconstructed authorization for {group}: {errors[0].message}"
            )
        finalized.append(item)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in finalized)
        + ("\n" if finalized else ""),
        encoding="utf-8",
    )
    return {
        "finalized_count": len(finalized),
        "excluded_count": len(excluded),
        "excluded_groups": excluded,
        "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def load_reconstructed_authorizations(path: Path) -> dict[str, dict[str, Any]]:
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    indexed = {item["scenario_group"]: item for item in items}
    if len(indexed) != len(items):
        raise ValueError("duplicate scenario_group in reconstructed authorizations")
    return indexed
