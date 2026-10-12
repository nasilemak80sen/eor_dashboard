"""Evidence-preserving quality audit for the OGJ2014 technique dataset.

This script does not repair identities or merge labels automatically. It emits
review queues and support counts so a human can adjudicate from source evidence.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "src" / "notebooks" / "ml_data" / "OGJ2014_extracted_vs_Table1.xlsx"
SHEET = "OGJ2014_Extracted_Rows"
OUT = ROOT / "outputs" / "ml_research"
MISSING_TOKENS = {"", "nan", "none", "null", "na", "n/a", "unknown", "needs_review"}
RANGE_PAIRS = [
    ("depth", "depth_min_ft", "depth_max_ft", 0, None),
    ("porosity", "porosity_min_pct", "porosity_max_pct", 0, 100),
    ("permeability", "perm_min_md", "perm_max_md", 0, None),
    ("api", "api_min", "api_max", 0, 100),
    ("viscosity", "visc_min_cp", "visc_max_cp", 0, None),
    ("oil_saturation", "so_start_min_pct", "so_start_max_pct", 0, 100),
]
LABEL_EXPECTED = {
    "Combustion", "HC immiscible", "Hot water", "Miscible CO2", "Miscible HC",
    "Miscible acid gas", "Nitrogen immiscible", "Polymer", "Steam",
}


def norm_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def valid_id(series: pd.Series) -> pd.Series:
    values = series.map(norm_text).str.casefold()
    return values.ne("") & ~values.isin(MISSING_TOKENS)


def alias_key(value: object) -> str:
    value = norm_text(value).casefold().replace("’", "'")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value)


def audit(dataset: Path = DATASET) -> dict:
    if not dataset.is_file():
        raise FileNotFoundError(f"Dataset not found: {dataset}")
    df = pd.read_excel(dataset, sheet_name=SHEET, engine="openpyxl")
    required = {"record_id", "technique", "field_id", "field_name_normalized", "field_id_status"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing provenance columns required for audit: {missing}")

    field_valid = valid_id(df["field_id"])
    field_status = df["field_id_status"].map(norm_text).str.casefold()
    verified_mask = field_valid & field_status.isin({"verified", "confirmed"})
    field_support = []
    labels = df["technique"].map(norm_text)
    for label in sorted(labels.unique()):
        mask = labels.eq(label)
        field_support.append({
            "technique": label,
            "source_rows": int(mask.sum()),
            "rows_with_usable_field_id": int((mask & field_valid).sum()),
            "distinct_provisional_or_unverified_fields": int(df.loc[mask & field_valid, "field_id"].nunique()),
            "distinct_verified_fields": int(df.loc[mask & verified_mask, "field_id"].nunique()),
            "rows_with_unresolved_field_id": int((mask & ~field_valid).sum()),
        })

    unresolved = df.loc[~field_valid].copy()
    raw_col = "raw_line" if "raw_line" in df.columns else ("source_report" if "source_report" in df.columns else None)
    unresolved_rows = []
    unresolved_text_groups: dict[str, dict] = {}
    for idx, row in unresolved.iterrows():
        source_text = norm_text(row.get(raw_col, "")) if raw_col else ""
        group = unresolved_text_groups.setdefault(source_text, {
            "raw_source_text": source_text,
            "excel_rows": [],
            "record_ids": [],
            "techniques": set(),
            "formation_categories": set(),
        })
        group["excel_rows"].append(int(idx + 2))
        group["record_ids"].append(norm_text(row.get("record_id", "")))
        group["techniques"].add(norm_text(row.get("technique", "")))
        group["formation_categories"].add(norm_text(row.get("formation_category", "")))
        unresolved_rows.append({
            "excel_row": int(idx + 2),
            "record_id": norm_text(row.get("record_id", "")),
            "technique": norm_text(row.get("technique", "")),
            "formation_category": norm_text(row.get("formation_category", "")),
            "raw_source_text": source_text,
            "field_id_status": norm_text(row.get("field_id_status", "")),
            "tagging_rationale": norm_text(row.get("tagging_rationale", "")),
            "action": "manual source review; do not infer from formation, zone, well code, or row similarity",
        })

    # Potential split aliases are flags for human review only; never auto-merge groups.
    by_field_name: dict[str, dict] = {}
    by_alias: dict[str, dict] = {}
    for idx, row in df.loc[field_valid].iterrows():
        name = norm_text(row.get("field_name_normalized", ""))
        field_id = norm_text(row.get("field_id", ""))
        if not name or not field_id:
            continue
        name_key = name.casefold()
        exact = by_field_name.setdefault(name_key, {"names": set(), "field_ids": set(), "rows": []})
        exact["names"].add(name)
        exact["field_ids"].add(field_id)
        exact["rows"].append(int(idx + 2))
        key = alias_key(name)
        alias = by_alias.setdefault(key, {"names": set(), "field_ids": set(), "rows": []})
        alias["names"].add(name)
        alias["field_ids"].add(field_id)
        alias["rows"].append(int(idx + 2))

    alias_candidates = []
    def evidence_for(rows: list[int]) -> list[dict]:
        details = []
        for excel_row in sorted(set(rows)):
            source_idx = excel_row - 2
            source_row = df.iloc[source_idx]
            details.append({
                "excel_row": excel_row,
                "technique": norm_text(source_row.get("technique", "")),
                "field_name_normalized": norm_text(source_row.get("field_name_normalized", "")),
                "field_id": norm_text(source_row.get("field_id", "")),
                "raw_source_text": norm_text(source_row.get(raw_col, "")) if raw_col else "",
                "formation_category": norm_text(source_row.get("formation_category", "")),
            })
        return details

    for key, item in by_field_name.items():
        if len(item["field_ids"]) > 1:
            alias_candidates.append({
                "candidate_type": "same_casefolded_name_multiple_field_ids",
                "normalized_key": key,
                "field_names": sorted(item["names"]),
                "field_ids": sorted(item["field_ids"]),
                "source_excel_rows": sorted(item["rows"]),
                "row_evidence": evidence_for(item["rows"]),
                "decision": "review source evidence and geography; no automatic merge",
            })
    for key, item in by_alias.items():
        if len(item["names"]) > 1:
            alias_candidates.append({
                "candidate_type": "punctuation_accent_alias",
                "normalized_key": key,
                "field_names": sorted(item["names"]),
                "field_ids": sorted(item["field_ids"]),
                "source_excel_rows": sorted(item["rows"]),
                "row_evidence": evidence_for(item["rows"]),
                "decision": "review source evidence and geography; no automatic merge",
            })

    numeric_audit = {}
    feature_issues = []
    for name, low_col, high_col, minimum, maximum in RANGE_PAIRS:
        if low_col not in df.columns or high_col not in df.columns:
            numeric_audit[name] = {"status": "unavailable_missing_columns", "missing_low": None, "missing_high": None}
            continue
        low = pd.to_numeric(df[low_col], errors="coerce")
        high = pd.to_numeric(df[high_col], errors="coerce")
        invalid_order = low.notna() & high.notna() & high.lt(low)
        invalid_bounds = pd.Series(False, index=df.index)
        if minimum is not None:
            invalid_bounds |= (low.notna() & low.lt(minimum)) | (high.notna() & high.lt(minimum))
        if maximum is not None:
            invalid_bounds |= (low.notna() & low.gt(maximum)) | (high.notna() & high.gt(maximum))
        missing_low = low.isna()
        missing_high = high.isna()
        numeric_audit[name] = {
            "missing_low": int(missing_low.sum()),
            "missing_high": int(missing_high.sum()),
            "both_missing": int((missing_low & missing_high).sum()),
            "one_endpoint_missing": int((missing_low ^ missing_high).sum()),
            "invalid_min_max_order_rows": int(invalid_order.sum()),
            "out_of_plausible_bounds_rows": int(invalid_bounds.sum()),
            "minimum_rule": minimum,
            "maximum_rule": maximum,
        }
        for idx in df.index[invalid_order | invalid_bounds]:
            feature_issues.append({
                "excel_row": int(idx + 2),
                "record_id": norm_text(df.at[idx, "record_id"]),
                "technique": norm_text(df.at[idx, "technique"]),
                "feature_group": name,
                "low_column": low_col,
                "low_value": None if pd.isna(low.at[idx]) else float(low.at[idx]),
                "high_column": high_col,
                "high_value": None if pd.isna(high.at[idx]) else float(high.at[idx]),
                "issue": ";".join(
                    flag for flag, active in [
                        ("min_greater_than_max", bool(invalid_order.at[idx])),
                        ("outside_plausible_bounds", bool(invalid_bounds.at[idx])),
                    ] if active
                ),
                "action": "verify source extraction; do not clip or repair automatically",
            })

    label_rows = []
    for label, count in labels.value_counts(dropna=False).items():
        normalized = norm_text(label)
        label_rows.append({
            "raw_label": normalized,
            "row_count": int(count),
            "casefolded_whitespace_key": normalized.casefold(),
            "in_expected_label_vocabulary": normalized in LABEL_EXPECTED,
            "decision": "retain exact source label; any semantic mapping requires domain review",
        })
    label_normalized_groups: dict[str, list[str]] = defaultdict(list)
    for item in label_rows:
        label_normalized_groups[item["casefolded_whitespace_key"]].append(item["raw_label"])
    label_variants = {k: sorted(set(v)) for k, v in label_normalized_groups.items() if len(set(v)) > 1}

    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "ogj2014_unresolved_field_review.csv": unresolved_rows,
        "ogj2014_field_alias_review.csv": alias_candidates,
        "ogj2014_feature_range_issues.csv": feature_issues,
        "ogj2014_technique_label_audit.csv": label_rows,
    }
    for filename, rows in outputs.items():
        path = OUT / filename
        fields = sorted({key for row in rows for key in row})
        if not fields:
            fields = ["status"]
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    unresolved_distinct = [
        {
            **item,
            "excel_rows": sorted(item["excel_rows"]),
            "record_ids": sorted(item["record_ids"]),
            "techniques": sorted(item["techniques"]),
            "formation_categories": sorted(item["formation_categories"]),
            "row_count": len(item["excel_rows"]),
        }
        for item in unresolved_text_groups.values()
    ]
    summary = {
        "dataset": str(dataset.relative_to(ROOT)) if dataset.is_relative_to(ROOT) else str(dataset),
        "source_rows": int(len(df)),
        "source_rows_unique_record_id": bool(df["record_id"].is_unique),
        "unresolved_field_rows": len(unresolved_rows),
        "unresolved_distinct_source_text_count": len(unresolved_distinct),
        "unresolved_distinct_source_texts": unresolved_distinct,
        "unresolved_field_rows_detail": unresolved_rows,
        "field_identity_status_counts": {
            str(k): int(v) for k, v in field_status.value_counts(dropna=False).sort_index().items()
        },
        "support_by_technique": field_support,
        "provisional_identity_warning": "Current parser-generated field IDs are provisional, not independently verified; verified-field support is reported separately and must not be inferred from ID existence.",
        "potential_field_alias_or_split_candidates": len(alias_candidates),
        "alias_candidates": alias_candidates,
        "feature_completeness_and_range_audit": numeric_audit,
        "feature_range_issue_rows": len(feature_issues),
        "technique_label_counts": label_rows,
        "technique_label_keys_with_multiple_raw_variants": label_variants,
        "unrecognized_or_unreviewed_labels": [row for row in label_rows if not row["in_expected_label_vocabulary"]],
        "policy": "This audit only flags candidates. It never auto-assigns missing fields, merges field IDs, clips values, or remaps technique labels.",
    }
    (OUT / "ogj2014_data_quality_audit.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    audit()
