"""EOR Atlas Phase 3A ML integration smoke test."""

from src.ml.feature_builder import FEATURE_COUNT
from src.ml.model_service import ModelService


def create_test_reservoir() -> dict[str, object]:
    return {
        "depth_min_ft": 4500,
        "depth_max_ft": 5500,
        "porosity_min_pct": 17,
        "porosity_max_pct": 22,
        "perm_min_md": 50,
        "perm_max_md": 150,
        "api_min": 27,
        "api_max": 33,
        "visc_min_cp": 5,
        "visc_max_cp": 15,
        "so_min_pct": 65,
        "so_max_pct": 75,
        "formation_category": "Sandstone",
    }


def main() -> None:
    service = ModelService()
    result = service.predict(create_test_reservoir())

    assert service.is_loaded()
    assert result.success
    assert result.feature_count == FEATURE_COUNT == 17
    assert result.technique in service.encoder.classes_
    assert result.candidates == tuple(
        sorted(result.candidates, key=lambda candidate: candidate.probability, reverse=True)
    )
    assert abs(sum(candidate.probability for candidate in result.candidates) - 1.0) < 1e-6
    assert result.top_candidate == result.candidates[0]
    assert len(result.top_n(3)) == 3

    print("ML INTEGRATION TEST PASSED")


if __name__ == "__main__":
    main()