from src.ml.feature_builder import (
    FEATURE_NAMES,
    FEATURE_COUNT,
    build_features, 
    validate_feature_schema,
)


def main():
    print("=" * 70)
    print("EOR ATLAS — FEATURE BUILDER TEST")
    print("=" * 70)

    X = build_features(
        reservoir={
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
    )

    print("\nGenerated feature matrix:")
    print(X.to_string(index=False))

    print("\nShape:")
    print(X.shape)

    print("\nColumns:")
    for i, column in enumerate(X.columns, 1):
        print(f"{i:02d}. {column}")

    assert X.shape == (1, FEATURE_COUNT)
    assert list(X.columns) == FEATURE_NAMES

    assert FEATURE_COUNT == 17

    assert len(FEATURE_NAMES) == 17

    assert list(X.columns) == FEATURE_NAMES

    assert X["depth_mid_ft"].iloc[0] == 5000
    assert X["depth_span_ft"].iloc[0] == 1000

    assert X["perm_mid_md"].iloc[0] == 100
    assert X["perm_span_md"].iloc[0] == 100

    assert X["log10_perm_mid"].iloc[0] == 2

    assert X["formation_sandstone"].iloc[0] == 1
    assert X["formation_carbonates"].iloc[0] == 0
    assert X["formation_unconsolidated_sands"].iloc[0] == 0

    print("\n" + "=" * 70)
    print("FEATURE BUILDER TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()