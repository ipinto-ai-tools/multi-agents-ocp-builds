"""Pytest configuration and shared fixtures for test suite.

This module provides common fixtures and configuration for all test modules.
"""

import os
import pytest
from typing import Dict, Any

from tests.auth_helper import has_anthropic_auth, HAS_ANTHROPIC_AUTH


@pytest.fixture
def mock_vertex_auth(monkeypatch):
    """Fixture to set mock Vertex AI auth for tests."""
    monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("CLOUD_ML_REGION", "us-east5")


@pytest.fixture
def no_anthropic_auth(monkeypatch):
    """Fixture to ensure no Anthropic authentication is configured."""
    monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)
    monkeypatch.delenv("CLOUD_ML_REGION", raising=False)


@pytest.fixture
def sample_issue_data() -> Dict[str, str]:
    """Fixture providing sample GitHub issue data."""
    return {
        "title": "Add timeout support to BuildRun API",
        "description": """
Users need the ability to specify a timeout for BuildRun executions to prevent
builds from hanging indefinitely.

## Requirements
- Add timeout field to BuildRun spec
- Implement timeout enforcement in BuildRun controller
- Add validation for timeout values
- Update documentation and examples
""",
        "type": "feature",
    }


@pytest.fixture
def sample_design_output() -> Dict[str, Any]:
    """Fixture providing sample design agent output."""
    return {
        "design_analysis": """
# Design Analysis: Add Timeout Support to BuildRun API

## Problem Statement
Users cannot specify build timeouts, leading to hung builds.

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
        "risks": [
            "Breaking change if not backward compatible",
            "Timeout granularity needs consideration",
        ],
        "acceptance_criteria": [
            "BuildRun spec accepts timeout field",
            "Controller terminates builds exceeding timeout",
            "Backward compatible with existing BuildRuns",
        ],
        "implementation_plan": [
            "Update BuildRun API types",
            "Add validation webhook logic",
            "Implement timeout monitoring in controller",
            "Add tests",
            "Update documentation",
        ],
    }


@pytest.fixture
def sample_code_changes() -> Dict[str, str]:
    """Fixture providing sample code changes."""
    return {
        "pkg/apis/build/v1beta1/buildrun_types.go": "Added Timeout *metav1.Duration field",
        "pkg/controller/buildrun/controller.go": "Implemented timeout monitoring",
        "pkg/webhook/validation/buildrun.go": "Added timeout validation",
    }


@pytest.fixture
def sample_test_results() -> Dict[str, Dict[str, int]]:
    """Fixture providing sample test results."""
    return {
        "unit_tests": {"passed": 45, "failed": 0, "skipped": 0},
        "integration_tests": {"passed": 12, "failed": 0, "skipped": 0},
        "e2e_tests": {"passed": 8, "failed": 0, "skipped": 1},
    }


@pytest.fixture
def sample_docs_context(
    sample_issue_data,
    sample_design_output,
    sample_code_changes,
    sample_test_results,
) -> Dict[str, Any]:
    """Fixture providing complete context for docs agent."""
    return {
        "issue_title": sample_issue_data["title"],
        "issue_description": sample_issue_data["description"],
        "issue_type": sample_issue_data["type"],
        "design_analysis": sample_design_output["design_analysis"],
        "implementation_plan": "\n".join(sample_design_output["implementation_plan"]),
        "impacted_components": sample_design_output["impacted_components"],
        "risks": sample_design_output["risks"],
        "acceptance_criteria": sample_design_output["acceptance_criteria"],
        "code_changes": sample_code_changes,
        "files_modified": list(sample_code_changes.keys()),
        "test_results": sample_test_results,
        "test_summary": "All critical tests passing. One E2E test skipped.",
        "coverage_gaps": [],
        "test_failures": [],
    }


@pytest.fixture
def sample_workflow_state() -> Dict[str, Any]:
    """Fixture providing complete workflow state."""
    return {
        "issue_title": "Add timeout support to BuildRun API",
        "issue_description": "Users need build timeout configuration",
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
        "code_changes": {},
        "files_modified": [],
        "test_results": {},
        "test_summary": "",
        "coverage_gaps": [],
        "test_failures": [],
        "pr_summary": "",
        "release_notes": "",
        "docs_changes": {},
        "jtbd_documentation": "",
    }


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "real_api: mark test as requiring real Anthropic API (skip if Vertex AI not configured)"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on conditions."""
    skip_real_api = pytest.mark.skip(
        reason="No Vertex AI authentication configured (set ANTHROPIC_VERTEX_PROJECT_ID)"
    )

    for item in items:
        # Auto-skip real API tests if no auth configured
        if "real_api" in item.keywords and not HAS_ANTHROPIC_AUTH:
            item.add_marker(skip_real_api)
