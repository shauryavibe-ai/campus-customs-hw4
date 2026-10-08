"""Append-only audit trail of the shop assistant's agent loop -> outputs/audit_trail.json

One entry per chat message the agent handles ("run"), appended after the run ends:

    {
      "run_id": "…", "started_at": "2026-10-07T23:20:01.123-04:00", "model": "gpt-6-luna",
      "shopper": "guest" | "user:4", "page_product_id": "…" | null,
      "message": "short, redacted copy of what the shopper typed", "history_turns": 2,
      "events": [
        {"time": "…", "t_ms": 812, "type": "tool_call", "tool": "find_products",
         "args": "{\"category\": \"hoodies\"}", "result": "27 matches; top: …", "ms": 4, "ok": true},
        {"time": "…", "t_ms": 2310, "type": "retry", "reason": "reply states ['$55'] which no tool returned"}
      ],
      "stop_reason": "final_answer" | "content_filter" | "usage_limit" | "retries_exhausted" | "timeout" | "error",
      "error": null | "ExceptionType", "source": "ai" | "blocked" | "fallback",
      "reply": "short copy of the reply", "product_ids": ["…"],
      "usage": {"requests": 3, "tool_calls": 2, "input_tokens": …, "output_tokens": …},
      "ended_at": "…", "duration_ms": 4120
    }

Append-only: a new run is written in front of the file's closing "]}" under an exclusive file lock,
so earlier runs are never rewritten, and the file is valid JSON after every write.
Privacy: emails and long digit runs (card/phone numbers) are masked; no passwords, hashes, session
tokens or profile emails are ever logged (get_shopper_profile results are summarized, not copied).
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(os.getenv("AUDIT_TRAIL_PATH") or Path(__file__).resolve().parent.parent / "outputs" / "audit_trail.json")
SCHEMA_VERSION = 1
SHORT = 160
HEADER = {
    "schema_version": SCHEMA_VERSION,
    "description": "Append-only log of the Campus Customs shop assistant's agent loop: one run per chat message, "
    "with timed tool calls (short args/results), validator retries and the stop reason. Written by backend/audit.py.",
}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LONG_DIGITS = re.compile(r"(?:\d[ -]?){7,}\d")
log = logging.getLogger("campus_customs.audit")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def redact(text: str) -> str:
    """Mask emails and card/phone-like digit runs."""
    return _LONG_DIGITS.sub("[number]", _EMAIL.sub("[email]", text))


def short(value: Any, limit: int = SHORT) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str, separators=(", ", ": "))
    text = redact(" ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class AgentRun:
    """Collects one agent run's activity; `record()` turns it into the JSON entry."""

    model: str
    shopper: str
    message: str
    page_product_id: str | None = None
    history_turns: int = 0
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=now_iso)
    events: list[dict] = field(default_factory=list)
    usage: dict | None = None
    _t0: float = field(default_factory=time.perf_counter)

    def elapsed_ms(self) -> int:
        return round((time.perf_counter() - self._t0) * 1000)

    def event(self, type_: str, **details: Any) -> None:
        self.events.append({"time": now_iso(), "t_ms": self.elapsed_ms(), "type": type_, **details})

    def record(self, stop_reason: str, source: str, reply: str, product_ids: list[str], error: str | None = None) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "model": self.model,
            "shopper": self.shopper,
            "page_product_id": self.page_product_id,
            "message": short(self.message),
            "history_turns": self.history_turns,
            "events": self.events,
            "stop_reason": stop_reason,
            "error": error,
            "source": source,
            "reply": short(reply, 240),
            "product_ids": product_ids,
            "usage": self.usage,
            "ended_at": now_iso(),
            "duration_ms": self.elapsed_ms(),
        }


def append_run(entry: dict, path: Path | None = None) -> None:
    """Append one run to the trail without rewriting earlier runs."""
    path = path or AUDIT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(entry, ensure_ascii=False, indent=2)
    body = "\n".join("    " + line for line in body.splitlines())
    with open(path, "a+b") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0, os.SEEK_END)
            if f.tell() == 0:  # new file: header + first run
                head = json.dumps(HEADER, ensure_ascii=False, indent=2)[:-2]  # drop closing "\n}"
                f.write(f'{head},\n  "runs": [\n{body}\n  ]\n}}\n'.encode())
                return
            tail = b"\n  ]\n}\n"
            f.seek(-len(tail), os.SEEK_END)
            if f.read(len(tail)) != tail:
                raise ValueError(f"{path} doesn't end the way the audit writer expects; not appending")
            f.seek(-len(tail), os.SEEK_END)
            f.truncate()
            empty = f.tell() > 0 and _ends_with_open_list(f)
            f.write(f"{'' if empty else ','}\n{body}{tail.decode()}".encode())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _ends_with_open_list(f) -> bool:
    f.seek(-1, os.SEEK_END)
    last = f.read(1)
    f.seek(0, os.SEEK_END)
    return last == b"["


def safe_append(entry: dict) -> None:
    """Never let auditing break a shopper's chat."""
    try:
        append_run(entry)
    except Exception:
        log.exception("Could not write audit trail")
