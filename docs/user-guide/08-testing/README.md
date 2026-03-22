# Testing

The test suite validates all agents and the orchestration workflow using a dual-mode approach: fast offline testing with mocked responses when no API credentials are present, and full integration testing against the real Claude API when Vertex AI is configured. All 390 tests run under pytest with automatic skip logic so you never need to change commands based on your environment.

---

## Overview

| Metric | Value |
| ------ | ----- |
| Total tests | 390 |
| Core test modules | 14 |
| Mock-mode execution time | Completes in seconds |
| Real API execution time | Varies (network latency) |
| Test framework | pytest |

### Dual-Mode Testing

The suite detects your environment at collection time and adjusts automatically.

**Mock mode** runs when `ANTHROPIC_VERTEX_PROJECT_ID` is not set or the `google-auth` package is not installed. All tests that require a live API are skipped; the remaining 384 tests run entirely offline using fixtures and `unittest.mock` patches. This is the default for local development and CI pipelines without credentials.

**Real API mode** activates when `ANTHROPIC_VERTEX_PROJECT_ID` is set and `google.auth` is importable. All 390 tests run, including the 6 tests that are auto-skipped in mock mode and make actual calls to Claude via Vertex AI. Use this mode to validate end-to-end integration or catch breaking API changes.

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
- Completes in seconds
- Uses fixtures defined in `tests/conftest.py`
- 6 tests that require Vertex AI are automatically skipped via `skipif`
- Validates code structure, logic, response parsing, and error handling

The auto-skip logic is implemented in each test file using `tests/auth_helper.py`:

```python
# tests/auth_helper.py sets HAS_ANTHROPIC_AUTH at import time
from tests.auth_helper import HAS_ANTHROPIC_AUTH

@pytest.mark.skipif(not HAS_ANTHROPIC_AUTH, reason="Requires ANTHROPIC_VERTEX_PROJECT_ID")
def test_design_agent_with_real_api(...):
    ...
```

`HAS_ANTHROPIC_AUTH` is set at import time by `tests/auth_helper.py`, which checks for both the environment variable and the `google.auth` package. This means the skip decision is made once at collection, not per test. Note that `-m real_api` finds only 1 test; the primary skip mechanism is `skipif(not HAS_ANTHROPIC_AUTH)`.

### Real API Mode

- Requires `ANTHROPIC_VERTEX_PROJECT_ID` set to a valid GCP project ID
- Requires `gcloud auth application-default login` to have been run
- Makes actual Claude API calls through Vertex AI
- Validates the full integration path from agent code to API response
- Catches issues such as changed response formats or quota limits

The 6 tests that are skipped in mock mode are:

- `test_agents_validator_design.py::test_design_agent_with_real_api`
- `test_agents_validator_develop.py::test_development_agent_with_real_api`
- `test_agents_validator_docs.py::test_docs_agent_with_real_api`
- `test_agents_validator_orchestration.py::test_full_orchestration_with_real_api`
- `test_agents_validator_orchestration.py::test_shipwright_timeout_feature`
- `test_agents_validator_testing.py::test_testing_agent_with_real_api`

---

## Running Tests

| Command | Purpose |
| ------- | ------- |
| `uv run pytest tests/ -v` | All tests (auto-detects mode) |
| `uv run pytest tests/ -v -s` | All tests with captured output printed |
| `uv run pytest tests/test_agents_validator_design.py -v` | Design agent only |
| `uv run pytest tests/test_agents_validator_docs.py -v` | Docs agent only |
| `uv run pytest tests/test_agents_validator_orchestration.py -v` | Orchestration only |
| `uv run pytest tests/test_agents_code_review.py -v` | Code Review Agent only |
| `uv run pytest tests/test_agents_validator_jira.py -v` | Jira integration only |
| `uv run pytest tests/test_agents_validator_develop.py -v` | Development agent only |
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
| ---- | ----- | -------------- |
| `test_agents_code_review.py` | 90 | Code Review Agent: output parsing, severity classification, auto-fix loop routing, dry-run, validators, mock responses |
| `test_agents_validator_jira.py` | 68 | Jira ticket fetching, context injection, field parsing, error handling, dry-run mode |
| `test_agents_validator_develop.py` | 34 | Development agent code generation, prompt building, output parsing, review feedback injection |
| `test_agents_validator_orchestration.py` | 29 | Full 5-agent workflow, state management, node execution, graph routing, auto-fix loop |
| `test_agents_validator_dashboard.py` | 25 | Dashboard heartbeat, enricher pipeline, session storage, REST endpoints |
| `test_agents_validator_docs_enhanced.py` | 24 | Enhanced docs generation scenarios, RAG integration, SHIP format, JTBD docs |
| `test_agents_validator_docs.py` | 23 | Docs agent core: mock and real API, context building, section parsing, error scenarios |
| `test_agents_validator_rag.py` | 21 | RAG search, repository analysis, documentation retrieval |
| `test_agents_validator_testing.py` | 19 | Testing agent: Ginkgo v2 generation, DDT patterns, coverage analysis |
| `test_file_logger.py` | 19 | File logger, session logging, log level control, rotating handlers |
| `test_agents_validator_design.py` | 15 | Design agent: analysis, component context, parsing, error handling |
| `test_auth_config.py` | 13 | Authentication configuration, Vertex AI setup, ADC validation |
| `test_logging_integration.py` | 6 | Cross-module logging integration |
| `test_dashboard_cleanup.py` | 4 | Dashboard session cleanup and lifecycle |

### test_agents_validator_design.py (15 tests)

Three test classes cover the full design agent surface:

- `TestDesignAgent` - core functionality: mock responses, real API, component-only analysis, repository-based analysis
- `TestHelperFunctions` - validates helper utilities such as component context building
- `TestEdgeCases` - error handling and boundary conditions

### test_agents_validator_docs.py (23 tests)

Four test classes plus a standalone function:

- `TestDocsAgent` - mock and real API docs generation
- `TestHelperFunctions` - context construction and response parsing
- `TestEdgeCases` - missing data, malformed responses, API failures
- `TestIntegration` - full context flow from input to output

### test_agents_validator_orchestration.py (29 tests)

Six test classes validate the LangGraph pipeline end to end, including the auto-fix loop routing introduced by the Code Review Agent:

- `TestOrchestration` - full workflow with mock and real API
- `TestWorkflowNodes` - individual design and docs node execution
- `TestWorkflowGraph` - graph structure and edge validation
- `TestStateManagement` - state persistence across phases
- `TestIntegration` - end-to-end scenarios with realistic inputs
- `TestRealWorldScenarios` - real Shipwright issue simulations (e.g., BuildRun timeout feature)

### test_agents_code_review.py (90 tests)

Ten test classes cover the full Code Review Agent surface:

- `TestParseReviewOutput` - parsing `[BLOCKING]`/`[WARNING]`/`[SUGGESTION]` lines and `VERDICT`
- `TestFormatCodeForReview` - code formatting, file capping, and truncation marker
- `TestFeatureFlag` - `QODO_REVIEW_ENABLED=false` bypass
- `TestNoCodeFiles` - empty `code_files` skips review gracefully
- `TestDryRun` - dry-run returns `MOCK_CODE_REVIEW_PASS` without API call
- `TestClaudeReview` - Claude API mocked; validates result structure
- `TestErrorResilience` - agent returns `review_passed=True` on any error so pipeline is never blocked
- `TestValidators` - `validate_review_output` always passes, surfaces FAIL as warning
- `TestGraphRouting` - `should_continue` routes correctly for pass, fail, and max-iterations
- `TestMockResponses` - `MOCK_CODE_REVIEW_PASS`/`MOCK_CODE_REVIEW_FAIL` structure

---

## Shared Fixtures (conftest.py)

All shared test data is defined in `tests/conftest.py` and automatically available to every test file.

### Auth Fixtures

| Fixture | Mechanism | Used For |
| ------- | --------- | -------- |
| `mock_vertex_auth` | `monkeypatch.setenv` | Set `ANTHROPIC_VERTEX_PROJECT_ID=test-project-id` and `CLOUD_ML_REGION=us-east5` |
| `no_anthropic_auth` | `monkeypatch.delenv` | Clear all auth env vars to simulate unauthenticated state |

### Data Fixtures

| Fixture | Return Type | Used For |
| ------- | ----------- | -------- |
| `sample_issue_data` | `Dict[str, str]` | A realistic GitHub issue (BuildRun timeout feature request) |
| `sample_design_output` | `Dict[str, Any]` | Design agent result with analysis, components, risks, and plan |
| `sample_code_changes` | `Dict[str, str]` | Three modified Go files with descriptions |
| `sample_test_results` | `Dict[str, Dict[str, int]]` | Unit, integration, and E2E test pass/fail/skip counts |
| `sample_docs_context` | `Dict[str, Any]` | Complete docs agent input assembled from the four fixtures above |
| `sample_workflow_state` | `Dict[str, Any]` | Full LangGraph `AgentState` with all fields initialized |

### Fixture Composition

The data fixtures build on each other. `sample_docs_context` aggregates the four base fixtures, and `sample_workflow_state` reflects the complete pipeline state:

```text
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

    @pytest.mark.skipif(not HAS_ANTHROPIC_AUTH, reason="Requires ANTHROPIC_VERTEX_PROJECT_ID")
    def test_my_agent_with_real_api(self, sample_issue_data):
        """Validate agent against the live Claude API. Auto-skipped without Vertex AI."""
        result = run_my_agent(sample_issue_data["title"])
        assert result["key"]
```

**Best practices:**

1. Use descriptive names: `test_design_agent_without_api_key` not `test_1`
2. Test one behavior per test method
3. Reuse fixtures from `conftest.py` instead of repeating setup
4. Always mock external dependencies in non-real-API tests
5. Test error cases explicitly - validate the error message, not just that an exception was raised
6. Add docstrings explaining what each test validates
7. Use `@pytest.mark.skipif(not HAS_ANTHROPIC_AUTH, ...)` from `tests/auth_helper.py` for tests that require real API access

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

The test suite is designed to run in CI without credentials. Mock tests execute in seconds and have no external dependencies.

```yaml
# Example GitHub Actions step
- name: Run tests
  run: uv run pytest tests/ -v --cov=agents --cov=graph
  env:
    ANTHROPIC_VERTEX_PROJECT_ID: ${{ secrets.ANTHROPIC_VERTEX_PROJECT_ID }}
```

When `ANTHROPIC_VERTEX_PROJECT_ID` is not set as a secret, all tests guarded by `skipif(not HAS_ANTHROPIC_AUTH)` are skipped automatically and the job still passes. To run real API tests nightly, add a separate scheduled workflow that injects the secret.

---

## Troubleshooting

| Problem | Solution |
| ------- | -------- |
| `ModuleNotFoundError: google` | Install Vertex AI dependencies: `uv pip install "anthropic[vertex]"` |
| Tests hang with no output | Run with `-s` to disable output capture and see where execution stalls; check for an accidental real API call |
| Real API tests not running | Verify `ANTHROPIC_VERTEX_PROJECT_ID` is set and run `gcloud auth application-default login` |
| Import errors on test files | Run pytest from the project root; verify `PYTHONPATH` includes the project directory |
| Mock patches not applying | Confirm the patch target path matches the import in the module under test (patch where it is used, not where it is defined) |
| `conftest.py` fixtures not found | Confirm `tests/conftest.py` exists and pytest is invoked from the project root |
| Vertex AI quota errors | Check GCP console for rate limits; consider running real API tests on a schedule rather than every commit |
| `384 passed, 6 skipped` result | Expected behavior in mock mode — the 6 skipped tests require `ANTHROPIC_VERTEX_PROJECT_ID` (they use `skipif(not HAS_ANTHROPIC_AUTH)` from `tests/auth_helper.py`) |

---

← [Examples](../07-examples/README.md) | [Back to Index](../README.md)
