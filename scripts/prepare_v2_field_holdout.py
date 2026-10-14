"""Prepare a genuinely unseen field-level holdout for EOR Atlas v2.

The script refuses to create split files unless every eligible row is source-reviewed,
all core v2 inputs are measured and physically plausible, field IDs are confirmed,
and candidate holdout fields are absent from the reconstructed v1 training-field manifest.
It reserves entire canonical fields, never individual rows from a held-out field.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V1_FIELDS = ROOT / "data/provenance/catboost_v1.0.0_training_field_manifest.csv"
DEFAULT_INPUT = ROOT / "data/ml_research/v2_source_reviewed_training_rows.csv"
DEFAULT_OUTPUT = ROOT / "outputs/ml_research/v2_field_holdout_assignments.csv"
DEFAULT_REPORT = ROOT / "outputs/ml_research/v2_field_holdout_readiness.json"

CORE_NUMERIC = (
    "depth_ft",
    "temperature_c",
    "reservoir_pressure",
    "porosity_pct",
    "perm_md",
    "api",
    "visc_cp",
    "so_pct",
)
REQUIRED_COLUMNS = {
    "record_id",
    "field_id",
    "field_id_status",
    "source_review_status",
    "source_url",
    "source_record_id",
    "technique",
    "formation_category",
    "reservoir_pressure_unit",
    *CORE_NUMERIC,
}
DEFAULT_CLASSES = (
    "Combustion",
    "HC immiscible",
    "Hot water",
    "Miscible CO2",
    "Miscible HC",
    "Miscible acid gas",
    "Nitrogen immiscible",
    "Polymer",
    "Steam",
)


def _truthy(value: Any) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "y"}


def _numeric(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _row_blockers(row: pd.Series) -> list[str]:
    blockers: list[str] = []
    for column in CORE_NUMERIC:
        value = _numeric(row.get(column))
        if value is None:
            blockers.append(f"{column}: missing/non-finite/non-numeric")
    values = {column: _numeric(row.get(column)) for column in CORE_NUMERIC}
    checks = (
        ("depth_ft", lambda x: x > 0.01, "must be > 0.01 ft"),
        ("temperature_c", lambda x: -20 <= x <= 400, "must be between -20 and 400 C"),
        ("reservoir_pressure", lambda x: x > 0.01, "must be > 0.01 psia"),
        ("porosity_pct", lambda x: 0 <= x <= 100, "must be between 0 and 100%"),
        ("perm_md", lambda x: x >= 0, "must be >= 0 mD"),
        ("api", lambda x: 0 <= x <= 100, "must be between 0 and 100 API"),
        ("visc_cp", lambda x: x >= 1e-6, "must be >= 1e-6 cP"),
        ("so_pct", lambda x: 0 <= x <= 100, "must be between 0 and 100%"),
    )
    for column, predicate, message in checks:
        value = values[column]
        if value is not None and not predicate(value):
            blockers.append(f"{column}: {message}")
    pressure_unit = _text(row.get("reservoir_pressure_unit")).casefold().replace(" ", "")
    if pressure_unit != "psia":
        blockers.append("reservoir_pressure_unit must be canonical psia; preserve raw source value/unit separately")
    if _text(row.get("field_id_status")).casefold() != "confirmed":
        blockers.append("field_id_status is not confirmed")
    if _text(row.get("source_review_status")).casefold() not in {"confirmed", "approved"}:
        blockers.append("source_review_status is not confirmed/approved")
    if not _text(row.get("source_url")):
        blockers.append("source_url is missing")
    if not _text(row.get("source_record_id")):
        blockers.append("source_record_id is missing")
    if _text(row.get("field_id")).casefold() in {"", "nan", "none", "unknown", "needs_review"}:
        blockers.append("field_id is unresolved")
    if _text(row.get("technique")).casefold() in {"", "nan", "none", "unknown", "needs_review", "n/a"}:
        blockers.append("technique label is unresolved")
    if _text(row.get("formation_category")).casefold() in {"", "nan", "none", "unknown", "needs_review", "n/a"}:
        blockers.append("formation category is unresolved")
    if "needs_review" in row.index and _truthy(row.get("needs_review")):
        blockers.append("row is marked needs_review")
    return blockers


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_v1_fields(path: Path) -> tuple[set[str], dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"v1 field manifest is missing: {path}. First run "
            "'python scripts/reconstruct_v1_training_field_manifest.py' and inspect its report."
        )
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"field_id", "field_id_status", "field_identity_confirmed"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"v1 field manifest is missing required columns: {missing}")
    confirmed_mask = frame["field_identity_confirmed"].map(_truthy)
    unresolved = frame.loc[~confirmed_mask]
    if not unresolved.empty:
        raise ValueError(
            "Cannot prove a genuinely unseen holdout while v1 training has "
            f"{len(unresolved)} row(s) with unconfirmed field identity. Resolve these IDs first."
        )
    field_ids = {value.strip() for value in frame["field_id"] if value.strip()}
    if not field_ids:
        raise ValueError("v1 field manifest contains no confirmed field IDs.")
    report = {
        "v1_training_rows": int(len(frame)),
        "v1_confirmed_independent_fields": int(len(field_ids)),
        "v1_unconfirmed_field_rows": int(len(unresolved)),
    }
    return field_ids, report


def prepare_field_holdout(
    dataset_path: Path,
    v1_field_manifest_path: Path,
    *,
    holdout_fields_per_class: int = 2,
    minimum_train_fields_per_class: int = 6,
    seed: int = 42,
    required_classes: tuple[str, ...] = DEFAULT_CLASSES,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate a candidate dataset and reserve deterministic whole-field holdout groups."""
    if holdout_fields_per_class < 1 or minimum_train_fields_per_class < 1:
        raise ValueError("holdout_fields_per_class and minimum_train_fields_per_class must be positive.")
    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"Source-reviewed v2 training dataset not found: {dataset_path}. "
            "Do not replace it with the candidate evidence-lead register."
        )
    df = pd.read_csv(dataset_path, dtype=object, keep_default_na=False)
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"V2 dataset lacks required source/provenance/core columns: {missing_columns}")
    if df.empty:
        raise ValueError("V2 dataset has no rows.")
    if df["record_id"].astype(str).str.strip().eq("").any():
        raise ValueError("V2 dataset contains blank record_id values.")
    if df["record_id"].astype(str).duplicated().any():
        raise ValueError("V2 dataset contains duplicate record_id values.")

    v1_fields, v1_report = _load_v1_fields(v1_field_manifest_path)
    blockers_by_row: dict[str, list[str]] = {}
    eligible_indexes: list[int] = []
    for idx, row in df.iterrows():
        blockers = _row_blockers(row)
        if blockers:
            blockers_by_row[str(row["record_id"])] = blockers
        else:
            eligible_indexes.append(idx)
    eligible = df.loc[eligible_indexes].copy()
    excluded_count = int(len(df) - len(eligible))
    if eligible.empty:
        raise ValueError(
            "No training rows passed source and feature gates; refusing to create an empty/fictional holdout. "
            f"Excluded rows: {excluded_count}."
        )

    field_class_sets = (
        eligible.groupby("field_id")["technique"]
        .apply(lambda values: set(str(value).strip() for value in values))
        .to_dict()
    )
    fields_per_class_all = {
        label: sorted(field_id for field_id, labels in field_class_sets.items() if label in labels)
        for label in required_classes
    }
    missing_labels = [label for label, fields in fields_per_class_all.items() if not fields]
    if missing_labels:
        raise ValueError(f"No eligible source-reviewed fields for required classes: {missing_labels}")

    # The holdout must be genuinely unseen relative to the deployed v1 training rows.
    candidate_holdout_fields = sorted(
        {field for fields in fields_per_class_all.values() for field in fields if field not in v1_fields},
        key=lambda field: hashlib.sha256(f"{seed}:{field}".encode("utf-8")).hexdigest(),
    )
    candidate_class_support = {
        label: sum(field in candidate_holdout_fields for field in fields)
        for label, fields in fields_per_class_all.items()
    }
    insufficient_external = {
        label: count for label, count in candidate_class_support.items()
        if count < holdout_fields_per_class
    }
    if insufficient_external:
        raise ValueError(
            "Cannot reserve the requested genuinely-unseen holdout. Counts of eligible fields absent from v1 "
            f"training are {insufficient_external}; need {holdout_fields_per_class} per class. "
            "Do not substitute fields already in the v1 manifest."
        )

    chosen: list[str] = []
    held_per_class = {label: 0 for label in required_classes}
    while any(count < holdout_fields_per_class for count in held_per_class.values()):
        best_field = None
        best_gain = 0
        for field in candidate_holdout_fields:
            if field in chosen:
                continue
            labels = field_class_sets[field]
            gain = sum(
                held_per_class[label] < holdout_fields_per_class
                for label in required_classes
                if label in labels
            )
            if gain > best_gain:
                best_field, best_gain = field, gain
        if best_field is None:
            raise ValueError(
                "Greedy field-group selection could not cover every required class without breaking group isolation."
            )
        chosen.append(best_field)
        for label in required_classes:
            if label in field_class_sets[best_field] and held_per_class[label] < holdout_fields_per_class:
                held_per_class[label] += 1

    chosen_set = set(chosen)
    eligible["split"] = eligible["field_id"].map(lambda value: "holdout" if value in chosen_set else "train")
    if eligible.loc[eligible["split"] == "holdout", "field_id"].isin(v1_fields).any():
        raise AssertionError("Internal error: holdout has a field overlapping v1 training.")
    if set(eligible.loc[eligible["split"] == "train", "field_id"]) & set(eligible.loc[eligible["split"] == "holdout", "field_id"]):
        raise AssertionError("Internal error: train and holdout field IDs overlap.")

    train = eligible[eligible["split"] == "train"]
    holdout = eligible[eligible["split"] == "holdout"]
    train_support = {
        label: int(train.loc[train["technique"] == label, "field_id"].nunique())
        for label in required_classes
    }
    holdout_support = {
        label: int(holdout.loc[holdout["technique"] == label, "field_id"].nunique())
        for label in required_classes
    }
    below_train = {
        label: count for label, count in train_support.items()
        if count < minimum_train_fields_per_class
    }
    below_holdout = {
        label: count for label, count in holdout_support.items()
        if count < holdout_fields_per_class
    }
    if below_train or below_holdout:
        raise ValueError(
            "Field holdout rejected: post-split class support fails gates. "
            f"train={below_train}; holdout={below_holdout}. No split file was produced."
        )

    assignments = eligible[["record_id", "field_id", "technique", "source_url", "source_record_id", "split"]].copy()
    report = {
        "dataset_path": str(dataset_path),
        "v1_field_manifest_path": str(v1_field_manifest_path),
        **v1_report,
        "input_rows": int(len(df)),
        "eligible_rows": int(len(eligible)),
        "excluded_rows": excluded_count,
        "excluded_record_blockers": blockers_by_row,
        "train_rows": int(len(train)),
        "holdout_rows": int(len(holdout)),
        "holdout_fields": sorted(chosen_set),
        "holdout_fields_per_class_requested": holdout_fields_per_class,
        "minimum_train_fields_per_class": minimum_train_fields_per_class,
        "train_independent_field_support": train_support,
        "holdout_independent_field_support": holdout_support,
        "holdout_v1_field_overlap": sorted(set(holdout["field_id"]) & v1_fields),
        "train_holdout_field_overlap": sorted(set(train["field_id"]) & set(holdout["field_id"])),
        "v2_holdout_gate_passed": True,
        "production_promotion_approved": False,
        "interpretation": (
            "This only reserves an untouched, source-reviewed field-grouped evaluation set. "
            "It does not imply model performance, scientific validity, or approval for production."
        ),
    }
    return assignments, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--v1-field-manifest", type=Path, default=DEFAULT_V1_FIELDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--holdout-fields-per-class", type=int, default=2)
    parser.add_argument("--minimum-train-fields-per-class", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    assignments, report = prepare_field_holdout(
        args.dataset,
        args.v1_field_manifest,
        holdout_fields_per_class=args.holdout_fields_per_class,
        minimum_train_fields_per_class=args.minimum_train_fields_per_class,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    assignments.to_csv(args.output, index=False)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "report": str(args.report), **report}, indent=2))


if __name__ == "__main__":
    main()
