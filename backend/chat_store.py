"""Saved chat conversations for logged-in shoppers (the existing chat_messages table).

Row format, matching the rows already in the database:
    user_id        users.id of the shopper
    role           "user" or "assistant"
    content        the message text
    products_json  NULL for shopper messages; JSON list of the product cards shown with a reply
                   ([] when none). Older rows hold a different product snapshot shape, so cards
                   are always rebuilt from today's catalogue by product_id when loaded.
    created_at     filled in by SQLite (UTC)
    page_product_id  (added by this app, nullable) the product page the shopper was on when they
                   sent a message, so "this" can be understood later. NULL for older rows.

Only logged-in shoppers are saved here. Guests can chat normally; nothing of theirs is stored.
"""

from __future__ import annotations

import json
from pathlib import Path

import db
from models import ChatHistoryMessage, ChatTurn, ProductCard

HISTORY_PAGE = 100  # messages returned to the widget when a shopper comes back
AGENT_MEMORY = 20  # most recent messages the agent sees as conversation context


_schema_checked: set[Path] = set()


def ensure_schema() -> None:
    """Add the nullable page_product_id column to chat_messages once (non-destructive)."""
    if db.DB_PATH in _schema_checked:
        return
    with db.connect(write=True) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(chat_messages)")}
        if "page_product_id" not in columns:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN page_product_id TEXT")
    _schema_checked.add(db.DB_PATH)


def save_exchange(
    user_id: int, message: str, reply: str, cards: list[ProductCard], page_product_id: str | None = None
) -> None:
    """Store one shopper message (with the page they were on) and the reply it got, in one transaction."""
    ensure_schema()
    snapshot = json.dumps([c.model_dump() for c in cards], ensure_ascii=False)
    with db.connect(write=True) as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json, page_product_id) VALUES (?, 'user', ?, NULL, ?)",
            (user_id, message, page_product_id),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply, snapshot),
        )


def _rows(user_id: int, limit: int) -> list[dict]:
    ensure_schema()
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT id, role, content, products_json, page_product_id, created_at FROM chat_messages
               WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]  # oldest first


def _saved_ids(products_json: str | None) -> list[str]:
    """product_ids stored with a reply (works for both the old snapshot shape and ProductCard)."""
    try:
        saved = json.loads(products_json or "[]")
    except json.JSONDecodeError:
        return []
    return [item["product_id"] for item in saved if isinstance(item, dict) and isinstance(item.get("product_id"), str)]


def _cards(products_json: str | None, by_id: dict[str, dict]) -> list[ProductCard]:
    """Rebuild cards by product_id from today's data; skip anything no longer in the catalogue."""
    try:
        saved = json.loads(products_json or "[]")
    except json.JSONDecodeError:
        return []
    cards = []
    for item in saved if isinstance(saved, list) else []:
        product = by_id.get(item.get("product_id")) if isinstance(item, dict) else None
        if product:
            size = item.get("requested_size")
            cards.append(ProductCard.from_product(product, size if size in db.SIZES else None))
    return cards


def load_history(user_id: int, limit: int = HISTORY_PAGE) -> list[ChatHistoryMessage]:
    by_id = {p["product_id"]: p for p in db.load_products()}
    return [
        ChatHistoryMessage(
            id=r["id"],
            role=r["role"],
            content=r["content"],
            page_product_id=r["page_product_id"],
            products=_cards(r["products_json"], by_id) if r["role"] == "assistant" else [],
            created_at=r["created_at"],
        )
        for r in _rows(user_id, limit)
        if r["role"] in ("user", "assistant") and r["content"]
    ]


def recent_turns(user_id: int, limit: int = AGENT_MEMORY) -> list[ChatTurn]:
    """The conversation the agent remembers, read from the database (not from the browser):
    each reply with the product cards it showed, each shopper message with the page they were on."""
    return [
        ChatTurn(
            role=r["role"],
            content=r["content"][:2000],
            product_ids=_saved_ids(r["products_json"]) if r["role"] == "assistant" else [],
            page_product_id=r["page_product_id"] if r["role"] == "user" else None,
        )
        for r in _rows(user_id, limit)
        if r["role"] in ("user", "assistant") and r["content"].strip()
    ]


def message_count(user_id: int) -> int:
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user_id,)).fetchone()[0]
