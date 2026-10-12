"""Audit the OGJ2014 provenance groups before any ML benchmark.

This is a data/split diagnostic only. IDs are never features, and this script
does not train a model or claim predictive performance.
"""
from __future__ import annotations

import json
from pathlib import Path

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

    # Exact case groups are available for all rows in the current enriched workbook.
    if not _valid_group(df["case_id"]).all():
        raise ValueError("case_id is incomplete; refusing row-wise fallback.")
    groups = df["case_id"].astype(str).to_numpy()
    y = df["technique"].astype(str).str.strip()
    class_counts = y.value_counts().sort_values()
    group_count = int(pd.Series(groups).nunique())
    min_class_count = int(class_counts.min())
    folds = min(5, group_count, min_class_count)

    result = {
        "dataset": str(path.relative_to(ROOT)),
        "sheet": SHEET,
        "row_count": int(len(df)),
        "technique_class_count": int(y.nunique()),
        "technique_counts": {str(k): int(v) for k, v in y.value_counts().sort_index().items()},
        "record_id_unique": bool(df["record_id"].is_unique),
        "case_id_group_count": group_count,
        "case_id_rows_per_group": {
            "min": int(pd.Series(groups).value_counts().min()),
            "median": float(pd.Series(groups).value_counts().median()),
            "max": int(pd.Series(groups).value_counts().max()),
        },
        "field_id_nonblank_rows": int(_valid_group(df["field_id"]).sum()),
        "field_id_distinct_groups": int(df.loc[_valid_group(df["field_id"]), "field_id"].nunique()),
        "field_id_missing_rows": int((~_valid_group(df["field_id"])).sum()),
        "provenance_columns_excluded_from_features": sorted(c for c in ID_COLUMNS if c in df.columns),
        "validation_status": "unavailable",
        "validation_reason": "",
        "folds": 0,
        "split_method": "StratifiedGroupKFold",
        "group_overlap_by_fold": [],
    }

    if folds < 2:
        result["validation_reason"] = (
            "Not enough examples in every technique class to construct at least "
            "two stratified group folds. Do not substitute row-wise splitting."
        )
    else:
        splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=42)
        X = pd.DataFrame(index=df.index)  # split diagnostics only; no model features
        splits = list(splitter.split(X, y, groups))
        overlaps = []
        for train_idx, test_idx in splits:
            overlap = sorted(set(groups[train_idx]).intersection(groups[test_idx]))
            overlaps.append(overlap)
            if overlap:
                raise AssertionError(f"case_id leakage across train/test: {overlap}")
            if y.iloc[train_idx].nunique() < 2:
                raise ValueError("A training fold contains fewer than two target classes.")
            if len(test_idx) == 0:
                raise ValueError("A validation fold is empty.")
        result["validation_status"] = "split_integrity_passed"
        result["validation_reason"] = (
            "Case groups are isolated across folds. This verifies split integrity, "
            "not model performance or suitability of the extracted labels."
        )
        result["folds"] = folds
        result["group_overlap_by_fold"] = overlaps

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
