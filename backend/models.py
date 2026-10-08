"""Every data shape the API and the AI agent use, in one place.

Keep this file updated whenever the chat replies, product cards, agent output or account
forms change. Limits and cleaning rules live here too, so anything coming in from the
browser or out of the AI model is checked the same way everywhere.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from db import SIZES

Size = Literal["XS", "S", "M", "L", "XL", "XXL"]

# ---------- Limits ----------

MAX_MESSAGE_CHARS = 500  # one shopper message
MAX_TURN_CHARS = 2000  # one earlier message in the history
MAX_HISTORY_TURNS = 20  # earlier messages sent back with each request
MAX_HISTORY_CHARS = 12_000  # all history combined
MAX_REPLY_CHARS = 800  # one AI reply
MAX_CARDS = 4  # product cards per reply
LOW_STOCK_MAX = 5  # "Only N left" threshold, same as the website

PRODUCT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁦-⁩]")
_LINK_OR_HTML = re.compile(r"(https?://|www\.|<\s*/?\s*[a-z]+[^>]*>)", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Strip invisible/control characters (incl. bidi tricks) and surrounding whitespace."""
    return _CONTROL_CHARS.sub("", text).strip()


StockStatus = Literal["in stock", "low stock", "sold out"]


def stock_status(qty: int) -> StockStatus:
    if qty == 0:
        return "sold out"
    return "low stock" if qty <= LOW_STOCK_MAX else "in stock"


# ---------- Chat: fixed wording ----------

CHAT_GREETING = "What do you need today? What products are you looking for?"
CHAT_STARTERS = [
    "Do you have hoodies in my size?",
    "What's your cheapest crewneck?",
    "Show me gear for my residential college",
    "What do you have for Yale sports fans?",
    "I need a gift for a Yale parent",
    "Anything with Handsome Dan on it?",
    "What colors do your sweatshirts come in?",
    "Where is the store, and can I pick up in person?",
]
CHAT_RATE_LIMITED = "You're sending messages very quickly. Please wait a moment and try again."
CHAT_BLOCKED = (
    "I can only help with Campus Customs gear: styles, sizes, stock, gift ideas or visiting the store. "
    "What are you looking for today?"
)


class ChatStarters(BaseModel):
    """Greeting + dropdown questions shown when the chat opens."""

    greeting: str = CHAT_GREETING
    questions: list[str] = Field(default_factory=lambda: list(CHAT_STARTERS))


# ---------- Chat: request from the website ----------


def _valid_ids(ids: list[str]) -> list[str]:
    return [i for i in dict.fromkeys(ids) if isinstance(i, str) and PRODUCT_ID_RE.match(i)][:MAX_CARDS]


class ChatTurn(BaseModel):
    """One earlier message, so the agent can follow the conversation.

    For guests it comes from the browser (untrusted: treated as conversation, never as rules, and
    ids are only used to look products up). For logged-in shoppers it is read from chat_messages.
    """

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_TURN_CHARS)
    product_ids: list[str] = Field(
        default_factory=list, max_length=10, description="assistant turns: the product cards shown with this reply"
    )
    page_product_id: str | None = Field(
        default=None, max_length=200, description="user turns: the product page the shopper was on when sending it"
    )

    @field_validator("content")
    @classmethod
    def _clean(cls, v: str) -> str:
        return clean_text(v)

    @field_validator("product_ids")
    @classmethod
    def _ids(cls, v: list[str]) -> list[str]:
        return _valid_ids(v)

    @field_validator("page_product_id")
    @classmethod
    def _page(cls, v: str | None) -> str | None:
        return v if v and PRODUCT_ID_RE.match(v) else None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)
    page_product_id: str | None = Field(default=None, max_length=200)

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        v = clean_text(v)
        if not v:
            raise ValueError("Message is empty.")
        return v

    @field_validator("page_product_id")
    @classmethod
    def _valid_page_id(cls, v: str | None) -> str | None:
        # Comes from the page URL; anything that isn't a well-formed id is ignored, not trusted.
        return v if v and PRODUCT_ID_RE.match(v) else None

    @model_validator(mode="after")
    def _trim_history(self) -> ChatRequest:
        turns = [t for t in self.history if t.content][-MAX_HISTORY_TURNS:]
        while turns and sum(len(t.content) for t in turns) > MAX_HISTORY_CHARS:
            turns.pop(0)  # drop the oldest until the total fits
        self.history = turns
        return self


# ---------- Chat: product cards and replies (API contract v1) ----------
# This is the contract between the backend and the website's chat widget: the widget renders
# cards ONLY from these fields. Change them together with frontend/src/api.ts and bump
# CHAT_CONTRACT_VERSION. Documented in outputs/api_contract.md; schema in outputs/api_contract.openapi.json.

CHAT_CONTRACT_VERSION = "1.0"
SHORT_DESCRIPTION_CHARS = 110
Category = Literal["T-Shirts", "Crewnecks", "Hoodies", "Quarter-Zips", "Jackets & Fleece", "Long Sleeves"]


def category_of(garment_type: str) -> Category:
    """Same 6 store categories as the website (outputs/harness.md section 1.3)."""
    g = garment_type.lower()
    if "jacket" in g:
        return "Jackets & Fleece"
    if "quarter-zip" in g:
        return "Quarter-Zips"
    if "hood" in g:
        return "Hoodies"
    if "crewneck" in g or "mockneck" in g:
        return "Crewnecks"
    if "long-sleeve" in g:
        return "Long Sleeves"
    return "T-Shirts"


def short_description(description: str) -> str | None:
    if "filename-based stub" in description:  # placeholder rows have no real description
        return None
    if len(description) <= SHORT_DESCRIPTION_CHARS:
        return description
    cut = description[:SHORT_DESCRIPTION_CHARS]
    return cut[: cut.rfind(" ")].rstrip(" ,;:") + "…"


class CardSize(BaseModel):
    size: Size
    quantity: int = Field(ge=0, description="inventory.quantity at the time of the reply.")
    status: StockStatus


class ProductCard(BaseModel):
    """One product card under a chat reply. Built from the database by product_id, never from AI text."""

    product_id: str = Field(description="catalogue.product_id")
    name: str = Field(description="catalogue.name, cleaned for display")
    category: Category = Field(description="Store category derived from catalogue.garment_type")
    garment_type: str = Field(description="catalogue.garment_type")
    price: float = Field(ge=0, description="catalogue.price")
    currency: Literal["USD"] = "USD"
    short_description: str | None = Field(description="First ~110 chars of catalogue.description; null if none")
    colors: list[str] = Field(description="catalogue.colors")
    image_url: str = Field(description="Product photo, served by the API at /media/products/<file>.jpg")
    product_url: str = Field(description="Website path of the product page")
    sizes: list[CardSize] = Field(description="All six sizes in order XS..XXL with live quantities")
    sizes_in_stock: list[Size] = Field(description="Sizes with quantity > 0")
    total_stock: int = Field(ge=0, description="Sum of quantities across sizes")
    requested_size: Size | None = Field(default=None, description="Size the shopper asked about, if any")
    requested_size_qty: int | None = Field(default=None, description="Quantity in requested_size, if any")

    @classmethod
    def from_product(cls, product: dict, size: str | None = None) -> ProductCard:
        """`product` is a row from db.load_products(); `size` is the size the shopper asked about."""
        stock = product["stock"]
        image_file = product.get("image_file_path", f"products/{product['product_id']}.jpg")
        return cls(
            product_id=product["product_id"],
            name=product["name"],
            category=category_of(product["garment_type"]),
            garment_type=product["garment_type"],
            price=product["price"],
            short_description=short_description(product["description"]),
            colors=product["colors"],
            image_url=f"/media/{image_file}",
            product_url=f"/products/{product['product_id']}",
            sizes=[CardSize(size=s, quantity=stock[s], status=stock_status(stock[s])) for s in SIZES],
            sizes_in_stock=[s for s in SIZES if stock[s] > 0],
            total_stock=sum(stock.values()),
            requested_size=size,
            requested_size_qty=stock[size] if size else None,
        )


class ChatResponse(BaseModel):
    """What POST /api/chat sends back to the website."""

    contract_version: Literal["1.0"] = CHAT_CONTRACT_VERSION
    reply: str = Field(max_length=MAX_REPLY_CHARS + 200, description="Plain text to show in the chat bubble")
    products: list[ProductCard] = Field(
        default_factory=list, max_length=MAX_CARDS, description="Cards to render under the reply, in order"
    )
    # ai = agent answered; blocked = message refused by the safety filter; fallback = AI offline, rule-based answer
    source: Literal["ai", "blocked", "fallback"] = "ai"


class ChatHistoryMessage(BaseModel):
    """One saved message from chat_messages, as the widget shows it when a shopper returns."""

    id: int = Field(description="chat_messages.id")
    role: Literal["user", "assistant"] = Field(description="chat_messages.role")
    content: str = Field(description="chat_messages.content")
    page_product_id: str | None = Field(
        default=None, description="chat_messages.page_product_id: product page the shopper was on (user rows)"
    )
    products: list[ProductCard] = Field(
        default_factory=list, description="Cards shown with this reply, rebuilt from today's catalogue and stock"
    )
    created_at: str = Field(description="chat_messages.created_at (UTC, 'YYYY-MM-DD HH:MM:SS')")


class ChatHistory(BaseModel):
    """GET /api/chat/history: the logged-in shopper's saved conversation, oldest first."""

    contract_version: Literal["1.0"] = CHAT_CONTRACT_VERSION
    messages: list[ChatHistoryMessage]


class ShopReply(BaseModel):
    """The AI agent's structured answer. Checked before anything reaches the shopper."""

    reply: str = Field(description="Short, friendly plain-text answer for the shopper (no Markdown, no links).")
    product_ids: list[str] = Field(
        default_factory=list, description=f"Up to {MAX_CARDS} product_ids from tool results to show as cards."
    )
    size: Size | None = Field(default=None, description="Size the shopper asked about, if any.")

    @field_validator("reply")
    @classmethod
    def _safe_reply(cls, v: str) -> str:
        v = clean_text(v)
        if not v:
            raise ValueError("Reply is empty; write a short answer for the shopper.")
        if _LINK_OR_HTML.search(v):
            raise ValueError("Reply must be plain text with no links or HTML.")
        if len(v) > MAX_REPLY_CHARS:
            raise ValueError(f"Reply is too long; keep it under {MAX_REPLY_CHARS} characters.")
        return v

    @field_validator("product_ids")
    @classmethod
    def _dedupe_ids(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(pid.strip() for pid in v if pid.strip()))[:MAX_CARDS]


# ---------- Agent tool results (tools.py) ----------
# Every price and quantity the agent may mention comes from one of these, read from the database.
# Each field notes its source column (see outputs/harness.md section 6 for why each was chosen).
#
#   tool                     returns              database attributes it reads
#   find_products            SearchResult         catalogue.*, inventory.quantity (> 0 only)
#   get_product_description  ProductDescription   catalogue.description, colors, search_tags, garment_type
#   get_price                PriceInfo            catalogue.price
#   get_stock                StockInfo            inventory.size, inventory.quantity
#   get_shopper_profile      ShopperProfile       users.first_name, last_name, name, email, created_at
#                                                 (logged-in shopper only; id comes from the session)

class ProductMatch(BaseModel):
    """One search result: enough to identify a product and quote its price.

    Exact quantities are left out on purpose; "how many" questions go to get_stock.
    """

    product_id: str = Field(description="catalogue.product_id: the id every other tool takes.")
    name: str = Field(description="catalogue.name, cleaned for display.")
    garment_type: str = Field(description="catalogue.garment_type, e.g. 'pullover hoodie'.")
    price: float = Field(description="catalogue.price in USD.")
    colors: list[str] = Field(description="catalogue.colors.")
    sizes_in_stock: list[Size] = Field(description="Sizes whose inventory.quantity is above 0.")


class SearchResult(BaseModel):
    total_matches: int = Field(description="How many catalogue products matched (number of styles, not units).")
    ignored_keywords: list[str] = Field(default_factory=list, description="Search words nothing matched.")
    products: list[ProductMatch] = Field(description="Best matches first, at most `limit`.")


class ProductDescription(BaseModel):
    product_id: str = Field(description="catalogue.product_id.")
    name: str = Field(description="catalogue.name, cleaned for display.")
    garment_type: str = Field(description="catalogue.garment_type.")
    description: str | None = Field(
        description="catalogue.description; None for placeholder rows that have no real description."
    )
    colors: list[str] = Field(description="catalogue.colors.")
    tags: list[str] = Field(description="catalogue.search_tags (themes like 'bulldog', 'hockey').")
    page: str = Field(description="Website path of the product page.")


class PriceInfo(BaseModel):
    product_id: str = Field(description="catalogue.product_id.")
    name: str = Field(description="catalogue.name, cleaned for display.")
    price: float = Field(description="catalogue.price, read fresh from the database on each call.")
    currency: Literal["USD"] = "USD"


class SizeStock(BaseModel):
    size: Size = Field(description="inventory.size.")
    quantity: int = Field(description="inventory.quantity: units on hand, read fresh on each call.")
    status: StockStatus = Field(description="Derived from quantity: 0 sold out, 1-5 low stock, 6+ in stock.")


class StockInfo(BaseModel):
    product_id: str = Field(description="inventory.product_id.")
    name: str = Field(description="catalogue.name, cleaned for display.")
    sizes: list[SizeStock] = Field(description="One row per size asked about (all six if no size given).")
    total_units: int = Field(description="Sum of inventory.quantity over the sizes listed.")
    sizes_in_stock: list[Size] = Field(description="Sizes with inventory.quantity above 0 (all sizes).")


class ShopperProfile(BaseModel):
    """get_shopper_profile: the logged-in shopper's own account details (users table). Never the password hash."""

    logged_in: bool
    first_name: str | None = Field(default=None, description="users.first_name")
    last_name: str | None = Field(default=None, description="users.last_name")
    full_name: str | None = Field(default=None, description="users.name")
    email: str | None = Field(default=None, description="users.email")
    member_since: str | None = Field(default=None, description="users.created_at (UTC)")
    saved_messages: int = Field(default=0, description="How many of their chat messages are saved")


class ToolError(BaseModel):
    """Returned instead of guessing when a product can't be identified."""

    error: str
    suggestions: list[ProductMatch] = Field(default_factory=list, description="Real products the shopper may mean.")


# ---------- Bag and pickup reservations (Problem 9) ----------

MAX_PER_LINE = 10  # most units of one product+size in a bag
MAX_BAG_LINES = 30
STORE_PICKUP_ADDRESS = "Campus Customs, 57 Broadway, New Haven, CT 06511"


class BagItem(BaseModel):
    """One line in a shopper's bag, as the website stores and sends it."""

    product_id: str = Field(max_length=120)
    size: Size
    quantity: int = Field(ge=1, le=MAX_PER_LINE)

    @field_validator("product_id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not PRODUCT_ID_RE.match(v):
            raise ValueError("Invalid product id.")
        return v


class BagUpdate(BaseModel):
    """PUT /api/bag: the whole bag (replaces what's saved)."""

    items: list[BagItem] = Field(default_factory=list, max_length=MAX_BAG_LINES)


class BagLine(BagItem):
    """A saved/checked bag line with live data from the database."""

    name: str
    price: float
    image_url: str
    product_url: str
    available: int = Field(description="inventory.quantity for this size right now")
    line_total: float
    status: Literal["ok", "reduced", "sold_out"] = Field(
        description="ok; reduced = quantity lowered to what's in stock; sold_out = none left in this size"
    )


class Bag(BaseModel):
    items: list[BagLine]
    count: int = Field(description="Units across lines that can be reserved")
    subtotal: float = Field(description="Sum of line totals for lines that aren't sold out (USD)")


class Reservation(BaseModel):
    """POST /api/bag/reserve: confirmation the shopper shows at the counter."""

    code: str
    created_at: str
    name: str
    items: list[BagLine]
    total: float
    pickup_address: str = STORE_PICKUP_ADDRESS
    note: str = (
        "Show this code at the counter. Items were confirmed in stock when you reserved; pay in store when you pick up."
    )


# ---------- Accounts ----------


class SignupRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("first_name", "last_name", "email")
    @classmethod
    def _clean(cls, v: str) -> str:
        return clean_text(v)


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    """What the browser is allowed to see about a user. Never includes the password hash."""

    id: int
    first_name: str | None
    last_name: str | None
    name: str
    email: str
    created_at: str
