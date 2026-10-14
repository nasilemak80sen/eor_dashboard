from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from scripts.prepare_v2_field_holdout import prepare_field_holdout
from scripts.reconstruct_v1_training_field_manifest import reconstruct_manifest


CORE = {
    "depth_ft": 5000.0,
    "temperature_c": 90.0,
    "reservoir_pressure": 2500.0,
    "porosity_pct": 20.0,
    "perm_md": 100.0,
    "api": 35.0,
    "visc_cp": 2.0,
    "so_pct": 55.0,
}


def _write_v1_source_files(tmp_path: Path, *, field_status: str = "confirmed"):
    workbook_path = tmp_path / "source.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "OGJ2014_Extracted_Rows"
    ws.append([
        "technique", "record_id", "field_id", "field_id_status",
        "field_name_normalized",
    ])
    ws.append(["Hot water", "REC-A", "FIELD-A", field_status, "field a"])
    ws.append(["Hot water", "REC-B", "FIELD-B", "confirmed", "field b"])
    wb.save(workbook_path)

    manifest_path = tmp_path / "membership.csv"
    pd.DataFrame([
        {
            "record_id": "REC-A",
            "source_excel_row": 2,
            "source_row_sha256": "sha-a",
            "original_technique_label": "Hot water",
            "retained_by_historical_cleaner": "True",
        },
        {
            "record_id": "REC-B",
            "source_excel_row": 3,
            "source_row_sha256": "sha-b",
            "original_technique_label": "Hot water",
            "retained_by_historical_cleaner": "True",
        },
    ]).to_csv(manifest_path, index=False)
    return workbook_path, manifest_path


def _write_candidate_dataset(path: Path, field_ids: list[str]):
    rows = []
    for index, field_id in enumerate(field_ids):
        rows.append({
            "record_id": f"V2-{index}",
            "field_id": field_id,
            "field_id_status": "confirmed",
            "source_review_status": "confirmed",
            "source_url": f"https://example.org/paper-{index}",
            "source_record_id": f"Table-{index}-row-{index}",
            "technique": "Hot water",
            "formation_category": "Sandstone",
            "needs_review": False,
            **CORE,
        })
    pd.DataFrame(rows).to_csv(path, index=False)


def test_reconstruct_v1_field_manifest_joins_training_ids_to_confirmed_fields(tmp_path):
    workbook_path, membership_path = _write_v1_source_files(tmp_path)
    manifest, report = reconstruct_manifest(workbook_path, membership_path)

    assert len(manifest) == 2
    assert set(manifest["field_id"]) == {"FIELD-A", "FIELD-B"}
    assert manifest["field_identity_confirmed"].all()
    assert report["confirmed_independent_training_fields"] == 2
    assert report["holdout_overlap_check_ready"] is True


def test_reconstruct_v1_field_manifest_keeps_unresolved_identity_visible(tmp_path):
    workbook_path, membership_path = _write_v1_source_files(tmp_path, field_status="provisional")
    manifest, report = reconstruct_manifest(workbook_path, membership_path)

    assert not manifest.loc[manifest["record_id"] == "REC-A", "field_identity_confirmed"].iloc[0]
    assert report["unconfirmed_field_identity_training_rows"] == 1
    assert report["holdout_overlap_check_ready"] is False


def test_holdout_reserves_whole_unseen_fields_and_preserves_train_support(tmp_path):
    workbook_path, membership_path = _write_v1_source_files(tmp_path)
    v1_manifest, _ = reconstruct_manifest(workbook_path, membership_path)
    v1_fields_path = tmp_path / "v1-field-manifest.csv"
    v1_manifest.to_csv(v1_fields_path, index=False)

    dataset_path = tmp_path / "v2.csv"
    _write_candidate_dataset(dataset_path, ["FIELD-A", "FIELD-B", "FIELD-C", "FIELD-D"])

    assignments, report = prepare_field_holdout(
        dataset_path,
        v1_fields_path,
        holdout_fields_per_class=2,
        minimum_train_fields_per_class=2,
        required_classes=("Hot water",),
    )

    holdout = set(assignments.loc[assignments["split"] == "holdout", "field_id"])
    train = set(assignments.loc[assignments["split"] == "train", "field_id"])
    assert holdout == {"FIELD-C", "FIELD-D"}
    assert train == {"FIELD-A", "FIELD-B"}
    assert not holdout.intersection({"FIELD-A", "FIELD-B"})
    assert not train.intersection(holdout)
    assert report["holdout_v1_field_overlap"] == []
    assert report["train_independent_field_support"]["Hot water"] == 2
    assert report["holdout_independent_field_support"]["Hot water"] == 2
    assert report["v2_holdout_gate_passed"] is True


def test_holdout_refuses_to_call_v1_used_fields_unseen(tmp_path):
    _, membership_path = _write_v1_source_files(tmp_path)
    v1_manifest_path = tmp_path / "v1-field-manifest.csv"
    pd.DataFrame([
        {"field_id": "FIELD-A", "field_id_status": "confirmed", "field_identity_confirmed": True},
        {"field_id": "FIELD-B", "field_id_status": "confirmed", "field_identity_confirmed": True},
    ]).to_csv(v1_manifest_path, index=False)

    dataset_path = tmp_path / "v2.csv"
    _write_candidate_dataset(dataset_path, ["FIELD-A", "FIELD-B", "FIELD-C"])

    with pytest.raises(ValueError, match="genuinely-unseen holdout"):
        prepare_field_holdout(
            dataset_path,
            v1_manifest_path,
            holdout_fields_per_class=2,
            minimum_train_fields_per_class=1,
            required_classes=("Hot water",),
        )


def test_holdout_rejects_incomplete_core_features_instead_of_imputing(tmp_path):
    v1_manifest_path = tmp_path / "v1-field-manifest.csv"
    pd.DataFrame([
        {"field_id": "KNOWN", "field_id_status": "confirmed", "field_identity_confirmed": True}
    ]).to_csv(v1_manifest_path, index=False)
    dataset_path = tmp_path / "v2.csv"
    _write_candidate_dataset(dataset_path, ["FIELD-A", "FIELD-B", "FIELD-C"])
    frame = pd.read_csv(dataset_path)
    frame.loc[0, "reservoir_pressure"] = float("nan")
    frame.to_csv(dataset_path, index=False)

    with pytest.raises(ValueError, match="No training rows passed source and feature gates"):
        prepare_field_holdout(
            dataset_path,
            v1_manifest_path,
            holdout_fields_per_class=1,
            minimum_train_fields_per_class=1,
            required_classes=("Hot water",),
        )
