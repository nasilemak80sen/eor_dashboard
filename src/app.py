import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st
from tensorflow import keras

# -----------------------------
# CONFIG PATHS
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

MODEL_DIR = ROOT_DIR / "outputs" / "model_artifacts"
DATA_DIR = ROOT_DIR / "data"
WORKBOOK_PATH = ROOT_DIR / "EOR_Screening_Tool_2026.xlsx"

MODEL_PATH = MODEL_DIR / "eor_nn_alpha03.keras"
SCALER_PATH = MODEL_DIR / "scaler_alpha03.joblib"
LE_PATH = MODEL_DIR / "label_encoder.joblib"
CFG_PATH = MODEL_DIR / "config_alpha03.json"
RANGES_PATH = DATA_DIR / "NeuroFuzzy_EOR_Extracted_Tables.xlsx"
RANGES_SHEET = "Table1_Ranges"


# -----------------------------
# Streamlit page configuration
# -----------------------------
st.set_page_config(page_title="EOR Atlas Dashboard", page_icon="🛢️", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    .stAlert > div { border-radius: 12px; }
    .metric-card { background: linear-gradient(135deg, #0f172a, #1e293b); padding: 1rem 1.2rem; border-radius: 14px; color: white; }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# MODEL & DATA LOADERS
# -----------------------------
@st.cache_resource
def load_artifacts():
    model = keras.models.load_model(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    le = joblib.load(LE_PATH)
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return model, scaler, le, cfg


def norm_tech(x):
    if pd.isna(x):
        return np.nan
    x = str(x).strip().replace("CO22", "CO2").replace("*", "")
    return x


def norm_form(x):
    if pd.isna(x):
        return np.nan
    x = str(x).strip().lower()
    if "sandstone" in x:
        return "Sandstone"
    if "unconsolidated" in x:
        return "Unconsolidated sands"
    if "carbonate" in x:
        return "Carbonates"
    return np.nan


@st.cache_data
def load_env():
    table1 = pd.read_excel(RANGES_PATH, sheet_name=RANGES_SHEET, engine="openpyxl")
    table1["technique"] = table1["EOR technique"].apply(norm_tech)
    table1["formation_category"] = table1["Formation type"].apply(norm_form)
    table1 = table1.dropna(subset=["technique", "formation_category"]).copy()

    env = {}
    for _, row in table1.iterrows():
        key = (row["technique"], row["formation_category"])
        env[key] = {
            "depth": (row["Depth min (ft)"], row["Depth max (ft)"]),
            "por": (row["Porosity min (%)"], row["Porosity max (%)"]),
            "perm": (row["Permeability min (mD)"], row["Permeability max (mD)"]),
            "api": (row["Oil gravity min (°API)"], row["Oil gravity max (°API)"]),
            "visc": (row["Oil viscosity min (cp)"], row["Oil viscosity max (cp)"]),
            "so": (row["So at start min (%)"], row["So at start max (%)"]),
        }
    techs_all = sorted(set(key[0] for key in env.keys()))
    return env, techs_all


@st.cache_data
def load_workbook_sheets():
    if not WORKBOOK_PATH.exists():
        return {}

    sheets = {}
    excel_file = pd.ExcelFile(WORKBOOK_PATH, engine="openpyxl")
    for sheet_name in excel_file.sheet_names:
        try:
            df = pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
        except Exception:
            df = pd.DataFrame({"sheet": [sheet_name], "note": ["Unable to load sheet automatically"]})
        sheets[sheet_name] = df
    return sheets


def trap_membership(x, lower, upper, alpha=0.3):
    if pd.isna(x) or pd.isna(lower) or pd.isna(upper):
        return 0.0
    if upper == lower:
        return 1.0 if x == lower else 0.0

    width = upper - lower
    left = lower - alpha * width
    right = upper + alpha * width

    if x <= left or x >= right:
        return 0.0
    if lower <= x <= upper:
        return 1.0
    if left < x < lower:
        return (x - left) / (lower - left)
    return (right - x) / (right - upper)


def fuzzy_score_one(env, technique, formation, values, alpha=0.3):
    key = (technique, formation)
    if key not in env:
        return 0.0

    row = env[key]
    memberships = [
        trap_membership(values["depth_ft"], *row["depth"], alpha=alpha),
        trap_membership(values["porosity_pct"], *row["por"], alpha=alpha),
        trap_membership(values["perm_md"], *row["perm"], alpha=alpha),
        trap_membership(values["api"], *row["api"], alpha=alpha),
        trap_membership(values["visc_cp"], *row["visc"], alpha=alpha),
        trap_membership(values["so_pct"], *row["so"], alpha=alpha),
    ]
    return float(np.mean(memberships))


def compute_fuzzy_scores(env, techs_all, formation, values, alpha=0.3):
    scores = {}
    for technique in techs_all:
        scores[technique] = fuzzy_score_one(env, technique, formation, values, alpha=alpha)
    return scores


def fuzzy_explain_one(env, technique, formation, values, alpha=0.3):
    key = (technique, formation)
    if key not in env:
        return None

    row = env[key]
    parts = {
        "Depth (ft)": (values["depth_ft"], *row["depth"]),
        "Porosity (%)": (values["porosity_pct"], *row["por"]),
        "Permeability (mD)": (values["perm_md"], *row["perm"]),
        "API (°API)": (values["api"], *row["api"]),
        "Viscosity (cp)": (values["visc_cp"], *row["visc"]),
        "So (%)": (values["so_pct"], *row["so"]),
    }

    rows = []
    memberships = []
    for var, (val, lower, upper) in parts.items():
        membership = trap_membership(val, lower, upper, alpha=alpha)
        memberships.append(membership)
        rows.append(
            {
                "Variable": var,
                "Input": val,
                "Range_Min": lower,
                "Range_Max": upper,
                "Membership": float(membership),
            }
        )
    return rows, float(np.mean(memberships))


def build_features_for_nn(values, formation, techs_all, fuzzy_scores):
    depth_mid = values["depth_ft"]
    por_mid = values["porosity_pct"]
    perm_mid = values["perm_md"]
    api_mid = values["api"]
    visc_mid = values["visc_cp"]
    so_mid = values["so_pct"]

    depth_span = por_span = perm_span = api_span = visc_span = so_span = 0.0

    eps = 1e-6
    numeric = np.array(
        [
            depth_mid,
            por_mid,
            perm_mid,
            api_mid,
            visc_mid,
            so_mid,
            depth_span,
            por_span,
            perm_span,
            api_span,
            visc_span,
            so_span,
            np.log10(max(perm_mid, 0.0) + eps),
            np.log10(max(visc_mid, 0.0) + eps),
            np.log10(perm_span + 1.0 + eps),
            np.log10(visc_span + 1.0 + eps),
        ],
        dtype=float,
    )

    form_names = ["Sandstone", "Carbonates", "Unconsolidated sands"]
    form_onehot = np.array([1.0 if formation == name else 0.0 for name in form_names], dtype=float)
    fuzzy_vec = np.array([fuzzy_scores.get(t, 0.0) for t in techs_all], dtype=float)
    return np.concatenate([numeric, form_onehot, fuzzy_vec], axis=0)


def predict_case(model, scaler, label_encoder, env, techs_all, values, formation, alpha=0.3, rare_override=True, rare_threshold=0.90, nn_conf_threshold=0.60):
    fuzzy_scores = compute_fuzzy_scores(env, techs_all, formation, values, alpha=alpha)
    features = build_features_for_nn(values, formation, techs_all, fuzzy_scores)
    scaled_features = scaler.transform([features])
    probabilities = model.predict(scaled_features, verbose=0)[0]

    nn_idx = int(np.argmax(probabilities))
    nn_label = label_encoder.inverse_transform([nn_idx])[0]
    nn_conf = float(np.max(probabilities))

    top3_idx = np.argsort(probabilities)[-3:][::-1]
    top3 = [(label_encoder.inverse_transform([idx])[0], float(probabilities[idx])) for idx in top3_idx]

    mode = "NN"
    final_label = nn_label
    final_score = nn_conf

    if rare_override:
        rare_candidates = ["Hot water", "Miscible acid gas"]
        best_rare = None
        best_rare_score = -1.0
        for candidate in rare_candidates:
            score = fuzzy_scores.get(candidate, 0.0)
            if score > best_rare_score:
                best_rare_score = score
                best_rare = candidate

        if best_rare is not None and best_rare_score >= rare_threshold and nn_conf < nn_conf_threshold:
            final_label = best_rare
            final_score = best_rare_score
            mode = "FUZZY_RARE_OVERRIDE"

    return {
        "final_label": final_label,
        "final_score": final_score,
        "mode": mode,
        "nn_label": nn_label,
        "nn_conf": nn_conf,
        "top3": top3,
        "fuzzy_scores": fuzzy_scores,
    }


# -----------------------------
# UI
# -----------------------------
model, scaler, label_encoder, config = load_artifacts()
env, techs_all = load_env()
workbook_sheets = load_workbook_sheets()
alpha = config.get("alpha", 0.30)

st.title("🛢️ EOR Atlas Screening & Reports Dashboard")
st.caption("Separate AI/ML screening, workbook reporting, and lab data charts in dedicated tabs.")

st.sidebar.header("EOR Atlas Dashboard")
st.sidebar.write("Navigate using the tabs to view AI screening, workbook reports, and data charts.")
if WORKBOOK_PATH.exists():
    st.sidebar.success("Workbook loaded successfully.")
else:
    st.sidebar.warning("Workbook not found. Place EOR_Screening_Tool_2026.xlsx in the app root.")


def display_sheet(sheet_name, max_rows=200):
    df = workbook_sheets.get(sheet_name)
    if df is None:
        st.info(f"Sheet '{sheet_name}' is not available in the workbook.")
        return None
    st.write(f"**Sheet:** {sheet_name}")
    if df.empty:
        st.write("This sheet is empty.")
        return df
    st.dataframe(df.head(max_rows), use_container_width=True)
    return df


def chart_numeric_columns(df, title="Numeric chart"):
    numeric = df.select_dtypes(include=["number"])
    if numeric.shape[1] == 0:
        return
    st.write(f"**{title}**")
    st.line_chart(numeric)


def render_screening_picker(sheet_name):
    df = workbook_sheets.get(sheet_name)
    if df is None:
        st.info(f"Sheet '{sheet_name}' is not available.")
        return
    st.dataframe(df, use_container_width=True)
    if sheet_name == "Screening":
        if "EOR Type" in df.columns and "Score (%)" in df.columns:
            st.bar_chart(df.set_index("EOR Type")["Score (%)"].fillna(0))
    if sheet_name == "Ranking":
        if "EOR Type" in df.columns and "Score (%)" in df.columns:
            st.bar_chart(df.set_index("EOR Type")["Score (%)"].fillna(0))
    if sheet_name == "RF_EUR_Ranges":
        if "EOR Type" in df.columns and "EUR P50 (MMstb)" in df.columns:
            st.bar_chart(df.set_index("EOR Type")["EUR P50 (MMstb)"].fillna(0))


main_tabs = st.tabs(["AI/ML Screening", "Excel Reports", "Data & Charts", "Workbook Explorer"])

with main_tabs[0]:
    st.header("AI / ML Screening")
    st.write("Run the neural-network and fuzzy screening function separately from the workbook report tabs.")

    with st.expander("Screening inputs"):
        formation_category = st.selectbox("Formation category", ["Sandstone", "Carbonates", "Unconsolidated sands"], index=0)
        depth_ft = st.number_input("Depth (ft)", min_value=0.0, value=5000.0, step=50.0)
        porosity_pct = st.number_input("Porosity (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
        perm_md = st.number_input("Permeability (mD)", min_value=0.0, value=100.0, step=10.0)
        api = st.number_input("Oil gravity (°API)", min_value=0.0, max_value=80.0, value=35.0, step=0.5)
        visc_cp = st.number_input("Viscosity (cp)", min_value=0.0, value=2.0, step=0.1)
        so_pct = st.number_input("Oil saturation at start (%)", min_value=0.0, max_value=100.0, value=55.0, step=1.0)
        st.divider()
        rare_override = st.checkbox("Enable rare-class fuzzy override", value=True)
        rare_threshold = st.slider("Rare override threshold", 0.50, 1.00, 0.90, 0.01)
        nn_conf_threshold = st.slider("NN confidence threshold", 0.10, 0.95, 0.60, 0.05)

        preset = st.selectbox("Load a sample case", ["Default", "Sandstone - high porosity", "Carbonate - low permeability", "Unconsolidated sands - heavy oil"], index=0)
        if st.button("Apply preset"):
            presets = {
                "Default": {"depth_ft": 5000.0, "porosity_pct": 20.0, "perm_md": 100.0, "api": 35.0, "visc_cp": 2.0, "so_pct": 55.0},
                "Sandstone - high porosity": {"depth_ft": 4500.0, "porosity_pct": 28.0, "perm_md": 180.0, "api": 38.0, "visc_cp": 1.2, "so_pct": 62.0},
                "Carbonate - low permeability": {"depth_ft": 7000.0, "porosity_pct": 14.0, "perm_md": 35.0, "api": 28.0, "visc_cp": 3.5, "so_pct": 48.0},
                "Unconsolidated sands - heavy oil": {"depth_ft": 3200.0, "porosity_pct": 26.0, "perm_md": 220.0, "api": 24.0, "visc_cp": 4.8, "so_pct": 58.0},
            }
            chosen = presets[preset]
            depth_ft = chosen["depth_ft"]
            porosity_pct = chosen["porosity_pct"]
            perm_md = chosen["perm_md"]
            api = chosen["api"]
            visc_cp = chosen["visc_cp"]
            so_pct = chosen["so_pct"]

    if st.button("Run screening", type="primary"):
        values = {
            "depth_ft": depth_ft,
            "porosity_pct": porosity_pct,
            "perm_md": perm_md,
            "api": api,
            "visc_cp": visc_cp,
            "so_pct": so_pct,
        }

        result = predict_case(
            model=model,
            scaler=scaler,
            label_encoder=label_encoder,
            env=env,
            techs_all=techs_all,
            values=values,
            formation=formation_category,
            alpha=alpha,
            rare_override=rare_override,
            rare_threshold=rare_threshold,
            nn_conf_threshold=nn_conf_threshold,
        )

        st.success(f"Recommendation generated for {formation_category} with a combined fuzzy-neural screening score.")

        left_col, right_col = st.columns([1.25, 0.75])
        with left_col:
            st.subheader("Recommendation")
            st.metric("Final technique", result["final_label"], f"Score: {result['final_score']:.3f}")
            st.metric("NN prediction", result["nn_label"], f"Confidence: {result['nn_conf']:.3f}")
            st.metric("Screening mode", result["mode"], "")
            if result["mode"] == "FUZZY_RARE_OVERRIDE":
                st.warning("A rare-technique fuzzy override was triggered because the neural-network confidence was below the selected threshold.")
            top3_df = pd.DataFrame(result["top3"], columns=["Technique", "Probability"])
            st.dataframe(top3_df, use_container_width=True)

        with right_col:
            st.subheader("Fuzzy suitability scores")
            fuzzy_series = pd.Series(result["fuzzy_scores"]).sort_values(ascending=False)
            st.bar_chart(fuzzy_series)
            st.subheader("Why this technique?")
            explanation = fuzzy_explain_one(env, result["final_label"], formation_category, values, alpha=alpha)
            if explanation is None:
                st.info("No direct fuzzy envelope was found for this technique and formation pair.")
            else:
                explain_rows, explain_score = explanation
                explain_df = pd.DataFrame(explain_rows)
                st.write(f"Mean fuzzy membership score: **{explain_score:.3f}**")
                st.dataframe(explain_df, use_container_width=True)
                st.bar_chart(explain_df.set_index("Variable")["Membership"])

        st.markdown("---")
        st.subheader("Workbook overview")
        st.write("Use the Excel Reports tab to inspect the workbook-derived screening and report tables.")

        st.download_button(
            "Download result as JSON",
            json.dumps({
                "inputs": {"formation_category": formation_category, **values},
                "final": {
                    "technique": result["final_label"],
                    "score": float(result["final_score"]),
                    "mode": result["mode"],
                },
                "nn": {
                    "technique": result["nn_label"],
                    "confidence": float(result["nn_conf"]),
                    "top3": [{"technique": t, "prob": float(p)} for t, p in result["top3"]],
                },
                "fuzzy_scores": {k: float(v) for k, v in result["fuzzy_scores"].items()},
            }, indent=2),
            file_name="eor_screening_result.json",
            mime="application/json",
        )
    else:
        st.info("Fill the inputs and click Run screening to generate a recommendation.")
        col1, col2 = st.columns(2)
        col1.metric("Workbook sheets", len(workbook_sheets))
        col2.metric("Available EOR techniques", len(techs_all))

with main_tabs[1]:
    st.header("Excel Screening Reports")
    report_tabs = st.tabs(["Screening", "Ranking", "RF/EUR", "Criteria", "References", "Summary", "Scenario"])

    with report_tabs[0]:
        render_screening_picker("Screening")

    with report_tabs[1]:
        render_screening_picker("Ranking")

    with report_tabs[2]:
        render_screening_picker("RF_EUR_Ranges")

    with report_tabs[3]:
        display_sheet("Criteria")

    with report_tabs[4]:
        display_sheet("References_2026")

    with report_tabs[5]:
        display_sheet("Summary")

    with report_tabs[6]:
        display_sheet("ScenarioControls")

with main_tabs[2]:
    st.header("Laboratory, Field, and Performance Charts")
    lab_tabs = st.tabs(["Coreflood", "Adsorption", "Viscosity", "Thermal", "Phase Behavior", "Maps & Challenges"])

    with lab_tabs[0]:
        display_sheet("Coreflood Summary")
        display_sheet("Coreflood")
        coreflood_df = workbook_sheets.get("Coreflood")
        if coreflood_df is not None and "Water Flood Recovery, % OOIP " in coreflood_df.columns:
            st.bar_chart(coreflood_df.set_index("Core sample")["Water Flood Recovery, % OOIP "].fillna(0))

    with lab_tabs[1]:
        display_sheet("Adsorption")
        display_sheet("Vis_Shear")
        vis_df = workbook_sheets.get("Vis_Shear")
        if vis_df is not None and "Shear Rate  (1/sec)" in vis_df.columns and "Apparent Viscosity" in vis_df.columns:
            st.line_chart(vis_df.set_index("Shear Rate  (1/sec)")["Apparent Viscosity"].dropna())

    with lab_tabs[2]:
        display_sheet("Thermal")
        if "Viscosity (cp)" in workbook_sheets.get("Thermal", pd.DataFrame()).columns and "Time (days)" in workbook_sheets.get("Thermal", pd.DataFrame()).columns:
            st.line_chart(workbook_sheets["Thermal"].set_index("Time (days)")["Viscosity (cp)"].dropna())

    with lab_tabs[3]:
        display_sheet("Tidy_All")
        display_sheet("Phase_Points")
        display_sheet("Phase Behavior Results")

    with lab_tabs[4]:
        display_sheet("IFT_poly_F")
        display_sheet("IFT_sur_F")
        display_sheet("PB_2003")
        display_sheet("PB_2013_A")
        display_sheet("PB_2013_S")

    with lab_tabs[5]:
        display_sheet("map")
        display_sheet("Challenges")

with main_tabs[3]:
    st.header("Workbook Explorer")
    if workbook_sheets:
        selected_sheet = st.selectbox("Select workbook sheet", list(workbook_sheets.keys()))
        display_sheet(selected_sheet, max_rows=300)
    else:
        st.warning("Workbook is not loaded. Add EOR_Screening_Tool_2026.xlsx to the project root.")
