"""Tests for memory.models — Pydantic models for the persistent memory layer."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from memory.models import VALID_STAGES, MemoryEntry, MemoryQuery, MemoryType


class TestMemoryType:
    """MemoryType enum has all expected values."""

    def test_has_all_five_values(self) -> None:
        assert len(MemoryType) == 5

    def test_enum_members(self) -> None:
        expected = {
            "best_practice",
            "anti_pattern",
            "heuristic",
            "execution_note",
            "reusable_context",
        }
        assert {m.value for m in MemoryType} == expected

    def test_string_values_match_names(self) -> None:
        for member in MemoryType:
            assert member.value == member.name


class TestMemoryEntry:
    """MemoryEntry validation and defaults."""

    @pytest.fixture()
    def valid_entry_kwargs(self) -> dict:
        """Minimal kwargs that produce a valid MemoryEntry."""
        return {
            "session_id": "sess-1",
            "stage": "design",
            "memory_type": MemoryType.best_practice,
            "title": "Example title",
            "content": "Example content",
        }

    def test_valid_stages_accepted(self, valid_entry_kwargs: dict) -> None:
        for stage in VALID_STAGES:
            entry = MemoryEntry(**{**valid_entry_kwargs, "stage": stage})
            assert entry.stage == stage

    def test_invalid_stage_raises_validation_error(
        self, valid_entry_kwargs: dict
    ) -> None:
        with pytest.raises(ValidationError, match="stage must be one of"):
            MemoryEntry(**{**valid_entry_kwargs, "stage": "invalid_stage"})

    def test_default_id_is_none(self, valid_entry_kwargs: dict) -> None:
        entry = MemoryEntry(**valid_entry_kwargs)
        assert entry.id is None

    def test_default_tags_is_empty_list(self, valid_entry_kwargs: dict) -> None:
        entry = MemoryEntry(**valid_entry_kwargs)
        assert entry.tags == []

    def test_default_relevance_score(self, valid_entry_kwargs: dict) -> None:
        entry = MemoryEntry(**valid_entry_kwargs)
        assert entry.relevance_score == 1.0

    def test_default_issue_fields_are_none(self, valid_entry_kwargs: dict) -> None:
        entry = MemoryEntry(**valid_entry_kwargs)
        assert entry.issue_title is None
        assert entry.issue_type is None

    def test_default_created_at_is_none(self, valid_entry_kwargs: dict) -> None:
        entry = MemoryEntry(**valid_entry_kwargs)
        assert entry.created_at is None

    def test_tags_assigned_correctly(self, valid_entry_kwargs: dict) -> None:
        entry = MemoryEntry(**valid_entry_kwargs, tags=["go", "api"])
        assert entry.tags == ["go", "api"]

    def test_all_fields_set(self) -> None:
        entry = MemoryEntry(
            id=42,
            session_id="sess-2",
            stage="develop",
            memory_type=MemoryType.anti_pattern,
            title="Title",
            content="Content",
            tags=["tag1"],
            issue_title="Issue",
            issue_type="bug",
            created_at="2026-01-01T00:00:00",
            relevance_score=0.8,
        )
        assert entry.id == 42
        assert entry.session_id == "sess-2"
        assert entry.stage == "develop"
        assert entry.memory_type == MemoryType.anti_pattern
        assert entry.issue_type == "bug"
        assert entry.relevance_score == 0.8


class TestMemoryQuery:
    """MemoryQuery defaults and validation."""

    def test_default_max_results_is_5(self) -> None:
        query = MemoryQuery(query_text="search term")
        assert query.max_results == 5

    def test_default_stage_is_none(self) -> None:
        query = MemoryQuery(query_text="search term")
        assert query.stage is None

    def test_default_memory_types_is_none(self) -> None:
        query = MemoryQuery(query_text="search term")
        assert query.memory_types is None

    def test_default_issue_type_is_none(self) -> None:
        query = MemoryQuery(query_text="search term")
        assert query.issue_type is None

    def test_custom_max_results(self) -> None:
        query = MemoryQuery(query_text="x", max_results=10)
        assert query.max_results == 10

    def test_all_fields_set(self) -> None:
        query = MemoryQuery(
            query_text="timeout",
            stage="design",
            memory_types=[MemoryType.best_practice, MemoryType.heuristic],
            issue_type="feature",
            max_results=3,
        )
        assert query.query_text == "timeout"
        assert query.stage == "design"
        assert len(query.memory_types) == 2
        assert query.issue_type == "feature"
        assert query.max_results == 3
