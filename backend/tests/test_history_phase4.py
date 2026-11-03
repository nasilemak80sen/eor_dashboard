from __future__ import annotations
import sqlite3
from app.history import HistoryRepository

def test_history_health_reports_schema_and_count(tmp_path):
    db=tmp_path/"history.db"
    con=sqlite3.connect(db)
    con.execute("""CREATE TABLE screening_runs (
      id INTEGER PRIMARY KEY, timestamp TEXT, formation TEXT, status TEXT,
      recommended_technique TEXT, recommendation_status TEXT, recommendation_score REAL,
      recommendation_mode TEXT, input_payload TEXT, rule_trace TEXT, model_version TEXT
    )""")
    con.execute("INSERT INTO screening_runs VALUES (1,'2026-01-01','Sandstone','completed','Polymer','PASS',70,'HYBRID','{\"api\":35}','{\"gate\":\"PASS\"}','catboost-v1')")
    con.commit(); con.close()
    repo=HistoryRepository(db)
    assert repo.health()=={"configured":True,"readable":True,"schema_valid":True,"record_count":1}
    row=repo.get(1)
    assert row["input_payload"]=={"api":35}
    assert row["rule_trace"]=={"gate":"PASS"}
    assert row["model_version"]=="catboost-v1"

def test_history_remains_unconfigured_without_explicit_path():
    assert HistoryRepository(None).health()["configured"] is False
