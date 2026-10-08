# Usability Improvements (Problem 9)

Two usability improvements were added to the Campus Customs website, each with frontend and backend parts. For every change, this file shows **what was added**, **why it helps a shopper**, and **why it helps the business**. The design rationale is in `frontend_improvements.md`.

| # | Improvement | Shopper problem it fixes |
|---|---|---|
| 1 | **Bag + "Reserve for pickup at 57 Broadway"** | "Add to bag" said *"saved"* but saved nothing, and there was no way to act on a purchase decision |
| 2 | **Chat and product page work together** | The chat covered the product, you couldn't ask about the item you were viewing, and sizes were forgotten between chat and page |

---

## 1. Bag + Reserve for pickup

### What we added

**Frontend**

| Added | Where |
|---|---|
| **Bag tab with a live count** ("Bag (2)") in the header | `components/Layout.tsx` |
| **Real "Add to bag"** on product pages: adds the chosen size and quantity, says how many were added, with a "View bag →" link. Can't exceed stock | `pages/ProductDetail.tsx` |
| **Bag page** (`/bag`): photo, name, size, price each, quantity stepper, remove, line totals, subtotal | `pages/Bag.tsx` |
| **Live stock warnings** on each line: "Sold out in M. Choose another size" or "Only 1 left in L. Update to 1" | `pages/Bag.tsx` |
| **"Reserve for pickup at 57 Broadway"** button; guests see "Log in to reserve" and come straight back to their bag | `pages/Bag.tsx` |
| **Reservation confirmation** with a pickup code (e.g. `CC-CAF045`), the items, total due at pickup, and the store address | `pages/Bag.tsx` |
| **Bag kept for guests** in the browser, and **merged into the account** once when they log in | `bag.tsx`, `useBag.ts` |
| **"+ Add L to bag"** on chat product cards, for the size the shopper asked about | `components/ChatProductCard.tsx` |

**Backend**

| Added | Where |
|---|---|
| `bag_items` table: a logged-in shopper's saved bag | `bag.py` |
| `reservations` table: pickup requests with code, items, total, status | `bag.py` |
| `POST /api/bag/check`: prices every line and checks it against **live** `inventory.quantity` (works for guests; saves nothing) | `main.py`, `bag.py` |
| `GET / PUT /api/bag`: load or save the logged-in shopper's bag. Quantities are capped at stock (and 10 per line); unknown products are dropped | `main.py`, `bag.py` |
| `POST /api/bag/reserve`: re-checks stock. If anything changed it refuses with `409` and the corrected bag; otherwise it stores the reservation and empties the bag | `main.py`, `bag.py` |
| Data shapes `BagItem`, `BagLine`, `Bag`, `Reservation` | `models.py` |
| 9 tests: pricing, stock caps, privacy, login required, reserve, refusal when stock changes | `test_bag.py` |

### Why it helps the shopper
- **No more false promises.** The old message said an item was "saved" when it wasn't. Now what they add is really there when they come back, on any device once they're logged in.
- **Matches how Campus Customs actually sells.** There's no online checkout, so the site now supports the real path: pick items online, reserve, then try on and pay at 57 Broadway.
- **No wasted trip.** Stock is checked live on the Bag page and again at reservation. If a size sells out, they're told *which* item and how to fix it before they walk over.
- **Nothing is lost by logging in.** A guest's bag carries into their account at login.
- **Fewer steps from chat to bag.** If the assistant finds a hoodie in their size, one tap adds it.

### Why it helps the business
- **Turns browsing into commitments.** Reservations are a concrete action that brings shoppers into the store, where they can also try on and buy more.
- **New demand data it didn't have before:** which items and sizes are added to bags, reserved, or sold out while sitting in a bag. That helps with reorders and screen-printing runs.
- **Fewer frustrated pickups and fewer staff hours spent on them:** reservations are only accepted when every line is in stock at that moment.
- **Low risk.** No payments are taken online and inventory isn't changed automatically; staff confirm at the counter. The store can grow into online checkout later using the same bag.

### Evidence
- 9 backend tests pass.
- Browser walk-through (live system, database copy):
  1. A guest added 2 items.
  2. They logged in from the bag, and the bag merged into the account.
  3. One item was made to sell out; reserving was refused, and the Bag page flagged "Sold out in M".
  4. After removing it, the reservation went through with code `CC-CAF045`, saved in `reservations`, and the bag was emptied.

---

## 2. Chat and product page work together

### What we added

**Frontend**

| Added | Where |
|---|---|
| **Minimize on navigate:** clicking a chat card shrinks the chat to a **"Continue chat"** bubble, so the product page isn't covered; the conversation is kept | `components/ChatWidget.tsx`, `ChatProductCard.tsx` |
| **"Ask about this item"** button on every product page: opens the chat with quick questions for that product (colors, sizes in stock, price, similar items) | `pages/ProductDetail.tsx`, `useChatControl.ts`, `components/Layout.tsx` |
| **Size carried over:** chat cards open `/products/<id>?size=L` and the product page **preselects L**; every in-stock size chip on a chat card opens that size | `ChatProductCard.tsx`, `pages/ProductDetail.tsx` |
| **"Talking about: …" chip** at the top of the chat, showing which product "this" refers to | `components/ChatWidget.tsx` |
| **Full-screen chat on phones** with a clear "Back to page ×" button | `index.css` |

**Backend**

| Added | Where |
|---|---|
| `likely_subject()`: works out what "this" means (just opened a product page from the chat → that product; last reply showed one product → that one; otherwise the page they're on). The agent is now told this conclusion directly, with the reason | `assistant.py` |
| Context wording changed so the page the shopper **left** is no longer put in front of the model | `assistant.py` |
| Agent instructions: follow the stated "If they say 'this'…" conclusion unless the shopper names a different item | `prompts/prompts.md` |
| 3 tests, including the exact "opened a chat card, then asked about *this*" case | `test_context.py` |

### Why it helps the shopper
- **They can see what they asked about.** Opening a product from the chat no longer hides the photo behind the chat window, and the conversation is one tap away.
- **Questions start from the product.** "Ask about this item" gives ready-made questions, so they don't have to type "this hoodie" or the product's long name.
- **No repeated choices.** If they asked about size L, the page opens with L already selected and its stock shown.
- **Fewer misunderstandings.** The "Talking about" chip shows what the assistant will assume. The assistant uses the same rule as the chip, so "Do you have this in pink?" is answered about the product on screen.
- **Works on a phone**, where most students shop: a full-screen chat with an obvious way back.

### Why it helps the business
- **The chat is the site's standout feature; now it leads to sales.** The path is chat → product page in the right size → bag → reservation, with fewer steps and nothing to re-select.
- **Fewer wrong answers.** The assistant answering about the wrong item costs trust (and potentially a wasted trip). Before the fix, a live test answered about the hoodie the shopper had just *left*; after it, the answer matched the product on screen.
- **More questions per product page.** The "Ask about this item" entry point puts the assistant where purchase decisions happen.
- **No extra infrastructure.** It reuses the existing chat API and catalogue data, and the shop pages still work even when the chat is offline.

### Evidence
- **Tests:** 3 new context tests; 123 backend tests pass overall.
- **Browser walk-through with the live AI:**
  1. A `?size=M` link preselected M.
  2. "Ask about this item" opened the chat with four questions about the Basic Hoodie.
  3. A chat card opened the hockey hoodie in size L, and the chat minimized to "Continue chat".
  4. On reopening, the chip read "Talking about: Yale Sports Hoodie Hockey".
  5. "Do you have this in pink?" was answered about the hockey hoodie ("heather gray with navy blue lettering", matching the database).
  6. On a phone-sized screen the chat filled the screen and "Back to page" returned to the product.

---

## Summary for Campus Customs

| | Before | After |
|---|---|---|
| Acting on a choice | "Add to bag" showed a message; nothing was saved | Real bag (browser for guests, saved on the account when logged in) → pickup reservation with a code |
| Sold-out surprises | Found out at the store | Flagged on the Bag page and blocked at reservation |
| Chat → product | The chat window covered the product | The chat minimizes; the product opens in the size discussed |
| Asking about a product | Open the chat and type the product name | "Ask about this item" with ready-made questions |
| "Do you have **this** in pink?" | Could be answered about the wrong item | Chip and agent use the same rule; the answer names the right product |
| Phones | A small chat panel over the page | Full-screen chat with "Back to page" |
