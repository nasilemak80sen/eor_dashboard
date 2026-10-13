"""Field-isolated baseline benchmark for the OGJ2014 EOR technique table.

This is an observed-technique classification study, not a prediction of EOR
success. It preserves source rows, excludes unresolved field IDs from field-level
validation, and excludes low-support classes from this explicitly restricted
pilot without relabelling them.
"""
from __future__ import annotations

import hashlib
import json
import re
import joblib
from pathlib import Path
from typing import Any
import joblib

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from catboost import CatBoostClassifier
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from audit_ogj2014_data_quality import TECHNIQUE_FAMILY, TECHNIQUE_PATTERNS

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))
from ml.feature_builder import FEATURE_NAMES as PRODUCTION_FEATURE_NAMES  # noqa: E402
PRODUCTION_MODEL_PATH = ROOT / "outputs" / "model_artifacts" / "eor_catboost_v1.0.0.joblib"
PRODUCTION_CONFIG_PATH = ROOT / "outputs" / "model_artifacts" / "config_catboost_v1.0.0.json"

DATASET = ROOT / "src" / "notebooks" / "ml_data" / "OGJ2014_extracted_vs_Table1.xlsx"
SHEET = "OGJ2014_Extracted_Rows"
OUTPUT_DIR = ROOT / "outputs" / "ml_research"
SOURCE_ADJUDICATION_PATH = ROOT / "data" / "provenance" / "ogj2014_technique_label_adjudications.csv"
FIELD_IDENTITY_ADJUDICATION_PATH = ROOT / "data" / "provenance" / "ogj2014_field_identity_adjudications.csv"
TRAINING_MANIFEST_PATH = ROOT / "data" / "provenance" / "catboost_v1.0.0_training_manifest.csv"
TRAINING_MEMBERSHIP_REPORT_PATH = ROOT / "data" / "provenance" / "catboost_v1.0.0_training_membership.json"
PRODUCTION_MODEL_PATH = ROOT / "outputs" / "model_artifacts" / "eor_catboost_v1.0.0.joblib"
PRODUCTION_LABEL_ENCODER_PATH = ROOT / "outputs" / "model_artifacts" / "label_encoder_catboost_v1.0.0.joblib"
PRODUCTION_CLASSES = [
    "Combustion", "HC immiscible", "Hot water", "Miscible CO2", "Miscible HC",
    "Miscible acid gas", "Nitrogen immiscible", "Polymer", "Steam",
]
MINIMUM_FIELDS_PER_CLASS = 6
REQUESTED_FOLDS = 5
HOLDOUT_FRACTION = 0.20
SEED_START = 42
SEED_ATTEMPTS = 100
REPEATED_HOLDOUTS = 20
MINIMUM_HOLDOUT_FIELDS_PER_CLASS = 2
MINIMUM_TRAIN_FIELDS_PER_CLASS = MINIMUM_FIELDS_PER_CLASS - MINIMUM_HOLDOUT_FIELDS_PER_CLASS

NUMERIC_RANGES = [
    ("depth", "depth_min_ft", "depth_max_ft", "ft"),
    ("porosity", "porosity_min_pct", "porosity_max_pct", "pct"),
    ("perm", "perm_min_md", "perm_max_md", "md"),
    ("api", "api_min", "api_max", ""),
    ("visc", "visc_min_cp", "visc_max_cp", "cp"),
    ("so", "so_start_min_pct", "so_start_max_pct", "pct"),
]
REQUIRED_SOURCE_COLUMNS = {
    "record_id", "technique", "formation_category", "field_id", "field_id_status", "raw_line",
    *(column for _, lo, hi, _ in NUMERIC_RANGES for column in (lo, hi)),
}



def production_recipe_parameters(
    eligible_classes: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recover the trained v1 CatBoost recipe and adapt only class-specific settings.

    The loaded model's trees are never evaluated on the research holdout. Only its
    training parameters are reused to fit a fresh model inside each grouped fold.
    """
    if not PRODUCTION_MODEL_PATH.is_file() or not PRODUCTION_CONFIG_PATH.is_file():
        raise FileNotFoundError("Production v1 CatBoost artifact/config is missing.")
    config = json.loads(PRODUCTION_CONFIG_PATH.read_text(encoding="utf-8"))
    artifact = joblib.load(PRODUCTION_MODEL_PATH)
    if hasattr(artifact, "named_steps"):
        candidates = list(artifact.named_steps.values())
        model = next((item for item in candidates if isinstance(item, CatBoostClassifier)), None)
    else:
        model = artifact if isinstance(artifact, CatBoostClassifier) else None
    if model is None:
        raise TypeError(
            "Expected the production v1 artifact to contain a CatBoostClassifier; "
            f"received {type(artifact).__name__}."
        )

    params = {key: value for key, value in model.get_params().items() if value is not None}
    try:
        effective = model.get_all_params()
    except Exception:
        effective = {}
    # The artifact config omitted several hyperparameters; recover their effective
    # values from the serialized model rather than guessing research defaults.
    recoverable = (
        "iterations", "depth", "learning_rate", "loss_function", "eval_metric",
        "l2_leaf_reg", "random_seed", "random_strength", "border_count",
        "auto_class_weights", "bootstrap_type", "bagging_temperature", "subsample",
        "rsm", "one_hot_max_size", "min_data_in_leaf", "leaf_estimation_iterations",
        "leaf_estimation_method", "grow_policy", "max_leaves", "model_size_reg",
        "boosting_type", "score_function", "nan_mode", "task_type", "class_weights",
    )
    for key in recoverable:
        if (key not in params or params[key] is None) and effective.get(key) is not None:
            params[key] = effective[key]

    config_classes = [str(value) for value in config.get("classes", [])]
    adaptations = []
    # The recipe is retrained only on the eligible research class subset. Remove
    # fixed nine-class declarations and remap explicit weights by the source class
    # order, preserving weights for the classes that remain in this pilot.
    params.pop("classes_count", None)
    params.pop("class_names", None)
    params.pop("use_best_model", None)
    params.pop("eval_set", None)
    raw_weights = params.get("class_weights")
    if raw_weights is not None:
        if isinstance(raw_weights, dict):
            weight_map = {}
            for key, value in raw_weights.items():
                if isinstance(key, (int, np.integer)) or str(key).isdigit():
                    index = int(key)
                    if 0 <= index < len(config_classes):
                        weight_map[config_classes[index]] = float(value)
                else:
                    weight_map[str(key)] = float(value)
        elif isinstance(raw_weights, (list, tuple)):
            weight_map = {
                label: float(value)
                for label, value in zip(config_classes, raw_weights)
            }
        else:
            raise ValueError("Unsupported production class_weights representation.")
        if not all(label in weight_map for label in eligible_classes):
            raise ValueError(
                "Production artifact class weights cannot be mapped to every eligible class."
            )
        params["class_weights"] = {label: weight_map[label] for label in eligible_classes}
        params.pop("auto_class_weights", None)
        adaptations.append("restricted explicit class_weights to the eligible class subset")
    if not params.get("loss_function"):
        params["loss_function"] = "MultiClass"
        adaptations.append("set MultiClass loss because the artifact did not expose a loss_function")

    for required in ("iterations", "depth", "learning_rate"):
        if params.get(required) is None:
            raise ValueError(
                f"Production artifact does not expose effective {required}; "
                "cannot create a defensible fold-retrained recipe."
            )
    params["thread_count"] = 2
    params["verbose"] = False
    params["allow_writing_files"] = False
    adaptations.append("retrained from scratch within each field-grouped split; deployed trees not reused")

    report_params = {
        key: params.get(key)
        for key in (
            "iterations", "depth", "learning_rate", "loss_function", "eval_metric",
            "l2_leaf_reg", "random_seed", "random_strength", "border_count",
            "auto_class_weights", "bootstrap_type", "bagging_temperature", "subsample",
            "rsm", "one_hot_max_size", "min_data_in_leaf", "leaf_estimation_iterations",
            "leaf_estimation_method", "grow_policy", "max_leaves", "model_size_reg",
            "class_weights", "thread_count",
        )
        if params.get(key) is not None
    }
    metadata = {
        "status": "available",
        "artifact": str(PRODUCTION_MODEL_PATH.relative_to(ROOT)),
        "config": str(PRODUCTION_CONFIG_PATH.relative_to(ROOT)),
        "artifact_version": config.get("version"),
        "source_class_count": len(config_classes),
        "eligible_class_scope": list(eligible_classes),
        "parameters_used": report_params,
        "adaptations": adaptations,
        "interpretation": (
            "Fold-retrained production-compatible recipe comparison only; this does not score "
            "the deployed artifact or establish its held-out performance."
        ),
    }
    return params, metadata


def _valid_ids(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip()
    return values.notna() & values.ne("") & ~values.str.casefold().isin(
        {"unknown", "none", "nan", "na", "needs_review"}
    )


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build only engineering input features; never include IDs or provenance text."""
    X = pd.DataFrame(index=frame.index)
    for prefix, low_col, high_col, unit in NUMERIC_RANGES:
        low = pd.to_numeric(frame[low_col], errors="coerce")
        high = pd.to_numeric(frame[high_col], errors="coerce")
        invalid_order = low.notna() & high.notna() & high.lt(low)
        if invalid_order.any():
            raise ValueError(f"Invalid min/max ordering in {low_col}/{high_col}.")
        suffix = f"_{unit}" if unit else ""
        X[f"{prefix}_mid{suffix}"] = (low + high) / 2.0
        X[f"{prefix}_span{suffix}"] = (high - low).clip(lower=0)

    X["log10_perm_mid"] = np.log10(np.clip(X["perm_mid_md"], 1e-6, None))
    X["log10_visc_mid"] = np.log10(np.clip(X["visc_mid_cp"], 1e-6, None))
    formation = frame["formation_category"].astype("string").fillna("").str.strip()
    allowed_formations = ("Sandstone", "Carbonates", "Unconsolidated sands")
    invalid_formation = ~formation.isin(allowed_formations)
    if invalid_formation.any():
        values = sorted(formation[invalid_formation].dropna().astype(str).unique().tolist())
        raise ValueError(
            "Production feature schema does not accept unresolved formation categories: "
            f"{values}. Resolve/quarantine these rows instead of silently one-hot encoding them."
        )
    for category in allowed_formations:
        X[f"formation_{category.lower().replace(' ', '_')}"] = formation.eq(category).astype(float)

    # Use the exact deployed v1 feature names/order. This makes the research
    # benchmark schema-compatible while not claiming the already-trained
    # production artifact has been fairly evaluated on held-out rows.
    X = X.reindex(columns=PRODUCTION_FEATURE_NAMES)
    if list(X.columns) != PRODUCTION_FEATURE_NAMES:
        raise AssertionError("Research feature schema diverged from the production v1 schema.")

    forbidden = [
        col for col in X.columns
        if col.casefold().endswith("_id")
        or col.casefold() in {
            "record_id", "field_id", "case_id", "raw_line", "source_report",
            "publication_title", "tagging_rationale", "needs_review",
        }
    ]
    if forbidden:
        raise AssertionError(f"Provenance metadata entered model features: {forbidden}")
    values = X.to_numpy(dtype=float)
    if np.isinf(values).any():
        raise ValueError("Feature matrix contains infinite values.")
    # Missing measurements are imputed inside each training fold, never before splitting.
    return X.astype(float)


def label_semantic_conflict_audit(frame: pd.DataFrame) -> tuple[pd.Series, list[dict[str, Any]]]:
    """Flag explicit source-text technique terms that conflict with structured labels."""
    mask = pd.Series(False, index=frame.index, dtype=bool)
    details: list[dict[str, Any]] = []
    for idx, row in frame.iterrows():
        structured_label = str(row.get("technique", "")).strip()
        structured_family = TECHNIQUE_FAMILY.get(structured_label)
        raw_text = str(row.get("raw_line", "") or "")
        if structured_family is None or not raw_text.strip():
            continue
        detected = [
            {"term": term, "family": TECHNIQUE_FAMILY[term]}
            for term, pattern in TECHNIQUE_PATTERNS if pattern.search(raw_text)
        ]
        explicit_miscible = any(
            item["term"] in {"Miscible acid gas", "Miscible CO2", "CO2 miscible", "Miscible HC"}
            for item in detected
        )
        if re.search(r"\bmiscible\b", raw_text, re.I) and not explicit_miscible:
            detected.append({
                "term": "Miscible (unspecified subtype)",
                "family": TECHNIQUE_FAMILY["Miscible (unspecified subtype)"],
            })
        conflicting = [item for item in detected if item["family"] != structured_family]
        if not conflicting:
            continue
        mask.loc[idx] = True
        details.append({
            "excel_row": int(idx + 2),
            "record_id": str(row.get("record_id", "")),
            "structured_technique_label": structured_label,
            "structured_label_family": structured_family,
            "source_text_technique_mentions": sorted({item["term"] for item in detected}),
            "potentially_conflicting_mentions": sorted({item["term"] for item in conflicting}),
            "raw_source_text": raw_text,
            "action": "quarantined pending manual source-table review; no automatic relabel",
        })
    return mask, details


def source_section_label_conflict_audit(
    frame: pd.DataFrame,
) -> tuple[pd.Series, list[dict[str, Any]]]:
    """Flag source-section/duplicate-case label conflicts without rewriting labels."""
    mask = pd.Series(False, index=frame.index, dtype=bool)
    details: list[dict[str, Any]] = []
    raw_col = "raw_line" if "raw_line" in frame.columns else None
    if raw_col is None:
        return mask, details

    normalized = frame[raw_col].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    labels = frame["technique"].astype(str).str.strip()
    grouped_labels: dict[str, set[str]] = {}
    for raw_text, label in zip(normalized, labels):
        grouped_labels.setdefault(raw_text, set()).add(label)

    for idx, row in frame.iterrows():
        raw_text = normalized.loc[idx]
        label = labels.loc[idx]
        source_expected = None
        evidence = None

        # These exact source rows occur in the OGJ PDF's CO2-miscible table
        # (pp. 3-5, before the CO2-immiscible heading). The duplicated HC label
        # lacks a distinct source-row/project identifier and is not auto-corrected.
        if (
            grouped_labels.get(raw_text) == {"Miscible CO2", "Miscible HC"}
            and label == "Miscible HC"
        ):
            source_expected = "Miscible CO2"
            evidence = (
                "Same exact raw_line is present under both Miscible CO2 and Miscible HC; "
                "the matched row appears in the OGJ 2014 PDF's CO2-miscible table on pp. 3-5, "
                "before the CO2-immiscible heading. The HC-labelled duplicate is quarantined, not relabelled."
            )
        elif raw_text.startswith("Shell Canada Peace River Alta.") and label in {
            "Nitrogen immiscible", "Polymer"
        }:
            source_expected = "Steam"
            evidence = (
                "OGJ 2014 PDF p. 9 lists these Peace River rows in the Canadian table continuation "
                "before the next Nitrogen heading, within the preceding Steam section. "
                "The conflicting structured label is quarantined, not relabelled."
            )
        elif raw_text.startswith("Chaparral Energy North Burbank Okla.") and label == "Nitrogen immiscible":
            source_expected = "Chemical, polymer, surfactant (subtype unspecified)"
            evidence = (
                "OGJ 2014 PDF p. 7 places North Burbank under 'Chemical, polymer, surfactant', "
                "not Nitrogen immiscible. The specific chemical subtype is not inferred."
            )
        elif raw_text.startswith("Occidental Midland Farms Unit Tex.") and label == "Nitrogen immiscible":
            source_expected = "Chemical, polymer, surfactant (subtype unspecified)"
            evidence = (
                "OGJ 2014 PDF p. 7 places Midland Farms Unit under 'Chemical, polymer, surfactant', "
                "not Nitrogen immiscible. The specific chemical subtype is not inferred."
            )

        if source_expected is None:
            continue
        mask.loc[idx] = True
        details.append({
            "excel_row": int(idx + 2),
            "record_id": str(row.get("record_id", "")),
            "structured_technique_label": label,
            "source_section_technique_or_context": source_expected,
            "raw_source_text": raw_text,
            "source_evidence": evidence,
            "action": "quarantined pending source-table adjudication; technique label unchanged",
        })

    return mask, details



def verified_field_mask(df: pd.DataFrame) -> pd.Series:
    """Only source-confirmed field IDs can contribute to field-level evaluation."""
    if "field_id" not in df.columns or "field_id_status" not in df.columns:
        return pd.Series(False, index=df.index)
    valid = _valid_ids(df["field_id"])
    status = df["field_id_status"].astype("string").fillna("").str.strip().str.casefold()
    return valid & status.isin({"verified", "confirmed"})


def _all_classes_present(labels: np.ndarray, indices: np.ndarray, classes: set[str]) -> bool:
    return set(labels[indices].astype(str)) == classes


def _class_group_counts(labels: np.ndarray, groups: np.ndarray, indices: np.ndarray) -> dict[str, int]:
    """Count independent fields supporting each class within a partition."""
    return {
        label: int(np.unique(groups[indices][labels[indices] == label]).size)
        for label in sorted(set(labels.astype(str)))
    }


def make_group_holdout(
    labels: np.ndarray,
    groups: np.ndarray,
    *,
    test_size: float = HOLDOUT_FRACTION,
    seed_start: int = SEED_START,
    seed_attempts: int = SEED_ATTEMPTS,
) -> tuple[np.ndarray, np.ndarray, int]:
    classes = set(labels.astype(str))
    for seed in range(seed_start, seed_start + seed_attempts):
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        train_idx, test_idx = next(splitter.split(np.zeros(len(labels)), labels, groups))
        train_support = _class_group_counts(labels, groups, train_idx)
        test_support = _class_group_counts(labels, groups, test_idx)
        if (
            set(groups[train_idx]).isdisjoint(set(groups[test_idx]))
            and _all_classes_present(labels, train_idx, classes)
            and _all_classes_present(labels, test_idx, classes)
            and all(count >= MINIMUM_TRAIN_FIELDS_PER_CLASS for count in train_support.values())
            and all(count >= MINIMUM_HOLDOUT_FIELDS_PER_CLASS for count in test_support.values())
        ):
            return train_idx, test_idx, seed
    raise ValueError(
        "Could not find a field-isolated holdout with every eligible class represented "
        f"by at least {MINIMUM_TRAIN_FIELDS_PER_CLASS} training fields and "
        f"{MINIMUM_HOLDOUT_FIELDS_PER_CLASS} test fields. Do not use a row-wise fallback."
    )


def make_group_cv(
    labels: np.ndarray, groups: np.ndarray, *, requested_folds: int = REQUESTED_FOLDS
) -> tuple[list[tuple[np.ndarray, np.ndarray]], int, int]:
    class_group_support = {
        label: int(np.unique(groups[labels == label]).size)
        for label in sorted(set(labels.astype(str)))
    }
    folds = min(requested_folds, min(class_group_support.values(), default=0))
    if folds < 2:
        raise ValueError(
            "At least two independent fields per eligible class are required for grouped CV."
        )
    classes = set(labels.astype(str))
    for n_splits in range(folds, 1, -1):
        for seed in range(SEED_START, SEED_START + SEED_ATTEMPTS):
            splitter = StratifiedGroupKFold(
                n_splits=n_splits, shuffle=True, random_state=seed
            )
            splits = list(splitter.split(np.zeros(len(labels)), labels, groups))
            valid = True
            for train_idx, test_idx in splits:
                if not set(groups[train_idx]).isdisjoint(set(groups[test_idx])):
                    valid = False
                    break
                if not (
                    _all_classes_present(labels, train_idx, classes)
                    and _all_classes_present(labels, test_idx, classes)
                ):
                    valid = False
                    break
            if valid:
                return splits, n_splits, seed
    raise ValueError(
        "Could not construct group-isolated CV folds with complete class coverage. "
        "Report evaluation as unavailable rather than leaking fields across folds."
    )



class ProductionRecipeCatBoostEstimator(ClassifierMixin, BaseEstimator):
    """Clone-safe wrapper that constructs CatBoost only inside fit()."""

    def __init__(self, params: dict[str, Any]):
        self.params = params

    def fit(self, X: pd.DataFrame, y: np.ndarray):
        self.model_ = CatBoostClassifier(**self.params)
        self.model_.fit(X, y)
        self.classes_ = self.model_.classes_
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.model_.predict(X)).reshape(-1).astype(str)


def make_models(eligible_classes: list[str], production_params: dict[str, Any] | None = None) -> dict[str, Any]:
    # Median imputation is fitted separately inside each fold to avoid validation leakage.
    return {
        "DummyPrior": make_pipeline(
            SimpleImputer(strategy="median"),
            DummyClassifier(strategy="prior"),
        ),
        # CatBoost is evaluated on exactly the same field-isolated partitions as
        # the simple prior baseline. Imputation and missingness indicators are
        # fitted within each training fold, preventing validation leakage.
        "CatBoost": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            CatBoostClassifier(
                iterations=250,
                depth=6,
                learning_rate=0.05,
                loss_function="MultiClass",
                auto_class_weights="Balanced",
                random_seed=42,
                verbose=False,
                allow_writing_files=False,
                thread_count=2,
            ),
        ),
        **({
            "ProductionRecipeCatBoost": make_pipeline(
                SimpleImputer(strategy="median", add_indicator=True),
                ProductionRecipeCatBoostEstimator(production_params),
            )
        } if production_params is not None else {}),
        "LogisticRegression": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            StandardScaler(),
            LogisticRegression(max_iter=4000, class_weight="balanced", random_state=42),
        ),
        "RandomForest": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            RandomForestClassifier(
                n_estimators=400, min_samples_leaf=2, class_weight="balanced_subsample",
                random_state=42, n_jobs=-1,
            ),
        ),
        "ExtraTrees": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            ExtraTreesClassifier(
                n_estimators=400, min_samples_leaf=2, class_weight="balanced",
                random_state=42, n_jobs=-1,
            ),
        ),
        "HistGradientBoosting": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            HistGradientBoostingClassifier(
                max_iter=200, l2_regularization=1.0, random_state=42,
            ),
        ),
    }


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def decision_record(record_id: object, source_adj_by_id: pd.DataFrame) -> dict:
    key = str(record_id or "")
    if key not in source_adj_by_id.index:
        return {
            "source_adjudication_status": "unresolved_quarantined",
            "source_adjudicated_technique": "",
            "source_adjudicated_model_class": "",
            "taxonomy_status": "unresolved",
        }
    row = source_adj_by_id.loc[key]
    return {
        "source_adjudication_status": str(row["adjudication_status"]),
        "source_adjudicated_technique": str(row["source_adjudicated_technique"]),
        "source_adjudicated_model_class": str(row["source_adjudicated_model_class"]),
        "taxonomy_status": str(row["taxonomy_status"]),
    }



def feature_ready_mask(frame: pd.DataFrame) -> pd.Series:
    """Rows whose ranges/formation satisfy the production input contract."""
    mask = frame["formation_category"].astype("string").isin(
        ["Sandstone", "Carbonates", "Unconsolidated sands"]
    )
    for _prefix, low_col, high_col, _unit in NUMERIC_RANGES:
        low = pd.to_numeric(frame[low_col], errors="coerce")
        high = pd.to_numeric(frame[high_col], errors="coerce")
        mask &= low.notna() & high.notna() & np.isfinite(low) & np.isfinite(high) & high.ge(low)
    return mask.fillna(False)


def evaluate_production_on_genuinely_unseen_fields(frame: pd.DataFrame) -> dict[str, Any]:
    """Compare the deployed artifact and retrained baselines only on fields absent from its training manifest."""
    if not TRAINING_MANIFEST_PATH.is_file() or not TRAINING_MEMBERSHIP_REPORT_PATH.is_file():
        return {
            "status": "blocked_training_membership_manifest_missing",
            "reason": "No verified production training-row manifest is available.",
        }
    manifest = pd.read_csv(TRAINING_MANIFEST_PATH, dtype={"record_id": "string"})
    membership_report = json.loads(TRAINING_MEMBERSHIP_REPORT_PATH.read_text(encoding="utf-8"))
    if membership_report.get("status") != "reconstructed_and_verified":
        return {"status": "blocked_training_membership_unverified", "reason": membership_report.get("status", "unknown")}
    if len(manifest) != 526 or manifest["record_id"].isna().any() or manifest["record_id"].duplicated().any():
        raise ValueError("Production training manifest does not contain exactly 526 unique record IDs.")
    current_artifact_sha256 = hashlib.sha256(PRODUCTION_MODEL_PATH.read_bytes()).hexdigest()
    if current_artifact_sha256 != membership_report.get("current_model_artifact_sha256"):
        raise ValueError("Production artifact hash differs from the training-membership provenance report.")

    training_ids = set(manifest["record_id"].astype(str))
    unknown_training_ids = training_ids - set(frame["record_id"].astype(str))
    if unknown_training_ids:
        raise ValueError(f"{len(unknown_training_ids)} manifest record IDs are absent from the current workbook.")

    member_mask = frame["record_id"].astype(str).isin(training_ids)
    confirmed_field = verified_field_mask(frame)
    training_members = frame.loc[member_mask].copy()
    unresolved_member_mask = ~verified_field_mask(training_members)
    if unresolved_member_mask.any():
        return {
            "status": "blocked_training_member_identity_unresolved",
            "training_rows": int(len(training_members)),
            "training_rows_without_confirmed_field_identity": int(unresolved_member_mask.sum()),
            "reason": "A genuine unseen-field holdout cannot be proven when a production training row has no confirmed field identity.",
        }

    training_fields = set(training_members["field_id"].astype(str))
    ready = feature_ready_mask(frame)
    target_valid = frame["technique"].astype("string").isin(PRODUCTION_CLASSES)
    unseen_mask = confirmed_field & ready & target_valid & ~frame["field_id"].astype(str).isin(training_fields)
    unseen = frame.loc[unseen_mask].copy().reset_index(drop=True)
    if len(unseen) == 0:
        return {
            "status": "no_genuinely_unseen_confirmed_fields",
            "training_rows": int(len(training_members)),
            "training_field_groups": int(len(training_fields)),
            "unseen_holdout_rows": 0,
            "reason": "Every production-eligible confirmed field appears in at least one production training row, or remaining rows fail the production input contract.",
        }
    if set(unseen["field_id"].astype(str)) & training_fields:
        raise AssertionError("Production training field IDs overlap the unseen-field holdout.")
    if set(unseen["record_id"].astype(str)) & training_ids:
        raise AssertionError("Production training record IDs overlap the unseen-field holdout.")

    train_ready_mask = feature_ready_mask(training_members)
    train_target_valid = training_members["technique"].astype("string").isin(PRODUCTION_CLASSES)
    model_train = training_members.loc[
        verified_field_mask(training_members) & train_ready_mask & train_target_valid
    ].copy().reset_index(drop=True)
    if model_train.empty:
        return {
            "status": "no_eligible_training_rows_after_source_adjudication",
            "training_manifest_rows": int(len(manifest)),
            "unseen_holdout_rows": int(len(unseen)),
        }

    y_train = model_train["technique"].astype(str).to_numpy()
    y_test = unseen["technique"].astype(str).to_numpy()
    X_train = build_features(model_train)
    X_test = build_features(unseen)
    training_classes = sorted(set(y_train))
    test_classes = sorted(set(y_test))
    evaluated_classes = sorted(set(training_classes) & set(test_classes))
    test_field_support = {
        label: int(unseen.loc[unseen["technique"].astype(str).eq(label), "field_id"].nunique())
        for label in PRODUCTION_CLASSES
    }
    train_field_support = {
        label: int(model_train.loc[model_train["technique"].astype(str).eq(label), "field_id"].nunique())
        for label in PRODUCTION_CLASSES
    }

    # Direct artifact prediction uses the exact same untouched records as every
    # fold-retrained comparator. The stored artifact itself is never refit.
    deployed_model = joblib.load(PRODUCTION_MODEL_PATH)
    label_encoder = joblib.load(PRODUCTION_LABEL_ENCODER_PATH)
    raw_predictions = np.asarray(deployed_model.predict(X_test)).reshape(-1)
    if np.issubdtype(raw_predictions.dtype, np.number):
        predicted = label_encoder.inverse_transform(raw_predictions.astype(int))
    else:
        predicted = raw_predictions.astype(str)
    if not set(predicted.astype(str)).issubset(set(PRODUCTION_CLASSES)):
        raise ValueError("Deployed artifact emitted labels outside the v1 production class encoder.")

    def metrics_for(y_true, y_pred) -> dict[str, Any]:
        present = sorted(set(y_true.astype(str)))
        return {
            "macro_f1_observed_test_classes": float(f1_score(
                y_true, y_pred, labels=present, average="macro", zero_division=0
            )),
            "macro_f1_all_nine_classes": float(f1_score(
                y_true, y_pred, labels=PRODUCTION_CLASSES, average="macro", zero_division=0
            )),
            "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "confusion_matrix_all_nine_classes": confusion_matrix(
                y_true, y_pred, labels=PRODUCTION_CLASSES
            ).tolist(),
        }

    comparison = [{
        "model": "DeployedCatBoostV1.0.0",
        **metrics_for(y_test, predicted.astype(str)),
    }]
    try:
        prod_params, recipe_meta = production_recipe_parameters(training_classes)
        candidates = make_models(training_classes, prod_params)
        for name, estimator in candidates.items():
            model = clone(estimator)
            model.fit(X_train, y_train)
            candidate_predictions = model.predict(X_test).astype(str)
            comparison.append({"model": name, **metrics_for(y_test, candidate_predictions)})
    except Exception as exc:
        recipe_meta = {
            "status": "blocked",
            "reason": f"{type(exc).__name__}: {exc}",
        }

    # Corrected labels are used for the source truth; the production artifact was
    # trained on the original labels. This difference is intentional and recorded.
    nine_classes_present = set(test_classes) == set(PRODUCTION_CLASSES)
    every_class_has_holdout_support = all(
        test_field_support.get(label, 0) >= MINIMUM_HOLDOUT_FIELDS_PER_CLASS
        for label in PRODUCTION_CLASSES
    )
    full_source_support = {
        label: int(frame.loc[
            confirmed_field & frame["technique"].astype("string").eq(label), "field_id"
        ].nunique())
        for label in PRODUCTION_CLASSES
    }
    full_source_support_pass = all(
        count >= MINIMUM_FIELDS_PER_CLASS for count in full_source_support.values()
    )
    return {
        "status": (
            "unseen_field_diagnostic_all_nine_classes_present"
            if nine_classes_present and every_class_has_holdout_support
            else "unseen_field_diagnostic_subset_only_full_nine_class_gate_blocked"
        ),
        "training_membership_source": str(TRAINING_MANIFEST_PATH.relative_to(ROOT)),
        "training_membership_sha256": membership_report.get("training_membership_sha256_ordered_record_ids"),
        "training_rows_in_manifest": int(len(manifest)),
        "training_rows_used_for_retrained_candidates": int(len(model_train)),
        "production_training_field_groups": int(len(training_fields)),
        "unseen_field_holdout_rows": int(len(unseen)),
        "unseen_field_holdout_field_groups": int(unseen["field_id"].nunique()),
        "record_id_overlap": sorted(set(unseen["record_id"].astype(str)) & training_ids),
        "field_id_overlap": sorted(set(unseen["field_id"].astype(str)) & training_fields),
        "all_test_fields_absent_from_production_training": True,
        "training_independent_fields_by_class": train_field_support,
        "unseen_holdout_independent_fields_by_class": test_field_support,
        "unseen_test_classes": test_classes,
        "all_nine_classes_present_in_unseen_holdout": nine_classes_present,
        "every_nine_class_has_at_least_two_unseen_fields": every_class_has_holdout_support,
        "confirmed_field_support_all_nine_classes": full_source_support,
        "promotion_support_gate": (
            "pass" if full_source_support_pass else "blocked_insufficient_confirmed_independent_field_support"
        ),
        "comparison_models": comparison,
        "fold_retrained_production_recipe_metadata": recipe_meta,
        "label_truth": "source-adjudicated OGJ technique labels; original structured labels are preserved separately",
        "important_limitations": [
            "The deployed artifact predictions are evaluated only on confirmed field groups with no record in the reconstructed production training manifest.",
            "Rows with incomplete required inputs or source techniques outside the v1 nine-class taxonomy are excluded.",
            "If one or more classes lack sufficient confirmed independent fields, scores are diagnostic subset evidence, not a full nine-class promotion result.",
            "The deployed artifact was trained on original structured labels; this evaluation uses the source-adjudicated labels as reference truth.",
            "This task predicts observed technique associations, not EOR success, recovery uplift, or economics.",
        ],
    }


def audit_and_benchmark(dataset: Path = DATASET) -> dict[str, Any]:
    if not dataset.is_file():
        raise FileNotFoundError(f"Canonical OGJ2014 workbook not found: {dataset}")
    df = pd.read_excel(dataset, sheet_name=SHEET, engine="openpyxl")
    missing_columns = sorted(REQUIRED_SOURCE_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required source columns: {missing_columns}")
    if df.empty:
        raise ValueError("OGJ2014 source table is empty.")
    if df["record_id"].isna().any() or not df["record_id"].is_unique:
        raise ValueError("record_id must be populated and unique for every source row.")
    if df["technique"].isna().any() or df["technique"].astype(str).str.strip().eq("").any():
        raise ValueError("Original structured technique labels must remain present.")

    # Audit the original structured labels first. These columns remain unchanged
    # in the workbook; the sidecar supplies a separate, source-adjudicated target.
    original_structured_labels = df["technique"].astype("string").str.strip().copy()
    explicit_detected_mask, explicit_conflict_details = label_semantic_conflict_audit(df)
    section_detected_mask, source_section_conflict_details = source_section_label_conflict_audit(df)
    detected_conflict_mask = explicit_detected_mask | section_detected_mask
    detected_conflict_details = explicit_conflict_details + source_section_conflict_details
    detected_conflict_ids = {
        str(item.get("record_id", "")) for item in detected_conflict_details
    }

    if not SOURCE_ADJUDICATION_PATH.is_file():
        raise FileNotFoundError(
            f"Source adjudication register missing: {SOURCE_ADJUDICATION_PATH}. "
            "Run scripts/build_ogj2014_source_adjudications.py first."
        )
    adjudication_df = pd.read_csv(SOURCE_ADJUDICATION_PATH, dtype={"record_id": "string"}).fillna("")
    required_adjudication_columns = {
        "record_id", "excel_row", "raw_source_text", "source_adjudicated_technique",
        "source_adjudicated_model_class", "adjudication_status", "source_context_type",
    }
    missing_adjudication_columns = sorted(required_adjudication_columns - set(adjudication_df.columns))
    if missing_adjudication_columns:
        raise ValueError(f"Source adjudication register lacks columns: {missing_adjudication_columns}")
    if adjudication_df["record_id"].duplicated().any():
        raise ValueError("Source adjudication register contains duplicate record IDs.")
    if len(adjudication_df) != 187:
        raise ValueError(f"Expected 187 source adjudication decisions, found {len(adjudication_df)}.")

    workbook_ids = set(df["record_id"].astype(str))
    if not set(adjudication_df["record_id"].astype(str)).issubset(workbook_ids):
        raise ValueError("The source adjudication register references unknown record IDs.")
    conflict_register_ids = set(
        adjudication_df.loc[
            adjudication_df["source_context_type"].ne("exact_partial_row_profile_match"),
            "record_id",
        ].astype(str)
    )
    if conflict_register_ids != detected_conflict_ids:
        raise ValueError(
            "Source adjudication register does not exactly cover the 179 detected conflict records. "
            f"Missing={sorted(detected_conflict_ids-conflict_register_ids)[:5]}, "
            f"extra={sorted(conflict_register_ids-detected_conflict_ids)[:5]}"
        )
    if not set(adjudication_df["adjudication_status"]).issubset({
        "source_adjudicated_in_taxonomy", "source_adjudicated_out_of_taxonomy",
    }):
        raise ValueError("Every review-queue record must be resolved in-taxonomy or explicitly out-of-taxonomy.")

    original_ids_to_row = {
        str(record_id): int(index + 2) for index, record_id in enumerate(df["record_id"])
    }
    raw_by_id = dict(zip(df["record_id"].astype(str), df["raw_line"].astype(str)))
    for item in adjudication_df.itertuples(index=False):
        record_id = str(item.record_id)
        actual_row = original_ids_to_row.get(record_id)
        if actual_row != int(item.excel_row):
            raise ValueError(f"Excel-row/record-ID mismatch for {record_id}.")
        if clean_text(raw_by_id[record_id]) != clean_text(item.raw_source_text):
            raise ValueError(f"Raw source text changed for adjudicated record {record_id}.")

    source_adj_by_id = adjudication_df.set_index("record_id", drop=False)
    source_adjudicated_labels = original_structured_labels.copy()
    source_adjudication_status = pd.Series("not_flagged_by_source_audit", index=df.index, dtype="string")
    target_is_out_of_taxonomy = pd.Series(False, index=df.index, dtype=bool)
    for index, record_id in enumerate(df["record_id"].astype(str)):
        if record_id not in source_adj_by_id.index:
            continue
        decision = source_adj_by_id.loc[record_id]
        model_label = str(decision["source_adjudicated_model_class"]).strip()
        if model_label:
            if model_label not in PRODUCTION_CLASSES:
                raise ValueError(f"Adjudicated target is outside the production taxonomy: {model_label}")
            source_adjudicated_labels.iloc[index] = model_label
        else:
            source_adjudicated_labels.iloc[index] = pd.NA
            target_is_out_of_taxonomy.iloc[index] = True
        source_adjudication_status.iloc[index] = str(decision["adjudication_status"])

    df["structured_technique_label"] = original_structured_labels
    df["source_adjudication_status"] = source_adjudication_status
    df["technique"] = source_adjudicated_labels
    target_valid = df["technique"].astype("string").isin(PRODUCTION_CLASSES)

    source_adjudicated_ids = set(adjudication_df["record_id"].astype(str))
    unresolved_explicit_mask = explicit_detected_mask & ~df["record_id"].astype(str).isin(source_adjudicated_ids)
    unresolved_section_mask = section_detected_mask & ~df["record_id"].astype(str).isin(source_adjudicated_ids)
    label_conflict_mask = unresolved_explicit_mask | unresolved_section_mask
    label_reviewed = df.loc[~label_conflict_mask].copy()
    explicit_conflict_mask = unresolved_explicit_mask
    source_section_conflict_mask = unresolved_section_mask
    explicit_conflict_details = [
        {**item, **decision_record(item.get("record_id", ""), source_adj_by_id)}
        for item in explicit_conflict_details
    ]
    source_section_conflict_details = [
        {**item, **decision_record(item.get("record_id", ""), source_adj_by_id)}
        for item in source_section_conflict_details
    ]
    label_conflict_details = explicit_conflict_details + source_section_conflict_details

    source_valid_field = _valid_ids(df["field_id"])
    source_status = df["field_id_status"].astype("string").fillna("").str.strip().str.casefold()
    source_verified_field = source_valid_field & source_status.isin({"verified", "confirmed"}) & target_valid
    source_field_support = (
        df.loc[source_valid_field & target_valid].groupby("technique")["field_id"].nunique().sort_values()
    )
    source_verified_field_support = {
        label: int(df.loc[
            source_verified_field & df["technique"].astype("string").eq(label), "field_id"
        ].nunique())
        for label in PRODUCTION_CLASSES
    }

    identity_status = label_reviewed["field_id_status"].astype("string").fillna("").str.strip().str.casefold()
    verified_field = verified_field_mask(label_reviewed) & label_reviewed["technique"].astype("string").isin(PRODUCTION_CLASSES)
    # Only confirmed field IDs and source-adjudicated in-taxonomy labels enter the model scope.
    known = label_reviewed.loc[verified_field].copy()
    support_counts = {
        label: int(known.loc[known["technique"].astype(str).eq(label), "field_id"].nunique())
        for label in PRODUCTION_CLASSES
    }
    field_support = pd.Series(support_counts).sort_values()
    verified_field_support_after_quarantine = dict(support_counts)
    eligible_classes = sorted(
        label for label, count in support_counts.items()
        if count >= MINIMUM_FIELDS_PER_CLASS
    )
    unsupported_classes = {
        label: int(count) for label, count in support_counts.items()
        if count < MINIMUM_FIELDS_PER_CLASS
    }
    if len(eligible_classes) < 2:
        raise ValueError(
            "Fewer than two source-adjudicated classes meet the confirmed-field support threshold. "
            "The full nine-class evaluation is unavailable."
        )

    source_adjudication_summary = {
        "source_conflicts_detected": int(detected_conflict_mask.sum()),
        "explicit_text_conflicts_detected": int(explicit_detected_mask.sum()),
        "source_section_conflicts_detected": int(section_detected_mask.sum()),
        "source_conflicts_adjudicated": int(len(detected_conflict_ids & source_adjudicated_ids)),
        "source_conflicts_unresolved": int(label_conflict_mask.sum()),
        "conflict_records_excluded_as_out_of_taxonomy": int(
            adjudication_df.loc[
                adjudication_df["source_context_type"].ne("exact_partial_row_profile_match")
                & adjudication_df["source_adjudicated_model_class"].eq(""),
            ].shape[0]
        ),
        "all_nine_classes_supported_at_minimum": all(support_counts.get(label, 0) >= MINIMUM_FIELDS_PER_CLASS for label in PRODUCTION_CLASSES),
        "class_field_support": support_counts,
        "minimum_confirmed_fields_per_class": MINIMUM_FIELDS_PER_CLASS,
        "source_adjudication_register": str(SOURCE_ADJUDICATION_PATH.relative_to(ROOT)),
    }

    # Preserve each row and its original source values; no numeric-profile deduplication.
    scope = known.loc[known["technique"].astype(str).isin(eligible_classes)].copy().reset_index(drop=True)

    scope_feature_completeness = {}
    scope_feature_completeness_by_class = {}
    for feature_name, low_col, high_col, _unit in NUMERIC_RANGES:
        low = pd.to_numeric(scope[low_col], errors="coerce")
        high = pd.to_numeric(scope[high_col], errors="coerce")
        missing_low = low.isna()
        missing_high = high.isna()
        scope_feature_completeness[feature_name] = {
            "rows": int(len(scope)),
            "missing_low": int(missing_low.sum()),
            "missing_high": int(missing_high.sum()),
            "both_endpoints_missing": int((missing_low & missing_high).sum()),
            "one_endpoint_missing": int((missing_low ^ missing_high).sum()),
        }
        scope_feature_completeness_by_class[feature_name] = {
            str(label): {
                "rows": int((scope["technique"] == label).sum()),
                "missing_low": int((scope.loc[scope["technique"] == label, low_col].pipe(pd.to_numeric, errors="coerce").isna()).sum()),
                "missing_high": int((scope.loc[scope["technique"] == label, high_col].pipe(pd.to_numeric, errors="coerce").isna()).sum()),
            }
            for label in eligible_classes
        }

    try:
        production_params, production_recipe_metadata = production_recipe_parameters(eligible_classes)
    except Exception as exc:
        # Keep the research baseline available, but make a failed recipe recovery
        # visible rather than silently substituting guessed production parameters.
        production_params = None
        production_recipe_metadata = {
            "status": "blocked",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    model_factories = make_models(eligible_classes, production_params)

    X = build_features(scope)
    y = scope["technique"].astype(str).to_numpy()
    groups = scope["field_id"].astype(str).to_numpy()
    if len(scope) != len(X) or len(scope) != len(y) or len(scope) != len(groups):
        raise AssertionError("Feature/label/group row alignment changed.")
    train_idx, test_idx, holdout_seed = make_group_holdout(y, groups)
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    groups_train = groups[train_idx]
    cv_splits, cv_folds, cv_seed = make_group_cv(y_train, groups_train)

    cv_rows = []
    fitted_cv_models = {}
    for model_name, estimator in model_factories.items():
        fold_scores = []
        for fold_index, (fold_train, fold_test) in enumerate(cv_splits, start=1):
            if not set(groups_train[fold_train]).isdisjoint(set(groups_train[fold_test])):
                raise AssertionError(f"{model_name} fold {fold_index} has field leakage.")
            model = clone(estimator)
            model.fit(X_train.iloc[fold_train], y_train[fold_train])
            predictions = model.predict(X_train.iloc[fold_test]).astype(str)
            fold_scores.append({
                "fold": fold_index,
                "macro_f1": float(f1_score(y_train[fold_test], predictions, average="macro", zero_division=0)),
                "balanced_accuracy": float(balanced_accuracy_score(y_train[fold_test], predictions)),
                "accuracy": float(accuracy_score(y_train[fold_test], predictions)),
            })
        macro_values = [row["macro_f1"] for row in fold_scores]
        cv_rows.append({
            "model": model_name,
            "cv_folds": cv_folds,
            "cv_macro_f1_mean": float(np.mean(macro_values)),
            "cv_macro_f1_std": float(np.std(macro_values)),
            "cv_balanced_accuracy_mean": float(np.mean([row["balanced_accuracy"] for row in fold_scores])),
            "cv_accuracy_mean": float(np.mean([row["accuracy"] for row in fold_scores])),
            "fold_scores": fold_scores,
        })
    cv_rows.sort(key=lambda row: (row["cv_macro_f1_mean"], row["cv_balanced_accuracy_mean"]), reverse=True)
    selected_name = cv_rows[0]["model"]

    # Repeated field-isolated holdouts quantify sensitivity to which fields land in test.
    # These overlapping resamples are a split-variability analysis, not independent
    # replications or a formal confidence interval.
    repeated_scores: dict[str, list[dict[str, float]]] = {
        name: [] for name in model_factories
    }
    repeated_seeds: list[int] = []
    repeated_split_summaries: list[dict[str, Any]] = []
    for repeat_index in range(REPEATED_HOLDOUTS):
        split_train, split_test, split_seed = make_group_holdout(
            y, groups, seed_start=SEED_START + repeat_index * SEED_ATTEMPTS,
            seed_attempts=SEED_ATTEMPTS,
        )
        split_train_groups = groups[split_train]
        split_test_groups = groups[split_test]
        if not set(split_train_groups).isdisjoint(set(split_test_groups)):
            raise AssertionError(f"Repeated holdout {repeat_index + 1} has field leakage.")
        train_support = _class_group_counts(y, groups, split_train)
        test_support = _class_group_counts(y, groups, split_test)
        if (
            min(train_support.values()) < MINIMUM_TRAIN_FIELDS_PER_CLASS
            or min(test_support.values()) < MINIMUM_HOLDOUT_FIELDS_PER_CLASS
        ):
            raise AssertionError(f"Repeated holdout {repeat_index + 1} violates class field support.")
        repeated_seeds.append(split_seed)
        repeated_split_summaries.append({
            "repeat": repeat_index + 1,
            "seed": split_seed,
            "train_rows": int(len(split_train)),
            "test_rows": int(len(split_test)),
            "train_fields": int(pd.Series(split_train_groups).nunique()),
            "test_fields": int(pd.Series(split_test_groups).nunique()),
            "train_fields_per_class": train_support,
            "test_fields_per_class": test_support,
            "field_overlap": sorted(set(split_train_groups).intersection(set(split_test_groups))),
        })
        for name, estimator in model_factories.items():
            model = clone(estimator)
            model.fit(X.iloc[split_train], y[split_train])
            predictions = model.predict(X.iloc[split_test]).astype(str)
            repeated_scores[name].append({
                "macro_f1": float(f1_score(y[split_test], predictions, labels=eligible_classes, average="macro", zero_division=0)),
                "balanced_accuracy": float(balanced_accuracy_score(y[split_test], predictions)),
                "accuracy": float(accuracy_score(y[split_test], predictions)),
            })
    repeated_summary = []
    for name, scores in repeated_scores.items():
        row: dict[str, Any] = {"model": name, "repeated_holdouts": len(scores)}
        for metric in ("macro_f1", "balanced_accuracy", "accuracy"):
            values = np.asarray([score[metric] for score in scores], dtype=float)
            row[f"{metric}_mean"] = float(values.mean())
            row[f"{metric}_std"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
            row[f"{metric}_p05"] = float(np.quantile(values, 0.05))
            row[f"{metric}_p95"] = float(np.quantile(values, 0.95))
        row["interpretation"] = (
            "Empirical split-variability summary; 5th-95th percentiles are not a formal confidence interval."
        )
        repeated_summary.append(row)
    repeated_summary.sort(
        key=lambda row: (row["macro_f1_mean"], row["balanced_accuracy_mean"]), reverse=True
    )
    selected = clone(model_factories[selected_name])
    selected.fit(X_train, y_train)
    holdout_predictions = selected.predict(X_test).astype(str)
    labels_order = eligible_classes
    production_recipe_holdout = None
    if "ProductionRecipeCatBoost" in model_factories:
        recipe_model = clone(model_factories["ProductionRecipeCatBoost"])
        recipe_model.fit(X_train, y_train)
        recipe_predictions = recipe_model.predict(X_test).astype(str)
        production_recipe_holdout = {
            "macro_f1": float(f1_score(y_test, recipe_predictions, labels=labels_order, average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y_test, recipe_predictions)),
            "accuracy": float(accuracy_score(y_test, recipe_predictions)),
        }

    deployed_artifact_unseen_field_comparison = evaluate_production_on_genuinely_unseen_fields(df)
    training_membership_summary = (
        json.loads(TRAINING_MEMBERSHIP_REPORT_PATH.read_text(encoding="utf-8"))
        if TRAINING_MEMBERSHIP_REPORT_PATH.is_file() else None
    )
    full_nine_class_gate_pass = bool(source_adjudication_summary["all_nine_classes_supported_at_minimum"])

    report = {
        "dataset": str(dataset.relative_to(ROOT)),
        "sheet": SHEET,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "study_type": "source-adjudicated observed EOR technique classification",
        "not_a_prediction_of": "EOR success, recovery uplift, or economic value",
        "source_adjudication": source_adjudication_summary,
        "full_nine_class_support_gate": {
            "status": "passed" if full_nine_class_gate_pass else "blocked_insufficient_confirmed_independent_field_support",
            "minimum_confirmed_independent_fields_per_class": MINIMUM_FIELDS_PER_CLASS,
            "class_field_support": source_adjudication_summary["class_field_support"],
            "unsupported_classes": unsupported_classes,
            "required_classes": PRODUCTION_CLASSES,
        },
        "production_model_comparison": {
            "status": (
                "training_membership_reconstructed_direct_unseen_field_check_completed_full_class_gate_passed"
                if full_nine_class_gate_pass else
                "training_membership_reconstructed_direct_unseen_field_check_completed_full_nine_class_gate_blocked"
            ),
            "artifact": "outputs/model_artifacts/eor_catboost_v1.0.0.joblib",
            "artifact_config": "outputs/model_artifacts/config_catboost_v1.0.0.json",
            "artifact_version": "1.0.0",
            "artifact_class_count": 9,
            "artifact_configured_training_rows": 526,
            "source_workbook_rows": int(len(df)),
            "training_record_ids_available": bool(TRAINING_MANIFEST_PATH.is_file()),
            "training_dataset_hash_available": bool(
                training_membership_summary
                and training_membership_summary.get("historic_source_workbook_sha256")
                and training_membership_summary.get("training_membership_sha256_ordered_record_ids")
            ),
            "production_hyperparameters_fully_recorded_in_config": False,
            "effective_hyperparameters_recovered_from_serialized_model": True,
            "training_membership_reconstruction": training_membership_summary,
            "direct_deployed_artifact_evaluation_on_genuinely_unseen_fields": deployed_artifact_unseen_field_comparison,
            "reason": (
                "The historical training notebook/config and unchanged v1.0.0 artifact were used to reconstruct "
                "the exact 526 training record IDs and source workbook hashes. Evaluation now excludes every field "
                "with any production-training row. This permits a genuine unseen-field diagnostic, but does not "
                "override the full nine-class support gate: classes below the minimum remain promotion blockers. "
                "The original config still omits some effective CatBoost settings; these were recovered from the "
                "serialized artifact for fold-retrained recipe comparison."
            ),
            "allowed_next_step": (
                "Source-review the low-support class gaps and obtain additional independently documented fields. "
                "Do not promote based on a restricted pilot or an unseen-field diagnostic that lacks support across all nine classes."
            ),
            "research_pilot_classes": eligible_classes,
            "classes_below_minimum_confirmed_field_support": unsupported_classes,
            "fold_retrained_recipe": {
                **production_recipe_metadata,
                "grouped_cv": next(
                    (row for row in cv_rows if row["model"] == "ProductionRecipeCatBoost"),
                    None,
                ),
                "repeated_field_holdouts": next(
                    (row for row in repeated_summary if row["model"] == "ProductionRecipeCatBoost"),
                    None,
                ),
                "restricted_pilot_untouched_grouped_holdout_metrics": production_recipe_holdout,
            },
        },
        "row_preservation": {
            "source_rows": int(len(df)),
            "unique_record_ids": int(df["record_id"].nunique()),
            "rows_with_resolved_field_id_before_label_quarantine": int(source_valid_field.sum()),
            "rows_excluded_for_unresolved_field_id": int((~source_valid_field).sum()),
            "rows_quarantined_for_unresolved_label_conflicts": int(label_conflict_mask.sum()),
            "source_label_conflicts_detected": int(detected_conflict_mask.sum()),
            "source_label_conflicts_source_adjudicated": int(source_adjudication_summary["source_conflicts_adjudicated"]),
            "source_adjudication_rows_outside_v1_taxonomy": int(target_is_out_of_taxonomy.sum()),
            "rows_quarantined_for_explicit_text_conflict_unresolved": int(explicit_conflict_mask.sum()),
            "explicit_text_conflict_rows_detected": int(explicit_detected_mask.sum()),
            "rows_quarantined_for_source_section_conflict_unresolved": int(source_section_conflict_mask.sum()),
            "source_section_conflict_rows_detected": int(section_detected_mask.sum()),
            "label_conflict_rows_also_missing_field_id": int((label_conflict_mask & ~source_valid_field).sum()),
            "rows_remaining_after_unresolved_conflict_quarantine": int(len(label_reviewed)),
            "rows_excluded_from_v1_target_as_out_of_taxonomy": int(target_is_out_of_taxonomy.sum()),
            "eligible_scope_rows": int(len(scope)),
            "feature_profile_deduplication": False,
            "source_rows_merged": False,
        },
        "field_support_all_classes_before_label_quarantine": {
            str(k): int(v) for k, v in source_field_support.sort_index().items()
        },
        "field_support_all_classes_after_label_quarantine": {
            str(k): int(v) for k, v in field_support.sort_index().items()
        },
        "field_identity_status_counts_before_label_quarantine": {
            str(k): int(v) for k, v in source_status.value_counts(dropna=False).sort_index().items()
        },
        "field_identity_status_counts_after_label_quarantine": {
            str(k): int(v) for k, v in identity_status.value_counts(dropna=False).sort_index().items()
        },
        "verified_independent_field_support_all_classes_before_label_quarantine": source_verified_field_support,
        "verified_independent_field_support_all_classes_after_label_quarantine": verified_field_support_after_quarantine,
        "label_semantic_review": {
            "quarantined_rows_total": int(label_conflict_mask.sum()),
            "explicit_text_conflicts_detected": int(explicit_detected_mask.sum()),
            "source_section_conflicts_detected": int(section_detected_mask.sum()),
            "source_conflicts_adjudicated": int(source_adjudication_summary["source_conflicts_adjudicated"]),
            "unresolved_conflict_rows_quarantined": int(label_conflict_mask.sum()),
            "adjudication_out_of_taxonomy_rows": int(source_adjudication_summary["conflict_records_excluded_as_out_of_taxonomy"]),
            "quarantined_by_original_structured_label": {
                str(k): int(v) for k, v in df.loc[label_conflict_mask, "structured_technique_label"].value_counts().sort_index().items()
            },
            "explicit_text_candidates": explicit_conflict_details,
            "source_section_candidates": source_section_conflict_details,
            "candidates": label_conflict_details,
            "policy": "Rows whose explicit source text or original table-section context conflicts with the structured label are excluded pending review. Technique labels are never automatically rewritten.",
        },
        "field_identity_verification_warning": (
            "Only source-confirmed identities enter grouped evaluation. The eight partial performance fragments have "
            "explicit full-profile source matches; the four Estreito source records share a canonical Rio Grande do Norte "
            "field ID but remain four distinct source rows. Salt Creek remains split by operator/geography."
        ),
        "minimum_independent_fields_per_class": MINIMUM_FIELDS_PER_CLASS,
        "minimum_holdout_fields_per_class": MINIMUM_HOLDOUT_FIELDS_PER_CLASS,
        "minimum_training_fields_per_class": MINIMUM_TRAIN_FIELDS_PER_CLASS,
        "eligible_classes": eligible_classes,
        "feature_completeness_in_eligible_scope": scope_feature_completeness,
        "feature_completeness_in_eligible_scope_by_class": scope_feature_completeness_by_class,
        "missing_value_handling": (
            "Numeric midpoint/span features are imputed inside each model pipeline using training-fold medians; "
            "tree pipelines also add missingness indicators. No imputer is fit on validation/test rows."
        ),
        "unsupported_classes_excluded_from_this_restricted_pilot": unsupported_classes,
        "restricted_scope_warning": (
            "The pilot excludes unsupported technique classes without renaming or merging them. "
            "Do not interpret these metrics as a validated nine-class production model."
        ),
        "feature_names": list(X.columns),
        "feature_missing_values": {
            str(column): int(count)
            for column, count in X.isna().sum().items() if int(count) > 0
        },
        "imputation_policy": "median imputation fitted within each training fold; missingness indicators for predictive estimators",
        "provenance_columns_used_as_features": False,
        "group_column": "field_id",
        "holdout": {
            "method": "GroupShuffleSplit with explicit complete-class coverage check",
            "test_fraction": float(len(test_idx) / len(scope)),
            "seed": holdout_seed,
            "train_rows": int(len(train_idx)),
            "test_rows": int(len(test_idx)),
            "train_fields": int(pd.Series(groups[train_idx]).nunique()),
            "test_fields": int(pd.Series(groups[test_idx]).nunique()),
            "train_fields_per_class": _class_group_counts(y, groups, train_idx),
            "test_fields_per_class": _class_group_counts(y, groups, test_idx),
            "field_overlap": sorted(set(groups[train_idx]).intersection(set(groups[test_idx]))),
        },
        "cross_validation": {
            "method": "StratifiedGroupKFold",
            "folds": cv_folds,
            "seed": cv_seed,
            "training_rows": int(len(train_idx)),
            "training_fields": int(pd.Series(groups_train).nunique()),
            "field_overlap_by_fold": [
                sorted(set(groups_train[tr]).intersection(set(groups_train[te])))
                for tr, te in cv_splits
            ],
            "model_comparison": cv_rows,
            "selection_metric": "mean grouped-CV macro-F1; balanced accuracy as tie-breaker",
        },
        "repeated_field_isolated_holdouts": {
            "requested_repeats": REPEATED_HOLDOUTS,
            "completed_repeats": len(repeated_split_summaries),
            "method": "Repeated GroupShuffleSplit; same field-isolated partitions for every model; minimum per-class field support enforced",
            "seed_start": SEED_START,
            "seed_attempts_per_repeat": SEED_ATTEMPTS,
            "field_overlap_by_repeat": [item["field_overlap"] for item in repeated_split_summaries],
            "split_support": repeated_split_summaries,
            "model_comparison": repeated_summary,
            "uncertainty_interpretation": "Across-split variability only; holdouts overlap and are not independent; percentiles are not confidence intervals.",
        },
        "selected_model": selected_name,
        "holdout_metrics": {
            "macro_f1": float(f1_score(y_test, holdout_predictions, labels=labels_order, average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y_test, holdout_predictions)),
            "accuracy": float(accuracy_score(y_test, holdout_predictions)),
            "per_class": classification_report(
                y_test, holdout_predictions, labels=labels_order, output_dict=True,
                zero_division=0,
            ),
            "confusion_matrix": confusion_matrix(y_test, holdout_predictions, labels=labels_order).tolist(),
            "confusion_matrix_labels": labels_order,
        },
        "promotion_status": (
            "not_eligible_for_promotion_insufficient_confirmed_independent_field_support"
            if not full_nine_class_gate_pass else
            "research_only_requires_engineering_review_and_external_validation"
        ),
        "limitations": [
            "Only source-confirmed field IDs are eligible for grouped evaluation. Eight partial fragments and four Estreito records were resolved from source table evidence without merging source rows; repeated rows still do not count as additional independent fields.",
            "The source table records observed techniques, not comparable outcomes or success labels.",
            "The 179 flagged source-label conflicts are captured in a separately versioned adjudication register. Source labels outside the v1 taxonomy remain excluded; original workbook labels are unchanged.",
            "Rows sharing a field remain in the same split; exact numeric profiles are not merged.",
            "The production training manifest was reconstructed from the historical workbook and preprocessing rules. Four classes remain below the minimum confirmed-field support gate; a full nine-class promotion decision remains blocked even though a direct unseen-field diagnostic is now possible.",
            "Repeated holdouts and grouped CV are preliminary internal estimates, not external validation.",
            "Repeated holdouts overlap in their training/test fields across repeats; score percentiles describe split variability, not formal confidence intervals.",
        ],
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "ogj2014_field_generalization_benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    pd.DataFrame([
        {key: value for key, value in row.items() if key != "fold_scores"}
        for row in cv_rows
    ]).to_csv(OUTPUT_DIR / "ogj2014_field_generalization_model_comparison.csv", index=False)
    pd.DataFrame(repeated_summary).to_csv(
        OUTPUT_DIR / "ogj2014_repeated_holdout_model_comparison.csv", index=False
    )
    return report


if __name__ == "__main__":
    print(json.dumps(audit_and_benchmark(), indent=2))
