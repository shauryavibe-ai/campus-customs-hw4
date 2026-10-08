"""Password hashing and login throttling.

Passwords are never stored. Each one is run through PBKDF2-HMAC-SHA256 with a
unique random salt and 600,000 iterations (OWASP's current recommendation), and
only the result is saved, in the format:

    pbkdf2_sha256$<iterations>$<salt>$<hex digest>

Checking a password re-derives the digest with the stored salt/iterations and
compares in constant time, so the original password can't be recovered from the
database and response timing doesn't leak how close a guess was.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16

MIN_PASSWORD = 8
MAX_PASSWORD = 128  # caps hashing cost so huge inputs can't be used to slow the server

COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "iloveyou1", "letmein1", "welcome1", "abc12345", "yale1701", "bulldog1",
    "boolaboola1", "11111111", "00000000", "passw0rd",
}

# Legacy hashes (the three seed users) were stored as pbkdf2_sha256$<salt>$<digest>
# without an iteration count; they were made with 120,000 iterations (verified against the
# Test User's known password). They're upgraded to the current format on next login.
LEGACY_ITERATIONS = int(os.getenv("LEGACY_PBKDF2_ITERATIONS", "120000"))


def _derive(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    return f"{ALGORITHM}${ITERATIONS}${salt}${_derive(password, salt, ITERATIONS)}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == ALGORITHM and parts[1].isdigit():
        _, iterations, salt, digest = parts
        iterations = int(iterations)
    elif len(parts) == 3 and parts[0] == ALGORITHM and LEGACY_ITERATIONS:
        _, salt, digest = parts
        iterations = LEGACY_ITERATIONS
    else:
        return False
    return hmac.compare_digest(_derive(password, salt, iterations), digest)


def needs_rehash(stored: str) -> bool:
    """True for hashes made with older/weaker settings, so they can be upgraded at login."""
    parts = stored.split("$")
    return not (len(parts) == 4 and parts[1].isdigit() and int(parts[1]) >= ITERATIONS)


_dummy_hash: str | None = None


def burn_equal_time(password: str) -> None:
    """Spend the same time as a real check when the email doesn't exist (hides which emails are registered)."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_hex(8))
    verify_password(password, _dummy_hash)


def password_problem(password: str, email: str = "") -> str | None:
    """Human-readable reason a new password is too weak, or None if it's acceptable."""
    if len(password) < MIN_PASSWORD:
        return f"Password must be at least {MIN_PASSWORD} characters."
    if len(password) > MAX_PASSWORD:
        return f"Password must be at most {MAX_PASSWORD} characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must include at least one letter and one number."
    if password.lower() in COMMON_PASSWORDS:
        return "That password is too common. Please choose something harder to guess."
    local = re.sub(r"[^a-z0-9]", "", email.split("@")[0].lower())
    if len(local) >= 4 and local in re.sub(r"[^a-z0-9]", "", password.lower()):
        return "Password shouldn't contain your email name."
    return None


class LoginThrottle:
    """Blocks repeated failed logins for the same email/IP to stop password guessing."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 15 * 60):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._failures.get(key, []) if now - t < self.window]
        self._failures[key] = recent
        return recent

    def retry_after(self, key: str) -> int:
        """Seconds until this key may try again (0 if not blocked)."""
        now = time.monotonic()
        with self._lock:
            recent = self._recent(key, now)
            if len(recent) < self.max_failures:
                return 0
            return int(self.window - (now - recent[0])) + 1

    def fail(self, key: str) -> None:
        with self._lock:
            self._recent(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


class RateLimiter:
    """Allows at most `limit` requests per `window_seconds` for each key (e.g. a visitor's IP)."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> int:
        """Record a request. Returns 0 if allowed, else seconds to wait."""
        now = time.monotonic()
        with self._lock:
            recent = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(recent) >= self.limit:
                self._hits[key] = recent
                return int(self.window - (now - recent[0])) + 1
            recent.append(now)
            self._hits[key] = recent
            return 0
