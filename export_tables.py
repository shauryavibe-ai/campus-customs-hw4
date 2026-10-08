"""Export every table in data/campus_customs.db to a JSON file in outputs/."""

import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "data" / "campus_customs.db"
OUT_DIR = HERE / "outputs"

# TEXT columns that store JSON; decoded so consumers get real lists/objects.
JSON_COLUMNS = {
    "catalogue": {"colors", "search_tags"},
    "chat_messages": {"products_json"},
}

# Columns never written out (credentials stay in the database only).
EXCLUDED_COLUMNS = {
    "users": {"password_hash"},
}


def export_table(conn: sqlite3.Connection, table: str) -> int:
    rows = conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
    json_cols = JSON_COLUMNS.get(table, set())
    excluded = EXCLUDED_COLUMNS.get(table, set())

    records = []
    for row in rows:
        record = {}
        for key in row.keys():
            if key in excluded:
                continue
            value = row[key]
            if key in json_cols and value is not None:
                value = json.loads(value)
            record[key] = value
        records.append(record)

    out_path = OUT_DIR / f"{table}.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    return len(records)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    tables = [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for table in tables:
        count = export_table(conn, table)
        print(f"{table}: {count} rows -> outputs/{table}.json")
    conn.close()


if __name__ == "__main__":
    main()
