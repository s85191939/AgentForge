"""Postgres-backed chat persistence using asyncpg.

Connects to the shared Ghostfolio Postgres via DATABASE_URL.
All tables are prefixed with 'agentforge_' to avoid conflicts.
Falls back gracefully to no-op if DATABASE_URL is not set.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

import asyncpg

logger = logging.getLogger("agentforge.database")

# Module-level connection pool
_pool: asyncpg.Pool | None = None


async def init_db(database_url: str | None) -> None:
    """Initialize the connection pool and create tables if needed."""
    global _pool
    if not database_url:
        logger.warning("DATABASE_URL not set — chat persistence disabled (in-memory only)")
        return

    try:
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agentforge_threads (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL DEFAULT 'New Chat',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agentforge_messages (
                    id          SERIAL PRIMARY KEY,
                    thread_id   TEXT NOT NULL REFERENCES agentforge_threads(id) ON DELETE CASCADE,
                    role        TEXT NOT NULL CHECK (role IN ('user', 'agent')),
                    content     TEXT NOT NULL,
                    metadata    JSONB DEFAULT '{}',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agentforge_messages_thread_id
                    ON agentforge_messages(thread_id, created_at)
            """)
        logger.info("Database initialized — chat persistence enabled")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        _pool = None


async def close_db() -> None:
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")


def is_available() -> bool:
    """Check if the database is available."""
    return _pool is not None


async def _ensure_thread_exists(thread_id: str) -> None:
    """Create thread if it doesn't exist (idempotent)."""
    if not _pool:
        return
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agentforge_threads (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            thread_id,
        )


async def create_thread(title: str = "New Chat") -> dict | None:
    """Create a new thread. Returns the thread dict or None if DB unavailable."""
    if not _pool:
        return None
    thread_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agentforge_threads (id, title, created_at, updated_at)"
            " VALUES ($1, $2, $3, $4)",
            thread_id, title, now, now,
        )
    return {
        "id": thread_id,
        "title": title,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


async def list_threads() -> list[dict]:
    """List all threads ordered by updated_at desc."""
    if not _pool:
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.id, t.title, t.created_at, t.updated_at,
                   COUNT(m.id) as message_count
            FROM agentforge_threads t
            LEFT JOIN agentforge_messages m ON m.thread_id = t.id
            GROUP BY t.id
            ORDER BY t.updated_at DESC
        """)
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "created_at": r["created_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
            "message_count": r["message_count"],
        }
        for r in rows
    ]


async def rename_thread(thread_id: str, title: str) -> bool:
    """Rename a thread. Returns True if updated."""
    if not _pool:
        return False
    async with _pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE agentforge_threads SET title = $1, updated_at = NOW()"
            " WHERE id = $2",
            title, thread_id,
        )
    return result == "UPDATE 1"


async def delete_thread(thread_id: str) -> bool:
    """Delete a thread and its messages. Returns True if deleted."""
    if not _pool:
        return False
    async with _pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM agentforge_threads WHERE id = $1", thread_id
        )
    return result == "DELETE 1"


async def save_message(
    thread_id: str, role: str, content: str, metadata: dict | None = None
) -> dict | None:
    """Save a message to a thread. Returns the message dict or None."""
    if not _pool:
        return None

    # Ensure the thread exists (idempotent)
    await _ensure_thread_exists(thread_id)

    meta_json = json.dumps(metadata or {})
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO agentforge_messages (thread_id, role, content, metadata)
               VALUES ($1, $2, $3, $4::jsonb)
               RETURNING id, created_at""",
            thread_id, role, content, meta_json,
        )
        await conn.execute(
            "UPDATE agentforge_threads SET updated_at = NOW() WHERE id = $1",
            thread_id,
        )
    return {
        "id": row["id"],
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "created_at": row["created_at"].isoformat(),
    }


async def load_messages(thread_id: str) -> list[dict]:
    """Load all messages for a thread, ordered by created_at."""
    if not _pool:
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, role, content, metadata, created_at
               FROM agentforge_messages
               WHERE thread_id = $1
               ORDER BY created_at ASC""",
            thread_id,
        )
    return [
        {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "metadata": (
                json.loads(r["metadata"])
                if isinstance(r["metadata"], str)
                else r["metadata"]
            ),
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
