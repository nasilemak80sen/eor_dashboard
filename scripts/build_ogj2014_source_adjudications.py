"""Build source-adjudication sidecars without rewriting original OGJ structured labels.

The sidecars retain each source record and raw text. Out-of-taxonomy techniques are
explicitly excluded from the v1 nine-class model rather than forced into a nearby class.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_ogj2014_field_generalization as benchmark  # noqa: E402
import build_ogj2014_provenance as provenance  # noqa: E402

DATASET = ROOT / "src" / "notebooks" / "ml_data" / "OGJ2014_extracted_vs_Table1.xlsx"
SHEET = "OGJ2014_Extracted_Rows"
OUT = ROOT / "data" / "provenance"
OGJ_URL = provenance.PUBLICATION_URL
PLANALTO_URL = (
    "https://www4.planalto.gov.br/legislacao/portal-legis/legislacao-1/decretos1/1986-decretos-1"
)
MODEL_CLASSES = {
    "Combustion", "HC immiscible", "Hot water", "Miscible CO2", "Miscible HC",
    "Miscible acid gas", "Nitrogen immiscible", "Polymer", "Steam",
}


def clean(value) -> str:
    return provenance.ns(value)


def mention_set(value) -> set[str]:
    if isinstance(value, list):
        return {str(item) for item in value}
    try:
        return {str(item) for item in ast.literal_eval(str(value))}
    except Exception:
        return {str(value)}


def resolved(
    *,
    record: pd.Series,
    excel_row: int,
    source_context: str,
    source_label: str,
    model_label: str | None,
    source_page: str,
    source_evidence: str,
    reason: str,
    taxonomy_status: str | None = None,
) -> dict:
    in_taxonomy = model_label in MODEL_CLASSES
    if taxonomy_status is None:
        taxonomy_status = "in_v1_taxonomy" if in_taxonomy else "outside_v1_taxonomy"
    if in_taxonomy != bool(model_label):
        raise AssertionError(f"Invalid taxonomy mapping for row {excel_row}: {model_label}")
    return {
        "excel_row": int(excel_row),
        "record_id": clean(record.get("record_id", "")),
        "raw_source_text": clean(record.get("raw_line", "")),
        "original_structured_technique_label": clean(record.get("technique", "")),
        "source_context_type": source_context,
        "source_adjudicated_technique": source_label,
        "source_adjudicated_model_class": model_label or "",
        "taxonomy_status": taxonomy_status,
        "adjudication_status": (
            "source_adjudicated_in_taxonomy" if in_taxonomy
            else "source_adjudicated_out_of_taxonomy"
        ),
        "exclude_from_v1_nine_class_benchmark": not in_taxonomy,
        "source_table_and_page": source_page,
        "source_evidence": source_evidence,
        "adjudication_rationale": reason,
        "source_pdf_url": OGJ_URL,
        "original_label_and_source_text_mutated": False,
    }


def main() -> None:
    if not DATASET.is_file():
        raise FileNotFoundError(DATASET)
    df = pd.read_excel(DATASET, sheet_name=SHEET, engine="openpyxl")
    required = {"record_id", "technique", "raw_line", "field_id", "field_id_status"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Source workbook is missing required provenance columns: {missing}")
    if df["record_id"].isna().any() or df["record_id"].duplicated().any():
        raise ValueError("Source record IDs must be populated and unique.")

    explicit_mask, explicit_details = benchmark.label_semantic_conflict_audit(df)
    section_mask, section_details = benchmark.source_section_label_conflict_audit(df)
    explicit_ids = {item["record_id"] for item in explicit_details}
    section_ids = {item["record_id"] for item in section_details}
    if len(explicit_details) != 109 or len(section_details) != 70:
        raise ValueError(
            "Conflict review queue changed. Re-review the source mappings before continuing: "
            f"explicit={len(explicit_details)}, section={len(section_details)}"
        )
    if explicit_ids & section_ids or len(explicit_ids | section_ids) != 179:
        raise ValueError("Conflict source-row IDs are not the expected 179 disjoint records.")

    adjudications: list[dict] = []
    row_by_excel = {index + 2: row for index, row in df.iterrows()}

    # 109 text conflicts: each rule is keyed to a specific source-table technique
    # mention, not to the prior structured label.
    for item in explicit_details:
        excel_row = int(item["excel_row"])
        record = row_by_excel[excel_row]
        raw = clean(item["raw_source_text"])
        mentions = set(item["potentially_conflicting_mentions"])
        page = "OGJ 2014 Table E, printed pp. 9-11"
        if "Steam" in mentions:
            lower = raw.casefold()
            if "water (steam scavenging)" in lower or "steam scavenging" in lower:
                source_label, model_label = "Water (Steam Scavenging)", None
                page = "OGJ 2014 Table E, printed p. 10"
                rationale = (
                    "The source names Water (Steam Scavenging) as a distinct technique. "
                    "It is not silently collapsed into the model's Steam class."
                )
            elif "steam-sagd" in lower or "steam–sagd" in lower:
                source_label, model_label = "Steam-SAGD", "Steam"
                rationale = (
                    "The OGJ source explicitly identifies Steam-SAGD. The source subtype is retained; "
                    "the existing nine-class schema only has a coarser Steam class."
                )
            elif "enhanced cyclic steam" in lower:
                source_label, model_label = "Enhanced cyclic steam", "Steam"
                rationale = (
                    "The source explicitly identifies enhanced cyclic steam. The source subtype is retained; "
                    "the v1 schema maps it to the existing Steam class."
                )
            elif "cyclic steam" in lower:
                source_label, model_label = "Cyclic steam", "Steam"
                rationale = (
                    "The source explicitly identifies cyclic steam. The source subtype is retained; "
                    "the v1 schema maps it to the existing Steam class."
                )
            else:
                source_label, model_label = "Steam", "Steam"
                rationale = (
                    "The explicit Steam technique mention is consistent with the source row. "
                    "The original structured Polymer label is not overwritten; source-adjudicated targets "
                    "are stored in this sidecar."
                )
        elif "CO2 immiscible" in mentions:
            source_label, model_label = "CO2 immiscible", None
            rationale = (
                "The source explicitly names CO2 immiscible. The v1 production taxonomy has no CO2-immiscible "
                "class, and it is not equivalent to HC immiscible; exclude rather than force-map."
            )
        elif "Miscible (unspecified subtype)" in mentions:
            if "magnus" in raw.casefold():
                source_label, model_label = "Hydrocarbon miscible", "Miscible HC"
                rationale = (
                    "The OGJ Table E Hydrocarbon miscible section contains the Magnus row; the shortened extracted "
                    "fragment omitted the section/type prefix. Source section resolves the subtype to hydrocarbon."
                )
            elif "hc miscible" in raw.casefold():
                source_label, model_label = "Hydrocarbon miscible", "Miscible HC"
                rationale = (
                    "The raw source explicitly says HC miscible. Normalized to the existing v1 Miscible HC class."
                )
            else:
                raise ValueError(f"Unresolved miscible subtype at row {excel_row}: {raw}")
        elif "CO2 miscible" in mentions:
            source_label, model_label = "Miscible CO2", "Miscible CO2"
            rationale = (
                "The OGJ Table E row explicitly says CO2 miscible. This is the same technique family as the "
                "v1 Miscible CO2 class."
            )
        elif "Microbial" in mentions:
            source_label, model_label = "Microbial", None
            rationale = (
                "The OGJ Table E row explicitly says Microbial. No Microbial class exists in the v1 nine-class "
                "production taxonomy; retain the source label and exclude it from the v1 benchmark."
            )
        elif "Surfactants" in mentions:
            source_label, model_label = "Surfactant", None
            page = "OGJ 2014 Table E, printed p. 11"
            rationale = (
                "The OGJ Table E row explicitly says Surfactant. No Surfactant class exists in the v1 taxonomy; "
                "do not map to Polymer without source evidence of that specific subtype."
            )
        else:
            raise ValueError(f"No source adjudication rule for row {excel_row}: {sorted(mentions)}")

        adjudications.append(resolved(
            record=record, excel_row=excel_row, source_context="explicit_source_text",
            source_label=source_label, model_label=model_label, source_page=page,
            source_evidence=clean(item.get("raw_source_text", "")),
            reason=rationale,
        ))

    # 70 section conflicts: adjudicate by the original section heading that
    # contains the exact row. Broad sections with no specific subtype remain out of taxonomy.
    for item in section_details:
        excel_row = int(item["excel_row"])
        record = row_by_excel[excel_row]
        section = clean(item["source_section_technique_or_context"])
        raw = clean(item["raw_source_text"])
        if section == "Miscible CO2":
            source_label, model_label = "Miscible CO2", "Miscible CO2"
            page = "OGJ 2014 Table C, printed pp. 3-5; before the CO2-immiscible heading"
            rationale = (
                "The exact source row is located under the OGJ CO2-miscible section and before the CO2-immiscible "
                "heading. Its structured Miscible HC label conflicts with the printed source section."
            )
        elif section == "Steam":
            source_label, model_label = "Steam", "Steam"
            page = "OGJ 2014 Table D, printed p. 9; Steam section before the Nitrogen heading"
            rationale = (
                "The exact Shell Canada Peace River source row is under the Steam section before the subsequent "
                "Nitrogen heading. The structured Polymer/Nitrogen label is retained but superseded for the "
                "source-adjudicated benchmark target."
            )
        elif section == "Chemical, polymer, surfactant (subtype unspecified)":
            source_label, model_label = "Chemical, polymer, surfactant (subtype unspecified)", None
            page = "OGJ 2014 Table C, printed p. 7; Chemical, polymer, surfactant section"
            rationale = (
                "The source places this field under a broad Chemical, polymer, surfactant section but does not "
                "establish a specific subtype. It is not automatically mapped to Polymer or Nitrogen immiscible."
            )
        else:
            raise ValueError(f"Unknown source-section adjudication at row {excel_row}: {section}")
        adjudications.append(resolved(
            record=record, excel_row=excel_row, source_context="original_source_table_section",
            source_label=source_label, model_label=model_label, source_page=page,
            source_evidence=clean(item.get("source_evidence", "")),
            reason=rationale,
        ))

    # The 8 source fragments are separately documented field/technique adjudications,
    # not added to the 179 conflict count.
    partial_count = 0
    for index, row in df.iterrows():
        raw = clean(row.get("raw_line", ""))
        override = provenance.reviewed_partial_field_override(raw)
        if not override:
            continue
        partial_count += 1
        excel_row = int(index + 2)
        field_name, geography, evidence = override
        if field_name in {"Carmopolis", "North Palo Seco"}:
            source_label, model_label = "Steam", "Steam"
            page = "OGJ 2014 Table E, printed pp. 9-10"
            rationale = (
                "The complete numeric/formation signature in this extracted performance fragment matches the named "
                "OGJ Table E Steam row. Source label is separately recorded because the workbook's original label "
                "is not changed."
            )
        elif field_name in {"Bennett Village", "Antilles Quarry"}:
            source_label, model_label = "Water (Steam Scavenging)", None
            page = "OGJ 2014 Table E, printed p. 10"
            rationale = (
                "The complete numeric/formation signature matches the named OGJ Table E Water (Steam Scavenging) "
                "row. This distinct technique is outside the v1 nine-class taxonomy and remains excluded."
            )
        else:
            raise ValueError(f"Unmapped reviewed partial source field: {field_name}")
        adjudications.append(resolved(
            record=row, excel_row=excel_row, source_context="exact_partial_row_profile_match",
            source_label=source_label, model_label=model_label, source_page=page,
            source_evidence=evidence,
            reason=rationale,
        ))
    if partial_count != 8:
        raise ValueError(f"Expected eight source-matched partial fragments, found {partial_count}.")

    adjud_df = pd.DataFrame(adjudications).sort_values(["excel_row", "source_context_type"])
    if adjud_df["record_id"].duplicated().any():
        dupes = adjud_df.loc[adjud_df["record_id"].duplicated(), "record_id"].tolist()
        raise ValueError(f"Duplicate source adjudication records found: {dupes[:5]}")
    if len(adjud_df) != 187:
        raise ValueError(f"Expected 187 adjudication rows (179 conflicts + 8 fragments), got {len(adjud_df)}.")
    if (adjud_df["adjudication_status"] == "unresolved").any():
        raise ValueError("No row may be labeled source-adjudicated without an explicit rule.")

    identity_rows = []
    for index, row in df.iterrows():
        raw = clean(row.get("raw_line", ""))
        field_result = provenance.reviewed_partial_field_override(raw)
        if field_result:
            field_name, geography, evidence = field_result
            rationale = evidence
            identity_source = "exact_table_e_performance_profile_match"
        elif raw.startswith(("Brazil Petrobras Steam Estreito",
                             "Rio Grande do Norte (RN) Petrobras Steam Estreito")):
            field_name, geography, why = provenance.parse_table_e_field(raw)
            rationale = why.removeprefix("source_verified: ")
            identity_source = "OGJ_Table_E_plus_official_decree_92_274"
        else:
            continue
        excel_row = int(index + 2)
        identity_rows.append({
            "excel_row": excel_row,
            "record_id": clean(row.get("record_id", "")),
            "original_technique_label": clean(row.get("technique", "")),
            "raw_source_text": raw,
            "field_name_source_adjudicated": field_name,
            "geography_source_adjudicated": geography,
            "canonical_field_id": provenance.hid("FIELD", provenance.nk(field_name) + "|" + provenance.nk(geography)),
            "field_identity_status": "confirmed",
            "identity_source": identity_source,
            "source_evidence": rationale,
            "source_pdf_url": OGJ_URL,
            "government_source_url": PLANALTO_URL if "Estreito" == field_name else "",
            "original_row_preserved": True,
            "independent_new_field_group": False if field_name in {
                "Carmopolis", "Bennett Village", "Antilles Quarry", "North Palo Seco", "Estreito"
            } else True,
        })
    identity_df = pd.DataFrame(identity_rows).sort_values(["field_name_source_adjudicated", "excel_row"])
    counts = identity_df["field_name_source_adjudicated"].value_counts().to_dict()
    if len(identity_df) != 12 or counts.get("Estreito") != 4:
        raise ValueError(f"Expected 12 identity adjudications, including four Estreito records; got {counts}")
    for field_name in ("Carmopolis", "Bennett Village", "Antilles Quarry", "North Palo Seco"):
        if counts.get(field_name) != 2:
            raise ValueError(f"Expected two repeated source rows for {field_name}, got {counts.get(field_name)}")

    OUT.mkdir(parents=True, exist_ok=True)
    adjud_path = OUT / "ogj2014_technique_label_adjudications.csv"
    identity_path = OUT / "ogj2014_field_identity_adjudications.csv"
    adjud_df.to_csv(adjud_path, index=False, encoding="utf-8-sig")
    identity_df.to_csv(identity_path, index=False, encoding="utf-8-sig")

    summary = {
        "source_rows": len(df),
        "source_unique_record_ids": int(df["record_id"].nunique()),
        "explicit_text_conflicts_adjudicated": len(explicit_details),
        "source_section_conflicts_adjudicated": len(section_details),
        "source_label_conflict_records": len(explicit_details) + len(section_details),
        "additional_partial_fragment_records_adjudicated": partial_count,
        "label_adjudication_records_total": len(adjud_df),
        "in_taxonomy_records": int(adjud_df["source_adjudicated_model_class"].ne("").sum()),
        "out_of_taxonomy_records": int(adjud_df["source_adjudicated_model_class"].eq("").sum()),
        "out_of_taxonomy_source_labels": sorted(adjud_df.loc[
            adjud_df["source_adjudicated_model_class"].eq(""), "source_adjudicated_technique"
        ].unique().tolist()),
        "identity_records_resolved": len(identity_df),
        "identity_field_groups_resolved": int(identity_df["canonical_field_id"].nunique()),
        "identity_rows_by_field": counts,
        "original_structured_labels_modified": False,
        "original_raw_source_text_modified": False,
        "source_pdf_url": OGJ_URL,
        "government_estreito_source_url": PLANALTO_URL,
    }
    (OUT / "ogj2014_source_adjudication_summary.json").write_text(
        pd.Series(summary).to_json(force_ascii=False, indent=2), encoding="utf-8"
    )
    print(pd.Series(summary).to_json(force_ascii=False, indent=2))


if __name__ == "__main__":
    main()
