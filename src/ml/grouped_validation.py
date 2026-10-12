"""Leakage-safe group selection and split construction for EOR research.

Provenance columns are identifiers for grouping/auditing only. They are never
features. If reliable group-aware validation cannot be constructed, fail closed
rather than silently falling back to row-wise random splitting.
"""
from __future__ import annotations

from typing import Iterator

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

PROVENANCE_COLUMNS = {
    "record_id",
    "source_report_group_id",
    "publication_id",
    "publication_title",
    "publication_id_status",
    "field_id",
    "field_name_normalized",
    "field_id_status",
    "project_id",
    "case_id",
    "case_id_status",
    "tagging_confidence",
    "tagging_rationale",
    "needs_review",
}

GROUP_PRIORITY = ("case_id", "field_id", "source_report_group_id", "publication_id", "Field")


def choose_group_column(df: pd.DataFrame) -> str:
    """Pick the most specific available grouping key, ignoring blank/unknown IDs."""
    for column in GROUP_PRIORITY:
        if column not in df.columns:
            continue
        values = df[column].astype("string").str.strip()
        valid = values.notna() & values.ne("") & ~values.str.casefold().isin(
            {"unknown", "none", "nan", "na", "needs_review"}
        )
        if valid.all() and values.nunique(dropna=True) >= 2:
            return column
    raise ValueError(
        "Leakage-safe evaluation requires a complete, non-empty grouping column "
        f"with at least two groups. Tried: {', '.join(GROUP_PRIORITY)}. "
        "Do not fall back to row-wise splitting."
    )


def assert_no_provenance_features(features: pd.DataFrame) -> None:
    """Reject any identifier/audit metadata accidentally passed as model input."""
    forbidden = sorted(
        column for column in features.columns
        if column in PROVENANCE_COLUMNS
        or column.casefold().endswith("_id")
        or column.casefold() in {"raw_line", "source_report", "publication_title",
                                 "field_name_normalized", "tagging_rationale",
                                 "tagging_confidence", "needs_review"}
    )
    if forbidden:
        raise ValueError(f"Provenance/leakage columns cannot be model features: {forbidden}")


def grouped_stratified_splits(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    folds: int = 5,
    random_state: int = 56,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], int]:
    """Build stratified group folds and verify group isolation and class support."""
    y = np.asarray(y)
    groups = np.asarray(groups, dtype=str)
    if len(X) != len(y) or len(y) != len(groups):
        raise ValueError("X, y, and groups must have identical row counts.")
    if pd.isna(groups).any() or any(not value.strip() for value in groups):
        raise ValueError("Group values must be complete and non-empty.")
    unique_groups = np.unique(groups)
    if len(unique_groups) < 2:
        raise ValueError("At least two distinct groups are required for validation.")

    class_counts = np.unique(y, return_counts=True)[1]
    min_class = int(class_counts.min()) if len(class_counts) else 0
    class_group_counts = {
        str(label): int(np.unique(groups[y == label]).size)
        for label in np.unique(y)
    }
    min_groups_per_class = min(class_group_counts.values(), default=0)
    actual_folds = min(
        int(folds), len(unique_groups), min_class, min_groups_per_class
    )
    if actual_folds < 2:
        sparse = {
            label: count for label, count in class_group_counts.items() if count < 2
        }
        if sparse:
            details = ", ".join(
                f"{label}: {count} independent group(s)"
                for label, count in sorted(sparse.items())
            )
            raise ValueError(
                "Group-isolated multiclass CV is unavailable because at least one "
                "technique occurs in fewer than two independent groups. "
                f"Unsupported class groups: {details}. Do not split a group or "
                "silently remove a technique label."
            )
        raise ValueError(
            "Insufficient class support or distinct groups for stratified group CV; "
            "collect more labelled groups or report evaluation as unavailable."
        )

    splitter = StratifiedGroupKFold(
        n_splits=actual_folds, shuffle=True, random_state=random_state
    )
    splits = list(splitter.split(X, y, groups))
    for train_idx, test_idx in splits:
        overlap = set(groups[train_idx]).intersection(groups[test_idx])
        if overlap:
            raise AssertionError(f"Group leakage detected across train/test: {sorted(overlap)}")
        if len(np.unique(y[train_idx])) < 2:
            raise ValueError("A training fold contains fewer than two target classes.")
        if len(test_idx) == 0:
            raise ValueError("A validation fold is empty.")
    return splits, actual_folds
