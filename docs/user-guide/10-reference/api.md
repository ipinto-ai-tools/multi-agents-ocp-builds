# API Reference

The FlowPilot dashboard exposes a REST API served by a FastAPI backend at `http://localhost:8080`. All endpoints accept and return JSON unless otherwise noted. Interactive API documentation is available at `http://localhost:8080/docs` when the dashboard is running.

---

## Core Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/health` | Health check -- returns `{"status": "healthy", "db_path": "..."}` |
| POST | `/api/heartbeat` | Receive an agent heartbeat (see [Heartbeat Protocol](#heartbeat-protocol)) |
| POST | `/api/runs` | Launch a new pipeline run from the web UI |

---

## Session Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/sessions` | List all sessions. Add `?include_archived=true` to include archived runs. |
| GET | `/api/sessions/{id}` | Get a specific session with all heartbeats |
| PATCH | `/api/sessions/{id}/archive` | Archive a session (hides from default list, preserves data) |
| DELETE | `/api/sessions/{id}` | Permanently delete a session, all heartbeats, and the log file |
| DELETE | `/api/sessions/cleanup` | Delete completed sessions older than N hours (`?max_age_hours=24`, default 24) |
| DELETE | `/api/sessions/completed` | Delete all completed or errored sessions regardless of age |
| DELETE | `/api/sessions/stuck` | Delete stale sessions with no heartbeat in N hours (`?max_stale_hours=6`, default 6) |

---

## Run Control Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/sessions/{id}/approve` | Signal approval or rejection (`?action=approve` or `?action=reject`) |
| POST | `/api/sessions/{id}/pause` | Signal a running pipeline to pause after the current phase |

---

## Log Streaming

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/sessions/{id}/logs` | Stream pipeline logs via Server-Sent Events (SSE) |

The Logs tab in the Run Details page connects to this endpoint. Logs are read from `/tmp/claude/logs/{session-id}.log` and streamed in real time.

---

## Artifact Downloads

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/sessions/{id}/download/all` | Download all artifacts as a single zip |
| GET | `/api/sessions/{id}/download/design` | Download design analysis as Markdown |
| GET | `/api/sessions/{id}/download/code` | Download generated code files as a zip |
| GET | `/api/sessions/{id}/download/tests` | Download test files as a zip (unit, integration, e2e) |
| GET | `/api/sessions/{id}/download/docs` | Download documentation files as a zip |

---

## Heartbeat Protocol

Each agent calls `emit_heartbeat(agent_name, state)` at the start and end of its phase. The `HeartbeatEmitter` in `dashboard/heartbeat.py` sends an HTTP POST to `/api/heartbeat`.

```python
# Called inside each agent node -- example from graph.py
emit_heartbeat("design", {**state, "phase": "design_complete"})
```

If the dashboard is unreachable, heartbeats fail silently. The workflow is never blocked by dashboard availability.

### Heartbeat Payload

```json
{
  "session_id": "abc-123-def-456",
  "agent": "design",
  "phase": "design_complete",
  "timestamp": "2026-03-15T10:00:00",
  "raw_state": {
    "issue_title": "Add timeout support",
    "issue_number": 42,
    "issue_type": "feature",
    "design_analysis": "...",
    "impacted_components": ["BuildRun", "Build"]
  }
}
```

Valid `phase` values: `planning`, `design`, `design_complete`, `develop`, `develop_complete`, `code_review`, `code_review_complete`, `testing`, `testing_complete`, `docs`, `docs_complete`, `done`, `error`.

The `agent` field identifies which agent emitted the heartbeat: `design`, `development`, `code_review`, `testing`, `docs`.

---

## Enricher Pipeline

Raw heartbeat data passes through eight enrichers before storage. Each enricher adds computed fields to the heartbeat record.

| Enricher | Purpose |
| --- | --- |
| **ModelInfoEnricher** | Reads the Claude model name from the environment |
| **TokenCountEnricher** | Estimates context window usage percentage based on state size |
| **PhaseStatusEnricher** | Maps `current_phase` to a human-readable status label |
| **ComponentsEnricher** | Extracts impacted Shipwright components from state |
| **RisksEnricher** | Extracts risks and derives an overall risk level |
| **IssueInfoEnricher** | Extracts issue title, type, and description |
| **JiraInfoEnricher** | Extracts Jira ticket ID, URL, priority, and labels |
| **TimestampEnricher** | Adds formatted and relative timestamps |

Enrichers are defined in `dashboard/enrichers.py` and run in sequence on every incoming heartbeat.

---

## Database Schema

The dashboard stores data in two SQLite tables at `DASHBOARD_DB_PATH` (default: `/tmp/claude/dashboard.db`).

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    issue_title TEXT,
    issue_type TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    phase TEXT,
    timestamp TIMESTAMP NOT NULL,
    model TEXT,
    context_tokens INTEGER,
    context_percent REAL,
    status TEXT,
    raw_state TEXT,
    enriched_data TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX idx_session_timestamp
ON heartbeats(session_id, timestamp DESC);
```

---

## Automatic Cleanup

A background task runs every 6 hours to clean up old sessions:

| Target | Condition |
| --- | --- |
| Completed sessions | Phase is `done` or `error` and last updated more than 24 hours ago |
| Stuck sessions | Non-terminal phase with no heartbeat for 4+ hours |

The manual `DELETE /api/sessions/stuck` endpoint defaults to `max_stale_hours=6` but accepts a custom value. The background task uses a fixed 4-hour threshold.

Cleanup events are logged:

```text
[INFO] [dashboard.backend] Started automatic cleanup task (runs every 6 hours)
[INFO] [dashboard.backend] Automatic cleanup: {'sessions_deleted': 5, 'heartbeats_deleted': 23}
```

---

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `DASHBOARD_URL` | `http://localhost:8080` | URL where agents send heartbeats |
| `DASHBOARD_ENABLED` | `true` | Set to `false` to disable heartbeat emissions |
| `DASHBOARD_DB_PATH` | `/tmp/claude/dashboard.db` | SQLite database path |

---

## Example: curl

```bash
# Health check
curl http://localhost:8080/api/health

# List all sessions
curl http://localhost:8080/api/sessions

# List including archived
curl "http://localhost:8080/api/sessions?include_archived=true"

# Get a specific session
curl http://localhost:8080/api/sessions/abc-123-def-456

# Delete completed sessions older than 12 hours
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=12"

# Delete all completed sessions
curl -X DELETE http://localhost:8080/api/sessions/completed

# Delete stuck sessions (no heartbeat for 2+ hours)
curl -X DELETE "http://localhost:8080/api/sessions/stuck?max_stale_hours=2"

# Archive a session
curl -X PATCH http://localhost:8080/api/sessions/abc-123-def-456/archive

# Permanently delete a session
curl -X DELETE http://localhost:8080/api/sessions/abc-123-def-456

# Approve a waiting session
curl -X POST "http://localhost:8080/api/sessions/abc-123-def-456/approve?action=approve"

# Send a test heartbeat
curl -X POST http://localhost:8080/api/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-123", "agent": "design", "phase": "done", "timestamp": "2026-03-15T10:00:00", "raw_state": {"issue_title": "Test"}}'
```

---

## Example: Python

```python
import requests

BASE = "http://localhost:8080"

# List sessions
sessions = requests.get(f"{BASE}/api/sessions").json()
for s in sessions:
    print(f"{s['id']}: {s.get('issue_title', 'untitled')} ({s['status']})")

# Delete sessions older than 48 hours
result = requests.delete(
    f"{BASE}/api/sessions/cleanup",
    params={"max_age_hours": 48}
).json()
print(f"Deleted {result['sessions_deleted']} sessions")

# Delete stuck sessions
result = requests.delete(
    f"{BASE}/api/sessions/stuck",
    params={"max_stale_hours": 2}
).json()
print(f"Deleted {result['sessions_deleted']} stuck sessions")
```

---

[← CLI Reference](cli.md) | [Back to Index](../README.md)
