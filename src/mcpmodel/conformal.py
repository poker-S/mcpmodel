"""Split-conformal risk sets for calibrated ordinal probabilities."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

import numpy as np

from mcpmodel.baseline import LABELS
from mcpmodel.ordinal import _validate_probabilities


@dataclass(frozen=True)
class ConformalRiskSet:
    alpha: float
    score_quantile: float
    fitted_case_ids: tuple[str, ...]

    def predict(self, probabilities: np.ndarray) -> list[tuple[str, ...]]:
        _validate_probabilities(probabilities)
        cutoff = 1.0 - self.score_quantile
        sets: list[tuple[str, ...]] = []
        for row in probabilities:
            members = tuple(
                label
                for label, probability in zip(LABELS, row, strict=True)
                if probability >= cutoff
            )
            if not members:
                members = (LABELS[int(np.argmax(row))],)
            sets.append(members)
        return sets


def fit_conformal(
    probabilities: np.ndarray,
    cases: list[dict[str, Any]],
    *,
    alpha: float,
) -> ConformalRiskSet:
    _validate_probabilities(probabilities)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")
    if len(cases) != len(probabilities) or not cases:
        raise ValueError("conformal cases and probability rows must be non-empty and aligned")
    label_to_index = {label: index for index, label in enumerate(LABELS)}
    truth = np.asarray([label_to_index[case["labels"]["inherent_risk"]] for case in cases])
    scores = 1.0 - probabilities[np.arange(len(truth)), truth]
    quantile_level = min(1.0, ceil((len(scores) + 1) * (1.0 - alpha)) / len(scores))
    score_quantile = float(np.quantile(scores, quantile_level, method="higher"))
    return ConformalRiskSet(
        alpha=alpha,
        score_quantile=score_quantile,
        fitted_case_ids=tuple(str(case["case_id"]) for case in cases),
    )
