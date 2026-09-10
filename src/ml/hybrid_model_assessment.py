"""Evaluation utilities for the engineering-aware CatBoost generation.

The next-generation EOR classifier should only be promoted after independent
validation demonstrates adequate class coverage, predictive performance, and
probability calibration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
)


@dataclass(frozen=True)
class ClassificationMetrics:
    accuracy: float
    balanced_accuracy: float
    macro_f1: float
    weighted_f1: float
    macro_precision: float
    weighted_precision: float
    macro_recall: float
    weighted_recall: float
    log_loss: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_probabilities(
    y_true: np.ndarray,
    y_probability: np.ndarray,
) -> ClassificationMetrics:
    """Evaluate multiclass probabilities with imbalance-aware metrics."""
    y_true = np.asarray(y_true)
    y_probability = np.asarray(y_probability, dtype=float)

    if y_probability.ndim != 2:
        raise ValueError("y_probability must be a 2D probability matrix.")
    if len(y_true) != len(y_probability):
        raise ValueError("y_true and y_probability must contain the same number of rows.")
    if not np.isfinite(y_probability).all():
        raise ValueError("Probability matrix contains non-finite values.")

    row_sums = y_probability.sum(axis=1)
    if np.any(row_sums <= 0):
        raise ValueError("Each probability row must have positive mass.")
    y_probability = y_probability / row_sums[:, None]
    y_pred = np.argmax(y_probability, axis=1)

    return ClassificationMetrics(
        accuracy=float(accuracy_score(y_true, y_pred)),
        balanced_accuracy=float(balanced_accuracy_score(y_true, y_pred)),
        macro_f1=float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        weighted_f1=float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        macro_precision=float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        weighted_precision=float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        macro_recall=float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        weighted_recall=float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
        log_loss_value=None,
    )


def evaluate_multiclass_model(
    y_true: np.ndarray,
    y_probability: np.ndarray,
) -> ClassificationMetrics:
    """Evaluate predictions and include multiclass cross-entropy."""
    metrics = evaluate_probabilities(y_true, y_probability)
    y_probability = np.asarray(y_probability, dtype=float)
    y_probability = y_probability / y_probability.sum(axis=1, keepdims=True)
    return ClassificationMetrics(
        **{
            **metrics.to_dict(),
            "log_loss": float(log_loss(y_true, y_probability, labels=np.arange(y_probability.shape[1]))),
        }
    )


def expected_calibration_error(
    y_true: np.ndarray,
    y_probability: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute a top-class expected calibration error (ECE)."""
    if n_bins < 2:
        raise ValueError("n_bins must be >= 2.")

    y_true = np.asarray(y_true)
    y_probability = np.asarray(y_probability, dtype=float)
    y_pred = np.argmax(y_probability, axis=1)
    confidence = np.max(y_probability, axis=1)
    correct = (y_pred == y_true).astype(float)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidence >= lower) & (confidence < upper)
        if upper == 1.0:
            mask = (confidence >= lower) & (confidence <= upper)
        if not mask.any():
            continue
        ece += mask.mean() * abs(confidence[mask].mean() - correct[mask].mean())
    return float(ece)


def class_support_report(y_true: np.ndarray, classes: list[str]) -> dict[str, int]:
    """Return class counts for promotion/data sufficiency review."""
    values = np.asarray(y_true)
    return {
        str(classes[index]): int(np.sum(values == index))
        for index in range(len(classes))
    }


def assess_training_readiness(
    y_true: np.ndarray,
    classes: list[str],
    *,
    minimum_samples_per_class: int = 5,
) -> dict[str, Any]:
    """Flag sparse-class risk before a new CatBoost model is promoted."""
    support = class_support_report(y_true, classes)
    sparse = {
        technique: count
        for technique, count in support.items()
        if count < minimum_samples_per_class
    }
    return {
        "ready": not sparse,
        "minimum_samples_per_class": minimum_samples_per_class,
        "class_support": support,
        "sparse_classes": sparse,
        "warning": (
            "One or more classes have insufficient observations for reliable supervised validation."
            if sparse
            else None
        ),
    }
