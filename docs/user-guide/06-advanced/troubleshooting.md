# Troubleshooting

Common issues and their solutions. Start with [Enabling Debug Logging](#enabling-debug-logging) if the issue is not listed here.

---

## Authentication Errors

### "No Claude authentication configured"

```
DesignAgentError: No Claude authentication configured
```

**Cause:** `ANTHROPIC_VERTEX_PROJECT_ID` is not set in the environment.

**Solutions:**

```bash
# Set up Vertex AI authentication
gcloud auth application-default login
gcloud auth application-default set-quota-project your-gcp-project-id
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id

# Or add to .env
echo "ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id" >> .env
```

Or bypass authentication entirely with dry run mode:

```bash
uv run python scripts/test_agents.py --e2e --dry-run
```

### "gcloud not authenticated" or ADC errors

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
gcloud auth application-default print-access-token  # Verify it works
```

### "Vertex AI API not enabled"

```bash
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

### "Permission denied" on Vertex AI

```bash
gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

---

## Import Errors

### "ImportError: anthropic library is required"

**Cause:** Dependencies are not installed.

```bash
# Install all dependencies
uv venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify a specific package
uv run --with anthropic python -c "import anthropic; print('OK')"
```

---

## Repository Path Errors

### "RepositorySearchError: Repository path does not exist"

```
RepositorySearchError: Repository path does not exist: /path/to/repo
```

**Solution:**

```bash
# Verify the path exists
ls -la /path/to/repo

# Clone the repository if missing
git clone https://github.com/shipwright-io/build.git /path/to/repo

# Update .env with the correct path
echo "SHIPWRIGHT_REPO_PATH=/path/to/repo" >> .env
```

Repository path is optional. Remove it from `.env` if you do not need deep code analysis and the agent will fall back to component metadata only.

---

## API Errors

### "Claude API call failed: rate_limit_error"

**Cause:** GCP quota exceeded for Vertex AI Claude requests.

**Solutions:**

```bash
# Increase timeout in .env
echo "API_TIMEOUT=120" >> .env
```

Check your quota in the GCP console under Vertex AI > Quotas. You may need to request a quota increase for Claude model requests.

The system includes built-in retry with exponential backoff, so transient errors typically resolve on their own.

---

## Agent Input Errors

### "Missing required context keys" (Docs Agent)

```
RuntimeError: Missing required context keys
```

**Cause:** The Docs Agent requires `design_analysis`, `code_changes`, and `test_results` in the context.

**Solution:** Ensure all required keys are present when calling the agent directly:

```python
context = {
    "design_analysis": "...",  # Required
    "code_changes": {},         # Required (can be empty dict)
    "test_results": {},         # Required (can be empty dict)
    # Optional: test_summary, issue_title, issue_description, issue_type
}
```

When running through the orchestrator, these keys are always populated by prior agents.

---

## Git Operation Errors

### "GitOpResult.error: Directory already exists"

```
GitOpResult.error: Directory already exists: /tmp/claude/repo
```

**Solution:**

```python
from tools.git_ops import GitOps

ops = GitOps()
ops.cleanup_repository("/tmp/claude/repo")
ops.clone_repository("https://github.com/org/repo.git")
```

---

## Dashboard Issues

### Sessions not appearing in the dashboard UI

**Checks:**

```bash
# Confirm the dashboard is running
curl http://localhost:8080/api/health

# Verify heartbeats are enabled in .env
grep DASHBOARD_ENABLED .env

# Check the database file exists
ls -l /tmp/claude/dashboard.db

# View recent activity
grep "heartbeat" logs/dashboard/dashboard.log | tail -10
```

If the dashboard is not running, agents continue normally - heartbeats fail silently and the workflow is not blocked.

### Dashboard shows stale data

Sessions auto-refresh every 3 seconds. If data appears stale, reload the page. If a session stopped updating, the agent may have completed or errored - check agent logs for the session ID.

---

## Performance Issues

### High Context Usage (>80%)

When agents report context usage above 80%, they may run out of space before completing.

**Solutions:**

- Break the task into smaller, more focused issues
- Reduce the scope of component analysis in the issue description
- Reduce the maximum repository files scanned:

```bash
echo "MAX_REPO_FILES=50" >> .env
```

### Slow Repository Analysis or API Timeouts

Reduce repository scan scope:

```bash
echo "MAX_REPO_FILES=50" >> .env
```

Enable caching:

```bash
echo "CACHE_DIR=.cache" >> .env
echo "CACHE_TTL=7200" >> .env
```

Increase API timeout:

```bash
echo "API_TIMEOUT=120" >> .env
```

Use sparse checkout when working with large repositories:

```python
from tools.git_ops import GitOps

ops = GitOps()
ops.clone_repository(
    "https://github.com/org/large-repo.git",
    sparse_checkout=["pkg/apis", "pkg/controller"]
)
```

---

## Enabling Debug Logging

Enable verbose output to trace issues through the workflow.

**For the orchestrator**, set in `.env`:

```bash
LOG_LEVEL=DEBUG
LOG_FILE_PATH=/tmp/muilti-agents-debug.log
```

Then run and follow the log:

```bash
uv run python scripts/orchestrate.py --title "Test" --description "Debug run"
tail -f /tmp/muilti-agents-debug.log
```

**For the test CLI**, use the `--debug` flag:

```bash
uv run python scripts/test_agents.py --agent design --dry-run --debug
cat /tmp/claude/agent-tests/test_*.log
```

See [Logging](logging.md) for more details on log locations and formats.

---

[← Previous: Logging](logging.md) | [Back to Index →](../README.md)
