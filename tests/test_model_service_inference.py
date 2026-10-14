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

VALID_RESERVOIR_CASES = [
    pytest.param(VALID_RESERVOIR, id="baseline-sandstone"),
    pytest.param(
        {
            "depth_min_ft": 8500.0,
            "depth_max_ft": 10500.0,
            "porosity_min_pct": 8.0,
            "porosity_max_pct": 18.0,
            "perm_min_md": 0.5,
            "perm_max_md": 15.0,
            "api_min": 29.0,
            "api_max": 36.0,
            "visc_min_cp": 0.7,
            "visc_max_cp": 3.0,
            "so_min_pct": 25.0,
            "so_max_pct": 45.0,
            "formation_category": "Carbonates",
        },
        id="carbonate-lower-permeability",
    ),
    pytest.param(
        {
            "depth_min_ft": 500.0,
            "depth_max_ft": 2000.0,
            "porosity_min_pct": 28.0,
            "porosity_max_pct": 38.0,
            "perm_min_md": 300.0,
            "perm_max_md": 1500.0,
            "api_min": 12.0,
            "api_max": 26.0,
            "visc_min_cp": 20.0,
            "visc_max_cp": 120.0,
            "so_min_pct": 40.0,
            "so_max_pct": 65.0,
            "formation_category": "Unconsolidated sands",
        },
        id="unconsolidated-high-permeability",
    ),
]

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


@pytest.mark.parametrize("reservoir", VALID_RESERVOIR_CASES)
def test_prediction_probabilities_are_finite_normalized_and_ranked(
    model_service: ModelService,
    reservoir: dict,
):
    result = model_service.predict(dict(reservoir))

    assert result.success is True
    assert result.technique in EXPECTED_CLASSES
    assert math.isfinite(result.confidence)
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence_level in {"Low", "Moderate", "High"}
    assert result.warning is None or "below the engineering decision threshold" in result.warning
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
        ({"api_max": 120.0}, "api_max must be between 0 and 100"),
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



def test_v1_reference_profile_matches_recorded_smoke_prediction(model_service: ModelService):
    """Golden regression for the controlled profile used during local validation."""
    result = model_service.predict(dict(VALID_RESERVOIR))

    assert result.technique == "Miscible HC"
    assert result.confidence == pytest.approx(0.677060985423021, abs=1e-6)
    assert [
        candidate.technique
        for candidate in result.candidates[:3]
    ] == ["Miscible HC", "Miscible CO2", "Polymer"]
    assert [
        candidate.probability
        for candidate in result.candidates[:3]
    ] == pytest.approx([0.677060985423021, 0.1453, 0.0759], abs=1e-3)
