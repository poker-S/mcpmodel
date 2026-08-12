import json
from pathlib import Path

from mcpmodel.features import extract_features

ROOT = Path(__file__).resolve().parents[1]


def test_feature_extraction_is_auditable() -> None:
    case = json.loads(
        (ROOT / "data" / "examples" / "case_approve_main_push.json").read_text(encoding="utf-8")
    )
    features = extract_features(case, config_dir=ROOT / "configs")
    assert features["tool_family"] == "git"
    assert features["resource_tag"] == "protected_branch"
    assert features["integrity"] == 1.0
    assert features["tool_gap"] == 0.0
