from pathlib import Path

import pandas as pd

from data.challenges import _find_column, _norm


def test_challenge_aliases_resolve_source_schema():
    columns = ["Field", "Field Area", "Challenges", "Lessons"]
    assert _find_column(columns, {"field"}) == "Field"
    assert _find_column(columns, {"field area", "area"}) == "Field Area"
    assert _find_column(columns, {"challenge", "challenges"}) == "Challenges"
    assert _find_column(columns, {"lesson", "lessons"}) == "Lessons"


def test_normalize_columns_is_stable():
    assert _norm("Field_Area") == "field area"
    assert _norm("Lessons Learnt") == "lessons learnt"
