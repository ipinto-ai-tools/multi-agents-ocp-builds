# Session Management

Each call to `orchestrate()` creates one session in the dashboard database. Sessions accumulate over time and require periodic cleanup to keep the database small.

---

## Session Lifecycle

A session progresses through these phases:

```
planning → executing → done
                    → error  (on failure)
```

Active sessions (any phase other than `done` or `error`) are never touched by cleanup operations.

### Dual Timestamps

Each session card in the UI shows two timestamps:

- **Started** — when the first heartbeat for the session was received. This is the wall-clock time the workflow began.
- **Last updated** — time elapsed since the most recent heartbeat. This value refreshes every 3 seconds while the dashboard is open.

Use the gap between these two values to identify stuck sessions. If "Last updated" has not advanced for several minutes while the session is still in an active phase, the agent has likely hung or lost connectivity. See [Troubleshooting](#troubleshooting) for steps to investigate.

---

## Automatic Cleanup

The dashboard backend runs a background task that automatically removes old completed sessions.

| Setting | Value |
|---------|-------|
| Frequency | Every 6 hours |
| Default threshold | Sessions completed more than 24 hours ago |
| Targets | Sessions with `phase='done'` or `phase='error'` only |

Cleanup events are written to the dashboard log:

```
[INFO] [dashboard.backend] Started automatic cleanup task (runs every 6 hours)
[INFO] [dashboard.backend] Automatic cleanup: {'sessions_deleted': 5, 'heartbeats_deleted': 23}
```

---

## Manual Cleanup

### Delete Old Completed Sessions

Remove completed sessions older than a specified age. Defaults to 24 hours.

```bash
# Default: delete sessions older than 24 hours
curl -X DELETE http://localhost:8080/api/sessions/cleanup

# Custom age: delete sessions older than 12 hours
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=12"

# Weekly retention: delete sessions older than 7 days
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=168"
```

Response:

```json
{
  "sessions_deleted": 3,
  "heartbeats_deleted": 15
}
```

### Delete All Completed Sessions

Remove all completed sessions regardless of age. Useful before demos.

```bash
curl -X DELETE http://localhost:8080/api/sessions/completed
```

Response:

```json
{
  "sessions_cleared": 10
}
```

---

## Python Client Examples

```python
import requests

# Delete sessions older than 48 hours
response = requests.delete(
    "http://localhost:8080/api/sessions/cleanup",
    params={"max_age_hours": 48}
)
result = response.json()
print(f"Deleted {result['sessions_deleted']} sessions")
print(f"Deleted {result['heartbeats_deleted']} heartbeats")

# Clear all completed sessions before a demo
response = requests.delete("http://localhost:8080/api/sessions/completed")
result = response.json()
print(f"Cleared {result['sessions_cleared']} completed sessions")
```

---

## Monitoring Database Size

```bash
# Check database file size
ls -lh /tmp/claude/dashboard.db

# Count active sessions via API
curl http://localhost:8080/api/sessions | jq 'length'

# View recent cleanup activity
grep "cleanup" logs/dashboard/dashboard.log | tail -20
```

---

## Custom Retention Policy

Use a scheduled script to implement custom cleanup policies:

```python
import requests
import schedule
import time

def cleanup_policy():
    """Keep only the last 48 hours of completed sessions."""
    response = requests.delete(
        "http://localhost:8080/api/sessions/cleanup",
        params={"max_age_hours": 48}
    )
    result = response.json()
    print(f"Cleanup: deleted {result['sessions_deleted']} sessions")

# Run daily at midnight
schedule.every().day.at("00:00").do(cleanup_policy)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## What Gets Deleted

### `DELETE /api/sessions/cleanup` (age-based)

Deletes sessions that meet ALL of these conditions:
1. Phase is `done` or `error`
2. Last updated more than `max_age_hours` ago
3. Cascade: also deletes all associated heartbeat records

### `DELETE /api/sessions/completed` (all completed)

Deletes sessions that meet ANY of these conditions:
1. Phase is `done` or `error`
2. No age restriction applies
3. Cascade: also deletes all associated heartbeat records

**Active sessions are never deleted by either endpoint.**

---

## Troubleshooting

### Sessions not being cleaned up automatically

```bash
# Verify the background task started
grep "Started automatic cleanup task" logs/dashboard/dashboard.log

# Check session phases - cleanup only targets done/error
curl http://localhost:8080/api/sessions | jq '.[].status'
```

### Database lock errors during cleanup

If you see `database is locked` errors:
- Reduce cleanup frequency by modifying `dashboard/backend.py`
- Ensure no other process holds a connection to the SQLite file
- Avoid running multiple cleanup calls concurrently

### Dashboard not receiving heartbeats

```bash
# Confirm dashboard is running
curl http://localhost:8080/api/health

# Verify heartbeats are enabled in .env
grep DASHBOARD_ENABLED .env

# Check the database exists
ls -l /tmp/claude/dashboard.db
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_DB_PATH` | `/tmp/claude/dashboard.db` | SQLite database path |
| `DASHBOARD_URL` | `http://localhost:8080` | Where agents send heartbeats |
| `DASHBOARD_ENABLED` | `true` | Set to `false` to disable heartbeat emissions |

To change the automatic cleanup threshold, edit `dashboard/backend.py`:

```python
# Change cleanup frequency (default: 6 hours → 12 hours)
await asyncio.sleep(12 * 60 * 60)

# Change age threshold (default: 24 hours → 48 hours)
result = db.cleanup_old_sessions(max_age_hours=48)
```

---

[← Previous: Dashboard Overview](overview.md) | [Next: Authentication Overview →](../05-authentication/overview.md)
