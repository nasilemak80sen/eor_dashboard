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
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
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
DATASET = ROOT / "src" / "notebooks" / "ml_data" / "OGJ2014_extracted_vs_Table1.xlsx"
SHEET = "OGJ2014_Extracted_Rows"
OUTPUT_DIR = ROOT / "outputs" / "ml_research"
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


def make_models() -> dict[str, Any]:
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

    explicit_conflict_mask, explicit_conflict_details = label_semantic_conflict_audit(df)
    source_section_conflict_mask, source_section_conflict_details = source_section_label_conflict_audit(df)
    label_conflict_mask = explicit_conflict_mask | source_section_conflict_mask
    label_conflict_details = explicit_conflict_details + source_section_conflict_details
    label_reviewed = df.loc[~label_conflict_mask].copy()
    source_valid_field = _valid_ids(df["field_id"])
    source_status = df["field_id_status"].astype("string").fillna("").str.strip().str.casefold()
    source_verified_field = source_valid_field & source_status.isin({"verified", "confirmed"})
    source_field_support = df.loc[source_valid_field].groupby("technique")["field_id"].nunique().sort_values()
    source_verified_field_support = {
        str(label): int(df.loc[source_verified_field & df["technique"].astype(str).eq(str(label)), "field_id"].nunique())
        for label in sorted(df["technique"].astype(str).unique())
    }

    verified_field = verified_field_mask(label_reviewed)
    # Provisional or unresolved identities remain in audit outputs, but cannot
    # increase class support or enter a field-generalisation benchmark.
    known = label_reviewed.loc[verified_field].copy()
    field_support = known.groupby("technique")["field_id"].nunique().sort_values()
    verified_field_support_after_quarantine = {
        str(label): int(label_reviewed.loc[verified_field & label_reviewed["technique"].astype(str).eq(str(label)), "field_id"].nunique())
        for label in sorted(label_reviewed["technique"].astype(str).unique())
    }
    eligible_classes = sorted(
        field_support[field_support >= MINIMUM_FIELDS_PER_CLASS].index.astype(str).tolist()
    )
    unsupported_classes = {
        str(label): int(count)
        for label, count in field_support.items()
        if count < MINIMUM_FIELDS_PER_CLASS
    }
    if len(eligible_classes) < 2:
        raise ValueError("Fewer than two technique classes meet the field-support threshold after label-conflict quarantine.")

    # Preserve every eligible non-conflicting source row; no feature-profile deduplication or label aggregation.
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

    # Repeated field-isolated holdouts quantify sensitivity to which fields land in test.
    # These overlapping resamples are a split-variability analysis, not independent
    # replications or a formal confidence interval.
    repeated_scores: dict[str, list[dict[str, float]]] = {
        name: [] for name in make_models()
    }
    repeated_seeds: list[int] = []
    repeated_split_summaries: list[dict[str, Any]] = []
    model_factories = make_models()
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
            "rows_with_resolved_field_id_before_label_quarantine": int(source_valid_field.sum()),
            "rows_excluded_for_unresolved_field_id": int((~source_valid_field).sum()),
            "rows_quarantined_for_label_semantic_review": int(label_conflict_mask.sum()),
            "rows_quarantined_for_explicit_text_conflict": int(explicit_conflict_mask.sum()),
            "rows_quarantined_for_source_section_conflict": int(source_section_conflict_mask.sum()),
            "label_conflict_rows_also_missing_field_id": int((label_conflict_mask & ~source_valid_field).sum()),
            "rows_remaining_after_label_quarantine": int(len(label_reviewed)),
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
            "explicit_text_conflict_rows": int(explicit_conflict_mask.sum()),
            "source_section_conflict_rows": int(source_section_conflict_mask.sum()),
            "quarantined_by_structured_label": {
                str(k): int(v) for k, v in df.loc[label_conflict_mask, "technique"].value_counts().sort_index().items()
            },
            "explicit_text_candidates": explicit_conflict_details,
            "source_section_candidates": source_section_conflict_details,
            "candidates": label_conflict_details,
            "policy": "Rows whose explicit source text or original table-section context conflicts with the structured label are excluded pending review. Technique labels are never automatically rewritten.",
        },
        "field_identity_verification_warning": (
            "Only field IDs with explicit source-document evidence are marked confirmed; remaining parser-derived IDs "
            "stay provisional. Scores are research-only field-isolation estimates, not validated EOR recommendations "
            "or evidence of EOR success, recovery uplift, or economic value."
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
        "promotion_status": "research_baseline_only_requires_engineering_review",
        "limitations": [
            "Field identifiers are provisional parser-derived candidates; no field groups are marked verified/confirmed, so true unseen-field generalization is not yet established.",
            "The source table records observed techniques, not comparable outcomes or success labels.",
            "Rows with explicit source-text conflicts or source-table-section conflicts are quarantined until manually adjudicated; no automatic relabelling is performed.",
            "Rows sharing a field remain in the same split; exact numeric profiles are not merged.",
            "Five low-support classes are excluded from this restricted pilot and require more independent fields before full multiclass evaluation.",
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
