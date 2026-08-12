"""Deterministic normalization of heterogeneous tool and action names."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class NormalizedCall:
    tool_family: str
    action: str
    status: str


class ToolNormalizer:
    """Map aliases to a small vocabulary and surface unknowns instead of guessing."""

    CANONICAL_ACTIONS = {
        "read",
        "write",
        "delete",
        "execute",
        "upload",
        "push",
        "deploy",
        "manage",
        "authenticate",
    }

    def __init__(self, config_path: Path) -> None:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.tool_aliases = {
            str(k).lower(): str(v).lower() for k, v in config["tool_aliases"].items()
        }
        self.action_aliases = {
            str(k).lower(): str(v).lower() for k, v in config["action_aliases"].items()
        }
        self.known_tools = {str(item).lower() for item in config["known_tool_families"]}

    def normalize(self, tool: str, action: str) -> NormalizedCall:
        raw_tool = tool.strip().lower()
        raw_action = action.strip().lower()
        family = self.tool_aliases.get(raw_tool, raw_tool)
        normalized_action = self.action_aliases.get(raw_action, raw_action)
        known = family in self.known_tools and normalized_action in self.CANONICAL_ACTIONS
        return NormalizedCall(family, normalized_action, "known" if known else "unknown")
