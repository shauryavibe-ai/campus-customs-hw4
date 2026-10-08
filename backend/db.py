"""Access to the Campus Customs SQLite database."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# CAMPUS_DB_PATH lets tests/demos run against a copy instead of the real database.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = Path(os.getenv("CAMPUS_DB_PATH") or DATA_DIR / "campus_customs.db")
PRODUCT_IMAGES_DIR = DATA_DIR / "products"  # served at /media/products (independent of which DB is used)
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

# Same display-name cleanup as the frontend (see outputs/harness.md section 1.6).
NAME_FIXES = [
    (r"^Ua Mens Tech L S 2 0$", "UA Men's Tech Long Sleeve 2.0"),
    (r"^Squash Left Chest Tennis$", "Squash Left Chest Crewneck"),
    (r"\b1 4 Zip\b", "¼-Zip"),
    (r"\bT Shirt\b", "T-Shirt"),
    (r"\bTri Blend\b", "Tri-Blend"),
    (r"\bSchool Of\b", "School of"),
    (r"\bCreqneck\b", "Crewneck"),
    (r"\bTrack Field\b", "Track & Field"),
    (r"\bTrack And Field\b", "Track & Field"),
    (r"\bVs\b", "vs."),
    (r"^Ua ", "UA "),
    (r" 1$", ""),
]


def display_name(name: str) -> str:
    for pattern, replacement in NAME_FIXES:
        name = re.sub(pattern, replacement, name)
    return name


@contextmanager
def connect(write: bool = False) -> Iterator[sqlite3.Connection]:
    """Read-only by default (catalogue/chat); write=True for account changes, committed on success."""
    mode = "rw" if write else "ro"
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode={mode}", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        if write:
            conn.commit()
    except Exception:
        if write:
            conn.rollback()
        raise
    finally:
        conn.close()


def table_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in ("catalogue", "inventory", "users", "chat_messages")
        }


def load_products() -> list[dict]:
    """Every catalogue row with its per-size stock, as plain dicts."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT product_id, name, garment_type, description, colors, search_tags, image_file_path, price "
            "FROM catalogue ORDER BY product_id"
        ).fetchall()
        stock: dict[str, dict[str, int]] = {}
        for r in conn.execute("SELECT product_id, size, quantity FROM inventory"):
            stock.setdefault(r["product_id"], {})[r["size"]] = r["quantity"]

    products = []
    for r in rows:
        sizes = stock.get(r["product_id"], {})
        products.append(
            {
                "product_id": r["product_id"],
                "name": display_name(r["name"]),
                "garment_type": r["garment_type"],
                "description": r["description"],
                "colors": json.loads(r["colors"]),
                "search_tags": json.loads(r["search_tags"]),
                "image_file_path": r["image_file_path"],
                "price": r["price"],
                "stock": {size: sizes.get(size, 0) for size in SIZES},
            }
        )
    return products
