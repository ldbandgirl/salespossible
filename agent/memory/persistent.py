"""
PersistentMemory — SQLite + FTS5 cross-session memory (Hermes-inspired).

Tables:
  sessions       — Full conversation log with metadata
  sessions_fts   — FTS5 virtual table for full-text search
  user_facts     — Extracted user/company facts (Honcho-style user modeling)
  context_files  — Tracks SOUL.md / MEMORY.md / SKILL.md content
  skills_meta    — Skill trigger counts + success rates for self-improvement
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
-- Session history
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_input TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    tools_used TEXT DEFAULT '[]',
    skills_triggered TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    metadata TEXT DEFAULT '{}'
);

-- Full-text search across sessions (FTS5 with Porter stemmer)
CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(
    content,
    session_id UNINDEXED,
    tokenize='porter unicode61'
);

-- User/company facts built up over time (Hermes user modeling)
CREATE TABLE IF NOT EXISTS user_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    fact TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source_session_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Context files snapshot (for change detection)
CREATE TABLE IF NOT EXISTS context_files (
    name TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    file_path TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Skills metadata (trigger count, success rate for auto-improvement)
CREATE TABLE IF NOT EXISTS skills_meta (
    name TEXT PRIMARY KEY,
    description TEXT DEFAULT '',
    trigger_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    last_triggered TEXT,
    last_improved TEXT,
    version INTEGER DEFAULT 1
);
"""


class PersistentMemory:
    """
    Async SQLite memory store with FTS5 search.

    Usage:
        mem = PersistentMemory(Path("~/.salespossible/memory.db"))
        await mem.save_session(...)
        results = await mem.search("pipeline review", top_k=5)
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(str(self.db_path))
            self._db.row_factory = aiosqlite.Row
            await self._db.executescript(SCHEMA)
            await self._db.commit()
        return self._db

    # ── Write ─────────────────────────────────────────────────────────────────

    async def save_session(
        self,
        *,
        session_id: str,
        user_input: str,
        agent_response: str,
        tools_used: list[str] | None = None,
        skills_triggered: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Persist a completed conversation turn."""
        db = await self._get_db()
        record_id = str(uuid.uuid4())

        await db.execute(
            """
            INSERT INTO sessions (id, user_input, agent_response, tools_used,
                                  skills_triggered, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                user_input,
                agent_response,
                json.dumps(tools_used or []),
                json.dumps(skills_triggered or []),
                json.dumps(metadata or {}),
            ),
        )

        # Index in FTS5 (combine user input + agent response for rich search)
        fts_content = f"{user_input}\n{agent_response}"
        await db.execute(
            "INSERT INTO sessions_fts (content, session_id) VALUES (?, ?)",
            (fts_content, record_id),
        )

        # Update skill trigger counts
        for skill_name in (skills_triggered or []):
            await db.execute(
                """
                INSERT INTO skills_meta (name, trigger_count, last_triggered)
                VALUES (?, 1, datetime('now'))
                ON CONFLICT(name) DO UPDATE SET
                    trigger_count = trigger_count + 1,
                    last_triggered = datetime('now')
                """,
                (skill_name,),
            )

        await db.commit()
        logger.debug("Saved session %s to memory", record_id[:8])
        return record_id

    async def upsert_user_fact(
        self,
        category: str,
        fact: str,
        source_session_id: str | None = None,
        confidence: float = 1.0,
    ) -> None:
        """Store or update a fact about the user (Hermes user modeling)."""
        db = await self._get_db()
        await db.execute(
            """
            INSERT INTO user_facts (category, fact, confidence, source_session_id)
            VALUES (?, ?, ?, ?)
            """,
            (category, fact, confidence, source_session_id),
        )
        await db.commit()

    # ── Read ──────────────────────────────────────────────────────────────────

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Full-text search across session history using FTS5 (Porter stemmer).

        Returns top_k sessions most relevant to query, ordered by BM25 rank.
        """
        db = await self._get_db()
        async with db.execute(
            """
            SELECT s.id, s.user_input, s.agent_response, s.tools_used,
                   s.skills_triggered, s.created_at
            FROM sessions_fts f
            JOIN sessions s ON s.id = f.session_id
            WHERE sessions_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, top_k),
        ) as cursor:
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_recent_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the N most recent sessions, newest first."""
        db = await self._get_db()
        async with db.execute(
            """
            SELECT id, user_input, agent_response, tools_used, skills_triggered, created_at
            FROM sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_user_facts(self, category: str | None = None) -> list[dict[str, Any]]:
        """Retrieve stored user facts, optionally filtered by category."""
        db = await self._get_db()
        if category:
            async with db.execute(
                "SELECT * FROM user_facts WHERE category = ? ORDER BY confidence DESC",
                (category,),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM user_facts ORDER BY category, confidence DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_skill_meta(self, skill_name: str) -> dict[str, Any] | None:
        """Get usage metadata for a skill."""
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM skills_meta WHERE name = ?", (skill_name,)
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def increment_skill_success(self, skill_name: str) -> None:
        """Record a successful skill execution."""
        db = await self._get_db()
        await db.execute(
            """
            INSERT INTO skills_meta (name, success_count)
            VALUES (?, 1)
            ON CONFLICT(name) DO UPDATE SET success_count = success_count + 1
            """,
            (skill_name,),
        )
        await db.commit()

    async def mark_skill_improved(self, skill_name: str, version: int) -> None:
        db = await self._get_db()
        await db.execute(
            """
            INSERT INTO skills_meta (name, version, last_improved)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
                version = ?,
                last_improved = datetime('now')
            """,
            (skill_name, version, version),
        )
        await db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
