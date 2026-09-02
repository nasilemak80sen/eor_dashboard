
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import joblib

DEFAULT_ARTIFACT = Path(__file__).resolve().parents[1] / "outputs" / "model_artifacts" / "eor_research_best.joblib"

def _mid(a, b): return (float(a) + float(b)) / 2.0
def _span(a, b): return max(float(b) - float(a), 0.0)

def _norm_formation(value):
    s = str(value).strip().lower()
    if "sandstone" in s: return "Sandstone"
    if "carbonate" in s: return "Carbonates"
    if "unconsolidated" in s: return "Unconsolidated sands"
    return str(value).strip()

def build_feature_row(
    *, depth_min_ft, depth_max_ft,
    porosity_min_pct, porosity_max_pct,
    perm_min_md, perm_max_md,
    api_min, api_max,
    visc_min_cp, visc_max_cp,
    so_min_pct, so_max_pct,
    formation
):
    formation = _norm_formation(formation)
    row = {
        "depth_mid_ft": _mid(depth_min_ft, depth_max_ft),
        "depth_span_ft": _span(depth_min_ft, depth_max_ft),
        "porosity_mid_pct": _mid(porosity_min_pct, porosity_max_pct),
        "porosity_span_pct": _span(porosity_min_pct, porosity_max_pct),
        "perm_mid_md": _mid(perm_min_md, perm_max_md),
        "perm_span_md": _span(perm_min_md, perm_max_md),
        "api_mid": _mid(api_min, api_max),
        "api_span": _span(api_min, api_max),
        "visc_mid_cp": _mid(visc_min_cp, visc_max_cp),
        "visc_span_cp": _span(visc_min_cp, visc_max_cp),
        "so_mid_pct": _mid(so_min_pct, so_max_pct),
        "so_span_pct": _span(so_min_pct, so_max_pct),
    }
    row["log10_perm_mid"] = float(np.log10(max(row["perm_mid_md"], 1e-6)))
    row["log10_visc_mid"] = float(np.log10(max(row["visc_mid_cp"], 1e-6)))
    for f in ["Sandstone", "Carbonates", "Unconsolidated sands"]:
        row["formation_" + f.lower().replace(" ", "_")] = 1.0 if formation == f else 0.0
    return pd.DataFrame([row])

class ResearchModelService:
    def __init__(self, artifact_path: Optional[Path | str] = None):
        self.artifact_path = Path(artifact_path) if artifact_path else DEFAULT_ARTIFACT
        self.bundle = None

    def load(self) -> bool:
        if not self.artifact_path.exists():
            return False
        self.bundle = joblib.load(self.artifact_path)
        required = {"model", "label_encoder", "feature_names"}
        missing = required.difference(self.bundle)
        if missing:
            raise ValueError(f"Artifact missing keys: {sorted(missing)}")
        return True

    @property
    def is_loaded(self) -> bool:
        return self.bundle is not None

    def model_info(self) -> Dict[str, Any]:
        if not self.bundle:
            return {"loaded": False}
        return {
            "loaded": True,
            "model_name": self.bundle.get("model_name", "Unknown"),
            "classes": list(self.bundle["label_encoder"].classes_),
            "feature_count": len(self.bundle["feature_names"]),
            "training_rows": self.bundle.get("training_rows"),
            "input_schema_version": self.bundle.get("input_schema_version"),
        }

    def predict_top3_from_ranges(self, **kwargs) -> List[Tuple[str, float]]:
        if not self.bundle:
            raise RuntimeError("Research model is not loaded.")
        X = build_feature_row(**kwargs)
        X = X.reindex(columns=self.bundle["feature_names"], fill_value=0.0)
        proba = np.asarray(self.bundle["model"].predict_proba(X)[0], dtype=float)
        labels = self.bundle["label_encoder"].inverse_transform(np.arange(len(proba)))
        order = np.argsort(proba)[::-1][:min(3, len(proba))]
        return [(str(labels[i]), float(proba[i])) for i in order]
