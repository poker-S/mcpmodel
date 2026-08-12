"""Probability calibration with explicit data-role separation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar

from mcpmodel.baseline import LABELS
from mcpmodel.ordinal import _validate_probabilities


@dataclass(frozen=True)
class TemperatureCalibrator:
    temperature: float
    fitted_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not np.isfinite(self.temperature) or self.temperature <= 0.0:
            raise ValueError("temperature must be finite and positive")

    def transform(self, probabilities: np.ndarray) -> np.ndarray:
        _validate_probabilities(probabilities)
        clipped = np.clip(probabilities, 1e-12, 1.0)
        logits = np.log(clipped) / self.temperature
        logits -= logits.max(axis=1, keepdims=True)
        calibrated = np.exp(logits)
        return calibrated / calibrated.sum(axis=1, keepdims=True)


def fit_temperature(
    probabilities: np.ndarray, cases: list[dict[str, Any]]
) -> TemperatureCalibrator:
    """Fit one temperature using only the cases explicitly passed by the caller."""
    _validate_probabilities(probabilities)
    if len(cases) != len(probabilities) or not cases:
        raise ValueError("calibration cases and probability rows must be non-empty and aligned")
    label_to_index = {label: index for index, label in enumerate(LABELS)}
    truth = np.asarray([label_to_index[case["labels"]["inherent_risk"]] for case in cases])

    def objective(log_temperature: float) -> float:
        temperature = float(np.exp(log_temperature))
        transformed = TemperatureCalibrator(temperature, ()).transform(probabilities)
        return float(-np.log(np.clip(transformed[np.arange(len(truth)), truth], 1e-12, 1.0)).mean())

    result = minimize_scalar(objective, bounds=(-3.0, 3.0), method="bounded")
    if not result.success:
        raise RuntimeError(f"temperature optimization failed: {result.message}")
    return TemperatureCalibrator(
        temperature=float(np.exp(result.x)),
        fitted_case_ids=tuple(str(case["case_id"]) for case in cases),
    )
