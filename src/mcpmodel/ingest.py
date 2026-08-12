"""Read-only ingestion of Chaitin sample datasets with explicit provenance."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from mcpmodel.validator import validate_document

CONVERTER_VERSION = "chaitin-ingest-0.1.0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "_", value.lower()).strip("_")[:100]


def _relative(path: Path, source_root: Path) -> str:
    return path.relative_to(source_root).as_posix()


def _record(
    *,
    source: dict[str, Any],
    source_root: Path,
    path: Path,
    locator: str,
    group: str,
    usage_role: str,
    label_status: str,
    payload: dict[str, Any],
    source_labels: dict[str, Any] | None = None,
    suffix: str,
) -> dict[str, Any]:
    record = {
        "record_id": _safe_id(f"{source['source_id']}_{suffix}"),
        "source_id": source["source_id"],
        "source_kind": source["source_kind"],
        "source_file": _relative(path, source_root),
        "source_file_sha256": sha256_file(path),
        "source_locator": locator,
        "scenario_group": _safe_id(group),
        "usage_role": usage_role,
        "label_status": label_status,
        "source_labels": source_labels or {},
        "payload": payload,
        "converter_version": CONVERTER_VERSION,
    }
    validate_document(record, "derived_record")
    return record


def _content_blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content", [])
    if isinstance(content, dict):
        return [content]
    return [item for item in content if isinstance(item, dict)]


def ingest_trajectories(source: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/session.jsonl")):
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        user_task = ""
        call_index = 0
        for event_index, event in enumerate(events, 1):
            if event.get("type") != "message":
                continue
            message = event.get("message", {})
            blocks = _content_blocks(message)
            if message.get("role") == "user" and not user_task:
                user_task = next(
                    (str(block.get("text", "")) for block in blocks if block.get("type") == "text"),
                    "",
                )
            if message.get("role") != "assistant":
                continue
            for block_index, block in enumerate(blocks, 1):
                if block.get("type") not in {"toolCall", "tool_use"}:
                    continue
                call_index += 1
                arguments = block.get("arguments", block.get("input", {}))
                if not isinstance(arguments, dict):
                    arguments = {"raw": arguments}
                records.append(
                    _record(
                        source=source,
                        source_root=root,
                        path=path,
                        locator=f"line:{event_index}/content:{block_index}",
                        group=path.parent.name,
                        usage_role="candidate_tool_call",
                        label_status="requires_human_label",
                        payload={
                            "user_task": user_task[:4000],
                            "tool": str(block.get("name", "unknown")),
                            "arguments": arguments,
                            "call_index": call_index,
                            "timestamp": event.get("timestamp"),
                            "source_untrust": 1.0,
                            "raw_tool_call_id": block.get("id"),
                        },
                        suffix=f"{path.parent.name}_{call_index:03d}",
                    )
                )
        reason_path = path.parent / "reason.md"
        if reason_path.exists():
            records.append(
                _record(
                    source=source,
                    source_root=root,
                    path=reason_path,
                    locator="markdown:<document>",
                    group=path.parent.name,
                    usage_role="scenario_seed",
                    label_status="source_evidence_only",
                    payload={"attack_analysis": reason_path.read_text(encoding="utf-8")},
                    suffix=f"{path.parent.name}_attack_analysis",
                )
            )
    known_groups = {record["scenario_group"] for record in records}
    for reason_path in sorted(root.glob("*/reason.md")):
        if _safe_id(reason_path.parent.name) in known_groups:
            continue
        records.append(
            _record(
                source=source,
                source_root=root,
                path=reason_path,
                locator="markdown:<document>",
                group=reason_path.parent.name,
                usage_role="scenario_seed",
                label_status="source_evidence_only",
                payload={"attack_analysis": reason_path.read_text(encoding="utf-8")},
                suffix=f"{reason_path.parent.name}_attack_analysis",
            )
        )
    return records


def ingest_prompts(source: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    path = root / "network-attack-prompt-sample.jsonl"
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        item = json.loads(line)
        records.append(
            _record(
                source=source,
                source_root=root,
                path=path,
                locator=f"line:{line_number}",
                group=f"prompt_{item['label_2']}_{line_number:03d}",
                usage_role="auxiliary_prompt",
                label_status="source_label_auxiliary",
                source_labels={"label": item["label"], "label_2": item["label_2"]},
                payload={"text": item["user"]},
                suffix=f"prompt_{line_number:03d}",
            )
        )
    return records


def ingest_vuln_atlas(source: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(root.glob("*/findings/*/vuln-features/feature-result.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        vuln_id = str(item.get("vuln_id", path.parents[1].name))
        finding_root = path.parents[1]
        supporting_sources = []
        supporting_payload: dict[str, Any] = {}
        for name in ("module-localization.json", "ai-participation.json"):
            support_path = finding_root / name
            if support_path.exists():
                supporting_sources.append(
                    {
                        "source_file": _relative(support_path, root),
                        "source_file_sha256": sha256_file(support_path),
                    }
                )
                supporting_payload[name.removesuffix(".json").replace("-", "_")] = json.loads(
                    support_path.read_text(encoding="utf-8")
                )
        records.append(
            _record(
                source=source,
                source_root=root,
                path=path,
                locator="json:<root>",
                group=f"vuln_atlas_{item.get('project_key', path.parents[3].name)}_{vuln_id}",
                usage_role="external_evaluation",
                label_status="source_evidence_only",
                source_labels={
                    "ai_involvement": item.get("ai_involvement_final"),
                    "architecture_layer": item.get("architecture_layer"),
                    "exposed_capability": item.get("exposed_capability"),
                },
                payload={
                    "features": item,
                    **supporting_payload,
                    "supporting_sources": supporting_sources,
                },
                suffix=f"{item.get('project_key', 'project')}_{vuln_id}",
            )
        )
    return records


def ingest_cve_verification(source: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(root.glob("*/sast_standardized.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        project = path.parent.name
        for index, finding in enumerate(item.get("findings", []), 1):
            finding_id = str(finding.get("finding_id", f"finding-{index}"))
            finding_root = path.parent / "findings" / finding_id
            support_payload: dict[str, Any] = {}
            supporting_sources = []
            for name in ("deployment.json", "verification_plan.json", "verification_result.json"):
                candidates = [finding_root / name, finding_root / "verify_requirements" / name]
                support_path = next(
                    (candidate for candidate in candidates if candidate.exists()), None
                )
                if support_path is not None:
                    supporting_sources.append(
                        {
                            "source_file": _relative(support_path, root),
                            "source_file_sha256": sha256_file(support_path),
                        }
                    )
                    support_payload[name.removesuffix(".json")] = json.loads(
                        support_path.read_text(encoding="utf-8")
                    )
            records.append(
                _record(
                    source=source,
                    source_root=root,
                    path=path,
                    locator=f"json:findings[{index - 1}]",
                    group=f"cve_{project}_{finding_id}",
                    usage_role="scenario_seed",
                    label_status="source_evidence_only",
                    source_labels={
                        "severity": finding.get("severity"),
                        "cvss": finding.get("cvss"),
                        "vuln_type": finding.get("vuln_type"),
                        "cwe": finding.get("cwe"),
                    },
                    payload={
                        "finding_id": finding_id,
                        "description": finding.get("description"),
                        "recommendation": finding.get("recommendation"),
                        "vul_pos": finding.get("vul_pos", []),
                        "dataflow": finding.get("dataflow", []),
                        **support_payload,
                        "supporting_sources": supporting_sources,
                    },
                    suffix=f"{project}_{finding_id}",
                )
            )
    return records


def ingest_deployment(source: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(root.glob("*/deploy_test_plan.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        project = path.parent.name
        for index, check in enumerate(item.get("items", []), 1):
            records.append(
                _record(
                    source=source,
                    source_root=root,
                    path=path,
                    locator=f"json:items[{index - 1}]",
                    group=f"deployment_{project}_{check.get('kind', 'check')}",
                    usage_role="candidate_tool_call",
                    label_status="requires_human_label",
                    source_labels={"status": check.get("status")},
                    payload={
                        "user_task": "Validate a reference project deployment",
                        "tool": "shell",
                        "arguments": {"command": check.get("command")},
                        "expected_result": check.get("result"),
                        "call_index": index,
                        "source_untrust": 0.1,
                    },
                    suffix=f"{project}_{index:03d}",
                )
            )
    return records


INGESTERS = {
    "agent_trajectory": ingest_trajectories,
    "prompt_classification": ingest_prompts,
    "vulnerability_corpus": ingest_vuln_atlas,
    "vulnerability_verification": ingest_cve_verification,
    "deployment_evaluation": ingest_deployment,
}


def build_sources(
    extracted_root: Path, raw_root: Path, config_path: Path, output_dir: Path
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=False)
    all_records: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    for source in config["sources"]:
        source_root = extracted_root / source["relative_root"]
        archive_path = raw_root / source["archive_name"]
        source_record = {
            "source_id": source["source_id"],
            "publisher": config["publisher"],
            "dataset_name": source["dataset_name"],
            "source_kind": source["source_kind"],
            "local_root": source["relative_root"],
            "archive_sha256": sha256_file(archive_path) if archive_path.exists() else None,
            "license_status": source["license_status"],
            "license_note": config["license_policy"],
            "allowed_use": source["allowed_use"],
            "ingested_at": "2026-08-12T00:00:00Z",
            "converter_version": CONVERTER_VERSION,
        }
        validate_document(source_record, "source_record")
        source_records.append(source_record)
        records = INGESTERS[source["source_kind"]](source, source_root)
        all_records.extend(records)
        (output_dir / f"{source['source_id']}.jsonl").write_text(
            "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records)
            + "\n",
            encoding="utf-8",
        )

    (output_dir / "sources.jsonl").write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True)
            for record in source_records
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "converter_version": CONVERTER_VERSION,
        "record_count": len(all_records),
        "by_source": dict(sorted(Counter(record["source_id"] for record in all_records).items())),
        "by_usage_role": dict(
            sorted(Counter(record["usage_role"] for record in all_records).items())
        ),
        "by_label_status": dict(
            sorted(Counter(record["label_status"] for record in all_records).items())
        ),
        "source_archives": {
            record["source_id"]: record["archive_sha256"] for record in source_records
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
