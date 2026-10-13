"""Tests for conservative OGJ2014 field/project separation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_ogj2014_provenance as provenance  # noqa: E402


def test_explicit_field_names_are_parsed_from_tables_a_to_d():
    examples = {
        "Kinder Morgan Goldsmith-Landreth TX 21,205 637 389 San Andres Carbonate": "Goldsmith-Landreth",
        "Resources Aneth Unit Utah San Juan 10/98 11,000 126 118 Desert Creek LS": "Aneth Unit",
        "Swan Hills LS 8-18 3-270 9,150 41 0.3 230 WF": "Swan Hills",
        "Crockett 7/97 1,200 2 2": "Crockett",
        "Superior S 23": None,
        "Carmopolis S/Congl. 22 200 2,460": None,
        "L’Enfer S 33 250 1,000": None,
    }
    for raw_line, expected in examples.items():
        field, reason, _ = provenance.parse_field(raw_line)
        assert field == expected, (raw_line, field, reason)


def test_source_document_resolves_previously_ambiguous_field_names():
    examples = {
        "Creek 1 Member SS 17 25 1,750 39 0.6 105": "Salt Creek Southern Unit",
        "Creek 2 Member SS 18 30 2,200 39 0.6 112": "Salt Creek Southern Unit",
        "Residual Oil Zone Dolo. 10 5 5,700 32 1.0 105": "Hanford (San Andres)",
        "(Enhanced cyclic steam) Alta. 2002 32 20 8 Clearwater US 32": "Cold Lake",
        "Apache Canada Zama-Keg River Alta. 6/04 3,840 12 12": "Zama-Keg River",
        "BP Prudhoe Bay Alas. 1977 50,000 330 32": "Prudhoe Bay",
        "BP Alaska Milne Point Alas. 3/95 20,000 84 52": "Alaska Milne Point",
        "Chevron San Ardo Calif. Monterey 7/87 700 7 3": "San Ardo",
        "Chevron West Coalinga Calif. Fresno 5/73 780 194 180": "West Coalinga",
        "ExxonMobil Hawkins Tex. Wood 8/87 2,800 27 6": "Hawkins",
        "Occidental Elk Hills Calif. Kern 2005 10,000 800 60": "Elk Hills",
        "Chaparral Energy North Burbank Okla. Osage 12/07 480 19 9": "North Burbank",
        "Occidental Midland Farms Unit Tex. Andrews 3/10 40 6 1": "Midland Farms Unit",
        "Shell Canada Peace River Alta. 1979 4,900 97 109": "Peace River",
    }
    for raw_line, expected in examples.items():
        field, reason, _ = provenance.parse_field(raw_line)
        assert field == expected, (raw_line, field, reason)
        assert reason.startswith("source_verified:")


def test_table_e_projects_are_not_misclassified_as_fields():
    examples = {
        "11/14 12/11 150 12 2 Valanginian S 30 300-15,000": "Emlichheim, Block 11/14",
        "2 immiscible Area 2102 6/76 58 6 2 Forest Sands S 32": "Area 2102",
        "(S ORS 01) US 30 400-1,200 2,600": "Orocual",
        "MFB-53) US 31.9 6,600 2,650 9.3 376 131": "Bare (F.O.)",
        "MFB-23) US 28.6 5,000 3,050 9.2 351 136": "Bare (F.O.)",
        "MM-407) S 30 1,500 3,820 11 270 159": "Melones",
        "MM-412) S 28 792 3,515 14.5 260 154": "Melones",
        "Superior S 23": "Bachaquero Lago",
        "Parrylands New Horizon Steam Block E 7/01 744 6 Forest Sands S": "Block E",
        "Batman TPAO CO2 immiscible Bati Raman 3/86 12,890 212 69": "Bati Raman",
        "Maturin, Campo Orocual PDVSA E&P Steam Orocual 5/00 22,776 35 12": "Orocual",
        "Bahia Petrobras CO2 miscible Miranga 12/09 27 10 Catu-1 S 20": "Miranga",
        "Bentheim Wintershall Holding AG Steam Emlichheim, Block 1 7/07 55 8 1 Valanginian": "Emlichheim, Block 1",
        "Lower Saxony, Grafschaft Bentheim Wintershall Holding AG Steam Emlichheim, Block 11/14 12/11 150 12": "Emlichheim, Block 11/14",
        "Forest Reserve Petrotrin CO2 immiscible EOR 34-Cyclic 84 NA 11": "EOR 34-Cyclic",
        "Shetlands Islands BP Hydrocarbon miscible Magnus 10/02 10,700 16 4": "Magnus",
        "Drenthe Nederlandse Aardolie Maatschappij (NAM) Steam Schoonebeek 1970 800": "Schoonebeek",
        "water Furrial 8/98 36,769 102 43 Naricual S": "Furrial",
        "Anzoategui PDVSA E&P Steam Arecuna (F.O) 12/83 1,544 15 15": "Arecuna (F.O.)",
        "Anzoategui PDVSA E&P Steam Bare (F.O). 3/87 8,066 66 65": "Bare (F.O.)",
    }
    for raw_line, expected in examples.items():
        project, context, reason = provenance.parse_project(raw_line)
        assert project == expected, (raw_line, project, context, reason)
        assert context
        assert reason.startswith(("source_verified:", "source_project_span"))


def test_table_e_field_parser_uses_explicit_pdf_field_column():
    examples = {
        "Bahia Petrobras CO2 immiscible Buracica 1991 1,670 7 Sergi S 22": "Buracica",
        "Bahia Petrobras CO2 miscible Rio Pojuca 1999 1 Agua Grande S": "Rio Pojuca",
        "Brazil Petrobras Microbial Carmopolis 6/02 45 10 Carmopolis S/Congl. 17": "Carmopolis",
        "Espirito Santo Petrobras Steam Fazenda Alegre 2001 1,255 59 Urucutuca S 27": "Fazenda Alegre",
        "Bentheim Wintershall Holding AG Steam Emlichheim, Block 1 7/07 55 8 1 Valanginian US 30": "Emlichheim, Block 1",
        "miscible Magnus 10/02 10,700 16 4 150 S 20": "Magnus",
        "Parrylands New Horizon Steam Block E 7/01 744 6 Forest Sands S 36": "Block E",
        "Maturin, Campo Mulata PDVSA E&P HC miscible Carito Central 12/96 12,000 45 10 Naricual S": "Carito Central",
    }
    for raw_line, expected in examples.items():
        field, context, reason = provenance.parse_table_e_field(raw_line)
        assert field == expected, (raw_line, field, context, reason)
        assert context
        assert reason.startswith(("source_verified:", "source_project_span"))


def test_salt_creek_same_name_is_not_merged_across_operator_and_geography():
    anadarko, anadarko_reason, anadarko_geo = provenance.parse_field(
        "Anadarko Salt Creek Wyo. Natrona 10/05 5 4 1 Wall Creek 1 (Frontier) S 17"
    )
    occidental, occidental_reason, occidental_geo = provenance.parse_field(
        "Occidental Salt Creek Tex. Kent 10/93 12,000 168 145 Canyon LS 20"
    )
    assert anadarko == occidental == "Salt Creek"
    assert anadarko_geo == "Wyo."
    assert occidental_geo == "Tex."
    anadarko_id = provenance.hid("FIELD", provenance.nk(anadarko) + "|" + provenance.nk(anadarko_geo))
    occidental_id = provenance.hid("FIELD", provenance.nk(occidental) + "|" + provenance.nk(occidental_geo))
    assert anadarko_id != occidental_id
    assert anadarko_reason.startswith("organization_field_span")
    assert occidental_reason.startswith("organization_field_span")


def test_estreito_rows_share_source_confirmed_canonical_field_without_row_merge():
    generic = "Brazil Petrobras Steam Estreito 12/09 176 48 Acu S 25"
    explicit_rn = "Rio Grande do Norte (RN) Petrobras Steam Estreito 1984 700 Acu S 25"
    a = provenance.parse_table_e_field(generic)
    b = provenance.parse_table_e_field(explicit_rn)
    assert a[0] == b[0] == "Estreito"
    assert a[1] == b[1] == "Rio Grande do Norte, Brazil"
    assert a[2].startswith("source_verified:")
    assert b[2].startswith("source_verified:")
    assert provenance.hid("FIELD", provenance.nk(a[0]) + "|" + provenance.nk(a[1])) == provenance.hid(
        "FIELD", provenance.nk(b[0]) + "|" + provenance.nk(b[1])
    )
    assert provenance.table_e_identity_hold_reason(generic) is None
    assert provenance.table_e_identity_hold_reason(explicit_rn) is None


def test_eight_partial_field_fragments_match_only_reviewed_source_rows():
    examples = {
        "Carmopolis S/Congl. 22 200 2,460 21 500 122 NC 3,860 3,860 Succ. Yes FW": ("Carmopolis", "Sergipe, Brazil"),
        "L’Enfer S 33 250 1,000 21.6 18 103 S 73 45 NC 280 280 Succ. Yes Exp. UL": ("Bennett Village", "Trinidad and Tobago"),
        "L’Enfer S 29 250 2,800 19.2 120 100 S 72 51 NC 330 330 Succ. Yes Exp. UL": ("Antilles Quarry", "Trinidad and Tobago"),
        "L’Enfer S 33 260 1,200 15 500 100 C 71 35 NC 1,132 1,132 Succ. Yes Exp. LW": ("North Palo Seco", "Trinidad and Tobago"),
    }
    for raw, expected in examples.items():
        override = provenance.reviewed_partial_field_override(raw)
        assert override is not None
        assert override[:2] == expected
        assert override[2].startswith("OGJ 2014 Table E")
    assert provenance.reviewed_partial_field_override("L’Enfer S 40 999 999") is None


def test_table_e_source_detection_uses_source_context_not_row_position():
    assert provenance.is_table_e_source_row(
        "Bahia Petrobras CO2 miscible Miranga 12/09 27 10 Catu-1 S 20"
    )
    assert provenance.is_table_e_source_row("MFB-53) US 31.9 6,600 2,650")
    assert provenance.is_ambiguous_source_fragment("Carmopolis S/Congl. 22 200 2,460")
    assert provenance.is_ambiguous_source_fragment("L’Enfer S 33 250 1,000")
    assert not provenance.is_table_e_source_row(
        "Shell Canada Peace River Alta. 1979 4,900 97 109 Bluesky S"
    )
    assert not provenance.is_table_e_source_row(
        "CNRL Pelican Lake Alta. 2006 187,000 1,000 200 Wabiskaw S"
    )


def test_ambiguous_table_e_pay_zones_do_not_get_project_or_field_ids():
    for raw_line in [
        "Carmopolis S/Congl. 22 200 2,460 21 500 122",
        "L’Enfer S 33 250 1,000 21.6 18 103",
    ]:
        project, _, project_reason = provenance.parse_project(raw_line)
        field, field_reason, _ = provenance.parse_field(raw_line)
        assert project is None, (raw_line, project, project_reason)
        assert field is None, (raw_line, field, field_reason)


def test_evidence_backed_field_aliases_remain_narrow():
    swan, swan_reason, swan_geo = provenance.parse_field(
        "Swan Hills LS 8-18 3-270 9,150 41 0.3 230 WF"
    )
    swan_report, _, report_geo = provenance.parse_field(
        "Devon Canada Swan Hills Alta. 10/04 5 1 Beaverhill Lake LS"
    )
    assert swan == swan_report == "Swan Hills"
    assert swan_geo == report_geo == "Alta."
    assert "corroborating source rows" in swan_reason

    arecuna_dot, context_dot, _ = provenance.parse_project(
        "Anzoategui PDVSA E&P Steam Arecuna (F.O.) 2/85 1,668 5 5 US"
    )
    arecuna_no_dot, context_no_dot, _ = provenance.parse_project(
        "Anzoategui PDVSA E&P Steam Arecuna (F.O) 12/83 1,544 15 15 US"
    )
    assert arecuna_dot == arecuna_no_dot == "Arecuna (F.O.)"
    assert context_dot == context_no_dot

    bare_dot, bare_context_dot, _ = provenance.parse_project(
        "Anzoategui PDVSA E&P Steam Bare (F.O.) 3/85 16,452 55 48 US"
    )
    bare_no_dot, bare_context_no_dot, _ = provenance.parse_project(
        "Anzoategui PDVSA E&P Steam Bare (F.O). 3/87 8,066 66 65 US"
    )
    assert bare_dot == bare_no_dot == "Bare (F.O.)"
    assert bare_context_dot == bare_context_no_dot
