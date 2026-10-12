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


def test_ambiguous_formation_and_well_identifiers_remain_unresolved():
    examples = [
        "Creek 1 Member SS 17 25 1,750 39 0.6 105",
        "Residual Oil Zone Dolo. 10 5 5,700 32 1.0 105",
        "MFB-53) US 31.9 6,600 2,650 9.3 376 131",
        "MM-407) S 30 1,500 3,820 11 270 159",
        "11/14 12/11 150 12 2 Valanginian S 30 300-15,000",
    ]
    for raw_line in examples:
        field, reason, _ = provenance.parse_field(raw_line)
        assert field is None, (raw_line, field, reason)
