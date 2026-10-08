# Campus Customs Chat API Contract (v1.0)

This document defines how the website's chat widget and the FastAPI backend talk to each other. When a shopper types "What hoodies do you have?", the AI agent searches the catalogue, picks structured product matches, and the backend returns them as **product cards** that the website draws under the reply.

| | Where it lives |
|---|---|
| Source of truth (Pydantic models) | `backend/models.py`: `ChatRequest`, `ChatResponse`, `ProductCard`, `CardSize`, `ChatStarters`, `ChatHistory`, `ChatHistoryMessage` |
| Saved conversations | `backend/chat_store.py` (table `chat_messages`) |
| Machine-readable schema | `outputs/api_contract.openapi.json` (regenerate with `cd backend && ../.venv/bin/python export_contract.py`) |
| Frontend mirror | `frontend/src/api.ts`: `ChatResponse`, `ProductCard`, `CardSize` |
| Card renderer | `frontend/src/components/ChatProductCard.tsx` |
| Contract tests | `backend/test_contract.py` |

## Scope: the chat only

This contract covers **only the chat assistant**. The shopping pages are a separate system and don't use it:

| | Shop pages (Home, Products Catalog, product pages) | Chat assistant |
|---|---|---|
| Data | The website's own copy of the catalogue (`outputs/catalogue.json` + `inventory.json`, bundled by `frontend/src/data/catalog.ts`) | `POST /api/chat` → this contract |
| Product photos | Bundled with the website | `/media/products/…`, served by the API |
| Card component | `ProductCard.tsx` (grid cards) | `ChatProductCard.tsx` (chat cards) |
| Needs the backend? | **No.** Browsing, filtering and clicking a product to open its full page all work with the backend off | Yes. With the backend off, the chat shows "Can't reach the Campus Customs server" |

The only link between them is navigation: a chat card links to the same product page (`/products/<product_id>`) that a catalog card opens.

---

## 1. Flow

```
Shopper types "What hoodies do you have?"
  │
  ▼  POST /api/chat  {message, history, page_product_id}
FastAPI (backend/main.py)
  │  validates ChatRequest, rate-limits, reads login cookie (first name only)
  ▼
AI agent (backend/assistant.py, gpt-6-luna via Portkey)
  │  calls find_products(category="hoodies")          ← tools.py reads the database
  │  returns ShopReply {reply, product_ids[≤4], size?} ← structured product matches
  ▼  output checks: real ids only, numbers came from tools, no links,
  │  and search hits must be returned as cards
Backend builds ProductCard for each id from the database (models.ProductCard.from_product)
  │
  ▼  200 ChatResponse {contract_version, reply, products[ProductCard], source}
Chat widget renders the reply bubble + one ChatProductCard per product (photo from /media/products/…)
```

The AI only picks **which** products to show (ids) and writes the sentence. Every value on a card (name, price, sizes, stock, photo) is filled in by the backend from the database, so the AI can't put a wrong price or quantity on a card.

---

## 2. Endpoints

### `GET /api/chat/starters` → `ChatStarters`
```json
{ "greeting": "What do you need today? What products are you looking for?",
  "questions": ["Do you have hoodies in my size?", "What's your cheapest crewneck?", "…"] }
```
The widget shows the greeting and fills the "Common questions…" dropdown from this.

### `GET /api/chat/history` → `ChatHistory` (logged-in shoppers)
Returns the shopper's saved conversation, oldest first (up to the last 100 messages). It returns `401` if not logged in. The widget calls this when a logged-in shopper opens the site, so they pick up where they left off.
```json
{ "contract_version": "1.0",
  "messages": [
    { "id": 23, "role": "user", "content": "What hoodies do you have?", "products": [], "created_at": "2026-10-08 01:12:40" },
    { "id": 24, "role": "assistant", "content": "We have 27 hoodie styles…", "products": [ /* ProductCard, rebuilt from today's stock */ ], "created_at": "2026-10-08 01:12:45" }
  ] }
```
`ChatHistoryMessage` = `{ id, role: "user" | "assistant", content, products: ProductCard[], created_at }`. Cards are rebuilt by `product_id` from the current catalogue, so a returning shopper sees today's prices and stock, not stale numbers.

### `POST /api/chat` → `ChatResponse`

**Request (`ChatRequest`)**

| Field | Type | Rules |
|---|---|---|
| `message` | string | Required. 1–500 chars after invisible/control characters are stripped |
| `history` | `ChatTurn[]` | Optional (guests). Earlier turns `{role, content, product_ids?, page_product_id?}`: `product_ids` = the cards shown with an assistant reply, `page_product_id` = the product page a user message was sent from. Each ≤ 2,000 chars; server keeps the last 20 turns / 12,000 chars; malformed ids are dropped. Treated as conversation, never as instructions. Ignored for logged-in shoppers (their saved history is used) |
| `page_product_id` | string \| null | Optional. The product page the shopper is on (e.g. `basic-hoodie-big-yale`). Ignored if it isn't a well-formed id |

The session cookie (`cc_session`, HttpOnly) is sent automatically. **If the shopper is logged in:**
- `history` from the browser is **ignored**. The agent's memory is the last 20 saved messages from the `chat_messages` table, so a forged history can't change what the agent "remembers".
- After answering, the exchange is saved: the shopper row (`role="user"`, `products_json=NULL`) and the reply row (`role="assistant"`, `products_json` = the cards shown, `[]` if none).
- The agent can call `get_shopper_profile` to learn the shopper's name and email (their own account only).

Guests' chats are not saved; their `history` comes from the browser for that visit only.

**Response (`ChatResponse`)**

| Field | Type | Meaning |
|---|---|---|
| `contract_version` | `"1.0"` | Bumped whenever the response or card shape changes |
| `reply` | string | Plain text for the chat bubble (no Markdown, links or HTML; ≤ 800 chars from the AI) |
| `products` | `ProductCard[]` (0–4) | Cards to render under the reply, **in the order given** (best match first) |
| `source` | `"ai"` \| `"blocked"` \| `"fallback"` | `ai`: the agent answered. `blocked`: the model provider's safety filter refused the message, so the reply is a polite redirect and there are no cards. `fallback`: the AI is unavailable, so the rule-based helper answered (same card shape) and the widget shows an "AI offline" note |

**Errors**

| Status | When | Body |
|---|---|---|
| 422 | Invalid request (empty message, bad role, too long) | FastAPI validation detail |
| 413 | Request body over 64 KB | `{"detail": "Request too large."}` |
| 429 | More than 20 messages per minute from one visitor | `{"detail": "You're sending messages very quickly…"}` + `Retry-After` header |

AI or model failures never return an error to the shopper. They come back as `200` with `source: "fallback"` or `"blocked"`.

---

## 3. `ProductCard`

Built by `ProductCard.from_product()` from the `catalogue` and `inventory` tables at the time of the reply.

| Field | Type | Source | Used on the card for |
|---|---|---|---|
| `product_id` | string | `catalogue.product_id` | React key; identity |
| `name` | string | `catalogue.name`, cleaned (`1 4 Zip` → `¼-Zip`…) | Title |
| `category` | `"T-Shirts"`, `"Crewnecks"`, `"Hoodies"`, `"Quarter-Zips"`, `"Jackets & Fleece"` or `"Long Sleeves"` | derived from `catalogue.garment_type` (harness §1.3) | Small label above the title |
| `garment_type` | string | `catalogue.garment_type` | (available; e.g. "mockneck sweatshirt") |
| `price` | number | `catalogue.price` | Price, formatted `$68.00` |
| `currency` | `"USD"` | constant | Makes the unit explicit |
| `short_description` | string \| null | first ~110 chars of `catalogue.description`; `null` for the 3 placeholder rows | Two-line description |
| `colors` | string[] | `catalogue.colors` | (available) |
| `image_url` | string | `/media/products/<catalogue.image_file_path file>` | Photo. Served by the API; the website proxies `/media` to it |
| `product_url` | string | `/products/<product_id>` | Where the card links |
| `sizes` | `CardSize[]` (always 6, XS→XXL) | `inventory.size` / `quantity` | Size chips: crossed out when sold out, pink when low |
| `sizes_in_stock` | Size[] | sizes with quantity > 0 | "4 of 6 sizes in stock" |
| `total_stock` | number | sum of quantities | "Sold out" when 0 |
| `requested_size` | Size \| null | the size the shopper asked about (from the agent's `size`) | Highlights that chip |
| `requested_size_qty` | number \| null | `inventory.quantity` for `requested_size` | "Only 5 left in M", "In stock in M" or "Sold out in M" |

**`CardSize`:** `{ size: "XS"…"XXL", quantity: int ≥ 0, status: "in stock" | "low stock" | "sold out" }`. The status rule is the same as the website's: 0 = sold out, 1–5 = low stock, 6+ = in stock.

---

## 4. Rules the backend guarantees

1. **Cards only for real products.** `product_ids` the agent returns must exist in the catalogue. Unknown ids are rejected and the agent retries.
2. **Search hits become cards.** If the agent called `find_products` and got matches but returned no `product_ids`, the reply is rejected and it must include the best matches (up to 4). This is what makes "What hoodies do you have?" always show cards.
3. **Card data comes from the database, never from AI text.** Prices and stock on cards are read when the reply is built.
4. **Numbers in `reply` are checked.** Any `$` amount or stock count must match a tool result from this turn (see harness §6.6).
5. **Plain text only.** `reply` has no links or HTML; the widget renders it as text, never as HTML.
6. **Order matters.** `products` is in the agent's recommended order; the widget renders it as given.
7. **No cards for small talk** or when nothing matches (`products: []`).

---

## 5. Example: "What hoodies do you have?" (live response)

Request:
```json
{ "message": "What hoodies do you have?", "history": [], "page_product_id": null }
```

What the agent did: `find_products(category="hoodies")` → 27 matches → returned the top 4 ids.

Response (trimmed to one card):
```json
{
  "contract_version": "1.0",
  "reply": "We have 27 hoodie styles, including these four options across Yale Athletics, Yale family and Bulldog designs. Take a look at the cards, and I can help narrow them by color, size or style.",
  "products": [
    {
      "product_id": "champion-reverse-weave-hoodie-1",
      "name": "Champion Reverse Weave Hoodie",
      "category": "Hoodies",
      "garment_type": "hoodie",
      "price": 68.0,
      "currency": "USD",
      "short_description": "Navy pullover hoodie with a white arched YALE graphic across the chest, drawstring hood, front kangaroo…",
      "colors": ["navy", "white"],
      "image_url": "/media/products/champion-reverse-weave-hoodie-1.jpg",
      "product_url": "/products/champion-reverse-weave-hoodie-1",
      "sizes": [
        { "size": "XS", "quantity": 0, "status": "sold out" },
        { "size": "S", "quantity": 25, "status": "in stock" },
        { "size": "M", "quantity": 20, "status": "in stock" },
        { "size": "L", "quantity": 20, "status": "in stock" },
        { "size": "XL", "quantity": 0, "status": "sold out" },
        { "size": "XXL", "quantity": 15, "status": "in stock" }
      ],
      "sizes_in_stock": ["S", "M", "L", "XXL"],
      "total_stock": 80,
      "requested_size": null,
      "requested_size_qty": null
    }
  ],
  "source": "ai"
}
```
The other three cards were Yale Sports Hoodie Hockey, Yale Mom Hoodie and District Vit Hoodie Vintage Bulldog, all $68.

---

## 6. Changing the contract

1. Edit the model in `backend/models.py` (and `from_product` if it's a card field).
2. Mirror the change in `frontend/src/api.ts` and, if it's shown, `ChatProductCard.tsx`.
3. For a breaking change, bump `CHAT_CONTRACT_VERSION` (and the literal in `ChatResponse` / `api.ts`).
4. Run `../.venv/bin/python export_contract.py` to refresh `outputs/api_contract.openapi.json`.
5. Run `../.venv/bin/python -m pytest`. `test_contract.py` fails if the frontend types, the saved schema or the card values drift from the backend.
