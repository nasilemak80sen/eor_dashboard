"""
EOR Atlas — Feature Builder

Responsible for converting reservoir screening inputs into the
exact feature schema expected by the trained EOR CatBoost model.

IMPORTANT
---------
The feature order defined here must remain synchronized with:

outputs/model_artifacts/config_catboost_v1.0.0.json
"""

from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd
import numpy as np

# ============================================================
# EOR ATLAS ML FEATURE SCHEMA
# ============================================================

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


FEATURE_COUNT = len(FEATURE_NAMES)


FORMATION_FEATURES = {
    "Sandstone": "formation_sandstone",
    "Carbonates": "formation_carbonates",
    "Unconsolidated sands": "formation_unconsolidated_sands",
}

# ============================================================
# HELPERS
# ============================================================

def _midpoint(minimum: float, maximum: float) -> float:
    """Return midpoint of a minimum/maximum range."""

    return (float(minimum) + float(maximum)) / 2.0


def _span(minimum: float, maximum: float) -> float:
    """Return absolute span of a minimum/maximum range."""

    return abs(float(maximum) - float(minimum))


def _validate_range(
    minimum: float,
    maximum: float,
    name: str,
) -> None:
    """Validate that a numeric range is logically valid."""

    if minimum is None or maximum is None:
        raise ValueError(f"{name}: both minimum and maximum are required.")

    if not np.isfinite(float(minimum)):
        raise ValueError(f"{name}: minimum must be finite.")

    if not np.isfinite(float(maximum)):
        raise ValueError(f"{name}: maximum must be finite.")

    if float(minimum) > float(maximum):
        raise ValueError(
            f"{name}: minimum cannot be greater than maximum."
        )


# ============================================================
# FORMATION ENCODING
# ============================================================

def encode_formation(
    formation_category: str,
) -> dict[str, int]:
    """
    Convert formation category into the three one-hot model features.
    """

    if formation_category not in FORMATION_FEATURES:
        valid = ", ".join(FORMATION_FEATURES.keys())

        raise ValueError(
            f"Unknown formation category: {formation_category!r}. "
            f"Expected one of: {valid}"
        )

    return {
        column: int(column == target_column)
        for column in FORMATION_FEATURES.values()
        for target_column in [FORMATION_FEATURES[formation_category]]
    }


# ============================================================
# FEATURE BUILDER
# ============================================================
def build_features(reservoir: dict[str, Any]) -> pd.DataFrame:
    """
    Convert reservoir screening inputs into the exact
    feature schema expected by the EOR CatBoost model.
    """

    depth_min = float(reservoir["depth_min_ft"])
    depth_max = float(reservoir["depth_max_ft"])

    porosity_min = float(reservoir["porosity_min_pct"])
    porosity_max = float(reservoir["porosity_max_pct"])

    perm_min = float(reservoir["perm_min_md"])
    perm_max = float(reservoir["perm_max_md"])

    api_min = float(reservoir["api_min"])
    api_max = float(reservoir["api_max"])

    visc_min = float(reservoir["visc_min_cp"])
    visc_max = float(reservoir["visc_max_cp"])

    so_min = float(reservoir["so_min_pct"])
    so_max = float(reservoir["so_max_pct"])

    formation = str(
        reservoir.get(
            "formation_category",
            "Sandstone",
        )
    ).strip()

    # --------------------------------------------------------
    # Midpoints
    # --------------------------------------------------------

    depth_mid = (depth_min + depth_max) / 2
    porosity_mid = (porosity_min + porosity_max) / 2
    perm_mid = (perm_min + perm_max) / 2
    api_mid = (api_min + api_max) / 2
    visc_mid = (visc_min + visc_max) / 2
    so_mid = (so_min + so_max) / 2

    # --------------------------------------------------------
    # Spans
    # --------------------------------------------------------

    depth_span = depth_max - depth_min
    porosity_span = porosity_max - porosity_min
    perm_span = perm_max - perm_min
    api_span = api_max - api_min
    visc_span = visc_max - visc_min
    so_span = so_max - so_min

    # --------------------------------------------------------
    # Log transforms
    # --------------------------------------------------------

    if perm_mid <= 0:
        raise ValueError(
            "Mean permeability must be greater than zero."
        )

    if visc_mid <= 0:
        raise ValueError(
            "Mean viscosity must be greater than zero."
        )

    log10_perm_mid = math.log10(perm_mid)
    log10_visc_mid = math.log10(visc_mid)

    # --------------------------------------------------------
    # Formation one-hot encoding
    # --------------------------------------------------------

    formation_sandstone = int(
        formation == "Sandstone"
    )

    formation_carbonates = int(
        formation == "Carbonates"
    )

    formation_unconsolidated_sands = int(
        formation == "Unconsolidated sands"
    )

    # --------------------------------------------------------
    # Construct feature row
    # --------------------------------------------------------

    features = {
        "depth_mid_ft": depth_mid,
        "depth_span_ft": depth_span,

        "porosity_mid_pct": porosity_mid,
        "porosity_span_pct": porosity_span,

        "perm_mid_md": perm_mid,
        "perm_span_md": perm_span,

        "api_mid": api_mid,
        "api_span": api_span,

        "visc_mid_cp": visc_mid,
        "visc_span_cp": visc_span,

        "so_mid_pct": so_mid,
        "so_span_pct": so_span,

        "log10_perm_mid": log10_perm_mid,
        "log10_visc_mid": log10_visc_mid,

        "formation_sandstone": formation_sandstone,
        "formation_carbonates": formation_carbonates,
        "formation_unconsolidated_sands": (
            formation_unconsolidated_sands
        ),
    }

    # --------------------------------------------------------
    # Force exact model order
    # --------------------------------------------------------

    df = pd.DataFrame(
        [[features[name] for name in FEATURE_NAMES]],
        columns=FEATURE_NAMES,
    )

    validate_feature_schema(df)

    return df
# ============================================================
# VALIDATION
# ============================================================
def validate_feature_schema(
    features: pd.DataFrame,
) -> None:
    """
    Validate that generated features exactly match
    the EOR Atlas ML model schema.
    """

    if not isinstance(features, pd.DataFrame):
        raise TypeError(
            "Features must be provided as a pandas DataFrame."
        )

    if features.shape[1] != FEATURE_COUNT:
        raise ValueError(
            f"Expected {FEATURE_COUNT} features, "
            f"received {features.shape[1]}."
        )

    actual = list(features.columns)

    if actual != FEATURE_NAMES:
        raise ValueError(
            "Feature schema mismatch.\n"
            f"Expected: {FEATURE_NAMES}\n"
            f"Received: {actual}"
        )

    if features.isnull().any().any():
        raise ValueError(
            "Feature matrix contains missing values."
        )
