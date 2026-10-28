from __future__ import annotations

import sqlite3

import pytest

from app.history import HistoryRepository, HistoryUnavailable


def make_db(path):
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE screening_runs (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            formation TEXT,
            status TEXT,
            recommended_technique TEXT,
            recommendation_status TEXT,
            recommendation_score REAL,
            recommendation_mode TEXT
        )
    """)
    con.execute(
        "INSERT INTO screening_runs VALUES (1, '2026-01-01T00:00:00', 'Sandstone', 'completed', 'Polymer', 'PASS', 70, 'ENGINEERING')"
    )
    con.commit()
    con.close()


def test_history_reads_expected_fields_without_mutating(tmp_path):
    db = tmp_path / "history.db"
    make_db(db)
    before = db.stat().st_size
    repo = HistoryRepository(db)
    assert repo.list(limit=10)[0]["recommended_technique"] == "Polymer"
    assert repo.get(1)["id"] == 1
    assert repo.get(99) is None
    assert db.stat().st_size == before


def test_history_requires_explicit_database_path():
    with pytest.raises(HistoryUnavailable, match="not configured"):
        HistoryRepository().list()


def test_history_rejects_incompatible_schema(tmp_path):
    db = tmp_path / "wrong.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE screening_runs (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()
    with pytest.raises(HistoryUnavailable, match="schema"):
        HistoryRepository(db).list()
