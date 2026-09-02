
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import hashlib
import json
import re
import numpy as np
import pandas as pd

SEED = 42

def find_project_root() -> Path:
    candidates = [Path.cwd(), *Path.cwd().parents]
    for p in candidates:
        if (p / "src").exists() and (p / "outputs").exists():
            return p
    return Path.cwd().parents[2]

PROJECT_ROOT = find_project_root()
ML_DATA_DIR = PROJECT_ROOT / "src" / "notebooks" / "ml_data"
ARTIFACT_DIR = PROJECT_ROOT / "outputs" / "model_artifacts"
PROCESSED_DIR = PROJECT_ROOT / "outputs" / "ml_research"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

COLUMN_ALIASES = {
    "technique": ["EOR technique", "EOR Technique", "technique", "Technique", "EOR_Technique", "EOR Method", "Method"],
    "formation": ["Formation type", "formation_category", "Formation", "Formation Type", "Rock Type", "rock_type"],
    "depth_min": ["Depth min (ft)", "depth_min_ft", "Depth_min_ft", "depth_min"],
    "depth_max": ["Depth max (ft)", "depth_max_ft", "Depth_max_ft", "depth_max"],
    "por_min": ["Porosity min (%)", "porosity_min_pct", "por_min"],
    "por_max": ["Porosity max (%)", "porosity_max_pct", "por_max"],
    "perm_min": ["Permeability min (mD)", "perm_min_md", "permeability_min_md", "perm_min"],
    "perm_max": ["Permeability max (mD)", "perm_max_md", "permeability_max_md", "perm_max"],
    "api_min": ["Oil gravity min (°API)", "api_min", "API min", "oil_api_min"],
    "api_max": ["Oil gravity max (°API)", "api_max", "API max", "oil_api_max"],
    "visc_min": ["Oil viscosity min (cp)", "visc_min_cp", "viscosity_min_cp", "visc_min"],
    "visc_max": ["Oil viscosity max (cp)", "visc_max_cp", "viscosity_max_cp", "visc_max"],
    "so_min": ["So at start min (%)", "so_start_min_pct", "so_min"],
    "so_max": ["So at start max (%)", "so_start_max_pct", "so_max"],
}

def normalize_col(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")

def find_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    exact = {str(c).strip().lower(): c for c in df.columns}
    for a in aliases:
        if a.strip().lower() in exact:
            return exact[a.strip().lower()]
    normalized = {normalize_col(c): c for c in df.columns}
    for a in aliases:
        if normalize_col(a) in normalized:
            return normalized[normalize_col(a)]
    return None

def discover_candidate_tables() -> List[Dict[str, Any]]:
    candidates = []
    for path in sorted(ML_DATA_DIR.glob("*.xlsx")):
        try:
            xls = pd.ExcelFile(path)
        except Exception as exc:
            candidates.append({"path": path, "error": str(exc)})
            continue
        for sheet in xls.sheet_names:
            try:
                df = pd.read_excel(path, sheet_name=sheet)
            except Exception as exc:
                candidates.append({"path": path, "sheet": sheet, "error": str(exc)})
                continue
            target = find_column(df, COLUMN_ALIASES["technique"])
            formation = find_column(df, COLUMN_ALIASES["formation"])
            range_hits = sum(
                find_column(df, COLUMN_ALIASES[k]) is not None
                for k in COLUMN_ALIASES if k not in {"technique", "formation"}
            )
            candidates.append({
                "path": str(path),
                "sheet": sheet,
                "rows": len(df),
                "columns": len(df.columns),
                "target_column": target,
                "formation_column": formation,
                "range_column_hits": range_hits,
            })
    return candidates

def select_training_table(preferred_name: str = "Dataset_01_EOR.xlsx") -> Tuple[pd.DataFrame, Dict[str, Any]]:
    candidates = discover_candidate_tables()
    valid = [
        c for c in candidates
        if c.get("target_column") is not None
        and c.get("formation_column") is not None
        and c.get("range_column_hits", 0) >= 10
        and "error" not in c
    ]
    if not valid:
        raise ValueError("No usable EOR training table was found in ml_data/.")
    preferred = [c for c in valid if Path(c["path"]).name.lower() == preferred_name.lower()]
    chosen = preferred[0] if preferred else max(valid, key=lambda x: (x["rows"], x["range_column_hits"]))
    return pd.read_excel(chosen["path"], sheet_name=chosen["sheet"]), chosen

def standardize_training_table(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for name, aliases in COLUMN_ALIASES.items():
        source = find_column(df, aliases)
        if source is not None:
            out[name] = df[source]

    required = [
        "technique", "formation",
        "depth_min", "depth_max", "por_min", "por_max",
        "perm_min", "perm_max", "api_min", "api_max",
        "visc_min", "visc_max", "so_min", "so_max",
    ]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    for c in required:
        if c not in {"technique", "formation"}:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    out["technique"] = out["technique"].astype(str).str.strip()
    out["formation"] = out["formation"].astype(str).str.strip().replace({
        "Carbonate": "Carbonates",
        "Unconsolidated Sand": "Unconsolidated sands",
    })

    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=required).copy()

    for lo, hi in [
            ("depth_min", "depth_max"), ("por_min", "por_max"), ("perm_min", "perm_max"),
            ("api_min", "api_max"), ("visc_min", "visc_max"),("so_min", "so_max"),]:
    
            out = out[out[hi] >= out[lo]]
    
    # Create one fingerprint per actual observation.
    fingerprints = []
    
    for row in out[required].itertuples(index=False, name=None):
            payload = "|".join(
                "" if pd.isna(v) else str(v)
                for v in row
            )
    
            fingerprints.append(
                hashlib.sha1(
                    payload.encode("utf-8")
                ).hexdigest()[:16]
            )
    
    out["record_fingerprint"] = fingerprints
    
    return out.reset_index(drop=True)

def build_feature_table(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    X = pd.DataFrame(index=df.index)
    for prefix, lo, hi in [
        ("depth", "depth_min", "depth_max"),
        ("porosity", "por_min", "por_max"),
        ("perm", "perm_min", "perm_max"),
        ("api", "api_min", "api_max"),
        ("visc", "visc_min", "visc_max"),
        ("so", "so_min", "so_max"),
    ]:
        X[f"{prefix}_mid" + ("_ft" if prefix == "depth" else "_pct" if prefix in {"porosity", "so"} else "_md" if prefix == "perm" else "" if prefix == "api" else "_cp")] = (df[lo] + df[hi]) / 2
        X[f"{prefix}_span" + ("_ft" if prefix == "depth" else "_pct" if prefix in {"porosity", "so"} else "_md" if prefix == "perm" else "" if prefix == "api" else "_cp")] = (df[hi] - df[lo]).clip(lower=0)

    X["log10_perm_mid"] = np.log10(np.clip(X["perm_mid_md"], 1e-6, None))
    X["log10_visc_mid"] = np.log10(np.clip(X["visc_mid_cp"], 1e-6, None))

    for formation in ["Sandstone", "Carbonates", "Unconsolidated sands"]:
        X[f"formation_{normalize_col(formation)}"] = df["formation"].eq(formation).astype(float)

    return X.astype(float), df["technique"].copy(), list(X.columns)

def top_k_accuracy(y_true, proba, k=3):
    pred = np.argsort(np.asarray(proba), axis=1)[:, -k:]
    return float(np.mean([y in row for y, row in zip(np.asarray(y_true), pred)]))

def safe_model_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, StratifiedKFold, RandomizedSearchCV
from sklearn.metrics import balanced_accuracy_score, f1_score, matthews_corrcoef, log_loss
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
import joblib

def optional_models():
    models = {}
    try:
        from xgboost import XGBClassifier
        models["XGBoost"] = (
            XGBClassifier(
                objective="multi:softprob",
                eval_metric="mlogloss",
                tree_method="hist",
                random_state=SEED,
                n_jobs=-1,
            ),
            {
                "n_estimators": [200, 400, 700],
                "max_depth": [2, 3, 4, 6],
                "learning_rate": [0.02, 0.05, 0.1],
                "subsample": [0.7, 0.9, 1.0],
                "colsample_bytree": [0.7, 0.9, 1.0],
                "min_child_weight": [1, 3, 5],
            },
        )
    except Exception as exc:
        print("XGBoost unavailable:", exc)
    try:
        from catboost import CatBoostClassifier
        models["CatBoost"] = (
            CatBoostClassifier(
                verbose=False,
                random_seed=SEED,
                auto_class_weights="Balanced",
            ),
            {
                "iterations": [200, 400, 700],
                "depth": [3, 4, 5, 6, 8],
                "learning_rate": [0.02, 0.05, 0.1],
                "l2_leaf_reg": [1, 3, 10],
            },
        )
    except Exception as exc:
        print("CatBoost unavailable:", exc)
    return models

def benchmark_models(X_train, y_train, X_test, y_test, le):
    models = {
        "LogisticRegression": (
            Pipeline([
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(
                    max_iter=3000,
                    class_weight="balanced",
                    random_state=SEED,
                )),
            ]),
            {"model__C": np.logspace(-2, 2, 12)},
        ),
        "SVM_RBF": (
            Pipeline([
                ("scaler", StandardScaler()),
                ("model", SVC(
                    probability=True,
                    class_weight="balanced",
                    random_state=SEED,
                )),
            ]),
            {
                "model__C": np.logspace(-2, 2, 10),
                "model__gamma": ["scale", 0.001, 0.01, 0.1, 1.0],
            },
        ),
        "KNN": (
            Pipeline([
                ("scaler", StandardScaler()),
                ("model", KNeighborsClassifier()),
            ]),
            {
                "model__n_neighbors": list(range(3, 18, 2)),
                "model__weights": ["uniform", "distance"],
                "model__p": [1, 2],
            },
        ),
        "RandomForest": (
            RandomForestClassifier(
                class_weight="balanced",
                random_state=SEED,
                n_jobs=-1,
            ),
            {
                "n_estimators": [300, 500, 800],
                "max_depth": [None, 3, 5, 8, 12],
                "min_samples_leaf": [1, 2, 4, 8],
                "max_features": ["sqrt", "log2", 0.6, 1.0],
            },
        ),
        "ExtraTrees": (
            ExtraTreesClassifier(
                class_weight="balanced",
                random_state=SEED,
                n_jobs=-1,
            ),
            {
                "n_estimators": [300, 500, 800],
                "max_depth": [None, 4, 6, 10, 14],
                "min_samples_leaf": [1, 2, 4, 8],
                "max_features": ["sqrt", "log2", 0.6, 1.0],
            },
        ),
        "HistGradientBoosting": (
            HistGradientBoostingClassifier(random_state=SEED),
            {
                "max_iter": [100, 200, 300],
                "learning_rate": [0.03, 0.05, 0.1],
                "max_leaf_nodes": [7, 15, 31],
                "l2_regularization": [0.0, 0.1, 1.0, 5.0],
            },
        ),
        "MLP": (
            Pipeline([
                ("scaler", StandardScaler()),
                ("model", MLPClassifier(
                    early_stopping=True,
                    validation_fraction=0.2,
                    max_iter=1500,
                    random_state=SEED,
                )),
            ]),
            {
                "model__hidden_layer_sizes": [(16,), (32,), (64,), (64, 32), (128, 64)],
                "model__alpha": [1e-5, 1e-4, 1e-3, 1e-2],
                "model__learning_rate_init": [1e-4, 5e-4, 1e-3],
            },
        ),
    }
    models.update(optional_models())

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    rows, fitted = [], {}

    for name, (estimator, params) in models.items():
        print(f"\n=== {name} ===")
        n_iter = min(10, max(1, sum(len(v) for v in params.values())))
        search = RandomizedSearchCV(
            estimator=estimator,
            param_distributions=params,
            n_iter=n_iter,
            scoring="f1_macro",
            cv=cv,
            random_state=SEED,
            n_jobs=-1,
            refit=True,
            error_score="raise",
        )
        search.fit(X_train, y_train)
        fitted[name] = search.best_estimator_
        proba = search.best_estimator_.predict_proba(X_test)
        pred = np.argmax(proba, axis=1)

        rows.append({
            "Model": name,
            "CV_MacroF1": search.best_score_,
            "Test_BalancedAccuracy": balanced_accuracy_score(y_test, pred),
            "Test_MacroF1": f1_score(y_test, pred, average="macro"),
            "Test_WeightedF1": f1_score(y_test, pred, average="weighted"),
            "Test_MCC": matthews_corrcoef(y_test, pred),
            "Test_LogLoss": log_loss(y_test, proba, labels=np.arange(len(le.classes_))),
            "Test_Top3": top_k_accuracy(y_test, proba, min(3, proba.shape[1])),
        })

    return (
        pd.DataFrame(rows).sort_values(
            ["Test_MacroF1", "Test_Top3", "CV_MacroF1"],
            ascending=[False, False, False],
        ).reset_index(drop=True),
        fitted,
    )
