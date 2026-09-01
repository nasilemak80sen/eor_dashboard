import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for candidate in (PROJECT_ROOT, PROJECT_ROOT / "EORWEBDEV"):
    candidate = candidate.resolve()
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

try:
    from data.database import DatabaseManager
except ModuleNotFoundError:
    from EORWEBDEV.data.database import DatabaseManager


def test_init_db_adds_missing_screening_run_columns(tmp_path):
    db_path = tmp_path / "eor_test.db"

    con = sqlite3.connect(db_path)
    con.execute(
        """
        CREATE TABLE screening_runs (
            id INTEGER PRIMARY KEY,
            formation TEXT NOT NULL,
            timestamp TEXT,
            depth_ft REAL NOT NULL,
            porosity_pct REAL NOT NULL,
            perm_md REAL NOT NULL,
            api REAL NOT NULL,
            visc_cp REAL NOT NULL,
            so_pct REAL NOT NULL
        )
        """
    )
    con.commit()
    con.close()

    DatabaseManager.init_db(db_path)

    con = sqlite3.connect(db_path)
    columns = [row[1] for row in con.execute("PRAGMA table_info(screening_runs)").fetchall()]
    con.close()

    assert "input_payload" in columns
    assert "rule_trace" in columns
    assert "assumptions" in columns
    assert "evidence_summary" in columns

