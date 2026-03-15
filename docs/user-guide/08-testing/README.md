# Testing

The test suite validates all agents and the orchestration workflow using a dual-mode approach: fast offline testing with mocked responses when no API credentials are present, and full integration testing against the real Claude API when Vertex AI is configured. All 57 tests run under pytest with automatic skip logic so you never need to change commands based on your environment.

---

## Overview

| Metric | Value |
|--------|-------|
| Total tests | 57 |
| Core test modules | 3 |
| Mock-mode execution time | ~0.85 seconds |
| Real API execution time | Varies (network latency) |
| Test framework | pytest |

### Dual-Mode Testing

The suite detects your environment at collection time and adjusts automatically.

**Mock mode** runs when `ANTHROPIC_VERTEX_PROJECT_ID` is not set or the `google-auth` package is not installed. All tests that require a live API are skipped; the remaining 53 tests run entirely offline using fixtures and `unittest.mock` patches. This is the default for local development and CI pipelines without credentials.

**Real API mode** activates when `ANTHROPIC_VERTEX_PROJECT_ID` is set and `google.auth` is importable. All 57 tests run, including the 4 marked `real_api` that make actual calls to Claude via Vertex AI. Use this mode to validate end-to-end integration or catch breaking API changes.

---

## Quick Start

```bash
# Run all tests (mock mode - no API credentials needed)
uv run pytest tests/ -v

# Run with real Vertex AI API
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project
gcloud auth application-default login
uv run pytest tests/ -v
```

---

## Test Modes

### Mock Mode (Default)

- No API credentials required
- Completes in approximately 0.85 seconds
- Uses fixtures defined in `tests/conftest.py`
- All `@pytest.mark.real_api` tests are automatically skipped
- Validates code structure, logic, response parsing, and error handling

The auto-skip logic lives in `conftest.py`:

```python
# conftest.py - pytest_collection_modifyitems
if "real_api" in item.keywords and not HAS_ANTHROPIC_AUTH:
    item.add_marker(skip_real_api)
```

`HAS_ANTHROPIC_AUTH` is set at import time by `tests/auth_helper.py`, which checks for both the environment variable and the `google.auth` package. This means the skip decision is made once at collection, not per test.

### Real API Mode

- Requires `ANTHROPIC_VERTEX_PROJECT_ID` set to a valid GCP project ID
- Requires `gcloud auth application-default login` to have been run
- Makes actual Claude API calls through Vertex AI
- Validates the full integration path from agent code to API response
- Catches issues such as changed response formats or quota limits

---

## Running Tests

| Command | Purpose |
|---------|---------|
| `uv run pytest tests/ -v` | All tests (auto-detects mode) |
| `uv run pytest tests/ -v -s` | All tests with captured output printed |
| `uv run pytest tests/test_agents_validator_design.py -v` | Design agent only |
| `uv run pytest tests/test_agents_validator_docs.py -v` | Docs agent only |
| `uv run pytest tests/test_agents_validator_orchestration.py -v` | Orchestration only |
| `uv run pytest tests/ --cov=agents --cov=graph --cov-report=html` | All tests with HTML coverage report |
| `uv run pytest -m "not real_api"` | Explicitly skip real API tests |
| `uv run pytest -m real_api` | Run only real API tests |
| `uv run pytest -m integration` | Run only integration tests |
| `uv run pytest -m slow` | Run only slow-running tests |
| `uv run pytest -m "not slow"` | Skip slow tests |

To run a specific test class or method:

```bash
uv run pytest tests/test_agents_validator_design.py::TestDesignAgent -v
uv run pytest tests/test_agents_validator_design.py::TestDesignAgent::test_design_agent_with_mock -v
```

---

## Test Files

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_agents_validator_design.py` | 15 | Design agent analysis, component context, parsing, error handling |
| `test_agents_validator_docs.py` | 21 | Docs generation, context building, section splitting, error scenarios |
| `test_agents_validator_orchestration.py` | 21 | Full workflow, state management, node execution, graph structure |
| `test_agents_validator_develop.py` | - | Development agent validation |
| `test_agents_validator_testing.py` | - | Testing agent validation |
| `test_agents_validator_docs_enhanced.py` | - | Enhanced docs agent scenarios |
| `test_auth_config.py` | - | Authentication configuration |

### test_agents_validator_design.py (15 tests)

Three test classes cover the full design agent surface:

- `TestDesignAgent` - core functionality: mock responses, real API, component-only analysis, repository-based analysis
- `TestHelperFunctions` - validates helper utilities such as component context building
- `TestEdgeCases` - error handling and boundary conditions

### test_agents_validator_docs.py (21 tests)

Four test classes plus a standalone function:

- `TestDocsAgent` - mock and real API docs generation
- `TestHelperFunctions` - context construction and response parsing
- `TestEdgeCases` - missing data, malformed responses, API failures
- `TestIntegration` - full context flow from input to output

### test_agents_validator_orchestration.py (21 tests)

Six test classes validate the LangGraph pipeline end to end:

- `TestOrchestration` - full workflow with mock and real API
- `TestWorkflowNodes` - individual design and docs node execution
- `TestWorkflowGraph` - graph structure and edge validation
- `TestStateManagement` - state persistence across phases
- `TestIntegration` - end-to-end scenarios with realistic inputs
- `TestRealWorldScenarios` - real Shipwright issue simulations (e.g., BuildRun timeout feature)

---

## Shared Fixtures (conftest.py)

All shared test data is defined in `tests/conftest.py` and automatically available to every test file.

### Auth Fixtures

| Fixture | Mechanism | Used For |
|---------|-----------|---------|
| `mock_vertex_auth` | `monkeypatch.setenv` | Set `ANTHROPIC_VERTEX_PROJECT_ID=test-project-id` and `CLOUD_ML_REGION=us-east5` |
| `no_anthropic_auth` | `monkeypatch.delenv` | Clear all auth env vars to simulate unauthenticated state |

### Data Fixtures

| Fixture | Return Type | Used For |
|---------|-------------|---------|
| `sample_issue_data` | `Dict[str, str]` | A realistic GitHub issue (BuildRun timeout feature request) |
| `sample_design_output` | `Dict[str, Any]` | Design agent result with analysis, components, risks, and plan |
| `sample_code_changes` | `Dict[str, str]` | Three modified Go files with descriptions |
| `sample_test_results` | `Dict[str, Dict[str, int]]` | Unit, integration, and E2E test pass/fail/skip counts |
| `sample_docs_context` | `Dict[str, Any]` | Complete docs agent input assembled from the four fixtures above |
| `sample_workflow_state` | `Dict[str, Any]` | Full LangGraph `AgentState` with all fields initialized |

### Fixture Composition

The data fixtures build on each other. `sample_docs_context` aggregates the four base fixtures, and `sample_workflow_state` reflects the complete pipeline state:

```
sample_issue_data    ──┐
sample_design_output ──┤
sample_code_changes  ──┼──> sample_docs_context ──> sample_workflow_state
sample_test_results  ──┘
```

Use the base fixtures directly in unit tests and the composite fixtures in integration or orchestration tests.

### Usage Example

```python
def test_design_output_structure(sample_issue_data, sample_design_output):
    assert "design_analysis" in sample_design_output
    assert sample_design_output["impacted_components"] == [
        "buildrun_api",
        "buildrun_controller",
        "webhook_validation",
    ]
```

---

## Pytest Markers

Three custom markers are registered in `conftest.py`:

```python
@pytest.mark.real_api     # Auto-skipped when Vertex AI is not configured
@pytest.mark.integration  # Integration-level tests spanning multiple components
@pytest.mark.slow         # Tests with significant runtime (real API or heavy computation)
```

Markers can be combined with boolean expressions:

```bash
uv run pytest -m "integration and not slow" -v
```

---

## Writing New Tests

Use this template when adding tests for a new agent or feature:

```python
import pytest
from unittest.mock import patch, MagicMock


class TestMyAgent:
    """Tests for my_agent module."""

    def test_my_agent_with_mock(self, sample_issue_data):
        """Validate agent output structure using a mocked API response."""
        with patch("agents.my_agent.get_anthropic_client") as mock_client:
            mock_client.return_value.messages.create.return_value = MagicMock(
                content=[MagicMock(text="## Section\nContent")]
            )
            result = run_my_agent(sample_issue_data["title"])
            assert result["key"] == "expected"

    @pytest.mark.real_api
    def test_my_agent_with_real_api(self, sample_issue_data):
        """Validate agent against the live Claude API. Auto-skipped without Vertex AI."""
        result = run_my_agent(sample_issue_data["title"])
        assert result["key"]
```

**Best practices:**

1. Use descriptive names: `test_design_agent_without_api_key` not `test_1`
2. Test one behavior per test method
3. Reuse fixtures from `conftest.py` instead of repeating setup
4. Always mock external dependencies in non-`real_api` tests
5. Test error cases explicitly - validate the error message, not just that an exception was raised
6. Add docstrings explaining what each test validates
7. Mark anything touching the real API with `@pytest.mark.real_api`

---

## Coverage Report

```bash
uv run pytest tests/ --cov=agents --cov=graph --cov-report=html
```

This generates an HTML report in `htmlcov/index.html`. Open it in a browser to see line-by-line coverage for the `agents/` and `graph/` packages. The project target is 90% coverage across these modules.

To view a terminal summary instead:

```bash
uv run pytest tests/ --cov=agents --cov=graph --cov-report=term-missing
```

---

## Continuous Integration

The test suite is designed to run in CI without credentials. Mock tests execute in under one second and have no external dependencies.

```yaml
# Example GitHub Actions step
- name: Run tests
  run: uv run pytest tests/ -v --cov=agents --cov=graph
  env:
    ANTHROPIC_VERTEX_PROJECT_ID: ${{ secrets.ANTHROPIC_VERTEX_PROJECT_ID }}
```

When `ANTHROPIC_VERTEX_PROJECT_ID` is not set as a secret, all `real_api` tests are skipped automatically and the job still passes. To run real API tests nightly, add a separate scheduled workflow that injects the secret.

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| `ModuleNotFoundError: google` | Install Vertex AI dependencies: `pip install anthropic[vertex]` |
| Tests hang with no output | Run with `-s` to disable output capture and see where execution stalls; check for an accidental real API call |
| Real API tests not running | Verify `ANTHROPIC_VERTEX_PROJECT_ID` is set and run `gcloud auth application-default login` |
| Import errors on test files | Run pytest from the project root; verify `PYTHONPATH` includes the project directory |
| Mock patches not applying | Confirm the patch target path matches the import in the module under test (patch where it is used, not where it is defined) |
| `conftest.py` fixtures not found | Confirm `tests/conftest.py` exists and pytest is invoked from the project root |
| Vertex AI quota errors | Check GCP console for rate limits; consider running real API tests on a schedule rather than every commit |
| `53 passed, 4 skipped` result | Expected behavior in mock mode - the 4 skipped tests require Vertex AI credentials |

---

← [Examples](../07-examples/README.md) | [Back to Index](../README.md)
