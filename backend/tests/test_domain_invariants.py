from __future__ import annotations

import sys
from pathlib import Path

# Use the same src-first import precedence as the production Streamlit entrypoint.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPOSITORY_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ml.hybrid_intelligence import HybridDecisionService


def test_hard_engineering_failure_cannot_win_on_high_ml_probability():
    screening = {
        "results": [
            {
                "EOR Technique": "CO2 Miscible Flood",
                "Status": "FAIL (critical)",
                "Score (%)": 0.0,
                "Cause of Fail/Pass": "MMP not satisfied",
            },
            {
                "EOR Technique": "Polymer (HPAM)",
                "Status": "PASS",
                "Score (%)": 70.0,
                "Cause of Fail/Pass": "Engineering criteria passed",
            },
        ]
    }
    result = HybridDecisionService().fuse(
        screening,
        {"Miscible CO2": 0.99, "Polymer": 0.01},
    )
    failed = next(row for row in result["ranking"] if row["EOR Technique"] == "CO2 Miscible Flood")
    assert failed["Gate Failed"] is True
    assert failed["Hybrid Score Raw"] == 0.0
    assert result["recommendation"]["EOR Technique"] == "Polymer (HPAM)"


def test_hybrid_rejects_invalid_probability_at_api_domain_boundary():
    import pytest

    with pytest.raises(ValueError, match="within \\[0, 1\\]"):
        HybridDecisionService().fuse(
            {"results": [{"EOR Technique": "CO2 Miscible Flood", "Status": "PASS", "Score (%)": 90}]},
            {"Miscible CO2": 1.01},
        )
