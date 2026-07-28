import json
import numpy as np
import pandas as pd
import joblib
import streamlit as st
from pathlib import Path
from tensorflow import keras

# -----------------------------
# PATH SETUP
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

MODEL_DIR = ROOT_DIR / "outputs" / "model_artifacts"
DATA_DIR  = ROOT_DIR / "data"

MODEL_PATH  = MODEL_DIR / "eor_nn_alpha03.keras"
SCALER_PATH = MODEL_DIR / "scaler_alpha03.joblib"
LE_PATH     = MODEL_DIR / "label_encoder.joblib"
CFG_PATH    = MODEL_DIR / "config_alpha03.json"

RANGES_PATH = DATA_DIR / "NeuroFuzzy_EOR_Extracted_Tables.xlsx"
RANGES_SHEET = "Table1_Ranges"

# -----------------------------
# LOAD ARTIFACTS
# -----------------------------
@st.cache_resource
def load_artifacts():
    model = keras.models.load_model(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    le = joblib.load(LE_PATH)
    with open(CFG_PATH, "r") as f:
        cfg = json.load(f)
    return model, scaler, le, cfg

@st.cache_data
def load_env():
    table1 = pd.read_excel(RANGES_PATH, sheet_name=RANGES_SHEET, engine="openpyxl")

    def norm_tech(x):
        if pd.isna(x): return np.nan
        return str(x).strip().replace("CO22", "CO2").replace("*", "")

    def norm_form(x):
        if pd.isna(x): return np.nan
        x = str(x).lower()
        if "sandstone" in x: return "Sandstone"
        if "carbonate" in x: return "Carbonates"
        if "unconsolidated" in x: return "Unconsolidated sands"
        return np.nan

    table1["technique"] = table1["EOR technique"].apply(norm_tech)
    table1["formation_category"] = table1["Formation type"].apply(norm_form)
    table1 = table1.dropna(subset=["technique", "formation_category"])

    ENV = {}
    for _, r in table1.iterrows():
        ENV[(r["technique"], r["formation_category"])] = {
            "depth": (r["Depth min (ft)"], r["Depth max (ft)"]),
            "por":   (r["Porosity min (%)"], r["Porosity max (%)"]),
            "perm":  (r["Permeability min (mD)"], r["Permeability max (mD)"]),
            "api":   (r["Oil gravity min (°API)"], r["Oil gravity max (°API)"]),
            "visc":  (r["Oil viscosity min (cp)"], r["Oil viscosity max (cp)"]),
            "so":    (r["So at start min (%)"], r["So at start max (%)"])
        }

    TECHS_ALL = sorted(set(k[0] for k in ENV.keys()))
    return ENV, TECHS_ALL

# -----------------------------
# FUZZY LOGIC
# -----------------------------
def trap(x, L, U, a=0.3):
    if pd.isna(x) or pd.isna(L) or pd.isna(U): return 0.0
    w = U - L
    left, right = L - a*w, U + a*w

    if x <= left or x >= right: return 0.0
    if L <= x <= U: return 1.0
    if left < x < L: return (x-left)/(L-left)
    return (right-x)/(right-U)

def fuzzy_scores(ENV, TECHS, form, x):
    scores = {}
    for t in TECHS:
        e = ENV.get((t, form))
        if not e:
            scores[t] = 0.0
            continue

        vals = [
            trap(x["depth_ft"], *e["depth"]),
            trap(x["porosity_pct"], *e["por"]),
            trap(x["perm_md"], *e["perm"]),
            trap(x["api"], *e["api"]),
            trap(x["visc_cp"], *e["visc"]),
            trap(x["so_pct"], *e["so"])
        ]
        scores[t] = float(np.mean(vals))
    return scores

# -----------------------------
# FEATURE BUILDER
# -----------------------------
def build_features(x, form, TECHS, fs):
    num = np.array([
        x["depth_ft"], x["porosity_pct"], x["perm_md"],
        x["api"], x["visc_cp"], x["so_pct"],
        0,0,0,0,0,0,
        np.log10(x["perm_md"]+1e-6),
        np.log10(x["visc_cp"]+1e-6),
        0,0
    ])

    form_map = ["Sandstone", "Carbonates", "Unconsolidated sands"]
    form_vec = [1 if form==f else 0 for f in form_map]

    fuzzy_vec = [fs[t] for t in TECHS]

    return np.concatenate([num, form_vec, fuzzy_vec])

# -----------------------------
# PREDICTION
# -----------------------------
def predict(model, scaler, le, ENV, TECHS, x, form):
    fs = fuzzy_scores(ENV, TECHS, form, x)
    feats = build_features(x, form, TECHS, fs)

    probs = model.predict(scaler.transform([feats]), verbose=0)[0]
    idx = np.argmax(probs)

    return {
        "label": le.inverse_transform([idx])[0],
        "conf": float(probs[idx]),
        "top3": sorted(
            [(le.inverse_transform([i])[0], float(p)) for i,p in enumerate(probs)],
            key=lambda x: x[1], reverse=True
        )[:3],
        "fuzzy": fs
    }

# -----------------------------
# UI
# -----------------------------
st.set_page_config(layout="wide")
st.title("EOR Technique Screening Tool")

model, scaler, le, cfg = load_artifacts()
ENV, TECHS = load_env()

# Sidebar
st.sidebar.header("Inputs")

form = st.sidebar.selectbox("Formation", ["Sandstone","Carbonates","Unconsolidated sands"])
depth = st.sidebar.number_input("Depth", 0.0, value=5000.0)
por = st.sidebar.number_input("Porosity", 0.0, 100.0, 20.0)
perm = st.sidebar.number_input("Permeability", 0.0, 100.0)
api = st.sidebar.number_input("API", 0.0, 80.0, 35.0)
visc = st.sidebar.number_input("Viscosity", 0.0, 2.0)
so = st.sidebar.number_input("So", 0.0, 100.0, 55.0)

# Init state
if "result" not in st.session_state:
    st.session_state.result = None
    st.session_state.x = None

if st.sidebar.button("Run"):
    x = {
        "depth_ft": depth,
        "porosity_pct": por,
        "perm_md": perm,
        "api": api,
        "visc_cp": visc,
        "so_pct": so
    }

    st.session_state.x = x
    st.session_state.result = predict(model, scaler, le, ENV, TECHS, x, form)

# -----------------------------
# DISPLAY
# -----------------------------
if st.session_state.result:

    res = st.session_state.result
    x = st.session_state.x

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Prediction")
        st.write("**Technique:**", res["label"])
        st.write("**Confidence:**", res["conf"])

        st.subheader("Top 3")
        for t,p in res["top3"]:
            st.write(f"{t}: {p:.3f}")

    with col2:
        st.subheader("Fuzzy Scores")
        st.bar_chart(pd.Series(res["fuzzy"]).sort_values(ascending=False))

    # Export
    payload = {
        "inputs": {"formation": form, **x},
        "result": res
    }

    st.download_button(
        "Download JSON",
        json.dumps(payload, indent=2),
        "result.json"
    )