import json
from pathlib import Path

import yaml

from mcpmodel.ingest import build_sources
from mcpmodel.validator import iter_documents, validate_document


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_multisource_ingestion_preserves_provenance(tmp_path) -> None:
    extracted = tmp_path / "extracted"
    raw = tmp_path / "raw"
    raw.mkdir()
    sources = [
        ("trajectory", "agent_trajectory", "trajectory", "train_after_human_label"),
        ("prompts", "prompt_classification", "prompts", "auxiliary_only"),
        ("atlas", "vulnerability_corpus", "atlas", "external_evaluation_only"),
        ("cve", "vulnerability_verification", "cve", "scenario_seed_only"),
        ("deployment", "deployment_evaluation", "deployment", "train_after_human_label"),
    ]
    config = {
        "publisher": "Test Publisher",
        "license_policy": "research only",
        "sources": [
            {
                "source_id": source_id,
                "dataset_name": source_id,
                "source_kind": kind,
                "relative_root": relative,
                "archive_name": f"{source_id}.zip",
                "license_status": "research_internal_only",
                "allowed_use": use,
            }
            for source_id, kind, relative, use in sources
        ],
    }
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    for source_id, _, _, _ in sources:
        (raw / f"{source_id}.zip").write_bytes(source_id.encode())

    trajectory = extracted / "trajectory" / "case-1" / "session.jsonl"
    trajectory.parent.mkdir(parents=True)
    trajectory.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "message",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "test"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-08-12T00:00:00Z",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "toolCall",
                                    "id": "1",
                                    "name": "exec",
                                    "arguments": {"command": "pytest"},
                                }
                            ],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    prompt_path = extracted / "prompts" / "network-attack-prompt-sample.jsonl"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        json.dumps({"label": "safe", "label_2": "Security Research", "user": "review"}),
        encoding="utf-8",
    )
    _write_json(
        extracted
        / "atlas"
        / "project"
        / "findings"
        / "CVE-1"
        / "vuln-features"
        / "feature-result.json",
        {"vuln_id": "CVE-1", "project_key": "project", "exposed_capability": "code_execution"},
    )
    _write_json(
        extracted / "cve" / "project" / "sast_standardized.json",
        {"findings": [{"finding_id": "CVE-2", "severity": "HIGH", "cvss": 8.0}]},
    )
    _write_json(
        extracted / "deployment" / "project" / "deploy_test_plan.json",
        {"items": [{"kind": "test", "status": "PASS", "command": "pytest", "result": "ok"}]},
    )

    output = tmp_path / "output"
    manifest = build_sources(extracted, raw, config_path, output)
    assert manifest["record_count"] == 5
    assert manifest["by_usage_role"]["candidate_tool_call"] == 2
    for path in output.glob("*.jsonl"):
        if path.name == "sources.jsonl":
            continue
        for _, record in iter_documents(path):
            validate_document(record, "derived_record")
            assert len(record["source_file_sha256"]) == 64
            assert record["source_locator"]
