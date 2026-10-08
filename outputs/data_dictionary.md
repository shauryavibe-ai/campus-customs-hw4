# Campus Customs — Data Dictionary

Source: `data/campus_customs.db` (SQLite), plus 102 product photos in `data/products/`.

| Table | Rows | What it holds |
|---|---|---|
| `catalogue` | 102 | One row per product (the store's catalog) |
| `inventory` | 612 | Stock on hand per product per size (102 products × 6 sizes) |
| `users` | 3 | Registered shopper accounts |
| `chat_messages` | 22 | Chat history between shoppers and the AI shopping assistant |
| `sqlite_sequence` | 3 | SQLite's internal autoincrement counters (not business data) |

Relationships: `inventory.product_id → catalogue.product_id`, and `chat_messages.user_id → users.id`. There are no orphan rows in either relationship.

---

## `catalogue`

| Field | Type | Meaning | Notes |
|---|---|---|---|
| `product_id` | TEXT, PK | URL-style slug that uniquely identifies the product, e.g. `basic-hoodie-big-yale` | Always equals the image filename without `.jpg` |
| `name` | TEXT | Display name, e.g. "Basic Hoodie Big Yale" | Built from the slug, so some names look odd ("Champion Reverse Weave Hoodie 1", "Yale Sports Creqneck Field Hockey") |
| `garment_type` | TEXT | Kind of garment | Free text with **22 variants** for about 7 real categories (e.g. "short-sleeve T-shirt", "short-sleeve t-shirt", "t-shirt"). Needs normalizing before it can drive category filters |
| `description` | TEXT | One-sentence visual description of the item (color, cut, graphic) | Seems AI-generated from the photo. 3 products have a placeholder description instead ("Vision blocked; filename-based stub") |
| `colors` | TEXT (JSON array) | Colors that appear on the garment, e.g. `["navy blue", "white"]` | Not normalized ("navy" vs "navy blue", "gray" vs "heather gray"). Empty `[]` for the same 3 placeholder products |
| `search_tags` | TEXT (JSON array) | Keywords for search/recommendation, e.g. `["Yale hoodie", "navy hoodie", …]` | Placeholder products only have tags taken from the filename |
| `image_file_path` | TEXT | Relative path to the photo, e.g. `products/basic-hoodie-big-yale.jpg` | Relative to `data/`. All 102 files exist |
| `price` | REAL | Price in USD | Set by garment class, not by item: T-shirts $32, mockneck/long-sleeve performance shirts/basic hooded sweatshirts $45, crewnecks $58, hoodies $68, quarter-zips $72, full-zip hoods $88, fleeces/jackets $98 |

**Placeholder products (incomplete data):** `benjamin-franklin-t-shirt`, `berkeley-sweater-fleece-jacket`, `timothy-dwight-college-crewneck`.

## `inventory`

| Field | Type | Meaning | Notes |
|---|---|---|---|
| `id` | INTEGER, PK, autoincrement | Row ID | 1–612 |
| `product_id` | TEXT, FK → `catalogue` | Which product | |
| `size` | TEXT | Size label | Always one of `XS, S, M, L, XL, XXL` |
| `quantity` | INTEGER | Units in stock for that product and size | Only uses the values 0, 2, 5, 8, 12, 15, 20, 25 (synthetic data). 145 of 612 size rows are **0 (out of stock)**. No product is fully sold out; totals range from 9 to 116 units, with 5,920 units overall |

`UNIQUE(product_id, size)`, so each product has exactly one row per size.

## `users`

| Field | Type | Meaning | Notes |
|---|---|---|---|
| `id` | INTEGER, PK, autoincrement | User ID | 1–3 |
| `name` | TEXT | Full name | Duplicates `first_name` + `last_name` |
| `email` | TEXT, UNIQUE | Login identifier | |
| `password_hash` | TEXT | Salted PBKDF2 password hash (never plaintext) | Must never be shown or sent to the AI model |
| `created_at` | TEXT | Signup timestamp, `YYYY-MM-DD HH:MM:SS` | SQLite `datetime('now')`, so it's in **UTC** |
| `first_name` | TEXT, nullable | First name | Added later with `ALTER TABLE`; the assistant uses it to greet users by name |
| `last_name` | TEXT, nullable | Last name | Added later with `ALTER TABLE` |

Current users: Test User (id 1), Ada Lovelace (id 2, no chats), Tauhid Zaman (id 3).

## `chat_messages`

| Field | Type | Meaning | Notes |
|---|---|---|---|
| `id` | INTEGER, PK, autoincrement | Message ID; gives the conversation order | |
| `user_id` | INTEGER, FK → `users` | Which shopper's conversation this message belongs to | One continuous thread per user (no separate session/thread ID) |
| `role` | TEXT | `user` (shopper) or `assistant` (AI) | Messages strictly alternate user → assistant |
| `content` | TEXT | Message text | Assistant replies use Markdown (`**bold**`, bullet lists) |
| `products_json` | TEXT (JSON), nullable | Snapshot of the product cards the assistant showed with its reply | `NULL` on user messages; `[]` when no products were shown. Each element is a full catalogue row **plus** `image_url` (`/media/products/…`), `inventory` (list of `{size, quantity}`), and `total_stock`, as they were when the reply was sent |
| `created_at` | TEXT | Timestamp (UTC) | |

### What the chat logs show
- Shoppers ask by category ("hoodies", "fleeces"), color ("in pink?"), price ("cheapest fleece"), mascot/keyword ("Handsome Dan", "bulldog"), and products they're looking at ("this hoodie is cool right").
- Gaps: the store has no shorts, and "Handsome Dan" isn't tagged anywhere, even though there are bulldog products.
- One assistant reply called a $72 quarter-zip the "cheapest fleece", which shows how inconsistent `garment_type` labels can mislead the AI.

---

## Added in Problem 4: accounts & login

### `users`: how new accounts are written
- Sign-up inserts `first_name`, `last_name`, `name` (= first + last), a lower-cased `email`, and `password_hash`. `created_at` is filled in by SQLite (UTC).
- **`password_hash` format for new accounts:** `pbkdf2_sha256$600000$<32-hex-char random salt>$<64-hex-char digest>` (PBKDF2-HMAC-SHA256, 600,000 iterations, unique salt per user). The plain password is never stored.
- The 3 original seed users use an older format, `pbkdf2_sha256$<salt>$<digest>`, which doesn't record the iteration count. Testing with the Test User's known password confirmed it was **120,000 iterations** with the salt used as text, which is now the built-in default for these hashes. On a user's first successful login, their hash is automatically upgraded to the 600,000-iteration format (the Test User's already has been).

### `sessions` (new table, created automatically on first login)

| Field | Type | Meaning |
|---|---|---|
| `token_hash` | TEXT, PK | SHA-256 of the random session token kept in the browser's HttpOnly `cc_session` cookie. The raw token is never stored |
| `user_id` | INTEGER, FK → `users` | Who is logged in |
| `created_at` | TEXT (UTC) | When the session started |
| `expires_at` | TEXT (UTC) | Sessions last 7 days; expired rows are cleaned up at the next login |

---

## Added with saved chat history: `chat_messages` is now written by the app

- Every chat exchange of a **logged-in** shopper is saved as two rows: `role='user'` (`products_json` NULL) and `role='assistant'` (`products_json` = JSON list of the product cards shown, `[]` if none; current cards use the `models.ProductCard` shape). `created_at` is filled in by SQLite (UTC).
- Guests' chats are not saved.
- When a shopper returns, `GET /api/chat/history` reads their rows back. Cards are rebuilt by `product_id` from today's catalogue, so the 22 original rows (older product-snapshot format) load fine too.
- The agent's conversation memory for logged-in shoppers is the last 20 of these rows (`backend/chat_store.py`).
- New nullable column **`chat_messages.page_product_id`** (added automatically): for a shopper's message, the product page they were on when they sent it, so the agent can tell what "this" meant later. `NULL` for replies and for the original 22 rows. See harness §7.

---

## Added in Problem 9: bag and pickup reservations (created automatically by `backend/bag.py`)

| Table | Columns | Meaning |
|---|---|---|
| `bag_items` | `user_id`, `product_id`, `size`, `quantity` (>0), `updated_at`; PK (user_id, product_id, size) | A logged-in shopper's saved bag. Guests' bags stay in the browser |
| `reservations` | `id`, `code` (unique, e.g. `CC-CAF045`), `user_id`, `items_json` (the checked bag lines), `total`, `status` (`pending`), `created_at` | "Reserve for pickup at 57 Broadway" requests. They don't change `inventory`; staff confirm at the counter |
