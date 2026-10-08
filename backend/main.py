"""Campus Customs API: the FastAPI app that uvicorn runs.

Run from this directory:
  ../.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000

Routes
  GET  /api/health          database check
  GET  /api/chat/starters   greeting + common questions for the chat widget
  POST /api/chat            shopper message -> AI agent reply + product cards (contract v1, models.ChatResponse);
                            for logged-in shoppers the exchange is saved to chat_messages
  GET  /api/chat/history    the logged-in shopper's saved conversation (models.ChatHistory)
  POST /api/bag/check       price + stock-check a bag without saving (anyone; guests' bags live in the browser)
  GET  /api/bag | PUT /api/bag   the logged-in shopper's saved bag (replace on PUT)
  POST /api/bag/reserve     turn the saved bag into a pickup reservation at 57 Broadway
  GET  /media/products/*    product photos referenced by ProductCard.image_url
  POST /api/auth/signup | login | logout, GET /api/auth/me

The Vite frontend (http://127.0.0.1:5173) proxies /api to this server. The AI agent
(gpt-6-luna via Portkey) lives in assistant.py; its instructions are in prompts/prompts.md.
Every agent run is appended to outputs/audit_trail.json (audit.py).
The PORTKEY_API_KEY is read from the .env file on the server and never sent to the browser.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded

import assistant
import audit
import auth
import bag as bag_store
import chat_store
from chat import answer
from audit import AgentRun
from db import PRODUCT_IMAGES_DIR, table_counts
from models import (
    Bag,
    BagUpdate,
    Reservation,
    CHAT_BLOCKED,
    CHAT_RATE_LIMITED,
    ChatHistory,
    ChatRequest,
    ChatResponse,
    ChatStarters,
    LoginRequest,
    SignupRequest,
    UserOut,
)
from security import LoginThrottle, RateLimiter, password_problem

SESSION_COOKIE = "cc_session"
# Set COOKIE_SECURE=1 when served over HTTPS so the session cookie is never sent in plain text.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

app = FastAPI(title="Campus Customs API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)

# Product photos for chat cards (ProductCard.image_url). Only this one folder is exposed.
app.mount("/media/products", StaticFiles(directory=PRODUCT_IMAGES_DIR), name="product-images")

MAX_BODY_BYTES = 64 * 1024  # chat/auth requests are tiny; refuse anything bigger


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse({"detail": "Request too large."}, status_code=413)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith(("/api/auth", "/api/chat", "/api/bag")):
        response.headers["Cache-Control"] = "no-store"  # never cache personal or chat data
    return response


throttle = LoginThrottle()
# Caps AI usage per visitor so the API key can't be run up by one person or a script.
chat_limiter = RateLimiter(limit=int(os.getenv("CHAT_RATE_LIMIT", "20")), window_seconds=60)
log = logging.getLogger("campus_customs")
AI_TIMEOUT_SECONDS = 60


# ---------- Helpers ----------


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=auth.SESSION_DAYS * 24 * 3600,
        httponly=True,  # JavaScript can't read it, so injected scripts can't steal it
        samesite="lax",  # not sent on cross-site POSTs (CSRF protection)
        secure=COOKIE_SECURE,
        path="/",
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------- Routes ----------


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "tables": table_counts()}


@app.get("/api/chat/starters", response_model=ChatStarters)
def chat_starters() -> ChatStarters:
    return ChatStarters()


def _stop_reason(exc: BaseException) -> str:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(exc, UsageLimitExceeded):
        return "usage_limit"
    if isinstance(exc, UnexpectedModelBehavior):
        return "retries_exhausted"
    return "error"


async def _answer(message: str, history, user_id: int | None, page_product_id: str | None) -> ChatResponse:
    """Agent first; polite redirect if the provider's safety filter blocks it; rule-based fallback otherwise.

    Every run is appended to the audit trail (outputs/audit_trail.json) with its stop reason.
    """
    run = AgentRun(
        model=assistant.MODEL_NAME,
        shopper=f"user:{user_id}" if user_id is not None else "guest",
        message=message,
        page_product_id=page_product_id,
        history_turns=len(history),
    )
    try:
        reply, products = await asyncio.wait_for(
            assistant.ask(message, history=history, user_id=user_id, viewing_product_id=page_product_id, audit=run),
            timeout=AI_TIMEOUT_SECONDS,
        )
        audit.safe_append(run.record("final_answer", "ai", reply, [p.product_id for p in products]))
        return ChatResponse(reply=reply, products=products, source="ai")
    except ModelHTTPError as exc:
        if exc.status_code == 400 and "content_filter" in str(exc.body):
            # The model provider's safety filter refused the message (e.g. a jailbreak attempt).
            # Don't fall back to keyword search, which would echo the text; just steer back to shopping.
            log.info("Chat message blocked by provider content filter")
            audit.safe_append(run.record("content_filter", "blocked", CHAT_BLOCKED, [], error="ModelHTTPError(content_filter)"))
            return ChatResponse(reply=CHAT_BLOCKED, products=[], source="blocked")
        log.exception("AI assistant failed; using rule-based fallback")
        failure: BaseException = exc
    except Exception as exc:
        # The AI is unavailable (no key, network, timeout...): answer with the rule-based helper instead.
        log.exception("AI assistant failed; using rule-based fallback")
        failure = exc
    result = answer(message)
    run.event("fallback", note="rule-based helper answered instead of the AI")
    audit.safe_append(
        run.record(_stop_reason(failure), "fallback", result.reply, [c.product_id for c in result.products], error=type(failure).__name__)
    )
    return ChatResponse(reply=result.reply, products=result.products, source="fallback")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, cc_session: str | None = Cookie(default=None)) -> ChatResponse:
    if wait := chat_limiter.hit(_client_ip(request)):
        raise HTTPException(429, CHAT_RATE_LIMITED, headers={"Retry-After": str(wait)})
    message = req.message  # already cleaned and length-checked by ChatRequest
    user = auth.user_for_session(cc_session)
    if user:
        # Logged in: the saved conversation in the database is the agent's memory (the browser's copy is ignored).
        history = chat_store.recent_turns(user["id"])
    else:
        history = req.history
    response = await _answer(message, history, user["id"] if user else None, req.page_product_id)
    if user:
        try:
            chat_store.save_exchange(user["id"], message, response.reply, response.products, req.page_product_id)
        except Exception:
            log.exception("Could not save chat history")  # the shopper still gets their answer
    return response


@app.get("/api/chat/history", response_model=ChatHistory)
def chat_history(cc_session: str | None = Cookie(default=None)) -> ChatHistory:
    """The logged-in shopper's saved conversation (oldest first), so the widget can reload it."""
    user = auth.user_for_session(cc_session)
    if user is None:
        raise HTTPException(401, "Log in to see your saved chat.")
    return ChatHistory(messages=chat_store.load_history(user["id"]))


def _require_user(cc_session: str | None, message: str) -> dict:
    user = auth.user_for_session(cc_session)
    if user is None:
        raise HTTPException(401, message)
    return user


@app.post("/api/bag/check", response_model=Bag)
def bag_check(req: BagUpdate) -> Bag:
    """Live prices and stock for a bag, without saving anything (used for guests' browser bags)."""
    return bag_store.check(req.items)


@app.get("/api/bag", response_model=Bag)
def bag_get(cc_session: str | None = Cookie(default=None)) -> Bag:
    return bag_store.load(_require_user(cc_session, "Log in to see your saved bag.")["id"])


@app.put("/api/bag", response_model=Bag)
def bag_put(req: BagUpdate, cc_session: str | None = Cookie(default=None)) -> Bag:
    return bag_store.save(_require_user(cc_session, "Log in to save your bag.")["id"], req.items)


@app.post("/api/bag/reserve", response_model=Reservation)
def bag_reserve(cc_session: str | None = Cookie(default=None)):
    user = _require_user(cc_session, "Log in to reserve items for pickup.")
    try:
        return bag_store.reserve(user)
    except bag_store.ReservationProblem as problem:
        return JSONResponse({"detail": str(problem), "bag": problem.bag.model_dump()}, status_code=409)


@app.post("/api/auth/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, response: Response) -> dict:
    first, last = req.first_name.strip(), req.last_name.strip()
    email = _normalize_email(req.email)
    if not first or not last:
        raise HTTPException(422, "Please enter your first and last name.")
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Please enter a valid email address.")
    if problem := password_problem(req.password, email):
        raise HTTPException(422, problem)
    try:
        user = auth.create_user(first, last, email, req.password)
    except auth.EmailTaken:
        raise HTTPException(409, "An account with this email already exists. Try logging in.")
    _set_session_cookie(response, auth.create_session(user["id"]))
    return user


@app.post("/api/auth/login", response_model=UserOut)
def login(req: LoginRequest, request: Request, response: Response) -> dict:
    email = _normalize_email(req.email)
    key = f"{_client_ip(request)}|{email}"
    if wait := throttle.retry_after(key):
        raise HTTPException(
            429,
            f"Too many failed attempts. Please wait {max(1, wait // 60)} minute(s) and try again.",
            headers={"Retry-After": str(wait)},
        )
    user = auth.authenticate(email, req.password)
    if user is None:
        throttle.fail(key)
        # Same message whether the email or the password was wrong, so accounts can't be discovered.
        raise HTTPException(401, "Incorrect email or password.")
    throttle.reset(key)
    _set_session_cookie(response, auth.create_session(user["id"]))
    return user


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, cc_session: str | None = Cookie(default=None)) -> None:
    auth.delete_session(cc_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


@app.get("/api/auth/me", response_model=UserOut)
def me(cc_session: str | None = Cookie(default=None)) -> dict:
    user = auth.user_for_session(cc_session)
    if user is None:
        raise HTTPException(401, "Not logged in.")
    return user
