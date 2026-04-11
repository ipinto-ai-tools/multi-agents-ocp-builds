# Logging

The system writes structured logs at multiple levels. Logs are written to stdout by default and optionally to files configured through environment variables.

---

## Log Levels

| Level | Used for |
|-------|----------|
| `DEBUG` | Full context dumps, API call details, state transitions, all error tracebacks |
| `INFO` | High-level workflow events (agent start/complete, artifact saves, phase transitions) |
| `WARNING` | Non-fatal issues (repository analysis failed, RAG skipped, dashboard unreachable) |
| `ERROR` | Errors with stack traces that cause an agent to fail |
| `CRITICAL` | Fatal configuration errors |

---

## Configuration

Set these in your `.env` file:

```bash
LOG_LEVEL=INFO            # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=text           # text or json
LOG_FILE_PATH=/tmp/muilti-agents-ocp-builds.log
```

To enable file logging:

```bash
LOG_FILE_PATH=/tmp/muilti-agents-debug.log
```

---

## Log File Locations

### Application Logs

When `LOG_FILE_PATH` is set, all log output goes to that file in addition to stdout.

### Per-Agent Logs

Each stage runner writes to its own log file under `logs/stages/`:

```
logs/
├── stages/
│   ├── design_agent.log
│   ├── go_k8s_developer.log
│   ├── testing_agent.log
│   └── docs_agent.log
└── sessions/
    └── {session-id}/
        ├── design_agent.log
        ├── development_agent.log
        ├── testing_agent.log
        └── docs_agent.log
```

Session-specific logs in `logs/sessions/{session-id}/` are created for each `orchestrate()` call and contain only the logs from that session.

### Test CLI Logs

When using `scripts/test_agents.py`, logs are saved to the output directory:

```
/tmp/claude/agent-tests/
└── test_YYYYMMDD_HHMMSS.log
```

### Dashboard Logs

```
logs/dashboard/dashboard.log
```

---

## Agent-Specific Loggers

Each agent has its own named logger for easier log filtering:

| Logger name | Agent |
|-------------|-------|
| `multi_agent_testing.design` | Design Agent |
| `multi_agent_testing.testing` | Testing Agent |
| `multi_agent_testing.docs` | Documentation Agent |
| `multi_agent_testing.dashboard` | Dashboard |

Filter by agent in the log file:

```bash
grep "multi_agent_testing.design" /tmp/muilti-agents-debug.log
```

---

## Log Formats

### Text Format (default)

Console output:

```
INFO | multi_agent_testing.design | Starting DESIGN Agent
INFO | multi_agent_testing.design | Issue: Add timeout support
DEBUG | multi_agent_testing.design | Full context keys: ['issue_title', 'issue_description']
```

File output with timestamps:

```
[INFO] 2026-03-11 10:30:45 - multi_agent_testing.design - design_node:89 - Starting DESIGN Agent
```

### JSON Format

Set `LOG_FORMAT=json` for structured log output compatible with log aggregation tools:

```json
{"timestamp": "2026-03-11T10:30:45Z", "level": "INFO", "logger": "multi_agent_testing.design", "message": "Starting DESIGN Agent", "session_id": "abc-123"}
```

---

## Enabling Debug Logging

### For the Orchestrator

Set `LOG_LEVEL=DEBUG` in `.env`, then run:

```bash
uv run python scripts/orchestrate.py \
  --title "Test" \
  --description "Debug run" \
  --output-dir ./output
tail -f /tmp/muilti-agents-debug.log
```

### For the Test CLI

The `--debug` flag enables debug logging for a single test run without changing `.env`:

```bash
uv run python scripts/test_agents.py --agent design --dry-run --debug
cat /tmp/claude/agent-tests/test_*.log
```

Debug output includes:

- Full context dictionary keys at agent entry
- API call details (model, max tokens)
- Parsed output field counts (components, risks, criteria)
- State transitions between phases
- Artifact save confirmations

---

## Dashboard Cleanup Logs

Automatic session cleanup events appear in the dashboard log:

```bash
# View recent cleanup activity
grep "cleanup" logs/dashboard/dashboard.log | tail -20
```

Example entries:

```
[INFO] [dashboard.backend] Started automatic cleanup task (runs every 6 hours)
[INFO] [dashboard.backend] Automatic cleanup: {'sessions_deleted': 5, 'heartbeats_deleted': 23}
```

---

## Troubleshooting with Logs

**Agent appears to hang:** Check if the log shows the API call starting but not completing. This may indicate a timeout - increase `API_TIMEOUT` in `.env`.

**Missing outputs:** Enable DEBUG and look for parsing errors after the API call response is logged.

**Dashboard not receiving heartbeats:** Dashboard heartbeat failures are logged at WARNING level in the agent logs. Look for `emit_heartbeat` log entries.

**Repository analysis errors:** Look for WARNING entries from `tools/repo_search.py` - these are non-fatal and the agent continues with component metadata only.

---

[← Previous: Dry Run Mode](dry-run-mode.md) | [Next: Troubleshooting →](troubleshooting.md)
