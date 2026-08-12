"""Small declarative rule engine for immutable safety floors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

RISK_ORDINAL = {f"L{level}": level for level in range(5)}


@dataclass(frozen=True)
class RuleDecision:
    risk_floor: str
    decision: str | None
    matched_rules: tuple[str, ...]
    reason_codes: tuple[str, ...]


def _condition_matches(features: dict[str, Any], key: str, expected: Any) -> bool:
    if key.endswith("_min"):
        actual = float(features.get(key.removesuffix("_min"), 0.0))
        return actual >= float(expected)
    return features.get(key) == expected


class HardRuleEngine:
    def __init__(self, config_path: Path) -> None:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.rules = sorted(config["rules"], key=lambda rule: int(rule["priority"]))

    def evaluate(self, features: dict[str, Any]) -> RuleDecision:
        matched: list[str] = []
        reasons: list[str] = []
        risk_floor = "L0"
        decision: str | None = None
        for rule in self.rules:
            if all(
                _condition_matches(features, key, expected)
                for key, expected in rule["when"].items()
            ):
                matched.append(str(rule["id"]))
                reasons.append(str(rule["reason_code"]))
                effect = rule["effect"]
                candidate_floor = str(effect["risk_floor"])
                if RISK_ORDINAL[candidate_floor] > RISK_ORDINAL[risk_floor]:
                    risk_floor = candidate_floor
                    decision = str(effect["decision"])
        return RuleDecision(risk_floor, decision, tuple(matched), tuple(reasons))
