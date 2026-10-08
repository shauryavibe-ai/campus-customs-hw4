# Problem 9: Two Front-end Improvements

Both come from things observed while building and testing the site (Problems 3–8), not from generic best practice.

---

## 1. Turn "Add to bag" into a real "Reserve for pickup" bag

**What's wrong today**
- On every product page, "Add to bag" only shows a message: *"1 × Basic Hoodie Big Yale (M) saved. Online checkout is coming soon…"*. **Nothing is actually saved.** A shopper who browses three items and comes back finds nothing, and the word "saved" isn't true.
- There's no bag icon or count in the header, so the main buying action on the site is a dead end.
- The store's real model is pickup or try-on at 57 Broadway (no online checkout), but the site never lets a shopper act on that.

**The improvement**
- A **bag** in the header (pink badge with the item count) and a **Bag page**: item photo, name, size, quantity, line price and total, plus remove and change-quantity controls.
- **Guests:** the bag lives in the browser (`localStorage`). **Logged-in shoppers:** it's saved to their account, so it follows them across devices, just like chat history does now.
- **"Reserve for pickup at 57 Broadway"** button on the Bag page: it confirms the items and sizes are still in stock and shows a reservation summary to show at the counter. No payment, matching how the store actually works today.
- **Stock-aware:** you can't add more than `inventory.quantity` for a size. If an item sells out while it's in the bag, the line is flagged "Sold out in M — choose another size".
- **Chat tie-in:** product cards in the chat get a small "Add to bag" for the size the shopper asked about. The agent never adds anything itself; the shopper always taps.

**Why it matters**
- It removes the one misleading message on the site.
- It gives shoppers a way to act, which is the main thing the site is missing.
- It measures intent: bag adds and reservations become numbers the store can track, which it can't do today.

**How we'd know it works**
- % of product-page visits that add to bag
- Reservations started vs. completed
- Bag items that go out of stock before pickup (an inventory signal)

**Effort:** medium.
- **Frontend:** a bag context (like the login context), Bag page, header badge, changes to the product page.
- **Backend:** `bag_items` table + 3 small routes for logged-in shoppers.
- **Reuse:** all the existing stock data and `ProductCard` shapes.

---

## 2. Make the chat and the product page work together

**What's wrong today**
- **The chat covers the product.** Clicking a product card in the chat opens the product page, but the chat panel stays open on top of it (380 × 560 px on desktop) and hides most of the large photo the shopper just asked to see. On phones the panel covers nearly the whole screen.
- **No way in from the page.** There's no way to start a chat *about* the product you're looking at. Shoppers have to open the bubble and type "this", relying on the agent to work out the page (it does, since Problem 8, but the shopper can't see that).
- **The chat's size knowledge stops at the card.** When the shopper asked about size M, the card highlights M, but clicking it lands on the product page with no size selected, so they have to pick M again.

**The improvement**
- **Minimize on navigate:** when a chat card is clicked, the panel collapses to its bubble, with a small "1 new" / "Continue chat" pill. The product page is fully visible, and one tap brings the conversation back exactly as it was. On phones the open chat becomes a full-screen sheet with a clear "Back to product" button.
- **"Ask about this item" on every product page:** a pink outline button under the size picker. It opens the chat with quick questions for *this* product: "Is it true to size?", "What colors does it come in?", "Do you have it in M?", "Similar items?". The agent already gets the page context, so answers are about the right item.
- **Keep the size:** chat cards link to `/products/<id>?size=M`, and the product page preselects that size and shows its stock ("Only 5 left in M"). The size chips on chat cards become clickable shortcuts.
- **A visible "talking about" chip:** a small chip at the top of the chat shows what the assistant thinks "this" is ("Talking about: Basic Hoodie Big Yale ✕"), so the shopper can see it and clear it. It uses the same context the agent already receives.

**Why it matters**
- The chat is the site's most distinctive feature, but right now it fights the product page instead of helping it.
- These changes keep the conversation and the product on screen together, cut the steps from "the assistant found it" to "I'm looking at it in my size", and make the agent's understanding of "this" visible to the shopper.

**How we'd know it works**
- Chat card → product page → add to bag rate
- Use of "Ask about this item"
- Fewer follow-up messages like "no, I meant the other one"

**Effort:** small to medium. It's all frontend:
- chat widget state (open / minimized / full-screen)
- a `?size=` query parameter on the product page
- one new button
- the context chip (reads the current page + last cards already tracked in the widget)

No backend or API contract changes are needed.

---

## Suggested order

Build **#2 first**: it's small, frontend-only, and fixes a visible issue. Then **#1**, which can reuse #2's "Add to bag from chat card" entry point.

---

## Status: both built (Problem 9, Prompt 2)

### #2 Chat ↔ product page: built
- **Minimize on navigate:** clicking a chat card closes the panel to a **"Continue chat"** bubble, and the conversation is kept. On phones the chat opens as a full-screen sheet with a **"Back to page ×"** button.
- **"Ask about this item"** button on every product page opens the chat with four product questions (colors, sizes in stock, price, similar items).
- **Keep the size:** chat cards link to `/products/<id>?size=M` and the product page preselects that size. Every in-stock size chip on a chat card opens the product in that size.
- **"Talking about: …" chip** at the top of the chat. It uses the same rule as the agent (`assistant.likely_subject`), and the agent is now told that conclusion directly, so the chip and the answer always agree. *Change from the proposal:* no ✕ on the chip, since dismissing it wouldn't change what the agent assumes. The tooltip says to name another item to switch.

### #1 Bag + Reserve for pickup: built
- **Bag tab** in the header with a live count. **`/bag`** page with photo, size, quantity stepper (capped at stock and 10), remove, line totals and subtotal.
- **Where the bag lives:** guests' bags are kept in the browser. Logged-in shoppers' bags are saved in `bag_items`, and a guest bag is merged into the account once on login.
- **Live stock:** the Bag page checks every line with the server (`POST /api/bag/check`). Lines that sold out or dropped below the quantity are flagged with a fix ("Choose another size" / "Update to N").
- **Reserve for pickup at 57 Broadway** (logged in; guests get "Log in to reserve" and come back to the bag). The server re-checks stock, refuses with `409` + the corrected bag if anything changed, otherwise stores a `reservations` row and shows a code like `CC-CAF045`. Inventory isn't changed and there's no payment; staff confirm at the counter.
- **Add to bag from chat cards** for the size the shopper asked about ("+ Add L to bag").

### Verified
- **Tests:** 123 backend tests pass (9 new bag tests, 3 new "this" tests).
- **Browser walk-through with the live AI on a database copy:** all 13 steps pass, including:
  - "Do you have this in pink?" after opening a chat card answers about the product just opened
  - a sold-out line is flagged and blocks reserving until fixed
