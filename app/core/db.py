from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import DB_PATH, DATA_DIR

_RAW_DATABASE_URL = os.getenv("DATABASE_URL", "")


def _clean_dsn(url: str) -> str:
    """Strip query params psycopg2 doesn't understand (e.g. pgbouncer=true)."""
    if "?" in url:
        base, qs = url.split("?", 1)
        from urllib.parse import parse_qs, urlencode
        params = parse_qs(qs)
        params.pop("pgbouncer", None)
        clean_qs = urlencode(params, doseq=True)
        return f"{base}?{clean_qs}" if clean_qs else base
    return url


DATABASE_URL = _clean_dsn(_RAW_DATABASE_URL)

_USE_PG = bool(DATABASE_URL)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    if not _USE_PG:
        from pathlib import Path
        Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def _pg():
    """Lazy import psycopg2 only when PostgreSQL is used."""
    import psycopg2
    import psycopg2.extras
    return psycopg2

@contextmanager
def get_conn():
    if _USE_PG:
        pg = _pg()
        conn = pg.connect(DATABASE_URL)
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        import sqlite3
        _ensure_dirs()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _fetchone(conn, query: str, params: tuple = ()) -> dict[str, Any] | None:
    if _USE_PG:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None
    else:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def _fetchall(conn, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    if _USE_PG:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    else:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def _execute(conn, query: str, params: tuple = ()):
    if _USE_PG:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur
    else:
        return conn.execute(query, params)


def _executemany(conn, query: str, params_list: list[tuple]):
    if _USE_PG:
        cur = conn.cursor()
        for p in params_list:
            cur.execute(query, p)
    else:
        conn.executemany(query, params_list)


def _q(query: str) -> str:
    """Convert ? placeholders to %s for PostgreSQL."""
    if _USE_PG:
        return query.replace("?", "%s")
    return query


def _conflict_ignore(query: str) -> str:
    """Convert INSERT OR IGNORE to ON CONFLICT DO NOTHING for PostgreSQL."""
    if _USE_PG:
        return query.replace("INSERT OR IGNORE", "INSERT") + " ON CONFLICT DO NOTHING"
    return query


def init_db() -> None:
    with get_conn() as conn:
        if _USE_PG:
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    source TEXT,
                    status TEXT NOT NULL,
                    meta_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(id),
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    vector BYTEA NOT NULL,
                    dim INTEGER NOT NULL,
                    norm REAL NOT NULL
                )
            """)
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_chunks_agent_id ON chunks(agent_id)")
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(id),
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_questions_agent_id ON questions(agent_id)")
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS votes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS minds (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    era TEXT,
                    domain TEXT,
                    bio_summary TEXT,
                    persona TEXT NOT NULL,
                    thinking_style TEXT,
                    typical_phrases TEXT,
                    works TEXT,
                    avatar_seed TEXT,
                    version INTEGER DEFAULT 1,
                    chat_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_minds_name ON minds(LOWER(name))")
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS mind_works (
                    mind_id TEXT NOT NULL REFERENCES minds(id),
                    agent_id TEXT NOT NULL REFERENCES agents(id),
                    PRIMARY KEY (mind_id, agent_id)
                )
            """)
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS mind_memories (
                    id TEXT PRIMARY KEY,
                    mind_id TEXT NOT NULL REFERENCES minds(id),
                    user_id TEXT,
                    summary TEXT NOT NULL,
                    topic TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_mind_memories_mind ON mind_memories(mind_id)")
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_mind_memories_user ON mind_memories(mind_id, user_id)")

            # Pro tables
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    email TEXT NOT NULL,
                    tier TEXT DEFAULT 'free',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS usage (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id),
                    action TEXT NOT NULL,
                    tokens_used INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        else:
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    source TEXT,
                    status TEXT NOT NULL,
                    meta_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, """
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
            """)
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_chunks_agent_id ON chunks(agent_id)")
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(agent_id) REFERENCES agents(id)
                )
            """)
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(agent_id) REFERENCES agents(id)
                )
            """)
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_questions_agent_id ON questions(agent_id)")
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS votes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS minds (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    era TEXT,
                    domain TEXT,
                    bio_summary TEXT,
                    persona TEXT NOT NULL,
                    thinking_style TEXT,
                    typical_phrases TEXT,
                    works TEXT,
                    avatar_seed TEXT,
                    version INTEGER DEFAULT 1,
                    chat_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_minds_name ON minds(LOWER(name))")
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS mind_works (
                    mind_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    PRIMARY KEY (mind_id, agent_id),
                    FOREIGN KEY (mind_id) REFERENCES minds(id),
                    FOREIGN KEY (agent_id) REFERENCES agents(id)
                )
            """)
            _execute(conn, """
                CREATE TABLE IF NOT EXISTS mind_memories (
                    id TEXT PRIMARY KEY,
                    mind_id TEXT NOT NULL,
                    user_id TEXT,
                    summary TEXT NOT NULL,
                    topic TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (mind_id) REFERENCES minds(id)
                )
            """)
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_mind_memories_mind ON mind_memories(mind_id)")
            _execute(conn, "CREATE INDEX IF NOT EXISTS idx_mind_memories_user ON mind_memories(mind_id, user_id)")


def create_agent(name: str, agent_type: str, source: str | None, meta: dict[str, Any]) -> str:
    agent_id = str(uuid.uuid4())
    with get_conn() as conn:
        _execute(conn, _q(
            "INSERT INTO agents (id, name, type, source, status, meta_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
        ), (agent_id, name, agent_type, source, "indexing", json.dumps(meta), _utcnow()))
    return agent_id


def update_agent_status(agent_id: str, status: str, meta: dict[str, Any] | None = None) -> None:
    with get_conn() as conn:
        if meta is None:
            _execute(conn, _q("UPDATE agents SET status = ? WHERE id = ?"), (status, agent_id))
        else:
            _execute(conn, _q(
                "UPDATE agents SET status = ?, meta_json = ? WHERE id = ?"
            ), (status, json.dumps(meta), agent_id))


def get_agent(agent_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = _fetchone(conn, _q("SELECT * FROM agents WHERE id = ?"), (agent_id,))
        if not row:
            return None
        return _row_to_agent(row)


def list_agents() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = _fetchall(conn, "SELECT * FROM agents ORDER BY created_at DESC")
        return [_row_to_agent(r) for r in rows]


def _row_to_agent(row: dict[str, Any]) -> dict[str, Any]:
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
        params_list = [
            (
                rec["id"],
                agent_id,
                rec["chunk_index"],
                rec["text"],
                rec["vector"] if not _USE_PG else _pg().Binary(rec["vector"]),
                rec["dim"],
                rec["norm"],
            )
            for rec in chunk_records
        ]
        _executemany(conn, _q(
            "INSERT INTO chunks (id, agent_id, chunk_index, text, vector, dim, norm) VALUES (?, ?, ?, ?, ?, ?, ?)"
        ), params_list)


def get_chunks(agent_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _fetchall(conn, _q(
            "SELECT id, chunk_index, text, vector, dim, norm FROM chunks WHERE agent_id = ? ORDER BY chunk_index ASC"
        ), (agent_id,))


def add_message(agent_id: str, role: str, content: str) -> None:
    with get_conn() as conn:
        _execute(conn, _q(
            "INSERT INTO messages (id, agent_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)"
        ), (str(uuid.uuid4()), agent_id, role, content, _utcnow()))


def list_messages(agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = _fetchall(conn, _q(
            "SELECT role, content, created_at FROM messages WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?"
        ), (agent_id, limit))
        return list(reversed(rows))


# ─── Questions CRUD ───

def add_questions(agent_id: str, questions: list[str]) -> None:
    with get_conn() as conn:
        _executemany(conn, _q(
            "INSERT INTO questions (id, agent_id, text, created_at) VALUES (?, ?, ?, ?)"
        ), [(str(uuid.uuid4()), agent_id, q, _utcnow()) for q in questions])


def list_questions(agent_id: str) -> list[str]:
    with get_conn() as conn:
        rows = _fetchall(conn, _q(
            "SELECT text FROM questions WHERE agent_id = ? ORDER BY created_at ASC"
        ), (agent_id,))
        return [r["text"] for r in rows]


# ─── Votes CRUD ───

def create_vote(title: str) -> dict[str, Any]:
    with get_conn() as conn:
        existing = _fetchone(conn, _q(
            "SELECT id, title, count, created_at FROM votes WHERE LOWER(title) = LOWER(?)"
        ), (title,))
        if existing:
            _execute(conn, _q("UPDATE votes SET count = count + 1 WHERE id = ?"), (existing["id"],))
            return {"id": existing["id"], "title": existing["title"], "count": existing["count"] + 1}
        vote_id = str(uuid.uuid4())
        _execute(conn, _q(
            "INSERT INTO votes (id, title, count, created_at) VALUES (?, ?, 1, ?)"
        ), (vote_id, title, _utcnow()))
        return {"id": vote_id, "title": title, "count": 1}


def upvote(vote_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = _fetchone(conn, _q("SELECT id, title, count FROM votes WHERE id = ?"), (vote_id,))
        if not row:
            return None
        _execute(conn, _q("UPDATE votes SET count = count + 1 WHERE id = ?"), (vote_id,))
        return {"id": row["id"], "title": row["title"], "count": row["count"] + 1}


def delete_agent(agent_id: str) -> bool:
    with get_conn() as conn:
        _execute(conn, _q("DELETE FROM chunks WHERE agent_id = ?"), (agent_id,))
        _execute(conn, _q("DELETE FROM messages WHERE agent_id = ?"), (agent_id,))
        _execute(conn, _q("DELETE FROM questions WHERE agent_id = ?"), (agent_id,))
        cur = _execute(conn, _q("DELETE FROM agents WHERE id = ?"), (agent_id,))
        return cur.rowcount > 0


def list_votes() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return _fetchall(conn, "SELECT id, title, count, created_at FROM votes ORDER BY count DESC")


# ─── Catalog agent helpers ───

def ensure_catalog_agents(catalog: list[dict[str, Any]]) -> None:
    """Idempotently seed catalog books as agents. Skips titles that already exist."""
    with get_conn() as conn:
        existing_rows = _fetchall(conn, "SELECT name FROM agents")
        existing = {row["name"].lower() for row in existing_rows}
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
            _execute(conn, _q(
                "INSERT INTO agents (id, name, type, source, status, meta_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
            ), (agent_id, book["title"], "catalog", book.get("author", ""), "catalog", json.dumps(meta), _utcnow()))


def update_agent_meta(agent_id: str, updates: dict[str, Any]) -> None:
    """Merge updates into agent's meta_json without overwriting other keys."""
    with get_conn() as conn:
        row = _fetchone(conn, _q("SELECT meta_json FROM agents WHERE id = ?"), (agent_id,))
        if not row:
            return
        meta = json.loads(row["meta_json"] or "{}")
        meta.update(updates)
        _execute(conn, _q("UPDATE agents SET meta_json = ? WHERE id = ?"), (json.dumps(meta), agent_id))


def find_agent_by_name(name: str) -> dict[str, Any] | None:
    """Find an agent by name (case-insensitive)."""
    with get_conn() as conn:
        row = _fetchone(conn, _q(
            "SELECT * FROM agents WHERE LOWER(name) = LOWER(?)"
        ), (name,))
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
        _execute(conn, _q(
            "INSERT INTO agents (id, name, type, source, status, meta_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
        ), (agent_id, title, "catalog", author, "catalog", json.dumps(meta), _utcnow()))
    return agent_id


# ─── Minds CRUD ───

def create_mind(data: dict[str, Any]) -> str:
    """Insert a new mind agent. Returns mind_id."""
    mind_id = str(uuid.uuid4())
    with get_conn() as conn:
        _execute(conn, _q(
            """INSERT INTO minds
               (id, name, era, domain, bio_summary, persona, thinking_style,
                typical_phrases, works, avatar_seed, version, chat_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)"""
        ), (
            mind_id,
            data["name"],
            data.get("era", ""),
            data.get("domain", ""),
            data.get("bio_summary", ""),
            data["persona"],
            data.get("thinking_style", ""),
            json.dumps(data.get("typical_phrases", [])),
            json.dumps(data.get("works", [])),
            data.get("avatar_seed", data["name"].lower().replace(" ", "-")),
            _utcnow(),
        ))
    return mind_id


def get_mind(mind_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = _fetchone(conn, _q("SELECT * FROM minds WHERE id = ?"), (mind_id,))
        if not row:
            return None
        return _row_to_mind(row)


def find_mind_by_name(name: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = _fetchone(conn, _q(
            "SELECT * FROM minds WHERE LOWER(name) = LOWER(?)"
        ), (name,))
        if not row:
            return None
        return _row_to_mind(row)


def list_minds() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = _fetchall(conn, "SELECT * FROM minds ORDER BY chat_count DESC, created_at ASC")
        return [_row_to_mind(r) for r in rows]


def _row_to_mind(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "era": row["era"] or "",
        "domain": row["domain"] or "",
        "bio_summary": row["bio_summary"] or "",
        "persona": row["persona"],
        "thinking_style": row["thinking_style"] or "",
        "typical_phrases": json.loads(row["typical_phrases"] or "[]"),
        "works": json.loads(row["works"] or "[]"),
        "avatar_seed": row["avatar_seed"] or "",
        "version": row["version"],
        "chat_count": row["chat_count"],
        "created_at": row["created_at"],
    }


def increment_mind_chat_count(mind_id: str) -> None:
    with get_conn() as conn:
        _execute(conn, _q("UPDATE minds SET chat_count = chat_count + 1 WHERE id = ?"), (mind_id,))


def link_mind_work(mind_id: str, agent_id: str) -> None:
    with get_conn() as conn:
        _execute(conn, _conflict_ignore(_q(
            "INSERT OR IGNORE INTO mind_works (mind_id, agent_id) VALUES (?, ?)"
        )), (mind_id, agent_id))


def get_mind_work_ids(mind_id: str) -> list[str]:
    with get_conn() as conn:
        rows = _fetchall(conn, _q(
            "SELECT agent_id FROM mind_works WHERE mind_id = ?"
        ), (mind_id,))
        return [r["agent_id"] for r in rows]


# ─── Mind memories ───

def add_mind_memory(mind_id: str, summary: str, topic: str = "", user_id: str | None = None) -> None:
    with get_conn() as conn:
        _execute(conn, _q(
            "INSERT INTO mind_memories (id, mind_id, user_id, summary, topic, created_at) VALUES (?, ?, ?, ?, ?, ?)"
        ), (str(uuid.uuid4()), mind_id, user_id, summary, topic, _utcnow()))


def list_mind_memories(mind_id: str, user_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if user_id:
            rows = _fetchall(conn, _q(
                """SELECT summary, topic, created_at FROM mind_memories
                   WHERE mind_id = ? AND (user_id IS NULL OR user_id = ?)
                   ORDER BY created_at DESC LIMIT ?"""
            ), (mind_id, user_id, limit))
        else:
            rows = _fetchall(conn, _q(
                """SELECT summary, topic, created_at FROM mind_memories
                   WHERE mind_id = ? AND user_id IS NULL
                   ORDER BY created_at DESC LIMIT ?"""
            ), (mind_id, limit))
        return rows


# ─── Pro: User & Usage helpers ───

def get_or_create_user(user_id: str, email: str) -> dict[str, Any]:
    """Get existing user or create a new free-tier user."""
    with get_conn() as conn:
        row = _fetchone(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
        if row:
            return row
        _execute(conn, """
            INSERT INTO users (id, email, tier) VALUES (%s, %s, 'free')
            ON CONFLICT (id) DO NOTHING
        """, (user_id, email))
        row = _fetchone(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
        return row


def get_user(user_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return _fetchone(conn, "SELECT * FROM users WHERE id = %s", (user_id,))


def update_user_tier(user_id: str, tier: str, stripe_customer_id: str | None = None,
                     stripe_subscription_id: str | None = None) -> None:
    with get_conn() as conn:
        _execute(conn, """
            UPDATE users SET tier = %s, stripe_customer_id = COALESCE(%s, stripe_customer_id),
            stripe_subscription_id = COALESCE(%s, stripe_subscription_id)
            WHERE id = %s
        """, (tier, stripe_customer_id, stripe_subscription_id, user_id))


def find_user_by_stripe_customer(customer_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return _fetchone(conn, "SELECT * FROM users WHERE stripe_customer_id = %s", (customer_id,))


def record_usage(user_id: str, action: str, tokens_used: int = 0) -> None:
    with get_conn() as conn:
        _execute(conn, """
            INSERT INTO usage (user_id, action, tokens_used) VALUES (%s, %s, %s)
        """, (user_id, action, tokens_used))


def count_usage_today(user_id: str, action: str) -> int:
    with get_conn() as conn:
        row = _fetchone(conn, """
            SELECT COUNT(*) as cnt FROM usage
            WHERE user_id = %s AND action = %s
            AND created_at >= CURRENT_DATE
        """, (user_id, action))
        return row["cnt"] if row else 0
