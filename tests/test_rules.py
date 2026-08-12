from pathlib import Path

from mcpmodel.features import extract_features
from mcpmodel.pilot import generate_pilot
from mcpmodel.rules import HardRuleEngine

ROOT = Path(__file__).resolve().parents[1]


def _case(reason: str) -> dict:
    return next(case for case in generate_pilot() if reason in case["labels"]["reason_codes"])


def test_destructive_root_rule_denies() -> None:
    case = _case("DESTRUCTIVE_WORKSPACE_ROOT")
    features = extract_features(case, config_dir=ROOT / "configs")
    decision = HardRuleEngine(ROOT / "configs" / "hard_rules.yaml").evaluate(features)
    assert decision.risk_floor == "L4"
    assert decision.decision == "deny"


def test_protected_branch_rule_requires_approval() -> None:
    case = _case("PROTECTED_BRANCH_WRITE")
    features = extract_features(case, config_dir=ROOT / "configs")
    decision = HardRuleEngine(ROOT / "configs" / "hard_rules.yaml").evaluate(features)
    assert decision.risk_floor == "L3"
    assert decision.decision == "approve"
