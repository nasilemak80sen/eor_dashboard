"""
EOR Atlas – Enhanced Oil Recovery Screening & Decision Support Platform

Main Streamlit application.

Important architecture:
1. EOR Screening
   - Stand-alone deterministic screening driven by:
       EOR_Screening_Tool_2026.xlsx
       sheet: "Screening Tool"
   - Does NOT call the ML model.
   - Does NOT call the fuzzy engine.

2. EOR Intelligence
   - Uses the same screening inputs.
   - Runs fuzzy-envelope evaluation + neural-network inference.
   - Presents the TOP 3 EOR techniques predicted by the NN.
   - Does not replace the stand-alone Excel screening result.

The remaining dashboard tabs intentionally retain the existing UI/data
presentation structure.
"""

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import streamlit as st

try:
    import pydeck as pdk
except Exception:  # pragma: no cover - optional dependency
    pdk = None


# =============================================================================
# EXISTING APPLICATION SERVICES
# =============================================================================

from EORWEBDEV.src.tests.settings import settings
from utils.logging_config import logger
from utils.validators import InputValidator
from domain.fuzzy_engine import FuzzyEngine
from domain.rule_engine import EligibilityStatus
from EORWEBDEV.src.tests.model_service import ModelService
from data.repositories import EnvelopeRepository, WorkbookRepository
from data.queries import RepositoryFactory


# =============================================================================
# CONSTANTS
# =============================================================================

SCREENING_TOOL_SHEET = "Screening"

# Exact InputData row mapping from EOR_Screening_Tool_2026.xlsx.
# B4:B44 are the executable screening inputs/helpers used by Screening!B2:I14.
INPUT_LABELS = {
    "depth_ft": "Depth (ft)",
    "reservoir_pressure": "Reservoir Pressure (psia)",
    "temperature_c": "Temperature (°C)",
    "visc_cp": "Oil Viscosity (cP)",
    "api": "API Gravity (°API)",
    "perm_md": "Permeability (mD)",
    "porosity_frac": "Porosity (fraction)",
    "salinity_ppm": "Salinity / TDS (ppm)",
    "hardness_ppm": "Hardness Ca²⁺+Mg²⁺ (ppm)",
    "rock_type": "Rock Type",
    "net_pay_m": "Net Pay (m)",
    "heterogeneity": "Heterogeneity",
    "gas_availability": "Gas Availability",
    "oxygen_present": "Oxygen Present in Polymer System",
    "ooip_mmstb": "OOIP (MMstb)",
    "base_rf_pct": "Base RF without EOR (%)",
    "drive_mechanism": "Drive Mechanism",
    "drive_multiplier": "Drive Mech Multiplier",
    "co2_availability": "CO2 Availability",
    "mmp_satisfied": "MMP Satisfied?",
    "waterflood_history": "Waterflood History",
    "water_cut_pct": "Water Cut (%)",
    "field_maturity": "Field Maturity",
    "maturity_factor": "Maturity Factor",
    "mobility_ratio": "Mobility Ratio",
    "adsorption_risk": "Surfactant Adsorption Risk",
    "water_handling": "Produced Water Handling Complexity",
    "offshore": "Offshore Field?",
    "water_injection_facilities": "Water Injection Facilities",
    "gas_injection_facilities": "Gas Injection Facilities",
    "wag_ratio": "WAG Ratio",
    "gas_injectivity": "Gas Injectivity",
    "water_injectivity": "Water Injectivity",
    "gravity_override_risk": "Gravity Override Risk",
    "hc_gas_availability": "HC Gas Availability",
    "produced_gor_category": "Produced GOR Category",
    "gas_reinjectable": "Produced Gas Reinjectable?",
    "hc_source_status": "HC Gas Source Status (derived)",
    "produced_gor_scf_stb": "Produced GOR (scf/STB)",
    "gor_category_numeric": "GOR Category from Numeric (derived)",
}

# Workbook does not store an initial formula result for B22/B28; 1.0 is the
# neutral multiplier and mirrors the default screening case.
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


EOR_STATUS_COLORS = {
    "Candidate": [255, 120, 60, 210],
    "Multiple": [60, 120, 220, 210],
    "Historical": [120, 120, 120, 160],
    "Screened": [40, 160, 110, 200],
    "Unknown": [150, 150, 150, 150],
}


# =============================================================================
# STREAMLIT CONFIGURATION
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

    .stAlert > div {
        border-radius: 12px;
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

    .metric-card {
        background: linear-gradient(135deg, #0f172a, #1e293b);
        padding: 0.8rem 1rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 0.75rem;
    }

    .exec-kpi-card {
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.8rem;
        min-height: 110px;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.15);
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
        line-height: 1.2;
    }

    .sidebar-status-box {
        background: rgba(15, 23, 42, 0.04);
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 12px;
        padding: 0.75rem;
    }

    .status-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.5rem;
        margin: 0.35rem 0;
        font-size: 0.88rem;
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.18rem 0.5rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
    }

    .status-pill.ready {
        background: rgba(22, 163, 74, 0.12);
        color: #166534;
    }

    .status-pill.warn {
        background: rgba(245, 158, 11, 0.12);
        color: #b45309;
    }

    .top3-card {
        border: 1px solid rgba(15, 23, 42, 0.10);
        border-radius: 14px;
        padding: 1rem;
        background: rgba(248, 250, 252, 0.8);
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# GENERIC HELPERS
# =============================================================================

def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float."""
    if value is None:
        return default

    if isinstance(value, str) and not value.strip():
        return default

    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    if not np.isfinite(result):
        return default

    return result


def _normalise_text(value: Any) -> str:
    """Normalise text for flexible column matching."""
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = text.replace("_", " ")
    text = text.replace("-", " ")
    text = " ".join(text.split())
    return text


def _first_existing_column(
    df: pd.DataFrame,
    aliases: Sequence[str],
) -> Optional[str]:
    """Return a dataframe column matching one of the aliases."""
    mapping = {
        _normalise_text(column): column
        for column in df.columns
    }

    for alias in aliases:
        actual = mapping.get(_normalise_text(alias))
        if actual is not None:
            return actual

    return None


def _format_probability(value: Optional[float]) -> str:
    """Format either [0,1] probability or [0,100] percentage."""
    if value is None:
        return "N/A"

    return f"{value:.0%}" if abs(value) <= 1 else f"{value:.1f}%"


def _format_score(value: Optional[float]) -> str:
    """Format a 0-1 score."""
    if value is None:
        return "N/A"
    return f"{value:.3f}"


# =============================================================================
# SERVICE INITIALIZATION
# =============================================================================

@st.cache_resource
def initialize_services() -> Optional[Dict[str, Any]]:
    """
    Initialize reusable data/ML services.

    Deliberately does NOT instantiate ScreeningEngine because EOR Screening
    must remain stand-alone and Excel-driven.
    """
    logger.info("Initializing EOR Atlas services...")

    try:
        env, techs_all = EnvelopeRepository.load_envelopes()
        workbook_sheets = WorkbookRepository.load_workbook()

        fuzzy_engine = FuzzyEngine(
            env,
            alpha=settings.fuzzy_alpha,
        )

        model_service = ModelService()
        model_loaded = model_service.load()

        if not model_service.load():
            logger.warning(
                "ML model failed to load. EOR Intelligence will run "
                "with fuzzy information only."
            )

        return {
            "fuzzy_engine": fuzzy_engine,
            "model_service": model_service,
            "env": env,
            "techs_all": techs_all,
            "workbook_sheets": workbook_sheets,
            "model_loaded":model_loaded,
        }

    except Exception:
        logger.exception("Failed to initialize EOR Atlas services")
        st.error(
            "Application services could not be initialized. "
            "Check the configured workbook, fuzzy data and model artifacts."
        )
        return None


# =============================================================================
# EXCEL SCREENING TOOL — WORKBOOK-PARITY IMPLEMENTATION
# =============================================================================

class ExcelScreeningService:
    """
    Deterministic Python implementation of the executable Screening sheet.

    The workbook is the specification. The formulas in Screening!B2:I14 have
    been transcribed explicitly so the Streamlit result does not depend on
    fuzzy logic or neural-network inference.
    """

    METHODS = [
        ("CO2 Miscible Flood", 15.0),
        ("CO2 WAG", 18.0),
        ("HC Gas Miscible Flood", 14.0),
        ("HC Gas WAG", 17.0),
        ("Immiscible Gas Flood", 8.0),
        ("Immiscible Gas WAG", 12.0),
        ("Polymer (HPAM)", 10.0),
        ("Polymer (ATBS)", 12.0),
        ("SP", 15.0),
        ("ASP", 20.0),
        ("CSS", 15.0),
        ("Steam Flood", 18.0),
        ("ISC", 10.0),
    ]

    @staticmethod
    def _yes(value: Any) -> bool:
        return _normalise_text(value) == "yes"

    @staticmethod
    def _no(value: Any) -> bool:
        return _normalise_text(value) == "no"

    @staticmethod
    def _eq(value: Any, text: str) -> bool:
        return _normalise_text(value) == _normalise_text(text)

    @staticmethod
    def _in(value: Any, options: Sequence[str]) -> bool:
        return _normalise_text(value) in {_normalise_text(x) for x in options}

    @staticmethod
    def _gor_category(gor: Optional[float]) -> str:
        if gor is None:
            return ""
        if gor >= 1000:
            return "High"
        if gor >= 300:
            return "Moderate"
        return "Low"

    def prepare_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        values = dict(inputs)
        gor_num = _safe_float(values.get("produced_gor_scf_stb"))
        numeric_cat = self._gor_category(gor_num)

        if numeric_cat:
            values["gor_category_numeric"] = numeric_cat

        external_hc = self._yes(values.get("hc_gas_availability"))
        direct_gas = self._yes(values.get("gas_availability"))
        reinjectable = self._yes(values.get("gas_reinjectable"))
        cat = values.get("produced_gor_category") or numeric_cat
        cat = str(cat).strip()
        high_or_mod = self._in(cat, ["High", "Moderate"]) or self._in(
            numeric_cat, ["High", "Moderate"]
        )

        # InputData B42 helper logic per UserGuide: external source is
        # Available; high/moderate GOR + reinjection is Conditional; else Unavailable.
        if external_hc:
            values["hc_source_status"] = "Available"
        elif (not direct_gas) and high_or_mod and reinjectable:
            values["hc_source_status"] = "Conditional"
        else:
            values["hc_source_status"] = "Unavailable"

        # Where numeric GOR is present, use it as the helper category; otherwise
        # the user-entered category is retained.
        if numeric_cat:
            values["produced_gor_category"] = numeric_cat

        return values

    @staticmethod
    def _result(
        technique: str,
        critical_fail: bool,
        causes: List[str],
        score: float,
        max_incremental_rf: float,
        values: Dict[str, Any],
        conditional_causes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        conditional_causes = conditional_causes or []
        all_causes = list(causes) + list(conditional_causes)
        if critical_fail:
            status = "FAIL (critical)"
            suitability = "Not suitable"
            score = 0.0
            delta_rf = 0.0
        else:
            status = "CONDITIONAL" if conditional_causes else "PASS"
            if status == "CONDITIONAL":
                suitability = "Potentially suitable" if score >= 50 else "Marginal"
            elif score >= 80:
                suitability = "Highly suitable"
            elif score >= 50:
                suitability = "Potentially suitable"
            else:
                suitability = "Marginal"
            delta_rf = (score / 100.0) * max_incremental_rf

        drive = _safe_float(values.get("drive_multiplier"), 1.0) or 1.0
        maturity = _safe_float(values.get("maturity_factor"), 1.0) or 1.0
        delta_rf *= drive * maturity
        final_rf = (_safe_float(values.get("base_rf_pct"), 0.0) or 0.0) + delta_rf
        ooip = _safe_float(values.get("ooip_mmstb"), 0.0) or 0.0
        eur = ooip * final_rf / 100.0

        return {
            "EOR Technique": technique,
            "Critical Fail": bool(critical_fail),
            "Cause of Fail/Pass": "; ".join(all_causes) if all_causes else "All critical criteria passed",
            "Score (%)": float(score),
            "Status": status,
            "Suitability": suitability,
            "ΔRF_EOR (%)": float(delta_rf),
            "Final RF (%)": float(final_rf),
            "EUR (MMstb)": float(eur),
        }

    def screen(self, raw_inputs: Dict[str, Any], formation: str) -> Dict[str, Any]:
        v = self.prepare_inputs(raw_inputs)
        api = _safe_float(v.get("api"), 0.0) or 0.0
        visc = _safe_float(v.get("visc_cp"), 0.0) or 0.0
        depth = _safe_float(v.get("depth_ft"), 0.0) or 0.0
        temp = _safe_float(v.get("temperature_c"), 0.0) or 0.0
        perm = _safe_float(v.get("perm_md"), 0.0) or 0.0
        tds = _safe_float(v.get("salinity_ppm"), 0.0) or 0.0
        hardness = _safe_float(v.get("hardness_ppm"), 0.0) or 0.0
        water_cut = _safe_float(v.get("water_cut_pct"), 0.0) or 0.0
        gor = _safe_float(v.get("produced_gor_scf_stb"))
        gor_cat = str(v.get("produced_gor_category") or "")
        numeric_gor_cat = str(v.get("gor_category_numeric") or "")
        gor_high = self._eq(gor_cat, "High") or self._eq(numeric_gor_cat, "High")
        gor_mod = self._eq(gor_cat, "Moderate") or self._eq(numeric_gor_cat, "Moderate")
        gor_weight = 1.0 if gor_high else (0.5 if gor_mod else 0.0)
        hc_source_ok = self._in(v.get("hc_source_status"), ["Available", "Conditional"]) or self._yes(v.get("hc_gas_availability"))
        gas_source_ok = self._yes(v.get("gas_availability")) or hc_source_ok
        water_fac = self._yes(v.get("water_injection_facilities"))
        gas_fac = self._yes(v.get("gas_injection_facilities"))
        gas_inj = self._in(v.get("gas_injectivity"), ["Good", "Fair"])
        water_inj = self._in(v.get("water_injectivity"), ["Good", "Fair"])
        mobility_ok = self._in(v.get("mobility_ratio"), ["Favorable", "Neutral"])
        waterflood = self._yes(v.get("waterflood_history"))
        gravity_ok = self._in(v.get("gravity_override_risk"), ["Low", "Medium"])
        gravity_high = self._eq(v.get("gravity_override_risk"), "High")
        source_conditional = (
            (not self._yes(v.get("hc_gas_availability")))
            and (gor_high or gor_mod)
            and self._yes(v.get("gas_reinjectable"))
        )

        results: List[Dict[str, Any]] = []

        # Row 2 — CO2 Miscible Flood.
        causes = []
        for condition, message in [
            (api < 25, "API <25°"),
            (visc > 10, "Viscosity >10 cP"),
            (depth < 2500, "Depth <2500 ft"),
            (not self._yes(v.get("co2_availability")), "CO2 unavailable"),
            (not self._yes(v.get("mmp_satisfied")), "MMP not satisfied"),
        ]:
            if condition: causes.append(message)
        score = 100 * sum([
            api >= 25, visc <= 10, depth >= 2500,
            self._yes(v.get("co2_availability")), self._yes(v.get("mmp_satisfied")),
            waterflood, mobility_ok,
        ]) / 7
        results.append(self._result("CO2 Miscible Flood", bool(causes), causes, score, 15, v))

        # Row 3 — CO2 WAG.
        causes, cond = [], []
        for condition, message in [
            (api < 25, "API <25°"), (visc > 10, "Viscosity >10 cP"),
            (not self._yes(v.get("co2_availability")), "CO2 unavailable"),
            (not self._yes(v.get("mmp_satisfied")), "MMP not satisfied"),
            (not water_fac, "Water injection facilities unavailable"),
            (not gas_fac, "Gas injection facilities unavailable"),
        ]:
            if condition: causes.append(message)
        if gravity_high: cond.append("Conditional: gravity override risk high")
        score = 100 * sum([
            api >= 25, visc <= 10, self._yes(v.get("co2_availability")),
            self._yes(v.get("mmp_satisfied")), water_fac, gas_fac,
            waterflood, gas_inj, water_inj, gravity_ok,
        ]) / 10
        results.append(self._result("CO2 WAG", bool(causes), causes, score, 18, v, cond))

        # Row 4 — HC Gas Miscible Flood.
        causes, cond = [], []
        for condition, message in [
            (api < 25, "API <25°"), (visc > 10, "Viscosity >10 cP"),
            (depth < 2500, "Depth <2500 ft"),
            (not self._yes(v.get("mmp_satisfied")), "MMP not satisfied"),
            (not hc_source_ok, "HC gas source unavailable"),
        ]:
            if condition: causes.append(message)
        if source_conditional: cond.append("Conditional: produced GOR supports HC gas reinjection/recycling")
        score = 100 * sum([
            api >= 25, visc <= 10, depth >= 2500,
            self._yes(v.get("mmp_satisfied")), hc_source_ok, waterflood,
            mobility_ok, gor_weight,
        ]) / 8
        results.append(self._result("HC Gas Miscible Flood", bool(causes), causes, score, 14, v, cond))

        # Row 5 — HC Gas WAG.
        causes, cond = [], []
        for condition, message in [
            (api < 25, "API <25°"), (visc > 10, "Viscosity >10 cP"),
            (not self._yes(v.get("mmp_satisfied")), "MMP not satisfied"),
            (not hc_source_ok, "HC gas source unavailable"),
            (not water_fac, "Water injection facilities unavailable"),
            (not gas_fac, "Gas injection facilities unavailable"),
        ]:
            if condition: causes.append(message)
        if source_conditional: cond.append("Conditional: produced GOR supports HC gas reinjection/recycling")
        if gravity_high: cond.append("Conditional: gravity override risk high")
        score = 100 * sum([
            api >= 25, visc <= 10, self._yes(v.get("mmp_satisfied")), hc_source_ok,
            water_fac, gas_fac, waterflood, gas_inj, water_inj, gravity_ok, gor_weight,
        ]) / 11
        results.append(self._result("HC Gas WAG", bool(causes), causes, score, 17, v, cond))

        # Row 6 — Immiscible Gas Flood.
        causes, cond = [], []
        for condition, message in [
            (api < 15, "API <15°"), (visc > 35, "Viscosity >35 cP"),
            (not gas_source_ok, "Gas source unavailable"),
        ]:
            if condition: causes.append(message)
        if source_conditional: cond.append("Conditional: produced GOR supports gas recycling")
        score = 100 * sum([
            api >= 15, visc <= 35, gas_source_ok, waterflood, mobility_ok, gor_weight,
        ]) / 6
        results.append(self._result("Immiscible Gas Flood", bool(causes), causes, score, 8, v, cond))

        # Row 7 — Immiscible Gas WAG.
        causes, cond = [], []
        for condition, message in [
            (api < 15, "API <15°"), (visc > 35, "Viscosity >35 cP"),
            (not gas_source_ok, "Gas source unavailable"),
            (not water_fac, "Water injection facilities unavailable"),
            (not gas_fac, "Gas injection facilities unavailable"),
        ]:
            if condition: causes.append(message)
        if source_conditional: cond.append("Conditional: produced GOR supports gas recycling")
        if gravity_high: cond.append("Conditional: gravity override risk high")
        score = 100 * sum([
            api >= 15, visc <= 35, gas_source_ok, waterflood,
            water_fac, gas_fac, gas_inj, water_inj, gravity_ok, gor_weight,
        ]) / 10
        results.append(self._result("Immiscible Gas WAG", bool(causes), causes, score, 12, v, cond))

        # Row 8 — Polymer (HPAM).
        causes = []
        for condition, message in [
            (temp > 70, "Temperature >70°C"), (tds > 70000, "TDS >70,000 ppm"),
            (hardness > 500, "Hardness >500 ppm"), (perm < 50, "Permeability <50 mD"),
            (self._yes(v.get("oxygen_present")), "Oxygen present in polymer system"),
        ]:
            if condition: causes.append(message)
        score = 100 * sum([
            temp <= 70, tds <= 70000, hardness <= 500, perm >= 50,
            not self._yes(v.get("oxygen_present")), water_cut >= 50, mobility_ok,
        ]) / 7
        results.append(self._result("Polymer (HPAM)", bool(causes), causes, score, 10, v))

        # Row 9 — Polymer (ATBS).
        causes = []
        for condition, message in [
            (temp > 120, "Temperature >120°C"), (tds > 250000, "TDS >250,000 ppm"),
            (hardness > 5000, "Hardness >5,000 ppm"), (perm < 30, "Permeability <30 mD"),
            (self._yes(v.get("oxygen_present")), "Oxygen present in polymer system"),
        ]:
            if condition: causes.append(message)
        score = 100 * sum([
            temp <= 120, tds <= 250000, hardness <= 5000, perm >= 30,
            not self._yes(v.get("oxygen_present")), water_cut >= 50, mobility_ok,
        ]) / 7
        results.append(self._result("Polymer (ATBS)", bool(causes), causes, score, 12, v))

        # Row 10 — SP.
        causes = []
        for condition, message in [
            (api < 20, "API <20°"), (visc > 35, "Viscosity >35 cP"),
            (temp > 100, "Temperature >100°C"), (tds > 100000, "TDS >100,000 ppm"),
            (self._eq(v.get("adsorption_risk"), "High"), "Surfactant adsorption risk high"),
            (self._eq(v.get("water_handling"), "High"), "Produced-water handling complexity high"),
        ]:
            if condition: causes.append(message)
        score = 100 * sum([
            api >= 20, visc <= 35, temp <= 100, tds <= 100000,
            self._in(v.get("adsorption_risk"), ["Low", "Medium"]),
            self._in(v.get("water_handling"), ["Low", "Medium"]),
            self._in(v.get("rock_type"), ["Sandstone", "Carbonate", "Carbonates"]),
            water_cut >= 50,
        ]) / 8
        results.append(self._result("SP", bool(causes), causes, score, 15, v))

        # Row 11 — ASP.
        causes = []
        for condition, message in [
            (api < 22, "API <22°"), (visc > 30, "Viscosity >30 cP"),
            (temp > 90, "Temperature >90°C"), (tds > 10000, "TDS >10,000 ppm"),
            (hardness > 50, "Hardness >50 ppm"),
            (not self._eq(v.get("rock_type"), "Sandstone"), "Rock type is not Sandstone"),
        ]:
            if condition: causes.append(message)
        score = 100 * sum([
            api >= 22, visc <= 30, temp <= 90, tds <= 10000,
            hardness <= 50, self._eq(v.get("rock_type"), "Sandstone"),
            self._in(v.get("water_handling"), ["Low", "Medium"]), water_cut >= 50,
        ]) / 8
        results.append(self._result("ASP", bool(causes), causes, score, 20, v))

        # Row 12 — CSS.
        causes = []
        for condition, message in [
            (visc < 100, "Viscosity <100 cP"), (depth > 3000, "Depth >3000 ft"),
            (perm < 500, "Permeability <500 mD"),
        ]:
            if condition: causes.append(message)
        score = 100 * sum([visc >= 100, depth <= 3000, perm >= 500, self._no(v.get("offshore"))]) / 4
        results.append(self._result("CSS", bool(causes), causes, score, 15, v))

        # Row 13 — Steam Flood.
        causes = []
        for condition, message in [
            (visc < 100, "Viscosity <100 cP"), (depth > 3000, "Depth >3000 ft"),
            (perm < 1000, "Permeability <1000 mD"),
        ]:
            if condition: causes.append(message)
        score = 100 * sum([visc >= 100, depth <= 3000, perm >= 1000, self._no(v.get("offshore"))]) / 4
        results.append(self._result("Steam Flood", bool(causes), causes, score, 18, v))

        # Row 14 — ISC.
        causes = []
        for condition, message in [
            (visc < 10 or visc > 200, "Viscosity outside 10–200 cP"),
            (perm < 200, "Permeability <200 mD"),
        ]:
            if condition: causes.append(message)
        score = 100 * sum([10 <= visc <= 200, perm >= 200, self._no(v.get("offshore"))]) / 3
        results.append(self._result("ISC", bool(causes), causes, score, 10, v))

        # Excel Ranking! uses LARGE + MATCH, which repeats tied methods.
        # Streamlit fixes that presentation bug while preserving the score logic:
        # stable sort by score desc, then original workbook row order.
        ranked = sorted(results, key=lambda row: (-row["Score (%)"], row["EOR Technique"]))

        return {
            "status": "OK",
            "formation": formation,
            "inputs": v,
            "results": ranked,
            "source_sheet": "Screening",
            "ranking_note": "Distinct-method ranking; ties are kept distinct rather than repeated as in Ranking! MATCH logic.",
        }


# =============================================================================
# EXCEL SCREENING HELPERS
# =============================================================================

def get_screening_tool_dataframe(services: Dict[str, Any]) -> pd.DataFrame:
    """Return the actual executable Screening worksheet when available."""
    sheets = services.get("workbook_sheets", {})
    if "Screening" in sheets:
        return sheets["Screening"].copy()
    return pd.DataFrame()


def _screening_status_display(status: str) -> str:
    return {
        "PASS": "🟢 PASS",
        "CONDITIONAL": "🟡 CONDITIONAL",
        "FAIL (critical)": "🔴 FAIL (critical)",
    }.get(status, status)


def render_excel_screening_result(screen_result: Dict[str, Any]) -> None:
    """Render the complete workbook-parity Screening output."""
    if screen_result.get("status") != "OK":
        st.error(screen_result.get("message", "Screening failed."))
        return

    results = screen_result.get("results", [])
    if not results:
        st.warning("No screening results were generated.")
        return

    st.subheader("📋 EOR Screening Results")

    pass_count = sum(r["Status"] == "PASS" for r in results)
    conditional_count = sum(r["Status"] == "CONDITIONAL" for r in results)
    fail_count = sum(r["Status"] == "FAIL (critical)" for r in results)

    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 PASS", pass_count)
    c2.metric("🟡 CONDITIONAL", conditional_count)
    c3.metric("🔴 FAIL (critical)", fail_count)

    summary = pd.DataFrame(results).copy()
    summary["Status"] = summary["Status"].map(_screening_status_display)
    summary["Score (%)"] = summary["Score (%)"].round(1)
    summary["ΔRF_EOR (%)"] = summary["ΔRF_EOR (%)"].round(2)
    summary["Final RF (%)"] = summary["Final RF (%)"].round(2)
    summary["EUR (MMstb)"] = summary["EUR (MMstb)"].round(2)

    display_cols = [
        "EOR Technique", "Status", "Suitability", "Score (%)",
        "ΔRF_EOR (%)", "Final RF (%)", "EUR (MMstb)", "Cause of Fail/Pass",
    ]
    st.dataframe(summary[display_cols], use_container_width=True, hide_index=True)

    st.markdown("### Top screening candidates")
    top_candidates = pd.DataFrame(results).sort_values(
        ["Critical Fail", "Score (%)"], ascending=[True, False]
    ).head(3)
    top_cols = st.columns(min(3, len(top_candidates)))
    for col, (_, row) in zip(top_cols, top_candidates.iterrows()):
        with col:
            st.metric(str(row["EOR Technique"]), f'{row["Score (%)"]:.1f}%')
            st.caption(f'{_screening_status_display(row["Status"])} · {row["Suitability"]}')
            st.write(f'Incremental RF: **{row["ΔRF_EOR (%)"]:.2f}%**')
            st.write(f'EUR: **{row["EUR (MMstb)"]:.2f} MMstb**')

    st.markdown("### Criterion-level reasons")
    for row in results:
        title = f'{_screening_status_display(row["Status"])} — {row["EOR Technique"]} — {row["Score (%)"]:.1f}%'
        with st.expander(title, expanded=False):
            st.write(f'**Suitability:** {row["Suitability"]}')
            st.write(f'**Reason:** {row["Cause of Fail/Pass"]}')
            st.write(f'**ΔRF_EOR:** {row["ΔRF_EOR (%)"]:.2f}%')
            st.write(f'**Final RF:** {row["Final RF (%)"]:.2f}%')
            st.write(f'**EUR:** {row["EUR (MMstb)"]:.2f} MMstb')

    st.caption(
        "Deterministic screening only. This tab reproduces the executable Screening sheet logic and does not call the fuzzy engine or neural network."
    )


# =============================================================================
# SHARED SCREENING / INTELLIGENCE INPUT FORM
# =============================================================================

def render_replicated_eor_input_form(prefix: str) -> Tuple[Dict[str, Any], str, bool]:
    """Render the same InputData-equivalent fields for Screening and Intelligence."""
    d = SCREENING_INPUT_DEFAULTS

    with st.expander("📝 Reservoir Characteristics", expanded=True):
        a, b, c = st.columns(3)
        with a:
            formation = st.selectbox("Formation Category", settings.ui_config["formation_categories"], index=0, key=f"{prefix}_formation")
            depth_ft = st.number_input("Depth (ft)", 0.0, value=d["depth_ft"], step=50.0, key=f"{prefix}_depth")
            reservoir_pressure = st.number_input("Reservoir Pressure (psia)", 0.0, value=d["reservoir_pressure"], step=50.0, key=f"{prefix}_pressure")
            temperature_c = st.number_input("Temperature (°C)", 0.0, value=d["temperature_c"], step=1.0, key=f"{prefix}_temperature")
            visc_cp = st.number_input("Oil Viscosity (cP)", 0.0, value=d["visc_cp"], step=0.1, key=f"{prefix}_visc")
        with b:
            api = st.number_input("API Gravity (°API)", 0.0, 80.0, value=d["api"], step=0.5, key=f"{prefix}_api")
            perm_md = st.number_input("Permeability (mD)", 0.0, value=d["perm_md"], step=10.0, key=f"{prefix}_perm")
            porosity_frac = st.number_input("Porosity (fraction)", 0.0, 1.0, value=d["porosity_frac"], step=0.01, key=f"{prefix}_por")
            salinity_ppm = st.number_input("Salinity / TDS (ppm)", 0.0, value=d["salinity_ppm"], step=1000.0, key=f"{prefix}_tds")
            hardness_ppm = st.number_input("Hardness Ca²⁺+Mg²⁺ (ppm)", 0.0, value=d["hardness_ppm"], step=50.0, key=f"{prefix}_hardness")
        with c:
            rock_type = st.selectbox("Rock Type", ["Sandstone", "Carbonate", "Unconsolidated sands"], index=0, key=f"{prefix}_rock")
            net_pay_m = st.number_input("Net Pay (m)", 0.0, value=d["net_pay_m"], step=1.0, key=f"{prefix}_netpay")
            heterogeneity = st.selectbox("Heterogeneity", ["Low", "Moderate", "High"], index=1, key=f"{prefix}_heterogeneity")
            gas_availability = st.selectbox("Gas Availability", ["Yes", "No"], index=0, key=f"{prefix}_gas_availability")
            oxygen_present = st.selectbox("Oxygen Present in Polymer System", ["Yes", "No"], index=1, key=f"{prefix}_oxygen")
            so_pct = st.number_input("Oil Saturation (%) [ML feature]", 0.0, 100.0, value=55.0, step=1.0, key=f"{prefix}_so")

    with st.expander("🛢️ Recovery / EOR Context", expanded=True):
        a, b, c = st.columns(3)
        with a:
            ooip_mmstb = st.number_input("OOIP (MMstb)", 0.0, value=d["ooip_mmstb"], step=10.0, key=f"{prefix}_ooip")
            base_rf_pct = st.number_input("Base RF without EOR (%)", 0.0, 100.0, value=d["base_rf_pct"], step=1.0, key=f"{prefix}_base_rf")
            drive_mechanism = st.selectbox("Drive Mechanism", ["Waterflood", "Gas Drive", "Solution Gas Drive", "Natural Depletion", "Other"], index=0, key=f"{prefix}_drive")
            drive_multiplier = st.number_input("Drive Mech Multiplier", 0.0, 5.0, value=d["drive_multiplier"], step=0.05, key=f"{prefix}_drive_multiplier")
            waterflood_history = st.selectbox("Waterflood History", ["Yes", "No"], index=0, key=f"{prefix}_waterflood")
        with b:
            co2_availability = st.selectbox("CO2 Availability", ["Yes", "No"], index=0, key=f"{prefix}_co2")
            mmp_satisfied = st.selectbox("MMP Satisfied?", ["Yes", "No"], index=0, key=f"{prefix}_mmp")
            water_cut_pct = st.number_input("Water Cut (%)", 0.0, 100.0, value=d["water_cut_pct"], step=1.0, key=f"{prefix}_watercut")
            field_maturity = st.selectbox("Field Maturity", ["Early", "Mature", "Late"], index=1, key=f"{prefix}_maturity")
            maturity_factor = st.number_input("Maturity Factor", 0.0, 5.0, value=d["maturity_factor"], step=0.05, key=f"{prefix}_maturity_factor")
        with c:
            mobility_ratio = st.selectbox("Mobility Ratio", ["Favorable", "Neutral", "Unfavorable"], index=0, key=f"{prefix}_mobility")
            adsorption_risk = st.selectbox("Surfactant Adsorption Risk", ["Low", "Medium", "High"], index=0, key=f"{prefix}_adsorption")
            water_handling = st.selectbox("Produced Water Handling Complexity", ["Low", "Medium", "High"], index=0, key=f"{prefix}_water_handling")
            offshore = st.selectbox("Offshore Field?", ["Yes", "No"], index=1, key=f"{prefix}_offshore")

    with st.expander("🔁 Injection / WAG / Gas Context", expanded=False):
        a, b, c = st.columns(3)
        with a:
            water_injection_facilities = st.selectbox("Water Injection Facilities", ["Yes", "No"], index=0, key=f"{prefix}_water_fac")
            gas_injection_facilities = st.selectbox("Gas Injection Facilities", ["Yes", "No"], index=0, key=f"{prefix}_gas_fac")
            wag_ratio = st.selectbox("WAG Ratio", ["1:1", "2:1", "1:2", "Other"], index=0, key=f"{prefix}_wag_ratio")
        with b:
            gas_injectivity = st.selectbox("Gas Injectivity", ["Good", "Fair", "Poor"], index=0, key=f"{prefix}_gas_inj")
            water_injectivity = st.selectbox("Water Injectivity", ["Good", "Fair", "Poor"], index=0, key=f"{prefix}_water_inj")
            gravity_override_risk = st.selectbox("Gravity Override Risk", ["Low", "Medium", "High"], index=0, key=f"{prefix}_gravity")
        with c:
            hc_gas_availability = st.selectbox("HC Gas Availability", ["Yes", "No"], index=1, key=f"{prefix}_hc_availability")
            produced_gor_category = st.selectbox("Produced GOR Category", ["Low", "Moderate", "High"], index=1, key=f"{prefix}_gor_category")
            gas_reinjectable = st.selectbox("Produced Gas Reinjectable?", ["Yes", "No"], index=0, key=f"{prefix}_reinjectable")
            produced_gor_scf_stb = st.number_input("Produced GOR (scf/STB)", 0.0, value=d["produced_gor_scf_stb"], step=50.0, key=f"{prefix}_gor_numeric")

    values = {
        "depth_ft": depth_ft,
        "reservoir_pressure": reservoir_pressure,
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
    derived = ExcelScreeningService().prepare_inputs(values)

    st.caption(
        f'Workbook helper: HC Gas Source Status = **{derived.get("hc_source_status", "Unavailable")}** · '
        f'Numeric GOR Category = **{derived.get("gor_category_numeric", "—")}**'
    )

    return values, formation, True


# =============================================================================
# EOR INTELLIGENCE HELPERS
# =============================================================================

def run_eor_intelligence(
    services: Dict[str, Any],
    values: Dict[str, float],
    formation: str,
) -> Dict[str, Any]:
    """
    Run fuzzy + NN intelligence.

    IMPORTANT:
    - This function is independent from the Excel Screening Tool.
    - It returns the model's top 3 techniques rather than one final method.
    """
    fuzzy_engine: FuzzyEngine = services["fuzzy_engine"]
    model_service: ModelService = services["model_service"]
    techs_all: List[str] = services["techs_all"]

    fuzzy_scores = fuzzy_engine.evaluate_all(
        techs_all,
        formation,
        values,
    )

    fuzzy_ranked = sorted(
        fuzzy_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    ml_available = model_service.is_loaded()

    ml_probabilities: Dict[str, float] = {}
    ml_top3: List[Tuple[str, float]] = []

    if ml_available:
        try:
            features = model_service.build_features(
                values,
                formation,
                techs_all,
                fuzzy_scores,
            )

            probabilities, ml_top3 = model_service.predict(
                features
            )

            if probabilities is not None:
                # Label encoder is the authoritative mapping for the
                # neural-network output order.
                classes = list(
                    model_service.label_encoder.classes_
                )

                ml_probabilities = {
                    str(label): float(probability)
                    for label, probability in zip(
                        classes,
                        probabilities,
                    )
                }

        except Exception:
            logger.exception("EOR Intelligence ML inference failed")
            ml_available = False
            ml_probabilities = {}
            ml_top3 = []

    # Attach fuzzy support to the NN's top-3 predictions.
    top3_rows = []

    for rank, (technique, probability) in enumerate(
        ml_top3,
        start=1,
    ):
        fuzzy_score = fuzzy_scores.get(
            technique,
            0.0,
        )

        top3_rows.append(
            {
                "Rank": rank,
                "EOR Technique": technique,
                "NN Probability": float(probability),
                "Fuzzy Suitability": float(fuzzy_score),
            }
        )

    return {
        "formation": formation,
        "inputs": values,
        "fuzzy_scores": fuzzy_scores,
        "fuzzy_top5": fuzzy_ranked[:5],
        "ml_available": ml_available,
        "ml_probabilities": ml_probabilities,
        "ml_top3": ml_top3,
        "top3_rows": top3_rows,
    }


def render_eor_intelligence_result(
    result: Dict[str, Any],
) -> None:
    """Render top-3 EOR intelligence output."""
    st.subheader("🧠 EOR Intelligence Results")

    top3_rows = result.get("top3_rows", [])

    if not result.get("ml_available"):
        st.warning(
            "Neural-network artifacts are unavailable or inference failed. "
            "The fuzzy suitability ranking is shown below."
        )

        fuzzy_top5 = result.get("fuzzy_top5", [])

        if fuzzy_top5:
            fuzzy_df = pd.DataFrame(
                [
                    {
                        "Rank": index,
                        "EOR Technique": technique,
                        "Fuzzy Suitability": score,
                    }
                    for index, (technique, score)
                    in enumerate(fuzzy_top5, start=1)
                ]
            )

            st.dataframe(
                fuzzy_df,
                use_container_width=True,
                hide_index=True,
            )

        return

    if not top3_rows:
        st.info(
            "The model did not return any top-3 predictions."
        )
        return

    st.markdown(
        """
        The intelligence layer predicts the **three most likely EOR
        techniques** from the supplied reservoir characteristics. The
        fuzzy score is shown as a supporting suitability signal.
        """
    )

    # -------------------------------------------------------------------------
    # TOP-3 CARDS
    # -------------------------------------------------------------------------
    top_cols = st.columns(len(top3_rows))

    for col, row in zip(top_cols, top3_rows):
        with col:
            st.markdown(
                f"""
                <div class="top3-card">
                    <div style="font-size:0.75rem; color:#64748b;">
                        RANK {row["Rank"]}
                    </div>
                    <div style="font-size:1.25rem; font-weight:700;
                                margin:0.3rem 0;">
                        {row["EOR Technique"]}
                    </div>
                    <div style="font-size:0.85rem;">
                        NN Probability:
                        <strong>{_format_probability(row["NN Probability"])}</strong>
                    </div>
                    <div style="font-size:0.85rem; margin-top:0.2rem;">
                        Fuzzy Suitability:
                        <strong>{_format_score(row["Fuzzy Suitability"])}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # -------------------------------------------------------------------------
    # TOP-3 TABLE
    # -------------------------------------------------------------------------
    top3_df = pd.DataFrame(top3_rows).copy()

    top3_df["NN Probability"] = top3_df[
        "NN Probability"
    ].map(_format_probability)

    top3_df["Fuzzy Suitability"] = top3_df[
        "Fuzzy Suitability"
    ].map(_format_score)

    st.dataframe(
        top3_df,
        use_container_width=True,
        hide_index=True,
    )

    # -------------------------------------------------------------------------
    # FULL NN DISTRIBUTION
    # -------------------------------------------------------------------------
    if result.get("ml_probabilities"):
        st.subheader("Neural Network Probability Distribution")

        probability_series = (
            pd.Series(result["ml_probabilities"], dtype=float)
            .sort_values(ascending=False)
        )

        st.bar_chart(probability_series)

    # -------------------------------------------------------------------------
    # FUZZY DISTRIBUTION
    # -------------------------------------------------------------------------
    st.subheader("Fuzzy Suitability Distribution")

    fuzzy_series = (
        pd.Series(
            result.get("fuzzy_scores", {}),
            dtype=float,
        )
        .sort_values(ascending=False)
    )

    if not fuzzy_series.empty:
        st.bar_chart(fuzzy_series)

    st.info(
        "EOR Intelligence is an analytical ranking layer. "
        "Its Top-3 prediction does not override the stand-alone "
        "Excel Screening Tool result."
    )


# =============================================================================
# EXISTING DASHBOARD COMPONENTS
# =============================================================================

def render_database_summary_section() -> None:
    """Render database and screening activity overview."""
    try:
        recent_runs = RepositoryFactory.screening_repo().get_recent(
            days=30
        )
    except Exception as exc:
        logger.warning(
            "Database summary unavailable: %s",
            exc,
        )
        recent_runs = None

    st.subheader("📊 Platform Overview")

    path_status = settings.validate_paths()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Recent Runs",
        len(recent_runs)
        if recent_runs is not None
        else "N/A",
    )

    col2.metric(
        "Model Status",
        "Ready"
        if path_status.get("model")
        else "Missing",
    )

    col3.metric(
        "Workbook",
        "Loaded"
        if path_status.get("workbook")
        else "Missing",
    )

    col4.metric(
        "Environment",
        settings.environment.upper(),
    )

    if recent_runs is None:
        st.warning(
            "Screening history is currently unavailable."
        )
        return

    if recent_runs:
        table = []

        for run in recent_runs[:5]:
            table.append(
                {
                    "Time": (
                        run.timestamp.strftime(
                            "%Y-%m-%d %H:%M"
                        )
                        if run.timestamp
                        else "N/A"
                    ),
                    "Formation": run.formation,
                    "Recommendation": (
                        run.recommended_technique
                        or "N/A"
                    ),
                    "Score": (
                        round(
                            float(
                                run.recommendation_score
                            ),
                            3,
                        )
                        if run.recommendation_score
                        is not None
                        else None
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(table),
            use_container_width=True,
            hide_index=True,
        )


def render_executive_kpi_row() -> None:
    """Render executive KPI cards."""
    try:
        recent_runs = RepositoryFactory.screening_repo().get_recent(
            days=30
        )
    except Exception:
        recent_runs = None

    path_status = settings.validate_paths()

    active_runs = (
        len(recent_runs)
        if recent_runs is not None
        else "N/A"
    )

    st.subheader("Executive KPI Snapshot")

    kpis = [
        ("Recent Runs", active_runs),
        (
            "Model Status",
            "Ready"
            if path_status.get("model")
            else "Missing",
        ),
        (
            "Workbook",
            "Loaded"
            if path_status.get("workbook")
            else "Missing",
        ),
        (
            "Environment",
            settings.environment.upper(),
        ),
    ]

    cols = st.columns(4)

    for col, (label, value) in zip(cols, kpis):
        with col:
            st.markdown(
                f"""
                <div class="exec-kpi-card">
                    <div class="exec-kpi-label">
                        {label}
                    </div>
                    <div class="exec-kpi-value">
                        {value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_model_registry_section() -> None:
    """Render model registry."""
    st.subheader("🧠 Model Registry & Version History")

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

    if versions is None:
        st.warning(
            "Model registry is currently unavailable."
        )
        return

    if not versions:
        st.info(
            "No model versions are registered yet."
        )
        return

    rows = []

    for version in versions:
        rows.append(
            {
                "Version": version.version,
                "Algorithm": version.algorithm,
                "Framework": version.framework,
                "Accuracy": (
                    round(
                        float(
                            version.test_accuracy
                        ),
                        4,
                    )
                    if version.test_accuracy is not None
                    else None
                ),
                "Weighted F1": (
                    round(
                        float(
                            version.test_weighted_f1
                        ),
                        4,
                    )
                    if version.test_weighted_f1
                    is not None
                    else None
                ),
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


def render_saved_run_detail_section() -> None:
    """Display saved screening details and comparison."""
    st.subheader("🧾 Saved Run Detail & Comparison")

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

    if history is None:
        st.warning(
            "Historical screening data is currently unavailable."
        )
        return

    if not history:
        st.info(
            "No saved screening runs are available yet."
        )
        return

    history_df = pd.DataFrame(
        [
            {
                "Run ID": run.id,
                "Timestamp": (
                    run.timestamp.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if run.timestamp
                    else "N/A"
                ),
                "Formation": run.formation,
                "Recommendation": (
                    run.recommended_technique
                    or "N/A"
                ),
                "Status": (
                    run.recommendation_status
                    or "N/A"
                ),
                "Score": (
                    round(
                        float(
                            run.recommendation_score
                        ),
                        3,
                    )
                    if run.recommendation_score
                    is not None
                    else None
                ),
            }
            for run in history
        ]
    )

    st.dataframe(
        history_df,
        use_container_width=True,
        hide_index=True,
    )

    run_ids = [run.id for run in history]

    run_a_id = st.selectbox(
        "Select a saved run to reopen",
        run_ids,
        index=0,
        key="saved_run_a",
    )

    selected_run = next(
        (
            run
            for run in history
            if run.id == run_a_id
        ),
        history[0],
    )

    st.markdown("### Reopened assessment")

    detail_cols = st.columns(2)

    with detail_cols[0]:
        st.write(
            f"**Run ID:** {selected_run.id}"
        )

        st.write(
            "**Timestamp:** "
            f"{selected_run.timestamp.strftime('%Y-%m-%d %H:%M') if selected_run.timestamp else 'N/A'}"
        )

        st.write(
            f"**Formation:** "
            f"{selected_run.formation}"
        )

        st.write(
            "**Recommendation:** "
            f"{selected_run.recommended_technique or 'N/A'}"
        )

    with detail_cols[1]:
        st.write(
            "**Final Status:** "
            f"{selected_run.recommendation_status or 'N/A'}"
        )

        st.write(
            "**Score:** "
            f"{selected_run.recommendation_score if selected_run.recommendation_score is not None else 'N/A'}"
        )

        st.write(
            "**Model Version:** "
            f"{selected_run.model_version or 'N/A'}"
        )

        st.write(
            "**Data Readiness:** "
            f"{selected_run.data_readiness_pct or 'N/A'}%"
        )

    input_payload = selected_run.input_payload or {}

    if input_payload:
        st.write("**Exact input values:**")
        st.dataframe(
            pd.DataFrame([input_payload]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No exact input payload was stored."
        )

    rule_trace = selected_run.rule_trace or {}

    if rule_trace:
        st.write("**Structured rule trace:**")
        st.json(rule_trace)

    assumptions = selected_run.assumptions or {}

    if assumptions:
        st.write("**Recorded assumptions:**")
        st.json(assumptions)

    evidence_summary = (
        selected_run.evidence_summary or {}
    )

    if evidence_summary:
        st.write("**Evidence summary:**")
        st.json(evidence_summary)

    download_payload = {
        "run_id": selected_run.id,
        "timestamp": (
            selected_run.timestamp.isoformat()
            if selected_run.timestamp
            else None
        ),
        "formation": selected_run.formation,
        "recommendation": (
            selected_run.recommended_technique
        ),
        "status": selected_run.recommendation_status,
        "score": selected_run.recommendation_score,
        "inputs": input_payload,
        "rule_trace": rule_trace,
        "assumptions": assumptions,
        "evidence_summary": evidence_summary,
    }

    st.download_button(
        label="Download saved assessment JSON",
        data=json.dumps(
            download_payload,
            indent=2,
            default=str,
        ),
        file_name=(
            f"eor_run_{selected_run.id}.json"
        ),
        mime="application/json",
    )

    st.markdown("### Compare two saved runs")

    if len(history) >= 2:
        run_b_id = st.selectbox(
            "Select the second run for comparison",
            run_ids,
            index=min(
                1,
                len(run_ids) - 1,
            ),
            key="saved_run_b",
        )

        if run_a_id == run_b_id:
            st.caption(
                "Choose a different run for comparison."
            )
        else:
            try:
                comparison = (
                    RepositoryFactory
                    .screening_repo()
                    .compare_runs(
                        run_a_id,
                        run_b_id,
                    )
                )
            except Exception:
                comparison = {
                    "error":
                        "Comparison is currently unavailable."
                }

            if "error" in comparison:
                st.warning(
                    comparison["error"]
                )
            else:
                left = comparison["left"]
                right = comparison["right"]

                col_left, col_right = st.columns(2)

                with col_left:
                    st.write("**Left run**")
                    st.json(left)

                with col_right:
                    st.write("**Right run**")
                    st.json(right)

                st.metric(
                    "Score Delta",
                    f"{comparison['delta_score']:+.3f}",
                )
    else:
        st.info(
            "At least two saved runs are needed."
        )


def render_sidebar_status() -> None:
    """Render operational status in sidebar."""
    path_status = settings.validate_paths()

    model_ready = bool(
        path_status.get("model")
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
        <div class='sidebar-status-box'>

            <div class='status-row'>
                <span>Model</span>
                <span class='status-pill {'ready' if model_ready else 'warn'}'>
                    {'Ready' if model_ready else 'Missing'}
                </span>
            </div>

            <div class='status-row'>
                <span>Workbook</span>
                <span class='status-pill {'ready' if workbook_ready else 'warn'}'>
                    {'Loaded' if workbook_ready else 'Missing'}
                </span>
            </div>

            <div class='status-row'>
                <span>Config</span>
                <span class='status-pill {'ready' if config_ready else 'warn'}'>
                    {'Valid' if config_ready else 'Check'}
                </span>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.caption(
        "Decision stack"
    )

    st.sidebar.write("• Rule engine")
    st.sidebar.write("• Fuzzy logic")
    st.sidebar.write("• Neural network")
    st.sidebar.write("• Decision synthesis")


# =============================================================================
# EXECUTIVE OVERVIEW — KEEPING EXISTING UI
# =============================================================================

def render_executive_overview_section() -> None:
    """Executive overview aligned to the current portfolio UI."""
    st.header("🏠 Executive Overview")

    portfolio = pd.DataFrame(
        {
            "Metric": [
                "Fields",
                "Reservoirs",
                "EOR Families",
                "Historical Studies",
                "RF Gap (MMstb)",
                "Candidates",
            ],
            "Value": [
                41,
                600,
                9,
                128,
                1.31,
                18,
            ],
        }
    )

    metric_cols = st.columns(6)

    for i, (
        metric,
        value,
    ) in enumerate(
        zip(
            portfolio["Metric"],
            portfolio["Value"],
        )
    ):
        with metric_cols[i]:
            st.markdown(
                f"""
                <div class='exec-kpi-card'>
                    <div class='exec-kpi-label'>
                        {metric}
                    </div>
                    <div class='exec-kpi-value'>
                        {value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Preserve the current field dataset and map design.
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
                map_style=(
                    "mapbox://styles/mapbox/light-v9"
                ),
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
                        get_radius=(
                            "RF_Gap"
                        ),
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

    st.subheader(
        "Portfolio Summary Table"
    )

    st.dataframe(
        map_df,
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# EOR SCREENING — STAND-ALONE EXCEL TOOL
# =============================================================================

def render_eor_screening_tab(services: Dict[str, Any]) -> None:
    """Standalone workbook-parity EOR Screening — no ML, no fuzzy logic."""
    st.header("🔍 EOR Screening")
    st.write(
        "Deterministic reservoir screening using the executable logic from "
        "EOR_Screening_Tool_2026.xlsx → Screening!B2:I14."
    )

    inputs, formation, _ = render_replicated_eor_input_form("screening")

    if st.button("🚀 Run Screening", type="primary", use_container_width=True, key="excel_screening_run"):
        with st.spinner("Running deterministic Excel screening logic..."):
            try:
                result = ExcelScreeningService().screen(inputs, formation)
                st.session_state["excel_screening_result"] = result
                st.session_state["excel_screening_inputs"] = inputs
                st.session_state["excel_screening_formation"] = formation
            except Exception:
                logger.exception("Excel Screening execution failed")
                st.error("The workbook-parity screening could not be executed.")

    result = st.session_state.get("excel_screening_result")
    if result:
        st.success("✅ EOR Screening completed")
        render_excel_screening_result(result)

    st.divider()
    with st.expander("Workbook source / diagnostic", expanded=False):
        st.write(f"Workbook: `{settings.workbook_path}`")
        st.write("Executable worksheet: `Screening`")
        st.write("Input source: `InputData!B4:B44`")
        st.write("Output source: `Screening!B2:I14`")
        st.write("Ranking traceability: `Ranking` and `Summary`")
        st.caption(
            "The Python implementation is intentionally explicit rather than dynamically interpreting arbitrary min/max columns, because the workbook's Screening sheet contains method-specific boolean logic, conditional pathways, weighted GOR scoring and post-screening RF/EUR calculations."
        )




# =============================================================================
# FIELD / RESERVOIR CANDIDATES — KEEP CURRENT UI
# =============================================================================

def render_field_candidates_section() -> None:
    """Field and reservoir candidate screening aligned to the current UI."""
    st.header("🗺️ Field / Reservoir Candidates")

    candidate_df = pd.DataFrame(
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
        candidate_df.set_index(
            "Field"
        )["EUR_MMstb"]
    )

    st.subheader(
        "Opportunity Rank"
    )

    st.bar_chart(
        candidate_df.set_index(
            "Field"
        )["RF_Gap"]
    )

    st.dataframe(
        candidate_df,
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# FLUID / FLUID — KEEP CURRENT UI
# =============================================================================

def render_fluid_fluid_section() -> None:
    """Fluid-fluid CEOR section."""
    st.header("🧪 CEOR — Fluid / Fluid")

    rheology_df = pd.DataFrame(
        {
            "Shear_Rate": [
                10,
                30,
                50,
                100,
                200,
            ],
            "Polymer_A": [
                120,
                90,
                75,
                58,
                44,
            ],
            "Polymer_B": [
                132,
                104,
                82,
                64,
                49,
            ],
            "Polymer_C": [
                110,
                88,
                70,
                54,
                41,
            ],
        }
    ).set_index(
        "Shear_Rate"
    )

    st.subheader("Rheology")
    st.line_chart(
        rheology_df
    )

    thermal_df = pd.DataFrame(
        {
            "Time_Days": [
                0,
                7,
                14,
                30,
                60,
            ],
            "Retention_A": [
                100,
                96,
                90,
                84,
                79,
            ],
            "Retention_B": [
                100,
                92,
                85,
                75,
                68,
            ],
        }
    ).set_index(
        "Time_Days"
    )

    st.subheader(
        "Thermal Stability"
    )

    st.line_chart(
        thermal_df
    )

    phase_df = pd.DataFrame(
        {
            "Formulation": [
                "A-1",
                "A-2",
                "B-1",
                "B-2",
                "C-1",
            ],
            "No_Precipitation": [
                82,
                70,
                65,
                91,
                76,
            ],
            "Precipitation": [
                18,
                30,
                35,
                9,
                24,
            ],
        }
    )

    st.subheader(
        "Phase Behaviour"
    )

    st.bar_chart(
        phase_df.set_index(
            "Formulation"
        )
    )

    st.subheader(
        "IFT Comparison"
    )

    ift_df = pd.DataFrame(
        {
            "Formulation": [
                "F1",
                "F2",
                "F3",
                "F4",
            ],
            "IFT": [
                0.022,
                0.010,
                0.040,
                0.013,
            ],
        }
    )

    st.bar_chart(
        ift_df.set_index(
            "Formulation"
        )
    )


# =============================================================================
# FLUID / ROCK — KEEP CURRENT UI
# =============================================================================

def render_fluid_rock_section() -> None:
    """Fluid-rock CEOR section."""
    st.header("🪨 CEOR — Fluid / Rock")

    adsorption_df = pd.DataFrame(
        {
            "Days": [
                0,
                7,
                14,
                30,
                60,
            ],
            "Adsorption_Surf_A": [
                0.0,
                0.18,
                0.27,
                0.35,
                0.42,
            ],
            "Adsorption_Surf_B": [
                0.0,
                0.12,
                0.20,
                0.28,
                0.31,
            ],
        }
    ).set_index(
        "Days"
    )

    st.subheader(
        "Adsorption vs Time"
    )

    st.line_chart(
        adsorption_df
    )

    coreflood_df = pd.DataFrame(
        {
            "Core": [
                "Core 1",
                "Core 2",
                "Core 3",
                "Core 4",
            ],
            "Waterflood": [
                42,
                38,
                45,
                41,
            ],
            "EOR_Increment": [
                15,
                18,
                11,
                14,
            ],
        }
    )

    st.subheader(
        "Core Flood Incremental Recovery"
    )

    st.bar_chart(
        coreflood_df.set_index(
            "Core"
        )
    )

    sor_df = pd.DataFrame(
        {
            "Core": [
                "Core 1",
                "Core 2",
                "Core 3",
                "Core 4",
            ],
            "Sor_Reduction": [
                36,
                28,
                41,
                31,
            ],
        }
    )

    st.subheader(
        "Sor Reduction"
    )

    st.bar_chart(
        sor_df.set_index(
            "Core"
        )
    )


# =============================================================================
# CHALLENGES — KEEP CURRENT UI
# =============================================================================

def render_challenges_section() -> None:
    """Lessons learnt/challenge registry."""
    st.header(
        "⚠️ Challenges & Lessons Learnt"
    )

    challenge_df = pd.DataFrame(
        {
            "Field": [
                "Angsi",
                "Dulang",
                "Barton",
                "Baram",
            ],
            "Chemical_Compatibility": [
                "High",
                "Medium",
                "Low",
                "High",
            ],
            "Facilities": [
                "Medium",
                "Low",
                "High",
                "Medium",
            ],
            "Fluid_Handling": [
                "High",
                "Medium",
                "Medium",
                "Low",
            ],
            "Cost_Logistics": [
                "High",
                "Medium",
                "Low",
                "High",
            ],
        }
    )

    st.dataframe(
        challenge_df,
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
            "Count": [
                4,
                3,
                3,
                2,
                2,
            ],
        }
    )

    st.subheader(
        "Challenge Distribution"
    )

    st.bar_chart(
        dist.set_index(
            "Challenge"
        )
    )


# =============================================================================
# EOR INTELLIGENCE — FORM + FUZZY + TOP-3 ML
# =============================================================================

def render_eor_intelligence_section(services: Dict[str, Any]) -> None:
    """Replicated screening inputs → fuzzy envelope → neural-network Top 3."""
    st.header("🤖 EOR Intelligence")
    st.write(
        "The same reservoir inputs used by EOR Screening are replicated here. "
        "This layer is analytical only: fuzzy suitability and NN probabilities "
        "are shown separately, with the NN returning Top 3 techniques."
    )

    inputs, formation, _ = render_replicated_eor_input_form("intel")

    if st.button("🧠 Run EOR Intelligence", type="primary", use_container_width=True, key="run_eor_intelligence"):
        values = {
            "depth_ft": inputs["depth_ft"],
            "porosity_pct": inputs["porosity_pct"],
            "perm_md": inputs["perm_md"],
            "api": inputs["api"],
            "visc_cp": inputs["visc_cp"],
            "so_pct": inputs.get("so_pct", 55.0),
        }
        with st.spinner("Running fuzzy and neural-network intelligence..."):
            try:
                result = run_eor_intelligence(services, values, formation)
                st.session_state["eor_intelligence_result"] = result
                st.session_state["eor_intelligence_inputs"] = inputs
                st.session_state["eor_intelligence_formation"] = formation
            except Exception:
                logger.exception("EOR Intelligence execution failed")
                st.error("EOR Intelligence could not complete inference.")

    result = st.session_state.get("eor_intelligence_result")
    if result:
        render_eor_intelligence_result(result)

    st.divider()
    render_model_registry_section()
    st.write("---")
    render_saved_run_detail_section()


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """Main EOR Atlas application entry point."""
    st.title(
        "🛢️ EOR Atlas – Decision Support Platform"
    )

    st.caption(
        "Engineering-first EOR dashboard built around screening, "
        "candidate discovery, CEOR evidence, and auditability."
    )

    st.sidebar.header(
        "📋 EOR Atlas"
    )

    st.sidebar.caption(
        "Engineering decision workspace"
    )

    render_sidebar_status()

    path_status = settings.validate_paths()

    missing = [
        key
        for key, value in path_status.items()
        if not value
    ]

    if missing:
        st.sidebar.warning(
            f"Artifacts pending: {', '.join(missing)}"
        )

    services = initialize_services()

    fuzzy_engine = services["fuzzy_engine"]
    model_service = services["model_service"]
    techs_all = services["techs_all"]

    if services is None:
        st.error(
            "Failed to initialize application services."
        )
        return

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
        render_eor_screening_tab(
            services
        )

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

        st.write("---")

        st.subheader(
            "Historical outcome ledger"
        )

        try:
            history = (
                RepositoryFactory
                .screening_repo()
                .get_recent(days=365)
            )

            if not history:
                st.info(
                    "No historical records available yet."
                )
            else:
                history_df = pd.DataFrame(
                    [
                        {
                            "Run ID": run.id,
                            "Field": run.formation,
                            "Recommendation": (
                                run.recommended_technique
                            ),
                            "Status": (
                                run.recommendation_status
                            ),
                            "Score": (
                                run.recommendation_score
                            ),
                        }
                        for run in history
                    ]
                )

                st.dataframe(
                    history_df,
                    use_container_width=True,
                    hide_index=True,
                )

        except Exception as exc:
            logger.warning(
                "Historical results unavailable: %s",
                exc,
            )

            st.info(
                "No historical records available yet."
            )

    with tabs[6]:
        render_challenges_section()

    with tabs[7]:
        render_eor_intelligence_section(
            services
        )


if __name__ == "__main__":
    main()
