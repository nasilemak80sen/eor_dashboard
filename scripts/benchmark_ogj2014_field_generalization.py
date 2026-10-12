"""Field-isolated baseline benchmark for the OGJ2014 EOR technique table.

This is an observed-technique classification study, not a prediction of EOR
success. It preserves source rows, excludes unresolved field IDs from field-level
validation, and excludes low-support classes from this explicitly restricted
pilot without relabelling them.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
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

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "src" / "notebooks" / "ml_data" / "OGJ2014_extracted_vs_Table1.xlsx"
SHEET = "OGJ2014_Extracted_Rows"
OUTPUT_DIR = ROOT / "outputs" / "ml_research"
MINIMUM_FIELDS_PER_CLASS = 6
REQUESTED_FOLDS = 5
HOLDOUT_FRACTION = 0.20
SEED_START = 42
SEED_ATTEMPTS = 100
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
    "record_id", "technique", "formation_category", "field_id",
    *(column for _, lo, hi, _ in NUMERIC_RANGES for column in (lo, hi)),
}


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
    formation = frame["formation_category"].astype("string").fillna("Unknown").str.strip()
    for category in ("Sandstone", "Carbonates", "Unconsolidated sands", "Unknown"):
        X[f"formation_{category.lower().replace(' ', '_')}"] = formation.eq(category).astype(float)

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


def _all_classes_present(labels: np.ndarray, indices: np.ndarray, classes: set[str]) -> bool:
    return set(labels[indices].astype(str)) == classes


def _class_group_counts(labels: np.ndarray, groups: np.ndarray, indices: np.ndarray) -> dict[str, int]:
    """Count independent fields supporting each class within a partition."""
    return {
        label: int(np.unique(groups[indices][labels[indices] == label]).size)
        for label in sorted(set(labels.astype(str)))
    }


def make_group_holdout(
    labels: np.ndarray, groups: np.ndarray, *, test_size: float = HOLDOUT_FRACTION
) -> tuple[np.ndarray, np.ndarray, int]:
    classes = set(labels.astype(str))
    for seed in range(SEED_START, SEED_START + SEED_ATTEMPTS):
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


def make_models() -> dict[str, Any]:
    # Median imputation is fitted separately inside each fold to avoid validation leakage.
    return {
        "DummyPrior": make_pipeline(
            SimpleImputer(strategy="median"),
            DummyClassifier(strategy="prior"),
        ),
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
        raise ValueError("Technique labels must be present; do not infer or relabel them.")

    valid_field = _valid_ids(df["field_id"])
    known = df.loc[valid_field].copy()
    field_support = known.groupby("technique")["field_id"].nunique().sort_values()
    eligible_classes = sorted(
        field_support[field_support >= MINIMUM_FIELDS_PER_CLASS].index.astype(str).tolist()
    )
    unsupported_classes = {
        str(label): int(count)
        for label, count in field_support.items()
        if count < MINIMUM_FIELDS_PER_CLASS
    }
    if len(eligible_classes) < 2:
        raise ValueError("Fewer than two technique classes meet the field-support threshold.")

    # Preserve every eligible source row. No feature-profile deduplication or label aggregation.
    scope = known.loc[known["technique"].astype(str).isin(eligible_classes)].copy().reset_index(drop=True)
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
    for model_name, estimator in make_models().items():
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
    selected = make_models()[selected_name]
    selected.fit(X_train, y_train)
    holdout_predictions = selected.predict(X_test).astype(str)
    labels_order = eligible_classes

    report = {
        "dataset": str(dataset.relative_to(ROOT)),
        "sheet": SHEET,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "study_type": "observed EOR technique classification",
        "not_a_prediction_of": "EOR success, recovery uplift, or economic value",
        "row_preservation": {
            "source_rows": int(len(df)),
            "unique_record_ids": int(df["record_id"].nunique()),
            "rows_with_resolved_field_id": int(valid_field.sum()),
            "rows_excluded_for_unresolved_field_id": int((~valid_field).sum()),
            "eligible_scope_rows": int(len(scope)),
            "feature_profile_deduplication": False,
            "source_rows_merged": False,
        },
        "field_support_all_classes": {str(k): int(v) for k, v in field_support.sort_index().items()},
        "minimum_independent_fields_per_class": MINIMUM_FIELDS_PER_CLASS,
        "minimum_holdout_fields_per_class": MINIMUM_HOLDOUT_FIELDS_PER_CLASS,
        "minimum_training_fields_per_class": MINIMUM_TRAIN_FIELDS_PER_CLASS,
        "eligible_classes": eligible_classes,
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
        "promotion_status": "research_baseline_only_requires_engineering_review",
        "limitations": [
            "Field identifiers remain provisional and require domain review.",
            "The source table records observed techniques, not comparable outcomes or success labels.",
            "Rows sharing a field remain in the same split; exact numeric profiles are not merged.",
            "Four low-support classes are excluded from this restricted pilot and require more independent fields before full multiclass evaluation.",
            "A single holdout and grouped CV are preliminary estimates, not external validation.",
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
    return report


if __name__ == "__main__":
    print(json.dumps(audit_and_benchmark(), indent=2))
