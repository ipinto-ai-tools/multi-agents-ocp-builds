# Dashboard Architecture

## Overview

The dashboard provides real-time visibility into agent workflows. Think of it as a monitoring screen that shows what your Design, Testing, and Docs agents are doing right now - which components they're analyzing, how much context they're using, and what phase they're in.

## Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Workflows                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │Design Agent  │──→│Testing Agent │──→│ Docs Agent   │    │
│  └──────────────┘   └──────────────┘   └──────────────┘    │
│         │                  │                  │              │
│         │ Heartbeat        │ Heartbeat        │ Heartbeat    │
│         ↓                  ↓                  ↓              │
├─────────────────────────────────────────────────────────────┤
│                  Heartbeat Collector                         │
│         (Hooks in agents/graph.py nodes)                     │
│                         │                                    │
│                         ↓                                    │
├─────────────────────────────────────────────────────────────┤
│                   Enricher Pipeline                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │Model Info  │→ │Token Count │→ │Phase Status│→  Store     │
│  │Enricher    │  │Enricher    │  │Enricher    │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│                         │                                    │
│                         ↓                                    │
├─────────────────────────────────────────────────────────────┤
│                  Dashboard Backend                           │
│              (FastAPI + SQLite)                              │
│    - POST /api/heartbeat                                     │
│    - GET  /api/sessions                                      │
│    - GET  /api/sessions/{id}                                 │
│    - WebSocket /ws/sessions                                  │
│                         │                                    │
│                         ↓                                    │
├─────────────────────────────────────────────────────────────┤
│                    Web Frontend                              │
│           (HTML + Vanilla JS + CSS)                          │
│    - Session Cards (real-time updates)                       │
│    - Metrics: Context %, Phase, Components                   │
│    - Timeline: Design → Docs progression                     │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Heartbeat Emission

As agents work, they send regular "heartbeats" (status updates) to the dashboard:

```python
# In design_node() and docs_node()
heartbeat = {
    "session_id": state.get("session_id"),
    "agent": "design",  # or "docs"
    "phase": state.get("current_phase"),
    "timestamp": datetime.utcnow().isoformat(),
    "raw_state": {
        "issue_title": state.get("issue_title"),
        "impacted_components": state.get("impacted_components"),
        "risks": state.get("risks"),
        # ... other state fields
    }
}
# POST to dashboard API
```

### 2. Enricher Processing

The raw heartbeat data is processed to extract useful metrics. Each enricher adds specific information:

```python
# Example: Enrichers add specific metrics to each heartbeat

# ModelInfoEnricher: Which AI model is being used?
heartbeat["model"] = "claude-sonnet-4-20250514"

# TokenCountEnricher: How much of the context window is used?
heartbeat["context_tokens"] = len(str(heartbeat["raw_state"])) * 0.75
heartbeat["context_percent"] = (heartbeat["context_tokens"] / 200000) * 100

# PhaseStatusEnricher: What phase is the workflow in?
heartbeat["status"] = "design_done"  # or "in_progress", "complete", "error"
```

### 3. Storage

The enriched data is stored in a SQLite database for quick retrieval:

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

### 4. Real-time Updates

The browser automatically refreshes to show the latest status:

```javascript
// Frontend polls for updates every 5 seconds
setInterval(() => {
    fetch('/api/sessions')
        .then(response => response.json())
        .then(sessions => updateSessionCards(sessions));
}, 5000);
```

## Session Card Display

Each session shows:

```
┌─────────────────────────────────────────────┐
│ 🔵 Session abc123                          │
│                                             │
│ Issue: Add timeout support to BuildRun     │
│ Type: feature                               │
│                                             │
│ Design Agent   ✓ Complete                  │
│ Testing Agent  ⏳ In Progress              │
│ Docs Agent     ⏸ Pending                   │
│                                             │
│ Context: ████████░░ 82%                    │
│ Model: claude-sonnet-4                     │
│                                             │
│ Components: build_controller, buildrun_api │
│ Risks: 3 identified                        │
│                                             │
│ Last update: 2s ago                        │
└─────────────────────────────────────────────┘
```

## Technology Stack

### Backend
- **FastAPI**: REST API and WebSocket support
- **SQLite**: Lightweight storage for sessions/heartbeats
- **Uvicorn**: ASGI server

### Frontend
- **Vanilla JavaScript**: No framework overhead
- **Server-Sent Events (SSE)** or **WebSocket**: Real-time updates
- **CSS Grid**: Responsive session cards layout

### Integration
- **LangGraph hooks**: Inject heartbeat emission in graph nodes
- **Agent-agnostic**: Enricher pattern supports any agent type (Design, Testing, Docs, etc.)

## What You Can See

### 1. All Active Sessions at Once
View multiple agent workflows running simultaneously. See which ones are active, completed, or errored. Sort by time or context usage to focus on what matters.

### 2. Key Metrics That Matter
- **Context percentage**: The most important metric - tells you when an agent is running out of context space
- **Phase progression**: See the workflow move from Design → Docs → Complete
- **Component impact**: Which parts of the codebase are being analyzed
- **Risk tracking**: Visual alerts when risks are identified

### 3. Session Details
Click any session card to see the full details. Future versions will support pausing/resuming workflows and replaying session history.

### 4. Works with Any Agent Type
The dashboard isn't hardcoded for specific agents. It currently works with Design, Testing, and Docs agents. Add a new agent type, define its enrichers, and the dashboard automatically picks it up.

## Implementation Phases

### Phase 1: Core Dashboard (MVP)
- [ ] Heartbeat protocol and emission
- [ ] Basic enricher pipeline
- [ ] FastAPI backend with SQLite
- [ ] Simple web UI with session cards
- [ ] Real-time updates via SSE

### Phase 2: Enhanced Metrics
- [ ] Advanced enrichers (PR links, git status)
- [ ] Context usage graphs
- [ ] Phase duration analytics
- [ ] Risk highlighting and alerts

### Phase 3: Advanced Features
- [ ] WebSocket terminal relay (optional)
- [ ] Remote session spawning
- [ ] Session pause/resume
- [ ] Historical analysis and trends

## Comparison to Article

| Feature                    | Article Implementation | Our Implementation             |
|----------------------------|------------------------|--------------------------------|
| Agent Type                 | Claude Code CLI        | Design + Testing + Docs Agents |
| Heartbeat Source           | Hook scripts           | LangGraph node hooks  |
| Enricher Pattern           | ✓ Yes                  | ✓ Yes                 |
| Dashboard Backend          | API + DB               | FastAPI + SQLite      |
| Real-time Updates          | WebSocket              | SSE or WebSocket      |
| Terminal Relay             | ✓ tmux WebSocket       | ✗ Not needed          |
| Remote Session Spawning    | ✓ Yes                  | Future phase          |
| Multi-Device Support       | ✓ Yes                  | ✓ Yes                 |

## Design Decisions

### Why SQLite?
**Simple and practical**: No separate database server to install or configure. Perfect for local development. If you ever need to deploy this to a team server, you can switch to PostgreSQL later.

### Why Vanilla JavaScript?
**No build complexity**: The dashboard loads instantly - no webpack, no npm build step. Just open the HTML file in a browser. This keeps things simple and fast.

### Why Polling Instead of WebSockets?
**Good enough for now**: The dashboard refreshes every 5 seconds automatically. For monitoring agents that run for minutes, this is plenty fast. We can add WebSockets later if needed for sub-second updates.

### Why the Enricher Pattern?
**Clean separation of concerns**:
- Raw agent state goes in → enrichers extract metrics → dashboard displays them
- Want to show a new metric? Just add an enricher
- Each enricher is simple, testable, and independent
- Works for any agent type, not just Design and Docs

## Security Considerations

- Dashboard runs locally (localhost only by default)
- No authentication needed for local use
- For remote access: Add basic auth or API keys
- Sanitize session data before display (XSS prevention)

## Performance

- Heartbeat interval: 2-5 seconds (configurable)
- Database cleanup: Auto-purge sessions older than 7 days
- WebSocket connections: Max 100 concurrent clients
- Memory usage: ~50MB for 100 sessions

## Future Enhancements

1. **Multi-Project Support**: Monitor agents across different repos
2. **Alerting**: Notify when context exceeds threshold
3. **Session Replay**: Replay agent workflow from heartbeats
4. **Agent Logs**: Stream agent logs to dashboard
5. **Performance Analytics**: Track agent execution times
6. **Cost Tracking**: Estimate API costs from token usage
