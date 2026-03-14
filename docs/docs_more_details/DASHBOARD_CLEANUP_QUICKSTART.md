# Dashboard Cleanup - Quick Reference

## Quick Commands

### Cleanup old sessions (default: 24 hours)
```bash
curl -X DELETE http://localhost:8080/api/sessions/cleanup
```

### Cleanup with custom age
```bash
# 12 hours
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=12"

# 7 days
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=168"
```

### Clear all completed sessions
```bash
curl -X DELETE http://localhost:8080/api/sessions/completed
```

## Python Usage

```python
import requests

# Cleanup old sessions
response = requests.delete(
    "http://localhost:8080/api/sessions/cleanup",
    params={"max_age_hours": 24}
)
print(response.json())
# Output: {"sessions_deleted": 3, "heartbeats_deleted": 15}

# Clear all completed sessions
response = requests.delete("http://localhost:8080/api/sessions/completed")
print(response.json())
# Output: {"sessions_cleared": 10}
```

## What Gets Deleted

### By Age (cleanup endpoint)
- Completed sessions (`phase='done'` or `phase='error'`)
- Older than specified hours
- Includes all heartbeats

### Clear All (completed endpoint)
- All completed sessions (`phase='done'` or `phase='error'`)
- Regardless of age
- Includes all heartbeats

## Automatic Cleanup

- Runs every **6 hours**
- Deletes sessions older than **24 hours**
- Only targets completed sessions
- Logs to `logs/dashboard/dashboard.log`

## Testing

```bash
# Unit tests
PYTHONPATH=. uv run python tests/test_dashboard_cleanup.py

# API tests (requires running backend)
PYTHONPATH=. uv run python examples/test_cleanup_api.py
```

## Monitoring

```bash
# View cleanup logs
grep "cleanup" logs/dashboard/dashboard.log

# Check database size
ls -lh /tmp/claude/dashboard.db

# Count sessions
curl http://localhost:8080/api/sessions | jq 'length'
```

## Common Use Cases

### Weekly maintenance
```bash
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=168"
```

### Pre-demo cleanup
```bash
curl -X DELETE http://localhost:8080/api/sessions/completed
```

### Testing cleanup
```bash
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=1"
```

## See Also

- [Full Documentation](DASHBOARD_CLEANUP.md) - Detailed cleanup documentation
- [Backend API](../dashboard/backend.py) - Implementation details
