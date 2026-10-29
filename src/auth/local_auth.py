"""SQLite-backed local authentication for the EOR Atlas UI/UX proof of concept.

This module is deliberately local-only. It is not an enterprise identity provider
and must not be treated as production authentication.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PBKDF2_ITERATIONS = 310_000
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{3,64}$")


def auth_database_path() -> Path:
    """Return the dedicated POC-auth DB path, never the engineering history DB."""
    configured = os.environ.get("EOR_POC_AUTH_DB", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    # src/auth/local_auth.py -> repository root
    project_root = Path(__file__).resolve().parents[2]
    return project_root / ".local" / "eor_atlas_poc_auth.sqlite3"


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path).expanduser().resolve() if db_path is not None else auth_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_auth_database(db_path: str | Path | None = None) -> None:
    """Create only the local authentication schema."""
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS poc_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                salt_hex TEXT NOT NULL,
                password_hash_hex TEXT NOT NULL,
                iterations INTEGER NOT NULL,
                created_at_utc TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_poc_users_username ON poc_users(username)"
        )
    path = Path(db_path).expanduser().resolve() if db_path is not None else auth_database_path()
    try:
        # Best-effort restriction on platforms that support POSIX file modes.
        if os.name == "posix" and path.exists():
            path.chmod(0o600)
    except OSError:
        pass


def list_local_users(db_path: str | Path | None = None) -> list[str]:
    initialize_auth_database(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT username FROM poc_users ORDER BY username COLLATE NOCASE"
        ).fetchall()
    return [str(row["username"]) for row in rows]


def create_local_user(
    username: str,
    password: str,
    db_path: str | Path | None = None,
) -> tuple[bool, str]:
    """Create a local account using a salted PBKDF2 password hash."""
    username = (username or "").strip()
    password = password or ""
    if not USERNAME_PATTERN.fullmatch(username):
        return False, "Use 3–64 characters: letters, numbers, dot, underscore or hyphen."
    if len(password) < 10:
        return False, "Use a password with at least 10 characters."
    if len(password) > 1024:
        return False, "Password is too long."

    salt = secrets.token_bytes(32)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    created_at = datetime.now(timezone.utc).isoformat()
    initialize_auth_database(db_path)
    try:
        with _connect(db_path) as connection:
            connection.execute(
                """
                INSERT INTO poc_users
                    (username, salt_hex, password_hash_hex, iterations, created_at_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    username,
                    salt.hex(),
                    password_hash.hex(),
                    PBKDF2_ITERATIONS,
                    created_at,
                ),
            )
    except sqlite3.IntegrityError:
        return False, "That username already exists."
    except sqlite3.Error:
        return False, "The local POC account could not be created."
    return True, "Local POC account created."


def authenticate_local_user(
    username: str,
    password: str,
    db_path: str | Path | None = None,
) -> bool:
    """Verify credentials without returning password hashes or account data."""
    username = (username or "").strip()
    password = password or ""
    if not username or not password or len(password) > 1024:
        return False
    initialize_auth_database(db_path)
    try:
        with _connect(db_path) as connection:
            row = connection.execute(
                """
                SELECT salt_hex, password_hash_hex, iterations
                FROM poc_users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
    except sqlite3.Error:
        return False
    if row is None:
        # Perform a small fixed amount of work for unknown usernames.
        hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"eor-atlas-poc", 10_000)
        return False
    try:
        expected = bytes.fromhex(str(row["password_hash_hex"]))
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(str(row["salt_hex"])),
            int(row["iterations"]),
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def render_auth_gate() -> str | None:
    """Render first-user setup or local login. Returns a username on success."""
    import streamlit as st

    users = list_local_users()
    st.markdown(
        """
        <div class="poc-login-hero">
          <div class="poc-login-mark">EA</div>
          <p class="poc-login-kicker">EOR ATLAS · UI/UX PROOF OF CONCEPT</p>
          <h1>Reservoir decisions, clearer workflows.</h1>
          <p>Explore the redesigned workspace using local-only demo access.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "Local POC authentication only. Accounts are stored in a separate SQLite file on this machine; "
        "this is not corporate SSO and is not approved for production."
    )

    if not users:
        st.subheader("Set up your local POC account")
        st.caption("Create the first account to open the prototype. No default password is installed.")
        with st.form("poc_first_account", clear_on_submit=False):
            username = st.text_input("Username", max_chars=64, placeholder="e.g. reservoir.engineer")
            password = st.text_input("Password", type="password", max_chars=1024)
            confirmation = st.text_input("Confirm password", type="password", max_chars=1024)
            submitted = st.form_submit_button("Create local account", type="primary", use_container_width=True)
        if submitted:
            if password != confirmation:
                st.error("The passwords do not match.")
            else:
                ok, message = create_local_user(username, password)
                if ok:
                    st.session_state["local_poc_username"] = username.strip()
                    st.rerun()
                st.error(message)
        return None

    sign_in_tab, create_tab = st.tabs(["Sign in", "Create account"])
    with sign_in_tab:
        with st.form("poc_sign_in", clear_on_submit=False):
            username = st.text_input("Username", max_chars=64, key="poc_login_username")
            password = st.text_input("Password", type="password", max_chars=1024, key="poc_login_password")
            submitted = st.form_submit_button("Sign in to the POC", type="primary", use_container_width=True)
        if submitted:
            if authenticate_local_user(username, password):
                st.session_state["local_poc_username"] = username.strip()
                st.rerun()
            st.error("Username or password is incorrect.")

    with create_tab:
        st.caption("New users are local POC accounts on this machine, not corporate identities.")
        with st.form("poc_create_account", clear_on_submit=False):
            new_username = st.text_input("New username", max_chars=64, key="poc_new_username")
            new_password = st.text_input("New password", type="password", max_chars=1024, key="poc_new_password")
            confirm = st.text_input("Confirm new password", type="password", max_chars=1024, key="poc_confirm_password")
            create_submitted = st.form_submit_button("Create account", use_container_width=True)
        if create_submitted:
            if new_password != confirm:
                st.error("The passwords do not match.")
            else:
                ok, message = create_local_user(new_username, new_password)
                if ok:
                    st.session_state["local_poc_username"] = new_username.strip()
                    st.rerun()
                st.error(message)
    return None


def logout_local_user() -> None:
    """Clear Streamlit's session identity for this local POC."""
    import streamlit as st

    st.session_state.pop("local_poc_username", None)
    st.session_state.pop("poc_user", None)
    st.rerun()
