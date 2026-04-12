"""Tests for memory.service — high-level MemoryService facade."""

from __future__ import annotations

from pathlib import Path

import pytest

from memory.models import MemoryEntry, MemoryType
from memory.service import MemoryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def enabled_service(tmp_path: Path) -> MemoryService:
    """Return a MemoryService that is explicitly enabled with a temp DB."""
    return MemoryService(enabled=True, db_path=str(tmp_path / "svc.db"))


def _sample_entry(
    session_id: str = "sess-1",
    stage: str = "design",
    memory_type: MemoryType = MemoryType.best_practice,
    title: str = "Sample title",
    content: str = "Sample content",
) -> MemoryEntry:
    return MemoryEntry(
        session_id=session_id,
        stage=stage,
        memory_type=memory_type,
        title=title,
        content=content,
    )


# ---------------------------------------------------------------------------
# Enabled / disabled lifecycle
# ---------------------------------------------------------------------------

class TestEnabledDisabledLifecycle:
    """MemoryService respects MEMORY_ENABLED env var and explicit flag."""

    def test_disabled_by_default(self) -> None:
        svc = MemoryService()
        assert svc.enabled is False

    def test_enabled_via_env(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("MEMORY_ENABLED", "true")
        monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "env.db"))
        svc = MemoryService()
        assert svc.enabled is True

    def test_enabled_via_explicit_flag(self, tmp_path: Path) -> None:
        svc = MemoryService(enabled=True, db_path=str(tmp_path / "flag.db"))
        assert svc.enabled is True

    def test_disabled_via_explicit_flag(self, tmp_path: Path) -> None:
        svc = MemoryService(enabled=False, db_path=str(tmp_path / "off.db"))
        assert svc.enabled is False


# ---------------------------------------------------------------------------
# Disabled behaviour
# ---------------------------------------------------------------------------

class TestDisabledBehaviour:
    """When disabled, retrieve and store are safe no-ops."""

    def test_retrieve_when_disabled(self) -> None:
        svc = MemoryService(enabled=False)
        result = svc.retrieve_for_stage("design", {"issue_title": "test"})
        assert result == ""

    def test_store_when_disabled(self) -> None:
        svc = MemoryService(enabled=False)
        ids = svc.store_from_stage("design", {"session_id": "s1"}, {"design_analysis": "x"})
        assert ids == []


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

class TestRetrieveForStage:
    """retrieve_for_stage searches and formats memories."""

    def test_retrieve_for_stage_with_stored_memories(
        self, enabled_service: MemoryService
    ) -> None:
        # Store an entry directly through the underlying store
        assert enabled_service._store is not None
        enabled_service._store.store(
            _sample_entry(
                stage="design",
                title="Prior design",
                content="Build timeout logic for BuildRun controller",
            )
        )

        result = enabled_service.retrieve_for_stage(
            "design",
            {"issue_title": "timeout", "issue_description": "build timeout"},
        )
        assert "Prior design" in result
        assert "Cross-Session Memory Context" in result

    def test_retrieve_for_stage_no_matches(
        self, enabled_service: MemoryService
    ) -> None:
        result = enabled_service.retrieve_for_stage(
            "design",
            {"issue_title": "something", "issue_description": "else"},
        )
        assert result == ""


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class TestStoreFromStage:
    """store_from_stage extracts and persists memories."""

    def test_store_from_stage_returns_ids(
        self, enabled_service: MemoryService
    ) -> None:
        context = {
            "session_id": "s-1",
            "issue_title": "Timeout",
            "issue_type": "feature",
        }
        output = {
            "design_analysis": "Detailed analysis of timeout feature.",
            "risks": ["Breaking API change"],
            "implementation_plan": ["Update types", "Add tests"],
        }

        ids = enabled_service.store_from_stage("design", context, output)
        # design extractor: 1 reusable_context + 1 heuristic + 1 best_practice = 3
        assert len(ids) == 3
        assert all(isinstance(i, int) for i in ids)

    def test_store_from_stage_empty_output(
        self, enabled_service: MemoryService
    ) -> None:
        ids = enabled_service.store_from_stage(
            "design", {"session_id": "s-1"}, {}
        )
        assert ids == []


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

class TestFormatMemoriesForPrompt:
    """format_memories_for_prompt groups and formats memories."""

    def test_format_memories_for_prompt(self) -> None:
        memories = [
            _sample_entry(
                memory_type=MemoryType.best_practice,
                title="Practice A",
                content="Content A",
            ),
            _sample_entry(
                memory_type=MemoryType.heuristic,
                title="Heuristic B",
                content="Content B",
            ),
            _sample_entry(
                memory_type=MemoryType.best_practice,
                title="Practice C",
                content="Content C",
            ),
        ]

        result = MemoryService.format_memories_for_prompt(memories)
        assert "## Cross-Session Memory Context" in result
        assert "### Best Practices" in result
        assert "### Heuristics" in result
        assert "**Practice A**" in result
        assert "**Practice C**" in result
        assert "**Heuristic B**" in result

    def test_format_empty_memories(self) -> None:
        result = MemoryService.format_memories_for_prompt([])
        assert result == ""

    def test_format_truncates_at_2000_chars(self) -> None:
        # Create entries with enough content to exceed 2000 chars
        memories = [
            _sample_entry(
                memory_type=MemoryType.best_practice,
                title=f"Title {i}",
                content="X" * 300,
            )
            for i in range(20)
        ]

        result = MemoryService.format_memories_for_prompt(memories)
        assert len(result) <= 2000
        assert result.endswith("...")

    def test_format_single_memory(self) -> None:
        memories = [
            _sample_entry(
                memory_type=MemoryType.execution_note,
                title="Note",
                content="Detail",
            )
        ]

        result = MemoryService.format_memories_for_prompt(memories)
        assert "### Execution Notes" in result
        assert "**Note**: Detail" in result
