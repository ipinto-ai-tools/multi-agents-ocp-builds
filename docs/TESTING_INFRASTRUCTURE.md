# Testing Infrastructure

Comprehensive testing infrastructure for the multi-agent system with dry-run mode, debug logging, and future MCP server integration.

## Overview

The testing infrastructure enables manual and automated testing of agents without requiring live API calls or external service dependencies. All artifacts are stored locally for inspection and debugging.

## Components

### 1. Test CLI (`scripts/test_agents.py`)

Main command-line interface for testing agents individually or as a complete workflow.

**Features:**
- Individual agent testing (design, testing, docs)
- Complete E2E workflow testing
- Dashboard functionality testing
- Dry-run mode with mock responses (no API calls)
- Debug mode with verbose logging
- Local artifact storage
- Prepared for future MCP server integration

### 2. Mock Responses (`config/mock_responses.py`)

Pre-configured mock responses for each agent type. Used in dry-run mode to simulate Claude API responses without making actual API calls.

**Includes:**
- Design agent mock output (design analysis, components, risks, criteria)
- Testing agent mock output (test plans, specifications, Ginkgo code)
- Docs agent mock output (PR summary, release notes, documentation)

### 3. Logging Configuration (`utils/logging_config.py`)

Centralized logging setup with colored console output, file logging, and structured log messages.

**Features:**
- Debug and info log levels
- Colored console output (when running in terminal)
- File-based logging with timestamps
- Agent-specific loggers
- API call tracking
- Error reporting with tracebacks

### 4. MCP Server Stubs (`mcp/`)

Stub implementations for future MCP server integrations with GitHub and Jira.

**Status:** Not yet implemented - stubs provide interface definitions

**Future capabilities:**
- GitHub: Issues, PRs, workflows, repository operations
- Jira: Issues, transitions, comments, sprints

## Usage

### Test Individual Agents

Test a specific agent in isolation:

```bash
# Test design agent with dry-run (no API calls)
uv run python scripts/test_agents.py \
  --agent design \
  --dry-run \
  --debug

# Test testing agent with real API
uv run python scripts/test_agents.py \
  --agent testing \
  --title "Add timeout support" \
  --description "Users need build timeout configuration"

# Test docs agent with custom output directory
uv run python scripts/test_agents.py \
  --agent docs \
  --dry-run \
  --output-dir /tmp/my-test-output
```

### Test E2E Workflow

Test the complete workflow from design through documentation:

```bash
# E2E with dry-run
uv run python scripts/test_agents.py \
  --e2e \
  --dry-run \
  --debug

# E2E with real API
uv run python scripts/test_agents.py \
  --e2e \
  --title "Add timeout support to BuildRun" \
  --description "Users need to configure max execution time for builds" \
  --debug
```

### Test Dashboard

Verify dashboard components are working correctly:

```bash
# Test dashboard (dry-run safe)
uv run python scripts/test_agents.py \
  --dashboard \
  --debug

# Test with live dashboard (requires dashboard to be running)
# Terminal 1:
uv run --with fastapi --with "uvicorn[standard]" python scripts/run_dashboard.py

# Terminal 2:
uv run python scripts/test_agents.py \
  --dashboard
```

## Command-Line Options

### Test Modes (Required - choose one)

| Option | Description |
|--------|-------------|
| `--agent {design\|testing\|docs}` | Test specific agent individually |
| `--e2e` | Test complete E2E workflow (all agents) |
| `--dashboard` | Test dashboard functionality |

### Issue Details (Required for --agent and --e2e, unless --dry-run)

| Option | Description |
|--------|-------------|
| `--title TEXT` | Issue title |
| `--description TEXT` | Issue description |

**Note:** When using `--dry-run`, default values are used if title/description not provided.

### Test Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Use mock responses (no API calls) | False |
| `--debug` | Enable debug logging | False |
| `--output-dir PATH` | Directory for test artifacts | `/tmp/claude/agent-tests` |

## Output Artifacts

All test artifacts are saved to the output directory (default: `/tmp/claude/agent-tests`).

### Artifact Files

| File | Description |
|------|-------------|
| `test_YYYYMMDD_HHMMSS.log` | Complete test log with timestamps |
| `design_output.json` | Design agent output (structured JSON) |
| `testing_output.json` | Testing agent output (structured JSON) |
| `docs_output.json` | Docs agent output (structured JSON) |
| `e2e_result.json` | Complete E2E workflow results |
| `dashboard_test_results.json` | Dashboard test results and summary |

### Artifact Structure

**Example: `design_output.json`**
```json
{
  "design_analysis": "# Design Analysis...",
  "impacted_components": ["buildrun_api", "buildrun_controller"],
  "risks": [
    {
      "level": "high",
      "description": "...",
      "mitigation": "..."
    }
  ],
  "acceptance_criteria": ["...", "..."],
  "implementation_plan": ["Phase 1: ...", "Phase 2: ..."]
}
```

## Logging

### Log Levels

- **INFO**: High-level workflow events (agent start/complete, artifact saves)
- **DEBUG**: Detailed execution information (API calls, context, state transitions)
- **ERROR**: Errors and failures with stack traces

### Log Format

**Console output:**
```
INFO | multi_agent_testing.design | Starting DESIGN Agent
INFO | multi_agent_testing.design | Issue: Add timeout support
DEBUG | multi_agent_testing.design | Full context keys: ['issue_title', 'issue_description']
```

**File output:**
```
[INFO] 2026-03-11 10:30:45 - multi_agent_testing.design - design_node:89 - Starting DESIGN Agent
```

### Agent-Specific Loggers

Each agent has its own logger for easier filtering:

- `multi_agent_testing.design`
- `multi_agent_testing.testing`
- `multi_agent_testing.docs`
- `multi_agent_testing.dashboard`

## Dry-Run Mode

Dry-run mode enables testing without making API calls or external service connections.

### What's Mocked

- Claude API calls → Returns pre-configured mock responses
- Heartbeat emissions → Logged but not sent
- Dashboard API → Tests skip live backend checks

### What Still Works

- Logging and output capture
- Artifact generation and storage
- Code flow and state transitions
- Error handling and validation

### Use Cases

1. **Development**: Test code changes without API usage
2. **CI/CD**: Run tests in pipelines without credentials
3. **Debugging**: Isolate logic issues from API behavior
4. **Learning**: Understand workflow without API costs

### Example: Dry-Run vs Live

```bash
# Dry-run: Uses mocks, no authentication needed
uv run python scripts/test_agents.py --e2e --dry-run

# Live with Google Vertex AI (recommended)
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
export CLOUD_ML_REGION=  # Optional
# Ensure gcloud authentication is configured:
# gcloud auth application-default login
uv run python scripts/test_agents.py --e2e \
  --title "Add timeout" \
  --description "Users need timeout config"

# Live with Individual API Key
export ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
uv run python scripts/test_agents.py --e2e \
  --title "Add timeout" \
  --description "Users need timeout config"

# Live with Custom Enterprise Endpoint
export ANTHROPIC_BASE_URL=https://your-enterprise-endpoint.anthropic.com
export ANTHROPIC_AUTH_TOKEN=your_enterprise_auth_token
uv run python scripts/test_agents.py --e2e \
  --title "Add timeout" \
  --description "Users need timeout config"
```

## Debug Mode

Debug mode provides verbose logging for troubleshooting.

### What You Get

- Full context dumps (input state, agent configuration)
- API call details (model, token counts, timing)
- State transitions between workflow phases
- Stack traces for all errors
- Detailed artifact save confirmations

### Example Output

```bash
uv run python scripts/test_agents.py --agent design --dry-run --debug
```

```
DEBUG | multi_agent_testing.design | Full context keys: ['issue_title', 'issue_description', 'repo_path']
DEBUG | multi_agent_testing.design | [DRY-RUN] Claude API call: model=claude-sonnet-4, tokens=8000
DEBUG | multi_agent_testing.design | Impacted components: 3
DEBUG | multi_agent_testing.design | Risks identified: 3
DEBUG | multi_agent_testing.design | Acceptance criteria: 6
INFO  | multi_agent_testing | Artifact saved: /tmp/claude/agent-tests/design_output.json
```

## Dashboard Testing

Dashboard testing validates dashboard components work correctly.

### Test Coverage

| Test | Description | Dry-Run Safe |
|------|-------------|--------------|
| Imports | Dashboard modules import successfully | ✓ |
| Heartbeat | Heartbeat emission functionality | Partial |
| Enrichers | State enrichment pipeline | ✓ |
| Database | Backend API health check | ✗ |
| Frontend | Frontend file existence | ✓ |

### Running Dashboard Tests

```bash
# Dry-run (skips live backend check)
uv run python scripts/test_agents.py --dashboard --dry-run

# With live dashboard
# Terminal 1: Start dashboard
uv run python scripts/run_dashboard.py

# Terminal 2: Run tests
uv run python scripts/test_agents.py --dashboard
```

### Expected Output

```
[1/5] Testing dashboard module imports
✓ Dashboard modules import successfully

[2/5] Testing heartbeat emission
✓ Heartbeat emission (skipped in dry-run)

[3/5] Testing enrichers
✓ Enricher processed heartbeat: 15 fields

[4/5] Testing database operations
⊘ Database backend not running (start with run_dashboard.py)

[5/5] Testing frontend file existence
✓ Frontend file exists: /path/to/dashboard/frontend/index.html

Dashboard Test Summary
Passed: 3
Failed: 0
Skipped: 2
```

## Future: MCP Server Integration

The testing infrastructure is prepared for future MCP server integration.

### Planned Integrations

**GitHub MCP Server** (`mcp/github_stub.py`)
- Create and manage issues
- Create and review pull requests
- Manage GitHub Actions workflows
- Access repository metadata

**Jira MCP Server** (`mcp/jira_stub.py`)
- Create and manage issues/stories/epics
- Update issue status and transitions
- Add comments and attachments
- Search and filter issues

### Current Status

**Stub implementations only** - interfaces defined but not yet functional.

### Integration Path

1. Set up MCP servers for GitHub and Jira
2. Implement MCP client connections in stub files
3. Add MCP configuration to test CLI
4. Update dry-run mode to mock MCP responses
5. Add MCP-specific tests to dashboard testing

### Testing MCP Integration (Future)

```bash
# Test with GitHub MCP server
uv run python scripts/test_agents.py \
  --e2e \
  --with-github-mcp \
  --title "Add timeout" \
  --description "..."

# Test with Jira MCP server
uv run python scripts/test_agents.py \
  --e2e \
  --with-jira-mcp \
  --jira-project SHIP \
  --title "Add timeout" \
  --description "..."

# Dry-run with both MCP servers (mocked)
uv run python scripts/test_agents.py \
  --e2e \
  --dry-run \
  --with-github-mcp \
  --with-jira-mcp
```

## Troubleshooting

### "No Claude authentication configured" error

**Solution:** Choose one of the following:

**Option 1: Use dry-run mode (no authentication needed)**
```bash
uv run python scripts/test_agents.py --e2e --dry-run
```

**Option 2: Configure Google Vertex AI authentication (recommended)**
```bash
# Authenticate with gcloud
gcloud auth application-default login
gcloud auth application-default set-quota-project your-gcp-project-id

# Set project ID
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
export CLOUD_ML_REGION=  # Optional
```

**Option 3: Configure individual API key**
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

**Option 4: Configure custom enterprise endpoint**
```bash
export ANTHROPIC_BASE_URL=https://your-enterprise-endpoint.anthropic.com
export ANTHROPIC_AUTH_TOKEN=your_enterprise_auth_token
```

### Artifacts not found for sequential agent tests

**Cause:** Testing testing/docs agent individually without design output

**Solution:** Either:
1. Use `--dry-run` (uses mock data)
2. Run design agent first to generate artifacts
3. Use `--e2e` mode (runs all agents in sequence)

```bash
# Option 1: Dry-run
uv run python scripts/test_agents.py --agent testing --dry-run

# Option 2: Run design first
uv run python scripts/test_agents.py --agent design --title "..." --description "..."
uv run python scripts/test_agents.py --agent testing

# Option 3: E2E mode
uv run python scripts/test_agents.py --e2e --title "..." --description "..."
```

### Dashboard tests show "not running"

**Cause:** Dashboard backend is not started

**Solution:** Start dashboard in separate terminal:

```bash
# Terminal 1
uv run --with fastapi --with "uvicorn[standard]" python scripts/run_dashboard.py

# Terminal 2
uv run python scripts/test_agents.py --dashboard
```

### Import errors

**Cause:** Dependencies not installed

**Solution:** Install requirements:

```bash
# Option 1: Create virtual environment with uv
uv venv
source .venv/bin/activate
pip install -r requirements.txt

# Option 2: Use uv sync if pyproject.toml is configured
uv sync
```

## Best Practices

### Development Workflow

1. **Use dry-run for initial testing**
   ```bash
   uv run python scripts/test_agents.py --e2e --dry-run --debug
   ```

2. **Test with real API once dry-run passes**
   ```bash
   uv run python scripts/test_agents.py --e2e --title "..." --description "..."
   ```

3. **Check artifacts for correctness**
   ```bash
   cat /tmp/claude/agent-tests/e2e_result.json | jq .
   ```

4. **Save important test runs**
   ```bash
   uv run python scripts/test_agents.py --e2e \
     --output-dir ./test-runs/$(date +%Y%m%d) \
     --title "..." --description "..."
   ```

### CI/CD Integration

```bash
# In CI pipeline (no API key needed)
uv run python scripts/test_agents.py --e2e --dry-run

# Exit code: 0 if passed, 1 if failed
```

### Debugging Issues

1. Enable debug mode
2. Review logs in output directory
3. Inspect saved artifacts
4. Test components in isolation

```bash
# Full debug run
uv run python scripts/test_agents.py \
  --agent design \
  --dry-run \
  --debug \
  --output-dir /tmp/debug-run

# Review logs
cat /tmp/debug-run/test_*.log

# Inspect output
cat /tmp/debug-run/design_output.json | jq .
```

## Examples

### Example 1: Quick validation

```bash
# Validate all agents work (dry-run)
uv run python scripts/test_agents.py --e2e --dry-run
```

### Example 2: Test new feature

```bash
# Test timeout feature implementation
uv run python scripts/test_agents.py \
  --e2e \
  --title "Add BuildRun timeout support" \
  --description "Users need to configure max execution time to prevent hanging builds. Should support duration format like 30m, 1h." \
  --output-dir ./test-results/timeout-feature \
  --debug
```

### Example 3: Dashboard validation

```bash
# Start dashboard
uv run --with fastapi --with "uvicorn[standard]" python scripts/run_dashboard.py &

# Run E2E with dashboard monitoring
uv run python scripts/test_agents.py --e2e \
  --title "Test with dashboard" \
  --description "Verify dashboard displays workflow progress"

# Test dashboard components
uv run python scripts/test_agents.py --dashboard

# Open dashboard
open http://localhost:8080
```

### Example 4: Agent isolation testing

```bash
# Test each agent individually
uv run python scripts/test_agents.py --agent design --dry-run --debug
uv run python scripts/test_agents.py --agent testing --dry-run --debug
uv run python scripts/test_agents.py --agent docs --dry-run --debug
```

## Summary

The testing infrastructure provides:

✓ **Dry-run mode** - Test without API calls or external dependencies
✓ **Debug logging** - Verbose output for troubleshooting
✓ **Local artifacts** - All outputs saved for inspection
✓ **Individual testing** - Test agents in isolation
✓ **E2E testing** - Validate complete workflow
✓ **Dashboard testing** - Verify monitoring components
✓ **Future-ready** - Prepared for MCP server integration

Use `--dry-run` for development and `--debug` for troubleshooting. All artifacts are saved locally for inspection and analysis.
