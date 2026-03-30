# CLI Reference

The CLI is available for scripting, automation, and CI/CD pipelines. For interactive use, the [FlowPilot dashboard](../04-dashboard/overview.md) provides a richer experience with real-time progress, log streaming, and artifact downloads. CLI runs emit heartbeats to the dashboard, so you can still monitor progress in the web UI.

---

## `scripts/orchestrate.py` -- Run the Pipeline

The main entry point. Runs the full five-phase pipeline: Design --> Development --> Code Review --> Testing --> Documentation.

### From a Jira Ticket (Recommended)

```bash
uv run python scripts/orchestrate.py \
  --jira-ticket BUILD-1707 \
  --output-dir ./output/BUILD-1707
```

### From a Title and Description

```bash
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need configurable timeouts to prevent hanging builds" \
  --output-dir ./output
```

### With GitHub Issue Context

```bash
uv run python scripts/orchestrate.py \
  --title "Add timeout support" \
  --description "Description" \
  --github-issue SHIP-123 \
  --output-dir ./output
```

GitHub issues can be specified as `SHIP-NNN`, `owner/repo#N`, or a full URL.

### Options

| Option | Description | Default |
| --- | --- | --- |
| `--jira-ticket KEY` | Jira ticket ID (e.g. `BUILD-1707`). Fetches title, description, and metadata automatically. | -- |
| `--title TEXT` | Issue title (required if no `--jira-ticket`) | -- |
| `--description TEXT` | Issue description | -- |
| `--github-issue REF` | GitHub issue reference (`SHIP-123`, `owner/repo#N`, or URL) | -- |
| `--issue-type TYPE` | Issue type: `feature`, `bug`, or `refactor` | `feature` |
| `--output-dir PATH` | Directory for generated artifacts | -- |
| `--dry-run` | Use mock responses, no API calls or credentials needed | `false` |
| `--debug` | Enable `DEBUG` log level for this run | `false` |
| `--manual-approval` | Pause after each phase for user approval | `false` |

### Output Directory Structure

When `--output-dir` is specified, artifacts are saved as:

```text
output/
├── state.json          # Full pipeline state
├── design/             # Design analysis, component impact, risks
├── code/               # Generated Go source files
├── tests/              # Generated Ginkgo v2 test files
└── docs/               # PR summary, release notes
```

### What Happens During a Run

The terminal prints a header for each phase with a per-phase timer:

```text
Phase 1/5 · Design
Phase 2/5 · Development
Phase 3/5 · Code Review
Phase 4/5 · Testing
Phase 5/5 · Documentation
```

When all phases finish:

```text
Run complete
  Duration:   3m 42s
  Artifacts:  ./output/BUILD-1707
  Dashboard:  http://localhost:8080
```

If an agent raises an unhandled exception, the workflow sets `current_phase = "error"` and stops early.

---

## `scripts/run_dashboard.py` -- Start the Dashboard

Starts the FastAPI backend and serves the React frontend.

```bash
uv run python scripts/run_dashboard.py
```

| Endpoint | URL |
| --- | --- |
| Web UI | `http://localhost:8080` |
| API documentation | `http://localhost:8080/docs` |
| Health check | `http://localhost:8080/api/health` |

---

## `scripts/test_agents.py` -- Test Agents

Test individual agents or the full pipeline without running a production workflow.

### Full E2E Workflow

```bash
uv run python scripts/test_agents.py --e2e --dry-run
```

### Single Agent

```bash
uv run python scripts/test_agents.py --agent design --dry-run --debug
```

### Custom Issue Data

```bash
uv run python scripts/test_agents.py --e2e --dry-run \
  --title "Add SSH key support" \
  --description "Users need to build from private Git repos"
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `--agent {design\|testing\|docs}` | Test a specific agent | -- |
| `--e2e` | Test complete E2E workflow | -- |
| `--dashboard` | Test dashboard functionality | -- |
| `--title TEXT` | Override issue title | Mock title |
| `--description TEXT` | Override issue description | Mock description |
| `--dry-run` | Use mock responses | `false` |
| `--debug` | Enable verbose logging | `false` |
| `--output-dir PATH` | Artifact output directory | `/tmp/claude/agent-tests` |

### Output Artifacts

| File | Description |
| --- | --- |
| `test_YYYYMMDD_HHMMSS.log` | Complete test log with timestamps |
| `design_output.json` | Design agent structured output |
| `testing_output.json` | Testing agent structured output |
| `docs_output.json` | Docs agent structured output |
| `review_output.json` | Code Review agent structured output |
| `e2e_result.json` | Complete E2E workflow results |

---

## `scripts/publish.py` -- Publish Artifacts

Push generated artifacts to GitHub or update the Jira ticket after a pipeline run. Requires `--output-dir` to point to a completed run's output directory.

### Push Code as a Pull Request

Requires `GITHUB_TOKEN`, `TARGET_GITHUB_REPO`, and `TARGET_GITHUB_BASE_BRANCH` in `.env`.

```bash
uv run python scripts/publish.py \
  --output-dir ./output/BUILD-1707 \
  --push-code
```

### Update the Jira Ticket

Requires `JIRA_BASE_URL`, `JIRA_USER_EMAIL`, and `JIRA_API_TOKEN` in `.env`.

```bash
uv run python scripts/publish.py \
  --output-dir ./output/BUILD-1707 \
  --push-jira
```

### Both

```bash
uv run python scripts/publish.py \
  --output-dir ./output/BUILD-1707 \
  --push-code \
  --push-jira
```

---

## `examples/test_agents_demo.sh` -- Interactive Demo

An interactive, menu-driven Bash script for testing agents, the full pipeline, and dashboard functionality.

```bash
chmod +x examples/test_agents_demo.sh
./examples/test_agents_demo.sh
```

| Mode | Description |
| --- | --- |
| Dry-run | Mock responses, no API calls |
| Live | Real API calls, requires Vertex AI credentials |

| Test | Description |
| --- | --- |
| Individual agent | Test Design, Testing, or Docs agent in isolation |
| E2E workflow | All five agents in sequence |
| Dashboard | Test dashboard heartbeat and API |
| All | Run every test in sequence |

---

## `examples/auth_example.py` -- Verify Authentication

Validates Vertex AI authentication configuration without making API calls.

```bash
uv run python examples/auth_example.py
```

---

## `examples/logger_demo.py` -- Logging Patterns

Demonstrates all logging patterns: agent logging, session logging, log level control, and custom log paths.

```bash
uv run python examples/logger_demo.py
```

---

## `examples/test_cleanup_api.py` -- Dashboard API Test

Exercises every REST endpoint exposed by the dashboard backend. Requires the dashboard to be running.

```bash
# Terminal 1: start the dashboard
uv run python scripts/run_dashboard.py

# Terminal 2: run the API tests
PYTHONPATH=. python examples/test_cleanup_api.py
```

---

## Environment Variables That Affect CLI Behavior

| Variable | Effect on CLI |
| --- | --- |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Required for live runs. Not needed with `--dry-run`. |
| `JIRA_BASE_URL` / `JIRA_USER_EMAIL` / `JIRA_API_TOKEN` | Required for `--jira-ticket`. Not needed with `--dry-run`. |
| `CLAUDE_MODEL` | Model override (default: `claude-sonnet-4-6`) |
| `LOG_LEVEL` | Persistent log level. `--debug` overrides this to `DEBUG` for one run. |
| `MANUAL_APPROVAL` | Set to `true` to pause between phases. `--manual-approval` flag does the same per-run. |
| `QODO_REVIEW_ENABLED` | Set to `false` to skip code review entirely. |
| `DRY_RUN` | Set to `true` as an alternative to the `--dry-run` flag. |

See [Configuration](../01-getting-started/configuration.md) for the full environment variable reference.

---

[← Back to Index](../README.md) | [API Reference →](api.md)
