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
"Zulia PDVSA E&P","Anzoategui PDVSA E&P","Campo Jobo PDVSA E&P","Campo Pilon PDVSA E&P","Campo Cerro Negro PDVSA E&P","Maturin, Campo Mulata PDVSA E&P","Maturin, Campo Furrial PDVSA E&P","Lower Saxony, Grafschaft Bentheim Wintershall Holding AG","Lower Saxony, Diepholz Wintershall Holding AG","Rio Grande do Norte (RN) Petrobras","Bentheim Wintershall Holding AG","Point Fortin Petrotrin","Forest Reserve Petrotrin","Oropouche Petrotrin","Guapo Petrotrin","Pekanbaru PT Caltex","Espirito Santo Petrobras","Brazil Petrobras","Bahia Petrobras","Apache Canada","ExxonMobil Oil Canada","Shell Canada","Penn West Energy Trust","Pengrowth Corporation","Derek Oil & Gas Corp.","Derek Oil","MegaWest Energy Corp.","Encore Acquisition","Continental Resources","Chaparral Energy","Core Energy","Denbury Resources","Devon Canada","Devon","Energen Resources","ExxonMobil","Fasken","Hess","Kinder Morgan","Merit Energy","Occidental","ConocoPhillips","Husky Oil","Imperial Oil","CNRL","Cenovus","Penn West Energy","Seneca Resources","Tidelands","Great Western Drilling","Stanberry Oil","XTO Energy Inc.","XTO Energy","BP","Aera Energy","Berry","Carrizo","Chevron","Anadarko","Breitburn Energy","Apache","Orla Petco","Naftex","Bayou State","Whiting Petroleum","Trinity","Stockdale","Petrobras","Petrotrin","Wintershall Holding AG","PT Caltex","Scimitar","Nederlandse Aardolie Maatschappij (NAM)"]),key=len,reverse=True)
GEO=set("Calif. Calif Tex. Tex Wyo. Wyo Mo. Mo Mont. Mont Miss. Miss Alta. Alta Sask. Sask La. La Okla. Okla Alas. Alas Mich. Mich NM N.Mex. N.M. ND N.Dak. SD S.Dak. MT TX OCS Fla. Pa. Colo. Kan. Neb. Utah Ariz. Nev. Ark. Ala. Tenn. Ga. Ill. Ind. Ohio Va. N.Y. N.J. Alberta Saskatchewan".split())
DATE_RE=re.compile(r"(?<!\d)(?:\d{1,2}/\d{1,2}(?:/\d{1,2})?(?:-\d{1,2}/\d{1,2})?|19\d{2}|20\d{2})(?!\d)")
TECH=["Water (Steam Scavenging)","Hydrocarbon miscible","HC miscible/water","Cyclic steam","Steam–SAGD","Steam-SAGD","Miscible acid gas","Miscible CO2","Miscible HC","HC miscible","CO2 immiscible","CO2 miscible","Hot water","Enhanced cyclic steam","Technology","Surfactants","Surfactant","Nitrates","Microbial","Combustion","AGA","Polymer","Steam"]

def ns(v):
    if v is None:return ""
    return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",str(v)).replace("\u00a0"," ")).strip()
def nk(v):return ns(v).casefold()
def hid(p,k):return p+"-"+hashlib.sha256(k.encode()).hexdigest()[:12]
def source_norm(v):return ns(v)

PUBLICATION_TITLE = "2014 worldwide EOR survey"
PUBLICATION_URL = "https://img.ogj.com/files/base/ebm/ogj/document/2014/05/content_dam_ogj_en_downloadables_survey_downloads_worldwide_eor_2014_leftcolumn_downloadable_140505ogj_world_eor_corrected_79_91.pdf?dl=content_dam_ogj_en_downloadables_survey_downloads_worldwide_eor_2014_leftcolumn_downloadable_140505ogj_world_eor_corrected_79_91.pdf"
PUBLICATION_ID = hid("PUB", "Oil & Gas Journal|2014 worldwide EOR survey|Leena Koottungal")
PUBLICATION_EVIDENCE = (
    "Matched against the original Oil & Gas Journal '2014 worldwide EOR survey' PDF; "
    "the PDF identifies the survey title and Leena Koottungal as survey editor/news writer. "
    + PUBLICATION_URL
)
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
# Evidence-backed canonicalization is intentionally narrow: punctuation-only
# variants are unified only when the operator, field wording, formation and
# surrounding source context agree. Same-name fields in different geography
# are not merged.
REVIEWED_FIELD_CANONICAL_ALIASES = {}

REVIEWED_PROJECT_CANONICAL_ALIASES = {
    "arecuna (f.o)": "Arecuna (F.O.)",
    "arecuna (f.o.)": "Arecuna (F.O.)",
    "bare (f.o)": "Bare (F.O.)",
    "bare (f.o).": "Bare (F.O.)",
}
REVIEWED_FIELD_GEOGRAPHY = {
    "swan hills": "Alta.",
}

# Source-document overrides for previously unresolved rows. Field names and
# operator/location context are explicit in the original OGJ 2014 PDF.
REVIEWED_SOURCE_FIELD_OVERRIDES = [
    ("Creek 1 Member SS", "Salt Creek Southern Unit", "Wyo.",
     "OGJ 2014 worldwide EOR survey, p. 3: Anadarko Salt Creek Southern Unit, Wyoming; Creek 1 Member is the pay-zone text."),
    ("Creek 2 Member SS", "Salt Creek Southern Unit", "Wyo.",
     "OGJ 2014 worldwide EOR survey, p. 3: Anadarko Salt Creek Southern Unit, Wyoming; Creek 2 Member is the pay-zone text."),
    ("Residual Oil Zone Dolo.", "Hanford (San Andres)", "Tex.",
     "OGJ 2014 worldwide EOR survey, p. 3: Fasken Hanford (San Andres), Texas; Residual Oil Zone is reservoir/pay-zone context."),
    ("(Enhanced cyclic steam) Alta. 2002", "Cold Lake", "Alta.",
     "OGJ 2014 worldwide EOR survey, p. 7: Imperial Oil Cold Lake (Enhanced cyclic steam), Alberta; Clearwater is the pay zone, not the field."),
    ("Apache Canada Zama-Keg River Alta.", "Zama-Keg River", "Alta.",
     "OGJ 2014 worldwide EOR survey, p. 7: Acid gas miscible, Apache Canada, field Zama-Keg River, Alberta."),
    ("Hockley 2008 1,048 96 30 San Andres Dolo. 10", "Slaughter (North West Mallet)", "Tex. Hockley",
     "OGJ 2014 worldwide EOR survey, p. 5: the row reads Occidental Slaughter (North West Mallet), Texas, Hockley County, 2008, 1,048 acres, 96 producing wells, 30 injectors, San Andres Dolomite, 10% porosity."),
    ("Resources McElmo Unit Utah", "McElmo Unit", "Utah",
     "OGJ 2014 worldwide EOR survey, p. 5: the row reads Resolute Natural Resources McElmo Unit, Utah, 1/1/1985; 'Resources' is the operator suffix, not the field name."),
    ("BP Prudhoe Bay Alas.", "Prudhoe Bay", "Alas.",
     "OGJ 2014 worldwide EOR survey, p. 7: Hydrocarbon immiscible, BP, field Prudhoe Bay, Alaska."),
    ("BP Alaska Milne Point Alas.", "Alaska Milne Point", "Alas.",
     "OGJ 2014 worldwide EOR survey, p. 7: Hydrocarbon immiscible, BP, field Alaska Milne Point, Alaska."),
    ("Chevron San Ardo Calif.", "San Ardo", "Calif.",
     "OGJ 2014 worldwide EOR survey, p. 1: Hot water, Chevron, field San Ardo, California."),
    ("Chevron West Coalinga Calif.", "West Coalinga", "Calif.",
     "OGJ 2014 worldwide EOR survey, p. 1: Hot water, Chevron, field West Coalinga, California."),
    ("ExxonMobil Hawkins Tex.", "Hawkins", "Tex.",
     "OGJ 2014 worldwide EOR survey, p. 7: Nitrogen immiscible, ExxonMobil, field Hawkins, Texas."),
    ("Occidental Elk Hills Calif.", "Elk Hills", "Calif.",
     "OGJ 2014 worldwide EOR survey, p. 7: Nitrogen immiscible, Occidental, field Elk Hills, California."),
    ("Chaparral Energy North Burbank Okla.", "North Burbank", "Okla.",
     "OGJ 2014 worldwide EOR survey, p. 7: Chemical, polymer, surfactant section, field North Burbank, Oklahoma; this confirms field identity, not the structured technique label."),
    ("Occidental Midland Farms Unit Tex.", "Midland Farms Unit", "Tex.",
     "OGJ 2014 worldwide EOR survey, p. 7: Chemical, polymer, surfactant section, field Midland Farms Unit, Texas; this confirms field identity, not the structured technique label."),
    ("Shell Canada Peace River Alta.", "Peace River", "Alta.",
     "OGJ 2014 worldwide EOR survey, p. 9: Canadian EOR table lists Peace River rows before the next Nitrogen heading; field identity confirmed, technique label not inferred from this field rule."),
]

# Table E has separate Project and Field columns; its Field cells are blank
# in the source rows represented here. Do not turn project/pay-zone text into field IDs.
TABLE_E_PROJECT_OVERRIDES = [
    ("11/14 12/11", "Emlichheim, Block 11/14", "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG",
     "OGJ 2014 worldwide EOR survey, p. 9: project Emlichheim, Block 11/14; Field cell blank, 12/11 is start date."),
    ("Lower Saxony, Grafschaft Bentheim Wintershall Holding AG Steam Emlichheim, Block 11/14", "Emlichheim, Block 11/14", "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG",
     "OGJ 2014 worldwide EOR survey, p. 9: project Emlichheim, Block 11/14; Field cell blank."),
    ("Bentheim Wintershall Holding AG Steam Emlichheim, Block 11/14", "Emlichheim, Block 11/14", "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG",
     "OGJ 2014 worldwide EOR survey, p. 9: project Emlichheim, Block 11/14; Field cell blank."),
    ("Forest Reserve Petrotrin CO2 immiscible EOR 34-Cyclic", "EOR 34-Cyclic", "Forest Reserve Petrotrin",
     "OGJ 2014 worldwide EOR survey, p. 9: project EOR 34-Cyclic; Forest Reserve is the area, Field cell blank."),
    ("Northeast 2/02", "Northeast", "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG",
     "OGJ 2014 worldwide EOR survey, p. 9: project Northeast; Field cell blank."),
    ("7 North 2/99", "7 North", "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG",
     "OGJ 2014 worldwide EOR survey, p. 9: project 7 North; Field cell blank."),
    ("9 North 7/08", "9 North", "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG",
     "OGJ 2014 worldwide EOR survey, p. 9: project 9 North; Field cell blank."),
    ("miscible Magnus 10/02", "Magnus", "Shetlands Islands BP",
     "OGJ 2014 worldwide EOR survey, p. 10: project Magnus; Field cell blank."),
    ("water Furrial 8/98", "Furrial", "Maturin, Campo Furrial PDVSA E&P",
     "OGJ 2014 worldwide EOR survey, p. 11: project Furrial; raw fragment retains technique and project, Field cell blank."),
    ("2 immiscible Area 2102", "Area 2102", "Forest Reserve Petrotrin",
     "OGJ 2014 worldwide EOR survey, p. 9: project Area 2102; Forest Reserve is the area, Field cell blank."),
    ("(S ORS 01) US", "Orocual", "Maturin, Campo Orocual PDVSA E&P",
     "OGJ 2014 worldwide EOR survey, p. 11: project Orocual; S ORS 01 is pay-zone text and Field cell blank."),
    ("MFB-53)", "Bare (F.O.)", "Anzoategui PDVSA E&P",
     "OGJ 2014 worldwide EOR survey, p. 11: pay-zone identifier MFB-53 maps to project Bare (F.O.); Field cell blank."),
    ("MFB-23)", "Bare (F.O.)", "Anzoategui PDVSA E&P",
     "OGJ 2014 worldwide EOR survey, p. 11: pay-zone identifier MFB-23 maps to project Bare (F.O.); Field cell blank."),
    ("MM-407)", "Melones", "Anzoategui PDVSA E&P",
     "OGJ 2014 worldwide EOR survey, p. 11: pay-zone identifier MM-407 maps to project Melones; Field cell blank."),
    ("MM-412)", "Melones", "Anzoategui PDVSA E&P",
     "OGJ 2014 worldwide EOR survey, p. 11: pay-zone identifier MM-412 maps to project Melones; Field cell blank."),
    ("Superior S 23", "Bachaquero Lago", "Zulia PDVSA E&P",
     "OGJ 2014 worldwide EOR survey, p. 11: pay-zone suffix Superior S 23 uniquely matches project Bachaquero Lago; Field cell blank."),
    ("Parrylands New Horizon Steam Block E", "Block E", "Parrylands New Horizon",
     "OGJ 2014 worldwide EOR survey, p. 9: Parrylands is the area; project Block E; Field cell blank."),
    ("Batman TPAO CO2 immiscible Bati Raman", "Bati Raman", "Batman TPAO",
     "OGJ 2014 worldwide EOR survey, p. 11: project Bati Raman; Field cell blank."),
    ("Maturin, Campo Orocual PDVSA E&P Steam Orocual", "Orocual", "Maturin, Campo Orocual PDVSA E&P",
     "OGJ 2014 worldwide EOR survey, p. 11: project Orocual; Field cell blank."),
]

REVIEWED_FIELD_PREFIXES = [
    ("Kinder Morgan Goldsmith-Landreth TX", "Goldsmith-Landreth",
     "Operator prefix followed by explicit Goldsmith-Landreth field name."),
    ("Crockett 7/97", "Crockett",
     "Standalone field name immediately precedes the date token."),
    ("Resources Aneth Unit Utah San Juan", "Aneth Unit",
     "Explicit Aneth Unit name appears before Utah/San Juan geographic context."),
    ("Swan Hills LS", "Swan Hills",
     "Swan Hills is the explicit field name; LS is a following lithology abbreviation."),
]


def parse_field(raw):
    raw=ns(raw)
    for prefix, field_name, geography, evidence in REVIEWED_SOURCE_FIELD_OVERRIDES:
        if raw.casefold().startswith(prefix.casefold()):
            return field_name, "source_verified: " + evidence, geography
    for prefix, field_name, evidence in REVIEWED_FIELD_PREFIXES:
        if raw.casefold().startswith(prefix.casefold()):
            canonical_name = REVIEWED_FIELD_CANONICAL_ALIASES.get(
                field_name.casefold(), field_name
            )
            geography = REVIEWED_FIELD_GEOGRAPHY.get(canonical_name.casefold(), "")
            if canonical_name != field_name:
                evidence += " Canonicalized a punctuation-only alias supported by matching operator, field wording, formation, and source context."
            if geography:
                evidence += " Assigned Alberta (Alta.) from corroborating source rows that name the same Swan Hills field; LS is the following lithology abbreviation."
            return canonical_name, "reviewed_prefix: " + evidence, geography
    company,pos=find_company(raw)
    if company:
        rest=raw[pos+len(company):].strip(); m=DATE_RE.search(rest)
        if not m:return None,"no_date",""
        pre=striptech(rest[:m.start()]); toks=pre.split(); gi=None
        for i,t in enumerate(toks):
            if t in GEO:gi=i;break
        if gi is not None: field=" ".join(toks[:gi]).strip(" ,"); geo=toks[gi]
        else: field=pre.strip(" ,"); geo=""
        if field and len(field)<=100:
            canonical_name = REVIEWED_FIELD_CANONICAL_ALIASES.get(field.casefold(), field)
            if canonical_name != field:
                return canonical_name, "organization_field_span: punctuation-only alias canonicalized from matching source context", geo
            return field,"organization_field_span",geo
        return None,"ambiguous",""
    m=DATE_RE.search(raw)
    if m:
        pre=ns(raw[:m.start()]).strip(" ,")
        if 1<=len(pre.split())<=4 and not re.search(r"\b(?:Steam|Polymer|Microbial|Combustion|miscible|immiscible)\b",pre,re.I):
            return pre,"standalone_field", ""
    return None,"unresolved",""

TABLE_E_SOURCE_PREFIXES = (
    "Bahia Petrobras", "Brazil Petrobras", "Espirito Santo Petrobras",
    "Rio Grande do Norte (RN) Petrobras", "Sergipe Petrobras",
    "Bentheim Wintershall Holding AG", "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG",
    "Lower Saxony, Diepholz Wintershall Holding AG", "Northeast ", "7 North ", "9 North ",
    "Pekanbaru PT Caltex", "Drenthe Nederlandse Aardolie Maatschappij", "North Sea, Rogaland BP",
    "Shetlands Islands BP", "Parrylands New Horizon", "Forest Reserve Petrotrin",
    "Oropouche Petrotrin", "Guapo Petrotrin", "Point Fortin Petrotrin", "Palo Seco Petrotrin",
    "Quarry Petrotrin", "North Palo Seco Petrotrin", "Maturin, Campo", "Anzoategui PDVSA E&P",
    "Cairo Scimitar", "Batman TPAO", "Campo Cerro Negro", "Campo Jobo", "Campo Pilon",
    "Zulia PDVSA E&P", "11/14 12/11", "2 immiscible Area 2102", "(S ORS 01)",
    "MFB-53)", "MFB-23)", "MM-407)", "MM-412)", "Superior S 23", "miscible Magnus",
    "water Furrial ",
)


def is_table_e_source_row(raw: str) -> bool:
    """Identify international Table E rows/fragments by source-text evidence, not row position."""
    text = ns(raw)
    return any(text.casefold().startswith(prefix.casefold()) for prefix in TABLE_E_SOURCE_PREFIXES)


AMBIGUOUS_SOURCE_FRAGMENT_PREFIXES = (
    "Carmopolis S/Congl.", "L’Enfer S", "L'Enfer S", "Forest Sands S", "Valanginian ",
    "Naricual S", "Acu S ", "Urucutuca S", "Bluesky S", "Cretaceous-Bullhead",
    "Cruse E", "Cruse E & F", "L.L. S ", "Morichal-Memb.", "Jobo Member",
    "Rindu ", "Pertama-Kedua", "Garzan LS", "Bachaquero S", "Wabiskaw",
    "T(YAC.MFA-52)", "Catu-1 S",
)


def is_ambiguous_source_fragment(raw: str) -> bool:
    """Detect pay-zone/reservoir fragments that cannot establish a field or project."""
    text = ns(raw)
    return any(text.casefold().startswith(prefix.casefold()) for prefix in AMBIGUOUS_SOURCE_FRAGMENT_PREFIXES)


def parse_project(raw):
    """Parse the project column for OGJ Table E only; never treat it as a field."""
    raw = ns(raw)
    for prefix, project_name, project_context, evidence in TABLE_E_PROJECT_OVERRIDES:
        if raw.casefold().startswith(prefix.casefold()):
            project_name = REVIEWED_PROJECT_CANONICAL_ALIASES.get(project_name.casefold(), project_name)
            return project_name, project_context, "source_verified: " + evidence

    company, pos = find_company(raw)
    if not company:
        return None, "", "unresolved"
    project_context = ns(raw[:pos + len(company)])
    if project_context.casefold() == "bentheim wintershall holding ag":
        project_context = "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG"
    rest = striptech(raw[pos + len(company):].strip())
    date_match = DATE_RE.search(rest)
    if not date_match:
        return None, project_context, "no_date"
    project_name = ns(rest[:date_match.start()]).strip(" ,")
    if not project_name or len(project_name) > 100:
        return None, project_context, "ambiguous_project_span"
    project_name = REVIEWED_PROJECT_CANONICAL_ALIASES.get(project_name.casefold(), project_name)
    return project_name, project_context, "source_project_span"


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
                            "detail": "known header difference; source_report semantics unresolved, so source_report_group_id will be withheld",
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
        if item.get("detail") != "known header difference; source_report semantics unresolved, so source_report_group_id will be withheld"
    ]
    comparison = {
        "canonical_workbook": str(CANONICAL.relative_to(ROOT)),
        "mirror_workbook": str(MIRROR.relative_to(ROOT)),
        "target_sheet": TARGET,
        "copies_have_same_original_values": len(unexpected) == 0,
        "known_header_difference": allowed_header_diff,
        "unexpected_differences": unexpected,
        "handling": (
            "Each workbook preserves its own original column names. Because mirror O1 says source_report while its values match canonical raw_line values, the mirror's source_report semantics are unconfirmed and no source_report_group_id is assigned."
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

    source_report_semantics_confirmed = allowed_header_diff is None
    def build_tags(
        path: Path,
        source_sheets: dict,
        workbook_label: str,
        *,
        source_report_semantics_confirmed: bool,
    ) -> list[dict]:
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
        tags = []
        for excel_row, values in rows:
            content = "\\x1f".join("" if value is None else str(value) for value in values)
            occurrences[content] += 1
            record_id = hid("REC", content) + f"-{occurrences[content]:02d}"
            source_report = values[sr_i] if sr_i is not None else ""
            source_report_group_id = (
                hid("SRG", source_norm(source_report))
                if sr_i is not None
                and source_report_semantics_confirmed
                and source_norm(source_report)
                else ""
            )

            project_id = ""
            project_name = ""
            project_context = ""
            source_table = "unknown"
            project_rationale = (
                "No separate project column is provided in source Tables A-D; project_id intentionally left blank."
            )
            if raw_i is not None:
                raw = values[raw_i]
                raw_normalized = source_norm(raw)
                table_e_row = is_table_e_source_row(raw or "")
                ambiguous_fragment = is_ambiguous_source_fragment(raw or "")
                source_table = (
                    "Table E" if table_e_row
                    else ("Ambiguous source fragment" if ambiguous_fragment else "Tables A-D")
                )
                if table_e_row or ambiguous_fragment:
                    # OGJ Table E has distinct Project and Field columns. In the
                    # source rows represented here the Field cell is blank; do not
                    # mislabel the project name or pay zone as a field.
                    project_name, project_context, project_reason = (
                        parse_project(raw or "") if table_e_row else (None, "", "unresolved")
                    )
                    project_id = (
                        hid("PROJ", nk(project_context) + "|" + nk(project_name))
                        if project_name else ""
                    )
                    field = None
                    geography = ""
                    field_id = ""
                    field_status = "unknown"
                    confidence = "High" if project_id else "Low"
                    field_rationale = (
                        "OGJ Table E separates Project and Field. The source Field cell is blank for this row; "
                        "field_id is intentionally blank rather than reusing the project name or pay-zone text."
                        if table_e_row else
                        "raw_line is an ambiguous pay-zone/reservoir fragment without enough source-row context to identify a field; "
                        "field_id is intentionally blank."
                    )
                    if project_id:
                        if project_reason.startswith("source_verified:"):
                            evidence = project_reason.removeprefix("source_verified: ").strip()
                        else:
                            evidence = (
                                f"Project '{project_name}' is the explicit text between the source technique and start-date "
                                f"columns in OGJ Table E; source context '{project_context}'."
                            )
                        project_rationale = (
                            f"Project identity confirmed from the original OGJ source document: {evidence} "
                            f"Source PDF: {PUBLICATION_URL}"
                        )
                        case_id = hid("CASE", raw_normalized) if raw_normalized else ""
                        case_status = "provisional" if case_id else "needs_review"
                        case_rationale = (
                            "case_id is a deterministic hash of the exact normalized source fragment; repeated fragments share a group."
                            if case_id else
                            "No reliable source fragment for a case identifier."
                        )
                    else:
                        case_id = ""
                        case_status = "needs_review"
                        project_rationale = (
                            "Project identity unresolved because raw_line is a partial source fragment that does not uniquely "
                            "identify a project; no project_id was guessed."
                        )
                        case_rationale = (
                            "case_id withheld because the partial source fragment may represent multiple projects."
                        )
                else:
                    field, parse_reason, geography = parse_field(raw or "")
                    case_id = hid("CASE", raw_normalized) if raw_normalized else ""
                    case_status = "provisional" if case_id else "needs_review"
                    # Explicit operator -> field span -> geography/date and
                    # manually reviewed source rules support confirmed field IDs.
                    source_confirmed = bool(field) and (
                        parse_reason.startswith("source_verified:")
                        or parse_reason.startswith("reviewed_prefix:")
                        or parse_reason.startswith("organization_field_span")
                    )
                    confidence = "High" if source_confirmed else ("Medium" if field else "Low")
                    field_id = hid("FIELD", nk(field) + "|" + nk(geography)) if field else ""
                    field_status = (
                        "confirmed" if source_confirmed
                        else ("provisional" if field else "needs_review")
                    )
                    if field and parse_reason.startswith("source_verified:"):
                        field_rationale = (
                            f"Field identity confirmed from the original OGJ source document: "
                            + parse_reason.removeprefix("source_verified: ").strip()
                            + " Source PDF: " + PUBLICATION_URL
                        )
                    elif field and parse_reason.startswith("reviewed_prefix:"):
                        field_rationale = (
                            f"Field identity confirmed by a manually reviewed explicit field-name rule: "
                            + parse_reason.removeprefix("reviewed_prefix: ").strip()
                            + " Source PDF: " + PUBLICATION_URL
                        )
                    elif field and parse_reason.startswith("organization_field_span"):
                        field_rationale = (
                            f"Field identity confirmed from the explicit operator-to-field span '{field}' "
                            "bounded by source geography/date text in raw_line. Source PDF: "
                            + PUBLICATION_URL
                        )
                    elif field:
                        field_rationale = (
                            f"Field candidate '{field}' is a standalone pre-date span without sufficient operator/geography "
                            "context; retained as provisional pending corroboration."
                        )
                    else:
                        field_rationale = "Field identity unresolved from raw_line evidence; no candidate was guessed."
                    case_rationale = (
                        "case_id is a deterministic hash of exact normalized raw_line; exact repeats share a group."
                        if case_id else "No reliable raw_line evidence for a case identifier."
                    )
            else:
                field = None
                project_name = ""
                project_context = ""
                project_id = ""
                project_rationale = (
                    "This workbook has source_report but no raw_line column; project identity was not inferred from source_report."
                )
                case_id = ""
                case_status = "needs_review"
                field_id = ""
                field_status = "unknown"
                confidence = "Low"
                field_rationale = (
                    "This workbook has source_report but no raw_line column; field identity was not inferred from source_report."
                )
                case_rationale = (
                    "case_id was left blank because source_report is not treated as raw_line."
                )

            rationale = " ".join([
                "Publication identity confirmed: " + PUBLICATION_EVIDENCE,
                (
                    (
                        "source_report_group_id is based only on the original source_report column."
                        if source_report_semantics_confirmed else
                        "source_report_group_id was withheld because the mirror's source_report header conflicts with the canonical raw_line header and the values are identical; confirm the column semantics before grouping."
                    )
                    if sr_i is not None else
                    "No source_report column exists; source_report_group_id was not derived from raw_line."
                ),
                field_rationale,
                project_rationale,
                case_rationale,
            ])
            tags.append({
                "workbook": workbook_label,
                "excel_row": excel_row,
                "source_table": source_table,
                "source_report": source_report,
                "record_id": record_id,
                "source_report_group_id": source_report_group_id,
                "publication_id": PUBLICATION_ID,
                "publication_title": PUBLICATION_TITLE,
                "publication_id_status": "confirmed",
                "field_id": field_id,
                "field_name_normalized": ns(field),
                "field_id_status": field_status,
                "project_id": project_id,
                "project_name_normalized": ns(project_name),
                "project_context_normalized": ns(project_context),
                "project_id_status_internal": (
                    "confirmed" if project_id
                    else ("unknown" if source_table in {"Table E", "Ambiguous source fragment"} else "not_applicable")
                ),
                "case_id": case_id,
                "case_id_status": case_status,
                "tagging_confidence": confidence,
                "tagging_rationale": rationale,
                "needs_review": "Yes" if field_status in {"needs_review", "unknown"} or case_status == "needs_review" else "No",
            })
        # If one row establishes a field identity from explicit source evidence,
        # propagate confirmation only to rows sharing that exact deterministic field ID.
        # Do not merge IDs or propagate across differing geography/name keys.
        confirmed_field_ids = {
            tag["field_id"] for tag in tags
            if tag["field_id"] and tag["field_id_status"] == "confirmed"
        }
        for tag in tags:
            if tag["field_id"] in confirmed_field_ids and tag["field_id_status"] == "provisional":
                tag["field_id_status"] = "confirmed"
                tag["tagging_confidence"] = "High"
                tag["tagging_rationale"] += (
                    " Field ID confirmation propagated from an independently source-confirmed row "
                    "with the exact same deterministic field_id; no different field IDs were merged."
                )
        return tags

    canonical_tags = build_tags(
        CANONICAL,
        source_matrices["canonical"],
        "canonical",
        source_report_semantics_confirmed=False,
    )

    # The mirror's O1 header says source_report, so never interpret that column
    # as raw_line. Source-copy comparison verifies row-for-row value alignment
    # apart from that header; carry canonical metadata over by row position only.
    mirror_tags = []
    mirror_rows = source_matrices["mirror"][TARGET][1:]
    if len(mirror_rows) != len(canonical_tags):
        raise SystemExit("Canonical/mirror row count differs; refusing row-aligned metadata transfer.")
    for excel_row, (canonical_tag, mirror_row) in enumerate(zip(canonical_tags, mirror_rows), start=2):
        tag = dict(canonical_tag)
        tag["workbook"] = "mirror"
        tag["excel_row"] = excel_row
        tag["source_report"] = mirror_row[14] if len(mirror_row) > 14 else ""
        tag["source_report_group_id"] = ""
        tag["tagging_rationale"] = (
            tag["tagging_rationale"]
            + " Mirror metadata transferred from the canonical row only after verifying source-copy row alignment; "
              "the original source_report header/value was preserved and not interpreted as raw_line."
        )
        mirror_tags.append(tag)

    all_tags = {"canonical": canonical_tags, "mirror": mirror_tags}

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

    audit_fields = ["workbook", "excel_row", "source_table", "source_report", "project_name_normalized", "project_context_normalized", "project_id_status_internal"] + NEW_COLS
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
                ("publication_id", tag["publication_id"], tag["publication_title"],
                 PUBLICATION_EVIDENCE, tag["publication_id_status"]),
                ("project_id", tag["project_id"],
                 tag["project_context_normalized"] + "|" + tag["project_name_normalized"],
                 tag["tagging_rationale"], tag["project_id_status_internal"]),
                ("case_id", tag["case_id"], "exact-normalized-raw_line",
                 "Exact normalized raw_line text from canonical source copy.", tag["case_id_status"]),
                ("field_id", tag["field_id"], tag["field_name_normalized"],
                 tag["tagging_rationale"], tag["field_id_status"]),
                ("source_report_group_id", tag["source_report_group_id"], source_norm(tag["source_report"]),
                 "Only assigned when source_report semantics are confirmed; currently withheld for the mirror.", "needs_review"),
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
            "distinct_publication_ids": len({tag["publication_id"] for tag in tags if tag["publication_id"]}),
            "publication_id_status_counts": dict(Counter(tag["publication_id_status"] for tag in tags)),
            "distinct_project_ids": len({tag["project_id"] for tag in tags if tag["project_id"]}),
            "project_id_status_counts": dict(Counter(tag["project_id_status_internal"] for tag in tags)),
            "table_e_rows": sum(tag["source_table"] == "Table E" for tag in tags),
            "ambiguous_source_fragment_rows": sum(tag["source_table"] == "Ambiguous source fragment" for tag in tags),
            "table_e_rows_with_project_id": sum(tag["source_table"] == "Table E" and bool(tag["project_id"]) for tag in tags),
            "table_e_rows_without_project_id": sum(tag["source_table"] == "Table E" and not tag["project_id"] for tag in tags),
            "table_e_rows_without_field_id": sum(tag["source_table"] == "Table E" and not tag["field_id"] for tag in tags),
            "field_id_status_counts": dict(Counter(tag["field_id_status"] for tag in tags)),
            "field_rows_unknown": sum(tag["field_id_status"] == "unknown" for tag in tags),
            "field_rows_needing_review": sum(tag["field_id_status"] == "needs_review" for tag in tags),
            "field_rows_missing_outside_table_e": sum(tag["source_table"] != "Table E" and not tag["field_id"] for tag in tags),
            "case_rows_needing_review": sum(tag["case_id_status"] == "needs_review" for tag in tags),
        }

    summary = {
        "source_copy_comparison": comparison,
        "per_workbook": summaries,
        "verification": verification,
        "rows_tagged_total_across_copies": sum(len(tags) for tags in all_tags.values()),
        "notes": [
            "The two workbook copies retain their own original column names and values.",
            "Canonical raw_line is the evidence source for case and field tagging; the mirror's metadata is transferred only by verified row alignment.",
            "The mirror's source_report header and cell values are preserved and never interpreted as raw_line; source_report_group_id remains blank.",
            "All provenance IDs are grouping/audit metadata, not model features.",
            "Publication identity is confirmed against the official Oil & Gas Journal 2014 worldwide EOR survey PDF, with a stable publication_id and source URL recorded in tagging_rationale.",
            "Twenty-one previously unresolved rows were reviewed against the original PDF: eight have source-confirmed field identities; the remaining rows are project/pay-zone text or ambiguous fragments and are not forced into field_id.",
            "Table E rows are identified from source-text context, not Excel row position. Its source schema separates Project and Field; where the Field cell is blank, project IDs are recorded separately and field_id remains blank. Ambiguous fragments without unique project context are left without case_id as well.",
            "Field IDs extracted from explicit operator-to-field spans, manually reviewed rules, or source-document overrides are marked confirmed; standalone candidates without enough source context remain provisional.",
            "Only narrow source-supported field aliases are canonicalized; same-name fields with different geography remain separate.",
            "Salt Creek remains split because source rows explicitly identify different Texas/Kent/Canyon and Wyoming/Natrona/Wall Creek contexts.",
            "Any field candidate not established by source evidence remains blank and needs review.",
            "Project IDs are assigned only from the source Table E Project column or unique source-backed fragments; no project is inferred from numeric features or publication identity alone.",
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
