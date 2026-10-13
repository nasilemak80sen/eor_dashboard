from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.train_hybrid_catboost import (
    _validate_columns,
    validate_independent_group_support,
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
