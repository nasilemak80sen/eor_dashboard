"""Tests for the source-row-preserving OGJ2014 benchmark utilities."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark_ogj2014_field_generalization as benchmark  # noqa: E402


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "depth_min_ft": [1000, 1000, 2000, 2000],
        "depth_max_ft": [1200, 1200, 2400, 2400],
        "porosity_min_pct": [10, 10, 15, 15],
        "porosity_max_pct": [20, 20, 25, 25],
        "perm_min_md": [50, 50, 100, 100],
        "perm_max_md": [100, 100, 200, 200],
        "api_min": [20, 20, 30, 30],
        "api_max": [25, 25, 35, 35],
        "visc_min_cp": [5, 5, 10, 10],
        "visc_max_cp": [8, 8, 15, 15],
        "so_start_min_pct": [30, 30, 40, 40],
        "so_start_max_pct": [35, 35, 45, 45],
        "formation_category": ["Sandstone", "Sandstone", "Carbonates", "Carbonates"],
        "record_id": ["REC-1", "REC-2", "REC-3", "REC-4"],
        "field_id": ["FIELD-A", "FIELD-B", "FIELD-C", "FIELD-D"],
        "case_id": ["CASE-1", "CASE-2", "CASE-3", "CASE-4"],
        "technique": ["Steam", "Polymer", "Miscible CO2", "Miscible HC"],
    })


def test_features_exclude_ids_and_preserve_duplicate_numeric_profiles():
    frame = _sample_frame()
    features = benchmark.build_features(frame)

    assert len(features) == len(frame)
    assert features.iloc[0].equals(features.iloc[1])
    assert not any(name.endswith("_id") for name in features.columns)
    assert not any("record" in name.casefold() or "case" in name.casefold() for name in features.columns)


def test_field_holdout_and_cv_keep_fields_disjoint():
    labels = np.array(["Steam", "Polymer"] * 12)
    groups = np.repeat([f"FIELD-{i:02d}" for i in range(12)], 2)

    train, test, _ = benchmark.make_group_holdout(labels, groups)
    assert set(groups[train]).isdisjoint(set(groups[test]))
    train_support = benchmark._class_group_counts(labels, groups, train)
    test_support = benchmark._class_group_counts(labels, groups, test)
    assert min(train_support.values()) >= benchmark.MINIMUM_TRAIN_FIELDS_PER_CLASS
    assert min(test_support.values()) >= benchmark.MINIMUM_HOLDOUT_FIELDS_PER_CLASS

    splits, folds, _ = benchmark.make_group_cv(labels[train], groups[train], requested_folds=3)
    assert folds >= 2
    for train_idx, test_idx in splits:
        assert set(groups[train][train_idx]).isdisjoint(set(groups[train][test_idx]))



def test_label_semantic_conflicts_are_flagged_without_auto_relabel():
    frame = pd.DataFrame({
        "record_id": ["REC-1", "REC-2", "REC-3", "REC-4", "REC-5"],
        "technique": ["Polymer", "Polymer", "Steam", "Polymer", "Polymer"],
        "raw_line": [
            "Brazil Petrobras Steam Estreito 12/09",
            "Bahia Petrobras CO2 miscible Miranga 12/09",
            "Steam field example",
            "Brazil Petrobras Microbial Carmopolis 6/02",
            "miscible Magnus 10/02",
        ],
    })
    mask, details = benchmark.label_semantic_conflict_audit(frame)

    assert mask.tolist() == [True, True, False, True, True]
    assert [item["potentially_conflicting_mentions"] for item in details] == [
        ["Steam"], ["CO2 miscible"], ["Microbial"], ["Miscible (unspecified subtype)"]
    ]
    assert frame["technique"].tolist() == ["Polymer", "Polymer", "Steam", "Polymer", "Polymer"]
