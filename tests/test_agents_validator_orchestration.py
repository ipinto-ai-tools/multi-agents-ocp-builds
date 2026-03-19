"""Comprehensive tests for the Orchestration Workflow.

This module tests the full LangGraph orchestration workflow that coordinates
the Design and Documentation agents through the complete issue-to-docs pipeline.
"""

import os
import pytest
from unittest.mock import patch

from tests.auth_helper import HAS_ANTHROPIC_AUTH

from agents import graph

# Import commonly used functions
orchestrate = graph.orchestrate
build_workflow = graph.build_workflow
design_node = graph.design_node
develop_node = graph.develop_node
docs_node = graph.docs_node
should_continue = graph.should_continue

# Import testing_node separately to avoid pytest collection
# (pytest tries to collect it as a test due to name starting with "testing")
_testing_node = graph.testing_node


# Sample test data
SAMPLE_ISSUE_TITLE = "Add timeout support to BuildRun API"
SAMPLE_ISSUE_DESCRIPTION = """
Users need the ability to specify a timeout for BuildRun executions to prevent
builds from hanging indefinitely.

## Requirements
- Add timeout field to BuildRun spec
- Implement timeout enforcement in BuildRun controller
- Add validation for timeout values
"""

SAMPLE_DESIGN_OUTPUT = {
    "design_analysis": """
# Design Analysis: Add Timeout Support

## Problem Statement
Users cannot specify build timeouts.

## Impacted Components
- buildrun_api
- buildrun_controller
- webhook_validation

## Risks
- Breaking changes
- Timeout granularity

## Acceptance Criteria
- BuildRun accepts timeout field
- Controller enforces timeout
""",
    "impacted_components": ["buildrun_api", "buildrun_controller", "webhook_validation"],
    "risks": ["Breaking changes", "Timeout granularity"],
    "acceptance_criteria": ["BuildRun accepts timeout field", "Controller enforces timeout"],
    "implementation_plan": ["Update API", "Add controller logic", "Write tests"],
}

SAMPLE_DEVELOPMENT_OUTPUT = {
    "code_files": ["pkg/buildrun/timeout.go", "pkg/apis/build/v1beta1/types.go"],
    "test_files": ["pkg/buildrun/timeout_test.go"],
    "code_changes": {
        "pkg/buildrun/timeout.go": "// Timeout implementation...",
        "pkg/apis/build/v1beta1/types.go": "// BuildRun spec with timeout field...",
    },
    "files_modified": ["pkg/buildrun/timeout.go", "pkg/apis/build/v1beta1/types.go", "pkg/buildrun/timeout_test.go"],
    "pr_description": "Add timeout support to BuildRun API with proper validation",
}

SAMPLE_TESTING_OUTPUT = {
    "test_plan": "Test timeout enforcement and validation",
    "test_specifications": {
        "unit": ["TestTimeoutValidation", "TestTimeoutEnforcement"],
        "integration": ["TestBuildRunWithTimeout"],
        "e2e": ["TestTimeoutEndToEnd"],
    },
    "unit_tests": {
        "pkg/buildrun/timeout_test.go": "// Ginkgo unit tests...",
    },
    "integration_tests": {
        "test/integration/timeout_test.go": "// Integration tests...",
    },
    "e2e_tests": {
        "test/e2e/timeout_test.go": "// E2E tests...",
    },
    "test_summary": "All timeout tests passing",
    "coverage_analysis": "95% coverage on timeout logic",
}

SAMPLE_DOCS_OUTPUT = {
    "pr_summary": "Add BuildRun timeout support to prevent hung builds",
    "release_notes": "### Features\n- BuildRun timeout support",
    "docs_changes": {
        "docs/buildrun-api.md": "Add timeout field documentation",
    },
    "upgrade_notes": "Backward compatible change",
    "known_limitations": "Timeout has ~10s granularity",
}


class TestOrchestration:
    """Test suite for orchestration workflow."""

    @pytest.mark.skipif(
        not HAS_ANTHROPIC_AUTH,
        reason="No Anthropic authentication configured"
    )
    def test_full_orchestration_with_real_api(self):
        """Test full orchestration with real Claude API (if key available)."""
        result = orchestrate(
            title=SAMPLE_ISSUE_TITLE,
            description=SAMPLE_ISSUE_DESCRIPTION,
            issue_type="feature",
        )

        # Validate workflow completion
        assert result["current_phase"] in ["done", "error"]

        # Validate design phase outputs
        assert "design_analysis" in result
        assert len(result["design_analysis"]) > 0
        assert isinstance(result["impacted_components"], list)

        # Validate docs phase outputs (if design succeeded)
        if result["current_phase"] == "done":
            assert "pr_summary" in result
            assert len(result["pr_summary"]) > 0
            assert "release_notes" in result
            assert "docs_changes" in result

        # Print for manual inspection
        print("\n" + "="*80)
        print("ORCHESTRATION RESULT (Real API)")
        print("="*80)
        print(f"\nPhase: {result['current_phase']}")
        print(f"\nDesign Analysis (first 500 chars):")
        print(result["design_analysis"][:500] + "...")
        print(f"\nImpacted Components: {result['impacted_components']}")

        if result["current_phase"] == "done":
            print(f"\nPR Summary (first 300 chars):")
            print(result["pr_summary"][:300] + "...")
            print(f"\nDocs Changes: {list(result['docs_changes'].keys())}")

    @pytest.mark.skipif(
        HAS_ANTHROPIC_AUTH,
        reason="Anthropic authentication is configured - skipping mock test"
    )
    def test_full_orchestration_with_mock(self):
        """Test full orchestration with mocked agents."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        # Mock all agents
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                        result = orchestrate(
                            title=SAMPLE_ISSUE_TITLE,
                            description=SAMPLE_ISSUE_DESCRIPTION,
                            issue_type="feature",
                        )

                        # Validate all agents were called
                        mock_design.assert_called_once()
                        mock_develop.assert_called_once()
                        mock_testing.assert_called_once()
                        mock_docs.assert_called_once()

                        # Validate design agent call
                        design_call = mock_design.call_args
                        assert design_call.kwargs["title"] == SAMPLE_ISSUE_TITLE
                        assert design_call.kwargs["description"] == SAMPLE_ISSUE_DESCRIPTION

                        # Validate development agent received design outputs
                        develop_call = mock_develop.call_args
                        develop_state = develop_call.args[0]
                        assert develop_state["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                        assert develop_state["implementation_plan"] == SAMPLE_DESIGN_OUTPUT["implementation_plan"]

                        # Validate docs agent received all outputs
                        docs_call = mock_docs.call_args
                        context = docs_call.args[0]
                        assert context["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                        assert context["impacted_components"] == SAMPLE_DESIGN_OUTPUT["impacted_components"]

                        # Validate final state
                        assert result["current_phase"] == "done"
                        assert result["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                        assert result["code_files"] == SAMPLE_DEVELOPMENT_OUTPUT["code_files"]
                        assert result["test_plan"] == SAMPLE_TESTING_OUTPUT["test_plan"]
                        assert result["pr_summary"] == SAMPLE_DOCS_OUTPUT["pr_summary"]
                        assert result["release_notes"] == SAMPLE_DOCS_OUTPUT["release_notes"]

    def test_orchestration_with_repo_path(self):
        """Test orchestration with repository path."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                        result = orchestrate(
                            title=SAMPLE_ISSUE_TITLE,
                            description=SAMPLE_ISSUE_DESCRIPTION,
                            repo_path="/path/to/repo",
                        )

                        # Validate repo path was passed to design agent
                        design_call = mock_design.call_args
                        assert design_call.kwargs["repo_path"] == "/path/to/repo"

    def test_orchestration_state_initialization(self):
        """Test that initial state is properly set up."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                        result = orchestrate(
                            title="Test Issue",
                            description="Test Description",
                            repo_path="/repo",
                            issue_type="bug",
                        )

                        # Validate initial state was set correctly
                        assert result["issue_title"] == "Test Issue"
                        assert result["issue_description"] == "Test Description"
                        assert result["issue_type"] == "bug"
                        assert result["repo_path"] == "/repo"
                        assert result["target_branch"] == "main"

    def test_orchestration_design_error_handling(self):
        """Test orchestration when design phase fails."""
        with patch("agents.graph.run_design") as mock_design:
            # Simulate design agent failure
            mock_design.side_effect = Exception("Design failed")

            result = orchestrate(
                title=SAMPLE_ISSUE_TITLE,
                description=SAMPLE_ISSUE_DESCRIPTION,
            )

            # Should capture error
            assert result["current_phase"] == "error"
            assert "Error in design phase" in result["design_analysis"]

    def test_orchestration_docs_error_handling(self):
        """Test orchestration when docs phase fails."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.side_effect = Exception("Docs failed")

                        result = orchestrate(
                            title=SAMPLE_ISSUE_TITLE,
                            description=SAMPLE_ISSUE_DESCRIPTION,
                        )

                        # Design, develop, and testing should succeed but docs should fail
                        assert result["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                        assert result["code_files"] == SAMPLE_DEVELOPMENT_OUTPUT["code_files"]
                        assert result["test_plan"] == SAMPLE_TESTING_OUTPUT["test_plan"]
                        assert result["current_phase"] == "error"
                        assert "Error in docs phase" in result["pr_summary"]

    def test_orchestration_develop_error_handling(self):
        """Test orchestration when development phase fails."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                mock_develop.side_effect = Exception("Development failed")

                result = orchestrate(
                    title=SAMPLE_ISSUE_TITLE,
                    description=SAMPLE_ISSUE_DESCRIPTION,
                )

                # Design should succeed but development should fail
                assert result["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                assert result["current_phase"] == "error"
                # Verify error state was set (code_files should be empty list from error state)
                assert result["code_files"] == []

    def test_orchestration_testing_error_handling(self):
        """Test orchestration when testing phase fails."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                    mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                    mock_testing.side_effect = Exception("Testing failed")

                    result = orchestrate(
                        title=SAMPLE_ISSUE_TITLE,
                        description=SAMPLE_ISSUE_DESCRIPTION,
                    )

                    # Design and development should succeed but testing should fail
                    assert result["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                    assert result["code_files"] == SAMPLE_DEVELOPMENT_OUTPUT["code_files"]
                    assert result["current_phase"] == "error"
                    assert "Error in testing phase" in result["test_plan"]


class TestWorkflowNodes:
    """Test suite for individual workflow nodes."""

    def test_design_node_success(self):
        """Test design node with successful execution."""
        with patch("agents.graph.run_design") as mock_design:
            mock_design.return_value = SAMPLE_DESIGN_OUTPUT

            state = {
                "issue_title": "Test Issue",
                "issue_description": "Test Description",
                "repo_path": None,
            }

            result = design_node(state)

            # Validate outputs
            assert result["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
            assert result["impacted_components"] == SAMPLE_DESIGN_OUTPUT["impacted_components"]
            assert result["risks"] == SAMPLE_DESIGN_OUTPUT["risks"]
            assert result["acceptance_criteria"] == SAMPLE_DESIGN_OUTPUT["acceptance_criteria"]
            assert result["current_phase"] == "design_complete"

    def test_design_node_error(self):
        """Test design node with error."""
        with patch("agents.graph.run_design") as mock_design:
            mock_design.side_effect = Exception("Design error")

            state = {
                "issue_title": "Test Issue",
                "issue_description": "Test Description",
            }

            result = design_node(state)

            # Should capture error
            assert result["current_phase"] == "error"
            assert "Error in design phase" in result["design_analysis"]

    def test_develop_node_success(self):
        """Test develop node with successful execution."""
        with patch("agents.graph.run_development") as mock_develop:
            mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT

            state = {
                "issue_title": "Test Issue",
                "issue_description": "Test Description",
                "design_analysis": SAMPLE_DESIGN_OUTPUT["design_analysis"],
                "implementation_plan": SAMPLE_DESIGN_OUTPUT["implementation_plan"],
            }

            result = develop_node(state)

            # Validate outputs
            assert result["code_files"] == SAMPLE_DEVELOPMENT_OUTPUT["code_files"]
            assert result["test_files"] == SAMPLE_DEVELOPMENT_OUTPUT["test_files"]
            assert result["code_changes"] == SAMPLE_DEVELOPMENT_OUTPUT["code_changes"]
            assert result["files_modified"] == SAMPLE_DEVELOPMENT_OUTPUT["files_modified"]
            assert result["current_phase"] == "develop_complete"

    def test_develop_node_error(self):
        """Test develop node with error."""
        with patch("agents.graph.run_development") as mock_develop:
            mock_develop.side_effect = Exception("Development error")

            state = {
                "issue_title": "Test Issue",
                "issue_description": "Test Description",
                "design_analysis": "Design content",
                "implementation_plan": ["Plan"],
            }

            result = develop_node(state)

            # Should capture error
            assert result["current_phase"] == "error"
            assert "error" in result

    def test_testing_node_success(self):
        """Test testing node with successful execution."""
        with patch("agents.graph.run_testing") as mock_testing:
            mock_testing.return_value = SAMPLE_TESTING_OUTPUT

            state = {
                "design_analysis": "Design content",
                "impacted_components": ["build_api"],
                "acceptance_criteria": ["Criteria 1"],
                "risks": ["Risk 1"],
                "implementation_plan": ["Plan"],
                "issue_title": "Title",
                "issue_description": "Description",
                "issue_type": "feature",
            }

            result = _testing_node(state)

            # Validate outputs
            assert result["test_plan"] == SAMPLE_TESTING_OUTPUT["test_plan"]
            assert result["test_specifications"] == SAMPLE_TESTING_OUTPUT["test_specifications"]
            assert result["unit_tests"] == SAMPLE_TESTING_OUTPUT["unit_tests"]
            assert result["integration_tests"] == SAMPLE_TESTING_OUTPUT["integration_tests"]
            assert result["e2e_tests"] == SAMPLE_TESTING_OUTPUT["e2e_tests"]
            assert result["current_phase"] == "testing_complete"

    def test_testing_node_error(self):
        """Test testing node with error."""
        with patch("agents.graph.run_testing") as mock_testing:
            mock_testing.side_effect = Exception("Testing error")

            state = {
                "design_analysis": "Content",
                "impacted_components": [],
                "acceptance_criteria": [],
                "risks": [],
                "implementation_plan": [],
                "issue_title": "Title",
                "issue_description": "Description",
                "issue_type": "feature",
            }

            result = _testing_node(state)

            # Should capture error
            assert result["current_phase"] == "error"
            assert "Error in testing phase" in result["test_plan"]

    def test_docs_node_success(self):
        """Test docs node with successful execution."""
        with patch("agents.graph.run_docs") as mock_docs:
            mock_docs.return_value = SAMPLE_DOCS_OUTPUT

            state = {
                "design_analysis": "Design content",
                "impacted_components": ["build_api"],
                "risks": ["Risk 1"],
                "acceptance_criteria": ["Criteria 1"],
                "implementation_plan": "Plan",
                "code_changes": {},
                "test_results": {},
                "issue_title": "Title",
                "issue_description": "Description",
                "repo_path": "/test/repo",
            }

            result = docs_node(state)

            # Validate that repo_path was passed to docs agent
            context_arg = mock_docs.call_args[0][0]
            assert "repo_path" in context_arg
            assert context_arg["repo_path"] == "/test/repo"

            # Validate outputs
            assert result["pr_summary"] == SAMPLE_DOCS_OUTPUT["pr_summary"]
            assert result["release_notes"] == SAMPLE_DOCS_OUTPUT["release_notes"]
            assert result["docs_changes"] == SAMPLE_DOCS_OUTPUT["docs_changes"]
            assert result["current_phase"] == "done"

    def test_docs_node_error(self):
        """Test docs node with error."""
        with patch("agents.graph.run_docs") as mock_docs:
            mock_docs.side_effect = Exception("Docs error")

            state = {
                "design_analysis": "Content",
                "code_changes": {},
                "test_results": {},
                "repo_path": "/test/repo",
            }

            result = docs_node(state)

            # Should capture error
            assert result["current_phase"] == "error"
            assert "Error in docs phase" in result["pr_summary"]

    def test_should_continue_design_complete(self):
        """Test should_continue when design is complete."""
        state = {"current_phase": "design_complete"}

        result = should_continue(state)

        assert result == "develop"

    def test_should_continue_develop_complete(self):
        """Test should_continue routes to code_review after development."""
        state = {"current_phase": "develop_complete"}

        result = should_continue(state)

        assert result == "code_review"

    def test_should_continue_testing_complete(self):
        """Test should_continue routes to docs after testing."""
        state = {"current_phase": "testing_complete"}

        result = should_continue(state)

        assert result == "docs"

    def test_should_continue_error(self):
        """Test should_continue when there's an error."""
        state = {"current_phase": "error"}

        result = should_continue(state)

        assert result == "end"

    def test_should_continue_unknown_phase(self):
        """Test should_continue with unknown phase."""
        state = {"current_phase": "unknown"}

        result = should_continue(state)

        assert result == "end"


class TestWorkflowGraph:
    """Test suite for workflow graph structure."""

    def test_build_workflow(self):
        """Test workflow graph construction."""
        workflow = build_workflow()

        # Workflow should be compiled and ready to use
        assert workflow is not None

        # Test with mock state
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                        initial_state = {
                            "issue_title": "Test",
                            "issue_description": "Test",
                            "issue_type": "feature",
                            "repo_path": "",
                            "target_branch": "main",
                            "current_phase": "init",
                            "approval_status": "pending",
                            "messages": [],
                            "design_analysis": "",
                            "impacted_components": [],
                            "risks": [],
                            "acceptance_criteria": [],
                            "implementation_plan": "",
                            "test_plan": "",
                            "test_specifications": {},
                            "unit_tests": {},
                            "integration_tests": {},
                            "e2e_tests": {},
                            "coverage_analysis": "",
                            "code_files": [],
                            "test_files": [],
                            "code_changes": {},
                            "files_modified": [],
                            "test_results": {},
                            "test_summary": "",
                            "coverage_gaps": [],
                            "test_failures": [],
                            "pr_summary": "",
                            "release_notes": "",
                            "docs_changes": {},
                        }

                        result = workflow.invoke(initial_state)

                        # Should complete workflow
                        assert result["current_phase"] == "done"


class TestStateManagement:
    """Test suite for state management across phases."""

    def test_state_persistence_across_phases(self):
        """Test that state is preserved across workflow phases."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                        result = orchestrate(
                            title="Test Issue",
                            description="Test Description",
                            issue_type="feature",
                        )

                        # Original inputs should be preserved
                        assert result["issue_title"] == "Test Issue"
                        assert result["issue_description"] == "Test Description"
                        assert result["issue_type"] == "feature"

                        # Design outputs should be preserved
                        assert result["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                        assert result["impacted_components"] == SAMPLE_DESIGN_OUTPUT["impacted_components"]

                        # Development outputs should be preserved
                        assert result["code_files"] == SAMPLE_DEVELOPMENT_OUTPUT["code_files"]
                        assert result["files_modified"] == SAMPLE_DEVELOPMENT_OUTPUT["files_modified"]

                        # Testing outputs should be preserved
                        assert result["test_plan"] == SAMPLE_TESTING_OUTPUT["test_plan"]
                        assert result["unit_tests"] == SAMPLE_TESTING_OUTPUT["unit_tests"]

                        # Docs outputs should be added
                        assert result["pr_summary"] == SAMPLE_DOCS_OUTPUT["pr_summary"]
                        assert result["release_notes"] == SAMPLE_DOCS_OUTPUT["release_notes"]

    def test_state_contains_all_required_fields(self):
        """Test that final state contains all expected fields."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                        result = orchestrate(
                            title="Test",
                            description="Test",
                        )

                        # Validate all expected fields are present
                        expected_fields = [
                            "issue_title", "issue_description", "issue_type",
                            "design_analysis", "impacted_components", "risks",
                            "acceptance_criteria", "implementation_plan",
                            "test_plan", "test_specifications", "unit_tests",
                            "integration_tests", "e2e_tests", "coverage_analysis",
                            "code_changes", "files_modified", "test_results",
                            "test_summary", "coverage_gaps", "test_failures",
                            "pr_summary", "release_notes", "docs_changes",
                            "current_phase", "approval_status", "messages",
                            "repo_path", "target_branch",
                        ]

                        for field in expected_fields:
                            assert field in result, f"Missing field: {field}"


class TestIntegration:
    """Integration tests for full workflow."""

    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow with all phases."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        # Setup mocks
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                        # Run orchestration
                        result = orchestrate(
                            title=SAMPLE_ISSUE_TITLE,
                            description=SAMPLE_ISSUE_DESCRIPTION,
                            repo_path=None,
                            issue_type="feature",
                        )

                        # Validate complete flow
                        assert result["current_phase"] == "done"

                        # Validate design phase
                        assert result["design_analysis"] is not None
                        assert len(result["impacted_components"]) > 0
                        assert len(result["risks"]) > 0

                        # Validate development phase
                        assert result["code_files"] is not None
                        assert len(result["code_files"]) > 0
                        assert len(result["files_modified"]) > 0

                        # Validate testing phase
                        assert result["test_plan"] is not None
                        assert result["unit_tests"] is not None
                        assert isinstance(result["unit_tests"], dict)

                        # Validate docs phase
                        assert result["pr_summary"] is not None
                        assert result["release_notes"] is not None
                        assert isinstance(result["docs_changes"], dict)

                        # Validate agent coordination
                        mock_design.assert_called_once()
                        mock_develop.assert_called_once()
                        mock_testing.assert_called_once()
                        mock_docs.assert_called_once()

                        # Validate data flow from design to development
                        develop_state = mock_develop.call_args[0][0]
                        assert develop_state["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                        assert develop_state["implementation_plan"] == SAMPLE_DESIGN_OUTPUT["implementation_plan"]

                        # Validate data flow to docs
                        docs_context = mock_docs.call_args[0][0]
                        assert docs_context["design_analysis"] == SAMPLE_DESIGN_OUTPUT["design_analysis"]
                        assert docs_context["impacted_components"] == SAMPLE_DESIGN_OUTPUT["impacted_components"]

    def test_workflow_with_different_issue_types(self):
        """Test workflow with different issue types."""
        issue_types = ["feature", "bug", "refactor", "docs"]

        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                        mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                        mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                        mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                        for issue_type in issue_types:
                            result = orchestrate(
                                title="Test Issue",
                                description="Test Description",
                                issue_type=issue_type,
                            )

                            assert result["issue_type"] == issue_type
                            assert result["current_phase"] == "done"

    def test_partial_workflow_on_design_failure(self):
        """Test that workflow stops gracefully if design fails."""
        with patch("agents.graph.run_design") as mock_design:
            with patch("agents.graph.run_development") as mock_develop:
                with patch("agents.graph.run_testing") as mock_testing:
                    with patch("agents.graph.run_docs") as mock_docs:
                        mock_design.side_effect = Exception("Design failed")

                        result = orchestrate(
                            title="Test",
                            description="Test",
                        )

                        # Design should fail, other phases should not be called
                        assert result["current_phase"] == "error"
                        mock_design.assert_called_once()
                        mock_develop.assert_not_called()
                        mock_testing.assert_not_called()
                        mock_docs.assert_not_called()


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.mark.skipif(
        not HAS_ANTHROPIC_AUTH,
        reason="No Anthropic authentication configured"
    )
    def test_shipwright_timeout_feature(self):
        """Test with real Shipwright timeout feature request."""
        result = orchestrate(
            title="Add timeout support to BuildRun API",
            description=SAMPLE_ISSUE_DESCRIPTION,
            issue_type="feature",
        )

        # Should complete successfully
        assert result["current_phase"] in ["done", "error"]

        if result["current_phase"] == "done":
            # Should identify relevant components
            components = result.get("impacted_components", [])
            assert any("buildrun" in comp.lower() for comp in components)

            # Should have substantial documentation
            assert len(result.get("pr_summary", "")) > 100

            print("\n" + "="*80)
            print("REAL WORLD TEST: Shipwright Timeout Feature")
            print("="*80)
            print(f"\nComponents: {components}")
            print(f"\nRisks: {result.get('risks', [])}")
            print(f"\nPR Summary:\n{result.get('pr_summary', '')[:300]}...")


@pytest.fixture
def sample_state():
    """Fixture providing sample workflow state."""
    return {
        "issue_title": "Test Issue",
        "issue_description": "Test Description",
        "issue_type": "feature",
        "repo_path": "",
        "target_branch": "main",
        "current_phase": "init",
        "approval_status": "pending",
        "messages": [],
        "design_analysis": "",
        "impacted_components": [],
        "risks": [],
        "acceptance_criteria": [],
        "implementation_plan": "",
        "test_plan": "",
        "test_specifications": {},
        "unit_tests": {},
        "integration_tests": {},
        "e2e_tests": {},
        "coverage_analysis": "",
        "code_files": [],
        "test_files": [],
        "code_changes": {},
        "files_modified": [],
        "test_results": {},
        "test_summary": "",
        "coverage_gaps": [],
        "test_failures": [],
        "pr_summary": "",
        "release_notes": "",
        "docs_changes": {},
    }


def test_workflow_with_sample_state(sample_state):
    """Test workflow using sample state fixture."""
    with patch("agents.graph.run_design") as mock_design:
        with patch("agents.graph.run_development") as mock_develop:
            with patch("agents.graph.run_testing") as mock_testing:
                with patch("agents.graph.run_docs") as mock_docs:
                    mock_design.return_value = SAMPLE_DESIGN_OUTPUT
                    mock_develop.return_value = SAMPLE_DEVELOPMENT_OUTPUT
                    mock_testing.return_value = SAMPLE_TESTING_OUTPUT
                    mock_docs.return_value = SAMPLE_DOCS_OUTPUT

                    workflow = build_workflow()
                    result = workflow.invoke(sample_state)

                    assert result["current_phase"] == "done"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
