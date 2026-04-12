"""Tests for memory.extractor — rule-based memory extraction from stage outputs."""

from __future__ import annotations

from memory.extractor import extract_memories
from memory.models import MemoryType


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _base_context(
    session_id: str = "sess-1",
    issue_title: str = "Add timeout support",
    issue_type: str = "feature",
    impacted_components: list[str] | None = None,
) -> dict:
    return {
        "session_id": session_id,
        "issue_title": issue_title,
        "issue_type": issue_type,
        "impacted_components": impacted_components or ["buildrun_api"],
    }


# ---------------------------------------------------------------------------
# Design extractor
# ---------------------------------------------------------------------------

class TestExtractDesign:
    """Design stage extracts reusable_context, heuristic, and best_practice."""

    def test_extract_design_all_fields(self) -> None:
        context = _base_context()
        output = {
            "design_analysis": "Detailed design analysis content here.",
            "risks": ["Risk of breaking change", "Timeout edge cases"],
            "implementation_plan": ["Step 1: update API", "Step 2: add tests"],
        }

        entries = extract_memories("design", context, output)

        # 1 reusable_context (design_analysis)
        # 2 heuristics (one per risk)
        # 1 best_practice (implementation plan)
        assert len(entries) == 4

        types = [e.memory_type for e in entries]
        assert types.count(MemoryType.reusable_context) == 1
        assert types.count(MemoryType.heuristic) == 2
        assert types.count(MemoryType.best_practice) == 1

    def test_extract_design_session_and_tags(self) -> None:
        context = _base_context(
            session_id="s-42",
            impacted_components=["comp-a", "comp-b"],
        )
        output = {"design_analysis": "Some analysis"}

        entries = extract_memories("design", context, output)
        assert len(entries) == 1
        assert entries[0].session_id == "s-42"
        assert entries[0].tags == ["comp-a", "comp-b"]
        assert entries[0].stage == "design"

    def test_extract_design_no_risks_no_plan(self) -> None:
        output = {"design_analysis": "Just the analysis"}
        entries = extract_memories("design", _base_context(), output)
        assert len(entries) == 1
        assert entries[0].memory_type == MemoryType.reusable_context


# ---------------------------------------------------------------------------
# Develop extractor
# ---------------------------------------------------------------------------

class TestExtractDevelop:
    """Develop stage extracts execution_note, anti_pattern, and best_practice."""

    def test_extract_develop_code_files(self) -> None:
        context = _base_context()
        output = {
            "code_files": [{"path": "main.go"}, {"path": "handler.go"}],
            "test_files": [{"path": "main_test.go"}],
        }

        entries = extract_memories("develop", context, output)
        assert len(entries) == 1
        assert entries[0].memory_type == MemoryType.execution_note
        assert "main.go" in entries[0].content
        assert "handler.go" in entries[0].content
        assert "main_test.go" in entries[0].content

    def test_extract_develop_security_notes(self) -> None:
        context = _base_context()
        output = {
            "code_files": [],
            "security_notes": "Ensure RBAC is configured properly.",
        }

        entries = extract_memories("develop", context, output)
        assert len(entries) == 1
        assert entries[0].memory_type == MemoryType.best_practice
        assert "RBAC" in entries[0].content

    def test_extract_develop_review_passed_no_anti_patterns(self) -> None:
        context = _base_context()
        output = {
            "code_files": [],
            "review_passed": True,
            "review_findings": ["Minor style issue"],
        }

        entries = extract_memories("develop", context, output)
        # review_passed=True -> no anti_pattern entries
        anti = [e for e in entries if e.memory_type == MemoryType.anti_pattern]
        assert len(anti) == 0


class TestExtractDevelopReviewFailed:
    """When review_passed=False, anti-pattern entries are created."""

    def test_extract_develop_review_failed(self) -> None:
        context = _base_context()
        output = {
            "code_files": [],
            "review_passed": False,
            "review_findings": [
                "Missing error handling in timeout path",
                "No unit tests for edge case",
            ],
        }

        entries = extract_memories("develop", context, output)
        anti = [e for e in entries if e.memory_type == MemoryType.anti_pattern]
        assert len(anti) == 2
        assert "Missing error handling" in anti[0].content

    def test_extract_develop_review_failed_empty_findings(self) -> None:
        context = _base_context()
        output = {
            "code_files": [],
            "review_passed": False,
            "review_findings": [],
        }

        entries = extract_memories("develop", context, output)
        anti = [e for e in entries if e.memory_type == MemoryType.anti_pattern]
        assert len(anti) == 0


# ---------------------------------------------------------------------------
# Testing extractor
# ---------------------------------------------------------------------------

class TestExtractTesting:
    """Testing stage extracts reusable_context and heuristic."""

    def test_extract_testing(self) -> None:
        context = _base_context()
        output = {
            "test_plan": "Comprehensive test plan for timeout feature.",
            "coverage_analysis": "80% line coverage, 65% branch coverage.",
        }

        entries = extract_memories("testing", context, output)
        assert len(entries) == 2

        types = {e.memory_type for e in entries}
        assert MemoryType.reusable_context in types
        assert MemoryType.heuristic in types

    def test_extract_testing_no_coverage(self) -> None:
        context = _base_context()
        output = {"test_plan": "Basic plan"}

        entries = extract_memories("testing", context, output)
        assert len(entries) == 1
        assert entries[0].memory_type == MemoryType.reusable_context

    def test_extract_testing_empty_coverage(self) -> None:
        context = _base_context()
        output = {"test_plan": "Plan", "coverage_analysis": "   "}

        entries = extract_memories("testing", context, output)
        # Whitespace-only coverage is treated as empty
        assert len(entries) == 1


# ---------------------------------------------------------------------------
# Docs extractor
# ---------------------------------------------------------------------------

class TestExtractDocs:
    """Docs stage extracts reusable_context from PR summary."""

    def test_extract_docs(self) -> None:
        context = _base_context()
        output = {"pr_summary": "Added timeout support to BuildRun API."}

        entries = extract_memories("docs", context, output)
        assert len(entries) == 1
        assert entries[0].memory_type == MemoryType.reusable_context
        assert "timeout" in entries[0].content.lower()

    def test_extract_docs_empty_summary(self) -> None:
        context = _base_context()
        output = {"pr_summary": ""}

        entries = extract_memories("docs", context, output)
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestExtractEdgeCases:
    """Empty outputs and unknown stages."""

    def test_extract_empty_output(self) -> None:
        entries = extract_memories("design", _base_context(), {})
        assert entries == []

    def test_extract_unknown_stage(self) -> None:
        entries = extract_memories("unknown_stage", _base_context(), {"data": "value"})
        assert entries == []

    def test_extract_missing_keys(self) -> None:
        entries = extract_memories("develop", _base_context(), {"unrelated": "field"})
        assert entries == []

    def test_extract_whitespace_only_content(self) -> None:
        output = {"design_analysis": "   \n  "}
        entries = extract_memories("design", _base_context(), output)
        assert entries == []
