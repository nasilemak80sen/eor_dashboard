import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import MultiLabelBinarizer

from eor_ml_research_layer.notebooks.notebook_utils import (
    build_multilabel_table,
    grouped_cv_splits,
    grouped_holdout_indices,
    standardize_training_table,
    validate_grouped_dataset,
)
from eor_ml_research_layer.research_model_service import ResearchModelService


class _MultiLabelModel:
    def predict_proba(self, features):
        return np.array([[0.15, 0.80, 0.45]])


def _record(technique="Polymer", source_group="source-1", **overrides):
    row = {
        "technique": technique,
        "formation_category": "Sandstone",
        "depth_min_ft": 1000,
        "depth_max_ft": 2000,
        "porosity_min_pct": 15,
        "porosity_max_pct": 25,
        "perm_min_md": 10,
        "perm_max_md": 100,
        "api_min": 25,
        "api_max": 35,
        "visc_min_cp": 1,
        "visc_max_cp": 5,
        "so_start_min_pct": 40,
        "so_start_max_pct": 70,
        "source_id": source_group,
    }
    row.update(overrides)
    return row


def test_standardization_removes_exact_duplicates_and_keeps_source_group():
    df = standardize_training_table(
        pd.DataFrame([_record(), _record()])
    )

    assert len(df) == 1
    assert df.attrs["exact_duplicates_removed"] == 1
    assert df.loc[0, "source_group"] == "source-1"


def test_identical_profiles_merge_source_groups_for_leakage_safe_splits():
    df = standardize_training_table(
        pd.DataFrame([
            _record("Polymer", source_group="source-1"),
            _record("Polymer", source_group="source-2"),
        ])
    )

    profiles, label_sets, groups = build_multilabel_table(df)

    assert len(profiles) == 1
    assert label_sets == [("Polymer",)]
    assert groups is not None
    assert len(set(groups)) == 1


def test_identical_profiles_aggregate_all_techniques_and_link_source_groups():
    df = standardize_training_table(
        pd.DataFrame([
            _record("Polymer", source_group="source-1"),
            _record("Steam", source_group="source-2"),
        ])
    )

    profiles, label_sets, groups = build_multilabel_table(df)

    assert len(profiles) == 1
    assert label_sets == [("Polymer", "Steam")]
    assert groups is not None
    assert len(set(groups)) == 1


def test_grouped_validation_requires_source_ids_and_enough_independent_support():
    with pytest.raises(ValueError, match="no source_group identifier"):
        validate_grouped_dataset(np.array([0, 0]), None)

    with pytest.raises(ValueError, match="Sparse classes"):
        validate_grouped_dataset(
            np.array([0, 0, 1, 1]),
            np.array(["a", "b", "a", "b"]),
            minimum_groups_per_class=3,
        )
    with pytest.raises(ValueError, match="both positive and negative profiles"):
        validate_grouped_dataset(
            np.array([[1, 1], [1, 0], [1, 0], [1, 1]]),
            np.array(["a", "b", "c", "d"]),
            classes=["Always present", "Variable"],
            minimum_groups_per_class=1,
        )


def test_group_holdout_and_cv_keep_groups_disjoint():
    labels = np.array([[1, 0, 0]] * 8 + [[0, 1, 1]] * 8)
    groups = np.array([f"class-{label}-source-{i}" for label in [0, 1] for i in range(8)])

    train_idx, test_idx = grouped_holdout_indices(
        labels,
        groups,
        test_size=0.25,
        random_state=13,
        classes=["CO2", "Polymer", "Steam"],
    )
    assert set(groups[train_idx]).isdisjoint(set(groups[test_idx]))
    assert np.all(labels[train_idx].sum(axis=0) > 0)
    assert np.all(labels[test_idx].sum(axis=0) > 0)

    folds = grouped_cv_splits(labels[train_idx], groups[train_idx])
    assert len(folds) >= 2
    for fold_train, fold_validation in folds:
        assert set(groups[train_idx][fold_train]).isdisjoint(
            set(groups[train_idx][fold_validation])
        )
        assert np.all(labels[train_idx][fold_validation].sum(axis=0) > 0)


def test_research_service_ranks_multi_label_probabilities_by_saved_classes():
    mlb = MultiLabelBinarizer(classes=["CO2", "Polymer", "Steam"])
    mlb.fit([["CO2"], ["Polymer"]])
    service = ResearchModelService("unused.joblib")
    service.bundle = {
        "model": _MultiLabelModel(),
        "label_encoder": mlb,
        "feature_names": [],
        "target_type": "multi_label_suitability",
    }

    ranked = service.predict_top3_from_ranges(
        depth_min_ft=1000,
        depth_max_ft=2000,
        porosity_min_pct=15,
        porosity_max_pct=25,
        perm_min_md=10,
        perm_max_md=100,
        api_min=25,
        api_max=35,
        visc_min_cp=1,
        visc_max_cp=5,
        so_min_pct=40,
        so_max_pct=70,
        formation="Sandstone",
    )

    assert ranked == [("Polymer", 0.8), ("Steam", 0.45), ("CO2", 0.15)]
    assert service.model_info()["target_type"] == "multi_label_suitability"
