
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
    # IDs are metadata used for splitting/audit only, never predictive features.
    # Prefer exact case groups; the OGJ2014 workbook has blank field IDs on a
    # small number of unresolved rows, while case_id is complete.
    "source_group": [
        "case_id", "field_id", "Field Name", "Field",
        "source_report_group_id", "publication_id", "project_id",
        "source_id", "source_group", "report_id",
    ],
}

MINIMUM_GROUPS_PER_CLASS = 6

PROVENANCE_METADATA_COLUMNS = {
    "record_id", "source_report_group_id", "publication_id", "publication_title",
    "publication_id_status", "field_id", "field_name_normalized",
    "field_id_status", "project_id", "case_id", "case_id_status",
    "source_group", "tagging_confidence", "tagging_rationale", "needs_review",
}


def assert_no_provenance_features(features: pd.DataFrame) -> None:
    """Fail closed if provenance identifiers or audit metadata enter model X."""
    forbidden = sorted(
        column for column in features.columns
        if column in PROVENANCE_METADATA_COLUMNS
        or column.casefold().endswith("_id")
        or column.casefold() in {"raw_line", "source_report", "publication_title",
                                 "field_name_normalized", "tagging_rationale",
                                 "tagging_confidence", "needs_review"}
    )
    if forbidden:
        raise ValueError(
            "Provenance/audit columns cannot be model features: "
            + ", ".join(forbidden)
        )

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
                for k in COLUMN_ALIASES
                if k not in {"technique", "formation", "source_group"}
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
    if "source_group" in out.columns:
        source_groups = out["source_group"].astype("string").str.strip()
        missing_groups = source_groups.str.lower().isin(["", "nan", "none", "null"])
        out["source_group"] = source_groups.mask(missing_groups, pd.NA)

    for lo, hi in [
            ("depth_min", "depth_max"), ("por_min", "por_max"), ("perm_min", "perm_max"),
            ("api_min", "api_max"), ("visc_min", "visc_max"),("so_min", "so_max"),]:
    
            out = out[out[hi] >= out[lo]]
    
    out["record_fingerprint"] = _fingerprints(out[required])

    duplicate_key = ["record_fingerprint"]
    if "source_group" in out.columns:
        duplicate_key.append("source_group")
    duplicate_count = int(out.duplicated(duplicate_key).sum())
    out = out.drop_duplicates(duplicate_key, keep="first").reset_index(drop=True)
    out.attrs["exact_duplicates_removed"] = duplicate_count
    return out


def build_multilabel_table(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[Tuple[str, ...]], np.ndarray | None]:
    """Aggregate identical input profiles into one row with all associated labels."""
    required = [
        "technique", "formation",
        "depth_min", "depth_max", "por_min", "por_max",
        "perm_min", "perm_max", "api_min", "api_max",
        "visc_min", "visc_max", "so_min", "so_max",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Cannot build multi-label data; missing fields: {missing}")

    feature_columns = [column for column in required if column != "technique"]
    feature_fingerprints = _fingerprints(df[feature_columns])
    working = df.copy()
    working["feature_fingerprint"] = feature_fingerprints

    has_source_groups = "source_group" in working.columns
    source_series = None
    if has_source_groups:
        source_series = working["source_group"].astype("string").str.strip()
        source_series = source_series.mask(
            source_series.str.lower().isin(["", "nan", "none", "null"]),
            pd.NA,
        )

    parents: dict[str, str] = {}

    def find(node: str) -> str:
        parents.setdefault(node, node)
        if parents[node] != node:
            parents[node] = find(parents[node])
        return parents[node]

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    representatives = []
    label_sets: List[Tuple[str, ...]] = []
    group_nodes: List[str | None] = []
    for fingerprint, profile in working.groupby(
        "feature_fingerprint", sort=False, dropna=False
    ):
        profile_index = profile.index
        profile_labels = tuple(sorted(profile["technique"].astype(str).unique()))
        representatives.append(profile.iloc[0].drop(labels=["feature_fingerprint"]))
        label_sets.append(profile_labels)

        if not has_source_groups:
            group_nodes.append(None)
            continue

        profile_sources = source_series.loc[profile_index]
        if profile_sources.isna().any():
            group_nodes.append(None)
            continue

        profile_node = f"profile:{fingerprint}"
        for source_id in profile_sources.unique():
            source_node = f"source:{source_id}"
            union(profile_node, source_node)
        group_nodes.append(profile_node)

    record_columns = list(df.columns)
    records = pd.DataFrame(representatives).reindex(columns=record_columns).reset_index(drop=True)
    if not has_source_groups:
        return records, label_sets, None

    resolved_groups = [
        find(node) if node is not None else pd.NA
        for node in group_nodes
    ]
    return records, label_sets, np.asarray(resolved_groups, dtype=object)


def _fingerprints(frame: pd.DataFrame) -> List[str]:
    fingerprints = []
    for row in frame.itertuples(index=False, name=None):
        payload = "|".join("" if pd.isna(value) else str(value) for value in row)
        fingerprints.append(hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16])
    return fingerprints


def class_group_support(
    labels: pd.Series | np.ndarray,
    groups: pd.Series | np.ndarray,
    *,
    classes: List[str] | np.ndarray | None = None,
) -> Dict[str, int]:
    """Count independent source groups per class for single- or multi-label targets."""
    values = np.asarray(labels)
    group_values = np.asarray(groups)
    if values.ndim == 1:
        frame = pd.DataFrame({"label": values, "group": group_values})
        return {
            str(label): int(group.nunique())
            for label, group in frame.groupby("label", dropna=False)["group"]
        }
    if values.ndim != 2 or len(values) != len(group_values):
        raise ValueError("labels must be a 1D or 2D matrix aligned with groups.")
    class_names = list(classes) if classes is not None else [str(i) for i in range(values.shape[1])]
    if len(class_names) != values.shape[1]:
        raise ValueError("classes must have one name for each multi-label column.")
    return {
        str(class_names[index]): int(
            pd.Series(group_values[values[:, index].astype(bool)]).nunique()
        )
        for index in range(values.shape[1])
    }


def validate_grouped_dataset(
    labels: pd.Series | np.ndarray,
    groups: pd.Series | np.ndarray | None,
    *,
    minimum_groups_per_class: int = MINIMUM_GROUPS_PER_CLASS,
    classes: List[str] | np.ndarray | None = None,
) -> Dict[str, int]:
    """Reject evaluation data without independent source groups and class support."""
    if groups is None:
        raise ValueError(
            "Cannot claim independent-field/project validation: the dataset has no "
            "source_group identifier. Add a field, project, report, or publication ID."
        )
    group_values = pd.Series(np.asarray(groups), dtype="string").str.strip()
    missing_groups = group_values.isna() | group_values.str.lower().isin(
        ["", "nan", "none", "null"]
    )
    if missing_groups.any():
        raise ValueError("source_group contains blank values; resolve them before evaluation.")

    label_values = np.asarray(labels)
    if label_values.ndim == 2:
        positive_labels = np.any(label_values.astype(bool), axis=0)
        negative_labels = np.any(~label_values.astype(bool), axis=0)
        unsupported = np.flatnonzero(~(positive_labels & negative_labels))
        if len(unsupported):
            names = (
                list(classes)
                if classes is not None
                else [str(index) for index in range(label_values.shape[1])]
            )
            raise ValueError(
                "Each technique must have both positive and negative profiles for "
                "one-vs-rest learning. Unsupported techniques: "
                + ", ".join(str(names[index]) for index in unsupported)
            )

    support = class_group_support(labels, group_values, classes=classes)
    sparse = {
        label: count
        for label, count in support.items()
        if count < minimum_groups_per_class
    }
    if sparse:
        details = ", ".join(f"{label}: {count}" for label, count in sorted(sparse.items()))
        raise ValueError(
            f"At least {minimum_groups_per_class} independent source groups per class "
            f"are required for the grouped holdout and cross-validation. Sparse classes: {details}"
        )
    return support


def grouped_holdout_indices(
    labels: pd.Series | np.ndarray,
    groups: pd.Series | np.ndarray,
    *,
    test_size: float = 0.2,
    random_state: int = SEED,
    minimum_groups_per_class: int = MINIMUM_GROUPS_PER_CLASS,
    classes: List[str] | np.ndarray | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Create a reproducible group holdout with every technique represented."""
    labels = np.asarray(labels)
    groups = np.asarray(groups)
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1.")
    validate_grouped_dataset(
        labels,
        groups,
        minimum_groups_per_class=minimum_groups_per_class,
        classes=classes,
    )
    splitter = GroupShuffleSplit(
        n_splits=100,
        test_size=test_size,
        random_state=random_state,
    )
    all_classes = np.arange(labels.shape[1]) if labels.ndim == 2 else np.unique(labels)
    for train_indices, test_indices in splitter.split(
        np.zeros(len(labels)), labels, groups
    ):
        train_labels = labels[train_indices]
        test_labels = labels[test_indices]
        if labels.ndim == 2:
            train_classes = np.flatnonzero(np.any(train_labels.astype(bool), axis=0))
            test_classes = np.flatnonzero(np.any(test_labels.astype(bool), axis=0))
            train_negative = np.flatnonzero(np.any(~train_labels.astype(bool), axis=0))
            test_negative = np.flatnonzero(np.any(~test_labels.astype(bool), axis=0))
        else:
            train_classes = np.unique(train_labels)
            test_classes = np.unique(test_labels)
            train_negative = test_negative = all_classes
        if (
            set(train_classes) == set(all_classes)
            and set(test_classes) == set(all_classes)
            and set(train_negative) == set(all_classes)
            and set(test_negative) == set(all_classes)
        ):
            return train_indices, test_indices
    raise ValueError(
        "Could not form a grouped holdout containing every technique in both sets. "
        "Collect more independent source groups or review the multi-label distribution."
    )


def grouped_cv_splits(
    labels: pd.Series | np.ndarray,
    groups: pd.Series | np.ndarray,
    *,
    max_splits: int = 5,
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Build grouped CV folds and reject folds missing a technique."""
    labels = np.asarray(labels)
    groups = np.asarray(groups)
    support = class_group_support(labels, groups)
    n_splits = min(max_splits, min(support.values(), default=0))
    if n_splits < 2:
        raise ValueError("At least two independent source groups per class are required for CV.")

    all_classes = set(
        np.arange(labels.shape[1]) if labels.ndim == 2 else np.unique(labels)
    )
    splitter = GroupKFold(n_splits=n_splits)
    splits = []
    for train_indices, validation_indices in splitter.split(
        np.zeros(len(labels)), labels, groups
    ):
        validation_labels = labels[validation_indices]
        if labels.ndim == 2:
            train_labels = labels[train_indices]
            train_classes = np.flatnonzero(
                np.any(train_labels.astype(bool), axis=0)
            )
            train_negative = np.flatnonzero(np.any(~train_labels.astype(bool), axis=0))
            validation_classes = np.flatnonzero(
                np.any(validation_labels.astype(bool), axis=0)
            )
            validation_negative = np.flatnonzero(
                np.any(~validation_labels.astype(bool), axis=0)
            )
        else:
            train_classes = np.unique(labels[train_indices])
            validation_classes = np.unique(validation_labels)
            train_negative = validation_negative = all_classes
        if (
            set(train_classes) == all_classes
            and set(validation_classes) == all_classes
            and set(train_negative) == all_classes
            and set(validation_negative) == all_classes
        ):
            splits.append((train_indices, validation_indices))
    if len(splits) < 2:
        raise ValueError(
            "Fewer than two grouped CV folds contain every technique. "
            "Collect more independent source groups per class."
        )
    return splits

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

    X = X.astype(float)
    assert_no_provenance_features(X)
    return X, df["technique"].copy(), list(X.columns)

def multilabel_top_k_metrics(y_true, probabilities, k=3):
    """Return sample-level top-k hit rate and recall for multi-label targets."""
    y_true = np.asarray(y_true, dtype=bool)
    probabilities = np.asarray(probabilities, dtype=float)
    if y_true.shape != probabilities.shape:
        raise ValueError("Target and probability matrices must have the same shape.")
    top_indices = np.argsort(probabilities, axis=1)[:, -k:]
    hits = np.take_along_axis(y_true, top_indices, axis=1).sum(axis=1)
    true_counts = y_true.sum(axis=1)
    return {
        "top_k_hit_rate": float(np.mean(hits > 0)),
        "top_k_recall": float(np.mean(hits / np.maximum(true_counts, 1))),
    }

def safe_model_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import (
    GroupKFold,
    GroupShuffleSplit,
    RandomizedSearchCV,
)
from sklearn.multiclass import OneVsRestClassifier
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
                objective="binary:logistic",
                eval_metric="logloss",
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
                loss_function="Logloss",
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

def benchmark_models(X_train, y_train, groups_train):
    """Select multi-label estimators using grouped CV only, never the final holdout."""
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

    cv = grouped_cv_splits(y_train, groups_train)
    rows, fitted = [], {}

    for name, (estimator, params) in models.items():
        print(f"\n=== {name} ===")
        n_iter = min(10, max(1, sum(len(v) for v in params.values())))
        multi_label_estimator = OneVsRestClassifier(estimator)
        multi_label_params = {
            f"estimator__{parameter}": values
            for parameter, values in params.items()
        }
        search = RandomizedSearchCV(
            estimator=multi_label_estimator,
            param_distributions=multi_label_params,
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
        rows.append({
            "Model": name,
            "CV_MacroF1": search.best_score_,
            "CV_Folds": len(cv),
            "Best_Params": json.dumps(search.best_params_, sort_keys=True, default=str),
        })

    return (
        pd.DataFrame(rows).sort_values(
            ["CV_MacroF1"],
            ascending=[False],
        ).reset_index(drop=True),
        fitted,
    )
