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

Design Agent     Complete
Development      Complete
Testing          In Progress
Documentation    Waiting

Context: 64%
Model: claude-sonnet-4
Last update: 2s ago
```

### Key Metrics

| Metric | What to watch for |
|--------|-------------------|
| **Context percentage** | Monitor for >80% - agent may run out of space before completing |
| **Phase progression** | Confirms workflow is advancing (Design → Dev → Test → Docs → Done) |
| **Component impact** | Which parts of the Shipwright codebase are being analyzed |
| **Last update** | If this stops updating, the agent may have hung or crashed |

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
