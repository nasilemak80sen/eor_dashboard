from __future__ import annotations

import sqlite3
from pathlib import Path

from auth.local_auth import (
    authenticate_local_user,
    create_local_user,
    initialize_auth_database,
    list_local_users,
)


def test_local_poc_account_uses_salted_hash_not_plaintext(tmp_path: Path) -> None:
    db_path = tmp_path / "poc-auth.sqlite3"
    ok, message = create_local_user("reservoir.demo", "safe-demo-password-1", db_path)
    assert ok, message
    assert authenticate_local_user("reservoir.demo", "safe-demo-password-1", db_path)
    assert not authenticate_local_user("reservoir.demo", "wrong-password", db_path)
    assert not authenticate_local_user("unknown.demo", "safe-demo-password-1", db_path)
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT salt_hex, password_hash_hex, iterations FROM poc_users WHERE username = ?",
            ("reservoir.demo",),
        ).fetchone()
    assert row is not None
    assert row[0] and row[1] and row[0] != row[1]
    assert int(row[2]) >= 100_000
    assert "safe-demo-password-1" not in repr(row)


def test_local_poc_usernames_are_unique_case_insensitively(tmp_path: Path) -> None:
    db_path = tmp_path / "poc-auth.sqlite3"
    ok, message = create_local_user("Nabiel.Demo", "safe-demo-password-1", db_path)
    assert ok, message
    duplicate, message = create_local_user("nabiel.demo", "safe-demo-password-2", db_path)
    assert not duplicate
    assert "already exists" in message
    assert list_local_users(db_path) == ["Nabiel.Demo"]


def test_local_poc_validates_username_and_password(tmp_path: Path) -> None:
    db_path = tmp_path / "poc-auth.sqlite3"
    ok, message = create_local_user("x", "short", db_path)
    assert not ok
    assert "3–64 characters" in message
    ok, message = create_local_user("demo.user", "short", db_path)
    assert not ok
    assert "at least 10 characters" in message
    assert list_local_users(db_path) == []


def test_initializing_auth_does_not_create_engineering_history_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "poc-auth.sqlite3"
    initialize_auth_database(db_path)
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert tables == {"poc_users", "sqlite_sequence"}
