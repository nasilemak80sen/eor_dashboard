from __future__ import annotations
from pathlib import Path

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import streamlit as st

try:
    import pydeck as pdk
except Exception:
    pdk = None

from config.settings import settings
from utils.logging_config import logger
from domain.fuzzy_engine import FuzzyEngine
from data.repositories import EnvelopeRepository, WorkbookRepository
from data.queries import RepositoryFactory
from ml.model_service import ModelService


# =============================================================================
# CONSTANTS
# =============================================================================

SCREENING_TOOL_SHEET = "Screening"

SCREENING_INPUT_DEFAULTS = {
    "depth_ft": 5000.0,
    "reservoir_pressure": 2500.0,
    "temperature_c": 95.0,
    "visc_cp": 2.0,
    "api": 35.0,
    "perm_md": 100.0,
    "porosity_frac": 0.20,
    "salinity_ppm": 50000.0,
    "hardness_ppm": 300.0,
    "rock_type": "Sandstone",
    "net_pay_m": 30.0,
    "heterogeneity": "Moderate",
    "gas_availability": "Yes",
    "oxygen_present": "No",
    "ooip_mmstb": 100.0,
    "base_rf_pct": 35.0,
    "drive_mechanism": "Waterflood",
    "drive_multiplier": 1.0,
    "co2_availability": "Yes",
    "mmp_satisfied": "Yes",
    "waterflood_history": "Yes",
    "water_cut_pct": 60.0,
    "field_maturity": "Mature",
    "maturity_factor": 1.0,
    "mobility_ratio": "Favorable",
    "adsorption_risk": "Low",
    "water_handling": "Low",
    "offshore": "No",
    "water_injection_facilities": "Yes",
    "gas_injection_facilities": "Yes",
    "wag_ratio": "1:1",
    "gas_injectivity": "Good",
    "water_injectivity": "Good",
    "gravity_override_risk": "Low",
    "hc_gas_availability": "No",
    "produced_gor_category": "Moderate",
    "gas_reinjectable": "Yes",
    "produced_gor_scf_stb": 574.0,
}


# =============================================================================
# PAGE CONFIG / STYLE
# =============================================================================

st.set_page_config(
    page_title=settings.ui_config["page_title"],
    page_icon=settings.ui_config["page_icon"],
    layout=settings.ui_config["layout"],
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    .stTabs [role="tablist"] {
        background: rgba(15, 23, 42, 0.05);
        border-radius: 10px;
    }

    .stTabs [role="tab"] {
        padding: 0.7rem 1rem;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }

    .exec-kpi-card {
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        min-height: 110px;
        margin-bottom: 0.8rem;
    }

    .exec-kpi-label {
        color: rgba(255,255,255,0.75);
        font-size: 0.77rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }

    .exec-kpi-value {
        color: white;
        font-size: 1.8rem;
        font-weight: 700;
    }

    .top3-card,
    .model-status-card {
        border: 1px solid rgba(15, 23, 42, 0.10);
        border-radius: 14px;
        padding: 1rem;
        background: rgba(248, 250, 252, 0.85);
        margin-bottom: 0.8rem;
    }

    .intelligence-note {
        border-left: 4px solid #2563eb;
        background: rgba(37, 99, 235, 0.06);
        padding: 0.8rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }

    .status-box {
        background: rgba(15, 23, 42, 0.04);
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 12px;
        padding: 0.75rem;
    }

    .status-row {
        display: flex;
        justify-content: space-between;
        margin: 0.35rem 0;
        font-size: 0.88rem;
    }

    .status-pill {
        padding: 0.18rem 0.5rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
    }

    .ready {
        background: rgba(22, 163, 74, 0.12);
        color: #166534;
    }

    .warn {
        background: rgba(245, 158, 11, 0.12);
        color: #b45309;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# GENERIC HELPERS
# =============================================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _normalise_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _format_probability(value: float) -> str:
    return f"{value:.1%}" if abs(value) <= 1 else f"{value:.1f}%"


def _screening_status_display(status: str) -> str:
    return {
        "PASS": "🟢 PASS",
        "CONDITIONAL": "🟡 CONDITIONAL",
        "FAIL (critical)": "🔴 FAIL (critical)",
    }.get(status, status)


# =============================================================================
# SERVICE INITIALIZATION
# =============================================================================

@st.cache_resource
def initialize_services() -> Optional[Dict[str, Any]]:
    """Initialize reusable services once per Streamlit process."""

    try:
        env, techs_all = EnvelopeRepository.load_envelopes()
        workbook_sheets = WorkbookRepository.load_workbook()

        fuzzy_engine = FuzzyEngine(
            env,
            alpha=settings.fuzzy_alpha,
        )

        model_service = ModelService()
        model_loaded = model_service.is_loaded()

        return {
            "env": env,
            "techs_all": techs_all,
            "workbook_sheets": workbook_sheets,
            "fuzzy_engine": fuzzy_engine,
            "model_service": model_service,
            "model_loaded": model_loaded,
        }

    except Exception:
        logger.exception(
            "Failed to initialize EOR Atlas services."
        )
        return None


# =============================================================================
# DETERMINISTIC EXCEL SCREENING
# =============================================================================

class ExcelScreeningService:
    """Workbook-parity deterministic EOR screening."""

    @staticmethod
    def _yes(value: Any) -> bool:
        return _normalise_text(value) == "yes"

    @staticmethod
    def _no(value: Any) -> bool:
        return _normalise_text(value) == "no"

    @staticmethod
    def _eq(value: Any, target: str) -> bool:
        return _normalise_text(value) == _normalise_text(target)

    @staticmethod
    def _in(value: Any, options: Sequence[str]) -> bool:
        return _normalise_text(value) in {
            _normalise_text(x) for x in options
        }

    @staticmethod
    def _gor_category(gor: Optional[float]) -> str:
        if gor is None:
            return ""
        if gor >= 1000:
            return "High"
        if gor >= 300:
            return "Moderate"
        return "Low"

    def prepare_inputs(
        self,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        values = dict(inputs)
        gor = _safe_float(
            values.get("produced_gor_scf_stb")
        )
        numeric_cat = self._gor_category(gor)

        if numeric_cat:
            values["gor_category_numeric"] = numeric_cat
            values["produced_gor_category"] = numeric_cat

        external_hc = self._yes(
            values.get("hc_gas_availability")
        )
        direct_gas = self._yes(
            values.get("gas_availability")
        )
        reinjectable = self._yes(
            values.get("gas_reinjectable")
        )

        cat = values.get(
            "produced_gor_category"
        ) or numeric_cat

        if external_hc:
            values["hc_source_status"] = "Available"
        elif (
            not direct_gas
            and self._in(cat, ["High", "Moderate"])
            and reinjectable
        ):
            values["hc_source_status"] = "Conditional"
        else:
            values["hc_source_status"] = "Unavailable"

        return values

    @staticmethod
    def _result(
        technique: str,
        critical_fail: bool,
        causes: List[str],
        score: float,
        max_delta_rf: float,
        values: Dict[str, Any],
        conditional: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        conditional = conditional or []

        if critical_fail:
            status = "FAIL (critical)"
            suitability = "Not suitable"
            score = 0.0
            delta_rf = 0.0
        else:
            status = "CONDITIONAL" if conditional else "PASS"
            if score >= 80:
                suitability = "Highly suitable"
            elif score >= 50:
                suitability = "Potentially suitable"
            else:
                suitability = "Marginal"
            delta_rf = (
                score / 100.0
            ) * max_delta_rf

        drive = (
            _safe_float(
                values.get("drive_multiplier"),
                1.0,
            )
            or 1.0
        )
        maturity = (
            _safe_float(
                values.get("maturity_factor"),
                1.0,
            )
            or 1.0
        )

        delta_rf *= drive * maturity

        base_rf = (
            _safe_float(
                values.get("base_rf_pct"),
                0.0,
            )
            or 0.0
        )

        final_rf = base_rf + delta_rf

        ooip = (
            _safe_float(
                values.get("ooip_mmstb"),
                0.0,
            )
            or 0.0
        )

        eur = ooip * final_rf / 100.0

        reasons = list(causes) + list(conditional)

        return {
            "EOR Technique": technique,
            "Critical Fail": bool(critical_fail),
            "Cause of Fail/Pass": (
                "; ".join(reasons)
                if reasons
                else "All critical criteria passed"
            ),
            "Score (%)": float(score),
            "Status": status,
            "Suitability": suitability,
            "ΔRF_EOR (%)": float(delta_rf),
            "Final RF (%)": float(final_rf),
            "EUR (MMstb)": float(eur),
        }

    def screen(
        self,
        raw_inputs: Dict[str, Any],
        formation: str,
    ) -> Dict[str, Any]:

        v = self.prepare_inputs(raw_inputs)

        api = _safe_float(v.get("api"), 0) or 0
        visc = _safe_float(v.get("visc_cp"), 0) or 0
        depth = _safe_float(v.get("depth_ft"), 0) or 0
        temp = _safe_float(v.get("temperature_c"), 0) or 0
        perm = _safe_float(v.get("perm_md"), 0) or 0
        tds = _safe_float(v.get("salinity_ppm"), 0) or 0
        hardness = _safe_float(v.get("hardness_ppm"), 0) or 0
        water_cut = _safe_float(
            v.get("water_cut_pct"), 0
        ) or 0

        waterflood = self._yes(
            v.get("waterflood_history")
        )
        mobility_ok = self._in(
            v.get("mobility_ratio"),
            ["Favorable", "Neutral"],
        )
        water_fac = self._yes(
            v.get("water_injection_facilities")
        )
        gas_fac = self._yes(
            v.get("gas_injection_facilities")
        )
        gas_inj = self._in(
            v.get("gas_injectivity"),
            ["Good", "Fair"],
        )
        water_inj = self._in(
            v.get("water_injectivity"),
            ["Good", "Fair"],
        )
        gravity_ok = self._in(
            v.get("gravity_override_risk"),
            ["Low", "Medium"],
        )
        gravity_high = self._eq(
            v.get("gravity_override_risk"),
            "High",
        )

        hc_source_ok = (
            self._in(
                v.get("hc_source_status"),
                ["Available", "Conditional"],
            )
            or self._yes(
                v.get("hc_gas_availability")
            )
        )

        gas_source_ok = (
            self._yes(v.get("gas_availability"))
            or hc_source_ok
        )

        gor_category = str(
            v.get("produced_gor_category") or ""
        )
        gor_weight = (
            1.0 if gor_category == "High"
            else 0.5 if gor_category == "Moderate"
            else 0.0
        )

        source_conditional = (
            not self._yes(
                v.get("hc_gas_availability")
            )
            and gor_category in {"High", "Moderate"}
            and self._yes(
                v.get("gas_reinjectable")
            )
        )

        results = []

        # CO2 Miscible Flood
        causes = []
        for bad, msg in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (depth < 2500, "Depth <2500 ft"),
            (
                not self._yes(
                    v.get("co2_availability")
                ),
                "CO2 unavailable",
            ),
            (
                not self._yes(
                    v.get("mmp_satisfied")
                ),
                "MMP not satisfied",
            ),
        ]:
            if bad:
                causes.append(msg)

        score = 100 * sum([
            api >= 25,
            visc <= 10,
            depth >= 2500,
            self._yes(v.get("co2_availability")),
            self._yes(v.get("mmp_satisfied")),
            waterflood,
            mobility_ok,
        ]) / 7

        results.append(
            self._result(
                "CO2 Miscible Flood",
                bool(causes),
                causes,
                score,
                15,
                v,
            )
        )

        # CO2 WAG
        causes, conditional = [], []
        for bad, msg in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (
                not self._yes(
                    v.get("co2_availability")
                ),
                "CO2 unavailable",
            ),
            (
                not self._yes(
                    v.get("mmp_satisfied")
                ),
                "MMP not satisfied",
            ),
            (
                not water_fac,
                "Water injection facilities unavailable",
            ),
            (
                not gas_fac,
                "Gas injection facilities unavailable",
            ),
        ]:
            if bad:
                causes.append(msg)
        if gravity_high:
            conditional.append(
                "Conditional: gravity override risk high"
            )

        score = 100 * sum([
            api >= 25,
            visc <= 10,
            self._yes(v.get("co2_availability")),
            self._yes(v.get("mmp_satisfied")),
            water_fac,
            gas_fac,
            waterflood,
            gas_inj,
            water_inj,
            gravity_ok,
        ]) / 10

        results.append(
            self._result(
                "CO2 WAG",
                bool(causes),
                causes,
                score,
                18,
                v,
                conditional,
            )
        )

        # HC Gas Miscible Flood
        causes, conditional = [], []
        for bad, msg in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (depth < 2500, "Depth <2500 ft"),
            (
                not self._yes(
                    v.get("mmp_satisfied")
                ),
                "MMP not satisfied",
            ),
            (
                not hc_source_ok,
                "HC gas source unavailable",
            ),
        ]:
            if bad:
                causes.append(msg)
        if source_conditional:
            conditional.append(
                "Conditional: produced GOR supports HC gas reinjection/recycling"
            )

        score = 100 * sum([
            api >= 25,
            visc <= 10,
            depth >= 2500,
            self._yes(v.get("mmp_satisfied")),
            hc_source_ok,
            waterflood,
            mobility_ok,
            gor_weight,
        ]) / 8

        results.append(
            self._result(
                "HC Gas Miscible Flood",
                bool(causes),
                causes,
                score,
                14,
                v,
                conditional,
            )
        )

        # HC Gas WAG
        causes, conditional = [], []
        for bad, msg in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (
                not self._yes(
                    v.get("mmp_satisfied")
                ),
                "MMP not satisfied",
            ),
            (
                not hc_source_ok,
                "HC gas source unavailable",
            ),
            (
                not water_fac,
                "Water injection facilities unavailable",
            ),
            (
                not gas_fac,
                "Gas injection facilities unavailable",
            ),
        ]:
            if bad:
                causes.append(msg)
        if source_conditional:
            conditional.append(
                "Conditional: produced GOR supports HC gas reinjection/recycling"
            )
        if gravity_high:
            conditional.append(
                "Conditional: gravity override risk high"
            )

        score = 100 * sum([
            api >= 25,
            visc <= 10,
            self._yes(v.get("mmp_satisfied")),
            hc_source_ok,
            water_fac,
            gas_fac,
            waterflood,
            gas_inj,
            water_inj,
            gravity_ok,
            gor_weight,
        ]) / 11

        results.append(
            self._result(
                "HC Gas WAG",
                bool(causes),
                causes,
                score,
                17,
                v,
                conditional,
            )
        )

        # Immiscible Gas Flood
        causes, conditional = [], []
        for bad, msg in [
            (api < 15, "API <15°"),
            (visc > 35, "Viscosity >35 cP"),
            (
                not gas_source_ok,
                "Gas source unavailable",
            ),
        ]:
            if bad:
                causes.append(msg)
        if source_conditional:
            conditional.append(
                "Conditional: produced GOR supports gas recycling"
            )

        score = 100 * sum([
            api >= 15,
            visc <= 35,
            gas_source_ok,
            waterflood,
            mobility_ok,
            gor_weight,
        ]) / 6

        results.append(
            self._result(
                "Immiscible Gas Flood",
                bool(causes),
                causes,
                score,
                8,
                v,
                conditional,
            )
        )

        # Immiscible Gas WAG
        causes, conditional = [], []
        for bad, msg in [
            (api < 15, "API <15°"),
            (visc > 35, "Viscosity >35 cP"),
            (
                not gas_source_ok,
                "Gas source unavailable",
            ),
            (
                not water_fac,
                "Water injection facilities unavailable",
            ),
            (
                not gas_fac,
                "Gas injection facilities unavailable",
            ),
        ]:
            if bad:
                causes.append(msg)
        if source_conditional:
            conditional.append(
                "Conditional: produced GOR supports gas recycling"
            )
        if gravity_high:
            conditional.append(
                "Conditional: gravity override risk high"
            )

        score = 100 * sum([
            api >= 15,
            visc <= 35,
            gas_source_ok,
            waterflood,
            water_fac,
            gas_fac,
            gas_inj,
            water_inj,
            gravity_ok,
            gor_weight,
        ]) / 10

        results.append(
            self._result(
                "Immiscible Gas WAG",
                bool(causes),
                causes,
                score,
                12,
                v,
                conditional,
            )
        )

        # Polymer HPAM
        causes = []
        for bad, msg in [
            (temp > 70, "Temperature >70°C"),
            (tds > 70000, "TDS >70,000 ppm"),
            (hardness > 500, "Hardness >500 ppm"),
            (perm < 50, "Permeability <50 mD"),
            (
                self._yes(v.get("oxygen_present")),
                "Oxygen present in polymer system",
            ),
        ]:
            if bad:
                causes.append(msg)

        score = 100 * sum([
            temp <= 70,
            tds <= 70000,
            hardness <= 500,
            perm >= 50,
            not self._yes(v.get("oxygen_present")),
            water_cut >= 50,
            mobility_ok,
        ]) / 7

        results.append(
            self._result(
                "Polymer (HPAM)",
                bool(causes),
                causes,
                score,
                10,
                v,
            )
        )

        # Polymer ATBS
        causes = []
        for bad, msg in [
            (temp > 120, "Temperature >120°C"),
            (tds > 250000, "TDS >250,000 ppm"),
            (hardness > 5000, "Hardness >5,000 ppm"),
            (perm < 30, "Permeability <30 mD"),
            (
                self._yes(v.get("oxygen_present")),
                "Oxygen present in polymer system",
            ),
        ]:
            if bad:
                causes.append(msg)

        score = 100 * sum([
            temp <= 120,
            tds <= 250000,
            hardness <= 5000,
            perm >= 30,
            not self._yes(v.get("oxygen_present")),
            water_cut >= 50,
            mobility_ok,
        ]) / 7

        results.append(
            self._result(
                "Polymer (ATBS)",
                bool(causes),
                causes,
                score,
                12,
                v,
            )
        )

        # SP
        causes = []
        for bad, msg in [
            (api < 20, "API <20°"),
            (visc > 35, "Viscosity >35 cP"),
            (temp > 100, "Temperature >100°C"),
            (tds > 100000, "TDS >100,000 ppm"),
            (
                self._eq(
                    v.get("adsorption_risk"),
                    "High",
                ),
                "Surfactant adsorption risk high",
            ),
            (
                self._eq(
                    v.get("water_handling"),
                    "High",
                ),
                "Produced-water handling complexity high",
            ),
        ]:
            if bad:
                causes.append(msg)

        score = 100 * sum([
            api >= 20,
            visc <= 35,
            temp <= 100,
            tds <= 100000,
            self._in(
                v.get("adsorption_risk"),
                ["Low", "Medium"],
            ),
            self._in(
                v.get("water_handling"),
                ["Low", "Medium"],
            ),
            self._in(
                v.get("rock_type"),
                ["Sandstone", "Carbonate", "Carbonates"],
            ),
            water_cut >= 50,
        ]) / 8

        results.append(
            self._result(
                "SP",
                bool(causes),
                causes,
                score,
                15,
                v,
            )
        )

        # ASP
        causes = []
        for bad, msg in [
            (api < 22, "API <22°"),
            (visc > 30, "Viscosity >30 cP"),
            (temp > 90, "Temperature >90°C"),
            (tds > 10000, "TDS >10,000 ppm"),
            (hardness > 50, "Hardness >50 ppm"),
            (
                not self._eq(
                    v.get("rock_type"),
                    "Sandstone",
                ),
                "Rock type is not Sandstone",
            ),
        ]:
            if bad:
                causes.append(msg)

        score = 100 * sum([
            api >= 22,
            visc <= 30,
            temp <= 90,
            tds <= 10000,
            hardness <= 50,
            self._eq(
                v.get("rock_type"),
                "Sandstone",
            ),
            self._in(
                v.get("water_handling"),
                ["Low", "Medium"],
            ),
            water_cut >= 50,
        ]) / 8

        results.append(
            self._result(
                "ASP",
                bool(causes),
                causes,
                score,
                20,
                v,
            )
        )

        # CSS
        causes = []
        for bad, msg in [
            (visc < 100, "Viscosity <100 cP"),
            (depth > 3000, "Depth >3000 ft"),
            (perm < 500, "Permeability <500 mD"),
        ]:
            if bad:
                causes.append(msg)

        score = 100 * sum([
            visc >= 100,
            depth <= 3000,
            perm >= 500,
            self._no(v.get("offshore")),
        ]) / 4

        results.append(
            self._result(
                "CSS",
                bool(causes),
                causes,
                score,
                15,
                v,
            )
        )

        # Steam Flood
        causes = []
        for bad, msg in [
            (visc < 100, "Viscosity <100 cP"),
            (depth > 3000, "Depth >3000 ft"),
            (perm < 1000, "Permeability <1000 mD"),
        ]:
            if bad:
                causes.append(msg)

        score = 100 * sum([
            visc >= 100,
            depth <= 3000,
            perm >= 1000,
            self._no(v.get("offshore")),
        ]) / 4

        results.append(
            self._result(
                "Steam Flood",
                bool(causes),
                causes,
                score,
                18,
                v,
            )
        )

        # ISC
        causes = []
        for bad, msg in [
            (
                visc < 10 or visc > 200,
                "Viscosity outside 10–200 cP",
            ),
            (
                perm < 200,
                "Permeability <200 mD",
            ),
        ]:
            if bad:
                causes.append(msg)

        score = 100 * sum([
            10 <= visc <= 200,
            perm >= 200,
            self._no(v.get("offshore")),
        ]) / 3

        results.append(
            self._result(
                "ISC",
                bool(causes),
                causes,
                score,
                10,
                v,
            )
        )

        # Stable rank: score first, original technique order second.
        ranked = sorted(
            enumerate(results),
            key=lambda x: (
                -x[1]["Score (%)"],
                x[0],
            ),
        )

        return {
            "status": "OK",
            "formation": formation,
            "inputs": v,
            "results": [x[1] for x in ranked],
            "source_sheet": SCREENING_TOOL_SHEET,
        }


def render_excel_screening_result(
    result: Dict[str, Any],
) -> None:

    results = result["results"]

    st.subheader(
        "📋 EOR Screening Results"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "🟢 PASS",
        sum(
            r["Status"] == "PASS"
            for r in results
        ),
    )

    c2.metric(
        "🟡 CONDITIONAL",
        sum(
            r["Status"] == "CONDITIONAL"
            for r in results
        ),
    )

    c3.metric(
        "🔴 FAIL (critical)",
        sum(
            r["Status"] == "FAIL (critical)"
            for r in results
        ),
    )

    table = pd.DataFrame(
        results
    ).copy()

    table["Status"] = table[
        "Status"
    ].map(
        _screening_status_display
    )

    for col in [
        "Score (%)",
        "ΔRF_EOR (%)",
        "Final RF (%)",
        "EUR (MMstb)",
    ]:
        table[col] = table[
            col
        ].round(2)

    st.dataframe(
        table[
            [
                "EOR Technique",
                "Status",
                "Suitability",
                "Score (%)",
                "ΔRF_EOR (%)",
                "Final RF (%)",
                "EUR (MMstb)",
                "Cause of Fail/Pass",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# COMMON INPUT FORM
# =============================================================================

def render_eor_input_form(
    prefix: str,
) -> Tuple[Dict[str, Any], str]:
    """Render shared reservoir inputs for Screening and Intelligence."""

    d = SCREENING_INPUT_DEFAULTS

    with st.expander(
        "📝 Reservoir Characteristics",
        expanded=True,
    ):
        a, b, c = st.columns(3)

        with a:
            formation = st.selectbox(
                "Formation Category",
                settings.ui_config[
                    "formation_categories"
                ],
                index=0,
                key=f"{prefix}_formation",
            )

            depth_ft = st.number_input(
                "Depth (ft)",
                min_value=0.0,
                value=d["depth_ft"],
                step=50.0,
                key=f"{prefix}_depth",
            )

            st.number_input(
                "Reservoir Pressure (psia)",
                min_value=0.0,
                value=d["reservoir_pressure"],
                step=50.0,
                key=f"{prefix}_pressure",
            )

            temperature_c = st.number_input(
                "Temperature (°C)",
                min_value=0.0,
                value=d["temperature_c"],
                step=1.0,
                key=f"{prefix}_temperature",
            )

            visc_cp = st.number_input(
                "Oil Viscosity (cP)",
                min_value=0.0,
                value=d["visc_cp"],
                step=0.1,
                key=f"{prefix}_visc",
            )

        with b:
            api = st.number_input(
                "API Gravity (°API)",
                0.0,
                80.0,
                value=d["api"],
                step=0.5,
                key=f"{prefix}_api",
            )

            perm_md = st.number_input(
                "Permeability (mD)",
                min_value=0.0,
                value=d["perm_md"],
                step=10.0,
                key=f"{prefix}_perm",
            )

            porosity_frac = st.number_input(
                "Porosity (fraction)",
                0.0,
                1.0,
                value=d["porosity_frac"],
                step=0.01,
                key=f"{prefix}_por",
            )

            salinity_ppm = st.number_input(
                "Salinity / TDS (ppm)",
                min_value=0.0,
                value=d["salinity_ppm"],
                step=1000.0,
                key=f"{prefix}_tds",
            )

            hardness_ppm = st.number_input(
                "Hardness Ca²⁺+Mg²⁺ (ppm)",
                min_value=0.0,
                value=d["hardness_ppm"],
                step=50.0,
                key=f"{prefix}_hardness",
            )

        with c:
            rock_type = st.selectbox(
                "Rock Type",
                [
                    "Sandstone",
                    "Carbonate",
                    "Unconsolidated sands",
                ],
                key=f"{prefix}_rock",
            )

            net_pay_m = st.number_input(
                "Net Pay (m)",
                min_value=0.0,
                value=d["net_pay_m"],
                step=1.0,
                key=f"{prefix}_netpay",
            )

            heterogeneity = st.selectbox(
                "Heterogeneity",
                ["Low", "Moderate", "High"],
                index=1,
                key=f"{prefix}_heterogeneity",
            )

            gas_availability = st.selectbox(
                "Gas Availability",
                ["Yes", "No"],
                index=0,
                key=f"{prefix}_gas_availability",
            )

            oxygen_present = st.selectbox(
                "Oxygen Present in Polymer System",
                ["Yes", "No"],
                index=1,
                key=f"{prefix}_oxygen",
            )

            so_pct = st.number_input(
                "Oil Saturation (%) [CatBoost]",
                0.0,
                100.0,
                value=55.0,
                step=1.0,
                key=f"{prefix}_so",
            )

    with st.expander(
        "🛢️ Recovery / EOR Context",
        expanded=True,
    ):
        a, b, c = st.columns(3)

        with a:
            ooip_mmstb = st.number_input(
                "OOIP (MMstb)",
                min_value=0.0,
                value=d["ooip_mmstb"],
                step=10.0,
                key=f"{prefix}_ooip",
            )

            base_rf_pct = st.number_input(
                "Base RF without EOR (%)",
                0.0,
                100.0,
                value=d["base_rf_pct"],
                step=1.0,
                key=f"{prefix}_base_rf",
            )

            drive_mechanism = st.selectbox(
                "Drive Mechanism",
                [
                    "Waterflood",
                    "Gas Drive",
                    "Solution Gas Drive",
                    "Natural Depletion",
                    "Other",
                ],
                key=f"{prefix}_drive",
            )

            drive_multiplier = st.number_input(
                "Drive Mech Multiplier",
                0.0,
                5.0,
                value=d["drive_multiplier"],
                step=0.05,
                key=f"{prefix}_drive_multiplier",
            )

            waterflood_history = st.selectbox(
                "Waterflood History",
                ["Yes", "No"],
                index=0,
                key=f"{prefix}_waterflood",
            )

        with b:
            co2_availability = st.selectbox(
                "CO2 Availability",
                ["Yes", "No"],
                index=0,
                key=f"{prefix}_co2",
            )

            mmp_satisfied = st.selectbox(
                "MMP Satisfied?",
                ["Yes", "No"],
                index=0,
                key=f"{prefix}_mmp",
            )

            water_cut_pct = st.number_input(
                "Water Cut (%)",
                0.0,
                100.0,
                value=d["water_cut_pct"],
                step=1.0,
                key=f"{prefix}_watercut",
            )

            field_maturity = st.selectbox(
                "Field Maturity",
                ["Early", "Mature", "Late"],
                index=1,
                key=f"{prefix}_maturity",
            )

            maturity_factor = st.number_input(
                "Maturity Factor",
                0.0,
                5.0,
                value=d["maturity_factor"],
                step=0.05,
                key=f"{prefix}_maturity_factor",
            )

        with c:
            mobility_ratio = st.selectbox(
                "Mobility Ratio",
                [
                    "Favorable",
                    "Neutral",
                    "Unfavorable",
                ],
                index=0,
                key=f"{prefix}_mobility",
            )

            adsorption_risk = st.selectbox(
                "Surfactant Adsorption Risk",
                ["Low", "Medium", "High"],
                index=0,
                key=f"{prefix}_adsorption",
            )

            water_handling = st.selectbox(
                "Produced Water Handling Complexity",
                ["Low", "Medium", "High"],
                index=0,
                key=f"{prefix}_water_handling",
            )

            offshore = st.selectbox(
                "Offshore Field?",
                ["Yes", "No"],
                index=1,
                key=f"{prefix}_offshore",
            )

    with st.expander(
        "🔁 Injection / WAG / Gas Context",
        expanded=False,
    ):
        a, b, c = st.columns(3)

        with a:
            water_injection_facilities = st.selectbox(
                "Water Injection Facilities",
                ["Yes", "No"],
                index=0,
                key=f"{prefix}_water_fac",
            )

            gas_injection_facilities = st.selectbox(
                "Gas Injection Facilities",
                ["Yes", "No"],
                index=0,
                key=f"{prefix}_gas_fac",
            )

            wag_ratio = st.selectbox(
                "WAG Ratio",
                ["1:1", "2:1", "1:2", "Other"],
                index=0,
                key=f"{prefix}_wag_ratio",
            )

        with b:
            gas_injectivity = st.selectbox(
                "Gas Injectivity",
                ["Good", "Fair", "Poor"],
                index=0,
                key=f"{prefix}_gas_inj",
            )

            water_injectivity = st.selectbox(
                "Water Injectivity",
                ["Good", "Fair", "Poor"],
                index=0,
                key=f"{prefix}_water_inj",
            )

            gravity_override_risk = st.selectbox(
                "Gravity Override Risk",
                ["Low", "Medium", "High"],
                index=0,
                key=f"{prefix}_gravity",
            )

        with c:
            hc_gas_availability = st.selectbox(
                "HC Gas Availability",
                ["Yes", "No"],
                index=1,
                key=f"{prefix}_hc_availability",
            )

            produced_gor_category = st.selectbox(
                "Produced GOR Category",
                ["Low", "Moderate", "High"],
                index=1,
                key=f"{prefix}_gor_category",
            )

            gas_reinjectable = st.selectbox(
                "Produced Gas Reinjectable?",
                ["Yes", "No"],
                index=0,
                key=f"{prefix}_reinjectable",
            )

            produced_gor_scf_stb = st.number_input(
                "Produced GOR (scf/STB)",
                min_value=0.0,
                value=d["produced_gor_scf_stb"],
                step=50.0,
                key=f"{prefix}_gor_numeric",
            )

    values = {
        "depth_ft": depth_ft,
        "temperature_c": temperature_c,
        "visc_cp": visc_cp,
        "api": api,
        "perm_md": perm_md,
        "porosity_frac": porosity_frac,
        "porosity_pct": porosity_frac * 100.0,
        "so_pct": so_pct,
        "salinity_ppm": salinity_ppm,
        "hardness_ppm": hardness_ppm,
        "rock_type": rock_type,
        "net_pay_m": net_pay_m,
        "heterogeneity": heterogeneity,
        "gas_availability": gas_availability,
        "oxygen_present": oxygen_present,
        "ooip_mmstb": ooip_mmstb,
        "base_rf_pct": base_rf_pct,
        "drive_mechanism": drive_mechanism,
        "drive_multiplier": drive_multiplier,
        "co2_availability": co2_availability,
        "mmp_satisfied": mmp_satisfied,
        "waterflood_history": waterflood_history,
        "water_cut_pct": water_cut_pct,
        "field_maturity": field_maturity,
        "maturity_factor": maturity_factor,
        "mobility_ratio": mobility_ratio,
        "adsorption_risk": adsorption_risk,
        "water_handling": water_handling,
        "offshore": offshore,
        "water_injection_facilities": water_injection_facilities,
        "gas_injection_facilities": gas_injection_facilities,
        "wag_ratio": wag_ratio,
        "gas_injectivity": gas_injectivity,
        "water_injectivity": water_injectivity,
        "gravity_override_risk": gravity_override_risk,
        "hc_gas_availability": hc_gas_availability,
        "produced_gor_category": produced_gor_category,
        "gas_reinjectable": gas_reinjectable,
        "produced_gor_scf_stb": produced_gor_scf_stb,
    }

    derived = ExcelScreeningService().prepare_inputs(
        values
    )

    st.caption(
        "HC Gas Source Status = "
        f"**{derived.get('hc_source_status', 'Unavailable')}** · "
        "Numeric GOR Category = "
        f"**{derived.get('gor_category_numeric', '—')}**"
    )

    return values, formation

def build_eor_ml_input(
    values: Dict[str, Any],
    formation: str,
) -> Dict[str, Any]:
    """
    Convert EOR Atlas UI values into the exact range-based
    input schema expected by the production CatBoost model.
    """

    # ============================================================
    # Formation normalization
    # ============================================================

    formation_map = {
        "Sandstone": "Sandstone",
        "Carbonate": "Carbonates",
        "Carbonates": "Carbonates",
        "Unconsolidated sands": "Unconsolidated sands",
    }

    if formation not in formation_map:
        raise ValueError(
            f"Formation '{formation}' is not supported by "
            f"the active CatBoost model. "
            f"Supported formations: "
            f"{list(formation_map.keys())}"
        )

    # ============================================================
    # Actual EOR Intelligence input keys
    # ============================================================

    required_keys = [
        "depth_ft",
        "porosity_pct",
        "perm_md",
        "api",
        "visc_cp",
        "so_pct",
    ]

    missing = [
        key
        for key in required_keys
        if key not in values
    ]

    if missing:
        raise KeyError(
            "Missing EOR Intelligence inputs: "
            f"{missing}. "
            f"Available keys: {list(values.keys())}"
        )

    # ============================================================
    # Read values
    # ============================================================

    depth = float(
        values["depth_ft"]
    )

    porosity = float(
        values["porosity_pct"]
    )

    permeability = float(
        values["perm_md"]
    )

    api = float(
        values["api"]
    )

    viscosity = float(
        values["visc_cp"]
    )

    oil_saturation = float(
        values["so_pct"]
    )

    # ============================================================
    # Basic validation
    # ============================================================

    if depth <= 0:
        raise ValueError(
            "Depth must be greater than zero."
        )

    if not 0 <= porosity <= 100:
        raise ValueError(
            "Porosity must be between 0 and 100%."
        )

    if permeability <= 0:
        raise ValueError(
            "Permeability must be greater than zero."
        )

    if not 0 <= api <= 100:
        raise ValueError(
            "API gravity must be between 0 and 100°."
        )

    if viscosity <= 0:
        raise ValueError(
            "Viscosity must be greater than zero."
        )

    if not 0 <= oil_saturation <= 100:
        raise ValueError(
            "Oil saturation must be between 0 and 100%."
        )

    # ============================================================
    # Build exact production feature-builder input
    #
    # The production model uses range-based inputs.
    # Since the current UI provides a single value, use:
    #
    #     min = max = UI value
    #
    # The feature builder will then generate midpoint/span/log
    # features in the exact order expected by CatBoost.
    # ============================================================

    return {
        "depth_min_ft": depth,
        "depth_max_ft": depth,

        "porosity_min_pct": porosity,
        "porosity_max_pct": porosity,

        "perm_min_md": permeability,
        "perm_max_md": permeability,

        "api_min": api,
        "api_max": api,

        "visc_min_cp": viscosity,
        "visc_max_cp": viscosity,

        "so_min_pct": oil_saturation,
        "so_max_pct": oil_saturation,

        "formation_category": formation_map[formation],
    }

# =============================================================================
# EOR INTELLIGENCE
# =============================================================================
def run_eor_intelligence(
    services: Dict[str, Any],
    values: Dict[str, float],
    formation: str,
) -> Dict[str, Any]:
    """
    Run fuzzy suitability and CatBoost independently.

    Engineering screening remains authoritative for feasibility.
    """

    fuzzy_engine: FuzzyEngine = services[
        "fuzzy_engine"
    ]

    model_service: ModelService = services[
        "model_service"
    ]

    techs_all = list(
        services["techs_all"]
    )

    # ============================================================
    # Fuzzy suitability
    # ============================================================

    fuzzy_scores = fuzzy_engine.evaluate_all(
        techs_all,
        formation,
        values,
    )

    fuzzy_top5 = sorted(
        fuzzy_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]

    # ============================================================
    # CatBoost intelligence
    # ============================================================

    ml_top3 = []
    ml_probabilities = {}

    if model_service.is_loaded():

        ml_input = build_eor_ml_input(
            values,
            formation,
        )

        ml_result = model_service.predict(
            ml_input
        )

        if not ml_result.success:
            raise RuntimeError(
                ml_result.warning
                or "CatBoost prediction failed."
            )

        ml_top3 = ml_result.top_n(3)

        ml_probabilities = {
            candidate.technique: candidate.probability
            for candidate in ml_result.candidates
        }

    # ============================================================
    # Return independent signals
    # ============================================================

    return {
        "formation": formation,
        "fuzzy_scores": fuzzy_scores,
        "fuzzy_top5": fuzzy_top5,
        "ml_available": model_service.is_loaded(),
        "ml_top3": ml_top3,
        "ml_probabilities": ml_probabilities,
    }

def render_eor_intelligence_result(
    result: Dict[str, Any],
) -> None:

    st.subheader(
        "🧠 EOR Intelligence Results"
    )

    st.markdown(
        """
        <div class="intelligence-note">
        <strong>Independent signals:</strong>
        CatBoost provides a data-driven ranking, while fuzzy logic evaluates
        reservoir suitability against EOR envelopes. Neither signal overrides
        deterministic engineering screening.
        </div>
        """,
        unsafe_allow_html=True,
    )


    st.markdown("### 🤖 CatBoost Top 3")

    if result["ml_available"]:

        cols = st.columns(
            len(result["ml_top3"]) or 1
        )

        for col, candidate in zip(
            cols,
            result["ml_top3"],
        ):
            rank = candidate.rank
            technique = candidate.technique
            probability = candidate.probability

            with col:
                st.markdown(
                    f'<div class="top3-card">'
                    f'<div style="font-size:0.72rem;color:#64748b;">'
                    f'RANK {rank}'
                    f'</div>'
                    f'<div style="font-size:1.2rem;font-weight:700;">'
                    f'{technique}'
                    f'</div>'
                    f'<div>'
                    f'CatBoost probability: '
                    f'<strong>{_format_probability(probability)}</strong>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        ml_df = pd.DataFrame(
            [
                {
                    "Rank": candidate.rank,
                    "EOR Technique": candidate.technique,
                    "CatBoost Probability": candidate.probability,
                }
                for candidate in result["ml_top3"]
            ]
        )

        ml_df["CatBoost Probability"] = (
            ml_df["CatBoost Probability"]
            .map(_format_probability)
        )

        st.dataframe(
            ml_df,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.warning(
            "CatBoost model is unavailable."
        )
        
        st.markdown(
            "### 🌐 Fuzzy Suitability Top 5"
        )

        fuzzy_df = pd.DataFrame(
            [
                {
                    "Rank": i,
                    "EOR Technique": technique,
                    "Fuzzy Suitability": round(
                        float(score),
                        3,
                    ),
                }
                for i, (
                    technique,
                    score,
                ) in enumerate(
                    result["fuzzy_top5"],
                    start=1,
                )
            ]
        )

        st.dataframe(
            fuzzy_df,
            use_container_width=True,
            hide_index=True,
        )

        if result["ml_probabilities"]:
            st.markdown(
                "### CatBoost Probability Distribution"
            )

            st.bar_chart(
                pd.Series(
                    result["ml_probabilities"],
                    dtype=float,
                ).sort_values(
                    ascending=False
                )
            )

        st.markdown(
            "### Fuzzy Suitability Distribution"
        )

        if result["fuzzy_top5"]:
            st.bar_chart(
                pd.Series(
                    dict(result["fuzzy_top5"]),
                    dtype=float,
                )
            )

    st.info(
        "No weighted ML/fuzzy ensemble is applied. "
        "Use the deterministic screening result for engineering feasibility."
    )


# =============================================================================
# EOR SCREENING TAB
# =============================================================================

def render_eor_screening_tab() -> None:

    st.header(
        "🔍 EOR Screening"
    )

    st.write(
        "Deterministic reservoir screening only. "
        "This layer does not call CatBoost or fuzzy scoring."
    )

    inputs, formation = render_eor_input_form(
        "screening"
    )

    if st.button(
        "🚀 Run Screening",
        type="primary",
        use_container_width=True,
        key="excel_screening_run",
    ):
        try:
            result = ExcelScreeningService().screen(
                inputs,
                formation,
            )

            st.session_state[
                "excel_screening_result"
            ] = result

        except Exception:
            logger.exception(
                "EOR Screening failed."
            )
            st.error(
                "The deterministic screening could not be completed."
            )

    result = st.session_state.get(
        "excel_screening_result"
    )

    if result:
        st.success(
            "✅ EOR Screening completed"
        )
        render_excel_screening_result(
            result
        )

    with st.expander(
        "Workbook source / diagnostic",
        expanded=False,
    ):
        st.write(
            f"Workbook: `{settings.workbook_path}`"
        )
        st.write(
            "Executable worksheet: `Screening`"
        )
        st.write(
            "Input source: `InputData!B4:B44`"
        )
        st.write(
            "Output source: `Screening!B2:I14`"
        )


# =============================================================================
# OTHER DASHBOARD SECTIONS
# =============================================================================

def render_executive_overview_section():
    st.header("🏠 Executive Overview")

    metrics = [
        ("Fields", 41),
        ("Reservoirs", 600),
        ("EOR Families", 9),
        ("Historical Studies", 128),
        ("RF Gap (MMstb)", 1.31),
        ("Candidates", 18),
    ]

    cols = st.columns(6)

    for col, (
        label,
        value,
    ) in zip(
        cols,
        metrics,
    ):
        with col:
            st.markdown(
                f"""
                <div class="exec-kpi-card">
                    <div class="exec-kpi-label">{label}</div>
                    <div class="exec-kpi-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    map_df = pd.DataFrame(
        {
            "Field": [
                "Angsi",
                "Barton",
                "Dulang",
                "Tapis",
                "Baram",
            ],
            "Latitude": [
                4.3,
                4.1,
                3.9,
                3.8,
                5.0,
            ],
            "Longitude": [
                103.1,
                103.3,
                103.6,
                103.2,
                112.0,
            ],
            "EOR_Status": [
                "Candidate",
                "Multiple",
                "Historical",
                "Candidate",
                "Historical",
            ],
            "RF_Gap": [
                120,
                95,
                80,
                66,
                105,
            ],
        }
    )

    st.subheader(
        "Field Opportunity Map"
    )

    if pdk is not None:
        st.pydeck_chart(
            pdk.Deck(
                initial_view_state=pdk.ViewState(
                    latitude=4.3,
                    longitude=103.4,
                    zoom=5,
                    pitch=30,
                ),
                layers=[
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=map_df,
                        get_position=(
                            "[Longitude, Latitude]"
                        ),
                        get_color=[
                            255,
                            120,
                            60,
                            200,
                        ],
                        get_radius="RF_Gap",
                        pickable=True,
                    )
                ],
            )
        )
    else:
        st.map(
            map_df[
                [
                    "Latitude",
                    "Longitude",
                ]
            ]
        )

    st.dataframe(
        map_df,
        use_container_width=True,
        hide_index=True,
    )


def render_field_candidates_section():
    st.header(
        "🗺️ Field / Reservoir Candidates"
    )

    df = pd.DataFrame(
        {
            "Field": [
                "Angsi",
                "Dulang",
                "Barton",
                "Baram",
                "Tapis",
                "Penara",
            ],
            "Reservoir": [
                "A12",
                "E14",
                "B7",
                "E10",
                "N12",
                "P1",
            ],
            "Temperature_C": [
                85,
                93,
                72,
                108,
                80,
                66,
            ],
            "EUR_MMstb": [
                68,
                52,
                41,
                88,
                54,
                34,
            ],
            "RF_Gap": [
                20,
                18,
                15,
                24,
                17,
                12,
            ],
            "Permeability_mD": [
                120,
                160,
                80,
                180,
                110,
                90,
            ],
            "Method": [
                "CO2 WAG",
                "Polymer",
                "ASP",
                "CO2 WAG",
                "Polymer",
                "Steam",
            ],
        }
    )

    st.subheader(
        "Candidate Reservoir Scatter"
    )
    st.bar_chart(
        df.set_index("Field")[
            "EUR_MMstb"
        ]
    )

    st.subheader(
        "Opportunity Rank"
    )
    st.bar_chart(
        df.set_index("Field")[
            "RF_Gap"
        ]
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def render_fluid_fluid_section():
    st.header(
        "🧪 CEOR — Fluid / Fluid"
    )

    rheology = pd.DataFrame(
        {
            "Shear_Rate": [10, 30, 50, 100, 200],
            "Polymer_A": [120, 90, 75, 58, 44],
            "Polymer_B": [132, 104, 82, 64, 49],
            "Polymer_C": [110, 88, 70, 54, 41],
        }
    ).set_index(
        "Shear_Rate"
    )

    st.subheader(
        "Rheology"
    )
    st.line_chart(
        rheology
    )

    thermal = pd.DataFrame(
        {
            "Time_Days": [0, 7, 14, 30, 60],
            "Retention_A": [100, 96, 90, 84, 79],
            "Retention_B": [100, 92, 85, 75, 68],
        }
    ).set_index(
        "Time_Days"
    )

    st.subheader(
        "Thermal Stability"
    )
    st.line_chart(
        thermal
    )

    phase = pd.DataFrame(
        {
            "Formulation": ["A-1", "A-2", "B-1", "B-2", "C-1"],
            "No_Precipitation": [82, 70, 65, 91, 76],
            "Precipitation": [18, 30, 35, 9, 24],
        }
    )

    st.subheader(
        "Phase Behaviour"
    )
    st.bar_chart(
        phase.set_index("Formulation")
    )

    ift = pd.DataFrame(
        {
            "Formulation": ["F1", "F2", "F3", "F4"],
            "IFT": [0.022, 0.010, 0.040, 0.013],
        }
    )

    st.subheader(
        "IFT Comparison"
    )
    st.bar_chart(
        ift.set_index("Formulation")
    )


def render_fluid_rock_section():
    st.header(
        "🪨 CEOR — Fluid / Rock"
    )

    adsorption = pd.DataFrame(
        {
            "Days": [0, 7, 14, 30, 60],
            "Adsorption_Surf_A": [0.0, 0.18, 0.27, 0.35, 0.42],
            "Adsorption_Surf_B": [0.0, 0.12, 0.20, 0.28, 0.31],
        }
    ).set_index("Days")

    st.subheader(
        "Adsorption vs Time"
    )
    st.line_chart(
        adsorption
    )

    coreflood = pd.DataFrame(
        {
            "Core": ["Core 1", "Core 2", "Core 3", "Core 4"],
            "Waterflood": [42, 38, 45, 41],
            "EOR_Increment": [15, 18, 11, 14],
        }
    )

    st.subheader(
        "Core Flood Incremental Recovery"
    )
    st.bar_chart(
        coreflood.set_index("Core")
    )

    sor = pd.DataFrame(
        {
            "Core": ["Core 1", "Core 2", "Core 3", "Core 4"],
            "Sor_Reduction": [36, 28, 41, 31],
        }
    )

    st.subheader(
        "Sor Reduction"
    )
    st.bar_chart(
        sor.set_index("Core")
    )


def render_challenges_section():
    st.header(
        "⚠️ Challenges & Lessons Learnt"
    )

    df = pd.DataFrame(
        {
            "Field": ["Angsi", "Dulang", "Barton", "Baram"],
            "Chemical_Compatibility": ["High", "Medium", "Low", "High"],
            "Facilities": ["Medium", "Low", "High", "Medium"],
            "Fluid_Handling": ["High", "Medium", "Medium", "Low"],
            "Cost_Logistics": ["High", "Medium", "Low", "High"],
        }
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    dist = pd.DataFrame(
        {
            "Challenge": [
                "Chemical compatibility",
                "Facilities",
                "Fluid handling",
                "Cost / logistics",
                "Risk / uncertainty",
            ],
            "Count": [4, 3, 3, 2, 2],
        }
    )

    st.subheader(
        "Challenge Distribution"
    )
    st.bar_chart(
        dist.set_index("Challenge")
    )


def render_database_summary_section():
    st.subheader(
        "📊 Platform Overview"
    )

    try:
        recent = (
            RepositoryFactory
            .screening_repo()
            .get_recent(days=30)
        )
    except Exception as exc:
        logger.warning(
            "Database summary unavailable: %s",
            exc,
        )
        recent = None

    cols = st.columns(4)

    cols[0].metric(
        "Recent Runs",
        len(recent) if recent is not None else "N/A",
    )
    cols[1].metric(
        "Model Status",
        "Ready" if settings.validate_paths().get("model") else "Missing",
    )
    cols[2].metric(
        "Workbook",
        "Loaded" if settings.validate_paths().get("workbook") else "Missing",
    )
    cols[3].metric(
        "Environment",
        settings.environment.upper(),
    )

    if recent:
        rows = [
            {
                "Time": (
                    run.timestamp.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if run.timestamp else "N/A"
                ),
                "Formation": run.formation,
                "Recommendation": run.recommended_technique or "N/A",
                "Score": run.recommendation_score,
            }
            for run in recent[:10]
        ]

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No recent screening records available."
        )


def render_model_registry_section():
    st.subheader(
        "🧠 Model Registry"
    )

    try:
        versions = (
            RepositoryFactory
            .model_version_repo()
            .list_versions()
        )
    except Exception as exc:
        logger.warning(
            "Model registry unavailable: %s",
            exc,
        )
        versions = None

    if not versions:
        st.info(
            "No registered model versions available."
        )
        return

    rows = []

    for version in versions:
        rows.append(
            {
                "Version": version.version,
                "Algorithm": version.algorithm,
                "Framework": version.framework,
                "Accuracy": version.test_accuracy,
                "Weighted F1": version.test_weighted_f1,
                "Training Date": (
                    version.training_date.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if version.training_date
                    else "N/A"
                ),
                "Active": (
                    "Yes"
                    if version.is_active
                    else "No"
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


def render_saved_run_detail_section():
    st.subheader(
        "🧾 Saved Run Detail & Comparison"
    )

    try:
        history = (
            RepositoryFactory
            .screening_repo()
            .get_recent(days=365)
        )
    except Exception as exc:
        logger.warning(
            "Historical screening data unavailable: %s",
            exc,
        )
        history = None

    if not history:
        st.info(
            "No saved screening runs available."
        )
        return

    run_ids = [
        run.id for run in history
    ]

    selected_id = st.selectbox(
        "Select a saved run",
        run_ids,
        key="saved_run_detail",
    )

    selected = next(
        (
            run for run in history
            if run.id == selected_id
        ),
        None,
    )

    if selected is None:
        return

    left, right = st.columns(2)

    with left:
        st.write(
            f"**Run ID:** {selected.id}"
        )
        st.write(
            f"**Timestamp:** {selected.timestamp}"
        )
        st.write(
            f"**Formation:** {selected.formation}"
        )
        st.write(
            f"**Recommendation:** {selected.recommended_technique or 'N/A'}"
        )

    with right:
        st.write(
            f"**Status:** {selected.recommendation_status or 'N/A'}"
        )
        st.write(
            f"**Score:** {selected.recommendation_score}"
        )
        st.write(
            f"**Model Version:** {selected.model_version or 'N/A'}"
        )
        st.write(
            f"**Data Readiness:** {selected.data_readiness_pct or 'N/A'}%"
        )

    if selected.input_payload:
        st.write(
            "**Exact input values:**"
        )
        st.dataframe(
            pd.DataFrame(
                [selected.input_payload]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if selected.rule_trace:
        with st.expander(
            "Structured rule trace"
        ):
            st.json(
                selected.rule_trace
            )

    if selected.assumptions:
        with st.expander(
            "Recorded assumptions"
        ):
            st.json(
                selected.assumptions
            )


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar_status(
    services: Dict[str, Any],
):
    path_status = settings.validate_paths()

    model_ready = bool(
        services.get("model_loaded")
    )
    workbook_ready = bool(
        path_status.get("workbook")
    )
    config_ready = bool(
        path_status.get("config")
    )

    st.sidebar.header(
        "Operational Status"
    )

    st.sidebar.markdown(
        f"""
        <div class="status-box">
            <div class="status-row">
                <span>CatBoost Model</span>
                <span class="status-pill {"ready" if model_ready else "warn"}">
                    {"Ready" if model_ready else "Unavailable"}
                </span>
            </div>
            <div class="status-row">
                <span>Workbook</span>
                <span class="status-pill {"ready" if workbook_ready else "warn"}">
                    {"Loaded" if workbook_ready else "Missing"}
                </span>
            </div>
            <div class="status-row">
                <span>ML Config</span>
                <span class="status-pill {"ready" if config_ready else "warn"}">
                    {"Valid" if config_ready else "Check"}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.caption(
        "Decision stack"
    )
    st.sidebar.write(
        "• Deterministic Excel screening"
    )
    st.sidebar.write(
        "• Fuzzy envelope suitability"
    )
    st.sidebar.write(
        "• CatBoost ML ranking"
    )


# =============================================================================
# MAIN
# =============================================================================

def main():

    st.title(
        "🛢️ EOR Atlas – Decision Support Platform"
    )

    st.caption(
        "Engineering-first EOR dashboard with deterministic screening, "
        "independent fuzzy suitability, and CatBoost intelligence."
    )

    services = initialize_services()

    if services is None:
        st.error(
            "EOR Atlas services failed to initialize."
        )
        return

    render_sidebar_status(
        services
    )

    tabs = st.tabs(
        [
            "🏠 Executive Overview",
            "🔍 EOR Screening",
            "🗺️ Field / Reservoir Candidates",
            "🧪 CEOR — Fluid / Fluid",
            "🪨 CEOR — Fluid / Rock",
            "📚 Past EOR Results",
            "⚠️ Challenges & Lessons",
            "🤖 EOR Intelligence",
        ]
    )

    with tabs[0]:
        render_executive_overview_section()

    with tabs[1]:
        render_eor_screening_tab()

    with tabs[2]:
        render_field_candidates_section()

    with tabs[3]:
        render_fluid_fluid_section()

    with tabs[4]:
        render_fluid_rock_section()

    with tabs[5]:
        st.header(
            "📚 Past EOR Results"
        )
        render_database_summary_section()
        st.divider()
        render_saved_run_detail_section()

    with tabs[6]:
        render_challenges_section()

    with tabs[7]:
        st.header(
            "🤖 EOR Intelligence"
        )

        st.write(
            "Uses the same reservoir inputs as EOR Screening. "
            "CatBoost and fuzzy suitability are independent signals."
        )

        inputs, formation = render_eor_input_form(
            "intel"
        )

        if st.button(
            "🧠 Run EOR Intelligence",
            type="primary",
            use_container_width=True,
            key="run_eor_intelligence",
        ):

            ml_values = {
                "depth_ft": inputs["depth_ft"],
                "porosity_pct": inputs["porosity_pct"],
                "perm_md": inputs["perm_md"],
                "api": inputs["api"],
                "visc_cp": inputs["visc_cp"],
                "so_pct": inputs["so_pct"],
            }

            with st.spinner(
                "Running fuzzy and CatBoost intelligence..."
            ):
                try:
                    result = run_eor_intelligence(
                        services,
                        ml_values,
                        formation,
                    )

                    st.session_state[
                        "eor_intelligence_result"
                    ] = result

                except Exception:
                    logger.exception(
                        "EOR Intelligence execution failed."
                    )
                    st.error(
                        "EOR Intelligence could not complete."
                    )

        result = st.session_state.get(
            "eor_intelligence_result"
        )

        if result:
            render_eor_intelligence_result(
                result
            )

            st.divider()

            model_service = services[
                "model_service"
            ]

            if model_service.is_loaded():
                with st.expander(
                    "🔧 CatBoost Model Information",
                    expanded=False,
                ):
                    st.json(
                        model_service.get_model_info()
                    )

            st.divider()
            render_model_registry_section()


if __name__ == "__main__":
    main()
