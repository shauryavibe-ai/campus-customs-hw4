"""Shared test setup.

- Tests never write to the real audit trail (outputs/audit_trail.json).
- Each test gets a fresh chat rate limit (all tests share one client address).
"""

import pytest

import audit
import main
from security import RateLimiter


@pytest.fixture(autouse=True)
def _temp_audit_trail(tmp_path, monkeypatch):
    path = tmp_path / "audit_trail.json"
    monkeypatch.setattr(audit, "AUDIT_PATH", path)
    return path


@pytest.fixture(autouse=True)
def _fresh_chat_limit(monkeypatch):
    monkeypatch.setattr(main, "chat_limiter", RateLimiter(limit=main.chat_limiter.limit, window_seconds=60))
