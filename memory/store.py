"""SQLite storage layer for persistent cross-session memory.

Provides full-text search (FTS5) over stored memories with BM25 ranking,
optional filtering by stage, memory type, and issue type, and basic CRUD
operations scoped to sessions.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from memory.models import MemoryEntry, MemoryQuery
from utils.file_logger import get_logger

logger = get_logger("memory.store")

_DEFAULT_DB_PATH = str(
    Path.home() / ".local" / "share" / "flowpilot" / "memory.db"
)


def _escape_fts5(text: str) -> str:
    """Quote each token to disable FTS5 operator interpretation."""
    tokens = text.replace('"', '').split()
    return " ".join(f'"{t}"' for t in tokens) if tokens else ""


class MemoryStore:
    """SQLite-backed store for pipeline memories with FTS5 search."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.path.expanduser(
            os.getenv("MEMORY_DB_PATH", _DEFAULT_DB_PATH)
        )
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_schema()
        logger.info("MemoryStore initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create the memories table, FTS5 virtual table, and sync triggers."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id      TEXT NOT NULL,
                    stage           TEXT NOT NULL,
                    memory_type     TEXT NOT NULL,
                    title           TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    tags            TEXT,
                    issue_title     TEXT,
                    issue_type      TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    relevance_score REAL DEFAULT 1.0
                )
            """)

            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    title, content, tags,
                    content='memories',
                    content_rowid='id'
                )
            """)

            # Keep FTS index in sync with the main table.
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories
                BEGIN
                    INSERT INTO memories_fts(rowid, title, content, tags)
                    VALUES (new.id, new.title, new.content, new.tags);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories
                BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, title, content, tags)
                    VALUES ('delete', old.id, old.title, old.content, old.tags);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories
                BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, title, content, tags)
                    VALUES ('delete', old.id, old.title, old.content, old.tags);
                    INSERT INTO memories_fts(rowid, title, content, tags)
                    VALUES (new.id, new.title, new.content, new.tags);
                END
            """)

            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a new connection with ``Row`` factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Row conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        """Convert a ``sqlite3.Row`` into a ``MemoryEntry``."""
        tags_raw: str | None = row["tags"]
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        return MemoryEntry(
            id=row["id"],
            session_id=row["session_id"],
            stage=row["stage"],
            memory_type=row["memory_type"],
            title=row["title"],
            content=row["content"],
            tags=tags,
            issue_title=row["issue_title"],
            issue_type=row["issue_type"],
            created_at=row["created_at"],
            relevance_score=row["relevance_score"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, entry: MemoryEntry) -> int:
        """Persist a ``MemoryEntry`` and return its new row id."""
        tags_str = ",".join(entry.tags) if entry.tags else None
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO memories
                    (session_id, stage, memory_type, title, content,
                     tags, issue_title, issue_type, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.session_id,
                    entry.stage,
                    entry.memory_type,
                    entry.title,
                    entry.content,
                    tags_str,
                    entry.issue_title,
                    entry.issue_type,
                    entry.relevance_score,
                ),
            )
            conn.commit()
            row_id: int = cursor.lastrowid  # type: ignore[assignment]
            logger.debug("Stored memory id=%d title=%r", row_id, entry.title)
            return row_id
        finally:
            conn.close()

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Search memories using FTS5 with BM25 ranking and optional filters.

        When ``query.query_text`` is empty the method falls back to a plain
        ``SELECT`` on the ``memories`` table with the same optional filters.
        """
        conn = self._connect()
        try:
            params: list[object] = []

            escaped_query = _escape_fts5(query.query_text) if query.query_text and query.query_text.strip() else ""
            if escaped_query:
                # FTS5 path -- join back to memories for filter columns.
                sql = """
                    SELECT m.*
                    FROM memories_fts fts
                    JOIN memories m ON m.id = fts.rowid
                    WHERE memories_fts MATCH ?
                """
                params.append(escaped_query)
            else:
                sql = "SELECT * FROM memories WHERE 1=1"

            if query.stage:
                sql += " AND m.stage = ?" if escaped_query else " AND stage = ?"
                params.append(query.stage)

            if query.memory_types:
                placeholders = ",".join("?" * len(query.memory_types))
                col = "m.memory_type" if escaped_query else "memory_type"
                sql += f" AND {col} IN ({placeholders})"
                params.extend(query.memory_types)

            if query.issue_type:
                sql += " AND m.issue_type = ?" if escaped_query else " AND issue_type = ?"
                params.append(query.issue_type)

            if escaped_query:
                sql += " ORDER BY rank"
            else:
                sql += " ORDER BY created_at DESC"

            sql += " LIMIT ?"
            params.append(query.max_results)

            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_session(self, session_id: str) -> list[MemoryEntry]:
        """Return all memories for *session_id* ordered by creation time."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM memories WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_by_session(self, session_id: str) -> int:
        """Delete all memories for *session_id* and return the number removed."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM memories WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            deleted: int = cursor.rowcount
            logger.info(
                "Deleted %d memories for session %s", deleted, session_id
            )
            return deleted
        finally:
            conn.close()

    def count(self) -> int:
        """Return the total number of stored memories."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            return cursor.fetchone()[0]
        finally:
            conn.close()
