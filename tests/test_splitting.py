import copy

import pytest

from mcpmodel.pilot import generate_pilot
from mcpmodel.splitting import assert_no_group_leakage, group_split, split_manifest


def test_group_split_is_deterministic_and_leak_free() -> None:
    cases = generate_pilot()
    first = group_split(cases)
    second = group_split(cases)
    assert split_manifest(first, 20260812) == split_manifest(second, 20260812)
    assert sorted(len(values) for values in first.values()) == [6, 6, 18]
    assert_no_group_leakage(first)


def test_leakage_is_detected() -> None:
    cases = generate_pilot()
    leaked = {"train": [cases[0]], "validation": [copy.deepcopy(cases[0])], "test": []}
    with pytest.raises(ValueError, match="leaked"):
        assert_no_group_leakage(leaked)
