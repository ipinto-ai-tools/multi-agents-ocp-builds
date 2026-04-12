"""Tests for memory.store — SQLite + FTS5 storage layer."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from memory.models import MemoryEntry, MemoryQuery, MemoryType
from memory.store import MemoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path: Path) -> MemoryStore:
    """Return a MemoryStore backed by a temp-dir SQLite database."""
    return MemoryStore(db_path=str(tmp_path / "test_memory.db"))


def _make_entry(
    session_id: str = "sess-1",
    stage: str = "design",
    memory_type: MemoryType = MemoryType.best_practice,
    title: str = "Test title",
    content: str = "Test content",
    tags: list[str] | None = None,
    issue_title: str | None = None,
    issue_type: str | None = None,
) -> MemoryEntry:
    return MemoryEntry(
        session_id=session_id,
        stage=stage,
        memory_type=memory_type,
        title=title,
        content=content,
        tags=tags or [],
        issue_title=issue_title,
        issue_type=issue_type,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInit:
    """Database and schema creation."""

    def test_init_creates_db(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "init_test.db")
        MemoryStore(db_path=db_path)
        assert Path(db_path).exists()

    def test_init_creates_tables(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "tables_test.db")
        MemoryStore(db_path=db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "memories" in tables
        # FTS5 virtual tables create multiple shadow tables; the main one:
        assert "memories_fts" in tables

    def test_init_creates_parent_dirs(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "sub" / "dir" / "deep.db")
        MemoryStore(db_path=db_path)
        assert Path(db_path).exists()


class TestStoreAndRetrieve:
    """store() + get_by_session() round-trip."""

    def test_store_and_retrieve(self, store: MemoryStore) -> None:
        entry = _make_entry(title="Alpha", content="First memory")
        row_id = store.store(entry)
        assert isinstance(row_id, int)
        assert row_id > 0

        results = store.get_by_session("sess-1")
        assert len(results) == 1
        assert results[0].title == "Alpha"
        assert results[0].content == "First memory"
        assert results[0].id == row_id

    def test_store_multiple_sessions(self, store: MemoryStore) -> None:
        store.store(_make_entry(session_id="a", title="A"))
        store.store(_make_entry(session_id="b", title="B"))

        assert len(store.get_by_session("a")) == 1
        assert len(store.get_by_session("b")) == 1
        assert len(store.get_by_session("c")) == 0


class TestSearchFTS:
    """Full-text search with BM25 ranking."""

    def test_search_fts_returns_relevant(self, store: MemoryStore) -> None:
        store.store(_make_entry(title="Timeout handling", content="Build timeout logic for BuildRun"))
        store.store(_make_entry(title="Webhook setup", content="Configure admission webhooks"))
        store.store(_make_entry(title="Timeout validation", content="Validate timeout field values"))

        query = MemoryQuery(query_text="timeout", max_results=10)
        results = store.search(query)

        # Both timeout entries should appear; webhook should not
        titles = [r.title for r in results]
        assert "Timeout handling" in titles
        assert "Timeout validation" in titles
        assert "Webhook setup" not in titles

    def test_search_fts_respects_max_results(self, store: MemoryStore) -> None:
        for i in range(10):
            store.store(_make_entry(title=f"Timeout item {i}", content="timeout content"))

        query = MemoryQuery(query_text="timeout", max_results=3)
        results = store.search(query)
        assert len(results) == 3


class TestSearchWithFilters:
    """Filtered search by stage, memory_type, and issue_type."""

    def test_filter_by_stage(self, store: MemoryStore) -> None:
        store.store(_make_entry(stage="design", title="Design note", content="design data"))
        store.store(_make_entry(stage="develop", title="Dev note", content="develop data"))

        query = MemoryQuery(query_text="note", stage="design", max_results=10)
        results = store.search(query)
        assert len(results) == 1
        assert results[0].stage == "design"

    def test_filter_by_memory_type(self, store: MemoryStore) -> None:
        store.store(
            _make_entry(
                memory_type=MemoryType.best_practice,
                title="Best practice",
                content="practice detail",
            )
        )
        store.store(
            _make_entry(
                memory_type=MemoryType.anti_pattern,
                title="Anti-pattern",
                content="pattern detail",
            )
        )

        query = MemoryQuery(
            query_text="detail",
            memory_types=[MemoryType.anti_pattern],
            max_results=10,
        )
        results = store.search(query)
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.anti_pattern

    def test_filter_by_issue_type(self, store: MemoryStore) -> None:
        store.store(_make_entry(issue_type="feature", title="Feature entry", content="feature info"))
        store.store(_make_entry(issue_type="bug", title="Bug entry", content="bug info"))

        query = MemoryQuery(query_text="entry", issue_type="bug", max_results=10)
        results = store.search(query)
        assert len(results) == 1
        assert results[0].issue_type == "bug"


class TestSearchEmptyQuery:
    """Empty query_text falls back to regular SELECT."""

    def test_search_empty_query(self, store: MemoryStore) -> None:
        store.store(_make_entry(title="Alpha", content="First"))
        store.store(_make_entry(title="Beta", content="Second"))

        query = MemoryQuery(query_text="", max_results=10)
        results = store.search(query)
        assert len(results) == 2

    def test_search_empty_query_with_stage_filter(self, store: MemoryStore) -> None:
        store.store(_make_entry(stage="design", title="D1", content="design stuff"))
        store.store(_make_entry(stage="testing", title="T1", content="testing stuff"))

        query = MemoryQuery(query_text="", stage="testing", max_results=10)
        results = store.search(query)
        assert len(results) == 1
        assert results[0].stage == "testing"


class TestDelete:
    """delete_by_session removes entries and returns count."""

    def test_delete_by_session(self, store: MemoryStore) -> None:
        store.store(_make_entry(session_id="del-sess", title="A"))
        store.store(_make_entry(session_id="del-sess", title="B"))
        store.store(_make_entry(session_id="keep-sess", title="C"))

        deleted = store.delete_by_session("del-sess")
        assert deleted == 2
        assert len(store.get_by_session("del-sess")) == 0
        assert len(store.get_by_session("keep-sess")) == 1

    def test_delete_nonexistent_session_returns_zero(self, store: MemoryStore) -> None:
        deleted = store.delete_by_session("no-such-session")
        assert deleted == 0


class TestCount:
    """count() returns the total number of stored memories."""

    def test_count_empty(self, store: MemoryStore) -> None:
        assert store.count() == 0

    def test_count_after_inserts(self, store: MemoryStore) -> None:
        store.store(_make_entry(title="One"))
        store.store(_make_entry(title="Two"))
        store.store(_make_entry(title="Three"))
        assert store.count() == 3

    def test_count_after_delete(self, store: MemoryStore) -> None:
        store.store(_make_entry(session_id="s1", title="One"))
        store.store(_make_entry(session_id="s1", title="Two"))
        store.delete_by_session("s1")
        assert store.count() == 0


class TestTagsRoundTrip:
    """Tags stored as comma-separated string, retrieved as list."""

    def test_tags_roundtrip(self, store: MemoryStore) -> None:
        entry = _make_entry(tags=["buildrun", "controller", "api"])
        store.store(entry)

        results = store.get_by_session("sess-1")
        assert len(results) == 1
        assert results[0].tags == ["buildrun", "controller", "api"]

    def test_empty_tags_roundtrip(self, store: MemoryStore) -> None:
        entry = _make_entry(tags=[])
        store.store(entry)

        results = store.get_by_session("sess-1")
        assert results[0].tags == []

    def test_single_tag_roundtrip(self, store: MemoryStore) -> None:
        entry = _make_entry(tags=["single"])
        store.store(entry)

        results = store.get_by_session("sess-1")
        assert results[0].tags == ["single"]
