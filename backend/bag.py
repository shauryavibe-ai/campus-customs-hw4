"""Shopping bag for logged-in shoppers + "Reserve for pickup at 57 Broadway".

Guests keep their bag in the browser; when they log in it is merged into their account here.
Every line is checked against live stock (inventory table) whenever it's saved or reserved.

Tables (created automatically, non-destructive):
    bag_items     user_id, product_id, size, quantity, updated_at   (one row per product+size)
    reservations  id, code, user_id, items_json, total, status, created_at
A reservation records what the shopper will pick up; it does not change inventory (store staff
confirm at the counter), and there is no online payment.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

import db
from models import MAX_PER_LINE, Bag, BagItem, BagLine, Reservation

_schema_ready: set = set()


class ReservationProblem(Exception):
    """The bag can't be reserved as-is (empty, or stock changed). Carries the re-checked bag."""

    def __init__(self, message: str, bag: Bag):
        super().__init__(message)
        self.bag = bag


def ensure_schema() -> None:
    if db.DB_PATH in _schema_ready:
        return
    with db.connect(write=True) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS bag_items (
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, product_id, size),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES catalogue(product_id)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )"""
        )
    _schema_ready.add(db.DB_PATH)


def check(items: list[BagItem]) -> Bag:
    """Price each line and cap it at live stock. Unknown products are dropped; duplicates merged."""
    merged: dict[tuple[str, str], int] = {}
    for item in items:
        key = (item.product_id, item.size)
        merged[key] = min(MAX_PER_LINE, merged.get(key, 0) + item.quantity)

    lines: list[BagLine] = []
    with db.connect() as conn:
        for (product_id, size), wanted in merged.items():
            row = conn.execute(
                """SELECT c.name, c.price, c.image_file_path, i.quantity FROM catalogue c
                   JOIN inventory i ON i.product_id = c.product_id
                   WHERE c.product_id = ? AND i.size = ?""",
                (product_id, size),
            ).fetchone()
            if row is None:
                continue  # not a real product/size: drop it
            available = row["quantity"]
            quantity = min(wanted, available) if available else wanted
            status = "sold_out" if available == 0 else ("reduced" if quantity < wanted else "ok")
            lines.append(
                BagLine(
                    product_id=product_id,
                    size=size,
                    quantity=quantity,
                    name=db.display_name(row["name"]),
                    price=row["price"],
                    image_url=f"/media/{row['image_file_path']}",
                    product_url=f"/products/{product_id}",
                    available=available,
                    line_total=0.0 if status == "sold_out" else round(row["price"] * quantity, 2),
                    status=status,
                )
            )
    payable = [line for line in lines if line.status != "sold_out"]
    return Bag(
        items=lines,
        count=sum(line.quantity for line in payable),
        subtotal=round(sum(line.line_total for line in payable), 2),
    )


def load(user_id: int) -> Bag:
    ensure_schema()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT product_id, size, quantity FROM bag_items WHERE user_id = ? ORDER BY updated_at, rowid",
            (user_id,),
        ).fetchall()
    return check([BagItem(product_id=r["product_id"], size=r["size"], quantity=min(r["quantity"], MAX_PER_LINE)) for r in rows])


def save(user_id: int, items: list[BagItem]) -> Bag:
    """Replace the shopper's saved bag with `items` (after checking them against live stock)."""
    ensure_schema()
    bag = check(items)
    with db.connect(write=True) as conn:
        conn.execute("DELETE FROM bag_items WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO bag_items (user_id, product_id, size, quantity) VALUES (?, ?, ?, ?)",
            [(user_id, line.product_id, line.size, line.quantity) for line in bag.items],
        )
    return bag


def reserve(user: dict) -> Reservation:
    """Turn the saved bag into a pickup reservation, if every line is still fully in stock."""
    bag = load(user["id"])
    if not bag.items:
        raise ReservationProblem("Your bag is empty.", bag)
    if any(line.status != "ok" for line in bag.items):
        raise ReservationProblem(
            "Some items changed since you added them (sold out or fewer left). Review your bag and try again.",
            save(user["id"], [BagItem(**line.model_dump(include={"product_id", "size", "quantity"})) for line in bag.items]),
        )
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db.connect(write=True) as conn:
        for _ in range(5):
            code = f"CC-{secrets.token_hex(3).upper()}"
            if not conn.execute("SELECT 1 FROM reservations WHERE code = ?", (code,)).fetchone():
                break
        conn.execute(
            "INSERT INTO reservations (code, user_id, items_json, total, created_at) VALUES (?, ?, ?, ?, ?)",
            (code, user["id"], json.dumps([line.model_dump() for line in bag.items]), bag.subtotal, created),
        )
        conn.execute("DELETE FROM bag_items WHERE user_id = ?", (user["id"],))
    return Reservation(code=code, created_at=created, name=user["name"], items=bag.items, total=bag.subtotal)
