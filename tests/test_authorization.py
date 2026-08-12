import json
from pathlib import Path

from mcpmodel.authorization import compute_authorization_gap
from mcpmodel.normalizer import ToolNormalizer

ROOT = Path(__file__).resolve().parents[1]


def test_matching_call_has_no_authorization_gap() -> None:
    case = json.loads(
        (ROOT / "data" / "examples" / "case_allow_readme.json").read_text(encoding="utf-8")
    )
    normalizer = ToolNormalizer(ROOT / "configs" / "tool_normalization.yaml")
    normalized = normalizer.normalize(case["call"]["tool"], case["call"]["action"])
    gap = compute_authorization_gap(
        case["authorization"],
        case["call"],
        normalized_tool=normalized.tool_family,
        normalized_action=normalized.action,
    )
    assert sum(gap.as_features().values()) == 0.0


def test_late_and_excess_call_has_two_gaps() -> None:
    case = json.loads(
        (ROOT / "data" / "examples" / "case_allow_readme.json").read_text(encoding="utf-8")
    )
    case["call"]["timestamp"] = "2026-08-14T00:00:00Z"
    gap = compute_authorization_gap(
        case["authorization"],
        case["call"],
        normalized_tool="filesystem",
        normalized_action="read",
        calls_used=5,
    )
    assert gap.temporal_gap == 1.0
    assert gap.cardinality_gap == 1.0
