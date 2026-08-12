import csv
import json
from pathlib import Path

import pytest

from mcpmodel.authorization_reconstruction import (
    REVIEW_FIELDS,
    create_authorization_reconstruction_pack,
    finalize_authorization_reviews,
    normalize_observed_call,
)
from mcpmodel.normalizer import ToolNormalizer

CONFIG = Path(__file__).parents[1] / "configs" / "tool_normalization.yaml"
SCHEMAS = Path(__file__).parents[1] / "schemas"


def _record(record_id: str, index: int, tool: str, arguments: dict) -> dict:
    return {
        "record_id": record_id,
        "scenario_group": "group_001",
        "usage_role": "candidate_tool_call",
        "source_id": "source_001",
        "source_kind": "agent_trajectory",
        "source_file": "case/session.jsonl",
        "source_file_sha256": "a" * 64,
        "source_locator": f"line:{index}",
        "source_labels": {},
        "payload": {
            "user_task": "check the service status",
            "tool": tool,
            "arguments": arguments,
            "call_index": index,
            "source_untrust": 1.0,
            "timestamp": f"2026-08-12T00:00:0{index}Z",
        },
    }


def _fill_reviews(pack: Path, mismatch: bool = False) -> None:
    values = {
        "decision": "include",
        "subject": "external_agent",
        "tools_json": '["http"]',
        "actions_json": '["read"]',
        "resources_json": '["https://example.test/status"]',
        "sinks_json": '["https://example.test"]',
        "valid_from": "2026-08-12T00:00:00Z",
        "valid_until": "2026-08-12T00:10:00Z",
        "max_calls": "2",
        "subject_basis": "task_implied",
        "tools_basis": "task_implied",
        "actions_basis": "task_implied",
        "resources_basis": "task_explicit",
        "sinks_basis": "task_implied",
        "temporal_basis": "policy_defaulted",
        "cardinality_basis": "policy_defaulted",
        "task_evidence_quote": "check the service status",
    }
    for reviewer in ("A", "B"):
        path = pack / f"authorization-review-{reviewer}.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            row = next(csv.DictReader(handle))
        row.update(values)
        row["reviewer_id"] = f"reviewer_{reviewer.lower()}"
        if mismatch and reviewer == "B":
            row["max_calls"] = "3"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerow(row)


def test_normalization_extracts_http_scope_without_executing() -> None:
    normalizer = ToolNormalizer(CONFIG)
    scope = normalize_observed_call(
        "shell", {"command": "curl https://example.test/status"}, normalizer
    )
    assert scope.tool == "shell"
    assert scope.action == "execute"
    assert scope.resource == "command:curl"
    assert scope.sink == "https://example.test"
    assert scope.status == "known"


def test_pack_groups_calls_and_keeps_machine_proposal_non_authoritative(tmp_path) -> None:
    records = [
        _record("case_001", 1, "web_fetch", {"url": "https://example.test/status"}),
        _record("case_002", 2, "process", {"action": "poll", "sessionId": "p1"}),
    ]
    manifest = create_authorization_reconstruction_pack(
        records, tmp_path / "pack", ToolNormalizer(CONFIG)
    )
    draft = json.loads((tmp_path / "pack" / "authorization-drafts.jsonl").read_text())
    assert manifest["scenario_count"] == 1
    assert manifest["candidate_count"] == 2
    assert manifest["machine_proposal_is_authoritative"] is False
    assert draft["machine_proposal"]["valid_from"] is None
    assert draft["machine_proposal"]["tools"] == []
    assert draft["machine_proposal"]["resources"] == []
    assert draft["proposal_basis"]["tools"] == "not_evidenced"


def test_finalize_requires_independent_matching_reviews(tmp_path) -> None:
    records = [_record("case_001", 1, "web_fetch", {"url": "https://example.test/status"})]
    pack = tmp_path / "pack"
    create_authorization_reconstruction_pack(records, pack, ToolNormalizer(CONFIG))
    _fill_reviews(pack)
    result = finalize_authorization_reviews(pack, tmp_path / "authorizations.jsonl", SCHEMAS)
    output = json.loads((tmp_path / "authorizations.jsonl").read_text())
    assert result["finalized_count"] == 1
    assert output["review"]["resolution"] == "agreement"
    assert output["authorization"]["max_calls"] == 2


def test_finalize_blocks_disagreement_without_adjudication(tmp_path) -> None:
    records = [_record("case_001", 1, "web_fetch", {"url": "https://example.test/status"})]
    pack = tmp_path / "pack"
    create_authorization_reconstruction_pack(records, pack, ToolNormalizer(CONFIG))
    _fill_reviews(pack, mismatch=True)
    with pytest.raises(ValueError, match="requires completed adjudication"):
        finalize_authorization_reviews(pack, tmp_path / "authorizations.jsonl", SCHEMAS)
