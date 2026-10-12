import numpy as np
import pandas as pd
import pytest

from ml.grouped_validation import (
    assert_no_provenance_features,
    choose_group_column,
    grouped_stratified_splits,
)


def test_field_id_has_priority_over_case_and_legacy_field():
    df = pd.DataFrame({
        "case_id": ["case-a", "case-b", "case-c", "case-d"],
        "field_id": ["field-a", "field-a", "field-b", "field-b"],
        "Field": ["old-a", "old-a", "old-b", "old-b"],
    })
    assert choose_group_column(df) == "field_id"


def test_incomplete_field_ids_do_not_silently_fall_back_to_case_ids():
    df = pd.DataFrame({
        "field_id": ["field-a", ""],
        "case_id": ["case-a", "case-b"],
    })
    with pytest.raises(ValueError, match="Field-level validation is blocked"):
        choose_group_column(df)


def test_group_selection_rejects_incomplete_ids_instead_of_row_split():
    df = pd.DataFrame({"case_id": ["case-a", "", "case-b"]})
    with pytest.raises(ValueError, match="Leakage-safe evaluation requires"):
        choose_group_column(df)


def test_grouped_splits_never_split_a_group_across_train_and_test():
    X = pd.DataFrame({"porosity": np.arange(24, dtype=float)})
    y = np.array([0, 1] * 12)
    groups = np.repeat([f"case-{i}" for i in range(12)], 2)
    splits, n_folds = grouped_stratified_splits(X, y, groups, folds=4)
    assert n_folds == 4
    for train_idx, test_idx in splits:
        assert set(groups[train_idx]).isdisjoint(set(groups[test_idx]))


def test_provenance_columns_cannot_be_model_features():
    with pytest.raises(ValueError, match="cannot be model features"):
        assert_no_provenance_features(pd.DataFrame({
            "porosity": [15.0],
            "case_id": ["CASE-123"],
        }))


def test_model_feature_columns_pass_provenance_guard():
    assert_no_provenance_features(pd.DataFrame({
        "porosity_pct": [15.0],
        "permeability_md": [100.0],
    }))
