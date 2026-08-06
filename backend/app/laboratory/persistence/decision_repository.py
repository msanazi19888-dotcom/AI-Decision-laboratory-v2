"""
Persists every replenishment decision so decision history is actually
kept, not recomputed and discarded on every request. Uses SQLite via
the Python standard library -- deliberately not adding SQLAlchemy or
a full database server, since this project's own working rule is
"don't add a technology unless the current version genuinely needs
it," and a single-file embedded database is the right amount of
machinery for a project of this scope.

This also opens the door to real evaluation later: with decisions on
record, actual outcomes (was the recommendation followed? did a
stockout occur anyway?) could eventually be recorded against them --
that's future work, not built here, but this table is what it would
be built on.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "decisions.db"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                product_name TEXT,
                created_at TEXT NOT NULL,
                requested_quantity REAL,
                final_position TEXT,
                confidence REAL,
                reason TEXT,
                department_votes_json TEXT,
                full_response_json TEXT
            )
            """
        )
        conn.commit()


def save_decision(product_id: str, product_name: str, decision_context: dict,
                   final_decision: dict, full_response: dict) -> int:
    init_db()
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO decisions (
                product_id, product_name, created_at, requested_quantity,
                final_position, confidence, reason, department_votes_json,
                full_response_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                product_name,
                datetime.now(timezone.utc).isoformat(),
                decision_context.get("requested_quantity"),
                final_decision.get("final_position"),
                final_decision.get("confidence"),
                final_decision.get("reason"),
                json.dumps(final_decision.get("department_votes", {})),
                json.dumps(full_response),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_decisions(limit: int = 50) -> list[dict]:
    init_db()
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, product_id, product_name, created_at,
                   requested_quantity, final_position, confidence, reason
            FROM decisions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_decision(decision_id: int) -> dict | None:
    init_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT full_response_json FROM decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["full_response_json"])
