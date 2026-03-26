# Dashboard Overview

The dashboard provides real-time visibility into agent workflows. It shows which phase each agent is in, how much of the context window has been consumed, which Shipwright components are being analyzed, and a history of completed sessions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Workflows                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │Design Agent  │──>│Testing Agent │──>│ Docs Agent   │    │
│  └──────────────┘   └──────────────┘   └──────────────┘    │
│         │ Heartbeat        │ Heartbeat        │ Heartbeat    │
│         ↓                  ↓                  ↓              │
├─────────────────────────────────────────────────────────────┤
│                  Enricher Pipeline                           │
│         ModelInfoEnricher → TokenCountEnricher → PhaseStatus│
│                         │                                    │
│                         ↓                                    │
├─────────────────────────────────────────────────────────────┤
│                  Dashboard Backend                           │
│              FastAPI + SQLite (dashboard/backend.py)         │
│    POST /api/heartbeat     GET /api/sessions                 │
│                         │                                    │
│                         ↓                                    │
├─────────────────────────────────────────────────────────────┤
│                    Web Frontend                              │
│           HTML + Vanilla JS (3-second auto-refresh)          │
│    Session Cards | Context % | Phase badges | Components     │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

- **Backend:** FastAPI + SQLite + Uvicorn
- **Frontend:** Vanilla JavaScript, CSS Grid, polling every 3 seconds
- **Integration:** Agents emit heartbeats via HTTP POST to `/api/heartbeat`
- **Storage:** SQLite at `DASHBOARD_DB_PATH` (default: `/tmp/claude/dashboard.db`)

---

## Starting the Dashboard

```bash
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py
```

| Endpoint | URL |
|----------|-----|
| Web UI | http://localhost:8080 |
| API documentation | http://localhost:8080/docs |
| Health check | http://localhost:8080/api/health |

---

## What the Dashboard Shows

Each active session is displayed as a card:

```
Session abc123
Issue: Add timeout support to BuildRun
Type: feature

[ Design ] --> [ Dev ] --> [ Review ] --> [ Testing ] --> [ Docs ]
  done           done        active         pending        pending

Tests: 12 unit / 4 integration / 2 e2e
Code files: 6    Artifacts: /tmp/claude/sessions/abc123/
Review: PASS

Started: 2026-03-26 14:00:00    Last updated: 2s ago

Context: 64%
Model: claude-sonnet-4
```

### Session Card Layout

Each session card displays the following fields:

**Phase timeline strip**
A row of five phase bubbles — Design, Dev, Review, Testing, Docs — shown in order. Each bubble carries one of three states:

- `done` — the phase completed successfully
- `active` — the phase is currently running
- `pending` — the phase has not started yet

The timeline gives an at-a-glance view of where the workflow is without reading individual status labels.

**Test counts**
Unit, integration, and end-to-end test counts produced by the Testing agent. Displayed as `N unit / N integration / N e2e`. These values are populated once the testing phase completes.

**Code files count**
The number of code files generated or modified by the Development agent.

**Artifact path link**
A clickable path to the session output directory on disk. Use this to locate generated code, test files, and documentation artifacts.

**Review badge**
A `PASS` or `FAIL` badge from the Code Review agent. A `FAIL` badge indicates the auto-fix loop is still iterating or that review did not pass before the workflow ended.

**Dual timestamps**

- **Started** — when the session was first created (first heartbeat received)
- **Last updated** — time elapsed since the most recent heartbeat

**Context and model**
Context window usage percentage and the Claude model name in use.

**Risks**
If the Design agent identified risks, they are rendered directly in the card for quick reference.

### Key Metrics and What to Monitor

| Metric | What to watch for |
|--------|-------------------|
| **Phase timeline strip** | Check that bubbles progress left-to-right; a bubble stuck on `active` for a long time may indicate a hung agent |
| **Context percentage** | Monitor for >80% — agent may run out of space before completing |
| **Phase progression** | Confirms workflow is advancing (Design → Dev → Review → Test → Docs → Done) |
| **Component impact** | Which parts of the Shipwright codebase are being analyzed |
| **Last updated** | If this stops advancing, the agent may have hung or crashed |
| **Review badge** | A persistent `FAIL` badge means the review loop did not converge — check agent logs |

---

## Heartbeat Protocol

Each agent calls `emit_heartbeat(agent_name, state)` at the start and end of its phase. The `HeartbeatEmitter` in `dashboard/heartbeat.py` sends an HTTP POST to `/api/heartbeat`.

```python
# Called inside each agent node - example from graph.py
emit_heartbeat("design", {**state, "phase": "design_complete"})
```

If the dashboard is unreachable, heartbeats fail silently. The workflow is never blocked by dashboard availability.

### Enricher Pipeline

Raw heartbeat data passes through three enrichers before storage:

- **ModelInfoEnricher** - Reads the Claude model name from state
- **TokenCountEnricher** - Estimates context window usage percentage based on state size
- **PhaseStatusEnricher** - Maps `current_phase` to a human-readable status label

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/heartbeat` | Receive agent heartbeat |
| GET | `/api/sessions` | List all sessions |
| GET | `/api/sessions/{id}` | Get specific session details |
| DELETE | `/api/sessions/cleanup` | Delete completed sessions older than N hours |
| DELETE | `/api/sessions/completed` | Delete all completed sessions |
| GET | `/api/health` | Health check |

---

## Database Schema

The dashboard stores data in two SQLite tables:

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    issue_title TEXT,
    issue_type TEXT,
    status TEXT
);

CREATE TABLE heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    agent TEXT,
    phase TEXT,
    timestamp TIMESTAMP,
    model TEXT,
    context_tokens INTEGER,
    context_percent REAL,
    raw_state JSON,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

---

## Log Locations

Agent logs are written under the `logs/` directory when logging is configured:

```
logs/
├── agents/
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

---

## Running with the Workflow

```bash
# Terminal 1: start the dashboard
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py

# Terminal 2: run the workflow
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds"
```

The session appears in the dashboard within seconds of the workflow starting.

---

[← Previous: Docs Agent](../03-agents/docs-agent.md) | [Next: Session Management →](session-management.md)
