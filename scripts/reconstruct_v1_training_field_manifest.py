"""Reconstruct field identity membership for the historical CatBoost v1 training rows.

This is a provenance audit, not a model-training step. It joins the replayed
historical training-row manifest to the source workbook's source-reviewed field
identity columns. It deliberately fails closed when IDs are missing, duplicated,
or when training rows cannot be linked back to the source workbook.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK = ROOT / "src/notebooks/ml_data/OGJ2014_extracted_vs_Table1.xlsx"
DEFAULT_TRAINING_MANIFEST = ROOT / "data/provenance/catboost_v1.0.0_training_manifest.csv"
DEFAULT_OUTPUT = ROOT / "data/provenance/catboost_v1.0.0_training_field_manifest.csv"
DEFAULT_REPORT = ROOT / "data/provenance/catboost_v1.0.0_training_field_manifest_report.json"
SHEET = "OGJ2014_Extracted_Rows"
REQUIRED_WORKBOOK_COLUMNS = {
    "record_id", "field_id", "field_id_status", "field_name_normalized", "technique"
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    return _text(value).casefold() in {"true", "1", "yes", "y"}


def _read_source_rows(workbook_path: Path) -> pd.DataFrame:
    if not workbook_path.is_file():
        raise FileNotFoundError(workbook_path)
    book = load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        if SHEET not in book.sheetnames:
            raise ValueError(f"Source workbook is missing sheet {SHEET!r}.")
        ws = book[SHEET]
        iterator = ws.iter_rows(values_only=True)
        header_values = next(iterator, None)
        if not header_values:
            raise ValueError("Source workbook source sheet is empty.")
        headers = [_text(item) for item in header_values]
        if len(set(headers)) != len(headers):
            raise ValueError("Source workbook has duplicate column names.")
        missing = sorted(REQUIRED_WORKBOOK_COLUMNS.difference(headers))
        if missing:
            raise ValueError(
                "Source workbook lacks field-provenance columns required for a "
                f"v1 overlap audit: {missing}. Run the source-provenance build first."
            )
        positions = {name: headers.index(name) for name in REQUIRED_WORKBOOK_COLUMNS}
        wanted = [
            "record_id", "field_id", "field_id_status",
            "field_name_normalized", "technique",
        ]
        rows = []
        for excel_row, values in enumerate(iterator, start=2):
            rows.append({
                "source_excel_row_actual": excel_row,
                **{name: _text(values[positions[name]]) for name in wanted},
            })
    finally:
        book.close()
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("Source workbook has no data rows.")
    if frame["record_id"].eq("").any():
        raise ValueError("Source workbook contains blank record_id values.")
    duplicates = sorted(frame.loc[frame["record_id"].duplicated(keep=False), "record_id"].unique())
    if duplicates:
        raise ValueError(f"Source workbook contains duplicate record IDs: {duplicates[:10]}")
    return frame


def reconstruct_manifest(
    workbook_path: Path = DEFAULT_WORKBOOK,
    training_manifest_path: Path = DEFAULT_TRAINING_MANIFEST,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return per-training-row field identity and an auditable summary report."""
    if not training_manifest_path.is_file():
        raise FileNotFoundError(training_manifest_path)
    membership = pd.read_csv(training_manifest_path, dtype=str, keep_default_na=False)
    required_manifest = {
        "record_id", "source_excel_row", "source_row_sha256",
        "original_technique_label", "retained_by_historical_cleaner",
    }
    missing = sorted(required_manifest.difference(membership.columns))
    if missing:
        raise ValueError(f"Historical training manifest misses columns: {missing}")
    if membership["record_id"].eq("").any():
        raise ValueError("Historical training manifest contains blank record IDs.")
    if membership["record_id"].duplicated().any():
        raise ValueError("Historical training manifest contains duplicate record IDs.")
    retained = membership[membership["retained_by_historical_cleaner"].map(_truthy)].copy()
    if retained.empty:
        raise ValueError("Historical training manifest has no retained training rows.")

    source = _read_source_rows(workbook_path)
    joined = retained.merge(
        source,
        on="record_id",
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    unmatched = joined.loc[joined["_merge"] != "both", "record_id"].tolist()
    if unmatched:
        raise ValueError(
            f"{len(unmatched)} historical training IDs could not be found in the current "
            f"source workbook; examples: {unmatched[:10]}"
        )
    # Verify row identity and label have not silently shifted relative to the historical manifest.
    joined["manifest_source_excel_row"] = joined["source_excel_row"].astype(str)
    joined["workbook_row_matches_manifest"] = (
        joined["manifest_source_excel_row"] == joined["source_excel_row_actual"].astype(str)
    )
    row_mismatch = int((~joined["workbook_row_matches_manifest"]).sum())
    if row_mismatch:
        raise ValueError(
            f"{row_mismatch} training IDs map to a different physical workbook row than the historical manifest."
        )
    joined["field_id_status"] = joined["field_id_status"].fillna("").astype(str).str.strip()
    joined["field_identity_confirmed"] = (
        joined["field_id"].fillna("").astype(str).str.strip().ne("")
        & joined["field_id_status"].str.casefold().eq("confirmed")
    )
    joined["field_id"] = joined["field_id"].fillna("").astype(str).str.strip()
    joined["field_name_normalized"] = joined["field_name_normalized"].fillna("").astype(str).str.strip()
    columns = [
        "record_id", "source_excel_row", "original_technique_label", "field_id",
        "field_name_normalized", "field_id_status", "field_identity_confirmed",
        "source_row_sha256", "workbook_row_matches_manifest",
    ]
    output = joined[columns].sort_values(["field_id", "record_id"]).reset_index(drop=True)
    confirmed = output[output["field_identity_confirmed"]]
    report = {
        "source_workbook": str(workbook_path),
        "historical_membership_manifest": str(training_manifest_path),
        "source_sheet": SHEET,
        "retained_historical_training_rows": int(len(output)),
        "matched_to_source_workbook_rows": int(len(output)),
        "source_row_identity_mismatches": row_mismatch,
        "confirmed_field_identity_training_rows": int(len(confirmed)),
        "unconfirmed_field_identity_training_rows": int(len(output) - len(confirmed)),
        "confirmed_independent_training_fields": int(confirmed["field_id"].nunique()),
        "field_identity_status_counts": {
            str(key or "<blank>"): int(value)
            for key, value in output["field_id_status"].value_counts(dropna=False).items()
        },
        "unconfirmed_record_ids": output.loc[~output["field_identity_confirmed"], "record_id"].tolist(),
        "holdout_overlap_check_ready": bool(output["field_identity_confirmed"].all()),
        "warning": (
            "A holdout is not genuinely unseen until every production training row has a source-confirmed field ID "
            "and the candidate holdout field IDs are absent from this manifest."
        ),
    }
    return output, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--training-manifest", type=Path, default=DEFAULT_TRAINING_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    manifest, report = reconstruct_manifest(args.workbook, args.training_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(args.output, index=False)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "report": str(args.report), **report}, indent=2))


if __name__ == "__main__":
    main()
