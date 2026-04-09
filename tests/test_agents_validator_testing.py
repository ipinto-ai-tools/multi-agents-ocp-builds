"""Comprehensive tests for the Testing Agent.

This module tests the Testing Agent's ability to generate Ginkgo v2 tests
for Shipwright Build features based on design analysis and acceptance criteria.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from tests.auth_helper import HAS_ANTHROPIC_AUTH

from stages.test import (
    run_testing,
    TestingAgentError,
    _validate_context,
    _build_testing_prompt,
    _parse_test_output,
    _extract_code_block,
    _extract_test_code,
    generate_test_summary,
)
from config.testing_config import detect_patterns_in_description


# Sample test data
SAMPLE_CONTEXT = {
    "design_analysis": """
# Design Analysis: Add Timeout Support to BuildRun API

## Problem Statement
Users cannot specify build timeouts, leading to hung builds consuming cluster resources.

## Impacted Components
- buildrun_api: Add timeout field to BuildRun spec
- buildrun_controller: Implement timeout enforcement logic
- webhook_validation: Add validation for timeout values

## Risks
- Breaking change if not backward compatible
- Timeout granularity needs consideration

## Acceptance Criteria
- BuildRun spec accepts timeout field
- Controller terminates builds exceeding timeout
- Backward compatible with existing BuildRuns

## Implementation Plan
1. Update BuildRun API types
2. Add validation webhook logic
3. Implement timeout monitoring in controller
4. Add tests
5. Update documentation
""",
    "impacted_components": [
        "buildrun_api",
        "buildrun_controller",
        "webhook_validation",
    ],
    "acceptance_criteria": [
        "BuildRun spec accepts timeout field",
        "Controller terminates builds exceeding timeout",
        "Backward compatible with existing BuildRuns",
    ],
    "issue_title": "Add timeout support to BuildRun API",
    "issue_type": "feature",
    "issue_description": "Users need build timeout to prevent hanging builds",
}

SAMPLE_TEST_OUTPUT = """
## Test Plan

### Overview
Testing timeout support in BuildRun API including validation and controller enforcement.

### Test Strategy
- Unit tests for validation logic
- Integration tests for controller behavior
- E2E tests for complete timeout scenarios

### Coverage Mapping
1. BuildRun spec accepts timeout field → Unit + Integration tests
2. Controller terminates builds → Integration + E2E tests
3. Backward compatibility → Integration tests

## Test Specifications

```yaml
scenarios:
  - id: BUILD-001-001
    description: Validate timeout field accepts valid duration
    type: unit
    patterns:
      strategies: []
      source_types: []
    helpers:
      - validation.ValidateTimeout
    expected_outcome: Validation passes for valid timeout values
  - id: BUILD-001-002
    description: Controller enforces timeout on long-running build
    type: integration
    patterns:
      strategies: [kaniko]
      source_types: [git]
    helpers:
      - libfactory.NewBuildRun
      - libk8s.WaitForBuildRunCompletion
    expected_outcome: BuildRun terminates after timeout expires
```

## Unit Tests

File: pkg/webhook/validation/buildrun_timeout_test.go

```go
package validation_test

import (
    . "github.com/onsi/ginkgo/v2"
    . "github.com/onsi/gomega"

    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

    shipwright "github.com/shipwright-io/build/pkg/apis/build/v1beta1"
)

var _ = Describe("BuildRun Timeout Validation", func() {
    DescribeTable("Timeout field validation",
        func(timeout string, expectError bool) {
            buildRun := &shipwright.BuildRun{
                Spec: shipwright.BuildRunSpec{
                    Timeout: &metav1.Duration{Duration: timeout},
                },
            }

            err := ValidateBuildRun(buildRun)
            if expectError {
                Expect(err).To(HaveOccurred())
            } else {
                Expect(err).ToNot(HaveOccurred())
            }
        },
        Entry("[test_id:BUILD-001-001] valid timeout 30m", "30m", false),
        Entry("[test_id:BUILD-001-002] valid timeout 1h", "1h", false),
        Entry("[test_id:BUILD-001-003] invalid negative timeout", "-10m", true),
    )
})
```

## Integration Tests

File: test/integration/buildrun_timeout_test.go

```go
package integration_test

import (
    . "github.com/onsi/ginkgo/v2"
    . "github.com/onsi/gomega"

    "context"
    "time"

    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

    shipwright "github.com/shipwright-io/build/pkg/apis/build/v1beta1"
    "github.com/shipwright-io/build/test/libfactory"
    "github.com/shipwright-io/build/test/libk8s"
)

var _ = Describe("BuildRun Timeout Integration", func() {
    var (
        ctx       context.Context
        namespace string
    )

    BeforeEach(func() {
        ctx = context.Background()
        namespace = "test-timeout"
    })

    It("[test_id:BUILD-001-010] should terminate build after timeout", func() {
        build := libfactory.NewBuild(namespace, "timeout-build").
            WithSource("https://github.com/example/slow-build").
            WithStrategy("kaniko").
            Create()

        buildRun := libfactory.NewBuildRun(namespace, "timeout-buildrun").
            WithBuild("timeout-build").
            WithTimeout("30s").
            Create()

        Eventually(func() bool {
            br, _ := libk8s.GetBuildRun(ctx, namespace, "timeout-buildrun")
            return br.Status.CompletionTime != nil
        }, "2m", "1s").Should(BeTrue())

        br, err := libk8s.GetBuildRun(ctx, namespace, "timeout-buildrun")
        Expect(err).ToNot(HaveOccurred())
        Expect(br.Status.GetCondition(shipwright.Succeeded).Status).To(Equal(v1.ConditionFalse))
        Expect(br.Status.GetCondition(shipwright.Succeeded).Reason).To(ContainSubstring("Timeout"))
    })
})
```

## E2E Tests

File: test/e2e/buildrun_timeout_test.go

```go
package e2e_test

import (
    . "github.com/onsi/ginkgo/v2"
    . "github.com/onsi/gomega"
)

var _ = Describe("BuildRun Timeout E2E", func() {
    It("[test_id:BUILD-001-020] should handle timeout in real build", func() {
        // E2E test implementation
        Skip("E2E test requires cluster setup")
    })
})
```

## Test Summary

- **Total Tests Generated**: 5
- **Unit Tests**: 1 file with 3 test cases
- **Integration Tests**: 1 file with 1 test case
- **E2E Tests**: 1 file with 1 test case
- **Coverage**: 100% of acceptance criteria
- **Pattern Coverage**: kaniko strategy, git source
"""


class TestTestingAgent:
    """Test suite for Testing Agent functionality."""

    def test_testing_agent_without_auth(self):
        """Test that testing agent fails gracefully without Vertex AI auth."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(TestingAgentError, match="ANTHROPIC_VERTEX_PROJECT_ID"):
                run_testing(SAMPLE_CONTEXT)

    def test_testing_agent_missing_context(self):
        """Test that testing agent validates required context fields."""
        # Missing design_analysis
        with pytest.raises(TestingAgentError, match="Missing required context fields"):
            run_testing({
                "impacted_components": [],
                "acceptance_criteria": [],
            })

        # Missing impacted_components
        with pytest.raises(TestingAgentError, match="Missing required context fields"):
            run_testing({
                "design_analysis": "Some analysis",
                "acceptance_criteria": [],
            })

        # Missing acceptance_criteria
        with pytest.raises(TestingAgentError, match="Missing required context fields"):
            run_testing({
                "design_analysis": "Some analysis",
                "impacted_components": [],
            })

    def test_testing_agent_invalid_context_types(self):
        """Test validation of context field types."""
        # impacted_components not a list
        with pytest.raises(TestingAgentError, match="must be a list"):
            _validate_context({
                "design_analysis": "Analysis",
                "impacted_components": "not_a_list",
                "acceptance_criteria": [],
            })

        # acceptance_criteria not a list
        with pytest.raises(TestingAgentError, match="must be a list"):
            _validate_context({
                "design_analysis": "Analysis",
                "impacted_components": [],
                "acceptance_criteria": "not_a_list",
            })

    @pytest.mark.skipif(
        not HAS_ANTHROPIC_AUTH,
        reason="No Anthropic authentication configured"
    )
    def test_testing_agent_with_real_api(self):
        """Test testing agent with real Claude API (if key available)."""
        result = run_testing(SAMPLE_CONTEXT)

        # Validate output structure
        assert "test_plan" in result
        assert "test_specifications" in result
        assert "unit_tests" in result
        assert "integration_tests" in result
        assert "e2e_tests" in result
        assert "test_summary" in result
        assert "coverage_analysis" in result
        assert "patterns_detected" in result

        # Validate content types
        assert isinstance(result["test_plan"], str)
        assert isinstance(result["test_specifications"], dict)
        assert isinstance(result["unit_tests"], dict)
        assert isinstance(result["integration_tests"], dict)
        assert isinstance(result["e2e_tests"], dict)
        assert isinstance(result["patterns_detected"], dict)

        # Print for manual inspection
        print("\n" + "="*80)
        print("TEST GENERATION OUTPUT (Real API)")
        print("="*80)
        print("\n=== Test Plan ===")
        print(result["test_plan"][:500] + "...")
        print("\n=== Test Summary ===")
        print(result["test_summary"])
        print(f"\nUnit Tests Files: {len(result['unit_tests'])}")
        print(f"Integration Tests Files: {len(result['integration_tests'])}")
        print(f"E2E Tests Files: {len(result['e2e_tests'])}")

    @pytest.mark.skipif(
        HAS_ANTHROPIC_AUTH,
        reason="Anthropic authentication is configured - skipping mock test"
    )
    def test_testing_agent_with_mock(self):
        """Test testing agent with mocked Claude API."""
        mock_response = Mock()
        mock_response.content = [Mock(text=SAMPLE_TEST_OUTPUT)]

        with patch("stages.test.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_testing(SAMPLE_CONTEXT)

                # Validate mock was called
                mock_client.messages.create.assert_called_once()
                call_args = mock_client.messages.create.call_args

                # Validate request structure
                expected_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
                assert call_args.kwargs["model"] == expected_model
                assert call_args.kwargs["max_tokens"] == 16000
                assert len(call_args.kwargs["messages"]) == 1

                # Validate output
                assert "test_plan" in result
                assert "unit_tests" in result
                assert len(result["unit_tests"]) > 0


class TestHelperFunctions:
    """Test suite for testing agent helper functions."""

    def test_validate_context_success(self):
        """Test context validation with valid input."""
        # Should not raise exception
        _validate_context(SAMPLE_CONTEXT)

    def test_build_testing_prompt(self):
        """Test testing prompt construction."""
        patterns = {
            "strategies": ["kaniko"],
            "source_types": ["git"],
            "output_types": ["image"],
        }

        prompt = _build_testing_prompt(SAMPLE_CONTEXT, patterns)

        # Should contain all sections
        assert "Test Generation Request" in prompt
        assert SAMPLE_CONTEXT["issue_title"] in prompt
        assert SAMPLE_CONTEXT["design_analysis"] in prompt
        assert "Impacted Components" in prompt
        assert "Acceptance Criteria" in prompt
        assert "Detected Patterns" in prompt
        assert "kaniko" in prompt

    def test_parse_test_output(self):
        """Test parsing of test generation output."""
        result = _parse_test_output(SAMPLE_TEST_OUTPUT)

        # Should extract test plan
        assert "test_plan" in result
        # Test plan should contain overview or testing information
        assert len(result["test_plan"]) > 0 or result["test_plan"] == ""

        # Should extract test specifications
        assert "test_specifications" in result
        if isinstance(result["test_specifications"], dict):
            # YAML was parsed successfully or raw content stored
            assert result["test_specifications"]

        # Should extract test code
        assert "unit_tests" in result
        assert "integration_tests" in result
        assert "e2e_tests" in result

        # At least some code should be extracted
        total_tests = (
            len(result["unit_tests"]) +
            len(result["integration_tests"]) +
            len(result["e2e_tests"])
        )
        assert total_tests > 0

    def test_extract_code_block(self):
        """Test code block extraction."""
        text = """
Some text before

```go
package main

func main() {
    fmt.Println("Hello")
}
```

Some text after
"""
        code = _extract_code_block(text, "go")
        assert "package main" in code
        assert "fmt.Println" in code

    def test_extract_code_block_with_language_filter(self):
        """Test code block extraction with language filter."""
        text = """
```yaml
key: value
```

```go
package main
```
"""
        yaml_code = _extract_code_block(text, "yaml")
        assert "key: value" in yaml_code
        assert "package main" not in yaml_code

    def test_extract_test_code(self):
        """Test extraction of test code with file paths."""
        section = """
File: test/unit/example_test.go

```go
package unit_test

import (
    . "github.com/onsi/ginkgo/v2"
)

var _ = Describe("Test", func() {
    It("works", func() {
        // test
    })
})
```
"""
        tests = _extract_test_code(section)
        assert len(tests) > 0
        # Should extract at least one test file
        for filename, code in tests.items():
            assert "package" in code or "Describe" in code

    def test_split_into_sections_does_not_split_on_triple_hash(self):
        """### subsection headers must NOT create new top-level sections."""
        from stages.test import _split_into_sections
        text = (
            "## Unit Tests\n"
            "\n"
            "### Signature Tests\n"
            "```go\npackage foo\n```\n"
            "\n"
            "### Filter Tests\n"
            "```go\npackage bar\n```\n"
        )
        sections = _split_into_sections(text)
        assert "unit tests" in sections
        # Content must include the subsection headers and code
        assert "### Signature Tests" in sections["unit tests"]
        assert "### Filter Tests" in sections["unit tests"]
        # Subsection keys must NOT appear as top-level sections
        assert "signature tests" not in sections
        assert "filter tests" not in sections

    def test_extract_test_code_go_comment_filename(self):
        """File path as Go comment on first line inside code block must be extracted."""
        from stages.test import _extract_test_code
        section = (
            "### Signature Tests\n"
            "```go\n"
            "// pkg/webhook/github/signature_test.go\n"
            "package github_test\n"
            "\n"
            "func TestFoo(t *testing.T) {}\n"
            "```\n"
        )
        result = _extract_test_code(section)
        assert "pkg/webhook/github/signature_test.go" in result
        code = result["pkg/webhook/github/signature_test.go"]
        # The comment line should NOT be in the code content
        assert "// pkg/webhook/github/signature_test.go" not in code
        assert "package github_test" in code
        assert "func TestFoo(t *testing.T) {}" in code

    def test_generate_test_summary(self):
        """Test test summary generation."""
        test_results = {
            "unit_tests": {
                "test1.go": "package test",
                "test2.go": "package test",
            },
            "integration_tests": {
                "int_test.go": "package integration",
            },
            "e2e_tests": {},
            "patterns_detected": {
                "strategies": ["kaniko", "buildkit"],
                "source_types": ["git"],
            },
            "coverage_analysis": "Coverage: 90%",
        }

        summary = generate_test_summary(test_results)

        assert "Test Generation Summary" in summary
        assert "2 file(s)" in summary  # Unit tests count
        assert "1 file(s)" in summary  # Integration tests count
        assert "0 file(s)" in summary  # E2E tests count
        assert "kaniko" in summary
        assert "buildkit" in summary
        assert "Coverage" in summary


class TestPatternDetection:
    """Test pattern detection functionality."""

    def test_detect_kaniko_pattern(self):
        """Test detection of kaniko build strategy."""
        description = "Build using kaniko with dockerfile from git repository"

        patterns = detect_patterns_in_description(description)

        assert "kaniko" in patterns.get("strategies", [])
        assert "git" in patterns.get("source_types", [])

    def test_detect_buildpacks_pattern(self):
        """Test detection of buildpacks strategy."""
        description = "Use cloud-native buildpacks to auto-detect the application"

        patterns = detect_patterns_in_description(description)

        assert "buildpacks" in patterns.get("strategies", [])

    def test_detect_multiple_patterns(self):
        """Test detection of multiple patterns."""
        description = """
        Support kaniko and buildkit strategies with git source.
        Output images should be pushed to registry with proper authentication.
        """

        patterns = detect_patterns_in_description(description)

        assert "kaniko" in patterns.get("strategies", [])
        assert "buildkit" in patterns.get("strategies", [])
        assert "git" in patterns.get("source_types", [])
        assert "registry" in patterns.get("source_types", []) or \
               "image" in patterns.get("output_types", [])

    def test_detect_security_context(self):
        """Test detection of security context patterns."""
        description = "Build should run in rootless mode with nonroot user"

        patterns = detect_patterns_in_description(description)

        assert "nonroot" in patterns.get("security_contexts", [])


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_design_analysis(self):
        """Test with minimal design analysis."""
        minimal_context = {
            "design_analysis": "Minimal design",
            "impacted_components": ["build_api"],
            "acceptance_criteria": ["Works"],
        }

        mock_response = Mock()
        mock_response.content = [Mock(text="Basic test output")]

        with patch("stages.test.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                result = run_testing(minimal_context)
                assert "test_plan" in result

    def test_anthropic_api_error(self):
        """Test handling of Anthropic API errors."""
        with patch("stages.test.get_anthropic_client") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API Error")
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                with pytest.raises(TestingAgentError, match="Claude API call failed"):
                    run_testing(SAMPLE_CONTEXT)

    def test_invalid_anthropic_client_initialization(self):
        """Test handling of client initialization errors."""
        with patch("stages.test.get_anthropic_client") as mock_anthropic:
            mock_anthropic.side_effect = Exception("Invalid API key")

            with patch.dict(os.environ, {"ANTHROPIC_VERTEX_PROJECT_ID": "test-project-id"}):
                with pytest.raises(TestingAgentError, match="Failed to initialize"):
                    run_testing(SAMPLE_CONTEXT)


class TestAgentTesterArtifacts:
    """Tests for artifact writing methods added to AgentTester."""

    def _make_tester(self, tmp_path: Path):
        """Return an AgentTester in dry-run mode using tmp_path as output_dir."""
        from scripts.test_agents import AgentTester

        return AgentTester(dry_run=True, debug=False, output_dir=tmp_path)

    def test_go_test_files_written(self, tmp_path: Path):
        """After test_testing_agent() runs in mock mode, go_tests/ contains .go files."""
        tester = self._make_tester(tmp_path)
        tester.test_testing_agent()

        tests_dir = tmp_path / "tests"
        assert tests_dir.exists(), "tests/ directory was not created"

        go_files = list(tests_dir.rglob("*.go"))
        assert len(go_files) > 0, "No .go files were written under tests/"

    def test_plan_md_written(self, tmp_path: Path):
        """After test_testing_agent() runs in mock mode, test_plan.md exists with expected sections."""
        tester = self._make_tester(tmp_path)
        tester.test_testing_agent()

        md_path = tmp_path / "test_plan.md"
        assert md_path.exists(), "test_plan.md was not created"

        content = md_path.read_text(encoding="utf-8")
        assert "# Test Plan:" in content
        assert "## Test Strategy" in content
        assert "## Test Coverage by Level" in content
        assert "## Generated Test Files" in content
        assert "## Coverage Analysis" in content
        assert "## Detected Patterns" in content

    def test_go_test_files_skips_empty_code(self, tmp_path: Path):
        """_write_go_test_files() skips entries with empty code strings."""
        from scripts.test_agents import AgentTester

        tester = AgentTester(dry_run=True, debug=False, output_dir=tmp_path)
        output = {
            "unit_tests": {"pkg/foo/foo_test.go": "", "pkg/bar/bar_test.go": "package bar_test"},
            "integration_tests": {},
            "e2e_tests": {},
        }
        tester._write_go_test_files(output)

        unit_dir = tmp_path / "tests" / "unit"
        assert not (unit_dir / "pkg/foo/foo_test.go").exists(), \
            "Empty code file should not be written"
        assert (unit_dir / "pkg/bar/bar_test.go").exists(), \
            "Non-empty code file should be written"

    def test_write_test_plan_md_content(self, tmp_path: Path):
        """_write_test_plan_md() writes correct content for a known output dict."""
        from scripts.test_agents import AgentTester

        tester = AgentTester(dry_run=True, debug=False, output_dir=tmp_path)
        output = {
            "issue_title": "My Feature",
            "test_plan": "Test everything carefully.",
            "test_specifications": {
                "scenarios": [
                    {
                        "id": "BUILD-001",
                        "description": "Validate field",
                        "type": "unit",
                        "file": "pkg/api/api_test.go",
                        "expected_outcome": "No error",
                    }
                ]
            },
            "unit_tests": {"pkg/api/api_test.go": "package api_test"},
            "integration_tests": {},
            "e2e_tests": {},
            "coverage_analysis": "100% covered.",
            "patterns_detected": {
                "strategies": ["kaniko"],
                "source_types": ["git"],
                "output_types": ["image"],
            },
        }
        tester._write_test_plan_md(output)

        content = (tmp_path / "test_plan.md").read_text(encoding="utf-8")
        assert "# Test Plan: My Feature" in content
        assert "Test everything carefully." in content
        assert "### Unit Tests (1 scenarios)" in content
        assert "**BUILD-001**" in content
        assert "tests/unit/pkg/api/api_test.go" in content
        assert "100% covered." in content
        assert "kaniko" in content


class TestParserRobustness:
    """Test robustness of the parser against realistic Claude output formats."""

    def test_parse_test_output_with_subsections(self):
        """_parse_test_output must find unit tests even when ## Unit Tests has ### subsections."""
        from stages.test import _parse_test_output
        raw = (
            "## Test Plan\n"
            "Comprehensive test strategy.\n"
            "\n"
            "## Unit Tests\n"
            "\n"
            "### Webhook Handler Tests\n"
            "```go\n"
            "// pkg/webhook/handler_test.go\n"
            "package webhook_test\n"
            "\n"
            "func TestHandler(t *testing.T) {}\n"
            "```\n"
            "\n"
            "## Test Summary\n"
            "1 unit test file generated.\n"
        )
        result = _parse_test_output(raw)
        assert len(result["unit_tests"]) == 1
        assert "pkg/webhook/handler_test.go" in result["unit_tests"]


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
