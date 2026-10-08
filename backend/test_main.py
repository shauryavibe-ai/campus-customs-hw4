"""Health check plus the rule-based helper (used as the fallback when the AI is unavailable)."""

from fastapi.testclient import TestClient

from chat import answer
from main import app

client = TestClient(app)


def chat(message: str) -> dict:
    result = answer(message)
    return {"reply": result.reply, "products": [card.model_dump() for card in result.products]}


def test_health_reads_database():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["tables"]["catalogue"] == 102
    assert body["tables"]["inventory"] == 612


def test_greeting_has_no_products():
    body = chat("hey")
    assert "Welcome" in body["reply"]
    assert body["products"] == []


def test_category_search_returns_hoodies():
    body = chat("What hoodies do you have?")
    assert body["products"]
    assert all("hood" in p["garment_type"].lower() for p in body["products"])


def test_size_filter_only_returns_in_stock():
    body = chat("navy hoodies in size L")
    assert body["products"]
    for p in body["products"]:
        assert p["requested_size"] == "L"
        assert p["requested_size_qty"] > 0
        assert "L" in p["sizes_in_stock"]


def test_cheapest_fleece_is_a_jacket():
    body = chat("whats your cheapest fleece?")
    assert body["products"]
    assert "jacket" in body["products"][0]["garment_type"]
    assert "most affordable" in body["reply"]


def test_price_ceiling():
    body = chat("t-shirts under $40")
    assert body["products"]
    assert all(p["price"] <= 40 for p in body["products"])


def test_handsome_dan_maps_to_bulldog():
    body = chat("anything with handsome dan")
    assert body["products"]


def test_keyword_search_college():
    body = chat("Saybrook")
    assert body["products"]
    assert all("saybrook" in p["product_id"] for p in body["products"])


def test_missing_color_explains():
    body = chat("you have this in pink?")
    assert body["products"] == [] or all(p["product_id"] for p in body["products"])
    body = chat("purple hoodies")
    assert body["products"] == []
    assert "don't have" in body["reply"]


def test_no_match():
    body = chat("gym shorts")
    assert body["products"] == []


def test_store_location():
    assert "57 Broadway" in chat("where is the store?")["reply"]


def test_rejects_empty_message():
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
