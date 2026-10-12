"""Regression tests for the evidence-preserving OGJ2014 data-quality audit."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_ogj2014_data_quality as quality  # noqa: E402


def test_quality_audit_flags_unresolved_rows_aliases_ranges_and_labels(tmp_path, monkeypatch):
    frame = pd.DataFrame({
        "record_id": ["R1", "R2", "R3", "R4"],
        "technique": ["Steam", "Steam", "Unreviewed technique", "Polymer"],
        "field_id": ["FIELD-A", "FIELD-B", "", "FIELD-C"],
        "field_name_normalized": ["L’Enfer", "L'Enfer", "", "Goldsmith-Landreth"],
        "field_id_status": ["provisional", "provisional", "needs_review", "provisional"],
        "tagging_rationale": ["source phrase", "source phrase", "unresolved", "source phrase"],
        "raw_line": ["L’Enfer S 1998", "L'Enfer S 1999", "ambiguous zone code", "Goldsmith-Landreth Steam TX 1997"],
        "formation_category": ["Sandstone"] * 4,
        "depth_min_ft": [100, 100, 100, 100],
        "depth_max_ft": [200, 200, 200, 200],
        "porosity_min_pct": [10, 10, 110, 10],
        "porosity_max_pct": [20, 20, 120, 20],
        "perm_min_md": [1, 1, 1, 1],
        "perm_max_md": [10, 10, 10, 10],
        "api_min": [20, 20, 20, 20],
        "api_max": [30, 30, 30, 30],
        "visc_min_cp": [1, 1, 1, 1],
        "visc_max_cp": [2, 2, 2, 2],
        "so_start_min_pct": [None, 30, 30, 30],
        "so_start_max_pct": [None, 40, 40, 40],
    })
    dataset = tmp_path / "test.xlsx"
    with pd.ExcelWriter(dataset, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=quality.SHEET, index=False)
    monkeypatch.setattr(quality, "OUT", tmp_path / "audit")

    summary = quality.audit(dataset)

    assert summary["source_rows"] == 4
    assert summary["unresolved_field_rows"] == 1
    assert summary["unresolved_distinct_source_texts"][0]["source_evidence_assessment"]
    assert summary["support_by_technique"][0]["distinct_verified_fields"] == 0
    assert summary["potential_field_alias_or_split_candidates"] >= 1
    assert summary["feature_completeness_and_range_audit"]["oil_saturation"]["both_missing"] == 1
    assert summary["feature_range_issue_rows"] >= 1
    assert summary["unrecognized_or_unreviewed_labels"][0]["raw_label"] == "Unreviewed technique"
    assert summary["potential_label_semantic_conflict_rows"] == 1
    assert summary["potential_label_semantic_conflict_candidates"][0]["structured_technique_label"] == "Polymer"
    remediation = {row["technique"]: row for row in summary["class_support_remediation"]}
    assert remediation["Steam"]["verified_independent_fields"] == 0
    assert remediation["Steam"]["verified_field_gap_to_six"] == 6
    assert remediation["Polymer"]["rows_flagged_for_label_semantic_review"] == 1
    assert remediation["Polymer"]["source_rows_after_label_review"] == 0
    assert (tmp_path / "audit" / "ogj2014_class_support_remediation.csv").is_file()
    assert (tmp_path / "audit" / "ogj2014_unresolved_field_review.csv").is_file()
