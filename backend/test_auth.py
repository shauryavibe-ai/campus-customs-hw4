import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

import db
import main
import security

GOOD = {"first_name": "Grace", "last_name": "Hopper", "email": "Grace.Hopper@Yale.edu", "password": "Compiler1952"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Each test gets its own copy of the database and a fresh login throttle."""
    test_db = tmp_path / "campus_customs.db"
    shutil.copy(db.DB_PATH, test_db)
    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setattr(security, "ITERATIONS", 1_000)  # keep tests fast; production uses 600k
    monkeypatch.setattr(main, "throttle", security.LoginThrottle(max_failures=3))
    with TestClient(main.app) as c:
        yield c


def user_row(email: str) -> sqlite3.Row:
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row


def test_production_settings_are_strong():
    # No client fixture here, so these are the real (unpatched) settings.
    assert security.ITERATIONS >= 600_000
    assert security.SALT_BYTES >= 16


def test_signup_saves_user_with_hashed_password(client):
    res = client.post("/api/auth/signup", json=GOOD)
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "grace.hopper@yale.edu"
    assert body["first_name"] == "Grace" and body["name"] == "Grace Hopper"
    assert "password" not in str(body).lower()

    row = user_row("grace.hopper@yale.edu")
    assert row["first_name"] == "Grace" and row["last_name"] == "Hopper"
    stored = row["password_hash"]
    assert GOOD["password"] not in stored
    algo, iterations, salt, digest = stored.split("$")
    assert algo == "pbkdf2_sha256" and int(iterations) == security.ITERATIONS
    assert len(salt) == 32 and len(digest) == 64


def test_same_password_gets_different_hashes(client):
    a = security.hash_password("SamePass123")
    b = security.hash_password("SamePass123")
    assert a != b  # unique salt per user
    assert security.verify_password("SamePass123", a) and security.verify_password("SamePass123", b)
    assert not security.verify_password("samepass123", a)


def test_signup_logs_in_and_me_works(client):
    client.post("/api/auth/signup", json=GOOD)
    cookie = client.cookies.get(main.SESSION_COOKIE)
    assert cookie
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["first_name"] == "Grace"


def test_session_cookie_is_httponly(client):
    res = client.post("/api/auth/signup", json=GOOD)
    header = res.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header


def test_session_token_not_stored_in_plain_text(client):
    client.post("/api/auth/signup", json=GOOD)
    token = client.cookies.get(main.SESSION_COOKIE)
    conn = sqlite3.connect(db.DB_PATH)
    stored = [r[0] for r in conn.execute("SELECT token_hash FROM sessions")]
    conn.close()
    assert stored and token not in stored


def test_duplicate_email_rejected(client):
    client.post("/api/auth/signup", json=GOOD)
    res = client.post("/api/auth/signup", json={**GOOD, "email": "grace.hopper@yale.edu"})
    assert res.status_code == 409


@pytest.mark.parametrize(
    "password, reason",
    [("short1", "at least"), ("onlyletters", "letter and one number"), ("password123", "too common"),
     ("gracehopper99", "email name")],
)
def test_weak_passwords_rejected(client, password, reason):
    res = client.post("/api/auth/signup", json={**GOOD, "password": password})
    assert res.status_code == 422
    assert reason in res.json()["detail"]


def test_bad_email_rejected(client):
    assert client.post("/api/auth/signup", json={**GOOD, "email": "not-an-email"}).status_code == 422


def test_login_logout_flow(client):
    client.post("/api/auth/signup", json=GOOD)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    res = client.post("/api/auth/login", json={"email": "GRACE.hopper@yale.edu", "password": GOOD["password"]})
    assert res.status_code == 200 and res.json()["last_name"] == "Hopper"
    assert client.get("/api/auth/me").status_code == 200

    old_token = client.cookies.get(main.SESSION_COOKIE)
    client.post("/api/auth/logout")
    # The old token is revoked server-side, not just deleted from the browser.
    client.cookies.set(main.SESSION_COOKIE, old_token)
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_and_unknown_email_look_the_same(client):
    client.post("/api/auth/signup", json=GOOD)
    client.post("/api/auth/logout")
    wrong = client.post("/api/auth/login", json={"email": GOOD["email"], "password": "WrongPass999"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@yale.edu", "password": "WrongPass999"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_repeated_failures_are_throttled(client):
    client.post("/api/auth/signup", json=GOOD)
    client.post("/api/auth/logout")
    for _ in range(3):
        assert client.post("/api/auth/login", json={"email": GOOD["email"], "password": "Nope12345"}).status_code == 401
    blocked = client.post("/api/auth/login", json={"email": GOOD["email"], "password": GOOD["password"]})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_old_hashes_are_upgraded_on_login(client, monkeypatch):
    client.post("/api/auth/signup", json=GOOD)
    client.post("/api/auth/logout")
    monkeypatch.setattr(security, "ITERATIONS", 2_000)  # pretend the policy got stronger
    client.post("/api/auth/login", json={"email": GOOD["email"], "password": GOOD["password"]})
    assert user_row("grace.hopper@yale.edu")["password_hash"].split("$")[1] == "2000"


def test_forged_cookie_rejected(client):
    client.cookies.set(main.SESSION_COOKIE, "made-up-token")
    assert client.get("/api/auth/me").status_code == 401


def test_legacy_seed_hash_format_verifies():
    # Seed users were hashed as pbkdf2_sha256$<salt>$<digest> with 120,000 iterations.
    import hashlib

    digest = hashlib.pbkdf2_hmac("sha256", b"Legacy1234", b"somesalt", 120_000).hex()
    legacy = f"pbkdf2_sha256$somesalt${digest}"
    assert security.verify_password("Legacy1234", legacy)
    assert not security.verify_password("legacy1234", legacy)
    assert security.needs_rehash(legacy)
