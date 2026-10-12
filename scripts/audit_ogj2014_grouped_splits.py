"""Audit case- and field-grouped splits for OGJ2014 without training a model."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "src" / "notebooks" / "ml_data" / "OGJ2014_extracted_vs_Table1.xlsx"
SHEET = "OGJ2014_Extracted_Rows"
OUTPUT = ROOT / "outputs" / "ml_research" / "ogj2014_grouped_split_audit.json"
ID_COLUMNS = {
    "record_id", "source_report_group_id", "publication_id", "publication_title",
    "publication_id_status", "field_id", "field_name_normalized",
    "field_id_status", "project_id", "case_id", "case_id_status",
    "tagging_confidence", "tagging_rationale", "needs_review",
}


def _valid_group(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip()
    return values.notna() & values.ne("") & ~values.str.casefold().isin(
        {"unknown", "none", "nan", "na", "needs_review"}
    )


def _audit_grouped_splits(
    frame: pd.DataFrame,
    labels: pd.Series,
    groups: pd.Series,
    *,
    group_name: str,
    expected_classes: list[str],
    max_folds: int = 5,
) -> dict:
    """Check train/test group isolation and report class coverage without hiding gaps."""
    labels = labels.reset_index(drop=True).astype(str)
    groups = groups.reset_index(drop=True).astype(str)
    if len(frame) != len(labels) or len(labels) != len(groups):
        raise ValueError(f"{group_name}: labels, groups, and rows are misaligned.")
    if groups.str.strip().eq("").any():
        raise ValueError(f"{group_name}: group values must not be blank.")

    counts = labels.value_counts()
    unique_groups = int(groups.nunique())
    class_group_counts = {
        label: int(groups[labels.eq(label)].nunique()) for label in expected_classes
    }
    classes_present = sorted(labels.unique().tolist())
    classes_missing = sorted(set(expected_classes) - set(classes_present))
    min_class_rows = int(counts.min()) if not counts.empty else 0
    folds = min(max_folds, unique_groups, min_class_rows)

    result = {
        "group_column": group_name,
        "rows_evaluated": int(len(frame)),
        "group_count": unique_groups,
        "class_row_counts": {str(k): int(v) for k, v in counts.sort_index().items()},
        "independent_groups_per_class": class_group_counts,
        "classes_missing_from_subset": classes_missing,
        "folds": 0,
        "split_method": "StratifiedGroupKFold",
        "group_overlap_by_fold": [],
        "class_coverage_by_fold": [],
        "all_expected_classes_present_in_each_train_and_test": False,
        "validation_status": "unavailable",
        "validation_reason": "",
    }

    if len(frame) == 0:
        result["validation_reason"] = f"No rows have a usable {group_name}."
        return result
    if classes_missing:
        result["validation_reason"] = (
            "Some technique classes have no rows with a valid grouping identifier. "
            "No labels were assigned to guessed groups."
        )
        return result
    if folds < 2:
        result["validation_reason"] = (
            "Insufficient row/class/group support for at least two grouped folds. "
            "Do not substitute row-wise splitting."
        )
        return result

    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=42)
    X = pd.DataFrame(index=range(len(frame)))  # diagnostics only; not predictive features
    splits = list(splitter.split(X, labels, groups))
    all_classes = set(expected_classes)
    overlaps = []
    coverage = []
    all_classes_covered = True

    for train_idx, test_idx in splits:
        overlap = sorted(set(groups.iloc[train_idx]).intersection(set(groups.iloc[test_idx])))
        overlaps.append(overlap)
        if overlap:
            raise AssertionError(f"{group_name} leakage across train/test: {overlap}")
        if len(test_idx) == 0:
            raise ValueError(f"{group_name}: a validation fold is empty.")

        train_classes = set(labels.iloc[train_idx].unique())
        test_classes = set(labels.iloc[test_idx].unique())
        missing_train = sorted(all_classes - train_classes)
        missing_test = sorted(all_classes - test_classes)
        all_classes_covered &= not missing_train and not missing_test
        coverage.append({
            "train_rows": int(len(train_idx)),
            "test_rows": int(len(test_idx)),
            "classes_missing_from_train": missing_train,
            "classes_missing_from_test": missing_test,
        })

    result["folds"] = folds
    result["group_overlap_by_fold"] = overlaps
    result["class_coverage_by_fold"] = coverage
    result["all_expected_classes_present_in_each_train_and_test"] = bool(all_classes_covered)
    result["validation_status"] = (
        "split_integrity_passed" if all_classes_covered
        else "split_integrity_passed_support_limited"
    )
    result["validation_reason"] = (
        "Groups are isolated across folds. Class coverage is complete in every train/test fold."
        if all_classes_covered else
        "Groups are isolated, but at least one train/test fold lacks one or more technique classes. "
        "This is a split-integrity audit only, not evidence that model evaluation is statistically adequate."
    )
    return result


def audit(path: Path = DATASET) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Canonical provenance workbook not found: {path}")
    df = pd.read_excel(path, sheet_name=SHEET, engine="openpyxl")
    required = {"technique", "case_id", "field_id", "record_id"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Provenance workbook missing required columns: {missing}")
    if df.empty:
        raise ValueError("The OGJ2014 extracted table is empty.")
    if df["record_id"].isna().any() or df["record_id"].astype(str).str.strip().eq("").any():
        raise ValueError("record_id must be present on every source row.")
    if df["record_id"].duplicated().any():
        raise ValueError("record_id must be unique per source row.")

    labels = df["technique"].astype(str).str.strip()
    if labels.eq("").any():
        raise ValueError("Technique labels must be non-empty; do not infer or rewrite labels.")
    expected_classes = sorted(labels.unique().tolist())

    valid_case = _valid_group(df["case_id"])
    if not valid_case.all():
        raise ValueError("case_id is incomplete; refusing row-wise fallback.")
    case_groups = df["case_id"].astype(str)
    case_audit = _audit_grouped_splits(
        df, labels, case_groups, group_name="case_id", expected_classes=expected_classes
    )

    valid_field = _valid_group(df["field_id"])
    field_df = df.loc[valid_field].copy().reset_index(drop=True)
    field_labels = field_df["technique"].astype(str).str.strip()
    field_groups = field_df["field_id"].astype(str)
    field_audit = _audit_grouped_splits(
        field_df,
        field_labels,
        field_groups,
        group_name="field_id",
        expected_classes=expected_classes,
    )

    result = {
        "dataset": str(path.relative_to(ROOT)),
        "sheet": SHEET,
        "row_count": int(len(df)),
        "technique_class_count": int(labels.nunique()),
        "technique_counts": {str(k): int(v) for k, v in labels.value_counts().sort_index().items()},
        "record_id_unique": bool(df["record_id"].is_unique),
        "case_id_group_count": int(case_groups.nunique()),
        "case_id_rows_per_group": {
            "min": int(case_groups.value_counts().min()),
            "median": float(case_groups.value_counts().median()),
            "max": int(case_groups.value_counts().max()),
        },
        "field_id_nonblank_rows": int(valid_field.sum()),
        "field_id_distinct_groups": int(df.loc[valid_field, "field_id"].nunique()),
        "field_id_missing_rows": int((~valid_field).sum()),
        "provenance_columns_excluded_from_features": sorted(c for c in ID_COLUMNS if c in df.columns),
        "case_level_validation": case_audit,
        "field_level_validation": {
            **field_audit,
            "rows_excluded_missing_field_id": int((~valid_field).sum()),
        },
        # Backwards-compatible top-level fields refer explicitly to case-level grouping.
        "validation_status": case_audit["validation_status"],
        "validation_reason": case_audit["validation_reason"],
        "folds": case_audit["folds"],
        "split_method": case_audit["split_method"],
        "group_overlap_by_fold": case_audit["group_overlap_by_fold"],
        "model_performance_computed": False,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
