"""API contract tests: POST /api/chat -> ChatResponse v1 -> product cards the website renders."""

import re
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic_ai import models
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import assistant
import db
import export_contract
import main
from models import CHAT_CONTRACT_VERSION, CardSize, ChatHistory, ChatHistoryMessage, ChatResponse, ChatTurn, ProductCard

models.ALLOW_MODEL_REQUESTS = False
client = TestClient(main.app)
API_TS = Path(__file__).resolve().parent.parent / "frontend" / "src" / "api.ts"


def search_then_answer(search_args: dict, n_cards: int = 4, skip_cards_first: bool = False) -> FunctionModel:
    """Fake LLM: calls find_products, then answers with the top results as product_ids."""
    state = {"answered_without_cards": False}

    def respond(messages, info: AgentInfo) -> ModelResponse:
        returns = [p.content for m in messages if isinstance(m, ModelRequest) for p in m.parts if p.part_kind == "tool-return"]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("find_products", search_args)])
        if skip_cards_first and not state["answered_without_cards"]:
            state["answered_without_cards"] = True
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"reply": "We have lots of hoodies!"})])
        ids = [p.product_id for p in returns[0].products[:n_cards]]
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"reply": "Here are some hoodies we carry.", "product_ids": ids})])

    return FunctionModel(respond)


def db_truth(product_id: str) -> tuple[float, dict[str, int]]:
    conn = sqlite3.connect(f"{db.DB_PATH.as_uri()}?mode=ro", uri=True)
    price = conn.execute("SELECT price FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()[0]
    stock = dict(conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall())
    conn.close()
    return price, stock


def ask(message: str, model: FunctionModel) -> dict:
    with assistant.agent.override(model=model):
        res = client.post("/api/chat", json={"message": message})
    assert res.status_code == 200, res.text
    return res.json()


# ---------- "What hoodies do you have?" end to end ----------


def test_what_hoodies_returns_contract_cards():
    body = ask("What hoodies do you have?", search_then_answer({"category": "hoodies"}))
    ChatResponse.model_validate(body)  # exact shape
    assert body["contract_version"] == CHAT_CONTRACT_VERSION and body["source"] == "ai"
    assert 1 <= len(body["products"]) <= 4

    for card in body["products"]:
        assert card["category"] == "Hoodies"
        assert card["product_url"] == f"/products/{card['product_id']}"
        assert [s["size"] for s in card["sizes"]] == ["XS", "S", "M", "L", "XL", "XXL"]
        price, stock = db_truth(card["product_id"])
        assert card["price"] == price
        assert {s["size"]: s["quantity"] for s in card["sizes"]} == stock
        assert card["total_stock"] == sum(stock.values())
        assert card["sizes_in_stock"] == [s for s in ["XS", "S", "M", "L", "XL", "XXL"] if stock[s] > 0]
        img = client.get(card["image_url"])  # the website loads this exact URL
        assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"


def test_search_results_must_come_back_as_cards():
    # The model first answers without product_ids; the contract rule makes it retry with cards.
    body = ask("What hoodies do you have?", search_then_answer({"category": "hoodies"}, skip_cards_first=True))
    assert body["source"] == "ai" and body["products"]


def test_size_question_fills_requested_size():
    def respond(messages, info: AgentInfo) -> ModelResponse:
        returns = [p.content for m in messages if isinstance(m, ModelRequest) for p in m.parts if p.part_kind == "tool-return"]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("find_products", {"category": "hoodies", "size": "M"})])
        ids = [p.product_id for p in returns[0].products[:2]]
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"reply": "In M:", "product_ids": ids, "size": "M"})])

    body = ask("hoodies in M?", FunctionModel(respond))
    for card in body["products"]:
        _, stock = db_truth(card["product_id"])
        assert card["requested_size"] == "M" and card["requested_size_qty"] == stock["M"] > 0


def test_fallback_answers_follow_the_same_contract():
    def broken(messages, info):
        raise RuntimeError("AI down")

    body = ask("What hoodies do you have?", FunctionModel(broken))
    ChatResponse.model_validate(body)
    assert body["source"] == "fallback" and body["products"]
    assert all(c["image_url"].startswith("/media/products/") for c in body["products"])


def test_small_talk_has_no_cards():
    def hello(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"reply": "Hey there!"})])

    body = ask("hi", FunctionModel(hello))
    assert body["products"] == []


# ---------- frontend and backend stay in sync ----------


def ts_interface_fields(name: str) -> set[str]:
    source = API_TS.read_text()
    body = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.S)
    assert body, f"interface {name} not found in frontend/src/api.ts"
    return set(re.findall(r"^\s+(\w+)\??:", body.group(1), re.M))


def test_frontend_types_match_backend_models():
    for ts_name, model in [
        ("ProductCard", ProductCard),
        ("CardSize", CardSize),
        ("ChatResponse", ChatResponse),
        ("ChatHistoryMessage", ChatHistoryMessage),
        ("ChatHistory", ChatHistory),
        ("ChatTurn", ChatTurn),
    ]:
        assert ts_interface_fields(ts_name) == set(model.model_fields), f"{ts_name} differs from models.{model.__name__}"


def test_saved_openapi_contract_is_up_to_date():
    assert export_contract.OUT.read_text() == export_contract.render(), (
        "outputs/api_contract.openapi.json is stale. Run: ../.venv/bin/python export_contract.py"
    )


# ---------- image route is safe ----------


def test_media_route_only_serves_product_photos():
    assert client.get("/media/products/../campus_customs.db").status_code == 404
    assert client.get("/media/products/%2e%2e/campus_customs.db").status_code == 404
    assert client.get("/media/products/not-a-real-file.jpg").status_code == 404
