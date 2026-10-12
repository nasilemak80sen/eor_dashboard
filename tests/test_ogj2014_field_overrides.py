"""Tests for conservative, evidence-based OGJ2014 field-name tagging."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_ogj2014_provenance as provenance  # noqa: E402


def test_reviewed_field_prefixes_resolve_only_explicit_names():
    examples = {
        "Kinder Morgan Goldsmith-Landreth TX 21,205 637 389 San Andres Carbonate": "Goldsmith-Landreth",
        "Resources Aneth Unit Utah San Juan 10/98 11,000 126 118 Desert Creek LS": "Aneth Unit",
        "Swan Hills LS 8-18 3-270 9,150 41 0.3 230 WF": "Swan Hills",
        "Carmopolis S/Congl. 22 200 2,460 21 500 122 NC": "Carmopolis",
        "miscible Magnus 10/02 10,700 16 4 150 S": "Magnus",
        "Parrylands New Horizon Steam Block E 7/01 744 6 Forest Sands S": "Parrylands",
        "Forest Reserve Petrotrin CO2 immiscible EOR 34-Cyclic 84 NA 11": "Forest Reserve",
        "L’Enfer S 33 250 1,000 21.6 18 103": "L’Enfer",
        "Batman TPAO CO2 immiscible Bati Raman 3/86 12,890 212 69": "Bati Raman",
    }
    for raw_line, expected in examples.items():
        field, reason, _ = provenance.parse_field(raw_line)
        assert field == expected
        assert reason.startswith("reviewed_prefix:")


def test_source_document_resolves_previously_ambiguous_field_names():
    examples = {
        "Creek 1 Member SS 17 25 1,750 39 0.6 105": "Salt Creek Southern Unit",
        "Creek 2 Member SS 18 30 2,200 39 0.6 112": "Salt Creek Southern Unit",
        "Residual Oil Zone Dolo. 10 5 5,700 32 1.0 105": "Hanford (San Andres)",
        "(Enhanced cyclic steam) Alta. 2002 32 20 8 Clearwater US 32": "Cold Lake",
        "11/14 12/11 150 12 2 Valanginian S 30 300-15,000": "Emlichheim, Block 11/14",
        "2 immiscible Area 2102 6/76 58 6 2 Forest Sands S 32": "Area 2102",
        "(S ORS 01) US 30 400-1,200 2,600": "Orocual",
        "MFB-53) US 31.9 6,600 2,650 9.3 376 131": "Bare (F.O.)",
        "MFB-23) US 28.6 5,000 3,050 9.2 351 136": "Bare (F.O.)",
        "MM-407) S 30 1,500 3,820 11 270 159": "Melones",
        "MM-412) S 28 792 3,515 14.5 260 154": "Melones",
    }
    for raw_line, expected in examples.items():
        field, reason, _ = provenance.parse_field(raw_line)
        assert field == expected, (raw_line, field, reason)
        assert reason.startswith("source_verified:")


def test_unknown_member_and_well_codes_stay_unresolved():
    examples = [
        "Creek 3 Member SS 17 25 1,750 39 0.6 105",
        "MFB-999) US 31.9 6,600 2,650 9.3 376 131",
        "Unknown Member SS 17 25 1,750 39 0.6 105",
    ]
    for raw_line in examples:
        field, reason, _ = provenance.parse_field(raw_line)
        assert field is None, (raw_line, field, reason)


def test_evidence_backed_aliases_share_canonical_field_identity():
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

    bare_dot, _, bare_geo_dot = provenance.parse_field(
        "Anzoategui PDVSA E&P Steam Bare (F.O.) 3/85 16,452 55 48 US"
    )
    bare_no_dot, _, bare_geo_no_dot = provenance.parse_field(
        "Anzoategui PDVSA E&P Steam Bare (F.O). 3/87 8,066 66 65 US"
    )
    assert bare_dot == bare_no_dot == "Bare (F.O.)"
    assert bare_geo_dot == bare_geo_no_dot
