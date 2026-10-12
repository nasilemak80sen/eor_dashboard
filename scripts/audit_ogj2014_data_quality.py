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
TECHNIQUE_FAMILY = {
    "Miscible acid gas": "miscible_acid_gas",
    "Miscible CO2": "miscible_co2",
    "CO2 miscible": "miscible_co2",
    "Miscible HC": "miscible_hc",
    "CO2 immiscible": "co2_immiscible",
    "HC immiscible": "hc_immiscible",
    "Nitrogen immiscible": "nitrogen_immiscible",
    "Hot water": "hot_water",
    "Polymer": "polymer",
    "Combustion": "combustion",
    "Steam": "steam",
    "Enhanced cyclic steam": "steam",
    "Microbial": "microbial",
    "Nitrates": "nitrates",
    "Surfactants": "surfactants",
    "Miscible (unspecified subtype)": "miscible_unspecified",
}
TECHNIQUE_PATTERNS = [
    ("Miscible acid gas", re.compile(r"\bmiscible\s+acid\s+gas\b", re.I)),
    ("Miscible CO2", re.compile(r"\bmiscible\s+CO2\b", re.I)),
    ("CO2 miscible", re.compile(r"\bCO2\s+miscible\b", re.I)),
    ("Miscible HC", re.compile(r"\bmiscible\s+HC\b", re.I)),
    ("CO2 immiscible", re.compile(r"\bCO2\s+immiscible\b", re.I)),
    ("HC immiscible", re.compile(r"\bHC\s+immiscible\b", re.I)),
    ("Nitrogen immiscible", re.compile(r"\bnitrogen\s+immiscible\b", re.I)),
    ("Hot water", re.compile(r"\bhot\s+water\b", re.I)),
    ("Enhanced cyclic steam", re.compile(r"\benhanced\s+cyclic\s+steam\b", re.I)),
    ("Polymer", re.compile(r"\bpolymer\b", re.I)),
    ("Combustion", re.compile(r"\bcombustion\b", re.I)),
    ("Steam", re.compile(r"\bsteam\b", re.I)),
    ("Microbial", re.compile(r"\bmicrobial\b", re.I)),
    ("Nitrates", re.compile(r"\bnitrates?\b", re.I)),
    ("Surfactants", re.compile(r"\bsurfactants?\b", re.I)),
]


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


def unresolved_evidence_assessment(raw_source_text: object) -> str:
    """Human-reviewed rationale for why the current source phrase is not enough."""
    raw = norm_text(raw_source_text).casefold()
    assessments = [
        ("creek 1 member", "Creek/member/SS wording may identify a stratigraphic member or interval; no unambiguous field identity."),
        ("creek 2 member", "Creek/member/SS wording may identify a stratigraphic member or interval; no unambiguous field identity."),
        ("residual oil zone", "Explicit reservoir-zone and dolomite wording is not sufficient to identify a field."),
        ("(enhanced cyclic steam) alta.", "Technique, province/year, and Clearwater wording do not establish whether Clearwater is a field or formation."),
        ("11/14 12/11", "Date-like values and Valanginian stratigraphic wording provide no explicit field name."),
        ("2 immiscible area", "Leading technique/area tokens and Forest Sands wording do not establish a field identity."),
        ("(s ors 01)", "S ORS 01 is identifier-like and could be a project/well code; no field name is explicit."),
        ("mfb-53)", "MFB-53 is identifier-like and could be a well/project code; no field name is explicit."),
        ("mfb-23)", "MFB-23 is identifier-like and could be a well/project code; no field name is explicit."),
        ("mm-407)", "MM-407 is identifier-like and could be a well/project code; no field name is explicit."),
        ("mm-412)", "MM-412 is identifier-like and could be a well/project code; no field name is explicit."),
    ]
    for prefix, assessment in assessments:
        if raw.startswith(prefix):
            return assessment
    return "No explicit, defensible field name identified in the available source text; keep unresolved pending source-document review."


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

    support_by_label = {item["technique"]: item for item in field_support}
    remediation_priority = [
        "Miscible acid gas", "HC immiscible", "Hot water", "Nitrogen immiscible"
    ]
    remediation_rows = []
    for label, support in support_by_label.items():
        provisional_count = support["distinct_provisional_or_unverified_fields"]
        verified_count = support["distinct_verified_fields"]
        remediation_rows.append({
            "priority": remediation_priority.index(label) + 1 if label in remediation_priority else 5,
            "technique": label,
            "source_rows": support["source_rows"],
            "rows_with_usable_field_id": support["rows_with_usable_field_id"],
            "provisional_or_unverified_field_groups": provisional_count,
            "verified_independent_fields": verified_count,
            "unresolved_field_rows": support["rows_with_unresolved_field_id"],
            "minimum_verified_fields_for_pilot": 6,
            "provisional_group_gap_to_six": max(0, 6 - provisional_count),
            "verified_field_gap_to_six": max(0, 6 - verified_count),
            "recommended_action": (
                "Prioritise source-backed field identity and additional independent cases; keep class out of pilot"
                if label in remediation_priority else
                "Verify provisional field identities before treating support as independent"
            ),
        })
    remediation_rows.sort(key=lambda row: (row["priority"], row["technique"]))

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
        group["source_evidence_assessment"] = unresolved_evidence_assessment(source_text)
        assessment = unresolved_evidence_assessment(source_text)
        unresolved_rows.append({
            "excel_row": int(idx + 2),
            "record_id": norm_text(row.get("record_id", "")),
            "technique": norm_text(row.get("technique", "")),
            "formation_category": norm_text(row.get("formation_category", "")),
            "raw_source_text": source_text,
            "field_id_status": norm_text(row.get("field_id_status", "")),
            "tagging_rationale": norm_text(row.get("tagging_rationale", "")),
            "source_evidence_assessment": assessment,
            "action": "keep unresolved unless the original source document explicitly establishes field identity",
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

    feature_completeness_by_technique = {}
    for label in sorted(labels.unique()):
        class_mask = labels.eq(label)
        per_feature = {}
        for feature_name, low_col, high_col, _, _ in RANGE_PAIRS:
            low = pd.to_numeric(df[low_col], errors="coerce") if low_col in df.columns else pd.Series(float('nan'), index=df.index)
            high = pd.to_numeric(df[high_col], errors="coerce") if high_col in df.columns else pd.Series(float('nan'), index=df.index)
            missing_low = class_mask & low.isna()
            missing_high = class_mask & high.isna()
            per_feature[feature_name] = {
                "rows": int(class_mask.sum()),
                "missing_low": int(missing_low.sum()),
                "missing_high": int(missing_high.sum()),
                "both_endpoints_missing": int((missing_low & missing_high).sum()),
                "one_endpoint_missing": int((missing_low ^ missing_high).sum()),
            }
        feature_completeness_by_technique[label] = per_feature

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

    # Raw-line technique mentions are only review signals. A source row may
    # contain contextual terms, so the structured label is never auto-rewritten.
    label_semantic_candidates = []
    if raw_col:
        for idx, row in df.iterrows():
            raw_text = norm_text(row.get(raw_col, ""))
            structured_label = norm_text(row.get("technique", ""))
            structured_family = TECHNIQUE_FAMILY.get(structured_label)
            detected = []
            for term, pattern in TECHNIQUE_PATTERNS:
                if pattern.search(raw_text):
                    detected.append({"term": term, "family": TECHNIQUE_FAMILY[term]})
            explicit_miscible = any(
                item["term"] in {"Miscible acid gas", "Miscible CO2", "CO2 miscible", "Miscible HC"}
                for item in detected
            )
            if re.search(r"\bmiscible\b", raw_text, re.I) and not explicit_miscible:
                detected.append({
                    "term": "Miscible (unspecified subtype)",
                    "family": TECHNIQUE_FAMILY["Miscible (unspecified subtype)"],
                })
            conflicting = [
                item for item in detected
                if structured_family is not None and item["family"] != structured_family
            ]
            if conflicting:
                label_semantic_candidates.append({
                    "excel_row": int(idx + 2),
                    "record_id": norm_text(row.get("record_id", "")),
                    "structured_technique_label": structured_label,
                    "structured_label_family": structured_family,
                    "source_text_technique_mentions": sorted(
                        {item["term"] for item in detected}
                    ),
                    "potentially_conflicting_mentions": sorted(
                        {item["term"] for item in conflicting}
                    ),
                    "raw_source_text": raw_text,
                    "action": "manual source-table review; do not relabel from text scan alone",
                })

    source_section_label_candidates = []
    source_section_conflict_indices = set()
    if raw_col:
        normalized_raw = df[raw_col].map(norm_text)
        labels_by_raw: dict[str, set[str]] = defaultdict(set)
        for raw_text, label in zip(normalized_raw, labels):
            labels_by_raw[raw_text].add(label)

        for idx, row in df.iterrows():
            raw_text = normalized_raw.loc[idx]
            label = labels.loc[idx]
            expected_context = None
            evidence = None
            if labels_by_raw.get(raw_text) == {"Miscible CO2", "Miscible HC"} and label == "Miscible HC":
                expected_context = "Miscible CO2"
                evidence = (
                    "Exact raw_line also appears as Miscible CO2 and matches the OGJ 2014 PDF's "
                    "CO2-miscible table on pp. 3-5, before the CO2-immiscible heading."
                )
            elif raw_text.startswith("Shell Canada Peace River Alta.") and label in {"Nitrogen immiscible", "Polymer"}:
                expected_context = "Steam"
                evidence = (
                    "OGJ 2014 PDF p. 9 lists Peace River rows in the Canadian table continuation before "
                    "the next Nitrogen heading, within the preceding Steam section."
                )
            elif raw_text.startswith("Chaparral Energy North Burbank Okla.") and label == "Nitrogen immiscible":
                expected_context = "Chemical, polymer, surfactant (subtype unspecified)"
                evidence = "OGJ 2014 PDF p. 7 places North Burbank under the Chemical, polymer, surfactant section."
            elif raw_text.startswith("Occidental Midland Farms Unit Tex.") and label == "Nitrogen immiscible":
                expected_context = "Chemical, polymer, surfactant (subtype unspecified)"
                evidence = "OGJ 2014 PDF p. 7 places Midland Farms Unit under the Chemical, polymer, surfactant section."

            if expected_context is None:
                continue
            source_section_conflict_indices.add(int(idx))
            source_section_label_candidates.append({
                "excel_row": int(idx + 2),
                "record_id": norm_text(row.get("record_id", "")),
                "structured_technique_label": label,
                "source_section_technique_or_context": expected_context,
                "raw_source_text": raw_text,
                "source_evidence": evidence,
                "action": "quarantine pending source-table adjudication; keep technique label unchanged",
            })

    explicit_conflict_indices = {item["excel_row"] - 2 for item in label_semantic_candidates}
    all_conflict_indices = explicit_conflict_indices | source_section_conflict_indices
    label_conflict_index_mask = pd.Series(df.index.isin(all_conflict_indices), index=df.index)
    explicit_conflict_index_mask = pd.Series(df.index.isin(explicit_conflict_indices), index=df.index)
    source_section_conflict_index_mask = pd.Series(df.index.isin(source_section_conflict_indices), index=df.index)
    for remediation in remediation_rows:
        label = remediation["technique"]
        class_mask = labels.eq(label)
        class_explicit_mask = class_mask & explicit_conflict_index_mask
        class_source_section_mask = class_mask & source_section_conflict_index_mask
        class_conflict_mask = class_mask & label_conflict_index_mask
        class_remaining_mask = class_mask & ~label_conflict_index_mask
        remaining_fields_mask = class_remaining_mask & field_valid
        remaining_verified_mask = class_remaining_mask & verified_mask
        remediation["rows_flagged_for_explicit_label_review"] = int(class_explicit_mask.sum())
        remediation["rows_flagged_for_source_section_review"] = int(class_source_section_mask.sum())
        remediation["rows_flagged_for_label_semantic_review"] = int(class_conflict_mask.sum())
        remediation["source_rows_after_label_review"] = int(class_remaining_mask.sum())
        remediation["provisional_field_groups_after_label_review"] = int(
            df.loc[remaining_fields_mask, "field_id"].nunique()
        )
        remediation["verified_independent_fields_after_label_review"] = int(
            df.loc[remaining_verified_mask, "field_id"].nunique()
        )

    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "ogj2014_unresolved_field_review.csv": unresolved_rows,
        "ogj2014_field_alias_review.csv": alias_candidates,
        "ogj2014_feature_range_issues.csv": feature_issues,
        "ogj2014_technique_label_audit.csv": label_rows,
        "ogj2014_class_support_remediation.csv": remediation_rows,
        "ogj2014_technique_label_semantic_review.csv": label_semantic_candidates,
        "ogj2014_source_section_label_conflicts.csv": source_section_label_candidates,
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
    table_e_mask = df.get("tagging_rationale", pd.Series("", index=df.index)).fillna("").astype(str).str.contains("OGJ Table E", case=False)
    project_valid = _valid_group(df["project_id"]) if "project_id" in df.columns else pd.Series(False, index=df.index)
    case_valid = _valid_group(df["case_id"]) if "case_id" in df.columns else pd.Series(False, index=df.index)
    needs_review_mask = df.get("needs_review", pd.Series("No", index=df.index)).astype(str).str.casefold().eq("yes")
    summary = {
        "dataset": str(dataset.relative_to(ROOT)) if dataset.is_relative_to(ROOT) else str(dataset),
        "source_rows": int(len(df)),
        "source_rows_unique_record_id": bool(df["record_id"].is_unique),
        "unresolved_field_rows": len(unresolved_rows),
        "field_rows_unknown_by_source_schema": int(field_status.astype(str).eq("unknown").sum()),
        "field_rows_needing_review": int(field_status.astype(str).eq("needs_review").sum()),
        "unresolved_field_rows_excluding_source_schema_unknown": int(field_status.astype(str).isin(["needs_review", "provisional"]).sum() if "field_id" not in df.columns else ( (~field_valid) & ~field_status.astype(str).eq("unknown") ).sum()),
        "project_id_nonblank_rows": int(project_valid.sum()),
        "distinct_project_ids": int(df.loc[project_valid, "project_id"].nunique()) if "project_id" in df.columns else 0,
        "case_id_nonblank_rows": int(case_valid.sum()),
        "case_id_blank_rows": int((~case_valid).sum()),
        "rows_needing_review_flag": int(needs_review_mask.sum()),
        "table_e_rows_detected_from_tagging_rationale": int(table_e_mask.sum()),
        "table_e_rows_without_project_id": int((table_e_mask & ~project_valid).sum()),
        "table_e_rows_without_field_id": int((table_e_mask & ~field_valid).sum()),
        "unresolved_distinct_source_text_count": len(unresolved_distinct),
        "unresolved_distinct_source_texts": unresolved_distinct,
        "unresolved_field_rows_detail": unresolved_rows,
        "field_identity_status_counts": {
            str(k): int(v) for k, v in field_status.value_counts(dropna=False).sort_index().items()
        },
        "support_by_technique": field_support,
        "class_support_remediation": remediation_rows,
        "rows_quarantined_for_label_semantic_review": len(all_conflict_indices),
        "rows_quarantined_for_explicit_text_conflict": len(explicit_conflict_indices),
        "rows_quarantined_for_source_section_conflict": len(source_section_conflict_indices),
        "source_section_label_conflict_candidates": source_section_label_candidates,
        "provisional_identity_warning": "Only explicit operator-to-field spans, manually reviewed field-name rules, and source-document overrides are confirmed. Standalone candidates without sufficient source context remain provisional; verified independent-field support is reported separately.",
        "potential_field_alias_or_split_candidates": len(alias_candidates),
        "alias_candidates": alias_candidates,
        "feature_completeness_and_range_audit": numeric_audit,
        "feature_completeness_by_technique": feature_completeness_by_technique,
        "feature_range_issue_rows": len(feature_issues),
        "technique_label_counts": label_rows,
        "technique_label_keys_with_multiple_raw_variants": label_variants,
        "potential_label_semantic_conflict_rows": len(all_conflict_indices),
        "explicit_text_label_conflict_candidates": label_semantic_candidates,
        "potential_label_semantic_conflict_candidates": label_semantic_candidates + source_section_label_candidates,
        "unrecognized_or_unreviewed_labels": [row for row in label_rows if not row["in_expected_label_vocabulary"]],
        "policy": "This audit only flags candidates. It never auto-assigns missing fields, merges field IDs, clips values, or remaps technique labels.",
    }
    (OUT / "ogj2014_data_quality_audit.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    audit()
