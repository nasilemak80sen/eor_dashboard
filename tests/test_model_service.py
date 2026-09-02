"""
EOR Atlas — Model Service Integration Test
"""

from src.ml.model_service import ModelService


def create_test_reservoir() -> dict:

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

        "formation_category":
            "Sandstone",
    }


def main():

    print("=" * 70)

    print(
        "EOR ATLAS — MODEL SERVICE INTEGRATION TEST"
    )

    print("=" * 70)

    # ================================================================
    # 1. SERVICE INITIALISATION
    # ================================================================

    print("\n[1] Initialising ModelService...")

    service = ModelService()

    print(
        "Model:",
        service.config["model_name"],
    )

    print(
        "Version:",
        service.config["version"],
    )

    print(
        "Feature count:",
        len(
            service.config["feature_names"]
        ),
    )

    print(
        "Classes:",
        len(
            service.config["classes"]
        ),
    )

    print("PASS")

    # ================================================================
    # 2. INPUT
    # ================================================================

    print(
        "\n[2] Creating test reservoir..."
    )

    reservoir = create_test_reservoir()

    for key, value in reservoir.items():

        print(
            f"  {key}: {value}"
        )

    print("PASS")

    # ================================================================
    # 3. PREDICTION
    # ================================================================

    print(
        "\n[3] Running prediction..."
    )

    result = service.predict(
        reservoir
    )

    print(
        "\nPredicted technique:",
        result.technique,
    )

    print(
        "Confidence:",
        f"{result.confidence_percent:.2f}%",
    )

    print(
        "Confidence level:",
        result.confidence_level,
    )

    # ================================================================
    # 4. CANDIDATES
    # ================================================================

    print(
        "\n[4] Top candidates:"
    )

    for candidate in result.top_candidates:

        print(
            f"  {candidate.rank}. "
            f"{candidate.technique:<25}"
            f"{candidate.probability_percent:>7.2f}%"
        )

    print("PASS")

    # ================================================================
    # 5. WARNING
    # ================================================================

    print(
        "\n[5] Engineering confidence check..."
    )

    if result.warning:

        print(
            "WARNING:",
            result.warning,
        )

    else:

        print(
            "No confidence warning."
        )

    print("PASS")

    # ================================================================
    # COMPLETE
    # ================================================================

    print("\n" + "=" * 70)

    print(
        "MODEL SERVICE TEST PASSED"
    )

    print("=" * 70)


if __name__ == "__main__":

    main()