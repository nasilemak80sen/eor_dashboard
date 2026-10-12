from pathlib import Path
from collections import Counter, defaultdict
from copy import copy
import csv, hashlib, json, re, shutil, unicodedata
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"work"/"ogj2014_provenance"; OUT.mkdir(parents=True,exist_ok=True)
CANONICAL=ROOT/"src/notebooks/ml_data/OGJ2014_extracted_vs_Table1.xlsx"
MIRROR=ROOT/"data/OGJ2014_extracted_vs_Table1.xlsx"
TARGET="OGJ2014_Extracted_Rows"
NEW_COLS=["record_id","source_report_group_id","publication_id","publication_title","publication_id_status","field_id","field_name_normalized","field_id_status","project_id","case_id","case_id_status","tagging_confidence","tagging_rationale","needs_review"]
COMPANIES=sorted(set([
"Zulia PDVSA E&P","Anzoategui PDVSA E&P","Campo Jobo PDVSA E&P","Campo Pilon PDVSA E&P","Campo Cerro Negro PDVSA E&P","Maturin, Campo Mulata PDVSA E&P","Maturin, Campo Furrial PDVSA E&P","Lower Saxony, Grafschaft Bentheim Wintershall Holding AG","Lower Saxony, Diepholz Wintershall Holding AG","Rio Grande do Norte (RN) Petrobras","Bentheim Wintershall Holding AG","Point Fortin Petrotrin","Forest Reserve Petrotrin","Oropouche Petrotrin","Guapo Petrotrin","Pekanbaru PT Caltex","Espirito Santo Petrobras","Brazil Petrobras","Bahia Petrobras","Apache Canada","ExxonMobil Oil Canada","Shell Canada","Penn West Energy Trust","Pengrowth Corporation","Derek Oil & Gas Corp.","Derek Oil","MegaWest Energy Corp.","Encore Acquisition","Continental Resources","Chaparral Energy","Core Energy","Denbury Resources","Devon Canada","Devon","Energen Resources","ExxonMobil","Fasken","Hess","Kinder Morgan","Merit Energy","Occidental","ConocoPhillips","Husky Oil","Imperial Oil","CNRL","Cenovus","Penn West Energy","Seneca Resources","Tidelands","Great Western Drilling","Stanberry Oil","XTO Energy Inc.","XTO Energy","BP","Aera Energy","Berry","Carrizo","Chevron","Anadarko","Breitburn Energy","Apache","Orla Petco","Naftex","Bayou State","Whiting Petroleum","Trinity","Stockdale","Petrobras","Petrotrin","Wintershall Holding AG","PT Caltex"]),key=len,reverse=True)
GEO=set("Calif. Calif Tex. Tex Wyo. Wyo Mo. Mo Mont. Mont Miss. Miss Alta. Alta Sask. Sask La. La Okla. Okla Alas. Alas Mich. Mich NM N.Mex. N.M. ND N.Dak. SD S.Dak. MT TX OCS Fla. Pa. Colo. Kan. Neb. Utah Ariz. Nev. Ark. Ala. Tenn. Ga. Ill. Ind. Ohio Va. N.Y. N.J. Alberta Saskatchewan".split())
DATE_RE=re.compile(r"(?<!\d)(?:\d{1,2}/\d{1,2}(?:/\d{1,2})?(?:-\d{1,2}/\d{1,2})?|19\d{2}|20\d{2})(?!\d)")
TECH=["Miscible acid gas","Miscible CO2","Miscible HC","CO2 immiscible","CO2 miscible","Hot water","Enhanced cyclic steam","Technology","Surfactants","Nitrates","Microbial","Polymer","Combustion","Steam"]

def ns(v):
    if v is None:return ""
    return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",str(v)).replace("\u00a0"," ")).strip()
def nk(v):return ns(v).casefold()
def hid(p,k):return p+"-"+hashlib.sha256(k.encode()).hexdigest()[:12]
def source_norm(v):return ns(v)
def find_company(raw):
    low=raw.casefold()
    for c in COMPANIES:
        p=low.find(c.casefold())
        if p>=0 and not (c=="Resources" and p!=0):return c,p
    return None,None
def striptech(s):
    s=ns(s)
    s=re.sub(r"^TECHNOLOGY","",s,flags=re.I).strip()
    changed=True
    while changed:
        changed=False
        for t in sorted(TECH,key=len,reverse=True):
            if s.casefold().startswith(t.casefold()+" "):
                s=s[len(t):].strip();changed=True;break
    return s
# Manually reviewed field-name prefixes for rows the general parser could not
# resolve. Each candidate is taken from an explicit field-like name in raw_line;
# formations, reservoir zones, well IDs, and ambiguous codes remain unresolved.
REVIEWED_FIELD_PREFIXES = [
    ("Kinder Morgan Goldsmith-Landreth TX", "Goldsmith-Landreth",
     "Operator prefix followed by explicit Goldsmith-Landreth field name."),
    ("Crockett 7/97", "Crockett",
     "Standalone field name immediately precedes the date token."),
    ("Resources Aneth Unit Utah San Juan", "Aneth Unit",
     "Explicit Aneth Unit name appears before Utah/San Juan geographic context."),
    ("Swan Hills LS", "Swan Hills",
     "Swan Hills is the explicit field name; LS is a following lithology abbreviation."),
    ("Carmopolis S/Congl.", "Carmopolis",
     "Carmopolis is the explicit field name preceding the sand/conglomerate abbreviation."),
    ("miscible Magnus", "Magnus",
     "Magnus is the named field following the technique qualifier."),
    ("Parrylands New Horizon Steam Block E", "Parrylands",
     "Parrylands is the explicit named field preceding operator/steam-block context."),
    ("Forest Reserve Petrotrin CO2 immiscible EOR", "Forest Reserve",
     "Explicit field name precedes operator and EOR descriptor."),
    ("L’Enfer S", "L’Enfer",
     "L’Enfer is the explicit named field; S is a following location/formation token."),
    ("L'Enfer S", "L'Enfer",
     "L'Enfer is the explicit named field; S is a following location/formation token."),
    ("Batman TPAO CO2 immiscible Bati Raman", "Bati Raman",
     "Bati Raman is the explicit named field following operator/technique context."),
    ("Superior S 23", "Superior",
     "Standalone named field token precedes the following location/measurement tokens."),
]


def parse_field(raw):
    raw=ns(raw)
    for prefix, field_name, evidence in REVIEWED_FIELD_PREFIXES:
        if raw.casefold().startswith(prefix.casefold()):
            return field_name, "reviewed_prefix: " + evidence, ""
    company,pos=find_company(raw)
    if company:
        rest=raw[pos+len(company):].strip(); m=DATE_RE.search(rest)
        if not m:return None,"no_date",""
        pre=striptech(rest[:m.start()]); toks=pre.split(); gi=None
        for i,t in enumerate(toks):
            if t in GEO:gi=i;break
        if gi is not None: field=" ".join(toks[:gi]).strip(" ,"); geo=toks[gi]
        else: field=pre.strip(" ,"); geo=""
        if field and len(field)<=100:return field,"organization_field_span",geo
        return None,"ambiguous",""
    m=DATE_RE.search(raw)
    if m:
        pre=ns(raw[:m.start()]).strip(" ,")
        if 1<=len(pre.split())<=4 and not re.search(r"\b(?:Steam|Polymer|Microbial|Combustion|miscible|immiscible)\b",pre,re.I):
            return pre,"standalone_field", ""
    return None,"unresolved",""

def matrix(path):
    wb=load_workbook(path,data_only=False,read_only=False)
    return wb,{ws.title:[[c.value for c in row] for row in ws.iter_rows()] for ws in wb.worksheets}

def verify(before,after):
    fails=[]
    if list(before)!=list(after):fails.append("sheet names/order changed")
    for s in before:
        if s==TARGET:
            a,b=before[s],after[s]
            for r in range(len(a)):
                for c in range(15):
                    av=a[r][c] if c<len(a[r]) else None; bv=b[r][c] if c<len(b[r]) else None
                    if av!=bv:fails.append(f"{s}!R{r+1}C{c+1} changed");return fails
        elif before[s]!=after[s]:fails.append(f"{s} original values changed");return fails
    return fails

def main():
    workbooks = [
        ("canonical", CANONICAL, "OGJ2014_extracted_vs_Table1_provenance.xlsx"),
        ("mirror", MIRROR, "OGJ2014_extracted_vs_Table1_provenance_mirror.xlsx"),
    ]
    source_matrices = {}
    for label, path, _ in workbooks:
        _, sheets = matrix(path)
        source_matrices[label] = sheets

    canonical_sheets = source_matrices["canonical"]
    mirror_sheets = source_matrices["mirror"]
    mismatch_rows = []
    if list(canonical_sheets) != list(mirror_sheets):
        mismatch_rows.append({
            "scope": "workbook",
            "detail": "sheet names/order differ",
            "canonical": list(canonical_sheets),
            "mirror": list(mirror_sheets),
        })
    else:
        for sheet in canonical_sheets:
            left = canonical_sheets[sheet]
            right = mirror_sheets[sheet]
            if sheet != TARGET:
                if left != right:
                    mismatch_rows.append({
                        "scope": sheet,
                        "detail": "non-target sheet values differ",
                    })
                continue

            if len(left) != len(right):
                mismatch_rows.append({
                    "scope": sheet,
                    "detail": "row counts differ",
                    "canonical_rows": len(left),
                    "mirror_rows": len(right),
                })
            for row_index in range(max(len(left), len(right))):
                left_row = left[row_index] if row_index < len(left) else []
                right_row = right[row_index] if row_index < len(right) else []
                for col_index in range(15):
                    lv = left_row[col_index] if col_index < len(left_row) else None
                    rv = right_row[col_index] if col_index < len(right_row) else None
                    if lv == rv:
                        continue
                    if (
                        row_index == 0 and col_index == 14
                        and {lv, rv} == {"raw_line", "source_report"}
                    ):
                        mismatch_rows.append({
                            "scope": f"{TARGET}!O1",
                            "detail": "known semantic header difference; columns will be tagged independently",
                            "canonical_header": lv,
                            "mirror_header": rv,
                        })
                        continue
                    mismatch_rows.append({
                        "scope": sheet,
                        "detail": f"cell R{row_index+1}C{col_index+1} differs",
                        "canonical": repr(lv),
                        "mirror": repr(rv),
                    })
                    if len(mismatch_rows) >= 30:
                        break
                if len(mismatch_rows) >= 30:
                    break
            if len(mismatch_rows) >= 30:
                break

    allowed_header_diff = next(
        (item for item in mismatch_rows if item.get("scope") == f"{TARGET}!O1"),
        None,
    )
    unexpected = [
        item for item in mismatch_rows
        if item.get("detail") != "known semantic header difference; columns will be tagged independently"
    ]
    comparison = {
        "canonical_workbook": str(CANONICAL.relative_to(ROOT)),
        "mirror_workbook": str(MIRROR.relative_to(ROOT)),
        "target_sheet": TARGET,
        "copies_have_same_original_values": len(unexpected) == 0,
        "known_header_difference": allowed_header_diff,
        "unexpected_differences": unexpected,
        "handling": (
            "Each workbook is tagged using its own original column names; source_report is never treated as raw_line."
        ),
    }
    (OUT / "ogj2014_source_copy_comparison.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )
    if unexpected:
        raise SystemExit(
            "SOURCE COPIES HAVE ADDITIONAL DIFFERENCES; no workbook was modified. "
            + json.dumps(unexpected[:10], ensure_ascii=False)
        )

    def build_tags(path: Path, source_sheets: dict, workbook_label: str) -> list[dict]:
        sheet_rows = source_sheets[TARGET]
        headers = sheet_rows[0]
        expected = [
            "technique", "formation_category", "porosity_min_pct", "porosity_max_pct",
            "perm_min_md", "perm_max_md", "depth_min_ft", "depth_max_ft", "api_min",
            "api_max", "visc_min_cp", "visc_max_cp", "so_start_min_pct",
            "so_start_max_pct", "raw_line",
        ]
        expected_mirror = expected[:14] + ["source_report"]
        existing_enriched = (
            len(headers) == 15 + len(NEW_COLS)
            and headers[:15] in (expected, expected_mirror)
            and headers[15:] == NEW_COLS
        )
        base_headers = headers[:15]
        if not existing_enriched and base_headers not in (expected, expected_mirror):
            raise SystemExit(f"Unexpected headers in {path}: {headers}")
        if len(headers) not in (15, 15 + len(NEW_COLS)):
            raise SystemExit(f"Unexpected column count in {path}: {len(headers)}")

        raw_i = base_headers.index("raw_line") if "raw_line" in base_headers else None
        sr_i = base_headers.index("source_report") if "source_report" in base_headers else None
        rows = [
            (excel_row, [row[col] if col < len(row) else None for col in range(15)])
            for excel_row, row in enumerate(sheet_rows[1:], start=2)
        ]
        occurrences = Counter()
        raw_counts = Counter(
            source_norm(values[raw_i]) for _, values in rows
            if raw_i is not None and source_norm(values[raw_i])
        )
        tags = []
        for excel_row, values in rows:
            content = "\\x1f".join("" if value is None else str(value) for value in values)
            occurrences[content] += 1
            record_id = hid("REC", content) + f"-{occurrences[content]:02d}"
            source_report = values[sr_i] if sr_i is not None else ""
            source_report_group_id = (
                hid("SRG", source_norm(source_report))
                if sr_i is not None and source_norm(source_report) else ""
            )

            if raw_i is not None:
                raw = values[raw_i]
                raw_normalized = source_norm(raw)
                field, parse_reason, geography = parse_field(raw or "")
                case_id = hid("CASE", raw_normalized) if raw_normalized else ""
                case_status = "provisional" if case_id else "needs_review"
                # Repeated raw_line supports case grouping, not field-name certainty.
                confidence = (
                    "Low" if not field
                    else ("Medium" if parse_reason.startswith("reviewed_prefix:") else "Medium")
                )
                field_id = hid("FIELD", nk(field) + "|" + nk(geography)) if field else ""
                field_status = "provisional" if field else "needs_review"
                if field and parse_reason.startswith("reviewed_prefix:"):
                    field_rationale = (
                        f"Field candidate '{field}' assigned using a manually reviewed raw_line rule: "
                        + parse_reason.removeprefix("reviewed_prefix: ").strip()
                    )
                elif field:
                    field_rationale = (
                        f"Field candidate '{field}' extracted by the conservative organization/date parser; "
                        "identity remains provisional."
                    )
                else:
                    field_rationale = "Field identity unresolved from raw_line evidence; no candidate was guessed."
                case_rationale = (
                    "case_id is a deterministic hash of exact normalized raw_line; exact repeats share a group."
                    if case_id else "No reliable raw_line evidence for a case identifier."
                )
            else:
                field = None
                case_id = ""
                case_status = "needs_review"
                field_id = ""
                field_status = "needs_review"
                confidence = "Low"
                field_rationale = (
                    "This workbook has source_report but no raw_line column; field identity was not inferred from source_report."
                )
                case_rationale = (
                    "case_id was left blank because source_report is not treated as raw_line."
                )

            rationale = " ".join([
                "No explicit publication citation/title is present; publication identity was not invented.",
                (
                    "source_report_group_id is based only on the original source_report column."
                    if sr_i is not None else
                    "No source_report column exists; source_report_group_id was not derived from raw_line."
                ),
                field_rationale,
                case_rationale,
            ])
            tags.append({
                "workbook": workbook_label,
                "excel_row": excel_row,
                "source_report": source_report,
                "record_id": record_id,
                "source_report_group_id": source_report_group_id,
                "publication_id": "",
                "publication_title": "",
                "publication_id_status": "needs_review",
                "field_id": field_id,
                "field_name_normalized": ns(field),
                "field_id_status": field_status,
                "project_id": "",
                "case_id": case_id,
                "case_id_status": case_status,
                "tagging_confidence": confidence,
                "tagging_rationale": rationale,
                "needs_review": "Yes" if field_status == "needs_review" or case_status == "needs_review" else "No",
            })
        return tags

    all_tags = {
        label: build_tags(path, source_matrices[label], label)
        for label, path, _ in workbooks
    }

    for label, path, output_name in workbooks:
        out_path = OUT / output_name
        shutil.copy2(path, out_path)
        workbook = load_workbook(out_path, data_only=False, read_only=False)
        worksheet = workbook[TARGET]
        current_headers = [
            worksheet.cell(1, col).value
            for col in range(1, worksheet.max_column + 1)
        ]
        if current_headers[15:15 + len(NEW_COLS)] == NEW_COLS:
            worksheet.delete_cols(16, len(NEW_COLS))
        elif worksheet.max_column != 15:
            raise SystemExit(f"Unexpected existing columns in {path}: {current_headers}")

        start_col = 16
        style_source = worksheet.cell(1, start_col - 1)
        for offset, header in enumerate(NEW_COLS):
            cell = worksheet.cell(1, start_col + offset, header)
            cell._style = copy(style_source._style)
            cell.font = copy(style_source.font)
            cell.fill = copy(style_source.fill)
            cell.border = copy(style_source.border)
            cell.alignment = copy(style_source.alignment)

        for excel_row, tag in enumerate(all_tags[label], start=2):
            for offset, header in enumerate(NEW_COLS):
                worksheet.cell(excel_row, start_col + offset, tag[header])
        workbook.save(out_path)

    audit_fields = ["workbook", "excel_row", "source_report"] + NEW_COLS
    with (OUT / "ogj2014_row_tagging_audit.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=audit_fields)
        writer.writeheader()
        for label, _, _ in workbooks:
            writer.writerows(all_tags[label])

    mappings = {}
    for label, _, _ in workbooks:
        for tag in all_tags[label]:
            candidates = [
                ("record_id", tag["record_id"], "row-content-hash",
                 "Original first 15 row values hashed with deterministic occurrence counter.", "confirmed"),
                ("case_id", tag["case_id"], "exact-normalized-raw_line",
                 "Exact normalized raw_line text.", "provisional"),
                ("field_id", tag["field_id"], tag["field_name_normalized"],
                 "Conservative field candidate from raw_line; inspect rationale before treating as confirmed.", "provisional"),
                ("source_report_group_id", tag["source_report_group_id"], source_norm(tag["source_report"]),
                 "Exact normalized source_report text only.", "provisional"),
            ]
            for id_type, identifier, normalized_key, evidence, status in candidates:
                if not identifier:
                    continue
                key = (label, id_type, identifier)
                if key not in mappings:
                    mappings[key] = {
                        "workbook": label,
                        "id_type": id_type,
                        "id": identifier,
                        "normalized_key": normalized_key,
                        "supporting_evidence": evidence,
                        "status": status,
                        "confidence": tag["tagging_confidence"],
                        "source_rows": [],
                        "needs_review": "No",
                    }
                mappings[key]["source_rows"].append(str(tag["excel_row"]))
                if tag["needs_review"] == "Yes":
                    mappings[key]["needs_review"] = "Yes"

    mapping_fields = ["workbook", "id_type", "id", "normalized_key", "supporting_evidence",
                      "status", "confidence", "source_rows", "needs_review"]
    with (OUT / "ogj2014_id_mapping.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=mapping_fields)
        writer.writeheader()
        for item in sorted(mappings.values(), key=lambda value: (value["workbook"], value["id_type"], value["id"])):
            item["source_rows"] = ";".join(item["source_rows"])
            writer.writerow(item)

    verification = {}
    summaries = {}
    for label, path, output_name in workbooks:
        _, before = matrix(path)
        output_path = OUT / output_name
        _, after = matrix(output_path)
        check_book = load_workbook(output_path, data_only=False, read_only=False)
        check_sheet = check_book[TARGET]
        output_headers = [
            check_sheet.cell(1, col).value
            for col in range(1, check_sheet.max_column + 1)
        ]
        failures = verify(before, after)
        tags = all_tags[label]
        if not all(tag["record_id"] for tag in tags):
            failures.append("record_id missing on one or more source rows")
        if len({tag["record_id"] for tag in tags}) != len(tags):
            failures.append("record_id is not unique within workbook")
        original_headers = before[TARGET][0][:15]
        verification[label] = {
            "input_path": str(path.relative_to(ROOT)),
            "output_path": str(output_path.relative_to(ROOT)),
            "failures": failures,
            "original_rows_including_header": len(before[TARGET]),
            "output_rows_including_header": len(after[TARGET]),
            "original_columns": 15,
            "output_columns": len(output_headers),
            "original_headers_preserved": output_headers[:15] == original_headers,
            "provenance_columns_appended_in_order": output_headers[15:] == NEW_COLS,
            "technique_unchanged": all(
                before[TARGET][index][0] == after[TARGET][index][0]
                for index in range(len(before[TARGET]))
            ),
            "needs_review_rows": sum(tag["needs_review"] == "Yes" for tag in tags),
        }
        summaries[label] = {
            "workbook": str(path.relative_to(ROOT)),
            "rows_tagged": len(tags),
            "source_report_column_present": "source_report" in original_headers,
            "distinct_source_report_groups": len({
                tag["source_report_group_id"] for tag in tags if tag["source_report_group_id"]
            }),
            "distinct_record_ids": len({tag["record_id"] for tag in tags if tag["record_id"]}),
            "distinct_case_ids": len({tag["case_id"] for tag in tags if tag["case_id"]}),
            "distinct_field_ids": len({tag["field_id"] for tag in tags if tag["field_id"]}),
            "publication_ids_assigned": 0,
            "project_ids_assigned": 0,
            "field_rows_needing_review": sum(tag["field_id_status"] == "needs_review" for tag in tags),
            "case_rows_needing_review": sum(tag["case_id_status"] == "needs_review" for tag in tags),
        }

    summary = {
        "source_copy_comparison": comparison,
        "per_workbook": summaries,
        "verification": verification,
        "rows_tagged_total_across_copies": sum(len(tags) for tags in all_tags.values()),
        "notes": [
            "The two workbook copies retain their own original column names and values.",
            "raw_line is used for field/case candidate extraction only when that column exists.",
            "source_report is never treated as raw_line; on the mirror copy it contributes only to source_report_group_id.",
            "All provenance IDs are grouping/audit metadata, not model features.",
            "Publication and project identities were not invented from the workbook name or raw text.",
        ],
    }
    (OUT / "ogj2014_provenance_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (OUT / "ogj2014_provenance_summary.md").write_text(
        "# OGJ2014 provenance preparation\n\n"
        + json.dumps(summary, indent=2)
        + "\n\nThe source-copy comparison is reported explicitly. Each workbook is enriched from its own schema; "
          "the mirror's source_report column is never repurposed as raw_line.\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    if any(item["failures"] for item in verification.values()):
        raise SystemExit("Workbook verification failed; inspect summary before consuming the outputs.")


if __name__=="__main__":
    main()
