"""Synthetic acceptance tests for the Baronia workbook input contract."""

from io import BytesIO

import pandas as pd
import pytest

from data.baronia_wag_evidence import load_baronia_wag


def test_loader_rejects_missing_required_sheets_before_normalization():
    workbook = BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame({"Metric": ["Synthetic"], "Value": [1]}).to_excel(
            writer, sheet_name="Summary", index=False
        )

    with pytest.raises(ValueError, match="missing sheets"):
        load_baronia_wag(
            workbook_bytes=workbook.getvalue(),
            workbook_name="synthetic-incomplete.xlsx",
        )
