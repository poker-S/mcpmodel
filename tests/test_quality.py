import csv
import json

import pytest

from mcpmodel.quality import audit_external_annotation_pack


def _pack(tmp_path, *, leak: bool = False):
    pack = tmp_path / "pack"
    pack.mkdir()
    context = {
        "case_id": "case_001",
        "scenario_group": "group_001",
        "authorization_id": "auth_1234567890abcdef",
        "authorization": {"subject": "agent"},
        "call": {
            "tool": "http",
            "action": "read",
            "resource": "https://example.test",
            "sink": "<none>",
            "arguments": {},
        },
    }
    if leak:
        context["source_labels"] = {"unsafe": True}
    (pack / "contexts.jsonl").write_text(json.dumps(context) + "\n", encoding="utf-8")
    (pack / "manifest.json").write_text(
        json.dumps({"authorization_status": "independently_reconstructed", "case_count": 1}),
        encoding="utf-8",
    )
    with (pack / "labels-A.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id"])
        writer.writeheader()
        writer.writerow({"case_id": "case_001"})
    return pack


def test_external_pack_audit_passes_clean_context(tmp_path) -> None:
    result = audit_external_annotation_pack(_pack(tmp_path))
    assert result["status"] == "passed"
    assert result["forbidden_context_key_count"] == 0


def test_external_pack_audit_blocks_source_label_leak(tmp_path) -> None:
    with pytest.raises(ValueError, match="forbidden keys"):
        audit_external_annotation_pack(_pack(tmp_path, leak=True))
