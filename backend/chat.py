"""Rule-based shop assistant (no AI yet).

Parses a shopper's message for category, size, color, price and keywords, then
answers from the live catalogue and inventory tables. The AI agent can later
replace `answer()` while keeping the same request/response shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from db import load_products
from models import ProductCard

MAX_RESULTS = 4
STORE_ADDRESS = "57 Broadway, New Haven, CT"

# (plural label, singular label, words the shopper might use, test on lower-cased garment_type)
CATEGORIES = [
    ("long sleeves", "long-sleeve shirt", ["long sleeve", "long sleeves", "long-sleeve", "longsleeve"], lambda g: "long-sleeve" in g),
    ("quarter-zips", "quarter-zip", ["quarter zip", "quarter zips", "quarter-zip", "quarter-zips", "1/4 zip", "1/4 zips", "¼ zip", "1 4 zip", "qzip"], lambda g: "quarter-zip" in g),
    ("jackets & fleece", "jacket or fleece", ["fleece", "fleeces", "jacket", "jackets", "coat", "coats", "bomber"], lambda g: "jacket" in g),
    ("hoodies", "hoodie", ["hoodie", "hoodies", "hooded", "hoody"], lambda g: "hood" in g),
    ("crewnecks", "crewneck", ["crewneck", "crewnecks", "crew neck", "crew necks", "mockneck"], lambda g: "crewneck" in g or "mockneck" in g),
    ("sweatshirts", "sweatshirt", ["sweatshirt", "sweatshirts", "sweater", "sweaters"], lambda g: "sweatshirt" in g or "hood" in g or "crewneck" in g),
    ("T-shirts", "T-shirt", ["t-shirt", "t-shirts", "tshirt", "tshirts", "t shirt", "t shirts", "tee", "tees", "shirt", "shirts"], lambda g: "t-shirt" in g),
]

# Shopper color word -> substrings to look for in the catalogue's color names.
COLORS = {
    "navy": ["navy"],
    "blue": ["blue", "navy"],
    "gray": ["gray"],
    "grey": ["gray"],
    "charcoal": ["charcoal"],
    "white": ["white", "cream", "ivory"],
    "cream": ["cream", "ivory"],
    "black": ["black"],
    "red": ["red"],
    "green": ["green"],
    "yellow": ["yellow", "gold"],
    "gold": ["gold"],
    "pink": ["pink", "coral"],
    "coral": ["coral"],
    "orange": ["orange"],
    "purple": ["purple"],
}

SIZE_WORDS = {"extra small": "XS", "small": "S", "medium": "M", "large": "L", "extra large": "XL", "2xl": "XXL"}
SYNONYMS = {"handsome dan": "bulldog", "bulldogs": "bulldog", "q-zip": "quarter-zip"}
STOPWORDS = set(
    """a an and any anything are at be can do does for from got have i in is it its me my of on
    or show some something that the there this to u want with you your yo im i'm looking need
    get find whats what's which who do have cool right please pls thanks thank any item items
    gear stuff merch yale campus customs one ones like word on it buy sell carry options
    cheap cheaper cheapest lowest budget affordable expensive priciest premium under below less
    than over above dollars dollar price prices cost size sizes color colors colour stock
    available availability in-stock instock left what how where when why does got ur about
    these those all tell see has had also too just really very much many more other else
    dont don't do any anything new options hi hey hello look looking check most least""".split()
)


@dataclass
class Query:
    category: tuple | None = None
    size: str | None = None
    color: str | None = None
    max_price: float | None = None
    sort: str | None = None  # "asc" | "desc"
    keywords: list[str] = field(default_factory=list)


@dataclass
class ChatAnswer:
    reply: str
    products: list[ProductCard]


def _strip_phrases(text: str, phrases: list[str]) -> str:
    for p in sorted(phrases, key=len, reverse=True):
        text = re.sub(rf"(?<![\w-]){re.escape(p)}(?![\w-])", " ", text)
    return text


def parse(message: str) -> Query:
    q = Query()
    low = message.lower()
    for phrase, replacement in SYNONYMS.items():
        low = low.replace(phrase, replacement)

    for cat in CATEGORIES:
        if any(re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", low) for w in cat[2]):
            q.category = cat
            low = _strip_phrases(low, cat[2])
            break

    size = re.search(r"\b(xxl|xl|xs)\b", low) or re.search(r"\bsize\s+(xxl|xl|xs|s|m|l)\b", low)
    if size:
        q.size = size.group(1).upper()
    elif m := re.search(r"\b([SML])\b", message):  # bare S/M/L only when capitalized
        q.size = m.group(1)
    else:
        for word, code in sorted(SIZE_WORDS.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"\b{word}\b", low):
                q.size = code
                break
    low = re.sub(r"\b(size\s+)?(xxl|xl|xs|2xl|extra small|extra large|small|medium|large)\b", " ", low)

    for word in COLORS:
        if re.search(rf"\b{word}\b", low):
            q.color = word
            low = re.sub(rf"\b{word}\b", " ", low)
            break

    if price := re.search(r"(?:under|below|less than|<)\s*\$?\s*(\d+(?:\.\d+)?)", low):
        q.max_price = float(price.group(1))
        q.sort = "asc"
        low = low.replace(price.group(0), " ")
    if re.search(r"\b(cheap|cheaper|cheapest|lowest|budget|affordable|least expensive)\b", low):
        q.sort = "asc"
    elif re.search(r"\b(most expensive|priciest|premium|nicest)\b", low):
        q.sort = "desc"

    words = re.findall(r"[a-z0-9][a-z0-9'-]*", low)
    q.keywords = [w for w in words if w not in STOPWORDS and len(w) > 1 and not w.isdigit()]
    return q


def _haystack(p: dict) -> str:
    return " ".join(
        [p["name"], p["product_id"], p["garment_type"], p["description"], *p["colors"], *p["search_tags"]]
    ).lower()


def _money(value: float) -> str:
    return f"${value:,.0f}" if value == int(value) else f"${value:,.2f}"


def small_talk(message: str) -> str | None:
    low = message.lower().strip()
    if re.fullmatch(r"(hi|hello|hey|yo|hiya|sup|good (morning|afternoon|evening))[!. ]*", low):
        return (
            "Hey! Welcome to Campus Customs. Ask me about hoodies, crewnecks, quarter-zips, "
            "your residential college, a sport, or a size, and I'll check what's on the shelf."
        )
    if re.search(r"\b(thanks|thank you|thx|ty)\b", low):
        return "Anytime! Holler if you want me to check another size or style."
    if re.search(r"\b(help|what can you do|how does this work)\b", low):
        return (
            "I can search our live catalogue and stock. Try: \"navy hoodies in M\", "
            "\"cheapest fleece\", \"Saybrook\", \"hockey\", or \"t-shirts under $40\"."
        )
    if re.search(r"\b(where|address|location|located|visit|store hours|hours|directions)\b", low):
        return f"You'll find us at {STORE_ADDRESS}, right across from campus. Stop by to try on sizes!"
    return None


def find(q: Query, products: list[dict] | None = None) -> tuple[list[dict], list[str]]:
    """Filter and rank catalogue products for a parsed query.

    Returns (ranked products, keywords that were ignored because nothing matched them).
    Shared by the rule-based fallback below and the AI agent's search tool.
    """
    products = load_products() if products is None else products
    if q.category:
        products = [p for p in products if q.category[3](p["garment_type"].lower())]
    if q.color:
        needles = COLORS.get(q.color, [q.color])
        products = [p for p in products if any(n in c for c in p["colors"] for n in needles)]
    if q.max_price is not None:
        products = [p for p in products if p["price"] <= q.max_price]
    if q.size:
        products = [p for p in products if p["stock"][q.size] > 0]

    scored = []
    for p in products:
        hay = _haystack(p)
        score = sum(1 for k in q.keywords if k in hay)
        if q.keywords and score == 0:
            continue
        scored.append((score, p))

    ignored: list[str] = []
    if not scored and q.keywords and (q.category or q.size or q.color or q.max_price):
        # Unknown extra words shouldn't hide real matches for the style/size/color asked for.
        ignored, q.keywords = q.keywords, []
        scored = [(0, p) for p in products]

    if q.sort == "asc":
        scored.sort(key=lambda sp: (-sp[0], sp[1]["price"]))
    elif q.sort == "desc":
        scored.sort(key=lambda sp: (-sp[0], -sp[1]["price"]))
    else:
        scored.sort(key=lambda sp: (-sp[0], -sum(sp[1]["stock"].values())))
    return [p for _, p in scored], ignored


def answer(message: str) -> ChatAnswer:
    if reply := small_talk(message):
        return ChatAnswer(reply, [])

    q = parse(message)
    if not (q.category or q.size or q.color or q.max_price or q.sort or q.keywords):
        return ChatAnswer(
            "I'm a simple shop helper for now. Try a style (hoodies, tees, quarter-zips), "
            "a college or sport, a color, or a size like M.",
            [],
        )

    ranked, ignored = find(q)

    plural, singular = (q.category[0], q.category[1]) if q.category else ("items", "item")
    filters = [f'matching "{" ".join(q.keywords)}"'] if q.keywords else []
    if q.color:
        filters.append(f"in {q.color}")
    if q.max_price is not None:
        filters.append(f"under {_money(q.max_price)}")
    if q.size:
        filters.append(f"in stock in {q.size}")

    def described(n: int) -> str:
        return " ".join([singular if n == 1 else plural, *filters])

    if not ranked:
        if q.color and q.color not in ("navy", "gray", "grey", "white", "cream", "blue"):
            return ChatAnswer(
                f"Sorry, we don't have {described(2)} right now. Most of our gear comes in navy, "
                "heather gray and cream. Want me to show you some of those?",
                [],
            )
        return ChatAnswer(
            f"I couldn't find any {described(2)} in the catalogue right now. "
            "Try another style, size or keyword, like a college name or a sport.",
            [],
        )

    top = [ProductCard.from_product(p, q.size) for p in ranked[:MAX_RESULTS]]
    prefix = f'I couldn\'t match "{" ".join(ignored)}", but here\'s what I have. ' if ignored else ""
    if q.sort == "asc":
        best = top[0]
        reply = f"The most affordable {described(1)} is the {best.name} at {_money(best.price)}."
    elif q.sort == "desc":
        best = top[0]
        reply = f"Our top-end pick for {described(2)} is the {best.name} at {_money(best.price)}."
    else:
        reply = f"I found {len(ranked)} {described(len(ranked))}."
    if len(ranked) > 1:
        reply += f" Here {'are' if len(top) > 1 else 'is'} the top {len(top)}:"
    return ChatAnswer(prefix + reply, top)
