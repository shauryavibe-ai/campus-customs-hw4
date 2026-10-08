"""Tests for tools.py: real lookups from the database and the 'never invent numbers' check."""

import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import assistant
import db
import main
import tools
from models import PriceInfo, ProductDescription, StockInfo, ToolError

models.ALLOW_MODEL_REQUESTS = False
client = TestClient(main.app)
HOODIE = "basic-hoodie-big-yale"


class Ctx:
    """Minimal stand-in for RunContext when calling tools directly."""

    def __init__(self):
        self.deps = tools.ShopDeps()


def db_row(sql: str, *args):
    conn = sqlite3.connect(f"{db.DB_PATH.as_uri()}?mode=ro", uri=True)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return rows


# ---------- each tool returns exactly what's in the database ----------


def test_get_price_matches_catalogue_table():
    ctx = Ctx()
    out = tools.get_price(ctx, HOODIE)
    assert isinstance(out, PriceInfo)
    assert out.price == db_row("SELECT price FROM catalogue WHERE product_id = ?", HOODIE)[0][0]
    assert out.price in ctx.deps.ledger.prices


def test_get_stock_matches_inventory_table():
    ctx = Ctx()
    out = tools.get_stock(ctx, HOODIE)
    assert isinstance(out, StockInfo)
    expected = dict(db_row("SELECT size, quantity FROM inventory WHERE product_id = ?", HOODIE))
    assert {s.size: s.quantity for s in out.sizes} == expected
    assert out.total_units == sum(expected.values())
    assert set(expected.values()) <= ctx.deps.ledger.quantities


def test_get_stock_single_size_and_status():
    out = tools.get_stock(Ctx(), "ice-hockey-left-chest-hoodie", size="M")
    assert len(out.sizes) == 1 and out.sizes[0].size == "M"
    assert out.sizes[0].quantity == 0 and out.sizes[0].status == "sold out"


def test_get_product_description():
    out = tools.get_product_description(Ctx(), HOODIE)
    assert isinstance(out, ProductDescription)
    assert "kangaroo pocket" in out.description and out.page == f"/products/{HOODIE}"


def test_placeholder_product_has_no_fake_description():
    out = tools.get_product_description(Ctx(), "benjamin-franklin-t-shirt")
    assert out.description is None


def test_lookup_by_name_works():
    out = tools.get_price(Ctx(), "Basic Hoodie Big Yale")
    assert isinstance(out, PriceInfo) and out.product_id == HOODIE


def test_ambiguous_name_returns_suggestions_not_a_guess():
    out = tools.get_price(Ctx(), "hoodie")
    assert isinstance(out, ToolError) and "Several products match" in out.error
    assert out.suggestions


def test_unknown_product_is_an_error_not_a_guess():
    out = tools.get_stock(Ctx(), "pink unicorn onesie")
    assert isinstance(out, ToolError)


def test_find_products_records_prices():
    ctx = Ctx()
    out = tools.find_products(ctx, category="hoodies", size="XL", sort="price_low_to_high", limit=3)
    assert out.products and all("XL" in p.sizes_in_stock for p in out.products)
    assert {p.price for p in out.products} <= ctx.deps.ledger.prices


def test_stock_is_read_fresh_from_database(tmp_path, monkeypatch):
    # Change stock in a copy of the database after the catalogue was loaded: get_stock must see it.
    import shutil

    copy = tmp_path / "db.sqlite"
    shutil.copy(db.DB_PATH, copy)
    monkeypatch.setattr(db, "DB_PATH", copy)
    ctx = Ctx()
    conn = sqlite3.connect(copy)
    conn.execute("UPDATE inventory SET quantity = 3 WHERE product_id = ? AND size = 'M'", (HOODIE,))
    conn.commit()
    conn.close()
    assert tools.get_stock(ctx, HOODIE, size="M").sizes[0].quantity == 3


# ---------- the number fact check ----------


def ledger_with(prices=(), quantities=()):
    ledger = tools.FactLedger()
    ledger.prices.update(prices)
    ledger.quantities.update(quantities)
    return ledger


@pytest.mark.parametrize(
    "reply, problems",
    [
        ("It's $68 and we have 5 left in M.", []),
        ("Two of them would be $136.", []),  # 2 x a looked-up price is fine
        ("It's $59.", ["$59"]),
        ("Only 12 left in M!", ["Only 12"]),
        ("We have 40 units in stock.", ["40 units"]),
        ("Grab it for 50 dollars.", ["50 dollars"]),
        ("The 2025 Yale vs. Harvard tee is a classic.", []),  # not a price or stock count
    ],
)
def test_unsupported_numbers(reply, problems):
    assert tools.unsupported_numbers(reply, ledger_with(prices={68.0}, quantities={5, 8})) == problems


def test_shoppers_own_budget_can_be_repeated():
    assert tools.unsupported_numbers("Here's what I found under $70.", ledger_with(), "anything under $70?") == []


# ---------- end to end through the agent ----------


def script(steps):
    """Fake LLM that plays back tool calls / final answers in order."""
    calls = iter(steps)

    def respond(messages, info: AgentInfo) -> ModelResponse:
        name, args = next(calls)
        if name == "final":
            name = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(name, args)])

    return FunctionModel(respond)


def test_invented_price_is_corrected_before_reaching_shopper():
    real = db_row("SELECT price FROM catalogue WHERE product_id = ?", HOODIE)[0][0]
    steps = [
        ("final", {"reply": "The Basic Hoodie is $55.", "product_ids": [HOODIE]}),  # invented -> rejected
        ("get_price", {"product": HOODIE}),
        ("final", {"reply": f"The Basic Hoodie is ${real:.0f}.", "product_ids": [HOODIE]}),
    ]
    with assistant.agent.override(model=script(steps)):
        body = client.post("/api/chat", json={"message": "how much is the basic hoodie?"}).json()
    assert body["source"] == "ai"
    assert body["reply"] == f"The Basic Hoodie is ${real:.0f}."
    assert body["products"][0]["price"] == real


def test_invented_quantity_never_reaches_shopper():
    steps = [("final", {"reply": "Only 99 left in M, hurry!", "product_ids": [HOODIE], "size": "M"})] * 6
    with assistant.agent.override(model=script(steps)):
        body = client.post("/api/chat", json={"message": "how many in M?"}).json()
    assert "99" not in body["reply"]


def test_stock_question_end_to_end():
    real = dict(db_row("SELECT size, quantity FROM inventory WHERE product_id = ?", HOODIE))["M"]
    steps = [
        ("get_stock", {"product": HOODIE, "size": "M"}),
        ("final", {"reply": f"We have {real} in stock in M.", "product_ids": [HOODIE], "size": "M"}),
    ]
    with assistant.agent.override(model=script(steps)):
        body = client.post("/api/chat", json={"message": "how many basic hoodies in M?"}).json()
    assert body["source"] == "ai" and body["products"][0]["requested_size_qty"] == real


def test_prompt_documents_every_tool_and_its_database_field():
    text = assistant.base_instructions()
    for tool in tools.TOOLS:
        assert f"`{tool.__name__}" in text, f"{tool.__name__} missing from prompts.md"
    for column in ("catalogue.price", "inventory.quantity", "catalogue.description"):
        assert column in text
    assert "How many Yale hoodies are there?" in text and "How much is the Basic Hoodie Big Yale?" in text
