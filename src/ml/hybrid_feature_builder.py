"""Engineering-aware feature builder for the next EOR CatBoost generation.

This module deliberately excludes fuzzy suitability. It converts the full
ScreenTool context, including optional v3 inputs (Sorw and Produced GOR), into
a stable tabular feature matrix for future supervised retraining.

The live production v1 model does not consume this schema yet. It is designed
for the next labeled training dataset and model version.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
import pandas as pd


FEATURE_NAMES = [
    "depth_ft",
    "depth_log10",
    "temperature_c",
    "reservoir_pressure_psi",
    "porosity_pct",
    "permeability_md",
    "permeability_log10",
    "api",
    "viscosity_cp",
    "viscosity_log10",
    "oil_saturation_pct",
    "phi_so",
    "sorw_pct",
    "sorw_provided",
    "movable_oil_saturation_pct",
    "movable_oil_fraction",
    "produced_gor_log10",
    "gor_provided",
    "gor_low",
    "gor_moderate",
    "gor_high",
    "salinity_log10",
    "hardness_log10",
    "net_pay_m",
    "water_cut_pct",
    "co2_available",
    "mmp_satisfied",
    "waterflood_history",
    "water_injection_facilities",
    "gas_injection_facilities",
    "gas_injectivity_score",
    "water_injectivity_score",
    "mobility_ratio_score",
    "heterogeneity_score",
    "field_maturity_score",
    "adsorption_risk_score",
    "water_handling_score",
    "offshore",
    "gas_reinjectable",
    "hc_gas_available",
    "injection_gas_available",
    "wag_ratio_numeric",
    "pressure_bubble_margin",
    "formation_sandstone",
    "formation_carbonates",
    "formation_unconsolidated_sands",
]


CATEGORY_SCORES = {
    "injectivity": {"poor": 0.0, "fair": 0.5, "good": 1.0},
    "mobility": {"unfavorable": 0.0, "neutral": 0.5, "favorable": 1.0},
    "heterogeneity": {"high": 0.0, "moderate": 0.5, "low": 1.0},
    "maturity": {"early": 0.0, "mature": 0.5, "late": 1.0},
    "risk": {"high": 0.0, "medium": 0.5, "low": 1.0},
    "water_handling": {"high": 0.0, "medium": 0.5, "low": 1.0},
}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().replace("_", " ").replace("-", " ").split())


def _number(values: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = float(values.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if np.isfinite(value) else default


def _positive_log10(value: float) -> float:
    return math.log10(max(float(value), 1e-6))


def _binary_yes(values: Mapping[str, Any], key: str) -> float:
    return 1.0 if _norm(values.get(key)) == "yes" else 0.0


def _score(values: Mapping[str, Any], key: str, family: str) -> float:
    return float(CATEGORY_SCORES[family].get(_norm(values.get(key)), 0.0))


def _gor_category(gor: float | None) -> str:
    if gor is None:
        return ""
    if gor >= 1000:
        return "high"
    if gor >= 300:
        return "moderate"
    return "low"


def build_hybrid_features(values: Mapping[str, Any], formation: str) -> pd.DataFrame:
    """Build the versioned engineering-aware feature vector."""
    depth = _number(values, "depth_ft")
    temperature = _number(values, "temperature_c")
    pressure = _number(values, "reservoir_pressure")
    porosity = _number(values, "porosity_pct")
    permeability = _number(values, "perm_md")
    api = _number(values, "api")
    viscosity = _number(values, "visc_cp")
    so = _number(values, "so_pct")
    salinity = _number(values, "salinity_ppm")
    hardness = _number(values, "hardness_ppm")
    net_pay = _number(values, "net_pay_m")
    water_cut = _number(values, "water_cut_pct")

    sorw_raw = values.get("sorw_pct")
    sorw = None
    try:
        if sorw_raw not in (None, ""):
            sorw = float(sorw_raw)
            if not np.isfinite(sorw):
                sorw = None
    except (TypeError, ValueError):
        sorw = None

    gor_raw = values.get("produced_gor_scf_stb")
    gor = None
    try:
        if gor_raw not in (None, ""):
            gor = float(gor_raw)
            if not np.isfinite(gor):
                gor = None
    except (TypeError, ValueError):
        gor = None

    movable = max(so - sorw, 0.0) if sorw is not None else 0.0
    phi_so = porosity * so / 100.0
    gor_cat = _gor_category(gor)

    bubble_point = _number(values, "bubble_point_psi", 0.0)
    pressure_margin = pressure - bubble_point if bubble_point > 0 else 0.0

    wag = _norm(values.get("wag_ratio", "1:1"))
    wag_map = {"1:1": 1.0, "2:1": 2.0, "1:2": 0.5}

    normalized_formation = _norm(formation)

    row = {
        "depth_ft": depth,
        "depth_log10": _positive_log10(depth),
        "temperature_c": temperature,
        "reservoir_pressure_psi": pressure,
        "porosity_pct": porosity,
        "permeability_md": permeability,
        "permeability_log10": _positive_log10(permeability),
        "api": api,
        "viscosity_cp": viscosity,
        "viscosity_log10": _positive_log10(viscosity),
        "oil_saturation_pct": so,
        "phi_so": phi_so,
        "sorw_pct": sorw if sorw is not None else 0.0,
        "sorw_provided": 1.0 if sorw is not None else 0.0,
        "movable_oil_saturation_pct": movable,
        "movable_oil_fraction": movable / 100.0,
        "produced_gor_log10": _positive_log10(gor) if gor is not None and gor > 0 else 0.0,
        "gor_provided": 1.0 if gor is not None else 0.0,
        "gor_low": 1.0 if gor_cat == "low" else 0.0,
        "gor_moderate": 1.0 if gor_cat == "moderate" else 0.0,
        "gor_high": 1.0 if gor_cat == "high" else 0.0,
        "salinity_log10": _positive_log10(salinity),
        "hardness_log10": _positive_log10(hardness),
        "net_pay_m": net_pay,
        "water_cut_pct": water_cut,
        "co2_available": _binary_yes(values, "co2_availability"),
        "mmp_satisfied": _binary_yes(values, "mmp_satisfied"),
        "waterflood_history": _binary_yes(values, "waterflood_history"),
        "water_injection_facilities": _binary_yes(values, "water_injection_facilities"),
        "gas_injection_facilities": _binary_yes(values, "gas_injection_facilities"),
        "gas_injectivity_score": _score(values, "gas_injectivity", "injectivity"),
        "water_injectivity_score": _score(values, "water_injectivity", "injectivity"),
        "mobility_ratio_score": _score(values, "mobility_ratio", "mobility"),
        "heterogeneity_score": _score(values, "heterogeneity", "heterogeneity"),
        "field_maturity_score": _score(values, "field_maturity", "maturity"),
        "adsorption_risk_score": _score(values, "adsorption_risk", "risk"),
        "water_handling_score": _score(values, "water_handling", "water_handling"),
        "offshore": _binary_yes(values, "offshore"),
        "gas_reinjectable": _binary_yes(values, "gas_reinjectable"),
        "hc_gas_available": _binary_yes(values, "hc_gas_availability"),
        "injection_gas_available": _binary_yes(values, "gas_availability"),
        "wag_ratio_numeric": wag_map.get(wag, 1.0),
        "pressure_bubble_margin": pressure_margin,
        "formation_sandstone": 1.0 if normalized_formation == "sandstone" else 0.0,
        "formation_carbonates": 1.0 if "carbonate" in normalized_formation else 0.0,
        "formation_unconsolidated_sands": 1.0 if "unconsolidated" in normalized_formation else 0.0,
    }

    return pd.DataFrame([[row[name] for name in FEATURE_NAMES]], columns=FEATURE_NAMES)
