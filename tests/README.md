# Test Suite for Multi-Agent OpenShift Builds System

This directory contains comprehensive tests for the Design Agent, Documentation Agent, and full orchestration workflow.

## Test Files

### `test_design_agent.py`
Tests for the Design Agent that analyzes feature requests and produces design documents.

**Test Coverage:**
- Design agent with/without API key
- Real API integration (when `ANTHROPIC_API_KEY` is set)
- Mocked API responses (when key not set)
- Component-only analysis (without repository)
- Repository-based analysis
- Helper function validation
- Error handling and edge cases

**Key Test Classes:**
- `TestDesignAgent`: Core design agent functionality
- `TestHelperFunctions`: Helper function validation
- `TestEdgeCases`: Error handling and edge cases

### `test_docs_agent.py`
Tests for the Documentation Agent that generates PR summaries, release notes, and documentation changes.

**Test Coverage:**
- Docs agent with complete context
- Real API integration (when `ANTHROPIC_API_KEY` is set)
- Mocked API responses (when key not set)
- Context with test failures
- Context with coverage gaps
- Response parsing
- Error handling

**Key Test Classes:**
- `TestDocsAgent`: Core docs agent functionality
- `TestHelperFunctions`: Context building and parsing
- `TestEdgeCases`: Error scenarios
- `TestIntegration`: Full context flow

### `test_orchestration.py`
Tests for the LangGraph orchestration workflow that coordinates all agents.

**Test Coverage:**
- Full end-to-end workflow
- State management across phases
- Node execution (design and docs nodes)
- Workflow graph structure
- Error propagation
- Different issue types
- Real-world scenarios

**Key Test Classes:**
- `TestOrchestration`: Full workflow tests
- `TestWorkflowNodes`: Individual node testing
- `TestWorkflowGraph`: Graph structure validation
- `TestStateManagement`: State persistence
- `TestIntegration`: End-to-end scenarios
- `TestRealWorldScenarios`: Real Shipwright issues

## Running Tests

### Run All Tests
```bash
uv run pytest tests/ -v
```

### Run Specific Test File
```bash
uv run pytest tests/test_design_agent.py -v
uv run pytest tests/test_docs_agent.py -v
uv run pytest tests/test_orchestration.py -v
```

### Run with Output Capture Disabled (see print statements)
```bash
uv run pytest tests/ -v -s
```

### Run Only Fast Tests (skip real API calls)
```bash
# This automatically skips tests that require ANTHROPIC_API_KEY
ANTHROPIC_API_KEY= uv run pytest tests/ -v
```

### Run with Real API
```bash
# Set your API key first
export ANTHROPIC_API_KEY=your-key-here
uv run pytest tests/ -v
```

### Run Specific Test Class or Method
```bash
uv run pytest tests/test_design_agent.py::TestDesignAgent -v
uv run pytest tests/test_design_agent.py::TestDesignAgent::test_design_agent_with_mock -v
```

### Run with Coverage
```bash
uv run pytest tests/ --cov=agents --cov=graph --cov-report=html
```

## Test Behavior with/without API Key

The test suite intelligently adapts based on whether `ANTHROPIC_API_KEY` is set:

### Without API Key (Default)
- Tests use mocked Claude API responses
- Fast execution (no network calls)
- Validates code structure and logic
- Tests error handling with mock failures

### With API Key
- Tests make real Claude API calls
- Validates actual API integration
- Tests real design analysis quality
- Tests real documentation generation
- Slower execution (network latency)

**The tests will automatically:**
- Skip real API tests if key is not set
- Run mock tests if key is set (to validate mocking logic)
- Use `@pytest.mark.skipif` to conditionally run tests

## Fixtures

The `conftest.py` file provides shared fixtures:

### API Key Fixtures
- `mock_api_key`: Sets a mock API key for tests
- `no_api_key`: Ensures API key is not set

### Data Fixtures
- `sample_issue_data`: Sample GitHub issue
- `sample_design_output`: Sample design agent output
- `sample_code_changes`: Sample code modifications
- `sample_test_results`: Sample test execution results
- `sample_docs_context`: Complete context for docs agent
- `sample_workflow_state`: Complete workflow state

### Usage Example
```python
def test_with_fixtures(sample_issue_data, sample_design_output):
    result = run_design(
        title=sample_issue_data["title"],
        description=sample_issue_data["description"],
    )
    assert "design_analysis" in result
```

## Test Markers

Custom pytest markers for organizing tests:

- `@pytest.mark.real_api`: Tests requiring real API key
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Slow-running tests

### Filter by Marker
```bash
# Run only integration tests
uv run pytest tests/ -m integration -v

# Skip slow tests
uv run pytest tests/ -m "not slow" -v
```

## Example Output

### Successful Test Run
```
tests/test_design_agent.py::TestDesignAgent::test_design_agent_with_mock PASSED
tests/test_design_agent.py::TestHelperFunctions::test_build_component_context PASSED
tests/test_docs_agent.py::TestDocsAgent::test_docs_agent_with_mock PASSED
tests/test_orchestration.py::TestOrchestration::test_full_orchestration_with_mock PASSED

=================== 45 passed in 2.5s ===================
```

### With Real API
```
tests/test_design_agent.py::TestDesignAgent::test_design_agent_with_real_api PASSED
  DESIGN ANALYSIS OUTPUT (Real API)
  ================================================================================
  # Design Analysis: Add Timeout Support to BuildRun API
  ...

tests/test_orchestration.py::TestRealWorldScenarios::test_shipwright_timeout_feature PASSED
  REAL WORLD TEST: Shipwright Timeout Feature
  ================================================================================
  Components: ['buildrun_api', 'buildrun_controller', 'webhook_validation']
  ...
```

## Writing New Tests

### Test Structure Template
```python
import pytest
from unittest.mock import Mock, patch

class TestNewFeature:
    """Test suite for new feature."""

    def test_basic_functionality(self):
        """Test basic feature behavior."""
        # Arrange
        input_data = "test"

        # Act
        result = new_feature(input_data)

        # Assert
        assert result == expected_output

    def test_with_mock_api(self):
        """Test with mocked API."""
        with patch("module.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_client.messages.create.return_value = Mock(
                content=[Mock(text="response")]
            )
            mock_anthropic.return_value = mock_client

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                result = new_feature()
                assert result is not None
```

### Best Practices
1. **Use descriptive test names**: `test_design_agent_without_api_key`
2. **Test one thing per test**: Focus on single behavior
3. **Use fixtures**: Reuse common test data
4. **Mock external dependencies**: Don't rely on network/filesystem
5. **Test error cases**: Validate error handling
6. **Add docstrings**: Explain what the test validates
7. **Use assertions**: Make expectations clear

## Troubleshooting

### Tests Failing with API Key
- Check API key is valid: `echo $ANTHROPIC_API_KEY`
- Verify network connectivity
- Check API rate limits
- Review API error messages in test output

### Mock Tests Failing
- Verify mock setup matches actual API structure
- Check that patches target correct module paths
- Ensure mock return values match expected structure

### Import Errors
- Ensure you're running from project root
- Check all dependencies installed: `uv pip list`
- Verify Python path includes project directory

### Fixtures Not Found
- Check `conftest.py` is in tests directory
- Verify fixture names match usage
- Ensure pytest discovers conftest.py

## Continuous Integration

These tests are designed to run in CI environments:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    uv run pytest tests/ -v --cov=agents --cov=graph
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

**Without API key in CI:**
- Tests will use mocks
- Fast execution
- No external dependencies

**With API key in CI:**
- Tests validate real integration
- Catches API breaking changes
- Requires rate limit consideration
