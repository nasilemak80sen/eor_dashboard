from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from src.config.settings import settings


FEATURE_NAMES = [
    "depth_mid_ft",
    "depth_span_ft",
    "porosity_mid_pct",
    "porosity_span_pct",
    "perm_mid_md",
    "perm_span_md",
    "api_mid",
    "api_span",
    "visc_mid_cp",
    "visc_span_cp",
    "so_mid_pct",
    "so_span_pct",
    "log10_perm_mid",
    "log10_visc_mid",
    "formation_sandstone",
    "formation_carbonates",
    "formation_unconsolidated_sands",
]


def main() -> None:

    print("=" * 70)
    print("EOR ATLAS — ML MODEL SMOKE TEST")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. Load artifacts
    # ---------------------------------------------------------

    print("\n[1] Loading model artifacts...")

    model = joblib.load(settings.model_path)
    encoder = joblib.load(settings.label_encoder_path)

    print(f"Model   : {type(model).__name__}")
    print(f"Encoder : {type(encoder).__name__}")

    # ---------------------------------------------------------
    # 2. Validate model schema
    # ---------------------------------------------------------

    print("\n[2] Validating model schema...")

    model_features = list(model.feature_names_)

    if model_features != FEATURE_NAMES:
        print("\nWARNING: Model feature names differ from expected schema.")

        print("\nExpected:")
        for i, name in enumerate(FEATURE_NAMES, 1):
            print(f"{i:02d}. {name}")

        print("\nModel:")
        for i, name in enumerate(model_features, 1):
            print(f"{i:02d}. {name}")

        raise RuntimeError(
            "Model feature schema does not match application schema."
        )

    print("Feature count :", len(model_features))
    print("Feature order : VALID")

    # ---------------------------------------------------------
    # 3. Create representative reservoir input
    # ---------------------------------------------------------

    print("\n[3] Creating test reservoir input...")

    test_input = {
        "depth_mid_ft": 5000.0,
        "depth_span_ft": 1000.0,

        "porosity_mid_pct": 20.0,
        "porosity_span_pct": 5.0,

        "perm_mid_md": 100.0,
        "perm_span_md": 50.0,

        "api_mid": 30.0,
        "api_span": 5.0,

        "visc_mid_cp": 10.0,
        "visc_span_cp": 5.0,

        "so_mid_pct": 70.0,
        "so_span_pct": 10.0,

        "log10_perm_mid": 2.0,
        "log10_visc_mid": 1.0,

        "formation_sandstone": 1,
        "formation_carbonates": 0,
        "formation_unconsolidated_sands": 0,
    }

    # ---------------------------------------------------------
    # 4. Build DataFrame
    # ---------------------------------------------------------

    X = pd.DataFrame(
        [[test_input[name] for name in FEATURE_NAMES]],
        columns=FEATURE_NAMES,
    )

    print("\nInput features:")
    print(X.to_string(index=False))

    # ---------------------------------------------------------
    # 5. Validate input
    # ---------------------------------------------------------

    print("\n[4] Validating input...")

    assert X.shape == (1, 17)

    assert list(X.columns) == FEATURE_NAMES

    assert not X.isnull().any().any()

    print("Shape        :", X.shape)
    print("Columns      : VALID")
    print("Missing data : NONE")

    # ---------------------------------------------------------
    # 6. Run prediction
    # ---------------------------------------------------------

    print("\n[5] Running CatBoost prediction...")

    encoded_prediction = model.predict(X)

    probabilities = model.predict_proba(X)[0]

    encoded_class = int(encoded_prediction[0])

    print("Encoded prediction:", encoded_class)

    # ---------------------------------------------------------
    # 7. Decode prediction
    # ---------------------------------------------------------

    print("\n[6] Decoding prediction...")

    technique = encoder.inverse_transform(
        [encoded_class]
    )[0]

    print("Predicted technique:", technique)

    # ---------------------------------------------------------
    # 8. Probability distribution
    # ---------------------------------------------------------

    print("\n[7] Prediction probabilities...")

    class_names = encoder.classes_

    probability_table = (
        pd.DataFrame(
            {
                "Technique": class_names,
                "Probability": probabilities,
            }
        )
        .sort_values(
            "Probability",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    probability_table["Probability"] = (
        probability_table["Probability"] * 100
    )

    print(
        probability_table.to_string(
            index=False,
            formatters={
                "Probability": "{:.2f}%".format,
            },
        )
    )

    # ---------------------------------------------------------
    # 9. Confidence
    # ---------------------------------------------------------

    confidence = float(probabilities.max())

    print("\nConfidence:", f"{confidence:.2%}")

    # ---------------------------------------------------------
    # 10. Final result
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("PREDICTION SUCCESSFUL")
    print("=" * 70)

    print(f"Technique : {technique}")
    print(f"Confidence: {confidence:.2%}")

    print("\nTop 3 candidates:")

    for _, row in probability_table.head(3).iterrows():

        print(
            f"  {row['Technique']:<25}"
            f"{row['Probability']:.2f}%"
        )


if __name__ == "__main__":
    main()