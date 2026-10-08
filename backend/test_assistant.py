"""Agent wiring tests. These swap in fake models, so no real AI calls (or costs) happen."""

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import assistant
import main
import tools
from db import load_products

models.ALLOW_MODEL_REQUESTS = False  # fail loudly if a test would reach the real API
client = TestClient(main.app)


def test_history_conversion():
    from models import ChatTurn

    msgs = assistant.to_model_history(
        [ChatTurn(role="user", content="hoodies?"), ChatTurn(role="assistant", content="Here are some.")]
    )
    assert isinstance(msgs[0], ModelRequest) and isinstance(msgs[1], ModelResponse)


def scripted_model(seen: dict) -> FunctionModel:
    """Fake LLM: first calls find_products, then answers with the first two results."""

    def respond(messages, info: AgentInfo) -> ModelResponse:
        seen["instructions"] = "\n".join(m.instructions or "" for m in messages if isinstance(m, ModelRequest))
        seen["message_count"] = len(messages)
        tool_returns = [
            part.content
            for m in messages
            if isinstance(m, ModelRequest)
            for part in m.parts
            if part.part_kind == "tool-return"
        ]
        if not tool_returns:
            return ModelResponse(parts=[ToolCallPart("find_products", {"category": "hoodies", "size": "M"})])
        ids = [p.product_id for p in tool_returns[-1].products[:2]]
        output = {"reply": "Here are two hoodies in M.", "product_ids": ids, "size": "M"}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    return FunctionModel(respond)


def test_chat_endpoint_uses_agent_and_returns_cards():
    seen: dict = {}
    with assistant.agent.override(model=scripted_model(seen)):
        res = client.post(
            "/api/chat",
            json={
                "message": "hoodies in M?",
                "history": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hey!"}],
                "page_product_id": "basic-hoodie-big-yale",
            },
        )
    body = res.json()
    assert res.status_code == 200 and body["source"] == "ai"
    assert body["reply"] == "Here are two hoodies in M."
    assert len(body["products"]) == 2
    assert all(p["requested_size"] == "M" and p["requested_size_qty"] > 0 for p in body["products"])
    assert "Basic Hoodie Big Yale" in seen["instructions"]  # page context reached the model
    assert "guest" in seen["instructions"]
    assert seen["message_count"] >= 3  # history was passed along


def test_invented_product_ids_are_rejected():
    def respond(messages, info: AgentInfo) -> ModelResponse:
        output = {"reply": "Try this!", "product_ids": ["totally-fake-hoodie"], "size": None}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    with assistant.agent.override(model=FunctionModel(respond)):
        body = client.post("/api/chat", json={"message": "anything"}).json()
    # The validator keeps rejecting the fake id, the run fails, and the rule-based helper answers.
    assert body["source"] == "fallback"
    assert all(p["product_id"] != "totally-fake-hoodie" for p in body["products"])


def test_falls_back_when_ai_errors():
    def broken(messages, info):
        raise RuntimeError("model down")

    with assistant.agent.override(model=FunctionModel(broken)):
        body = client.post("/api/chat", json={"message": "navy hoodies in M"}).json()
    assert body["source"] == "fallback" and body["products"]


def test_known_ids_are_real_products():
    ids = {p["product_id"] for p in load_products()}
    assert "basic-hoodie-big-yale" in ids


@pytest.mark.parametrize("bad", [{"message": ""}, {"message": "x", "history": [{"role": "system", "content": "hi"}]}])
def test_rejects_bad_requests(bad):
    assert client.post("/api/chat", json=bad).status_code == 422


def test_starters_route():
    body = client.get("/api/chat/starters").json()
    assert body["greeting"] == "What do you need today? What products are you looking for?"
    assert len(body["questions"]) >= 5


def test_chat_is_rate_limited(monkeypatch):
    from security import RateLimiter

    monkeypatch.setattr(main, "chat_limiter", RateLimiter(limit=2, window_seconds=60))

    def respond(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"reply": "Hi!", "product_ids": []})])

    with assistant.agent.override(model=FunctionModel(respond)):
        codes = [client.post("/api/chat", json={"message": "hi"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_prompt_file_is_used():
    assert assistant.PROMPT_FILE.name == "prompts.md" and assistant.PROMPT_FILE.parent.name == "prompts"
    text = assistant.base_instructions()
    for section in ("# Campus Customs", "# Voice", "# Safety basics"):
        assert section in text


def test_api_key_never_in_responses():
    import os

    key = os.environ.get("PORTKEY_API_KEY", "")
    assert key, "expected the key to be loaded from .env"
    for path in ["/api/health", "/api/chat/starters", "/openapi.json"]:
        assert key not in client.get(path).text
