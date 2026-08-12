import json
from pathlib import Path

from mcpmodel.external_annotation import create_external_annotation_pack
from mcpmodel.normalizer import ToolNormalizer

CONFIG = Path(__file__).parents[1] / "configs" / "tool_normalization.yaml"


def test_external_pack_keeps_source_and_marks_missing_authorization(tmp_path) -> None:
    records = [
        {
            "record_id": "external_001",
            "scenario_group": "group_001",
            "usage_role": "candidate_tool_call",
            "source_id": "source_001",
            "source_kind": "agent_trajectory",
            "source_file": "case/session.jsonl",
            "source_file_sha256": "a" * 64,
            "source_locator": "line:2/content:1",
            "source_labels": {},
            "payload": {
                "user_task": "run test",
                "tool": "exec",
                "arguments": {"command": "pytest"},
                "call_index": 1,
                "source_untrust": 1.0,
            },
        }
    ]
    summary = create_external_annotation_pack(records, tmp_path / "pack")
    contexts = (tmp_path / "pack" / "contexts.jsonl").read_text(encoding="utf-8")
    assert summary["case_count"] == 1
    assert summary["authorization_status"] == "requires_reconstruction"
    assert '"source_file_sha256": "aaaaaaaa' in contexts
    assert "must_be_reconstructed_by_annotator" in contexts


def test_external_pack_uses_only_finalized_authorized_groups(tmp_path) -> None:
    records = [
        {
            "record_id": "external_001",
            "scenario_group": "group_001",
            "usage_role": "candidate_tool_call",
            "source_id": "source_001",
            "source_kind": "agent_trajectory",
            "source_file": "case/session.jsonl",
            "source_file_sha256": "a" * 64,
            "source_locator": "line:2/content:1",
            "source_labels": {"unsafe": True},
            "payload": {
                "user_task": "fetch https://example.test/status",
                "tool": "web_fetch",
                "arguments": {"url": "https://example.test/status"},
                "call_index": 1,
                "source_untrust": 1.0,
                "timestamp": "2026-08-12T00:00:01Z",
            },
        }
    ]
    task = records[0]["payload"]["user_task"]
    import hashlib

    authorizations = {
        "group_001": {
            "authorization_id": "auth_1234567890abcdef",
            "scenario_group": "group_001",
            "case_ids": ["external_001"],
            "task_sha256": hashlib.sha256(task.encode()).hexdigest(),
            "authorization": {
                "subject": "external_agent",
                "tools": ["http"],
                "actions": ["read"],
                "resources": ["https://example.test/status"],
                "sinks": ["https://example.test"],
                "valid_from": "2026-08-12T00:00:00Z",
                "valid_until": "2026-08-12T00:10:00Z",
                "max_calls": 1,
            },
        }
    }
    summary = create_external_annotation_pack(
        records,
        tmp_path / "pack",
        reconstructed_authorizations=authorizations,
        normalizer=ToolNormalizer(CONFIG),
    )
    context = json.loads((tmp_path / "pack" / "contexts.jsonl").read_text())
    assert summary["authorization_status"] == "independently_reconstructed"
    assert context["call"]["tool"] == "http"
    assert context["call"]["resource"] == "https://example.test/status"
    assert "source_labels" not in context
