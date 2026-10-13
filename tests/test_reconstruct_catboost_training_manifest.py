"""Regression tests for exact historical OGJ2014 record-ID reconstruction."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from reconstruct_catboost_training_manifest import make_record_ids  # noqa: E402


def test_record_ids_match_provenance_builder_delimiter_and_duplicate_suffix():
    row = ["Brazil", "Petrobras", "Steam", "Field A", "2001"]
    # The historical provenance builder hashes the literal four-character
    # sequence \\x1f between cells, not the ASCII unit-separator byte.
    content = r"\\x1f".join(str(value) for value in row)
    key = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]

    ids = make_record_ids([["header"] * 15, row, row])

    assert ids == [f"REC-{key}-01", f"REC-{key}-02"]
