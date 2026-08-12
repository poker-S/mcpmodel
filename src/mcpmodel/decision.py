"""Hard-rule-first selective governance decisions with auditable reasons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mcpmodel.baseline import LABELS
from mcpmodel.features import extract_features
from mcpmodel.rules import RISK_ORDINAL, HardRuleEngine


@dataclass(frozen=True)
class GovernanceDecision:
    action: str
    predicted_risk: str
    risk_set: tuple[str, ...]
    expected_risk: float
    hard_risk_floor: str
    matched_rules: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide(
    case: dict[str, Any],
    probabilities: np.ndarray,
    risk_set: tuple[str, ...],
    *,
    config_dir: Path,
) -> GovernanceDecision:
    """Choose the least permissive action justified by frozen safety policy.

    Statistical uncertainty can allow or escalate to approval, but it cannot
    create an automatic deny. Automatic deny remains restricted to a matched
    immutable hard rule with no declared safe downgrade.
    """
    if probabilities.shape != (len(LABELS),):
        raise ValueError("one five-class probability row is required")
    if not risk_set or any(label not in RISK_ORDINAL for label in risk_set):
        raise ValueError("risk_set must contain known risk labels")
    features = extract_features(case, config_dir=config_dir)
    hard = HardRuleEngine(config_dir / "hard_rules.yaml").evaluate(features)
    predicted = LABELS[int(np.argmax(probabilities))]
    expected = float(sum(index * value for index, value in enumerate(probabilities)))
    max_risk = max(RISK_ORDINAL[label] for label in risk_set)

    reasons = list(hard.reason_codes)
    if hard.decision == "deny":
        action = "deny"
        reasons.append("HARD_RULE_DENY")
    elif hard.decision in {"rewrite", "isolate"} and max_risk <= RISK_ORDINAL[hard.risk_floor]:
        action = hard.decision
        reasons.append("HARD_RULE_SAFE_DOWNGRADE")
    elif hard.decision == "approve" or max_risk >= 2:
        action = "approve"
        reasons.append("UNCERTAINTY_OR_RISK_REQUIRES_APPROVAL")
    else:
        action = "allow"
        reasons.append("LOW_RISK_SET_AUTO_ALLOW")

    return GovernanceDecision(
        action=action,
        predicted_risk=predicted,
        risk_set=risk_set,
        expected_risk=expected,
        hard_risk_floor=hard.risk_floor,
        matched_rules=hard.matched_rules,
        reason_codes=tuple(dict.fromkeys(reasons)),
    )
