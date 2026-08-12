import json
from pathlib import Path

import pytest

from mcpmodel.validator import ValidationFailure, validate_document

ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    return json.loads((ROOT / "data" / "examples" / name).read_text(encoding="utf-8"))


def test_examples_conform_to_case_schema() -> None:
    for path in (ROOT / "data" / "examples").glob("*.json"):
        validate_document(json.loads(path.read_text(encoding="utf-8")))


def test_nested_authorization_is_validated() -> None:
    case = load_example("case_allow_readme.json")
    del case["authorization"]["subject"]
    with pytest.raises(ValidationFailure, match="authorization.*subject"):
        validate_document(case)
