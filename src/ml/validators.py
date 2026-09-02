"""Validation utilities for EOR Atlas ML inputs."""

from __future__ import annotations

import math
from typing import Any

from src.ml.feature_builder import FEATURE_COUNT, FEATURE_NAMES


REQUIRED_RESERVOIR_FIELDS = [
    "depth_min_ft", "depth_max_ft",
    "porosity_min_pct", "porosity_max_pct",
    "perm_min_md", "perm_max_md",
    "api_min", "api_max",
    "visc_min_cp", "visc_max_cp",
    "so_min_pct", "so_max_pct",
    "formation_category",
]


def validate_reservoir_input(reservoir: dict[str, Any]) -> None:
    """Validate the canonical reservoir input contract."""

    if not isinstance(reservoir, dict):
        raise TypeError("Reservoir input must be a dictionary.")

    missing = [field for field in REQUIRED_RESERVOIR_FIELDS if field not in reservoir]
    if missing:
        raise ValueError("Missing required reservoir fields: " + ", ".join(missing))

    numeric_fields = [field for field in REQUIRED_RESERVOIR_FIELDS if field != "formation_category"]
    for field in numeric_fields:
        value = reservoir[field]
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Reservoir field '{field}' must be numeric. Received: {value!r}") from exc
        if not math.isfinite(numeric_value):
            raise ValueError(f"Reservoir field '{field}' must be finite.")

    range_pairs = [
        ("depth_min_ft", "depth_max_ft"),
        ("porosity_min_pct", "porosity_max_pct"),
        ("perm_min_md", "perm_max_md"),
        ("api_min", "api_max"),
        ("visc_min_cp", "visc_max_cp"),
        ("so_min_pct", "so_max_pct"),
    ]
    for minimum_field, maximum_field in range_pairs:
        if float(reservoir[minimum_field]) > float(reservoir[maximum_field]):
            raise ValueError(f"{minimum_field} cannot be greater than {maximum_field}.")

    for field in ("depth_min_ft", "depth_max_ft", "perm_min_md", "perm_max_md", "visc_min_cp", "visc_max_cp"):
        if float(reservoir[field]) <= 0:
            raise ValueError(f"{field} must be greater than zero.")

    for field in ("porosity_min_pct", "porosity_max_pct", "so_min_pct", "so_max_pct"):
        if not 0 <= float(reservoir[field]) <= 100:
            raise ValueError(f"{field} must be between 0 and 100.")

    valid_formations = {"Sandstone", "Carbonates", "Unconsolidated sands"}
    formation = str(reservoir["formation_category"]).strip()
    if formation not in valid_formations:
        raise ValueError(
            f"Unsupported formation category: {formation!r}. "
            f"Expected one of: {sorted(valid_formations)}"
        )


def validate_feature_matrix(features: Any) -> None:
    """Validate the final feature matrix before model prediction."""

    if features is None:
        raise ValueError("Feature matrix cannot be None.")
    if features.shape[1] != FEATURE_COUNT:
        raise ValueError(f"Expected {FEATURE_COUNT} features, received {features.shape[1]}.")
    if list(features.columns) != FEATURE_NAMES:
        raise ValueError(
            "Feature order mismatch.\n"
            f"Expected: {FEATURE_NAMES}\n"
            f"Received: {list(features.columns)}"
        )
    if features.isnull().any().any():
        raise ValueError("Feature matrix contains missing values.")
