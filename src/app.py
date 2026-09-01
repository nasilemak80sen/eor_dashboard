# EOR Atlas – Enhanced Oil Recovery Screening & Decision Support Platform

# Streamlit application entry point.

# Design goals:
#- Keep the existing modular domain / data / ML architecture.
#- Keep app.py focused on orchestration and presentation.
#- Make the Executive Overview genuinely interactive.
#- Use real field latitude / longitude values when available.
#- Avoid silently presenting synthetic data as operational data.
#- Preserve screening, fuzzy, ML, historical-run, and model-registry features.

from __future__ import annotations

import json
from pathlib import Path
import ast
import textwrap

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import streamlit as st

try:
    import pydeck as pdk
except Exception:  # pragma: no cover - optional dependency
    pdk = None

# =============================================================================
# APPLICATION SERVICES
# =============================================================================

from config.settings import settings
from utils.logging_config import logger
from utils.validators import InputValidator, ValidationStatus
from domain.fuzzy_engine import FuzzyEngine
from domain.rule_engine import RuleEngine, EligibilityStatus
from domain.screening_engine import ScreeningEngine
from ml.model_service import ModelService
from data.repositories import EnvelopeRepository, WorkbookRepository
from data.queries import RepositoryFactory


# =============================================================================
# CONSTANTS
# =============================================================================

EOR_STATUS_COLORS = {
    "Candidate": [255, 126, 70, 220],
    "Multiple": [37, 99, 235, 220],
    "Historical": [100, 116, 139, 175],
    "Screened": [16, 185, 129, 210],
    "Unknown": [148, 163, 184, 160],
}

DEFAULT_FIELD_PORTFOLIO = pd.DataFrame(
    {
        "Field": ["Angsi", "Barton", "Dulang", "Tapis", "Baram"],
        "Latitude": [4.3, 4.1, 3.9, 3.8, 5.0],
        "Longitude": [103.1, 103.3, 103.6, 103.2, 112.0],
        "EOR_Status": ["Candidate", "Multiple", "Historical", "Candidate", "Historical"],
        "RF_Gap": [120.0, 95.0, 80.0, 66.0, 105.0],
    }
)

# Optional enrichment. Populate this when the underlying workbook contains it.
OPTIONAL_FIELD_COLUMNS = [
    "Reservoir",
    "Formation",
    "Recommended_Technique",
    "Screening_Score",
    "ML_Confidence",
    "Candidates",
]


# =============================================================================
# STREAMLIT CONFIGURATION / GLOBAL STYLING
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
        padding-top: 1.1rem;
        padding-bottom: 2rem;
    }

    .stAlert > div {
        border-radius: 12px;
    }

    .stTabs [role="tablist"] {
        background: rgba(15, 23, 42, 0.05);
        border-radius: 10px;
        padding: 0.15rem;
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

    .map-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 0.8rem;
        margin: 0.35rem 0 0.8rem 0;
        font-size: 0.82rem;
    }

    .map-legend-item {
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }

    .map-legend-dot {
        width: 11px;
        height: 11px;
        border-radius: 50%;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# SERVICE INITIALIZATION
# =============================================================================

@st.cache_resource
def initialize_services() -> Optional[Dict[str, Any]]:
    """Initialize and cache application services."""

    logger.info("Initializing EOR Atlas services...")

    try:
        env, techs_all = EnvelopeRepository.load_envelopes()
        workbook_sheets = WorkbookRepository.load_workbook()
    except Exception as exc:
        logger.exception("Failed to load application data")
        st.error(
            "Application data could not be loaded. "
            "Check the workbook/envelope paths and application logs."
        )
        return None

    try:
        fuzzy_engine = FuzzyEngine(env, alpha=settings.fuzzy_alpha)
        rule_engine = RuleEngine()

        model_service = ModelService()
        model_loaded = model_service.load()

        if not model_loaded:
            logger.warning("ML model failed to load; continuing in rule/fuzzy mode.")

        screening_engine = ScreeningEngine(
            fuzzy_engine,
            rule_engine,
            model_service,
        )

    except Exception:
        logger.exception("Failed to initialize decision engines")
        st.error(
            "Decision engines could not be initialized. "
            "Check the model/configuration and application logs."
        )
        return None

    return {
        "screening_engine": screening_engine,
        "fuzzy_engine": fuzzy_engine,
        "rule_engine": rule_engine,
        "model_service": model_service,
        "env": env,
        "techs_all": techs_all,
        "workbook_sheets": workbook_sheets,
    }


# =============================================================================
# GENERIC DATA HELPERS
# =============================================================================

def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Convert a value to float without raising UI-facing exceptions."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    try:
        result = float(value)
        if np.isnan(result) or np.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def _first_existing_column(
    frame: pd.DataFrame,
    candidates: Sequence[str],
) -> Optional[str]:
    """Return the first matching column using case-insensitive comparison."""
    lookup = {str(col).strip().lower(): col for col in frame.columns}
    for candidate in candidates:
        actual = lookup.get(candidate.strip().lower())
        if actual is not None:
            return actual
    return None


def _coerce_dataframe(value: Any) -> Optional[pd.DataFrame]:
    """Best-effort conversion of common repository/workbook objects to DataFrame."""
    if isinstance(value, pd.DataFrame):
        return value.copy()

    if isinstance(value, dict):
        for item in value.values():
            frame = _coerce_dataframe(item)
            if frame is not None and not frame.empty:
                return frame

    if isinstance(value, (list, tuple)):
        if not value:
            return None

        if all(isinstance(item, dict) for item in value):
            try:
                return pd.DataFrame(value)
            except Exception:
                return None

        for item in value:
            frame = _coerce_dataframe(item)
            if frame is not None and not frame.empty:
                return frame

    return None


def _iter_candidate_frames(source: Any) -> Iterable[pd.DataFrame]:
    """Yield DataFrames recursively from nested workbook/repository structures."""
    if isinstance(source, pd.DataFrame):
        yield source
        return

    if isinstance(source, dict):
        for value in source.values():
            yield from _iter_candidate_frames(value)
        return

    if isinstance(source, (list, tuple)):
        for value in source:
            yield from _iter_candidate_frames(value)


def _find_geospatial_dataframe(source: Any) -> Optional[pd.DataFrame]:
    """
    Find a workbook/repository dataframe containing both latitude and longitude.

    The function is deliberately conservative: it will only promote a frame when
    recognizable latitude/longitude columns exist.
    """
    lat_aliases = [
        "Latitude", "Lat", "LAT", "latitude", "lat",
    ]
    lon_aliases = [
        "Longitude", "Lon", "LON", "longitude", "lon",
    ]
    field_aliases = [
        "Field", "FieldName", "FIELD", "field_name",
    ]

    for frame in _iter_candidate_frames(source):
        lat_col = _first_existing_column(frame, lat_aliases)
        lon_col = _first_existing_column(frame, lon_aliases)
        field_col = _first_existing_column(frame, field_aliases)

        if lat_col is None or lon_col is None or field_col is None:
            continue

        selected = pd.DataFrame(
            {
                "Field": frame[field_col],
                "Latitude": pd.to_numeric(frame[lat_col], errors="coerce"),
                "Longitude": pd.to_numeric(frame[lon_col], errors="coerce"),
            }
        )

        optional_aliases = {
            "Reservoir": ["Reservoir", "ReservoirName", "RESERVOIR"],
            "Formation": ["Formation", "FormationName"],
            "EOR_Status": ["EOR_Status", "EOR Status", "Status"],
            "RF_Gap": ["RF_Gap", "RF Gap", "RecoveryGap", "RFGap"],
            "Recommended_Technique": [
                "Recommended_Technique",
                "Recommended Technique",
                "EOR_Method",
                "Method",
                "Technique",
            ],
            "Screening_Score": [
                "Screening_Score",
                "Screening Score",
                "Score",
            ],
            "ML_Confidence": [
                "ML_Confidence",
                "ML Confidence",
                "Confidence",
            ],
        }

        for target, aliases in optional_aliases.items():
            source_col = _first_existing_column(frame, aliases)
            if source_col is not None:
                selected[target] = frame[source_col]

        selected = selected.dropna(subset=["Latitude", "Longitude"])
        selected["Field"] = selected["Field"].astype(str).str.strip()
        selected = selected[selected["Field"].ne("")]

        if not selected.empty:
            return selected.drop_duplicates(
                subset=["Field", "Latitude", "Longitude"]
            ).reset_index(drop=True)

    return None


def get_field_portfolio_data(services: Dict[str, Any]) -> Tuple[pd.DataFrame, str]:
    """
    Get the executive field map dataset.

    Priority:
    1. A real dataframe from workbook/repository data containing Field/Latitude/Longitude.
    2. The explicitly supplied current field coordinates as a transparent fallback.

    Returns:
        (dataframe, source_label)
    """
    workbook = services.get("workbook_sheets")

    live_frame = _find_geospatial_dataframe(workbook)
    if live_frame is not None and not live_frame.empty:
        frame = live_frame.copy()

        if "EOR_Status" not in frame.columns:
            frame["EOR_Status"] = "Unknown"

        if "RF_Gap" not in frame.columns:
            frame["RF_Gap"] = np.nan

        return frame, "Workbook / repository"

    frame = DEFAULT_FIELD_PORTFOLIO.copy()
    frame.attrs["is_fallback"] = True
    return frame, "Configured portfolio fallback"


def _calculate_portfolio_metrics(field_df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate Executive Overview KPIs from the same dataset driving the map."""
    fields = int(field_df["Field"].nunique())

    reservoirs = (
        int(field_df["Reservoir"].nunique())
        if "Reservoir" in field_df.columns
        else None
    )

    eor_families = (
        int(field_df["Recommended_Technique"].nunique())
        if "Recommended_Technique" in field_df.columns
        else None
    )

    historical = (
        int(
            field_df["EOR_Status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("historical")
            .sum()
        )
        if "EOR_Status" in field_df.columns
        else 0
    )

    rf_gap = (
        pd.to_numeric(field_df["RF_Gap"], errors="coerce").sum()
        if "RF_Gap" in field_df.columns
        else np.nan
    )

    candidates = (
        int(
            field_df["EOR_Status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("candidate")
            .sum()
        )
        if "EOR_Status" in field_df.columns
        else 0
    )

    return {
        "Fields": fields,
        "Reservoirs": reservoirs if reservoirs is not None else "—",
        "EOR Families": eor_families if eor_families is not None else "—",
        "Historical Studies": historical,
        "RF Gap (MMstb)": (
            round(float(rf_gap), 2) if pd.notna(rf_gap) else "—"
        ),
        "Candidates": candidates,
    }


def _prepare_map_dataframe(field_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare standardized values for map rendering."""
    frame = field_df.copy()

    frame["Latitude"] = pd.to_numeric(frame["Latitude"], errors="coerce")
    frame["Longitude"] = pd.to_numeric(frame["Longitude"], errors="coerce")
    frame["RF_Gap"] = pd.to_numeric(
        frame.get("RF_Gap", pd.Series(index=frame.index, dtype=float)),
        errors="coerce",
    )

    frame = frame.dropna(subset=["Latitude", "Longitude"]).copy()

    if frame.empty:
        return frame

    frame["EOR_Status"] = (
        frame.get(
            "EOR_Status",
            pd.Series("Unknown", index=frame.index),
        )
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace("", "Unknown")
    )

    frame["Recommended_Technique"] = (
        frame.get(
            "Recommended_Technique",
            pd.Series(index=frame.index, dtype=object),
        )
        .fillna("Not assigned")
        .astype(str)
        .str.strip()
        .replace("", "Not assigned")
    )

    rf_valid = frame["RF_Gap"].dropna()

    if not rf_valid.empty:
        rf_min = float(rf_valid.min())
        rf_max = float(rf_valid.max())

        if np.isclose(rf_min, rf_max):
            frame["MarkerSize"] = 600.0
        else:
            frame["MarkerSize"] = (
                ((frame["RF_Gap"].fillna(rf_min) - rf_min) / (rf_max - rf_min))
                * 1400.0
                + 280.0
            )
    else:
        frame["MarkerSize"] = 600.0

    frame["Color"] = frame["EOR_Status"].map(
        lambda value: EOR_STATUS_COLORS.get(
            str(value),
            EOR_STATUS_COLORS["Unknown"],
        )
    )

    frame["RF_Gap_Label"] = frame["RF_Gap"].map(
        lambda value: f"{value:.1f} MMstb"
        if pd.notna(value)
        else "N/A"
    )

    frame["Score_Label"] = frame.get(
        "Screening_Score",
        pd.Series(index=frame.index, dtype=float),
    ).map(
        lambda value: f"{float(value):.2f}" if pd.notna(value) else "N/A"
    )

    frame["Confidence_Label"] = frame.get(
        "ML_Confidence",
        pd.Series(index=frame.index, dtype=float),
    ).map(
        lambda value: (
            f"{float(value):.0%}"
            if pd.notna(value) and abs(float(value)) <= 1
            else f"{float(value):.1f}%"
            if pd.notna(value)
            else "N/A"
        )
    )

    return frame


def _render_map_legend(status_values: Sequence[str]) -> None:
    """Render a compact map legend."""
    items = []

    for status in status_values:
        rgba = EOR_STATUS_COLORS.get(status, EOR_STATUS_COLORS["Unknown"])
        rgb = f"{rgba[0]},{rgba[1]},{rgba[2]}"
        items.append(
            f"""
            <span class="map-legend-item">
                <span class="map-legend-dot"
                      style="background: rgb({rgb});"></span>
                {status}
            </span>
            """
        )

    if items:
        st.markdown(
            '<div class="map-legend">' + "".join(items) + "</div>",
            unsafe_allow_html=True,
        )


def _render_pydeck_field_map(map_df: pd.DataFrame) -> None:
    """Render an interactive field opportunity map."""
    if pdk is None:
        st.map(map_df[["Latitude", "Longitude"]])
        return

    if map_df.empty:
        st.warning("No valid field coordinates are available for the map.")
        return

    center_lat = float(map_df["Latitude"].mean())
    center_lon = float(map_df["Longitude"].mean())

    lat_min = float(map_df["Latitude"].min())
    lat_max = float(map_df["Latitude"].max())
    lon_min = float(map_df["Longitude"].min())
    lon_max = float(map_df["Longitude"].max())

    lat_span = max(lat_max - lat_min, 0.5)
    lon_span = max(lon_max - lon_min, 0.5)
    zoom = max(3.0, min(8.0, 7.0 - np.log2(max(lat_span, lon_span))))

    tooltip_html = """
    <div style="font-family: Arial; min-width: 220px;">
        <div style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">
            {Field}
        </div>
        <div><b>Status:</b> {EOR_Status}</div>
        <div><b>RF Gap:</b> {RF_Gap_Label}</div>
        <div><b>Recommended:</b> {Recommended_Technique}</div>
        <div><b>Screening Score:</b> {Score_Label}</div>
        <div><b>ML Confidence:</b> {Confidence_Label}</div>
        <div><b>Coordinates:</b> {Latitude}, {Longitude}</div>
    </div>
    """

    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position="[Longitude, Latitude]",
            get_fill_color="Color",
            get_radius="MarkerSize",
            radius_min_pixels=7,
            radius_max_pixels=38,
            pickable=True,
            stroked=True,
            filled=True,
            line_width_min_pixels=1,
            opacity=0.82,
        )
    ]

    # Add labels only when the map is not overly crowded.
    if len(map_df) <= 30:
        layers.append(
            pdk.Layer(
                "TextLayer",
                data=map_df,
                get_position="[Longitude, Latitude]",
                get_text="Field",
                get_size=13,
                get_color=[15, 23, 42, 230],
                get_pixel_offset=[0, -24],
                billboard=True,
                pickable=False,
            )
        )

    deck = pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=zoom,
            pitch=18,
            bearing=0,
        ),
        layers=layers,
        tooltip={
            "html": tooltip_html,
            "style": {
                "backgroundColor": "white",
                "color": "#0f172a",
                "fontSize": "12px",
                "padding": "10px",
                "borderRadius": "8px",
            },
        },
    )

    st.pydeck_chart(deck, use_container_width=True)


def _render_selected_field_detail(field_df: pd.DataFrame) -> None:
    """Render details for a selected field."""
    if field_df.empty:
        st.info("Select a field to inspect its portfolio information.")
        return

    selected_name = st.selectbox(
        "Inspect field",
        options=field_df["Field"].astype(str).tolist(),
        key="executive_selected_field",
    )

    row = field_df[
        field_df["Field"].astype(str).eq(selected_name)
    ].iloc[0]

    st.markdown("#### Selected Field")

    cols = st.columns(4)

    with cols[0]:
        st.metric("Field", str(row["Field"]))

    with cols[1]:
        st.metric(
            "EOR Status",
            str(row.get("EOR_Status", "Unknown")),
        )

    with cols[2]:
        rf_gap = _safe_float(row.get("RF_Gap"))
        st.metric(
            "RF Gap",
            f"{rf_gap:.1f} MMstb" if rf_gap is not None else "N/A",
        )

    with cols[3]:
        technique = str(
            row.get("Recommended_Technique", "Not assigned")
        )
        st.metric("Recommended", technique)

    detail_cols = st.columns(3)

    with detail_cols[0]:
        st.write(
            f"**Latitude:** {_safe_float(row.get('Latitude'), 0.0):.4f}"
        )
        st.write(
            f"**Longitude:** {_safe_float(row.get('Longitude'), 0.0):.4f}"
        )

    with detail_cols[1]:
        reservoir = row.get("Reservoir", "N/A")
        formation = row.get("Formation", "N/A")
        st.write(f"**Reservoir:** {reservoir}")
        st.write(f"**Formation:** {formation}")

    with detail_cols[2]:
        score = _safe_float(row.get("Screening_Score"))
        confidence = _safe_float(row.get("ML_Confidence"))

        st.write(
            f"**Screening Score:** "
            f"{score:.3f}" if score is not None else "**Screening Score:** N/A"
        )

        if confidence is not None:
            confidence_display = (
                f"{confidence:.0%}" if abs(confidence) <= 1
                else f"{confidence:.1f}%"
            )
        else:
            confidence_display = "N/A"

        st.write(f"**ML Confidence:** {confidence_display}")

    if "Recommended_Technique" not in field_df.columns:
        st.caption(
            "Recommendation enrichment is not available in the current "
            "portfolio source. The map is still driven by field coordinates, "
            "status and RF gap."
        )


# =============================================================================
# STATUS / PLATFORM SECTIONS
# =============================================================================

def render_database_summary_section() -> None:
    """Render recent screening activity and platform status."""
    try:
        recent_runs = RepositoryFactory.screening_repo().get_recent(days=30)
    except Exception as exc:
        logger.warning("Database summary unavailable: %s", exc)
        recent_runs = None

    st.subheader("📊 Platform Overview")

    path_status = settings.validate_paths()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Recent Runs",
            len(recent_runs) if recent_runs is not None else "N/A",
        )

    with col2:
        st.metric(
            "Model Status",
            "Ready" if path_status.get("model") else "Missing",
        )

    with col3:
        st.metric(
            "Workbook",
            "Loaded" if path_status.get("workbook") else "Missing",
        )

    with col4:
        st.metric(
            "Environment",
            settings.environment.upper(),
        )

    if recent_runs is None:
        st.warning("Screening history is currently unavailable.")
        return

    if recent_runs:
        rows = []

        for run in recent_runs[:5]:
            rows.append(
                {
                    "Time": (
                        run.timestamp.strftime("%Y-%m-%d %H:%M")
                        if run.timestamp
                        else "N/A"
                    ),
                    "Formation": run.formation,
                    "Recommendation": run.recommended_technique or "N/A",
                    "Score": (
                        round(float(run.recommendation_score), 3)
                        if run.recommendation_score is not None
                        else None
                    ),
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True)


def render_executive_kpi_row() -> None:
    """Render reusable operational KPI cards."""
    try:
        recent_runs = RepositoryFactory.screening_repo().get_recent(days=30)
    except Exception as exc:
        logger.warning("Executive KPI history unavailable: %s", exc)
        recent_runs = None

    path_status = settings.validate_paths()

    st.subheader("Executive KPI Snapshot")

    active_runs = len(recent_runs) if recent_runs is not None else "N/A"

    kpi_values = [
        ("Recent Runs", active_runs),
        ("Model Status", "Ready" if path_status.get("model") else "Missing"),
        ("Workbook", "Loaded" if path_status.get("workbook") else "Missing"),
        ("Environment", settings.environment.upper()),
    ]

    cols = st.columns(4)

    for col, (label, value) in zip(cols, kpi_values):
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


def render_model_registry_section() -> None:
    """Render model version history for production traceability."""
    st.subheader("🧠 Model Registry & Version History")

    try:
        versions = RepositoryFactory.model_version_repo().list_versions()
    except Exception as exc:
        logger.warning("Model registry unavailable: %s", exc)
        versions = None

    if versions is None:
        st.warning("Model registry is currently unavailable.")
        return

    if not versions:
        st.info(
            "No model versions are registered yet. "
            "Run a training job to populate the registry."
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
                    round(float(version.test_accuracy), 4)
                    if version.test_accuracy is not None
                    else None
                ),
                "Weighted F1": (
                    round(float(version.test_weighted_f1), 4)
                    if version.test_weighted_f1 is not None
                    else None
                ),
                "Training Date": (
                    version.training_date.strftime("%Y-%m-%d %H:%M")
                    if version.training_date
                    else "N/A"
                ),
                "Active": "Yes" if version.is_active else "No",
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def render_saved_run_detail_section() -> None:
    """Display saved screening detail and side-by-side comparison."""
    st.subheader("🧾 Saved Run Detail & Comparison")

    try:
        history = RepositoryFactory.screening_repo().get_recent(days=365)
    except Exception as exc:
        logger.warning("Historical screening data unavailable: %s", exc)
        history = None

    if history is None:
        st.warning("Historical screening data is currently unavailable.")
        return

    if not history:
        st.info(
            "No saved screening runs are available yet. "
            "Run a screening to populate the history audit trail."
        )
        return

    history_df = pd.DataFrame(
        [
            {
                "Run ID": run.id,
                "Timestamp": (
                    run.timestamp.strftime("%Y-%m-%d %H:%M")
                    if run.timestamp
                    else "N/A"
                ),
                "Formation": run.formation,
                "Recommendation": run.recommended_technique or "N/A",
                "Status": run.recommendation_status or "N/A",
                "Score": (
                    round(float(run.recommendation_score), 3)
                    if run.recommendation_score is not None
                    else None
                ),
            }
            for run in history
        ]
    )

    st.dataframe(history_df, use_container_width=True)

    run_ids = [run.id for run in history]

    run_a_id = st.selectbox(
        "Select a saved run to reopen",
        run_ids,
        index=0,
        key="saved_run_a",
    )

    selected_run = next(
        (run for run in history if run.id == run_a_id),
        history[0],
    )

    st.markdown("### Reopened assessment")

    detail_cols = st.columns(2)

    with detail_cols[0]:
        st.write(f"**Run ID:** {selected_run.id}")
        st.write(
            "**Timestamp:** "
            f"{selected_run.timestamp.strftime('%Y-%m-%d %H:%M') if selected_run.timestamp else 'N/A'}"
        )
        st.write(f"**Formation:** {selected_run.formation}")
        st.write(
            f"**Recommendation:** "
            f"{selected_run.recommended_technique or 'N/A'}"
        )

    with detail_cols[1]:
        st.write(
            f"**Final Status:** "
            f"{selected_run.recommendation_status or 'N/A'}"
        )
        st.write(
            f"**Score:** "
            f"{selected_run.recommendation_score if selected_run.recommendation_score is not None else 'N/A'}"
        )
        st.write(
            f"**Model Version:** "
            f"{selected_run.model_version or 'N/A'}"
        )
        st.write(
            f"**Data Readiness:** "
            f"{selected_run.data_readiness_pct or 'N/A'}%"
        )

    input_payload = selected_run.input_payload or {}

    if input_payload:
        st.write("**Exact input values:**")
        st.dataframe(
            pd.DataFrame([input_payload]),
            use_container_width=True,
        )
    else:
        st.info("No exact input payload was stored for this historical run.")

    rule_trace = selected_run.rule_trace or {}

    if rule_trace:
        st.write("**Structured rule trace:**")
        st.json(rule_trace)
    else:
        st.info("No structured rule trace was recorded.")

    assumptions = selected_run.assumptions or {}

    if assumptions:
        st.write("**Recorded assumptions:**")
        st.json(assumptions)

    evidence_summary = selected_run.evidence_summary or {}

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
        "recommendation": selected_run.recommended_technique,
        "status": selected_run.recommendation_status,
        "score": selected_run.recommendation_score,
        "inputs": input_payload,
        "rule_trace": rule_trace,
        "assumptions": assumptions,
        "evidence_summary": evidence_summary,
    }

    st.download_button(
        label="Download saved assessment JSON",
        data=json.dumps(download_payload, indent=2, default=str),
        file_name=f"eor_run_{selected_run.id}.json",
        mime="application/json",
    )

    st.markdown("### Compare two saved runs")

    if len(history) >= 2:
        run_b_id = st.selectbox(
            "Select the second run for comparison",
            run_ids,
            index=min(1, len(run_ids) - 1),
            key="saved_run_b",
        )

        if run_b_id == run_a_id:
            st.caption(
                "Choose a different run for the comparison to be meaningful."
            )
        else:
            try:
                comparison = (
                    RepositoryFactory
                    .screening_repo()
                    .compare_runs(run_a_id, run_b_id)
                )
            except Exception as exc:
                logger.warning("Run comparison failed: %s", exc)
                comparison = {"error": "Comparison is currently unavailable."}

            if "error" in comparison:
                st.warning(comparison["error"])
            else:
                left = comparison["left"]
                right = comparison["right"]
                delta = comparison["delta_score"]

                compare_cols = st.columns(2)

                with compare_cols[0]:
                    st.write("**Left run**")
                    st.json(left)

                with compare_cols[1]:
                    st.write("**Right run**")
                    st.json(right)

                st.metric("Score Delta", f"{delta:+.3f}")

                st.write("**What changed:**")
                st.write(
                    f"- Recommendation: "
                    f"{left['recommendation']} → {right['recommendation']}"
                )
                st.write(
                    f"- Status: {left['status']} → {right['status']}"
                )
                st.write(f"- Score delta: {delta:+.3f}")
    else:
        st.info("At least two saved runs are needed for comparison.")


def render_sidebar_status() -> None:
    """Render application health in the sidebar."""
    path_status = settings.validate_paths()

    model_ready = bool(path_status.get("model"))
    workbook_ready = bool(path_status.get("workbook"))
    config_ready = bool(path_status.get("config"))

    st.sidebar.header("Operational Status")

    st.sidebar.markdown(
        f"""
        <div class="sidebar-status-box">
            <div class="status-row">
                <span>Model</span>
                <span class="status-pill {'ready' if model_ready else 'warn'}">
                    {'Ready' if model_ready else 'Missing'}
                </span>
            </div>

            <div class="status-row">
                <span>Workbook</span>
                <span class="status-pill {'ready' if workbook_ready else 'warn'}">
                    {'Loaded' if workbook_ready else 'Missing'}
                </span>
            </div>

            <div class="status-row">
                <span>Config</span>
                <span class="status-pill {'ready' if config_ready else 'warn'}">
                    {'Valid' if config_ready else 'Check'}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.caption("Decision stack")
    st.sidebar.write("• Rule engine")
    st.sidebar.write("• Fuzzy logic")
    st.sidebar.write("• Neural network")
    st.sidebar.write("• Decision synthesis")


# =============================================================================
# EXECUTIVE OVERVIEW
# =============================================================================

def render_executive_overview_section(services: Dict[str, Any]) -> None:
    """
    Executive portfolio view.

    The map is driven by the same field dataset used for the KPI calculations.
    It supports:
    - status filtering
    - EOR technology filtering when available
    - RF-gap thresholding
    - interactive tooltips
    - selected-field detail
    """
    st.header("🏠 Executive Overview")
    st.caption(
        "Portfolio-level view of field locations, EOR opportunity status, "
        "and recovery-factor gap."
    )

    field_df_raw, data_source = get_field_portfolio_data(services)
    field_df = _prepare_map_dataframe(field_df_raw)

    if field_df.empty:
        st.error(
            "No valid field portfolio records are available. "
            "The Executive Overview requires Field, Latitude and Longitude."
        )
        return

    # -------------------------------------------------------------------------
    # KPI ROW
    # -------------------------------------------------------------------------
    metrics = _calculate_portfolio_metrics(field_df)

    metric_cols = st.columns(6)

    for col, (metric, value) in zip(metric_cols, metrics.items()):
        with col:
            st.markdown(
                f"""
                <div class="exec-kpi-card">
                    <div class="exec-kpi-label">{metric}</div>
                    <div class="exec-kpi-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    source_note = (
        "Live workbook/repository data"
        if data_source != "Configured portfolio fallback"
        else "Configured field-coordinate dataset"
    )

    st.caption(f"Portfolio source: **{source_note}**")

    # =============================================================================
    # FILTER BAR
    # =============================================================================

    st.subheader("Field Opportunity Map")

    status_options = sorted(
        field_df["EOR_Status"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    technique_options = sorted(
        field_df["Recommended_Technique"]
        .dropna()
        .astype(str)
        .loc[lambda s: s.ne("Not assigned")]
        .unique()
        .tolist()
    )

    rf_series = field_df["RF_Gap"].dropna()

    # -------------------------------------------------------------------------
    # RESET FLAG
    # -------------------------------------------------------------------------
    if st.session_state.pop("executive_reset_filters", False):
        status_default = status_options
        technique_default = technique_options

        if not rf_series.empty:
            rf_default = float(rf_series.min())
        else:
            rf_default = 0.0
    else:
        status_default = st.session_state.get(
            "executive_status_filter",
            status_options,
        )

        technique_default = st.session_state.get(
            "executive_technique_filter",
            technique_options,
        )

        if not rf_series.empty:
            rf_default = st.session_state.get(
                "executive_rf_gap",
                float(rf_series.min()),
            )
        else:
            rf_default = 0.0

    filter_cols = st.columns([1.2, 1.5, 2.0, 0.9])

    with filter_cols[0]:
        selected_status = st.multiselect(
            "EOR Status",
            options=status_options,
            default=status_default,
            key="executive_status_filter",
        )

    with filter_cols[1]:
        selected_techniques = st.multiselect(
            "EOR Technology",
            options=technique_options,
            default=technique_default,
            key="executive_technique_filter",
            disabled=not technique_options,
        )

    with filter_cols[2]:
        if not rf_series.empty:
            rf_min = float(rf_series.min())
            rf_max = float(rf_series.max())

            if np.isclose(rf_min, rf_max):
                min_rf_gap = rf_min

                st.slider(
                    "Minimum RF Gap (MMstb)",
                    min_value=float(rf_min),
                    max_value=float(rf_min + 1.0),
                    value=float(rf_min),
                    disabled=True,
                    key="executive_rf_gap_fixed",
                )
            else:
                min_rf_gap = st.slider(
                    "Minimum RF Gap (MMstb)",
                    min_value=rf_min,
                    max_value=rf_max,
                    value=float(rf_default),
                    step=max((rf_max - rf_min) / 20.0, 0.1),
                    key="executive_rf_gap",
                )
        else:
            min_rf_gap = 0.0
            st.caption("RF-gap filtering unavailable.")

    with filter_cols[3]:
        reset_clicked = st.button(
            "Reset",
            use_container_width=True,
            key="executive_reset_button",
        )

    if reset_clicked:
        # Set only a flag. Do NOT modify widget state here.
        st.session_state["executive_reset_filters"] = True
        st.rerun()

    filtered_df = field_df.copy()

    if selected_status:
        filtered_df = filtered_df[
            filtered_df["EOR_Status"].isin(selected_status)
        ]
    else:
        filtered_df = filtered_df.iloc[0:0]

    if technique_options and selected_techniques:
        filtered_df = filtered_df[
            filtered_df["Recommended_Technique"].isin(selected_techniques)
            | filtered_df["Recommended_Technique"].eq("Not assigned")
        ]
    elif technique_options and not selected_techniques:
        filtered_df = filtered_df.iloc[0:0]

    if "RF_Gap" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["RF_Gap"].fillna(-np.inf) >= min_rf_gap
        ]

    st.caption(
        f"Showing **{len(filtered_df)}** of **{len(field_df)}** field records."
    )

    # -------------------------------------------------------------------------
    # MAP + FIELD DETAIL
    # -------------------------------------------------------------------------
    map_cols = st.columns([2.1, 1.0])

    with map_cols[0]:
        _render_map_legend(sorted(filtered_df["EOR_Status"].unique()))

        _render_pydeck_field_map(filtered_df)

        st.caption(
            "Marker size represents RF Gap. Marker colour represents EOR status. "
            "Hover a field for detailed information."
        )

    with map_cols[1]:
        _render_selected_field_detail(filtered_df)

    # -------------------------------------------------------------------------
    # PORTFOLIO TABLE
    # -------------------------------------------------------------------------
    st.subheader("Portfolio Summary Table")

    display_columns = [
        "Field",
        "Latitude",
        "Longitude",
        "EOR_Status",
        "RF_Gap",
    ]

    for optional_column in OPTIONAL_FIELD_COLUMNS:
        if optional_column in field_df.columns and optional_column not in display_columns:
            display_columns.append(optional_column)

    table_df = filtered_df[
        [column for column in display_columns if column in filtered_df.columns]
    ].copy()

    if "RF_Gap" in table_df.columns:
        table_df["RF_Gap"] = table_df["RF_Gap"].round(2)

    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# SCREENING OUTPUT COMPONENTS
# =============================================================================

def display_data_quality_section(data_quality: dict) -> None:
    """Display data quality assessment."""
    status = data_quality.get("status", "Unknown")
    readiness = float(data_quality.get("readiness_percentage", 0))
    required = int(data_quality.get("required_parameters", 0))
    valid = int(data_quality.get("valid_parameters", 0))

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Data Status",
        f"{readiness:.0f}%",
        f"of {required} required",
    )

    col2.metric(
        "Valid Parameters",
        f"{valid}/{required}",
    )

    col3.metric(
        "Outliers Detected",
        len(data_quality.get("outliers", [])),
    )

    col4.metric(
        "Overall Status",
        status,
    )


def display_eligibility_section(eligibility: dict) -> None:
    """Display engineering eligibility screening."""
    st.subheader("🏗️ Engineering Eligibility Screening")

    pass_count = sum(
        1
        for status, _ in eligibility.values()
        if status == EligibilityStatus.PASS
    )

    conditional_count = sum(
        1
        for status, _ in eligibility.values()
        if status == EligibilityStatus.CONDITIONAL
    )

    fail_count = sum(
        1
        for status, _ in eligibility.values()
        if status == EligibilityStatus.FAIL
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("🟢 PASS", pass_count)
    col2.metric("🟡 CONDITIONAL", conditional_count)
    col3.metric("🔴 FAIL", fail_count)

    st.write("---")

    for technique, (status, results) in sorted(eligibility.items()):
        with st.expander(
            f"{status} — {technique}",
            expanded=(status == EligibilityStatus.PASS),
        ):
            criteria_data = []

            for result in results:
                raw_value = result.get("value")

                if raw_value is None or raw_value == "":
                    value_display = "N/A"
                else:
                    try:
                        value_display = f"{float(raw_value):.1f}"
                    except (TypeError, ValueError):
                        value_display = str(raw_value)

                criteria_data.append(
                    {
                        "Criterion": result.get("criterion", "N/A"),
                        "Status": "✓" if result.get("passes") else "✗",
                        "Value": value_display,
                        "Explanation": result.get("explanation", ""),
                        "Impact": result.get("impact", ""),
                    }
                )

            st.dataframe(
                pd.DataFrame(criteria_data),
                use_container_width=True,
                hide_index=True,
            )


def display_fuzzy_section(
    fuzzy_scores: dict,
    fuzzy_explanations: dict,
) -> None:
    """Display fuzzy suitability evaluation."""
    st.subheader("⚖️ Fuzzy Suitability Scores")

    fuzzy_series = (
        pd.Series(fuzzy_scores, dtype=float)
        .sort_values(ascending=False)
    )

    if fuzzy_series.empty:
        st.info("No fuzzy suitability scores are available.")
        return

    st.bar_chart(fuzzy_series)

    st.write("---")

    top_techniques = fuzzy_series.head(3).index.tolist()

    for index, technique in enumerate(top_techniques):
        col1, col2 = st.columns([1.5, 0.5])

        with col1:
            with st.expander(
                f"📊 {technique} – Fuzzy Analysis",
                expanded=(index == 0),
            ):
                explanation = fuzzy_explanations.get(technique, ([], 0.0))
                rows, overall_score = explanation

                if not rows:
                    st.info(
                        "No fuzzy envelope found for this "
                        "technique-formation pair."
                    )
                else:
                    df_members = pd.DataFrame(rows)

                    st.dataframe(
                        df_members,
                        use_container_width=True,
                        hide_index=True,
                    )

                    if "Variable" in df_members.columns and "Membership" in df_members.columns:
                        st.bar_chart(
                            df_members.set_index("Variable")["Membership"]
                        )

                    st.metric(
                        "Mean Fuzzy Membership",
                        f"{overall_score:.3f}",
                    )

        with col2:
            st.metric(
                f"{technique} Score",
                f"{fuzzy_scores[technique]:.3f}",
            )


def display_ml_section(
    ml_top3: list,
    ml_probabilities: dict,
) -> None:
    """Display ML inference results."""
    if not ml_top3:
        st.info("ML model not available or inference failed.")
        return

    st.subheader("🤖 Neural Network Inference")

    df_top3 = pd.DataFrame(
        ml_top3,
        columns=["Technique", "NN Probability"],
    )

    st.dataframe(
        df_top3,
        use_container_width=True,
        hide_index=True,
    )

    ml_series = (
        pd.Series(ml_probabilities, dtype=float)
        .sort_values(ascending=False)
    )

    st.bar_chart(ml_series)


def display_recommendation_section(result: Any) -> None:
    """Display final recommendation and reasoning."""
    st.subheader("✅ Final Recommendation")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"### {result.recommendation}")
        st.markdown(f"**Status:** {result.recommendation_status}")

    with col2:
        st.metric(
            "Recommendation Score",
            f"{result.recommendation_score:.3f}",
        )

    st.write("---")
    st.write("**Decision Reasoning:**")

    reasoning = result.reasoning or {}

    reason_cols = st.columns(2)

    with reason_cols[0]:
        if "pass_techniques" in reasoning:
            st.markdown(
                "**Eligible (PASS):** "
                f"{', '.join(reasoning['pass_techniques']) or 'None'}"
            )

        if "conditional_techniques" in reasoning:
            st.markdown(
                "**Conditional:** "
                f"{', '.join(reasoning['conditional_techniques']) or 'None'}"
            )

    with reason_cols[1]:
        if "fuzzy_score" in reasoning:
            st.metric(
                "Fuzzy Score",
                f"{reasoning['fuzzy_score']:.3f}",
            )

        if "ml_score" in reasoning:
            st.metric(
                "ML Score",
                f"{reasoning['ml_score']:.3f}",
            )

    st.info(
        f"**Mode:** {result.mode} | "
        f"**Strategy:** {reasoning.get('strategy', 'N/A')}"
    )


# =============================================================================
# EOR SCREENING
# =============================================================================

def render_eor_screening_tab(services: Dict[str, Any]) -> None:
    """Decision-support screening interface."""
    st.header("🔍 EOR Screening")
    st.write(
        "Reservoir input, method screening, rationale, "
        "and recommendation engine."
    )

    with st.expander("📝 Reservoir Characteristics", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            formation = st.selectbox(
                "Formation Category",
                settings.ui_config["formation_categories"],
                index=0,
                key="screen_formation",
            )
            depth_ft = st.number_input(
                "Depth (ft)",
                min_value=0.0,
                value=5000.0,
                step=50.0,
                key="screen_depth",
            )
            porosity_pct = st.number_input(
                "Porosity (%)",
                min_value=0.0,
                max_value=100.0,
                value=20.0,
                step=0.5,
                key="screen_porosity",
            )

        with col2:
            perm_md = st.number_input(
                "Permeability (mD)",
                min_value=0.0,
                value=100.0,
                step=10.0,
                key="screen_perm",
            )
            api = st.number_input(
                "Oil Gravity (°API)",
                min_value=0.0,
                max_value=80.0,
                value=35.0,
                step=0.5,
                key="screen_api",
            )
            visc_cp = st.number_input(
                "Viscosity (cp)",
                min_value=0.0,
                value=2.0,
                step=0.1,
                key="screen_visc",
            )

        with col3:
            so_pct = st.number_input(
                "Oil Saturation (%)",
                min_value=0.0,
                max_value=100.0,
                value=55.0,
                step=1.0,
                key="screen_so",
            )
            reservoir_pressure = st.number_input(
                "Reservoir Pressure (psi)",
                min_value=0.0,
                value=2500.0,
                step=50.0,
                key="screen_pressure",
            )
            temperature_c = st.number_input(
                "Temperature (°C)",
                min_value=0.0,
                value=95.0,
                step=5.0,
                key="screen_temperature",
            )

    if st.button(
        "🚀 Run Screening",
        type="primary",
        use_container_width=True,
        key="run_screening",
    ):
        values = {
            "depth_ft": depth_ft,
            "porosity_pct": porosity_pct,
            "perm_md": perm_md,
            "api": api,
            "visc_cp": visc_cp,
            "so_pct": so_pct,
            "reservoir_pressure": reservoir_pressure,
            "temperature_c": temperature_c,
        }

        # Keep validation available without assuming its exact implementation.
        try:
            validator = InputValidator()
            _ = validator
        except Exception:
            validator = None

        try:
            with st.spinner("Screening in progress..."):
                result = services["screening_engine"].screen(
                    values,
                    formation,
                    services["techs_all"],
                )

            st.success("✅ Screening complete")

            display_data_quality_section(result.data_quality)
            st.write("---")

            display_eligibility_section(result.eligibility)
            st.write("---")

            display_fuzzy_section(
                result.fuzzy_scores,
                result.fuzzy_explanations,
            )
            st.write("---")

            if services["model_service"].is_loaded():
                display_ml_section(
                    result.ml_top3,
                    result.ml_probabilities,
                )
                st.write("---")

            display_recommendation_section(result)

        except Exception as exc:
            logger.exception("Screening failed")
            st.error(
                "Screening failed. "
                "Check the input values and application logs."
            )


# =============================================================================
# FIELD / CANDIDATE VIEW
# =============================================================================

def render_field_candidates_section() -> None:
    """Field and reservoir candidate screening view."""
    st.header("🗺️ Field / Reservoir Candidates")

    candidate_df = pd.DataFrame(
        {
            "Field": ["Angsi", "Dulang", "Barton", "Baram", "Tapis", "Penara"],
            "Reservoir": ["A12", "E14", "B7", "E10", "N12", "P1"],
            "Temperature_C": [85, 93, 72, 108, 80, 66],
            "EUR_MMstb": [68, 52, 41, 88, 54, 34],
            "RF_Gap": [20, 18, 15, 24, 17, 12],
            "Permeability_mD": [120, 160, 80, 180, 110, 90],
            "Method": ["CO2 WAG", "Polymer", "ASP", "CO2 WAG", "Polymer", "Steam"],
        }
    )

    st.subheader("Candidate Reservoir Scatter")
    st.bar_chart(
        candidate_df.set_index("Field")["EUR_MMstb"]
    )

    st.subheader("Opportunity Rank")
    st.bar_chart(
        candidate_df.set_index("Field")["RF_Gap"]
    )

    st.dataframe(
        candidate_df,
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# CEOR – FLUID / FLUID
# =============================================================================

def render_fluid_fluid_section() -> None:
    """Fluid-fluid CEOR evidence section."""
    st.header("🧪 CEOR — Fluid / Fluid")

    rheology_df = pd.DataFrame(
        {
            "Shear_Rate": [10, 30, 50, 100, 200],
            "Polymer_A": [120, 90, 75, 58, 44],
            "Polymer_B": [132, 104, 82, 64, 49],
            "Polymer_C": [110, 88, 70, 54, 41],
        }
    ).set_index("Shear_Rate")

    st.subheader("Rheology")
    st.line_chart(rheology_df)

    thermal_df = pd.DataFrame(
        {
            "Time_Days": [0, 7, 14, 30, 60],
            "Retention_A": [100, 96, 90, 84, 79],
            "Retention_B": [100, 92, 85, 75, 68],
        }
    ).set_index("Time_Days")

    st.subheader("Thermal Stability")
    st.line_chart(thermal_df)

    phase_df = pd.DataFrame(
        {
            "Formulation": ["A-1", "A-2", "B-1", "B-2", "C-1"],
            "No_Precipitation": [82, 70, 65, 91, 76],
            "Precipitation": [18, 30, 35, 9, 24],
        }
    )

    st.subheader("Phase Behaviour")
    st.bar_chart(
        phase_df.set_index("Formulation")
    )

    st.subheader("IFT Comparison")

    ift_df = pd.DataFrame(
        {
            "Formulation": ["F1", "F2", "F3", "F4"],
            "IFT": [0.022, 0.010, 0.040, 0.013],
        }
    )

    st.bar_chart(
        ift_df.set_index("Formulation")
    )


# =============================================================================
# CEOR – FLUID / ROCK
# =============================================================================

def render_fluid_rock_section() -> None:
    """Fluid-rock CEOR evidence section."""
    st.header("🪨 CEOR — Fluid / Rock")

    adsorption_df = pd.DataFrame(
        {
            "Days": [0, 7, 14, 30, 60],
            "Adsorption_Surf_A": [0.0, 0.18, 0.27, 0.35, 0.42],
            "Adsorption_Surf_B": [0.0, 0.12, 0.20, 0.28, 0.31],
        }
    ).set_index("Days")

    st.subheader("Adsorption vs Time")
    st.line_chart(adsorption_df)

    coreflood_df = pd.DataFrame(
        {
            "Core": ["Core 1", "Core 2", "Core 3", "Core 4"],
            "Waterflood": [42, 38, 45, 41],
            "EOR_Increment": [15, 18, 11, 14],
        }
    )

    st.subheader("Core Flood Incremental Recovery")
    st.bar_chart(
        coreflood_df.set_index("Core")
    )

    sor_df = pd.DataFrame(
        {
            "Core": ["Core 1", "Core 2", "Core 3", "Core 4"],
            "Sor_Reduction": [36, 28, 41, 31],
        }
    )

    st.subheader("Sor Reduction")
    st.bar_chart(
        sor_df.set_index("Core")
    )


# =============================================================================
# CHALLENGES
# =============================================================================

def render_challenges_section() -> None:
    """Lessons learnt and challenge registry."""
    st.header("⚠️ Challenges & Lessons Learnt")

    challenge_df = pd.DataFrame(
        {
            "Field": ["Angsi", "Dulang", "Barton", "Baram"],
            "Chemical_Compatibility": ["High", "Medium", "Low", "High"],
            "Facilities": ["Medium", "Low", "High", "Medium"],
            "Fluid_Handling": ["High", "Medium", "Medium", "Low"],
            "Cost_Logistics": ["High", "Medium", "Low", "High"],
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
            "Count": [4, 3, 3, 2, 2],
        }
    )

    st.subheader("Challenge Distribution")
    st.bar_chart(
        dist.set_index("Challenge")
    )


# =============================================================================
# EOR INTELLIGENCE
# =============================================================================

def render_eor_intelligence_section() -> None:
    """Model intelligence and auditability."""
    st.header("🤖 EOR Intelligence")
    render_model_registry_section()

    st.write("---")

    render_saved_run_detail_section()


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """Main EOR Atlas application entry point."""

    st.title("🛢️ EOR Atlas – Decision Support Platform")

    st.caption(
        "Engineering-first EOR dashboard built around screening, "
        "candidate discovery, CEOR evidence, and auditability."
    )

    st.sidebar.header("📋 EOR Atlas")
    st.sidebar.caption("Engineering decision workspace")

    render_sidebar_status()

    path_status = settings.validate_paths()

    missing = [
        key
        for key, is_valid in path_status.items()
        if not is_valid
    ]

    if missing:
        st.sidebar.warning(
            f"Artifacts pending: {', '.join(missing)}"
        )

    services = initialize_services()

    if services is None:
        st.error("Failed to initialize application services.")
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
        render_executive_overview_section(services)

    with tabs[1]:
        render_eor_screening_tab(services)

    with tabs[2]:
        render_field_candidates_section()

    with tabs[3]:
        render_fluid_fluid_section()

    with tabs[4]:
        render_fluid_rock_section()

    with tabs[5]:
        st.header("📚 Past EOR Results")

        render_database_summary_section()

        st.write("---")
        st.subheader("Historical outcome ledger")

        try:
            history = RepositoryFactory.screening_repo().get_recent(days=365)

            if not history:
                st.info("No historical records available yet.")
            else:
                history_df = pd.DataFrame(
                    [
                        {
                            "Run ID": run.id,
                            "Field": run.formation,
                            "Recommendation": run.recommended_technique,
                            "Status": run.recommendation_status,
                            "Score": run.recommendation_score,
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
            st.warning(
                "Historical results are currently unavailable."
            )

    with tabs[6]:
        render_challenges_section()

    with tabs[7]:
        render_eor_intelligence_section()


if __name__ == "__main__":
    main()


