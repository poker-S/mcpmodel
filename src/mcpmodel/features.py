"""Transparent baseline features for authorization-aware risk estimation."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml

from mcpmodel.authorization import compute_authorization_gap
from mcpmodel.normalizer import ToolNormalizer

TOOL_CAPABILITY = {
    "filesystem": 0.45,
    "git": 0.65,
    "http": 0.65,
    "secrets": 0.9,
    "ci_deployment": 0.95,
    "shell": 1.0,
}

ACTION_SIDE_EFFECT = {
    "read": 0.05,
    "write": 0.55,
    "upload": 0.65,
    "push": 0.75,
    "manage": 0.8,
    "deploy": 0.9,
    "delete": 0.95,
    "execute": 1.0,
}


def _resource_features(resource: str, config_path: Path) -> dict[str, float | str]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    result: dict[str, float | str] = {"resource_tag": "default", **config["defaults"]}
    for rule in config["patterns"]:
        if fnmatchcase(resource, str(rule["pattern"])):
            result = {
                "resource_tag": str(rule["tag"]),
                "confidentiality": float(rule["confidentiality"]),
                "integrity": float(rule["integrity"]),
                "availability": float(rule["availability"]),
            }
            break
    return result


def extract_features(
    case: dict[str, Any],
    *,
    config_dir: Path,
    calls_used: int = 0,
) -> dict[str, float | str]:
    """Extract deterministic, auditable MVP features from a validated case."""
    call = case["call"]
    normalizer = ToolNormalizer(config_dir / "tool_normalization.yaml")
    normalized = normalizer.normalize(str(call["tool"]), str(call["action"]))
    gaps = compute_authorization_gap(
        case["authorization"],
        call,
        normalized_tool=normalized.tool_family,
        normalized_action=normalized.action,
        calls_used=calls_used,
    )
    resource = _resource_features(str(call["resource"]), config_dir / "resource_labels.yaml")
    return {
        "tool_family": normalized.tool_family,
        "action": normalized.action,
        "normalization_status": normalized.status,
        "execution_capability": TOOL_CAPABILITY.get(normalized.tool_family, 0.7),
        "side_effect": ACTION_SIDE_EFFECT.get(normalized.action, 0.5),
        "source_untrust": float(case["provenance"]["source_untrust"]),
        "taint_confidence": float(case["provenance"]["taint_confidence"]),
        **resource,
        **gaps.as_features(),
    }

