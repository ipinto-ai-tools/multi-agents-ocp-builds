# Dashboard Session Cleanup

The dashboard backend includes automatic and manual session cleanup functionality to prevent database bloat and maintain performance.

## Features

- **Automatic background cleanup** - Runs every 6 hours to remove old completed sessions
- **Manual cleanup endpoint** - Clean up sessions older than a specified age
- **Clear completed endpoint** - Immediately remove all completed sessions
- **Configurable thresholds** - Customize age limits for cleanup

## Automatic Cleanup

The dashboard backend automatically cleans up old completed sessions in the background.

### Configuration

- **Frequency**: Every 6 hours
- **Default threshold**: 24 hours
- **Target sessions**: Only sessions with `phase='done'` or `phase='error'`

### Behavior

The automatic cleanup task:
1. Starts when the backend server starts
2. Runs every 6 hours
3. Deletes completed sessions older than 24 hours
4. Logs results to the dashboard backend log

### Logs

Automatic cleanup events are logged:

```
[2026-03-12 18:00:00] [INFO] [dashboard.backend] - Started automatic cleanup task (runs every 6 hours)
[2026-03-12 18:00:00] [INFO] [dashboard.backend] - Automatic cleanup: {'sessions_deleted': 5, 'heartbeats_deleted': 23}
```

## Manual Cleanup API

### Endpoint: DELETE /api/sessions/cleanup

Clean up completed sessions older than a specified age.

**Parameters:**
- `max_age_hours` (optional, default: 24) - Maximum age in hours for completed sessions

**Returns:**
```json
{
  "sessions_deleted": 3,
  "heartbeats_deleted": 15
}
```

**Example:**

```bash
# Clean up sessions older than 24 hours (default)
curl -X DELETE http://localhost:8080/api/sessions/cleanup

# Clean up sessions older than 12 hours
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=12"

# Clean up sessions older than 7 days
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=168"
```

**Python example:**

```python
import requests

# Clean up old sessions
response = requests.delete(
    "http://localhost:8080/api/sessions/cleanup",
    params={"max_age_hours": 48}
)

result = response.json()
print(f"Deleted {result['sessions_deleted']} sessions")
print(f"Deleted {result['heartbeats_deleted']} heartbeats")
```

## Clear Completed Sessions API

### Endpoint: DELETE /api/sessions/completed

Clear all completed sessions regardless of age.

**Parameters:** None

**Returns:**
```json
{
  "sessions_cleared": 10
}
```

**Example:**

```bash
# Clear all completed sessions
curl -X DELETE http://localhost:8080/api/sessions/completed
```

**Python example:**

```python
import requests

# Clear all completed sessions
response = requests.delete("http://localhost:8080/api/sessions/completed")

result = response.json()
print(f"Cleared {result['sessions_cleared']} completed sessions")
```

## What Gets Deleted

### Cleanup by Age (DELETE /api/sessions/cleanup)

Deletes sessions that meet **ALL** these criteria:
1. **Completed status**: `phase='done'` OR `phase='error'`
2. **Age**: Older than `max_age_hours` parameter
3. **Cascading**: Deletes both session records and all associated heartbeats

### Clear All Completed (DELETE /api/sessions/completed)

Deletes sessions that meet **ANY** of these criteria:
1. `phase='done'` OR `phase='error'`
2. **No age restriction**: Deletes regardless of when the session completed
3. **Cascading**: Deletes both session records and all associated heartbeats

### What is NOT Deleted

Active sessions are never deleted by cleanup operations:
- Sessions with `phase='planning'`
- Sessions with `phase='executing'`
- Sessions with `phase='reviewing'`
- Any other active phase

## Use Cases

### Regular Maintenance

Run cleanup periodically to keep database size manageable:

```bash
# Weekly cleanup of sessions older than 7 days
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=168"
```

### Pre-Demo Cleanup

Clear all completed sessions before a demo:

```bash
# Remove all completed sessions
curl -X DELETE http://localhost:8080/api/sessions/completed
```

### Custom Retention Policy

Implement custom retention policies:

```python
import requests
import schedule
import time

def cleanup_policy():
    """Custom cleanup policy: keep 48 hours of completed sessions."""
    response = requests.delete(
        "http://localhost:8080/api/sessions/cleanup",
        params={"max_age_hours": 48}
    )
    result = response.json()
    print(f"Cleanup: {result}")

# Run every day at midnight
schedule.every().day.at("00:00").do(cleanup_policy)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Testing Cleanup

Test cleanup without affecting production data:

```bash
# Clean up sessions older than 1 hour (for testing)
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=1"
```

## Database Schema Impact

The cleanup operations affect two tables:

### Sessions Table
```sql
DELETE FROM sessions WHERE id IN (...)
```

### Heartbeats Table
```sql
DELETE FROM heartbeats WHERE session_id IN (...)
```

## Performance Considerations

- **Cleanup is transactional**: All deletes succeed or fail together
- **Indexed queries**: Uses index on `(session_id, timestamp)` for fast lookups
- **No blocking**: Cleanup runs in background thread (automatic mode)
- **Minimal impact**: Deletes use parameterized queries with batch operations

## Monitoring

### Check Cleanup Activity

View cleanup logs in the dashboard backend log:

```bash
# View recent cleanup activity
grep "cleanup" logs/dashboard/dashboard.log | tail -n 20
```

### Monitor Database Size

Check database file size:

```bash
# Check database size
ls -lh /tmp/claude/dashboard.db

# Or with du
du -h /tmp/claude/dashboard.db
```

### Session Count

Get current session count via API:

```bash
# Count active sessions
curl http://localhost:8080/api/sessions | jq 'length'
```

## Configuration

### Environment Variables

- `DASHBOARD_DB_PATH` - Database file path (default: `/tmp/claude/dashboard.db`)

### Customizing Automatic Cleanup

To change the automatic cleanup behavior, modify `dashboard/backend.py`:

```python
# Change cleanup frequency (default: 6 hours)
await asyncio.sleep(12 * 60 * 60)  # Run every 12 hours

# Change age threshold (default: 24 hours)
result = db.cleanup_old_sessions(max_age_hours=48)  # Keep 48 hours
```

## Testing

Run the cleanup tests:

```bash
# Run unit tests
PYTHONPATH=. uv run python tests/test_dashboard_cleanup.py

# Run API integration tests (requires running backend)
PYTHONPATH=. uv run python examples/test_cleanup_api.py
```

## Troubleshooting

### Cleanup Not Running

**Symptom**: Old sessions not being deleted

**Solutions**:
1. Check if background task is running:
   ```bash
   grep "Started automatic cleanup task" logs/dashboard/dashboard.log
   ```
2. Verify sessions are actually completed (`phase='done'` or `phase='error'`)
3. Check session age matches threshold

### Database Lock Errors

**Symptom**: `database is locked` errors during cleanup

**Solutions**:
1. Reduce cleanup frequency
2. Ensure no long-running queries during cleanup
3. Check for competing database connections

### Cleanup Deleting Too Much

**Symptom**: Active sessions being deleted

**Solutions**:
1. Verify phase values in heartbeats (`phase='done'` or `phase='error'` only)
2. Check `max_age_hours` parameter is correct
3. Review cleanup logs for unexpected deletions

## Best Practices

1. **Regular cleanup**: Run cleanup periodically (daily or weekly)
2. **Monitor logs**: Check cleanup logs for unexpected behavior
3. **Test first**: Test cleanup with short thresholds before production
4. **Backup important sessions**: Export sessions before mass cleanup
5. **Use appropriate thresholds**: Balance retention needs with database size

## Future Enhancements

Potential future improvements:

- Configurable cleanup schedule via environment variables
- Selective cleanup by agent type or issue type
- Archive mode (export before delete)
- Cleanup metrics dashboard
- Automatic vacuum after cleanup
