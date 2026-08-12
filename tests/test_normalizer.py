from pathlib import Path

from mcpmodel.normalizer import ToolNormalizer

ROOT = Path(__file__).resolve().parents[1]


def test_aliases_are_normalized() -> None:
    normalizer = ToolNormalizer(ROOT / "configs" / "tool_normalization.yaml")
    normalized = normalizer.normalize("read_file", "cat")
    assert normalized.tool_family == "filesystem"
    assert normalized.action == "read"
    assert normalized.status == "known"


def test_unknowns_are_not_silently_coerced() -> None:
    normalizer = ToolNormalizer(ROOT / "configs" / "tool_normalization.yaml")
    normalized = normalizer.normalize("mystery_tool", "teleport")
    assert normalized.status == "unknown"
