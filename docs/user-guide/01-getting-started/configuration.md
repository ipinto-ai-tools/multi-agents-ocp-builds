# Configuration

Configure the system using environment variables in a `.env` file.

---

## Setup

Copy the example file and open it in your editor:

```bash
cp .env.example .env
```

The only required variable for live runs is `ANTHROPIC_VERTEX_PROJECT_ID`. All others have sensible defaults.

---

## Environment Variables Reference

### Authentication

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_VERTEX_PROJECT_ID` | Yes | - | Your GCP project ID |
| `CLOUD_ML_REGION` | No | `us-east5` | GCP region for Vertex AI |

```bash
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
CLOUD_ML_REGION=us-east5
```

See [Vertex AI Setup](../05-authentication/vertex-ai.md) for authentication instructions.

### Claude Model

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model version |
| `CLAUDE_MAX_TOKENS` | `8000` | Default max tokens per response |

> **Note:** The Development and Testing agents override `CLAUDE_MAX_TOKENS` with 16000 to accommodate larger code generation outputs.

### Repository Paths

These paths are optional but enable agents to analyze actual Shipwright source code for more accurate component impact analysis.

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIPWRIGHT_REPO_PATH` | (none) | Path to Shipwright Build repository |
| `OPENSHIFT_BUILDS_REPO_PATH` | (none) | Path to OpenShift Builds repository |

```bash
SHIPWRIGHT_REPO_PATH=/home/user/git/shipwright-build
OPENSHIFT_BUILDS_REPO_PATH=/home/user/git/openshift-builds
```

### Dashboard

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_URL` | `http://localhost:8080` | URL where agents send heartbeats |
| `DASHBOARD_ENABLED` | `true` | Set to `false` to disable heartbeat emissions |
| `DASHBOARD_DB_PATH` | `/tmp/claude/dashboard.db` | SQLite database path |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | `text` | Format: `text` or `json` |
| `LOG_FILE_PATH` | (none) | File path for log output in addition to stdout |

```bash
LOG_LEVEL=DEBUG
LOG_FORMAT=text
LOG_FILE_PATH=/tmp/muilti-agents-ocp-builds.log
```

### Performance

| Variable | Default | Description |
|----------|---------|-------------|
| `API_TIMEOUT` | `60` | API request timeout in seconds |
| `MAX_REPO_FILES` | `100` | Maximum repository files to analyze |
| `CACHE_DIR` | `.cache` | Directory for cached repository analysis |
| `CACHE_TTL` | `3600` | Cache lifetime in seconds |

If you see slow repository analysis or API timeouts, reduce `MAX_REPO_FILES` first:

```bash
MAX_REPO_FILES=50
API_TIMEOUT=120
```

### GitHub Integration

Required for fetching upstream PR metadata linked to Jira tickets. `GITHUB_TOKEN` and `TARGET_GITHUB_REPO` are also used by `scripts/publish.py` to push generated code as a pull request.

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `GITHUB_TOKEN` | Optional | (none) | Personal access token for GitHub PR data. Required by `publish.py --push-code`. |
| `GITHUB_REQUEST_TIMEOUT` | Optional | `10` | Timeout in seconds for GitHub API requests. |
| `TARGET_GITHUB_REPO` | Optional | (none) | Target repository for `publish.py --push-code`, in `org/repo` format. |
| `TARGET_GITHUB_BASE_BRANCH` | Optional | `main` | Base branch in the target repository that the generated PR targets. |
| `QODO_API_KEY` | Optional | (none) | API key for Qodo code review. If not set, Qodo falls back to OAuth authentication. |

```bash
# GitHub Integration (optional — enriches docs agent with upstream PR context)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REQUEST_TIMEOUT=10

# Required by publish.py --push-code
TARGET_GITHUB_REPO=openshift-builds/builds
TARGET_GITHUB_BASE_BRANCH=main

# Optional — Qodo code review
QODO_API_KEY=your-qodo-api-key
```

To create a `GITHUB_TOKEN`: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens. Required scope: `Contents` (read-only) on the target repositories. For `publish.py --push-code`, the token also needs `Contents` (write) permission on the target repository.

### Privacy and Security

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `PII_REDACTION_ENABLED` | `true` | Redact PII from Jira and GitHub data before it enters the agent pipeline. Set to `false` only for local development — never in production. |
| `PROMPT_GUARD_ENABLED` | `true` | Sanitize external text for prompt injection patterns before assembling agent prompts. Set to `false` only for local development — never in production. |
| `OUTPUT_SANITIZER_ENABLED` | `true` | Enable the output sanitizer that checks agent responses before they are written to disk or returned to the caller. Set to `false` only for local development. |

See [PII Redaction](../07-security/pii-redaction.md) for details on what is redacted and how the public domain allowlist works.

### Agent Behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_REPO_ANALYSIS` | `true` | Enable repository code analysis |
| `DESIGN_OUTPUT_FORMAT` | `markdown` | Design output format: `markdown` or `json` |
| `MANUAL_APPROVAL` | `false` | Pause for user approval between agent phases |

---

## Complete Example .env

```bash
# Authentication (required)
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
CLOUD_ML_REGION=us-east5

# Repository context (optional but recommended)
SHIPWRIGHT_REPO_PATH=/home/user/git/shipwright-build

# Model settings
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TOKENS=8000

# Dashboard
DASHBOARD_URL=http://localhost:8080
DASHBOARD_ENABLED=true
DASHBOARD_DB_PATH=/tmp/claude/dashboard.db

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=text

# Performance
API_TIMEOUT=60
MAX_REPO_FILES=100

# Workflow control
MANUAL_APPROVAL=false
```

---

## Security Practices

- Never commit `.env` to version control. It is already listed in `.gitignore`.
- Set restrictive file permissions: `chmod 600 .env`
- Rotate gcloud credentials periodically with `gcloud auth application-default login`
- Do not set `ANTHROPIC_API_KEY` in `.env` — the system uses Vertex AI, not direct API keys

---

[← Previous: Quick Start](quick-start.md) | [Next: Architecture →](../02-concepts/architecture.md)
