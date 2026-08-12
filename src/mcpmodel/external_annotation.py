"""Build blinded annotation contexts from externally derived candidate tool calls."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from mcpmodel.annotation import OUTPUT_FIELDS
from mcpmodel.authorization_reconstruction import normalize_observed_call
from mcpmodel.normalizer import ToolNormalizer


def _authorization_placeholder() -> dict[str, Any]:
    return {
        "subject": "unknown_external_agent",
        "tools": [],
        "actions": [],
        "resources": [],
        "sinks": [],
        "valid_from": None,
        "valid_until": None,
        "max_calls": None,
        "status": "must_be_reconstructed_by_annotator",
    }


def create_external_annotation_pack(
    records: list[dict[str, Any]],
    output_dir: Path,
    annotators: tuple[str, ...] = ("A", "B", "C"),
    *,
    reconstructed_authorizations: dict[str, dict[str, Any]] | None = None,
    normalizer: ToolNormalizer | None = None,
) -> dict[str, Any]:
    candidates = [record for record in records if record["usage_role"] == "candidate_tool_call"]
    excluded_candidates = 0
    output_dir.mkdir(parents=True, exist_ok=False)
    contexts = []
    for record in candidates:
        reconstructed = None
        if reconstructed_authorizations is not None:
            reconstructed = reconstructed_authorizations.get(record["scenario_group"])
            if reconstructed is None:
                excluded_candidates += 1
                continue
            if record["record_id"] not in reconstructed["case_ids"]:
                raise ValueError(f"authorization case list does not contain {record['record_id']}")
            task = str(record["payload"].get("user_task", ""))
            if hashlib.sha256(task.encode("utf-8")).hexdigest() != reconstructed["task_sha256"]:
                raise ValueError(f"authorization task hash mismatch for {record['record_id']}")
            if normalizer is None:
                raise ValueError("normalizer is required with reconstructed authorizations")
        payload = record["payload"]
        arguments = payload.get("arguments", {})
        scope = (
            normalize_observed_call(str(payload.get("tool", "unknown")), arguments, normalizer)
            if reconstructed is not None
            else None
        )
        contexts.append(
            {
                "case_id": record["record_id"],
                "scenario_group": record["scenario_group"],
                "user_task": payload.get("user_task", ""),
                "authorization": (
                    reconstructed["authorization"]
                    if reconstructed is not None
                    else _authorization_placeholder()
                ),
                "authorization_id": (
                    reconstructed["authorization_id"] if reconstructed is not None else None
                ),
                "provenance": {
                    "source_id": record["source_id"],
                    "source_kind": record["source_kind"],
                    "source_file": record["source_file"],
                    "source_file_sha256": record["source_file_sha256"],
                    "source_locator": record["source_locator"],
                    "source_untrust": payload.get("source_untrust"),
                },
                "call": {
                    "tool": scope.tool if scope else payload.get("tool", "unknown"),
                    "action": scope.action if scope else None,
                    "resource": scope.resource if scope else None,
                    "sink": scope.sink if scope else None,
                    "arguments": arguments,
                    "call_index": payload.get("call_index"),
                    "calls_used": max(int(payload.get("call_index") or 1) - 1, 0),
                    "timestamp": payload.get("timestamp"),
                },
                "label_status": "requires_human_label",
            }
        )
    context_path = output_dir / "contexts.jsonl"
    context_path.write_text(
        "\n".join(json.dumps(context, ensure_ascii=False, sort_keys=True) for context in contexts)
        + "\n",
        encoding="utf-8",
    )
    for annotator in annotators:
        with (output_dir / f"labels-{annotator}.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            for context in contexts:
                writer.writerow({"case_id": context["case_id"], "annotator_id": annotator})
    manifest = {
        "case_count": len(contexts),
        "source_candidate_count": len(candidates),
        "excluded_without_final_authorization": excluded_candidates,
        "annotators": list(annotators),
        "contexts_sha256": hashlib.sha256(context_path.read_bytes()).hexdigest(),
        "labels_hidden": True,
        "authorization_status": (
            "independently_reconstructed"
            if reconstructed_authorizations is not None
            else "requires_reconstruction"
        ),
        "source_distribution": {
            source_id: sum(context["provenance"]["source_id"] == source_id for context in contexts)
            for source_id in sorted({context["provenance"]["source_id"] for context in contexts})
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
