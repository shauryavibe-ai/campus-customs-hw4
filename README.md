# Campus Customs: Yale apparel store with an AI shop assistant

Homework 4, AI Foundations for Managers (Yale SOM). A full-stack shop for **Campus Customs**, the Yale apparel store at 57 Broadway, New Haven:

- **React + TypeScript website** (Vite) in a dark Yale-blue theme: catalogue with filters, product pages with live stock by size, accounts, a bag with **"Reserve for pickup at 57 Broadway"**.
- **FastAPI backend** with SQLite: accounts with PBKDF2-hashed passwords and HttpOnly sessions, saved bags and reservations.
- **"Dan", an AI shop assistant** (a Yale bulldog drawn in SVG): a Pydantic AI agent on `gpt-6-luna` via Portkey. It answers only from the live database through typed tools, never invents prices or stock (checked), shows product cards, understands "this" from the page and the cards it showed, remembers logged-in shoppers' chats, and logs every run to an append-only audit trail.

**Full documentation:** [`outputs/harness.md`](outputs/harness.md) covers the architecture, the agent loop, models, tools, safety rules, limits, API routes and how to run it. See also [`outputs/api_contract.md`](outputs/api_contract.md), [`outputs/usability.md`](outputs/usability.md), [`outputs/design.md`](outputs/design.md) and the live test report [`outputs/app_check.md`](outputs/app_check.md). Every prompt used to build this is in [`ai_prompts.md`](ai_prompts.md).

## Not included (on purpose)

- **`data/campus_customs.db`**: the course database contains user emails, password hashes and chat history, so it's git-ignored. Place your own copy at `data/campus_customs.db` (from the course `data.zip`) before running the backend.
- **`.env`**: your Portkey API key. Copy `.env.example` to `.env` and add your key. It's git-ignored.
- Exports with personal data (`outputs/users.json`, `outputs/chat_messages.json`), the live audit trail, and local test logins.

## Run it

From this folder:

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env   # then put your PORTKEY_API_KEY in .env
```

Then, in two terminals:

```bash
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000
```
```bash
cd frontend && npm run dev
```

Open **http://localhost:5173**. API docs: http://127.0.0.1:8000/docs.

## Test it

```bash
cd backend && ../.venv/bin/python -m pytest -q        # 132 unit tests (fake AI, temporary databases)
.venv/bin/python scripts/app_check.py                 # live end-to-end check, writes outputs/app_check.html
```

## Layout

```
backend/    FastAPI app, Pydantic AI agent (assistant.py, tools.py, prompts/prompts.md), models.py, tests
frontend/   React + TypeScript site (Vite)
data/       product photos (the database is not committed)
outputs/    documentation, API contract, catalogue/inventory exports used by the site, test reports
scripts/    live end-to-end check
```
