"""Write the chat API contract (OpenAPI schema) to outputs/api_contract.openapi.json.

Run after changing anything in models.py that the chat uses:
  ../.venv/bin/python export_contract.py
test_contract.py fails if the saved file is out of date.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from main import app
from models import CHAT_CONTRACT_VERSION

OUT = Path(__file__).resolve().parent.parent / "outputs" / "api_contract.openapi.json"
CHAT_PATHS = ("/api/chat", "/api/chat/starters", "/api/chat/history")


def contract() -> dict:
    spec = copy.deepcopy(app.openapi())  # app.openapi() is cached; don't mutate the live schema
    spec["info"] = {
        "title": "Campus Customs chat API",
        "version": CHAT_CONTRACT_VERSION,
        "description": "Contract between the FastAPI backend and the website chat widget. See outputs/api_contract.md.",
    }
    spec["paths"] = {path: spec["paths"][path] for path in CHAT_PATHS}
    # Keep only the schemas the chat paths actually reference (directly or through other schemas).
    schemas = spec["components"]["schemas"]
    keep: set[str] = set()
    todo = [spec["paths"]]
    while todo:
        text = json.dumps(todo.pop())
        for name in schemas:
            if f'"#/components/schemas/{name}"' in text and name not in keep:
                keep.add(name)
                todo.append(schemas[name])
    spec["components"]["schemas"] = {name: schemas[name] for name in sorted(keep)}
    return spec


def render() -> str:
    return json.dumps(contract(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(OUT.parent.parent)}")
