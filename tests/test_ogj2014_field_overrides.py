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


def test_table_e_source_detection_uses_source_context_not_row_position():
    assert provenance.is_table_e_source_row(
        "Bahia Petrobras CO2 miscible Miranga 12/09 27 10 Catu-1 S 20"
    )
    assert provenance.is_table_e_source_row("MFB-53) US 31.9 6,600 2,650")
    assert provenance.is_table_e_source_row("Carmopolis S/Congl. 22 200 2,460")
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

    arecuna_dot, _, geo_dot = provenance.parse_field(
        "Anzoategui PDVSA E&P Steam Arecuna (F.O.) 2/85 1,668 5 5 US"
    )
    arecuna_no_dot, _, geo_no_dot = provenance.parse_field(
        "Anzoategui PDVSA E&P Steam Arecuna (F.O) 12/83 1,544 15 15 US"
    )
    assert arecuna_dot == arecuna_no_dot == "Arecuna (F.O.)"
    assert geo_dot == geo_no_dot
