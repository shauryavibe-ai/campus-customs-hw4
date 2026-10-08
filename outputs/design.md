# Design Update (Problem 10): Yale Blue and Dan the Bulldog

## Summary

We changed the website's colors to align with the official **Yale** and **Campus Customs** colors, and gave the chat assistant a **bulldog**, a nod to Handsome Dan, Yale's official mascot.

- **Yale colors:** the site now looks and feels like Yale. It matches what shoppers already associate with the university and with Campus Customs' own Yale merchandise, instead of a generic black-and-pink look.
- **The bulldog:** it gives the website the true feeling of being at Yale, and it differentiates the official Campus Customs site from fake or knock-off merchandise websites, which can copy product photos but not a recognizable, consistent Yale character.
- **Students love the bulldog.** Students we have talked to love the bulldog, which makes them more likely to start a conversation with the assistant. More conversations mean more shoppers finding the right item, size and color.

---

## 1. Colors: aligned with Yale and Campus Customs

| Role | Before | After | Used for |
|---|---|---|---|
| Page background | near-black `#0b0b0e` | near-black **navy** `#0a1220` | every page |
| Cards / panels | `#15151a` | dark navy `#121c2e` | product cards, forms, chat |
| **Brand color** | pink `#ff4fa3` | **Yale Blue `#00356B`** | announcement bar, "CC" logo, chat header, Dan's collar |
| Buttons | pink | Yale medium blue `#286DC0` (white text) | "Shop the catalog", "Add to bag", "Reserve", chat send, selected size |
| Highlights | pink | light blue `#6FA8FF` | prices, headings' accent words, links, focus rings, active tab |
| Small alerts | pink | pink, **only** for low stock | "Only 2 left in M", low-stock size chips, bag stock warnings |
| Browser tab | pink "CC" on black | white "CC" on Yale Blue | favicon and theme color |

**Why:**
- **Recognition and trust.** Yale Blue is the color shoppers already connect with Yale and with the Campus Customs storefront on Broadway. Seeing it tells a parent or student they're in the right place.
- **Consistency with the products.** Most of the catalogue is navy and heather gray, so the photos now sit naturally on the page instead of clashing with hot pink.
- **Pink still means something.** Keeping pink only for low stock makes scarcity stand out, because it's the one warm color on the page.

**Readability (WCAG contrast; AA needs 4.5:1):**

| Text | Contrast |
|---|---|
| White on the Yale Blue bar | 12.2:1 |
| White on blue buttons | 5.2:1 |
| Light-blue prices and links on the page | 7.8:1 |
| Body text | 17.3:1 |
| Muted text | 7.6:1 |
| Pink low-stock notes | 7.3:1 |

All of these pass AA.

**Project rule:** `AGENTS.md` normally requires black-and-pink. A scoped exception for this Campus Customs site (dark Yale-blue style, pink only for small accents) was approved and recorded there, so other projects keep the original rule.

---

## 2. Dan the Bulldog: the chat assistant's mascot

**What shoppers see**

| Where | What |
|---|---|
| Chat button (every page) | Dan's face with **"Ask Dan"** ("Continue chat" once a conversation has started) |
| Chat header | Dan's avatar: **"Dan · Campus Customs"** |
| Greeting | *"Woof! I'm Dan, the Campus Customs bulldog. What do you need today? What products are you looking for?"* (with the shopper's first name when logged in) |
| Each reply | A small Dan avatar next to the reply bubble |
| While the AI works | Dan tilts his head: *"Dan is sniffing out the catalogue…"* |

**How he's built**
- **Drawn in code (inline SVG), with no image file**, as `AGENTS.md` requires for creatures (`frontend/src/components/Bulldog.tsx`). He's a classic Yale bulldog: cream face with a tan eye patch, folded ears, wrinkled brow, droopy eyes, big nose, the bulldog underbite, and a **Yale Blue collar with a white "Y" tag**.
- **Gentle animation:** he blinks every few seconds and tilts his head while "thinking". Both animations switch off for shoppers who turn on the system's "reduce motion" setting.
- **The AI knows about the character:** its instructions (`backend/prompts/prompts.md`, Voice) say it appears as Dan. It can be lightly playful (an occasional "woof"), but it never claims to be a real dog or the real Handsome Dan, and it stays accurate about products, prices and stock.

**Why**
- **The true feeling of being at Yale.** The bulldog is the most recognizable Yale symbol after the "Y". Putting him in the chat makes the website feel like part of campus, not a generic online store.
- **Stands apart from fake websites.** Unofficial and knock-off merch sites can copy product photos, but a consistent, friendly Yale bulldog character that knows the real Campus Customs stock (and the shop at 57 Broadway) is hard to fake. It signals "this is the real store".
- **Students love the bulldog, so they're more likely to talk.** Students we have talked to love the bulldog. A friendly character invites people to start a chat in a way a plain "Chat with us" button doesn't. Since the assistant is what helps shoppers find the right item, size and color (and add it to their bag), more conversations should mean more helped shoppers and more reservations.
- **Personality without getting in the way.** Dan is small and only appears in the chat. Product pages, prices and stock stay clear and businesslike.

---

## 3. What changed in the code

| File | Change |
|---|---|
| `frontend/src/index.css` | New Yale-blue palette (`--yale`, `--primary`, `--accent`, …); every pink fill, line and tint mapped to blue; pink kept for low stock; bulldog styles and animations |
| `frontend/src/components/Bulldog.tsx` | **New:** Dan, drawn in SVG |
| `frontend/src/components/ChatWidget.tsx` | Dan on the chat button, header, replies and "thinking" indicator; "Woof!" greeting |
| `frontend/src/pages/ProductDetail.tsx` | Low-stock note uses the pink `low-stock` style |
| `frontend/public/favicon.svg`, `frontend/index.html` | Yale Blue favicon and browser theme color |
| `backend/prompts/prompts.md` | The agent knows it appears as Dan, and how to stay accurate in character |
| `AGENTS.md` | Scoped exception for the Campus Customs color scheme |

Nothing else changed in behavior: all 123 backend tests still pass, and the shop, bag and chat work as before.
