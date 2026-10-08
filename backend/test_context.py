"""The agent must know what "this" means: cards it showed, the page the shopper is on, and history."""

import re
import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import assistant
import db
import main
import security
from models import ChatTurn
from tools import ShopDeps

models.ALLOW_MODEL_REQUESTS = False
HOODIE, MOM, SAYBROOK = "basic-hoodie-big-yale", "yale-mom-hoodie", "saybrook-college-crewneck"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    copy = tmp_path / "campus_customs.db"
    shutil.copy(db.DB_PATH, copy)
    monkeypatch.setattr(db, "DB_PATH", copy)
    monkeypatch.setattr(security, "ITERATIONS", 1_000)
    monkeypatch.setattr(main, "throttle", security.LoginThrottle())
    monkeypatch.setattr(main, "chat_limiter", security.RateLimiter(limit=1000, window_seconds=60))


def capture(seen: dict, reply: str = "Got it.", ids: tuple = ()) -> FunctionModel:
    """Fake LLM: records the instructions + conversation it was given, then answers."""

    def respond(messages, info: AgentInfo) -> ModelResponse:
        seen["instructions"] = "\n".join(m.instructions or "" for m in messages if isinstance(m, ModelRequest))
        seen["conversation"] = "\n".join(
            str(p.content) for m in messages for p in m.parts if isinstance(p, (UserPromptPart, TextPart))
        )
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"reply": reply, "product_ids": list(ids)})])

    return FunctionModel(respond)


def chat(client, message, model, **extra):
    with assistant.agent.override(model=model):
        res = client.post("/api/chat", json={"message": message, **extra})
    assert res.status_code == 200, res.text
    return res.json()


# ---------- what the agent is shown ----------


def test_history_notes_list_cards_with_photo_color():
    deps = ShopDeps()
    msgs = assistant.to_model_history(
        [
            ChatTurn(role="user", content="show me the basic hoodie", page_product_id=SAYBROOK),
            ChatTurn(role="assistant", content="Here it is!", product_ids=[HOODIE]),
        ],
        deps,
    )
    user_text, reply_text = msgs[0].parts[0].content, msgs[1].parts[0].content
    assert "Sent while viewing the product page for" in user_text and "Saybrook College Crewneck" in user_text
    assert "Product cards shown to the shopper" in reply_text and "Basic Hoodie Big Yale" in reply_text
    assert "colors, main first: navy blue, white" in reply_text  # the blue photo the shopper saw
    assert not re.search(r"\$\d|\d+ (left|in stock)", user_text + reply_text)  # never prices or stock


def instructions_for(**deps_kwargs) -> str:
    class Ctx:
        deps = ShopDeps(**deps_kwargs)

    return assistant.shopper_context(Ctx())


def test_context_one_card_shown():
    text = instructions_for(last_cards=[HOODIE])
    assert "most recent reply showed exactly one product card" in text and "Basic Hoodie Big Yale" in text


def test_context_several_cards_in_order():
    text = instructions_for(last_cards=[HOODIE, MOM])
    assert "showed 2 product cards, in this order: 1)" in text
    assert text.index("Basic Hoodie Big Yale") < text.index("Yale Mom Hoodie")


def test_context_moved_to_new_page():
    text = instructions_for(viewing_product_id=SAYBROOK, previous_page=HOODIE)
    assert 'product page for "Saybrook College Crewneck"' in text
    assert "opened this page after their previous message" in text
    assert "Basic Hoodie" not in text  # the page they left isn't put in front of the model
    assert 'they mean "Saybrook College Crewneck"' in text


def test_context_card_clicked_from_chat():
    # Asked on the Basic Hoodie page, the reply showed the hockey hoodie, they clicked it -> "this" = hockey hoodie
    hockey = "yale-sports-hoodie-hockey"
    text = instructions_for(viewing_product_id=hockey, previous_page=HOODIE, last_cards=[hockey])
    assert 'they mean "Yale Sports Hoodie Hockey"' in text and "Basic Hoodie" not in text


def test_subject_rules_order():
    text = instructions_for(viewing_product_id=MOM, previous_page=MOM, last_cards=[HOODIE])  # same page, one card
    assert 'they mean "Basic Hoodie Big Yale"' in text  # the single card wins over the unchanged page
    text = instructions_for(viewing_product_id=MOM, previous_page=MOM)
    assert 'they mean "Yale Mom Hoodie"' in text
    text = instructions_for(last_cards=[HOODIE, MOM])
    assert '"This" is ambiguous' in text


def test_context_same_page():
    assert "same page" in instructions_for(viewing_product_id=HOODIE, previous_page=HOODIE)


def test_context_no_product_page():
    assert "not on a product page" in instructions_for()


def test_prompt_has_the_this_it_rules():
    rules = assistant.base_instructions()
    assert 'Knowing what "this", "it" or "that one" means' in rules
    assert "Never write such notes yourself" in rules


# ---------- guests: context comes from the browser, nothing is saved ----------


def test_guest_this_in_pink_after_cards():
    seen: dict = {}
    guest = TestClient(main.app)
    before = sqlite3.connect(db.DB_PATH).execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    chat(
        guest,
        "do you have this in pink?",
        capture(seen),
        history=[
            {"role": "user", "content": "show me the basic hoodie", "page_product_id": None},
            {"role": "assistant", "content": "Here it is!", "product_ids": [HOODIE]},
        ],
    )
    assert "Basic Hoodie Big Yale" in seen["conversation"] and "navy blue" in seen["conversation"]
    assert "exactly one product card" in seen["instructions"] and HOODIE in seen["instructions"]
    after = sqlite3.connect(db.DB_PATH).execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    assert after == before  # guests can chat, nothing stored


def test_guest_on_product_page():
    seen: dict = {}
    chat(TestClient(main.app), "do you have this in pink?", capture(seen), page_product_id=MOM)
    assert 'product page for "Yale Mom Hoodie"' in seen["instructions"]


def test_forged_ids_in_guest_history_are_dropped():
    seen: dict = {}
    chat(
        TestClient(main.app),
        "this one?",
        capture(seen),
        history=[{"role": "assistant", "content": "hi", "product_ids": ["../../etc/passwd", "not-a-product"]}],
    )
    assert "passwd" not in seen["conversation"] and "Product cards shown" not in seen["conversation"]


# ---------- logged in: the same context is saved and comes back from the database ----------


def test_logged_in_context_round_trips_through_database():
    shopper = TestClient(main.app)
    shopper.post("/api/auth/signup", json={"first_name": "Grace", "last_name": "Hopper", "email": "g@yale.edu", "password": "Compiler1952"})
    uid = shopper.get("/api/auth/me").json()["id"]

    chat(shopper, "show me the basic hoodie", capture({}, "Here it is!", (HOODIE,)), page_product_id=SAYBROOK)
    row = sqlite3.connect(db.DB_PATH).execute(
        "SELECT page_product_id FROM chat_messages WHERE user_id = ? AND role = 'user'", (uid,)
    ).fetchone()
    assert row[0] == SAYBROOK

    seen: dict = {}
    chat(shopper, "do you have this in pink?", capture(seen), page_product_id=SAYBROOK)  # history from DB
    assert "Sent while viewing the product page for" in seen["conversation"]
    assert "Product cards shown to the shopper with this reply" in seen["conversation"] and "navy blue" in seen["conversation"]
    assert "exactly one product card" in seen["instructions"] and "same page" in seen["instructions"]

    history = shopper.get("/api/chat/history").json()["messages"]
    assert history[0]["page_product_id"] == SAYBROOK and history[1]["products"][0]["product_id"] == HOODIE
