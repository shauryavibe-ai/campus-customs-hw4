"""Accounts (users table) and login sessions (sessions table)."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import db
from security import hash_password, needs_rehash, verify_password, burn_equal_time

SESSION_DAYS = 7
PUBLIC_USER_FIELDS = "id, first_name, last_name, name, email, created_at"


class EmailTaken(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(ts: datetime) -> str:
    # Same "YYYY-MM-DD HH:MM:SS" UTC format SQLite's datetime('now') uses in the users table.
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def _token_hash(token: str) -> str:
    # Only a hash of the session token is stored, so a leaked database can't be used to log in.
    return hashlib.sha256(token.encode()).hexdigest()


def _ensure_sessions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )"""
    )


def _public(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def create_user(first_name: str, last_name: str, email: str, password: str) -> dict:
    password_hash = hash_password(password)
    try:
        with db.connect(write=True) as conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
                (f"{first_name} {last_name}", email, password_hash, first_name, last_name),
            )
            row = conn.execute(f"SELECT {PUBLIC_USER_FIELDS} FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError as exc:  # UNIQUE(email)
        raise EmailTaken(email) from exc
    return _public(row)


def authenticate(email: str, password: str) -> dict | None:
    with db.connect(write=True) as conn:
        row = conn.execute(
            f"SELECT {PUBLIC_USER_FIELDS}, password_hash FROM users WHERE lower(email) = ?", (email,)
        ).fetchone()
        if row is None:
            burn_equal_time(password)
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        if needs_rehash(row["password_hash"]):
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), row["id"]))
    user = dict(row)
    user.pop("password_hash")
    return user


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    with db.connect(write=True) as conn:
        _ensure_sessions_table(conn)
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_fmt(now),))
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (_token_hash(token), user_id, _fmt(now), _fmt(now + timedelta(days=SESSION_DAYS))),
        )
    return token


def user_for_session(token: str | None) -> dict | None:
    if not token:
        return None
    with db.connect(write=True) as conn:
        _ensure_sessions_table(conn)
        row = conn.execute(
            f"""SELECT {", ".join(f"u.{f.strip()}" for f in PUBLIC_USER_FIELDS.split(","))}
                FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ?""",
            (_token_hash(token), _fmt(_now())),
        ).fetchone()
    return _public(row)


def delete_session(token: str | None) -> None:
    if not token:
        return
    with db.connect(write=True) as conn:
        _ensure_sessions_table(conn)
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
