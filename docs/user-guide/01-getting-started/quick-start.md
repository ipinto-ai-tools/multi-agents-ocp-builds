# Setup and Quick Start

Everything you need to go from zero to running the full agent pipeline.

---

## 1. Prerequisites

**Required tools:**

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`) — for Vertex AI authentication
- [gh CLI](https://cli.github.com/) — required only if using `publish.py --push-code`

**Clone and install:**

```bash
git clone https://github.com/your-org/muilti-agents-ocp-builds.git
cd muilti-agents-ocp-builds
uv venv && uv pip install -r requirements.txt
```

**Copy the example environment file:**

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in the sections that follow.

---

## 2. Configure Claude API (Google Vertex AI)

The system uses Google Vertex AI to access Claude. No API key is stored anywhere — authentication is handled entirely through Application Default Credentials (ADC) managed by the Google Cloud CLI.

### Step 1: Install the Google Cloud CLI

Follow the official guide: <https://cloud.google.com/sdk/docs/install>

Verify the installation:

```bash
gcloud --version
```

### Step 2: Authenticate

```bash
gcloud auth application-default login
```

This opens a browser window for Google account sign-in. Credentials are cached at `~/.config/gcloud/application_default_credentials.json`.

### Step 3: Set the billing project

```bash
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
```

If you do not know your project ID:

```bash
gcloud projects list
```

### Step 4: Enable the Vertex AI API

```bash
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

### Step 5: Grant IAM permissions

Your account needs the `roles/aiplatform.user` role:

```bash
gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

### Step 6: Set environment variables

In your `.env` file:

```bash
# Required
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id

# Optional — defaults to us-east5
CLOUD_ML_REGION=us-east5
```

Available regions: `us-east5` (default), `us-central1`, `europe-west1`, `asia-southeast1`.

### Model selection

```bash
# Claude model to use (default: claude-sonnet-4-6)
CLAUDE_MODEL=claude-sonnet-4-6

# Max tokens per response (default: 8000)
# Development and Testing agents override this with 16000 automatically
CLAUDE_MAX_TOKENS=8000
```

### Verify authentication

```bash
gcloud auth application-default print-access-token
```

Or run the bundled auth example:

```bash
uv run python examples/auth_example.py
```

---

## 3. Configure Jira

Jira integration lets you pass a ticket ID directly to the pipeline instead of writing `--title` and `--description` by hand. The system fetches the title, description, acceptance criteria, priority, labels, and linked issues automatically.

**Required variables:**

| Variable          | Description                              |
| ----------------- | ---------------------------------------- |
| `JIRA_BASE_URL`   | Your Atlassian Cloud base URL            |
| `JIRA_USER_EMAIL` | The email address tied to your API token |
| `JIRA_API_TOKEN`  | Your Atlassian API token                 |

**Generate a Jira API token:**

1. Go to <https://id.atlassian.com/manage-profile/security>
2. Under "API tokens", click "Create API token"
3. Give it a name and copy the generated value

Add to your `.env` file:

```bash
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

> **VPN required:** The Jira REST API endpoint is not reachable from outside the corporate network. If you are working off-VPN, use `--dry-run` mode instead.

---

## 4. Configure GitHub

GitHub integration enriches the docs agent with upstream PR context when Jira tickets have linked pull requests. It is also required by `publish.py --push-code` when pushing generated artifacts as a pull request.

| Variable                    | Purpose                                                                                   |
| --------------------------- | ----------------------------------------------------------------------------------------- |
| `GITHUB_TOKEN`              | Fetches PR metadata from Jira-linked pull requests; required for `publish.py --push-code` |
| `TARGET_GITHUB_REPO`        | Target repository for `publish.py --push-code`, in `org/repo` format                      |
| `TARGET_GITHUB_BASE_BRANCH` | Base branch the generated PR targets (default: `main`)                                    |

**Create a GitHub personal access token:**

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Set "Contents" to read-only on the target repositories
3. If using `publish.py --push-code`, also grant "Contents" write permission on the target repository

Add to your `.env` file:

```bash
# Enriches docs agent with upstream PR context
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REQUEST_TIMEOUT=10

# Required by publish.py --push-code
TARGET_GITHUB_REPO=openshift-builds/builds
TARGET_GITHUB_BASE_BRANCH=main
```

Without a `GITHUB_TOKEN`, the pipeline continues normally — PR enrichment is silently skipped.

---

## 5. Configure Qodo Code Review (optional)

The code review phase runs between Development and Testing and can automatically route failing code back to the Development agent for fixes. By default it uses Claude with no additional tools. Qodo CLI is an optional enhancement that adds static analysis on top of the Claude review.

**Two modes:**

| Mode | What it requires | When to use |
|------|-----------------|-------------|
| Claude-only (default) | Nothing — works out of the box | Most users |
| Qodo CLI + Claude | `npm install -g @qodo/command` + auth | Enhanced static analysis |

**Enable Qodo CLI (optional):**

```bash
npm install -g @qodo/command
```

Then set the path in `.env`:

```bash
QODO_CLI_PATH=/home/user/.npm-global/bin/qodo
```

**Authenticate Qodo:**

For local development, run the interactive login once:

```bash
qodo login
```

This stores the OAuth token at `~/.qodo/auth.key`. No further configuration is needed.

For CI or headless environments, use an API key instead:

```bash
# Generate at: https://app.qodo.ai/settings/api-keys
QODO_API_KEY=your-qodo-api-key
```

**Code review variables:**

```bash
# Set to false to skip code review entirely
QODO_REVIEW_ENABLED=true

# Maximum auto-fix iterations before continuing to Testing regardless
MAX_REVIEW_ITERATIONS=3

# Severity threshold that triggers the auto-fix loop
# high   = block only on [BLOCKING] findings (default)
# medium = block on [BLOCKING] and [WARNING] findings
# low    = block on any finding
QODO_BLOCKING_THRESHOLD=high
```

If Qodo CLI is unavailable, exits with an error, or times out, the agent automatically falls back to Claude-only review. The pipeline is never blocked by a Qodo CLI failure.

---

## 6. Configure Repository Paths

Repository paths are optional but strongly recommended. When set, the design agent reads actual Go types, CRDs, and controllers from source to produce more accurate component impact analysis.

**Upstream — Shipwright Build (open-source):**

```bash
# The open-source Shipwright Build repository
# Design agent uses this to analyze Go types, CRDs, and controllers
SHIPWRIGHT_REPO_PATH=/home/user/git/shipwright-build
```

Clone the upstream repo if you do not have it:

```bash
git clone https://github.com/shipwright-io/build.git /home/user/git/shipwright-build
```

**Downstream — OpenShift Builds (Red Hat fork):**

```bash
# The Red Hat downstream fork
# Provides downstream-specific patches and configurations
OPENSHIFT_BUILDS_REPO_PATH=/home/user/git/openshift-builds
```

Without these paths, the design agent falls back to component metadata only. Analysis is still valid, but less precise for deeply nested type hierarchies.

---

## 7. Debug and Logging

**CLI flag — single run only:**

The `--debug` flag enables `DEBUG` log level for a single pipeline run without changing your `.env`:

```bash
uv run python scripts/orchestrate.py \
  --jira-ticket BUILD-123 \
  --output-dir ./output/BUILD-123 \
  --debug
```

**Persistent logging via `.env`:**

```bash
# Verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
LOG_LEVEL=DEBUG

# Format: text or json (default: text)
LOG_FORMAT=text

# Write logs to a file in addition to stdout (optional)
LOG_FILE_PATH=/tmp/muilti-agents-ocp-builds.log
```

---

## 8. Run the Pipeline

### From a Jira ticket (recommended)

```bash
uv run python scripts/orchestrate.py \
  --jira-ticket BUILD-1707 \
  --output-dir ./output/BUILD-1707
```

The orchestrator fetches the ticket data automatically and runs the full five-phase pipeline: Design → Development → Code Review → Testing → Documentation.

### From a title and description

```bash
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need configurable timeouts to prevent hanging builds" \
  --output-dir ./output
```

### With debug logging

```bash
uv run python scripts/orchestrate.py \
  --jira-ticket BUILD-1707 \
  --output-dir ./output/BUILD-1707 \
  --debug
```

### What the output directory contains

When `--output-dir` is specified, the directory is created if it does not exist. Artifacts saved:

| Path | Contents |
|------|----------|
| `state.json` | Full pipeline state |
| `design/` | Design analysis, component impact, risks, acceptance criteria |
| `code/` | Generated Go source files |
| `tests/` | Generated Ginkgo v2 test files |
| `docs/` | PR summary, release notes, user documentation |

The `--output-dir` path is required by `scripts/publish.py` when pushing artifacts to GitHub or Jira.

### What happens during a run

The terminal prints a header for each phase with a per-phase timer:

```text
Phase 1/5 · Design
Phase 2/5 · Development
Phase 3/5 · Code Review
Phase 4/5 · Testing
Phase 5/5 · Documentation
```

When all phases finish, a summary is printed:

```text
Run complete
  Duration:   3m 42s
  Artifacts:  ./output/BUILD-1707
  Dashboard:  http://localhost:8080
```

If an agent raises an unhandled exception, the workflow sets `current_phase = "error"` and stops early. The final state contains the error message.

### Dry run (no credentials needed)

Use `--dry-run` to run without credentials or VPN. Pre-configured mock responses are used and no API calls are made:

```bash
uv run python scripts/orchestrate.py --jira-ticket SHIP-123 --dry-run
```

---

## 9. Monitor with the Dashboard

Start the dashboard before running the orchestrator to watch each agent's progress in real time.

**Terminal 1 — start the dashboard:**

```bash
uv run python scripts/run_dashboard.py
```

Open http://localhost:8080 in your browser.

**Terminal 2 — run the pipeline:**

```bash
uv run python scripts/orchestrate.py \
  --jira-ticket BUILD-1707 \
  --output-dir ./output/BUILD-1707
```

The dashboard shows each agent's current phase, context window usage, impacted components, and — when a Jira ticket is used — a badge linking directly to the ticket.

---

## 10. Publish Artifacts (optional)

After a pipeline run, `scripts/publish.py` can push the generated artifacts to GitHub or update the Jira ticket.

**Push generated code as a pull request:**

Requires `GITHUB_TOKEN`, `TARGET_GITHUB_REPO`, and `TARGET_GITHUB_BASE_BRANCH` to be set (see [section 4](#4-configure-github)).

```bash
uv run python scripts/publish.py \
  --output-dir ./output/BUILD-1707 \
  --push-code
```

**Update the Jira ticket:**

Requires Jira credentials to be set (see [section 3](#3-configure-jira)).

```bash
uv run python scripts/publish.py \
  --output-dir ./output/BUILD-1707 \
  --push-jira
```

Both flags can be combined:

```bash
uv run python scripts/publish.py \
  --output-dir ./output/BUILD-1707 \
  --push-code \
  --push-jira
```

---

## Complete .env Reference

A minimal working `.env` for live runs:

```bash
# Required — Vertex AI authentication
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=us-east5

# Jira integration
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here

# GitHub integration (optional but recommended)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
TARGET_GITHUB_REPO=openshift-builds/builds
TARGET_GITHUB_BASE_BRANCH=main

# Repository paths (optional but recommended)
SHIPWRIGHT_REPO_PATH=/home/user/git/shipwright-build
OPENSHIFT_BUILDS_REPO_PATH=/home/user/git/openshift-builds

# Model settings
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TOKENS=8000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=text

# Code review
QODO_REVIEW_ENABLED=true
MAX_REVIEW_ITERATIONS=3
QODO_BLOCKING_THRESHOLD=high
```

---

## Next Steps

- [Architecture](../02-concepts/architecture.md) — How the LangGraph pipeline and agent state work
- [Agents Overview](../02-concepts/agents-overview.md) — What each agent does and what it produces
- [Dashboard Overview](../04-dashboard/overview.md) — Dashboard features and session tracking
- [Configuration Reference](configuration.md) — Full list of all environment variables

---

[Next: Configuration →](configuration.md)
