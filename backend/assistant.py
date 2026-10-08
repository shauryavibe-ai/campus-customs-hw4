"""Pydantic AI shop assistant (gpt-6-luna via Portkey) with tools over the live catalogue.

Security model:
- The agent can only read the catalogue/inventory through the read-only tools in tools.py.
- Any price or stock count in a reply must match what those tools returned this turn.
- Its answer must fit models.ShopReply (plain text, no links/HTML, size-limited) and may only
  reference product ids that exist; product cards are then built from the database.
- Each run is capped (model calls, tool calls, output tokens) to bound cost and loops.
- It never sees passwords, password hashes or session tokens. For a logged-in shopper it can call
  get_shopper_profile, which returns only that shopper's own name and email (id from the session).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from pydantic_ai import Agent, ModelRetry, RunContext  # noqa: E402
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart  # noqa: E402
from pydantic_ai.models.openai import OpenAIResponsesModel  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

from models import ChatTurn, ProductCard, ShopReply  # noqa: E402
from audit import AgentRun, short  # noqa: E402
from tools import TOOLS, ShopDeps, unsupported_numbers  # noqa: E402

BACKEND = Path(__file__).resolve().parent
PROMPT_FILE = BACKEND / "prompts" / "prompts.md"  # the agent's instructions; edit there, not here
# The root AI Foundations/.env is the source of truth for PORTKEY_API_KEY (project rule), so it
# overrides any stale key exported by the shell (e.g. an old one in ~/.zshrc).
load_dotenv(BACKEND.parent.parent / ".env", override=True)
load_dotenv(BACKEND.parent / ".env")  # a .env next to this project (e.g. a fresh clone); never committed

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna").strip()
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")
# Hard caps per chat message: model round-trips, tool calls and generated tokens.
USAGE_LIMITS = UsageLimits(request_limit=8, tool_calls_limit=10, output_tokens_limit=6_000)
MODEL_SETTINGS = {"max_tokens": 2_000}


_prompt_cache: tuple[float, str] = (0.0, "")


def _instructions() -> str:
    """prompts.md, re-read whenever the file changes (uvicorn --reload only watches .py files)."""
    global _prompt_cache
    mtime = PROMPT_FILE.stat().st_mtime
    if mtime != _prompt_cache[0]:
        _prompt_cache = (mtime, PROMPT_FILE.read_text(encoding="utf-8"))
    return _prompt_cache[1]


log = logging.getLogger("campus_customs.assistant")


def model_or_none() -> OpenAIResponsesModel | None:
    """The real model, or None when no PORTKEY_API_KEY is configured.

    With None, a model supplied via agent.override(...) (the tests' fake models) still runs, so the
    test suite works in a fresh clone without a key. Without any model, the run fails and the chat
    falls back to the rule-based helper.
    """
    try:
        return build_model()
    except RuntimeError as exc:
        log.warning("%s The AI assistant is unavailable; chat will use the rule-based helper.", exc)
        return None


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set (add it to the .env file).")
    client = AsyncOpenAI(api_key=api_key, base_url=PORTKEY_BASE_URL, default_headers={"x-portkey-api-key": api_key})
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


# defer_model_check: the real model is only built on first use, so tests can override it.
agent = Agent(
    None,
    deps_type=ShopDeps,
    output_type=ShopReply,
    tools=TOOLS,  # tools.py: find_products, get_product_description, get_price, get_stock
    retries=3,  # lets the agent correct an unsupported number or bad product id
    model_settings=MODEL_SETTINGS,
    defer_model_check=True,
)


@agent.instructions
def base_instructions() -> str:
    return _instructions()


def describe_product(p: dict) -> str:
    """How a product is named to the agent: name, id, garment and colors (main/photo color first). No numbers."""
    return f'"{p["name"]}" (product_id {p["product_id"]}; {p["garment_type"]}; colors, main first: {", ".join(p["colors"]) or "not listed"})'


@agent.instructions
def shopper_context(ctx: RunContext[ShopDeps]) -> str:
    """What's on the shopper's screen right now, so "this", "it" and "that one" can be understood."""
    deps = ctx.deps
    lines = ["## Right now"]
    if deps.user_id is not None:
        lines.append(
            "- The shopper is logged in, and this conversation is saved to their account. Call "
            "get_shopper_profile (no arguments) when you need their name or email; it only returns their own account."
        )
    else:
        lines.append("- The shopper is a guest (not logged in). Nothing is saved; get_shopper_profile will say so.")

    viewing = deps.by_id(deps.viewing_product_id) if deps.viewing_product_id else None
    if viewing:
        lines.append(f"- They are on the product page for {describe_product(viewing)}.")
    else:
        lines.append("- They are not on a product page (home, catalogue, about or account page).")

    moved = deps.previous_page is not None and (deps.previous_page or None) != (viewing or {}).get("product_id")
    if deps.previous_page is not None:  # there was an earlier shopper message
        lines.append(
            "- They opened this page after their previous message (which was sent from a different page)."
            if moved and viewing
            else "- They have moved to a different page since their previous message."
            if moved
            else "- They were on this same page when they sent their previous message."
        )

    shown = [p for p in (deps.by_id(pid) for pid in deps.last_cards) if p]
    if len(shown) == 1:
        lines.append(f"- Your most recent reply showed exactly one product card: {describe_product(shown[0])}.")
    elif shown:
        listed = "; ".join(f"{i}) {describe_product(p)}" for i, p in enumerate(shown, 1))
        lines.append(f"- Your most recent reply showed {len(shown)} product cards, in this order: {listed}.")

    subject, reason = likely_subject(viewing, moved, shown)
    if subject:
        lines.append(
            f'- **If they say "this", "it" or "that one" without naming an item, they mean {describe_product(subject)}**, '
            f"because {reason}. Answer about this product unless they clearly name a different one."
        )
    elif len(shown) > 1:
        lines.append('- "This" is ambiguous right now (several cards were shown): ask which one, or answer for each by name.')
    return "\n".join(lines)


def likely_subject(viewing: dict | None, moved: bool, shown: list[dict]) -> tuple[dict | None, str]:
    """What "this" most likely means, using the same rules as the chat widget's "Talking about" chip."""
    if viewing and moved:
        return viewing, "they opened its product page after their last message"
    if len(shown) == 1:
        return shown[0], "your most recent reply showed only this product"
    if viewing:
        return viewing, "they are on its product page"
    return None, ""


def _retry(ctx: RunContext[ShopDeps], reason: str) -> ModelRetry:
    """Note a rejected answer on the audit trail, then send the agent back to fix it."""
    if ctx.deps.audit:
        ctx.deps.audit.event("retry", reason=short(reason))
    return ModelRetry(reason)


@agent.output_validator
def check_reply(ctx: RunContext[ShopDeps], output: ShopReply) -> ShopReply:
    # Text-level checks (plain text, no links, length, max cards) already ran in models.ShopReply.
    known = {p["product_id"] for p in ctx.deps.products}
    unknown = [pid for pid in output.product_ids if pid not in known]
    if unknown:
        raise _retry(ctx, f"These product_ids don't exist: {unknown}. Only use ids returned by the tools.")
    # Never let an invented price or stock count through: every number must come from a tool this turn.
    invented = unsupported_numbers(output.reply, ctx.deps.ledger, ctx.deps.user_text)
    if invented:
        raise _retry(ctx, 
            f"Your reply states {invented}, which no tool returned in this turn. Call get_price / get_stock "
            "(or find_products) for those items and use only the exact values they return, or leave the numbers out."
        )
    # API contract: if the agent searched and found matches, the shopper must see them as cards.
    if ctx.deps.ledger.search_hits and not output.product_ids:
        raise _retry(ctx, 
            "find_products returned matching products, so put the best matches (up to 4, in the order you "
            "recommend) in product_ids. The website shows them as product cards."
        )
    return output


def to_model_history(history: list[ChatTurn], deps: ShopDeps | None = None) -> list[ModelMessage]:
    """Turn the saved/browser history into Pydantic AI messages, with context notes in [brackets]:
    replies list the product cards they showed (name, id, colors with the photo color first), and
    shopper messages note the product page they were sent from. Notes never contain prices or stock."""
    by_id = deps.by_id if deps else (lambda _pid: None)
    messages: list[ModelMessage] = []
    for turn in history:
        text = turn.content
        if turn.role == "user":
            page = by_id(turn.page_product_id) if turn.page_product_id else None
            if page:
                text += f"\n\n[Sent while viewing the product page for {describe_product(page)}.]"
            messages.append(ModelRequest(parts=[UserPromptPart(content=text)]))
        else:
            shown = [p for p in (by_id(pid) for pid in turn.product_ids) if p]
            if shown:
                listed = "; ".join(f"{i}) {describe_product(p)}" for i, p in enumerate(shown, 1))
                text += f"\n\n[Product cards shown to the shopper with this reply, in order: {listed}.]"
            messages.append(ModelResponse(parts=[TextPart(content=text)]))
    return messages


async def ask(
    message: str,
    history: list[ChatTurn] | None = None,
    user_id: int | None = None,
    viewing_product_id: str | None = None,
    audit: AgentRun | None = None,
) -> tuple[str, list[ProductCard]]:
    """Run the agent and return (reply text, product cards built from the database).

    `audit` (optional) collects the run's tool calls, retries and usage for the audit trail.
    """
    history = history or []
    said = [t.content for t in history if t.role == "user"] + [message]
    user_turns = [t for t in history if t.role == "user"]
    deps = ShopDeps(
        user_id=user_id,
        viewing_product_id=viewing_product_id,
        user_text="\n".join(said),
        previous_page=(user_turns[-1].page_product_id or "") if user_turns else None,
        last_cards=history[-1].product_ids if history and history[-1].role == "assistant" else [],
        audit=audit,
    )
    result = await agent.run(
        message,
        message_history=to_model_history(history, deps),
        deps=deps,
        model=model_or_none(),  # agent.override(model=...) in tests takes precedence
        usage_limits=USAGE_LIMITS,
    )
    out = result.output
    if audit:
        u = result.usage
        audit.usage = {"requests": u.requests, "tool_calls": u.tool_calls, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}
        audit.event("final_output", product_ids=out.product_ids, size=out.size)
    cards = [ProductCard.from_product(deps.by_id(pid), out.size) for pid in out.product_ids]
    return out.reply, cards
