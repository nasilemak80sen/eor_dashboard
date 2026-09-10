"""EOR Atlas Hybrid Intelligence

Decision-fusion layer for the production EOR recommendation workflow.

Target architecture:
    Excel Gate -> CatBoost Intelligence -> Decision Fusion

The Excel/ScreenTool result remains the hard engineering gate; CatBoost
provides data-driven technique probabilities; this module reconciles both
signals without treating model probability as an engineering pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import numpy as np


MODEL_TO_SCREEN_TECHNIQUES: Dict[str, tuple[str, ...]] = {
    "Combustion": ("ISC",),
    "HC immiscible": ("Immiscible Gas Flood", "Immiscible Gas WAG"),
    "Hot water": ("Hot water",),
    "Miscible CO2": ("CO2 Miscible Flood", "CO2 WAG"),
    "Miscible HC": ("HC Gas Miscible Flood", "HC Gas WAG"),
    "Miscible acid gas": ("Miscible acid gas",),
    "Nitrogen immiscible": ("Immiscible Gas Flood", "Immiscible Gas WAG"),
    "Polymer": ("Polymer (HPAM)", "Polymer (ATBS)"),
    "Steam": ("Steam Flood",),
}


@dataclass(frozen=True)
class HybridWeights:
    """Initial weights for production decision fusion."""

    ml: float = 0.65
    engineering: float = 0.35
    conditional_penalty: float = 0.90

    def validate(self) -> None:
        if self.ml < 0 or self.engineering < 0:
            raise ValueError("Hybrid weights cannot be negative.")
        total = self.ml + self.engineering
        if not np.isclose(total, 1.0):
            raise ValueError(
                f"Hybrid ML + engineering weights must sum to 1.0; got {total:.6f}."
            )
        if not 0 < self.conditional_penalty <= 1:
            raise ValueError("conditional_penalty must be in (0, 1].")


class HybridDecisionService:
    """Combine deterministic engineering compatibility with CatBoost output."""

    def __init__(self, weights: HybridWeights | None = None) -> None:
        self.weights = weights or HybridWeights()
        self.weights.validate()

    @staticmethod
    def _safe_probability(value: Any) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if not np.isfinite(value):
            return 0.0
        return float(np.clip(value, 0.0, 1.0))

    @staticmethod
    def _engineering_score(result: Mapping[str, Any]) -> float:
        status = str(result.get("Status", "")).strip().upper()
        if status in {"FAIL (CRITICAL)", "FAIL"}:
            return 0.0
        try:
            score = float(result.get("Score (%)", 0.0)) / 100.0
        except (TypeError, ValueError):
            score = 0.0
        return float(np.clip(score, 0.0, 1.0))

    @staticmethod
    def _is_conditional(result: Mapping[str, Any]) -> bool:
        return str(result.get("Status", "")).strip().upper() == "CONDITIONAL"

    def fuse(
        self,
        screening_result: Mapping[str, Any],
        ml_probabilities: Mapping[str, float],
        *,
        top_n: int = 3,
        opportunity_context: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return the Excel-gated hybrid ranking."""
        if top_n < 1:
            raise ValueError("top_n must be >= 1.")

        screen_rows = list(screening_result.get("results", []))
        by_technique = {
            str(row.get("EOR Technique")): row
            for row in screen_rows
        }

        candidates: List[Dict[str, Any]] = []
        for model_class, probability in ml_probabilities.items():
            probability = self._safe_probability(probability)
            for technique in MODEL_TO_SCREEN_TECHNIQUES.get(model_class, ()):
                screen_row = by_technique.get(technique)
                if screen_row is None:
                    continue

                engineering = self._engineering_score(screen_row)
                conditional = self._is_conditional(screen_row)
                gate_failed = str(screen_row.get("Status", "")).strip().upper() in {
                    "FAIL",
                    "FAIL (CRITICAL)",
                }

                if gate_failed:
                    hybrid_raw = 0.0
                else:
                    hybrid_raw = (
                        self.weights.ml * probability
                        + self.weights.engineering * engineering
                    )
                    if conditional:
                        hybrid_raw *= self.weights.conditional_penalty

                candidates.append(
                    {
                        "EOR Technique": technique,
                        "CatBoost Class": model_class,
                        "CatBoost Probability": probability,
                        "Engineering Score": engineering,
                        "Engineering Status": screen_row.get("Status", ""),
                        "Hybrid Score Raw": float(hybrid_raw),
                        "Gate Failed": gate_failed,
                        "Conditional": conditional,
                        "Engineering Reason": screen_row.get("Cause of Fail/Pass", ""),
                    }
                )

        # Several CatBoost classes intentionally map to the same ScreenTool
        # technique. Keep the strongest mapped signal instead of double-counting.
        merged: Dict[str, Dict[str, Any]] = {}
        for row in candidates:
            technique = row["EOR Technique"]
            current = merged.get(technique)
            if current is None or row["Hybrid Score Raw"] > current["Hybrid Score Raw"]:
                merged[technique] = row

        ranked_all = sorted(
            merged.values(),
            key=lambda row: row["Hybrid Score Raw"],
            reverse=True,
        )
        ranked = ranked_all[:top_n]

        # Normalize only over the displayed ranking so the Top-N hybrid scores
        # form a useful 100% distribution in the UI.
        top_total = sum(row["Hybrid Score Raw"] for row in ranked)
        for row in ranked:
            row["Hybrid Score"] = (
                float(row["Hybrid Score Raw"] / top_total)
                if top_total > 0
                else 0.0
            )

        recommendation = ranked[0] if ranked else None

        return {
            "recommendation": recommendation,
            "ranking": ranked,
            "eligible_count": len(ranked_all),
            "weights": {
                "ml": self.weights.ml,
                "engineering": self.weights.engineering,
                "conditional_penalty": self.weights.conditional_penalty,
            },
            "opportunity_context": dict(opportunity_context or {}),
            "model_taxonomy_notes": [
                "CatBoost v1 classes are mapped to the current ScreenTool taxonomy.",
                "Unmapped model classes are excluded from the final recommendation.",
                "Hard ScreenTool failures override CatBoost probability.",
                "Hybrid weights are initial decision-fusion defaults and should be tuned on labeled validation cases.",
            ],
        }


def build_opportunity_context(values: Mapping[str, Any]) -> Dict[str, Any]:
    """Derive v3 opportunity context without making it a hard gate."""
    def number(key: str) -> Optional[float]:
        try:
            value = float(values.get(key))
        except (TypeError, ValueError):
            return None
        return value if np.isfinite(value) else None

    so = number("so_pct")
    sorw = number("sorw_pct")
    gor = number("produced_gor_scf_stb")

    movable = None
    movable_fraction = None
    if so is not None and sorw is not None:
        movable = max(so - sorw, 0.0)
        movable_fraction = movable / 100.0

    gor_category = None
    if gor is not None:
        if gor >= 1000:
            gor_category = "High"
        elif gor >= 300:
            gor_category = "Moderate"
        else:
            gor_category = "Low"

    return {
        "current_oil_saturation_pct": so,
        "sorw_pct": sorw,
        "movable_oil_saturation_pct": movable,
        "movable_oil_fraction": movable_fraction,
        "produced_gor_scf_stb": gor,
        "gor_category": gor_category,
        "sorw_available": sorw is not None,
        "gor_available": gor is not None,
    }
