from mcpmodel.external_annotation import create_external_annotation_pack


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
