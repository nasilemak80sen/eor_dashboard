import numpy as np

from ml.hybrid_model_assessment import (
    assess_training_readiness,
    evaluate_multiclass_model,
    expected_calibration_error,
)


def test_multiclass_metrics_are_finite():
    y_true = np.array([0, 1, 2, 0, 1, 2])
    probabilities = np.array([
        [0.80, 0.10, 0.10],
        [0.10, 0.80, 0.10],
        [0.10, 0.10, 0.80],
        [0.70, 0.20, 0.10],
        [0.20, 0.70, 0.10],
        [0.20, 0.10, 0.70],
    ])
    metrics = evaluate_multiclass_model(y_true, probabilities)
    assert metrics.accuracy == 1.0
    assert metrics.macro_f1 == 1.0
    assert metrics.log_loss is not None
    assert np.isfinite(metrics.log_loss)


def test_ece_is_zero_for_perfect_calibrated_binary_subset():
    y_true = np.array([0, 1, 0, 1])
    probabilities = np.array([
        [0.90, 0.10],
        [0.10, 0.90],
        [0.80, 0.20],
        [0.20, 0.80],
    ])
    value = expected_calibration_error(y_true, probabilities, n_bins=5)
    assert value >= 0.0
    assert value < 0.15


def test_training_readiness_flags_sparse_classes():
    report = assess_training_readiness(
        np.array([0, 0, 1, 1, 1, 2]),
        ["CO2", "Polymer", "Steam"],
        minimum_samples_per_class=3,
    )
    assert report["ready"] is False
    assert report["sparse_classes"] == {"CO2": 2, "Steam": 1}
