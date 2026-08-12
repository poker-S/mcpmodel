"""Auditable cumulative ordinal model for L0--L4 risk probabilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mcpmodel.baseline import CATEGORICAL, LABELS, NUMERIC, _records, feature_rows
from mcpmodel.rules import RISK_ORDINAL


@dataclass
class OrdinalRiskModel:
    """K-1 cumulative binary models with monotone probability projection.

    Model ``k`` estimates ``P(Y > k)``. Independently fitted cumulative models
    can cross, so inference applies a deterministic non-increasing projection
    before converting cumulative probabilities to class probabilities.
    """

    transformer: ColumnTransformer
    threshold_models: tuple[LogisticRegression, ...]

    def predict_proba_from_records(self, records: list[list[Any]]) -> np.ndarray:
        matrix = self.transformer.transform(records)
        cumulative = np.column_stack(
            [model.predict_proba(matrix)[:, 1] for model in self.threshold_models]
        )
        cumulative = np.minimum.accumulate(cumulative, axis=1)
        probabilities = np.column_stack(
            [
                1.0 - cumulative[:, 0],
                cumulative[:, 0] - cumulative[:, 1],
                cumulative[:, 1] - cumulative[:, 2],
                cumulative[:, 2] - cumulative[:, 3],
                cumulative[:, 3],
            ]
        )
        probabilities = np.clip(probabilities, 0.0, 1.0)
        return probabilities / probabilities.sum(axis=1, keepdims=True)


def _transformer() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("categorical", OneHotEncoder(handle_unknown="ignore"), list(range(len(CATEGORICAL)))),
            (
                "numeric",
                StandardScaler(),
                list(range(len(CATEGORICAL), len(CATEGORICAL) + len(NUMERIC))),
            ),
        ]
    )


def train_ordinal(cases: list[dict[str, Any]], config_dir: Path, seed: int) -> OrdinalRiskModel:
    """Fit fixed-configuration cumulative logistic models on training cases only."""
    if not cases:
        raise ValueError("ordinal training requires at least one case")
    records = _records(feature_rows(cases, config_dir))
    transformer = _transformer()
    matrix = transformer.fit_transform(records)
    ordinal_labels = np.asarray(
        [RISK_ORDINAL[case["labels"]["inherent_risk"]] for case in cases], dtype=int
    )
    models: list[LogisticRegression] = []
    for threshold in range(len(LABELS) - 1):
        binary = (ordinal_labels > threshold).astype(int)
        if np.unique(binary).size != 2:
            raise ValueError(f"training data has only one class at ordinal threshold {threshold}")
        model = LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=seed + threshold,
            solver="lbfgs",
        )
        model.fit(matrix, binary)
        models.append(model)
    return OrdinalRiskModel(transformer, tuple(models))


def predict_ordinal_proba(
    model: OrdinalRiskModel, cases: list[dict[str, Any]], config_dir: Path
) -> np.ndarray:
    if not cases:
        return np.empty((0, len(LABELS)), dtype=float)
    return model.predict_proba_from_records(_records(feature_rows(cases, config_dir)))


def probability_labels(probabilities: np.ndarray) -> list[str]:
    _validate_probabilities(probabilities)
    return [LABELS[index] for index in np.argmax(probabilities, axis=1)]


def _validate_probabilities(probabilities: np.ndarray) -> None:
    if probabilities.ndim != 2 or probabilities.shape[1] != len(LABELS):
        raise ValueError(f"expected probability matrix with {len(LABELS)} columns")
    if not np.all(np.isfinite(probabilities)):
        raise ValueError("probabilities must be finite")
    if np.any(probabilities < -1e-12) or np.any(probabilities > 1.0 + 1e-12):
        raise ValueError("probabilities must be in [0, 1]")
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-9):
        raise ValueError("probability rows must sum to one")
