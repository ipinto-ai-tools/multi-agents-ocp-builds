"""Comprehensive tests for the Design Agent.

This module tests the Design Agent's ability to analyze feature requests
and bug reports, producing design documents with proper component analysis,
risk assessment, and implementation planning.
"""

import os
import pytest
from unittest.mock import Mock, patch

from tests.auth_helper import HAS_ANTHROPIC_AUTH

from agents.design_agent import (
    run_design,
    DesignAgentError,
    _gather_repo_context,
    _build_component_context,
    _build_analysis_prompt,
    _parse_design_output,
)
from config.shipwright_components import COMPONENTS


# Sample test data
SAMPLE_ISSUE_TITLE = "Add timeout support to BuildRun API"
SAMPLE_ISSUE_DESCRIPTION = """
Users need the ability to specify a timeout for BuildRun executions to prevent
builds from hanging indefinitely. This should be configurable at both the Build
and BuildRun level, with BuildRun-level timeout taking precedence.

## Requirements
- Add timeout field to BuildRun spec
- Implement timeout enforcement in BuildRun controller
- Add validation for timeout values
- Update documentation and examples

## Use Case
Long-running builds that encounter network issues or hung processes can consume
cluster resources indefinitely. A timeout ensures resources are reclaimed.
"""

SAMPLE_DESIGN_OUTPUT = """
# Design Analysis: Add Timeout Support to BuildRun API

## Problem Statement
Users cannot specify build timeouts, leading to hung builds consuming cluster resources.

## Impacted Components
- buildrun_api: Add timeout field to BuildRun spec
- buildrun_controller: Implement timeout enforcement logic
- webhook_validation: Add validation for timeout values

## Risks
- Breaking change if not implemented with backward compatibility
- Timeout granularity (seconds vs minutes) needs careful consideration
- Race condition between timeout and natural build completion

## Acceptance Criteria
- BuildRun spec accepts timeout field (e.g., 30m, 1h)
- Controller terminates builds exceeding timeout
- Timeout validation rejects invalid values
- Backward compatible with existing BuildRuns

## Implementation Plan
1. Update BuildRun API types with timeout field
2. Add validation webhook logic
3. Implement timeout monitoring in controller
4. Add unit and integration tests
5. Update documentation
"""


class TestDesignAgent:
    """Test suite for Design Agent functionality."""

    def test_design_agent_without_auth(self):
        """Test that design agent fails gracefully without Vertex AI auth."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(DesignAgentError, match="ANTHROPIC_VERTEX_PROJECT_ID"):
                run_design(SAMPLE_ISSUE_TITLE, SAMPLE_ISSUE_DESCRIPTION)

    @pytest.mark.skipif(
        not HAS_ANTHROPIC_AUTH,
        reason="No Anthropic authentication configured"
    )
    def test_design_agent_with_real_api(self):
        """Test design agent with real Claude API (if key available)."""
        result = run_design(
            title=SAMPLE_ISSUE_TITLE,
            description=SAMPLE_ISSUE_DESCRIPTION,
            repo_path=None,  # No repo analysis
        )

        # Validate output structure
        assert "design_analysis" in result
        assert "impacted_components" in result
        assert "risks" in result
        assert "acceptance_criteria" in result
        assert "implementation_plan" in result

        # Validate content
        assert isinstance(result["design_analysis"], str)
        assert len(result["design_analysis"]) > 100  # Should have substantial content
        assert isinstance(result["impacted_components"], list)
        assert isinstance(result["risks"], list)
        assert isinstance(result["acceptance_criteria"], list)

        # Print for manual inspection
        print("\n" + "="*80)
        print("DESIGN ANALYSIS OUTPUT (Real API)")
        print("="*80)
        print(result["design_analysis"])
        print("\nImpacted Components:", result["impacted_components"])
        print("Risks Count:", len(result["risks"]))
        print("Acceptance Criteria Count:", len(result["acceptance_criteria"]))

    @pytest.mark.skipif(
        HAS_ANTHROPIC_AUTH,
        reason="Anthropic authentication is configured - skipping mock test"
    )
    def test_design_agent_with_mock(self):
        """Test design agent with mocked Claude API."""
        mock_response = Mock()
        mock_response.content = [Mock(text=SAMPLE_DESIGN_OUTPUT)]

        with patch("agents.design_agent.get_anthropic_client") as mock_get_client:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_design(
                    title=SAMPLE_ISSUE_TITLE,
                    description=SAMPLE_ISSUE_DESCRIPTION,
                )

                # Validate mock was called
                mock_client.messages.create.assert_called_once()
                call_args = mock_client.messages.create.call_args

                # Validate request structure
                expected_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
                assert call_args.kwargs["model"] == expected_model
                assert call_args.kwargs["max_tokens"] == 8000
                assert len(call_args.kwargs["messages"]) == 1

                # Validate output
                assert result["design_analysis"] == SAMPLE_DESIGN_OUTPUT
                assert "buildrun_api" in result["impacted_components"]
                assert "buildrun_controller" in result["impacted_components"]
                assert len(result["risks"]) > 0

    def test_design_agent_component_only(self):
        """Test design agent without repository path (component metadata only)."""
        mock_response = Mock()
        mock_response.content = [Mock(text=SAMPLE_DESIGN_OUTPUT)]

        with patch("agents.design_agent.get_anthropic_client") as mock_get_client:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_design(
                    title=SAMPLE_ISSUE_TITLE,
                    description=SAMPLE_ISSUE_DESCRIPTION,
                    repo_path=None,  # No repo analysis
                )

                # Should still produce valid output
                assert "design_analysis" in result
                assert isinstance(result["impacted_components"], list)

    def test_design_agent_with_repo_path(self):
        """Test design agent with repository path for code analysis."""
        mock_response = Mock()
        mock_response.content = [Mock(text=SAMPLE_DESIGN_OUTPUT)]

        with patch("agents.design_agent.get_anthropic_client") as mock_get_client:
            with patch("agents.design_agent.RepoSearch") as mock_repo_search:
                # Mock repository search results
                mock_searcher = Mock()
                mock_searcher.search_files.return_value = [
                    Mock(file_path="pkg/apis/build/v1beta1/buildrun_types.go"),
                ]
                mock_searcher.find_kubernetes_crds.return_value = []
                mock_searcher.analyze_go_packages.return_value = []
                mock_repo_search.return_value = mock_searcher

                mock_client = Mock()
                mock_client.messages.create.return_value = mock_response
                mock_get_client.return_value = mock_client

                with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                    result = run_design(
                        title=SAMPLE_ISSUE_TITLE,
                        description=SAMPLE_ISSUE_DESCRIPTION,
                        repo_path="/fake/repo/path",
                    )

                    # Validate repo search was called
                    mock_repo_search.assert_called_once_with("/fake/repo/path")
                    assert "design_analysis" in result


class TestHelperFunctions:
    """Test suite for design agent helper functions."""

    def test_build_component_context(self):
        """Test component context building."""
        context = _build_component_context()

        # Should contain component information
        assert "Shipwright Build Components" in context
        assert "build_api" in context
        assert "buildrun_api" in context
        assert "Build custom resource definition" in context

        # Should contain CRD types
        assert "Custom Resource Definitions" in context
        assert "Build" in context

        # Should contain build strategies
        assert "Build Strategies" in context
        assert "buildpacks-v3" in context or "Buildpacks" in context

        # Should contain OpenShift integrations
        assert "OpenShift Integrations" in context

        print("\n" + "="*80)
        print("COMPONENT CONTEXT (Sample)")
        print("="*80)
        print(context[:500] + "...\n")

    def test_build_analysis_prompt(self):
        """Test analysis prompt construction."""
        component_context = _build_component_context()

        prompt = _build_analysis_prompt(
            title=SAMPLE_ISSUE_TITLE,
            description=SAMPLE_ISSUE_DESCRIPTION,
            component_context=component_context,
            repo_context=None,
        )

        # Should contain all sections
        assert SAMPLE_ISSUE_TITLE in prompt
        assert SAMPLE_ISSUE_DESCRIPTION in prompt
        assert "Component Information" in prompt
        assert "Request" in prompt

        # Should contain analysis instructions
        assert "impacted components" in prompt.lower()
        assert "risks" in prompt.lower()
        assert "acceptance criteria" in prompt.lower()

    def test_build_analysis_prompt_with_repo_context(self):
        """Test analysis prompt with repository context."""
        component_context = _build_component_context()
        repo_context = {
            "api_files": ["pkg/apis/build/v1beta1/buildrun_types.go"],
            "controller_files": ["pkg/controller/buildrun/controller.go"],
            "package_structure": [
                {"name": "buildrun", "path": "pkg/controller/buildrun", "file_count": 5}
            ],
        }

        prompt = _build_analysis_prompt(
            title=SAMPLE_ISSUE_TITLE,
            description=SAMPLE_ISSUE_DESCRIPTION,
            component_context=component_context,
            repo_context=repo_context,
        )

        # Should contain repository context
        assert "Repository Context" in prompt
        assert "API Files Found" in prompt
        assert "Controller Files Found" in prompt
        assert "Package Structure" in prompt

    def test_parse_design_output(self):
        """Test parsing of design document output."""
        result = _parse_design_output(SAMPLE_DESIGN_OUTPUT)

        # Should extract impacted components
        assert "impacted_components" in result
        assert "buildrun_api" in result["impacted_components"]
        assert "buildrun_controller" in result["impacted_components"]
        assert "webhook_validation" in result["impacted_components"]

        # Should extract risks
        assert "risks" in result
        assert len(result["risks"]) > 0
        assert any("Breaking change" in risk for risk in result["risks"])

        # Should extract acceptance criteria
        assert "acceptance_criteria" in result
        assert len(result["acceptance_criteria"]) > 0
        assert any("timeout field" in criterion for criterion in result["acceptance_criteria"])

        # Should extract implementation plan
        assert "implementation_plan" in result
        # implementation_plan might be empty depending on parsing

    def test_gather_repo_context_error_handling(self):
        """Test repository context gathering with errors."""
        with patch("agents.design_agent.RepoSearch") as mock_repo_search:
            # Simulate repository search failure
            mock_repo_search.side_effect = Exception("Repository not found")

            context = _gather_repo_context("/nonexistent/path")

            # Should return context with error
            assert "error" in context
            assert "Repository analysis failed" in context["error"]

    def test_parse_design_output_with_missing_sections(self):
        """Test parsing when some sections are missing."""
        incomplete_output = """
        # Design Analysis

        ## Impacted Components
        - build_api

        ## Some Other Section
        This is not a tracked section.
        """

        result = _parse_design_output(incomplete_output)

        # Should handle missing sections gracefully
        assert "impacted_components" in result
        assert "build_api" in result["impacted_components"]
        assert "risks" in result
        assert "acceptance_criteria" in result
        assert "implementation_plan" in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_issue_description(self):
        """Test with empty issue description."""
        mock_response = Mock()
        mock_response.content = [Mock(text="Basic analysis")]

        with patch("agents.design_agent.get_anthropic_client") as mock_get_client:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_design(
                    title="Simple issue",
                    description="",  # Empty description
                )

                assert "design_analysis" in result

    def test_anthropic_api_error(self):
        """Test handling of Anthropic API errors."""
        with patch("agents.design_agent.get_anthropic_client") as mock_get_client:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API Error")
            mock_get_client.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                with pytest.raises(DesignAgentError, match="Claude API call failed"):
                    run_design("Title", "Description")

    def test_invalid_anthropic_client_initialization(self):
        """Test handling of client initialization errors."""
        with patch("agents.design_agent.get_anthropic_client") as mock_get_client:
            mock_get_client.side_effect = Exception("Invalid API key")

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                with pytest.raises(DesignAgentError, match="Failed to initialize"):
                    run_design("Title", "Description")


@pytest.fixture
def sample_repo_context():
    """Fixture providing sample repository context."""
    return {
        "package_structure": [
            {"name": "build", "path": "pkg/apis/build", "file_count": 10},
            {"name": "controller", "path": "pkg/controller", "file_count": 15},
        ],
        "api_files": [
            "pkg/apis/build/v1beta1/build_types.go",
            "pkg/apis/build/v1beta1/buildrun_types.go",
        ],
        "controller_files": [
            "pkg/controller/buildrun/controller.go",
        ],
        "crd_files": [
            "config/crds/shipwright.io_buildruns.yaml",
        ],
    }


def test_integration_with_real_components(sample_repo_context):
    """Integration test validating component recognition."""
    component_context = _build_component_context()

    # Verify all expected components are present
    for component_name in COMPONENTS.keys():
        assert component_name in component_context or \
               component_name.replace("_", " ") in component_context

    # Verify analysis prompt includes components
    prompt = _build_analysis_prompt(
        title="Test Issue",
        description="Test Description",
        component_context=component_context,
        repo_context=sample_repo_context,
    )

    assert len(prompt) > 1000  # Should be substantial
    assert "Component Information" in prompt
    assert "Repository Context" in prompt


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
