"""Build blinded annotation contexts from externally derived candidate tool calls."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from mcpmodel.annotation import OUTPUT_FIELDS


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
    records: list[dict[str, Any]], output_dir: Path, annotators: tuple[str, ...] = ("A", "B", "C")
) -> dict[str, Any]:
    candidates = [record for record in records if record["usage_role"] == "candidate_tool_call"]
    output_dir.mkdir(parents=True, exist_ok=False)
    contexts = []
    for record in candidates:
        contexts.append(
            {
                "case_id": record["record_id"],
                "scenario_group": record["scenario_group"],
                "user_task": record["payload"].get("user_task", ""),
                "authorization": _authorization_placeholder(),
                "provenance": {
                    "source_id": record["source_id"],
                    "source_kind": record["source_kind"],
                    "source_file": record["source_file"],
                    "source_file_sha256": record["source_file_sha256"],
                    "source_locator": record["source_locator"],
                    "source_untrust": record["payload"].get("source_untrust"),
                },
                "call": {
                    "tool": record["payload"].get("tool", "unknown"),
                    "arguments": record["payload"].get("arguments", {}),
                    "call_index": record["payload"].get("call_index"),
                    "timestamp": record["payload"].get("timestamp"),
                },
                "source_labels": record.get("source_labels", {}),
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
        "annotators": list(annotators),
        "contexts_sha256": hashlib.sha256(context_path.read_bytes()).hexdigest(),
        "labels_hidden": True,
        "authorization_status": "requires_reconstruction",
        "source_distribution": {
            source_id: sum(context["provenance"]["source_id"] == source_id for context in contexts)
            for source_id in sorted({context["provenance"]["source_id"] for context in contexts})
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
