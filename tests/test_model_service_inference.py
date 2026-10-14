from __future__ import annotations

import math

import pytest

from ml.model_service import ModelService


VALID_RESERVOIR = {
    "depth_min_ft": 4000.0,
    "depth_max_ft": 6000.0,
    "porosity_min_pct": 15.0,
    "porosity_max_pct": 25.0,
    "perm_min_md": 50.0,
    "perm_max_md": 150.0,
    "api_min": 28.0,
    "api_max": 35.0,
    "visc_min_cp": 2.0,
    "visc_max_cp": 8.0,
    "so_min_pct": 30.0,
    "so_max_pct": 50.0,
    "formation_category": "Sandstone",
}

EXPECTED_CLASSES = {
    "Combustion",
    "HC immiscible",
    "Hot water",
    "Miscible CO2",
    "Miscible HC",
    "Miscible acid gas",
    "Nitrogen immiscible",
    "Polymer",
    "Steam",
}


@pytest.fixture(scope="module")
def model_service() -> ModelService:
    return ModelService()


def test_saved_artifacts_match_expected_nine_class_contract(model_service: ModelService):
    info = model_service.get_model_info()

    assert model_service.is_loaded() is True
    assert info["model_version"] == "1.0.0"
    assert info["feature_count"] == 17
    assert set(info["classes"]) == EXPECTED_CLASSES
    assert len(info["classes"]) == 9


def test_prediction_probabilities_are_finite_normalized_and_ranked(model_service: ModelService):
    result = model_service.predict(dict(VALID_RESERVOIR))

    assert result.success is True
    assert result.technique in EXPECTED_CLASSES
    assert math.isfinite(result.confidence)
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence_level in {"Low", "Moderate", "High"}
    assert result.warning is None
    assert len(result.candidates) == 9

    probabilities = [candidate.probability for candidate in result.candidates]
    assert all(math.isfinite(p) and 0.0 <= p <= 1.0 for p in probabilities)
    assert sum(probabilities) == pytest.approx(1.0, abs=1e-6)
    assert probabilities == sorted(probabilities, reverse=True)
    assert result.candidates[0].technique == result.technique
    assert result.confidence == pytest.approx(probabilities[0], abs=1e-9)


@pytest.mark.parametrize(
    ("overrides", "error_pattern"),
    [
        (
            {"depth_min_ft": 7000.0, "depth_max_ft": 6000.0},
            "depth_min_ft cannot be greater than depth_max_ft",
        ),
        ({"porosity_min_pct": float("nan")}, "porosity_min_pct.*must be finite"),
        ({"formation_category": "unrecognized formation"}, "Unsupported formation category"),
    ],
)
def test_prediction_fails_closed_on_invalid_reservoir_inputs(
    model_service: ModelService,
    overrides: dict,
    error_pattern: str,
):
    invalid = dict(VALID_RESERVOIR)
    invalid.update(overrides)

    with pytest.raises(ValueError, match=error_pattern):
        model_service.predict(invalid)
