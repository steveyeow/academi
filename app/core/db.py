from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import DB_PATH, DATA_DIR


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                source TEXT,
                status TEXT NOT NULL,
                meta_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                vector BLOB NOT NULL,
                dim INTEGER NOT NULL,
                norm REAL NOT NULL,
                FOREIGN KEY(agent_id) REFERENCES agents(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_agent_id ON chunks(agent_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(agent_id) REFERENCES agents(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(agent_id) REFERENCES agents(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_agent_id ON questions(agent_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )


def create_agent(name: str, agent_type: str, source: str | None, meta: dict[str, Any]) -> str:
    agent_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO agents (id, name, type, source, status, meta_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (agent_id, name, agent_type, source, "indexing", json.dumps(meta), _utcnow()),
        )
    return agent_id


def update_agent_status(agent_id: str, status: str, meta: dict[str, Any] | None = None) -> None:
    with get_conn() as conn:
        if meta is None:
            conn.execute("UPDATE agents SET status = ? WHERE id = ?", (status, agent_id))
        else:
            conn.execute(
                "UPDATE agents SET status = ?, meta_json = ? WHERE id = ?",
                (status, json.dumps(meta), agent_id),
            )


def get_agent(agent_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not row:
            return None
        return _row_to_agent(row)


def list_agents() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
        return [_row_to_agent(r) for r in rows]


def _row_to_agent(row: sqlite3.Row) -> dict[str, Any]:
    meta_json = row["meta_json"] or "{}"
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "source": row["source"],
        "status": row["status"],
        "meta": json.loads(meta_json),
        "created_at": row["created_at"],
    }


def add_chunks(agent_id: str, chunk_records: Iterable[dict[str, Any]]) -> None:
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO chunks (id, agent_id, chunk_index, text, vector, dim, norm)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    rec["id"],
                    agent_id,
                    rec["chunk_index"],
                    rec["text"],
                    rec["vector"],
                    rec["dim"],
                    rec["norm"],
                )
                for rec in chunk_records
            ],
        )


def get_chunks(agent_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, chunk_index, text, vector, dim, norm FROM chunks WHERE agent_id = ? ORDER BY chunk_index ASC",
            (agent_id,),
        ).fetchall()


def add_message(agent_id: str, role: str, content: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, agent_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), agent_id, role, content, _utcnow()),
        )


def list_messages(agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


# ─── Questions CRUD ───

def add_questions(agent_id: str, questions: list[str]) -> None:
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO questions (id, agent_id, text, created_at) VALUES (?, ?, ?, ?)",
            [(str(uuid.uuid4()), agent_id, q, _utcnow()) for q in questions],
        )


def list_questions(agent_id: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT text FROM questions WHERE agent_id = ? ORDER BY created_at ASC",
            (agent_id,),
        ).fetchall()
        return [r["text"] for r in rows]


# ─── Votes CRUD ───

def create_vote(title: str) -> dict[str, Any]:
    with get_conn() as conn:
        # Check if title already exists (case-insensitive)
        existing = conn.execute(
            "SELECT id, title, count, created_at FROM votes WHERE LOWER(title) = LOWER(?)",
            (title,),
        ).fetchone()
        if existing:
            conn.execute("UPDATE votes SET count = count + 1 WHERE id = ?", (existing["id"],))
            return {"id": existing["id"], "title": existing["title"], "count": existing["count"] + 1}
        vote_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO votes (id, title, count, created_at) VALUES (?, ?, 1, ?)",
            (vote_id, title, _utcnow()),
        )
        return {"id": vote_id, "title": title, "count": 1}


def upvote(vote_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT id, title, count FROM votes WHERE id = ?", (vote_id,)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE votes SET count = count + 1 WHERE id = ?", (vote_id,))
        return {"id": row["id"], "title": row["title"], "count": row["count"] + 1}


def delete_agent(agent_id: str) -> bool:
    with get_conn() as conn:
        conn.execute("DELETE FROM chunks WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM messages WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM questions WHERE agent_id = ?", (agent_id,))
        cur = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        return cur.rowcount > 0


def list_votes() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, title, count, created_at FROM votes ORDER BY count DESC").fetchall()
        return [dict(r) for r in rows]


# ─── Catalog agent helpers ───

def ensure_catalog_agents(catalog: list[dict[str, Any]]) -> None:
    """Idempotently seed catalog books as agents. Skips titles that already exist."""
    with get_conn() as conn:
        existing = {
            row["name"].lower()
            for row in conn.execute("SELECT name FROM agents").fetchall()
        }
        for book in catalog:
            if book["title"].lower() in existing:
                continue
            agent_id = str(uuid.uuid4())
            meta = {
                "title": book["title"],
                "author": book.get("author", ""),
                "isbn": book.get("isbn"),
                "category": book.get("category", ""),
                "description": book.get("description", ""),
            }
            conn.execute(
                "INSERT INTO agents (id, name, type, source, status, meta_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agent_id, book["title"], "catalog", book.get("author", ""), "catalog", json.dumps(meta), _utcnow()),
            )


def update_agent_meta(agent_id: str, updates: dict[str, Any]) -> None:
    """Merge updates into agent's meta_json without overwriting other keys."""
    with get_conn() as conn:
        row = conn.execute("SELECT meta_json FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not row:
            return
        meta = json.loads(row["meta_json"] or "{}")
        meta.update(updates)
        conn.execute("UPDATE agents SET meta_json = ? WHERE id = ?", (json.dumps(meta), agent_id))


def find_agent_by_name(name: str) -> dict[str, Any] | None:
    """Find an agent by name (case-insensitive)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM agents WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if not row:
            return None
        return _row_to_agent(row)


def create_catalog_agent(title: str, author: str = "", isbn: str | None = None,
                         category: str = "", description: str = "") -> str:
    """Create a new catalog agent for a dynamically discovered book. Returns agent_id."""
    existing = find_agent_by_name(title)
    if existing:
        return existing["id"]
    meta = {"title": title, "author": author, "isbn": isbn, "category": category, "description": description}
    agent_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO agents (id, name, type, source, status, meta_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (agent_id, title, "catalog", author, "catalog", json.dumps(meta), _utcnow()),
        )
    return agent_id

