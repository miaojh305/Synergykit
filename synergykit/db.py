"""SQLite persistence layer for saved deals."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "synergykit.db"


def _connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create the deals table if it doesn't exist."""
    conn = _connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            payload     TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_deal(deal_payload: dict, name: str, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Insert a deal and return its row id."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    cur = conn.execute(
        "INSERT INTO deals (name, payload, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (name, json.dumps(deal_payload), now, now),
    )
    conn.commit()
    deal_id = cur.lastrowid
    conn.close()
    return deal_id


def list_deals(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    """Return all deals (without full payload) ordered by most recent first."""
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT id, name, created_at, updated_at FROM deals ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_deal(deal_id: int, db_path: Path = DEFAULT_DB_PATH) -> dict | None:
    """Load a single deal by id, parsing the JSON payload."""
    conn = _connect(db_path)
    row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"])
    return d


def delete_deal(deal_id: int, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Delete a deal by id."""
    conn = _connect(db_path)
    conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    conn.commit()
    conn.close()
