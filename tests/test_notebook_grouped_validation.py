"""Regression tests for provenance-aware, group-safe notebook preprocessing."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = REPO_ROOT / "eor_ml_research_layer" / "notebooks"
sys.path.insert(0, str(NOTEBOOK_DIR))

import notebook_utils as nu  # noqa: E402


def _raw_table() -> pd.DataFrame:
    return pd.DataFrame({
        "technique": ["Steam", "Polymer"],
        "formation_category": ["Sandstone", "Carbonates"],
        "depth_min_ft": [1000, 2000],
        "depth_max_ft": [1200, 2300],
        "porosity_min_pct": [10, 15],
        "porosity_max_pct": [20, 25],
        "perm_min_md": [50, 100],
        "perm_max_md": [100, 200],
        "api_min": [20, 30],
        "api_max": [25, 35],
        "visc_min_cp": [5, 10],
        "visc_max_cp": [8, 15],
        "so_start_min_pct": [30, 40],
        "so_start_max_pct": [35, 45],
        "case_id": ["CASE-001", "CASE-002"],
        "field_id": ["FIELD-001", "FIELD-002"],
        "project_id": ["", ""],
        "source_report_group_id": ["", ""],
    })


def test_field_id_is_used_for_grouping_before_case_and_empty_metadata():
    standardized = nu.standardize_training_table(_raw_table())
    assert standardized["source_group"].tolist() == ["FIELD-001", "FIELD-002"]


def test_incomplete_field_id_is_not_filled_from_case_id():
    raw = _raw_table()
    raw["field_id"] = ["FIELD-001", ""]
    standardized = nu.standardize_training_table(raw)
    assert standardized["source_group"].isna().any()
    with pytest.raises(ValueError, match="unresolved field IDs"):
        nu.validate_grouped_dataset(
            labels=[0, 1],
            groups=standardized["source_group"],
            minimum_groups_per_class=1,
        )


def test_rows_with_identical_numeric_profiles_are_not_merged():
    raw = _raw_table()
    duplicate = raw.iloc[[0]].copy()
    duplicate["technique"] = "Polymer"
    duplicate["field_id"] = "FIELD-003"
    raw = pd.concat([raw, duplicate], ignore_index=True)
    standardized = nu.standardize_training_table(raw)
    assert len(standardized) == len(raw)
    assert standardized.attrs["rows_merged_by_numeric_profile"] == 0


def test_provenance_identifiers_do_not_enter_feature_matrix():
    standardized = nu.standardize_training_table(_raw_table())
    features, _, feature_names = nu.build_feature_table(standardized)

    assert "case_id" not in feature_names
    assert "source_group" not in feature_names
    nu.assert_no_provenance_features(features)


def test_missing_group_ids_are_rejected_for_grouped_evaluation():
    with pytest.raises(ValueError, match="blank or unresolved field IDs"):
        nu.validate_grouped_dataset(
            labels=[0, 1, 0, 1],
            groups=["CASE-001", "", "CASE-002", "CASE-003"],
            minimum_groups_per_class=1,
        )
