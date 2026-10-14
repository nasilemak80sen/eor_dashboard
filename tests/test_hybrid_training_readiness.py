from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.train_hybrid_catboost import (
    _validate_columns,
    validate_independent_group_support,
    build_training_matrix,
    validate_nextgen_source_schema,
)


def test_training_rejects_missing_or_unresolved_target_labels():
    frame = pd.DataFrame({
        "technique": ["Steam", "nan"],
        "formation_category": ["Sandstone", "Carbonates"],
    })
    with pytest.raises(ValueError, match="missing or unresolved 'technique'"):
        _validate_columns(frame)


def test_training_quarantines_rows_marked_for_review():
    frame = pd.DataFrame({
        "technique": ["Steam", "Polymer"],
        "formation_category": ["Sandstone", "Carbonates"],
        "needs_review": [False, True],
    })
    with pytest.raises(ValueError, match="marked needs_review"):
        _validate_columns(frame)


def test_training_requires_independent_groups_per_class_not_only_row_counts():
    # Many rows from two fields are still only two independent field examples.
    y = np.array([0] * 12 + [1] * 12)
    groups = np.array(["field-a"] * 6 + ["field-b"] * 6 + ["field-c"] * 6 + ["field-d"] * 6)
    with pytest.raises(ValueError, match="insufficient independent field support"):
        validate_independent_group_support(y, groups, minimum_groups_per_class=3)


def test_training_readiness_accepts_sufficient_independent_field_support():
    y = np.array([0, 0, 0, 1, 1, 1])
    groups = np.array(["field-a", "field-b", "field-c", "field-d", "field-e", "field-f"])
    support = validate_independent_group_support(y, groups, minimum_groups_per_class=3)
    assert support == {"0": 3, "1": 3}



def test_nextgen_training_blocks_v1_range_data_without_measured_core_inputs():
    frame = pd.DataFrame({
        "technique": ["Steam", "Polymer"],
        "formation_category": ["Sandstone", "Carbonates"],
        "depth_min_ft": [4000, 3000],
        "depth_max_ft": [6000, 5000],
        "porosity_min_pct": [15, 12],
        "porosity_max_pct": [25, 24],
        "perm_min_md": [50, 100],
        "perm_max_md": [150, 200],
        "api_min": [28, 30],
        "api_max": [35, 36],
        "visc_min_cp": [2, 5],
        "visc_max_cp": [8, 10],
        "so_start_min_pct": [30, 20],
        "so_start_max_pct": [50, 40],
    })

    with pytest.raises(
        ValueError,
        match="Next-generation training is blocked.*source-backed v2 core input",
    ):
        build_training_matrix(frame)



def test_current_ogj2014_workbook_lacks_required_nextgen_core_measurements():
    project_root = Path(__file__).resolve().parents[1]
    source_path = (
        project_root
        / "src"
        / "notebooks"
        / "ml_data"
        / "OGJ2014_extracted_vs_Table1.xlsx"
    )
    assert source_path.is_file(), f"Expected checked-in source workbook at {source_path}"

    source = pd.read_excel(
        source_path,
        sheet_name="OGJ2014_Extracted_Rows",
        engine="openpyxl",
    )
    with pytest.raises(ValueError, match="Next-generation training is blocked") as exc_info:
        validate_nextgen_source_schema(source)

    message = str(exc_info.value)
    assert "temperature_c" in message
    assert "reservoir_pressure" in message
