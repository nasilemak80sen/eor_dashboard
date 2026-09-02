from EORWEBDEV.src.tests.model_service import ModelService


service = ModelService()

print("=" * 70)
print("EOR ATLAS — CATBOOST MODEL SERVICE TEST")
print("=" * 70)

loaded = service.load()

print("\nLoaded:", loaded)

if not loaded:
    raise SystemExit(
        "CatBoost model failed to load."
    )


print("\nMODEL INFO")
print("-" * 70)

info = service.get_model_info()

for key, value in info.items():
    print(f"{key}: {value}")


# ------------------------------------------------------------
# Test reservoir case
# ------------------------------------------------------------

values = {
    "depth_ft": 5000.0,
    "porosity_pct": 20.0,
    "perm_md": 100.0,
    "api": 35.0,
    "visc_cp": 2.0,
    "so_pct": 60.0,
}

formation = "Sandstone"


# ------------------------------------------------------------
# Prediction
# ------------------------------------------------------------

result = service.predict_from_inputs(
    values=values,
    formation=formation,
    top_n=3,
)


print("\nFEATURE VECTOR")
print("-" * 70)

print(
    result["features"]
)

print(
    "Feature count:",
    len(result["features"])
)


print("\nTOP 3 CATBOOST PREDICTIONS")
print("-" * 70)

for rank, (
    technique,
    probability,
) in enumerate(
    result["top_predictions"],
    start=1,
):

    print(
        f"{rank}. "
        f"{technique:<30} "
        f"{probability:.2%}"
    )