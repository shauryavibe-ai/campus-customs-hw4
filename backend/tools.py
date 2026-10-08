"""Tools the shop assistant uses to look up real Campus Customs data.

The agent never knows a price or stock number on its own. It must call:

    find_products            search the catalogue (names, styles, colors, budget, size in stock)
    get_product_description  what an item is: description, colors, style
    get_price                the item's current price, read from the catalogue table
    get_stock                units on hand per size, read from the inventory table
    get_shopper_profile      who is chatting: the logged-in shopper's name and email (users table)

Every price and quantity a tool returns is written to the run's FactLedger. Before a reply
reaches the shopper, `unsupported_numbers()` checks that each $ amount and stock count in
the text came from the ledger (or from the shopper's own message); otherwise the agent is
told to retry. Product cards are always rebuilt from the database, never from AI text.
"""

from __future__ import annotations

import functools
import re
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import Field
from pydantic_ai import RunContext

import db
from audit import AgentRun, short
from chat import CATEGORIES, STOPWORDS, Query, find, parse
from models import (
    PriceInfo,
    ShopperProfile,
    ProductDescription,
    ProductMatch,
    SearchResult,
    Size,
    SizeStock,
    StockInfo,
    ToolError,
    stock_status,
)

CategoryName = Literal[tuple(c[0] for c in CATEGORIES)]  # type: ignore[valid-type]
CATEGORY_BY_NAME = {c[0]: c for c in CATEGORIES}
ProductRef = Annotated[str, Field(max_length=120, description="A product_id (preferred) or the product's name.")]


# ---------- Run state ----------


@dataclass
class FactLedger:
    """Prices and quantities the tools returned during this chat message."""

    prices: set[float] = field(default_factory=set)
    quantities: set[int] = field(default_factory=set)
    product_ids: set[str] = field(default_factory=set)
    search_hits: list[str] = field(default_factory=list)  # ids find_products returned, in rank order

    def saw_product(self, product_id: str, price: float | None = None) -> None:
        self.product_ids.add(product_id)
        if price is not None:
            self.prices.add(round(float(price), 2))


@dataclass
class ShopDeps:
    """What one chat message's agent run can see.

    `user_id` comes from the login session (never from the AI or the browser), so
    get_shopper_profile can only ever read the account of the person actually chatting.
    No passwords, password hashes or session tokens are ever available to the agent.
    """

    user_id: int | None = None
    viewing_product_id: str | None = None  # product page they're on now
    previous_page: str | None = None  # page of their previous message ("" = no product page; None = first message)
    last_cards: list[str] = field(default_factory=list)  # cards shown with the agent's most recent reply
    user_text: str = ""  # what the shopper typed (this message + earlier ones), for the fact check
    products: list[dict] = field(default_factory=db.load_products)
    ledger: FactLedger = field(default_factory=FactLedger)
    audit: AgentRun | None = None  # audit-trail recorder for this run (audit.py)

    def by_id(self, product_id: str) -> dict | None:
        return next((p for p in self.products if p["product_id"] == product_id), None)


# ---------- Helpers ----------


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _match(p: dict) -> ProductMatch:
    return ProductMatch(
        product_id=p["product_id"],
        name=p["name"],
        garment_type=p["garment_type"],
        price=p["price"],
        colors=p["colors"],
        sizes_in_stock=[s for s in db.SIZES if p["stock"][s] > 0],
    )


def resolve(deps: ShopDeps, product: str) -> dict | ToolError:
    """Find exactly one product from an id or a name; otherwise explain and suggest, never guess.

    Name lookup is strict: every word the agent passes must appear in the product's name or id,
    so "pink unicorn onesie" is an error rather than whichever pink item happens to exist.
    """
    ref = product.strip()
    if hit := deps.by_id(ref.lower()):
        return hit
    wanted = _norm(ref)
    words = [w for w in wanted.split() if w not in STOPWORDS]
    named = [p for p in deps.products if _norm(p["name"]) == wanted]
    if not named and words:
        named = [p for p in deps.products if all(w in f"{_norm(p['name'])} {_norm(p['product_id'])}" for w in words)]
    if len(named) == 1:
        return named[0]

    # Not exactly one: offer real candidates for the agent to ask the shopper about.
    candidates = named or [p for p in deps.products if any(w in _norm(p["name"]) for w in words)]
    suggestions = [_match(p) for p in candidates[:3]]
    for s in suggestions:
        deps.ledger.saw_product(s.product_id, s.price)
    reason = "Several products match" if len(named) > 1 else "No product matches"
    return ToolError(error=f'{reason} "{ref}". Ask the shopper which one, or use find_products.', suggestions=suggestions)


def _fresh_price(product_id: str) -> tuple[str, float] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT name, price FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
    return (db.display_name(row["name"]), row["price"]) if row else None


def _fresh_stock(product_id: str) -> dict[str, int]:
    with db.connect() as conn:
        rows = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()
    found = {r["size"]: r["quantity"] for r in rows}
    return {s: found.get(s, 0) for s in db.SIZES}


# ---------- Audit trail ----------


def summarize(result: Any) -> str:
    """Short, privacy-safe description of a tool result for the audit trail."""
    if isinstance(result, SearchResult):
        top = ", ".join(p.product_id for p in result.products[:3])
        return f"{result.total_matches} matches; top: {top or 'none'}"
    if isinstance(result, PriceInfo):
        return f"{result.product_id}: ${result.price:.2f}"
    if isinstance(result, StockInfo):
        sizes = ", ".join(f"{s.size} {s.quantity}" for s in result.sizes)
        return f"{result.product_id}: {sizes}; total {result.total_units}"
    if isinstance(result, ProductDescription):
        return f"{result.product_id}: colors {', '.join(result.colors) or 'n/a'}; description {'yes' if result.description else 'none'}"
    if isinstance(result, ShopperProfile):
        return "logged in: name and email returned" if result.logged_in else "guest: no account details"
    if isinstance(result, ToolError):
        return f"error: {result.error} ({len(result.suggestions)} suggestions)"
    return short(result)


def audited(tool):
    """Record each call of `tool` (time, short args, short result, duration) on the run's audit trail."""

    @functools.wraps(tool)
    def wrapper(ctx: RunContext[ShopDeps], *args, **kwargs):
        started = time.perf_counter()
        given = {k: v for k, v in kwargs.items() if v not in (None, "")}  # only the arguments the agent set
        try:
            result = tool(ctx, *args, **kwargs)
        except Exception as exc:
            if ctx.deps.audit:
                ctx.deps.audit.event("tool_call", tool=tool.__name__, args=short(given or list(args)),
                                     result=f"raised {type(exc).__name__}", ms=round((time.perf_counter() - started) * 1000), ok=False)
            raise
        if ctx.deps.audit:
            ctx.deps.audit.event("tool_call", tool=tool.__name__, args=short(given or list(args)),
                                 result=summarize(result), ms=round((time.perf_counter() - started) * 1000),
                                 ok=not isinstance(result, ToolError))
        return result

    return wrapper


# ---------- Tools ----------


def find_products(
    ctx: RunContext[ShopDeps],
    keywords: Annotated[str, Field(max_length=200)] = "",
    category: CategoryName | None = None,  # type: ignore[valid-type]
    color: Annotated[str, Field(max_length=30)] | None = None,
    size: Size | None = None,
    max_price: Annotated[float, Field(ge=0, le=10_000)] | None = None,
    sort: Literal["relevance", "price_low_to_high", "price_high_to_low"] = "relevance",
    limit: Annotated[int, Field(ge=1, le=10)] = 6,
) -> SearchResult:
    """Search the Campus Customs catalogue. Use this first to find product_ids.

    Args:
        keywords: Words to match in names, descriptions and tags, e.g. "bulldog", "Saybrook", "hockey".
        category: Garment category to restrict to.
        color: A color the garment should include, e.g. "navy", "gray", "white".
        size: Only return items currently in stock in this size.
        max_price: Only return items at or below this price in USD.
        sort: Ranking. Use price_low_to_high for "cheapest" questions.
        limit: Maximum number of products to return.
    """
    q = parse(keywords) if keywords.strip() else Query()
    if category:
        q.category = CATEGORY_BY_NAME[category]
    if color:
        q.color = color.strip().lower()
    if size:
        q.size = size
    if max_price is not None:
        q.max_price = max_price
    q.sort = {"price_low_to_high": "asc", "price_high_to_low": "desc"}.get(sort, q.sort)
    ranked, ignored = find(q, ctx.deps.products)
    matches = [_match(p) for p in ranked[:limit]]
    for m in matches:
        ctx.deps.ledger.saw_product(m.product_id, m.price)
        ctx.deps.ledger.search_hits.append(m.product_id)
    return SearchResult(total_matches=len(ranked), ignored_keywords=ignored, products=matches)


def get_product_description(ctx: RunContext[ShopDeps], product: ProductRef) -> ProductDescription | ToolError:
    """Describe one product: what it looks like, its colors and style.

    Args:
        product: The product_id (preferred) or the product's name.
    """
    p = resolve(ctx.deps, product)
    if isinstance(p, ToolError):
        return p
    ctx.deps.ledger.saw_product(p["product_id"])
    description = None if "filename-based stub" in p["description"] else p["description"]
    return ProductDescription(
        product_id=p["product_id"],
        name=p["name"],
        garment_type=p["garment_type"],
        description=description,
        colors=p["colors"],
        tags=p["search_tags"],
        page=f"/products/{p['product_id']}",
    )


def get_price(ctx: RunContext[ShopDeps], product: ProductRef) -> PriceInfo | ToolError:
    """Get a product's current price in USD, straight from the catalogue table.

    Args:
        product: The product_id (preferred) or the product's name.
    """
    p = resolve(ctx.deps, product)
    if isinstance(p, ToolError):
        return p
    fresh = _fresh_price(p["product_id"])
    if fresh is None:
        return ToolError(error=f"{p['product_id']} is no longer in the catalogue.")
    name, price = fresh
    ctx.deps.ledger.saw_product(p["product_id"], price)
    return PriceInfo(product_id=p["product_id"], name=name, price=price)


def get_stock(ctx: RunContext[ShopDeps], product: ProductRef, size: Size | None = None) -> StockInfo | ToolError:
    """Get how many units are in stock right now, per size, straight from the inventory table.

    Args:
        product: The product_id (preferred) or the product's name.
        size: Only this size (XS, S, M, L, XL, XXL). Leave empty for every size.
    """
    p = resolve(ctx.deps, product)
    if isinstance(p, ToolError):
        return p
    stock = _fresh_stock(p["product_id"])
    sizes = [size] if size else db.SIZES
    rows = [SizeStock(size=s, quantity=stock[s], status=stock_status(stock[s])) for s in sizes]
    total = sum(r.quantity for r in rows)
    ledger = ctx.deps.ledger
    ledger.saw_product(p["product_id"])
    ledger.quantities.update(r.quantity for r in rows)
    ledger.quantities.add(total)
    ledger.quantities.add(sum(stock.values()))
    ledger.quantities.add(sum(1 for q in stock.values() if q > 0))  # "4 sizes in stock"
    return StockInfo(
        product_id=p["product_id"],
        name=p["name"],
        sizes=rows,
        total_units=total,
        sizes_in_stock=[s for s in db.SIZES if stock[s] > 0],
    )


def get_shopper_profile(ctx: RunContext[ShopDeps]) -> ShopperProfile:
    """Who is chatting: the logged-in shopper's first/last name, email and member-since date.

    Takes no arguments. It always returns the account of the shopper in this chat (from their
    login session), or logged_in=false for guests. Use it to greet them by name or when they
    ask about their account; it never includes passwords.
    """
    if ctx.deps.user_id is None:
        return ShopperProfile(logged_in=False)
    with db.connect() as conn:
        row = conn.execute(
            "SELECT first_name, last_name, name, email, created_at FROM users WHERE id = ?", (ctx.deps.user_id,)
        ).fetchone()
        saved = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (ctx.deps.user_id,)).fetchone()[0]
    if row is None:
        return ShopperProfile(logged_in=False)
    return ShopperProfile(
        logged_in=True,
        first_name=row["first_name"],
        last_name=row["last_name"],
        full_name=row["name"],
        email=row["email"],
        member_since=row["created_at"],
        saved_messages=saved,
    )


TOOLS = [audited(t) for t in (find_products, get_product_description, get_price, get_stock, get_shopper_profile)]


# ---------- Fact check ----------

_PRICE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:dollars|usd|bucks)\b", re.IGNORECASE)
_QTY = re.compile(
    r"\b(?:only|just)\s+(\d+)\b"
    r"|\b(\d+)\s+(?:units?|pieces?|left|in stock|available|remaining|on hand|in the shop)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def unsupported_numbers(reply: str, ledger: FactLedger, user_text: str = "") -> list[str]:
    """Prices or stock counts in `reply` that no tool returned (and the shopper didn't say)."""
    from_user = {float(n) for n in _NUMBER.findall(user_text.replace(",", ""))}
    allowed_prices = from_user | {round(p * k, 2) for p in ledger.prices for k in range(1, 11)}
    allowed_qty = from_user | {float(q) for q in ledger.quantities}

    problems = []
    for m in _PRICE.finditer(reply):
        value = float((m.group(1) or m.group(2)).replace(",", ""))
        if round(value, 2) not in allowed_prices:
            problems.append(m.group(0).strip())
    for m in _QTY.finditer(reply):
        value = float(m.group(1) or m.group(2))
        if value not in allowed_qty:
            problems.append(m.group(0).strip())
    return problems
