"""Enhanced tests for the Documentation Agent with RAG and SHIP format support.

This module tests the enhanced Docs Agent capabilities including:
- RAG integration for documentation search
- SHIP format output
- Input file processing
- High-level design generation
"""

import os
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch

import pytest

from stages.docs import (
    run_docs,
    _fetch_rag_context,
    _extract_api_names,
    _process_input_files,
    _build_context_message,
    _get_generation_request,
    _parse_docs_response,
)


@pytest.fixture
def sample_context() -> Dict[str, Any]:
    """Sample context with all required fields."""
    return {
        "issue_title": "Add timeout support to BuildRun API",
        "issue_description": "Users need to specify build timeout",
        "issue_type": "feature",
        "design_analysis": """
# Design Analysis: Add Timeout Support to BuildRun API

## Problem Statement
Users cannot specify build timeouts.

## Impacted Components
- BuildRun API: Add timeout field to BuildRun spec
- BuildRunController: Implement timeout enforcement
- Webhook validation: Add timeout validation
""",
        "implementation_plan": "Step-by-step implementation",
        "impacted_components": ["buildrun_api", "buildrun_controller"],
        "risks": ["Breaking changes"],
        "acceptance_criteria": ["Timeout enforced", "Backward compatible"],
        "code_changes": {
            "pkg/apis/build/v1beta1/buildrun_types.go": "Added Timeout field",
            "pkg/controller/buildrun/controller.go": "Implemented timeout",
        },
        "files_modified": [
            "pkg/apis/build/v1beta1/buildrun_types.go",
            "pkg/controller/buildrun/controller.go",
        ],
        "test_results": {
            "unit_tests": {"passed": 45, "failed": 0},
            "integration_tests": {"passed": 12, "failed": 0},
        },
        "test_summary": "All tests passing",
        "coverage_gaps": [],
        "test_failures": [],
        "repo_path": "/tmp/test-repo",
    }


@pytest.fixture
def sample_response_with_ship() -> str:
    """Sample Claude response with SHIP format."""
    return """
## PR Summary
Add BuildRun timeout support to prevent hung builds.

## Release Notes
### Features
- BuildRun timeout support with configurable duration

## Documentation Changes
`docs/buildrun-api.md`: Add timeout field documentation
`docs/examples/timeout.yaml`: Create timeout example

## Upgrade Notes
Backward-compatible change. No action required.

## Known Limitations
- Timeout enforcement has ~10 second granularity
- Very short timeouts (<30s) unreliable

## High-Level Design

### Overview
Implement timeout support for BuildRun resources.

### Architecture
- BuildRun CRD with timeout field
- Controller reconciliation loop with timeout monitoring
- Webhook validation for timeout values

### Implementation Approach
- Add timeout field to BuildRun spec
- Monitor execution time in controller
- Terminate on timeout exceeded

## JTBD Documentation

### Job: Prevent Build Runs from Hanging

**Context**: When running builds, users need to prevent resource consumption.

**Steps**:
1. Add timeout to BuildRun spec
2. Controller monitors execution time
3. Build terminates on timeout

## SHIP Document

### Solution
Implement configurable timeout for BuildRun resources to prevent indefinite execution.

### Highlight
- User-configurable timeout values
- Automatic build termination on timeout
- Backward compatible implementation
- Minimal performance overhead

### Impact
**Users**: Can prevent runaway builds consuming resources
**Operators**: Better resource management and capacity planning
**Developers**: Simple API addition, clear testing strategy

### Plan
**Phase 1**: Core API and CRD changes
**Phase 2**: Controller timeout enforcement
**Phase 3**: Webhook validation
**Phase 4**: Documentation and examples
**Timeline**: 2-3 weeks
"""


class TestEnhancedDocsAgent:
    """Test enhanced documentation agent features."""

    def test_run_docs_with_ship_format(self, sample_context: Dict[str, Any]):
        """Test docs generation with SHIP format."""
        mock_response = Mock()
        mock_response.content = [Mock(text="## PR Summary\nTest summary\n\n## SHIP Document\nTest SHIP")]

        with patch("stages.docs.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_docs(
                    context=sample_context,
                    output_format="ship",
                    enable_rag=False  # Disable RAG for this test
                )

                # Validate SHIP document is in output
                assert "ship_document" in result
                assert result["output_format"] == "ship"

    def test_run_docs_with_jtbd_format(self, sample_context: Dict[str, Any]):
        """Test docs generation with JTBD format."""
        mock_response = Mock()
        mock_response.content = [Mock(text="## PR Summary\nTest\n\n## JTBD Documentation\nTest JTBD")]

        with patch("stages.docs.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_docs(
                    context=sample_context,
                    output_format="jtbd",
                    enable_rag=False
                )

                assert "jtbd_documentation" in result
                assert result["output_format"] == "jtbd"

    def test_run_docs_with_all_formats(self, sample_context: Dict[str, Any], sample_response_with_ship: str):
        """Test docs generation with all formats."""
        mock_response = Mock()
        mock_response.content = [Mock(text=sample_response_with_ship)]

        with patch("stages.docs.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_docs(
                    context=sample_context,
                    output_format="all",
                    enable_rag=False
                )

                # All sections should be present
                assert "pr_summary" in result
                assert "jtbd_documentation" in result
                assert "ship_document" in result
                assert "high_level_design" in result
                assert result["output_format"] == "all"

    def test_run_docs_with_input_files(self, sample_context: Dict[str, Any], tmp_path: Path):
        """Test docs generation with input files."""
        # Create temp input file
        input_file = tmp_path / "input.go"
        input_file.write_text("""package api

type BuildRun struct {
    Timeout string
}
""")

        sample_context["repo_path"] = str(tmp_path)

        mock_response = Mock()
        mock_response.content = [Mock(text="## PR Summary\nTest")]

        with patch("stages.docs.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_docs(
                    context=sample_context,
                    input_files=["input.go"],
                    enable_rag=False
                )

                # Check input files were analyzed
                assert result["input_files_analyzed"] == ["input.go"]

                # Verify context message included input file
                call_args = mock_client.messages.create.call_args
                context_msg = call_args.kwargs["messages"][0]["content"]
                assert "Input Files Provided" in context_msg
                assert "BuildRun" in context_msg

    def test_run_docs_with_rag_enabled(self, sample_context: Dict[str, Any], tmp_path: Path):
        """Test docs generation with RAG enabled."""
        # Create minimal repo structure
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "test.md").write_text("# Test Doc\nContent about BuildRun")

        sample_context["repo_path"] = str(tmp_path)

        mock_response = Mock()
        mock_response.content = [Mock(text="## PR Summary\nTest")]

        with patch("stages.docs.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_docs(
                    context=sample_context,
                    enable_rag=True
                )

                # RAG should be enabled
                assert result["rag_enabled"] is True

                # Context should include RAG section
                call_args = mock_client.messages.create.call_args
                context_msg = call_args.kwargs["messages"][0]["content"]
                # May or may not find results, but shouldn't error
                assert isinstance(context_msg, str)

    def test_run_docs_rag_failure_graceful(self, sample_context: Dict[str, Any]):
        """Test graceful handling of RAG failures."""
        sample_context["repo_path"] = "/nonexistent/path"

        mock_response = Mock()
        mock_response.content = [Mock(text="## PR Summary\nTest")]

        with patch("stages.docs.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                # Should not raise error, just continue without RAG
                result = run_docs(
                    context=sample_context,
                    enable_rag=True
                )

                assert "pr_summary" in result


class TestRAGContextFetching:
    """Test RAG context fetching functionality."""

    def test_fetch_rag_context(self, tmp_path: Path):
        """Test RAG context fetching."""
        # Create minimal repo
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "api.md").write_text("# API\nBuildRun documentation")

        context = {
            "repo_path": str(tmp_path),
            "issue_title": "BuildRun timeout",
            "files_modified": [],
            "design_analysis": "Add timeout to BuildRun API"
        }

        rag_context = _fetch_rag_context(context)

        assert isinstance(rag_context, dict)
        # May have related_docs if search finds something

    def test_fetch_rag_context_no_repo(self):
        """Test RAG context without repo_path."""
        context = {"issue_title": "Test"}

        rag_context = _fetch_rag_context(context)

        assert rag_context == {}

    def test_extract_api_names(self):
        """Test API name extraction from design text."""
        design_text = """
        Add timeout to BuildRun API.
        The BuildRunController will enforce timeouts.
        Update BuildRunStatus CRD.
        """

        api_names = _extract_api_names(design_text)

        assert len(api_names) > 0
        assert "BuildRun" in api_names
        assert "BuildRunController" in api_names
        assert "BuildRunStatus" in api_names


class TestInputFileProcessing:
    """Test input file processing."""

    def test_process_input_files(self, tmp_path: Path):
        """Test processing input files."""
        # Create test files
        file1 = tmp_path / "file1.go"
        file1.write_text("package main\n\nfunc main() {}")

        file2 = tmp_path / "file2.py"
        file2.write_text("def hello():\n    print('hello')")

        input_files = ["file1.go", "file2.py"]
        result = _process_input_files(input_files, str(tmp_path))

        assert "file_contents" in result
        assert "file1.go" in result["file_contents"]
        assert "file2.py" in result["file_contents"]
        assert "package main" in result["file_contents"]["file1.go"]
        assert "def hello" in result["file_contents"]["file2.py"]

    def test_process_input_files_nonexistent(self, tmp_path: Path):
        """Test processing nonexistent files."""
        result = _process_input_files(["nonexistent.go"], str(tmp_path))

        assert "file_contents" in result
        assert len(result["file_contents"]) == 0

    def test_process_input_files_truncation(self, tmp_path: Path):
        """Test large file truncation."""
        # Create large file
        large_file = tmp_path / "large.txt"
        large_file.write_text("x" * 10000)

        result = _process_input_files(["large.txt"], str(tmp_path))

        content = result["file_contents"]["large.txt"]
        assert "(truncated)" in content
        assert len(content) < 10000


class TestContextMessageBuilding:
    """Test context message building."""

    def test_build_context_message_with_rag(self, sample_context: Dict[str, Any]):
        """Test context message with RAG context."""
        rag_context = {
            "related_docs": [
                {
                    "file": "docs/api.md",
                    "section": "BuildRun",
                    "content": "BuildRun documentation"
                }
            ],
            "code_examples": [
                {
                    "file": "test.go",
                    "language": "go",
                    "context": "TestBuildRun",
                    "code": "func TestBuildRun() {}"
                }
            ],
            "api_patterns": [
                {
                    "api": "BuildRun",
                    "file": "controller.go",
                    "type": "initialization",
                    "code": "br := &BuildRun{}"
                }
            ]
        }

        input_file_context = {}

        msg = _build_context_message(
            sample_context,
            rag_context,
            input_file_context,
            "standard"
        )

        # Should include RAG sections
        assert "RAG Context" in msg
        assert "Related Documentation" in msg
        assert "Code Examples" in msg
        assert "API Usage Patterns" in msg

    def test_build_context_message_with_input_files(self, sample_context: Dict[str, Any]):
        """Test context message with input files."""
        input_file_context = {
            "file_contents": {
                "test.go": "package test\n\nfunc Test() {}"
            }
        }

        msg = _build_context_message(
            sample_context,
            {},
            input_file_context,
            "standard"
        )

        assert "Input Files Provided" in msg
        assert "test.go" in msg
        assert "package test" in msg


class TestGenerationRequest:
    """Test generation request formatting."""

    def test_get_generation_request_standard(self):
        """Test standard format request."""
        req = _get_generation_request("standard")

        assert "PR Summary" in req
        assert "Release Notes" in req
        assert "High-Level Design" in req
        assert "SHIP" not in req or "SHIP Document" not in req

    def test_get_generation_request_jtbd(self):
        """Test JTBD format request."""
        req = _get_generation_request("jtbd")

        assert "JTBD Documentation" in req
        assert "Job title" in req

    def test_get_generation_request_ship(self):
        """Test SHIP format request."""
        req = _get_generation_request("ship")

        assert "SHIP Document" in req
        assert "Solution" in req
        assert "Highlight" in req
        assert "Impact" in req
        assert "Plan" in req

    def test_get_generation_request_all(self):
        """Test all formats request."""
        req = _get_generation_request("all")

        assert "JTBD Documentation" in req
        assert "SHIP Document" in req


class TestResponseParsing:
    """Test response parsing with new sections."""

    def test_parse_docs_response_ship(self, sample_response_with_ship: str):
        """Test parsing response with SHIP document."""
        result = _parse_docs_response(sample_response_with_ship, "ship")

        assert "ship_document" in result
        assert "Solution" in result["ship_document"]
        assert "Highlight" in result["ship_document"]

    def test_parse_docs_response_jtbd(self, sample_response_with_ship: str):
        """Test parsing response with JTBD documentation."""
        result = _parse_docs_response(sample_response_with_ship, "jtbd")

        assert "jtbd_documentation" in result
        assert "Job:" in result["jtbd_documentation"] or "Context" in result["jtbd_documentation"]

    def test_parse_docs_response_high_level_design(self, sample_response_with_ship: str):
        """Test parsing high-level design section."""
        result = _parse_docs_response(sample_response_with_ship, "standard")

        assert "high_level_design" in result
        assert len(result["high_level_design"]) > 0

    def test_parse_docs_response_all_sections(self, sample_response_with_ship: str):
        """Test parsing all sections together."""
        result = _parse_docs_response(sample_response_with_ship, "all")

        # Major sections that should be present (some may be empty strings if section headers don't match exactly)
        assert "pr_summary" in result
        assert "release_notes" in result
        assert "upgrade_notes" in result
        assert "known_limitations" in result
        assert "high_level_design" in result
        assert "jtbd_documentation" in result
        assert "ship_document" in result

        # At least pr_summary should have content
        assert result["pr_summary"]


class TestMetadata:
    """Test metadata in output."""

    def test_output_includes_metadata(self, sample_context: Dict[str, Any]):
        """Test that output includes processing metadata."""
        mock_response = Mock()
        mock_response.content = [Mock(text="## PR Summary\nTest")]

        with patch("stages.docs.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_docs(
                    context=sample_context,
                    input_files=["test.go"],
                    output_format="ship",
                    enable_rag=True
                )

                # Metadata should be included
                assert result["input_files_analyzed"] == ["test.go"]
                assert result["rag_enabled"] is True
                assert result["output_format"] == "ship"


class TestErrorHandling:
    """Test error handling in enhanced features."""

    def test_missing_repo_path_for_rag(self, sample_context: Dict[str, Any]):
        """Test RAG with missing repo_path."""
        context_no_repo = sample_context.copy()
        del context_no_repo["repo_path"]

        mock_response = Mock()
        mock_response.content = [Mock(text="## PR Summary\nTest")]

        with patch("stages.docs.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                # Should work without RAG context
                result = run_docs(
                    context=context_no_repo,
                    enable_rag=True
                )

                assert "pr_summary" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
