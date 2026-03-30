# Examples

The `examples/` directory contains runnable scripts for testing agents, verifying authentication, exploring the logging system, and interacting with the dashboard API. Each example is self-contained and designed to be run from the project root.

---

## Summary

| File | Purpose | Requires API? |
|------|---------|---------------|
| [`test_agents_demo.sh`](#1-interactive-agent-demo-test_agents_demosh) | Interactive menu-driven agent testing | Optional (dry-run available) |
| [`auth_example.py`](#2-authentication-auth_examplepy) | Verify Vertex AI authentication setup | Yes |
| [`logger_demo.py`](#3-logging-patterns-logger_demopy) | Demonstrate all logging patterns | No |
| [`test_cleanup_api.py`](#4-dashboard-api-test_cleanup_apipy) | Test and interact with the dashboard REST API | No (requires dashboard running) |

> **Note:** The E2E workflow now includes the Code Review Agent automatically. No new example files are required — the fifth agent runs as part of the existing pipeline.

---

## 1. Interactive Agent Demo (`test_agents_demo.sh`)

**File:** `examples/test_agents_demo.sh`

An interactive, menu-driven Bash script that walks you through testing individual agents, the full E2E workflow, and dashboard functionality. It is the fastest way to verify the system works end-to-end without writing any code.

### When to Use

- First-time setup verification after installation
- Confirming agents produce output before running a real workflow
- Demonstrating the system to others without editing Python files
- Quickly switching between dry-run and live mode during development

### How to Run

```bash
chmod +x examples/test_agents_demo.sh
./examples/test_agents_demo.sh
```

### Example Session

```
============================================
Multi-Agent System Testing Demo
============================================

Select testing mode:
1) Dry-run (mock responses, no API calls)
2) Live (real API calls, requires Vertex AI authentication)
Enter choice [1-2]: 1
Running in DRY-RUN mode (using mock responses)

What would you like to test?
1) Individual agent (design, testing, or docs)
2) Complete E2E workflow
3) Dashboard functionality
4) All of the above
Enter choice [1-4]: 2

Results will be saved to: /tmp/claude/agent-tests-demo-20260315_100000

Testing E2E workflow...
```

### Menu Options

| Choice | Description |
|--------|-------------|
| Mode 1 - Dry-run | Uses mock responses from `config/mock_responses.py`. No API credentials needed, no cost. |
| Mode 2 - Live | Makes real Vertex AI API calls. Requires `ANTHROPIC_VERTEX_PROJECT_ID` and valid `gcloud` credentials. |
| Test 1 - Individual agent | Prompts for which agent (Design, Testing, or Docs) and tests it in isolation. |
| Test 2 - E2E workflow | Runs all five agents in sequence (including Code Review) using `scripts/test_agents.py --e2e`. |
| Test 3 - Dashboard | Tests dashboard heartbeat and API. Prompts you to start the dashboard first. |
| Test 4 - All | Runs every agent individually, then E2E, then dashboard tests in sequence. |

### Output

All results are saved to a timestamped directory:

```
/tmp/claude/agent-tests-demo-<YYYYMMDD_HHMMSS>/
  test_YYYYMMDD_HHMMSS.log     # Full log with timestamps
  design_output.json           # Design agent structured output
  testing_output.json          # Testing agent structured output
  docs_output.json             # Docs agent structured output
  review_output.json           # Code Review agent structured output
  e2e_result.json              # Complete E2E workflow result
```

Inspect artifacts after the run:

```bash
cat /tmp/claude/agent-tests-demo-20260315_100000/design_output.json | jq .
cat /tmp/claude/agent-tests-demo-20260315_100000/e2e_result.json | jq .
```

> **Note:** The script passes `--debug` to all test commands, so logs include detailed per-agent execution information.

---

## 2. Authentication (`auth_example.py`)

**File:** `examples/auth_example.py`

A Python script that validates your Vertex AI authentication configuration and confirms the Anthropic client initializes correctly. Run this whenever you suspect a credentials problem before attempting a full workflow.

### When to Use

- First-time setup: confirm `ANTHROPIC_VERTEX_PROJECT_ID` is correctly configured
- After rotating credentials or switching GCP projects
- Troubleshooting `ValueError: Authentication not configured` errors from agents
- Verifying that `gcloud auth application-default login` completed successfully

### How to Run

```bash
# From project root
python examples/auth_example.py
```

### Key Functions Used

```python
from config.auth_config import get_anthropic_client, validate_authentication

# Inspect what credentials are present without making an API call
auth_info = validate_authentication()

# Initialize the AnthropicVertex client (raises ValueError if not configured)
client = get_anthropic_client()
```

`validate_authentication()` returns a dict with fields `auth_type`, `has_vertex_project_id`, and `has_vertex_region`. It does not make any network calls. `get_anthropic_client()` constructs the actual client and will raise `ValueError` if required environment variables are missing.

### Expected Output on Success

```
================================================================================
Authentication Configuration Example
================================================================================

1. Validating authentication configuration...
   Authentication Type: vertex_ai
   Has Vertex AI Project ID: True
   Has Vertex AI Region: True

2. Attempting to get Anthropic client...
   Successfully initialized AnthropicVertex client
   Client type: AnthropicVertex

================================================================================
Configuration Example:
================================================================================

# Google Vertex AI:
export ANTHROPIC_VERTEX_PROJECT_ID='my-gcp-project-id'
export CLOUD_ML_REGION='us-east5'  # Optional, defaults to us-east5
# Note: Uses gcloud auth automatically - run: gcloud auth application-default login
```

### Expected Output on Failure

```
2. Attempting to get Anthropic client...
   Authentication error: ANTHROPIC_VERTEX_PROJECT_ID environment variable not set

   To fix this, set:
   - ANTHROPIC_VERTEX_PROJECT_ID for Google Vertex AI
   - Then run: gcloud auth application-default login
```

> **Note:** The script intentionally does not make a live API call by default. To test the client end-to-end, uncomment the `client.messages.create()` block inside the file (doing so will consume API tokens).

---

## 3. Logging Patterns (`logger_demo.py`)

**File:** `examples/logger_demo.py`

A Python script that demonstrates every logging pattern used across the system. Run it to see exactly what each logger writes, where files are created, and how to control log levels dynamically.

### When to Use

- Learning how to add logging to a new agent or component
- Confirming the `utils.file_logger` module works in your environment
- Understanding log file locations before reading production logs
- Verifying that session-scoped logging tracks work across multiple phases

### How to Run

```bash
# From project root
python examples/logger_demo.py
```

### Logging Patterns Demonstrated

| Demo | Description | Output location |
|------|-------------|-----------------|
| Basic agent logging | `INFO`, `WARNING`, `ERROR` for a named agent | `logs/agents/design_agent.log` |
| Dashboard component logging | Separate loggers for backend and frontend subcomponents | `logs/dashboard/dashboard.log` |
| Session-specific logging | Loggers scoped to a session ID, one per phase | `logs/sessions/session_<id>_*.log` |
| Log level control | All five levels; dynamic level change mid-run | `logs/test_component.log` |
| Custom log file path | Writing to an arbitrary subdirectory under `logs/` | `logs/experiments/custom.log` |
| Console-only mode | Logger that emits to stdout only, no file created | stdout only |

### Key Functions

```python
from utils.file_logger import get_logger, get_session_logger, set_log_level

# Basic logger - writes to logs/agents/<name>.log
logger = get_logger("agents.my_agent")
logger.info("Starting analysis...")
logger.warning("Unexpected response format")

# Session logger - writes to logs/sessions/session_<id>_<component>.log
session_logger = get_session_logger(session_id, "design")
session_logger.info("Design phase started")

# Change log level for a named logger at runtime
set_log_level("agents.my_agent", logging.WARNING)

# Console-only logger - no file written
console_logger = get_logger("temp_component", file_output=False)
```

### Expected Output

```
============================================================
File Logger Demonstration
============================================================

=== Basic Logger Demo ===

✓ Logs written to: logs/agents/design_agent.log

=== Dashboard Logger Demo ===

✓ Logs written to: logs/dashboard/dashboard.log

=== Session Logger Demo ===

✓ Session logs written to: logs/sessions/session_abc-123-def-456_*.log

=== Log Level Demo ===

✓ All levels logged to: logs/test_component.log
✓ Log level changed to WARNING

=== Custom Log File Demo ===

✓ Logs written to: logs/experiments/custom.log

=== Console-Only Logger Demo ===

✓ Console-only logger (no file created)

============================================================
Demo complete! Check the logs/ directory for output.
============================================================
```

> **Note:** The `logs/` directory is created relative to your working directory when you run the script. If you run from the project root, logs appear at `<project-root>/logs/`.

---

## 4. Dashboard API (`test_cleanup_api.py`)

**File:** `examples/test_cleanup_api.py`

A Python script that exercises every REST endpoint exposed by the dashboard backend. It sends test heartbeats, lists sessions, and triggers cleanup operations so you can verify the dashboard API works correctly without running a full agent workflow.

### When to Use

- Verifying the dashboard backend is reachable and responding correctly
- Testing session cleanup endpoints before enabling automated cleanup in production
- Understanding the heartbeat payload format required by `POST /api/heartbeat`
- Debugging session state when the dashboard UI shows unexpected data

### Prerequisites

The dashboard backend must be running before you execute this script:

```bash
# Terminal 1: Start the dashboard
uv run python scripts/run_dashboard.py
```

### How to Run

```bash
# Terminal 2: Run the API tests
PYTHONPATH=. python examples/test_cleanup_api.py
```

### API Operations Demonstrated

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| Health check | `GET` | `/api/health` | Confirms the backend is up |
| List sessions | `GET` | `/api/sessions` | Returns all stored sessions |
| Cleanup old sessions | `DELETE` | `/api/sessions/cleanup?max_age_hours=24` | Removes sessions older than the threshold |
| Clear completed | `DELETE` | `/api/sessions/completed` | Removes all sessions in `done` or `error` phase |
| Send heartbeat | `POST` | `/api/heartbeat` | Stores a new session event |

### Heartbeat Payload Format

```python
heartbeat = {
    "session_id": "test-session-123",
    "agent": "design",
    "phase": "done",
    "timestamp": "2026-03-15T10:00:00",
    "raw_state": {
        "issue_title": "My Feature",
        "issue_number": 42,
        "issue_type": "feature"
    }
}
```

Valid values for `phase` include `planning`, `design`, `develop`, `testing`, `docs`, `done`, and `error`. The `agent` field identifies which agent emitted the heartbeat.

### Expected Output

```
Dashboard Cleanup API Test
============================================================
Make sure the dashboard backend is running:
  uv run python dashboard/backend.py
============================================================

=== Testing health endpoint ===
Status: 200
Response: {"status": "healthy", "db_path": "/tmp/claude/dashboard.db"}

=== Getting all sessions ===
Status: 200
Total sessions: 2
  - abc-123: Add SSH key support (phase: done)
  - def-456: Fix build timeout (phase: error)

--- Sending Test Heartbeats ---

=== Sending test heartbeat (session=test_session_1, phase=done) ===
Status: 200
Response: {"status": "ok"}

...

============================================================
Test Summary:
  Initial sessions: 2
  Sessions after test heartbeats: 5
  Sessions cleaned up (1h): 0
  Completed sessions cleared: 3
  Final sessions: 2
============================================================

All API tests completed successfully!
```

> **Note:** The cleanup with a 1-hour threshold will not delete the test heartbeats you just sent because they were created seconds ago. Use a 0-hour threshold or the `clear_completed` endpoint to remove them immediately.

---

## 5. Code Review Agent

The Code Review Agent (`agents/code_review_agent.py`) runs automatically between Development and Testing in every E2E workflow. The examples below show how to observe, configure, and inspect its behavior without modifying any agent code.

### When to Use

Use these examples when you want to:

- Observe the review step during dry-run development without consuming API tokens
- Disable the review phase temporarily to speed up iteration on non-code changes
- Tune how aggressively the auto-fix loop triggers before re-running development
- Enable Qodo CLI as the review backend instead of Claude
- Inspect review results programmatically after a workflow completes

In normal operation you do not need to interact with the Code Review Agent directly — it runs automatically and routes back to Development when it finds blocking issues.

### a) Dry-run with Review

In dry-run mode the Code Review Agent returns a mock PASS result without making any API call. The log will include the line `[DRY-RUN] Code review skipped`.

```bash
uv run python scripts/test_agents.py --e2e --dry-run --debug
```

### b) Disabling Review

Set `QODO_REVIEW_ENABLED=false` to skip the Code Review phase entirely. The pipeline proceeds directly from Development to Testing.

```bash
QODO_REVIEW_ENABLED=false uv run python scripts/orchestrate.py \
  --title "Feature title" \
  --description "Description" \
  --output-dir ./output
```

### c) Tuning the Auto-fix Loop

`MAX_REVIEW_ITERATIONS` controls how many times the pipeline can cycle back from Code Review to Development before proceeding regardless of verdict (default: `3`). `QODO_BLOCKING_THRESHOLD` controls which finding severity levels count as blocking:

| Threshold | Findings that trigger a re-run |
|-----------|-------------------------------|
| `high` | `[BLOCKING]` only (default) |
| `medium` | `[BLOCKING]` and `[WARNING]` |
| `low` | Any finding, including `[SUGGESTION]` |

```bash
MAX_REVIEW_ITERATIONS=5 QODO_BLOCKING_THRESHOLD=medium uv run python scripts/orchestrate.py \
  --title "Add timeout support" \
  --description "Users need configurable timeouts" \
  --output-dir ./output
```

### d) Optional Qodo CLI

Set `QODO_CLI_PATH` to the absolute path of the Qodo binary to use Qodo as the review backend. If the Qodo CLI fails or is unreachable, the agent automatically falls back to Claude-only review.

```bash
QODO_CLI_PATH=/usr/local/bin/qodo uv run python scripts/orchestrate.py \
  --title "Add timeout support" \
  --description "Description" \
  --output-dir ./output
```

### e) Reading Review Output from State

After `orchestrate()` returns, the review results are available directly on the state dict:

```python
from agents.graph import orchestrate

result = orchestrate(
    title="Add timeout support",
    description="Users need configurable timeouts"
)

print(result.get("review_summary"))    # e.g. "2 findings | 1 blocking | FAIL"
print(result.get("review_passed"))     # True or False
for finding in result.get("review_findings", []):
    print(finding)                     # "[BLOCKING] SECURITY: ..."
```

State fields populated by the Code Review Agent:

| Field | Type | Description |
|-------|------|-------------|
| `review_passed` | `bool` | `True` if the verdict was PASS |
| `review_findings` | `list[str]` | Individual classified findings |
| `review_summary` | `str` | Human-readable summary line |
| `review_iteration` | `int` | Number of review cycles completed |

### f) Dashboard Heartbeat for Review

The Code Review Agent emits heartbeats to the dashboard with `agent="code_review"`, so review status and verdict are visible in the real-time dashboard alongside the other agents.

---

[← Advanced](../06-advanced/troubleshooting.md) | [Back to Index](../README.md)
