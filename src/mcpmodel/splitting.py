"""Deterministic group-aware dataset splitting and leakage checks."""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Any

SPLIT_RATIOS = {"train": 0.6, "validation": 0.2, "test": 0.2}


def _target_sizes(total: int) -> dict[str, int]:
    train = round(total * SPLIT_RATIOS["train"])
    validation = round(total * SPLIT_RATIOS["validation"])
    return {"train": train, "validation": validation, "test": total - train - validation}


def group_split(
    cases: list[dict[str, Any]], seed: int = 20260812
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        groups.setdefault(str(case["scenario_group"]), []).append(case)

    rng = random.Random(seed)
    items = list(groups.items())
    rng.shuffle(items)
    items.sort(key=lambda item: len(item[1]), reverse=True)
    targets = _target_sizes(len(cases))
    result: dict[str, list[dict[str, Any]]] = {name: [] for name in SPLIT_RATIOS}
    for _, group_cases in items:
        destination = min(
            result,
            key=lambda name: (
                len(result[name]) / max(targets[name], 1),
                len(result[name]),
                name,
            ),
        )
        result[destination].extend(group_cases)

    assert_no_group_leakage(result)
    for values in result.values():
        values.sort(key=lambda case: case["case_id"])
    return result


def assert_no_group_leakage(splits: dict[str, list[dict[str, Any]]]) -> None:
    owner: dict[str, str] = {}
    for split_name, cases in splits.items():
        for case in cases:
            group = str(case["scenario_group"])
            if group in owner and owner[group] != split_name:
                raise ValueError(
                    f"scenario group leaked: {group} in {owner[group]} and {split_name}"
                )
            owner[group] = split_name


def split_manifest(splits: dict[str, list[dict[str, Any]]], seed: int) -> dict[str, Any]:
    records = []
    for split_name in sorted(splits):
        records.extend((case["case_id"], split_name) for case in splits[split_name])
    digest = hashlib.sha256(
        "\n".join(f"{case_id},{split}" for case_id, split in records).encode()
    ).hexdigest()
    return {
        "seed": seed,
        "strategy": "greedy_group_60_20_20",
        "assignment_sha256": digest,
        "splits": {
            name: {
                "case_count": len(cases),
                "group_count": len({case["scenario_group"] for case in cases}),
                "risk_distribution": dict(
                    sorted(Counter(case["labels"]["inherent_risk"] for case in cases).items())
                ),
                "case_ids": [case["case_id"] for case in cases],
            }
            for name, cases in splits.items()
        },
    }
