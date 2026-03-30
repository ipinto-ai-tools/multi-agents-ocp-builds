# Dry Run Mode

Dry run mode lets you test the system without making any Claude API calls. It uses pre-configured mock responses from `config/mock_responses.py`. No authentication is required.

---

## When to Use Dry Run Mode

| Use case | Benefit |
|----------|---------|
| Development | Test code changes without API usage or cost |
| CI/CD pipelines | Run validation without credentials |
| Debugging | Isolate logic issues from API behavior |
| Learning | Understand the workflow without API costs |

---

## What Is Mocked

| Component | Dry run behavior |
|-----------|-----------------|
| Design Agent | Returns mock design analysis, components, risks, criteria |
| Development Agent | Uses design mock output as input |
| Code Review Agent | Returns mock PASS result (`MOCK_CODE_REVIEW_PASS`); no API call, no Qodo CLI |
| Testing Agent | Returns mock test plans and Ginkgo v2 code |
| Docs Agent | Returns mock PR summary and release notes |
| Heartbeat emissions | Logged but not sent to dashboard |
| Dashboard API checks | Skipped |
| Skills (`fetch_jira_ticket`, `update_jira`, `fetch_github_prs`) | Each skill's `_mock_response()` is called instead of `_execute()` — see below |

The full workflow code path still executes - only the Claude API call itself is replaced with the mock response.

---

## Skills Layer and DRY_RUN

`DRY_RUN` handling for the skills layer is centralized in `Skill.run()` (`skills/base.py`). Every skill follows the same dispatch pattern automatically — no per-skill conditional is needed:

```python
# Skill.run() in skills/base.py
def run(self, inputs: dict) -> dict:
    if self._is_dry_run():          # reads DRY_RUN env var
        return self._mock_response()
    return self._execute(inputs)
```

**Per-skill mock behavior:**

| Skill | `_mock_response()` returns |
| ----- | ------------------------- |
| `FetchJiraTicketSkill` | Mapped mock Jira state (same fields as a real ticket fetch — title, description, issue type, linked PR URLs) |
| `UpdateJiraSkill` | `{"success": True, "dry_run": True}` |
| `FetchGitHubPRsSkill` | `{"pr_data": []}` |

This means entry points (`scripts/orchestrate.py`, `scripts/test_agents.py`) need no special casing for skills in dry-run mode — setting `DRY_RUN=true` is sufficient.

---

## Running Dry Run

### Full E2E Workflow

Test all five agents in sequence (including Code Review):

```bash
uv run python scripts/test_agents.py --e2e --dry-run
```

With verbose debug logging:

```bash
uv run python scripts/test_agents.py --e2e --dry-run --debug
```

### Single Agent

Test one agent in isolation:

```bash
# Design agent
uv run python scripts/test_agents.py --agent design --dry-run --debug

# Testing agent
uv run python scripts/test_agents.py --agent testing --dry-run --debug

# Docs agent
uv run python scripts/test_agents.py --agent docs --dry-run --debug
```

### Custom Issue Data

Override the default mock issue title and description:

```bash
uv run python scripts/test_agents.py --e2e --dry-run \
  --title "Add SSH key support for private Git repos" \
  --description "Users need to build from private Git repos using SSH authentication"
```

---

## Test CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--agent {design\|testing\|docs\|code_review}` | Test a specific agent | - |
| `--e2e` | Test complete E2E workflow | - |
| `--dashboard` | Test dashboard functionality | - |
| `--title TEXT` | Issue title | Default mock title |
| `--description TEXT` | Issue description | Default mock description |
| `--dry-run` | Use mock responses | false |
| `--debug` | Enable verbose logging | false |
| `--output-dir PATH` | Artifact output directory | `/tmp/claude/agent-tests` |

---

## Output Artifacts

All test runs save artifacts to the output directory:

| File | Description |
|------|-------------|
| `test_YYYYMMDD_HHMMSS.log` | Complete test log with timestamps |
| `design_output.json` | Design agent structured output |
| `testing_output.json` | Testing agent structured output |
| `docs_output.json` | Docs agent structured output |
| `e2e_result.json` | Complete E2E workflow results |
| `dashboard_test_results.json` | Dashboard test results |

Inspect artifacts after a run:

```bash
cat /tmp/claude/agent-tests/design_output.json | jq .
cat /tmp/claude/agent-tests/e2e_result.json | jq .
```

Save artifacts from important test runs to a dated directory:

```bash
uv run python scripts/test_agents.py --e2e --dry-run \
  --output-dir ./test-runs/$(date +%Y%m%d-%H%M%S)
```

---

## Dashboard Testing in Dry Run

Test dashboard components without a running backend:

```bash
# Dry-run skips the live backend check
uv run python scripts/test_agents.py --dashboard --dry-run
```

With a live dashboard:

```bash
# Terminal 1: start the dashboard
uv run python scripts/run_dashboard.py

# Terminal 2: run dashboard tests
uv run python scripts/test_agents.py --dashboard --debug
```

Expected output:

```
[1/5] Testing dashboard module imports
  OK Dashboard modules import successfully

[2/5] Testing heartbeat emission
  SKIP Heartbeat emission (skipped in dry-run)

[3/5] Testing enrichers
  OK Enricher processed heartbeat: 15 fields

[4/5] Testing database operations
  SKIP Database backend not running (start with run_dashboard.py)

[5/5] Testing frontend file existence
  OK Frontend file exists

Dashboard Test Summary: Passed: 3 | Failed: 0 | Skipped: 2
```

---

## CI/CD Integration

Dry run mode is designed for use in CI pipelines. It returns exit code 0 on success and 1 on failure.

```bash
# Minimal CI validation
uv run python scripts/test_agents.py --e2e --dry-run

# With stored artifacts
uv run python scripts/test_agents.py --e2e --dry-run \
  --output-dir ./ci-results/$(date +%Y%m%d-%H%M%S)
```

---

## Debug Output Example

Running with `--debug` shows detailed execution information:

```
DEBUG | multi_agent_testing.design | Full context keys: ['issue_title', 'issue_description', 'repo_path']
DEBUG | multi_agent_testing.design | [DRY-RUN] Claude API call: model=claude-sonnet-4, tokens=8000
DEBUG | multi_agent_testing.design | Impacted components: 3
DEBUG | multi_agent_testing.design | Risks identified: 3
DEBUG | multi_agent_testing.design | Acceptance criteria: 6
INFO  | multi_agent_testing | Artifact saved: /tmp/claude/agent-tests/design_output.json
```

---

[← Previous: Authentication](../05-authentication/authentication.md) | [Next: Logging →](logging.md) | [Output Validation →](output-validation.md)
