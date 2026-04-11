# Jira & Rovo Integration

Feed a Jira ticket directly into the agent pipeline. Instead of writing `--title` and `--description` by hand, pass a ticket ID and the system fetches the title, description, acceptance criteria, priority, labels, linked issues, and recent comments automatically — then makes all of that context available to every agent.

---

## Prerequisites

Before using this integration, confirm you have:

- The system installed and working (see [Installation](../01-getting-started/installation.md))
- VPN access to reach your internal Jira instance
- A Jira API token (see [Jira API Token](../05-authentication/authentication.md#jira-api-token))

The three required environment variables are:

| Variable | Purpose |
|----------|---------|
| `JIRA_BASE_URL` | Your Atlassian Cloud base URL |
| `JIRA_USER_EMAIL` | The email address tied to your API token |
| `JIRA_API_TOKEN` | Your Atlassian API token |

A `GITHUB_TOKEN` is optional but recommended if your Jira tickets link to GitHub pull requests — see [GitHub PR Integration](#github-pr-integration) below.

---

## Configuration

Add the following to your `.env` file in the project root:

```bash
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

Replace each value with your actual credentials. `JIRA_BASE_URL` must match your organization's Atlassian Cloud subdomain exactly — no trailing slash.

> **VPN required:** The Jira REST API endpoint is not reachable from outside the corporate network. If you are working off-VPN, use `--dry-run` mode instead (see below).

---

## Usage

### Basic usage

Pass `--jira-ticket` with a Jira ticket key in place of `--title` and `--description`:

```bash
uv run python scripts/orchestrate.py --jira-ticket SHIP-123
```

The orchestrator fetches the ticket data, builds the agent context, and runs the full five-phase pipeline.

### With manual approval

Pause after each phase to review and approve before continuing:

```bash
uv run python scripts/orchestrate.py --jira-ticket SHIP-456 --manual-approval
```

### Test without VPN (dry-run)

Use `--dry-run` to run without credentials or VPN. The system returns a pre-configured mock SHIP-123 ticket (a BuildRun timeout feature) and runs the full pipeline against it:

```bash
uv run python scripts/orchestrate.py --jira-ticket SHIP-123 --dry-run
```

---

## What Gets Fetched

The integration reads the following fields from the Jira REST API v3 and passes them as structured context to the agent pipeline:

| Field | Source | Used by |
|-------|--------|---------|
| Title | Jira — Summary | All agents |
| Description | Jira — Description (ADF converted to plain text) | Design agent |
| Acceptance Criteria | Jira — Custom AC field or AC section in description | Design, Testing agents |
| Priority | Jira — Priority field | Design agent |
| Labels | Jira — Labels | All agents |
| Linked Issues | Jira — Issue links | Design agent |
| Recent Comments | Jira — Last 5 comments (summarized) | Design agent |
| GitHub PR URLs | Remote links API (`/remotelink` endpoint) | Docs agent |
| GitHub PR Data | GitHub REST API v3 (via `GITHUB_TOKEN`) | Docs agent |

The acceptance criteria are extracted from the Jira custom field if present, or parsed from an "Acceptance Criteria" section in the description body if not. This allows the Testing agent to generate test cases directly from the ticket requirements without any manual copy-paste.

---

## Jira Badge in the Dashboard

When a workflow is started with `--jira-ticket`, a blue **Jira** badge appears on the session card in the dashboard. Clicking the badge opens the Jira ticket directly in a new browser tab.

Start the dashboard before running the orchestrator:

```bash
# Terminal 1
uv run python scripts/run_dashboard.py

# Terminal 2
uv run python scripts/orchestrate.py --jira-ticket SHIP-123
```

Open http://localhost:8080 and locate the session card. The badge is visible alongside the session ID and phase status.

---

## Dry-Run Mode

Dry-run mode is the recommended way to develop, test the integration, or run in environments without VPN access.

```bash
uv run python scripts/orchestrate.py --jira-ticket SHIP-123 --dry-run
```

When `--dry-run` is active:

- No HTTP request is made to Jira
- The mock stub in `mcp/jira_stub.py` returns a fixed SHIP-123 response describing a BuildRun timeout feature
- The `--jira-ticket` value is accepted and echoed in session metadata, but is not validated against a live Jira instance
- No credentials (`JIRA_BASE_URL`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`) are required

This is equivalent to passing a fixed `--title` and `--description` while still exercising the full Jira code path.

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `Cannot reach Jira. Are you connected to VPN?` | The `JIRA_BASE_URL` host is unreachable | Connect to VPN, or add `--dry-run` |
| `Jira ticket 'X' not found` | The ticket key does not exist in the project | Check the ticket key and project prefix |
| `Jira authentication failed (HTTP 401/403)` | Bad email or API token | Verify `JIRA_USER_EMAIL` and `JIRA_API_TOKEN` in `.env` |
| `JIRA_BASE_URL is not set` | Missing environment variable | Add all three variables to `.env` |

If you receive an authentication error after confirming credentials, regenerate the API token at [https://id.atlassian.com/manage-profile/security](https://id.atlassian.com/manage-profile/security) and update `.env`.

---

## GitHub PR Integration

When a Jira ticket has remote links pointing to GitHub pull requests, the docs agent automatically fetches full PR metadata and includes it in the documentation context. This gives the docs agent access to the actual code changes, review decisions, and merge status — without any manual input.

### How It Works

The pipeline follows four steps to enrich the docs agent with GitHub PR data:

1. **Remote links fetch** — After fetching the Jira ticket, the integration calls `GET /rest/api/3/issue/{id}/remotelink` via the `_fetch_remotelinks()` method. This returns all external URLs attached to the ticket.
2. **PR URL extraction** — From those remote links, any URL containing both `github.com` and `/pull/` is identified as a GitHub pull request URL.
3. **GitHub API fetch** — Each PR URL is resolved against the GitHub REST API v3 via `tools/github_client.py`, which retrieves full PR metadata.
4. **Docs agent context** — The collected PR data is assembled into an "Upstream GitHub Pull Requests" context section and passed to the docs agent alongside the Jira fields.

### What PR Metadata Is Fetched

`tools/github_client.py` retrieves the following for each linked pull request:

| Field | Description |
|-------|-------------|
| Title | PR title |
| Body | PR description, capped at 2000 characters to manage token usage |
| Author | GitHub username of the PR author |
| Reviewers | List of requested reviewers and review participants |
| State | `merged`, `open`, or `closed` |
| Labels | Labels applied to the PR |
| Base branch | The branch the PR targets |
| Head branch | The branch the PR was opened from |
| Files changed | List of changed files with `+additions` / `-deletions` counts |
| Created at | Timestamp when the PR was opened |
| Merged at | Timestamp when the PR was merged (if applicable) |

The PR body cap (2000 characters) prevents large PR descriptions from consuming a disproportionate share of the context window. The remaining fields are always included in full.

### Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Optional (but recommended) | Personal access token — without it, PR URLs are shown but metadata is not fetched |
| `GITHUB_REQUEST_TIMEOUT` | Optional | Timeout in seconds for GitHub API calls (default: `10`) |

Without a `GITHUB_TOKEN`, the remote link URLs are still extracted from Jira and logged, but no GitHub API call is made and no PR metadata is added to the docs agent context.

**To create a token:** GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens

Required scope: `Contents` (read-only) on the target repositories.

### Dry-Run Behavior

When `--dry-run` is used, no real GitHub API calls are made. Instead, mock PR data is returned from `config/mock_responses.py` (`MOCK_GITHUB_PR`). The mock response follows the same structure as a live response, so the docs agent processes it identically. This lets you test the full pipeline — including the "Upstream GitHub Pull Requests" context section — without a `GITHUB_TOKEN` or network access.

---

## Atlassian Rovo (Phase 3 - Planned)

> **Status: PLANNED.** Phase 1 (Jira REST API via `--jira-ticket`) is active today. Rovo MCP support is planned for a future phase.

### What Rovo Is

Atlassian Rovo is Atlassian's AI work intelligence platform. It provides AI-powered search and query capabilities across Jira, Confluence, and connected tools — surfacing relevant issues, pages, and decisions in context.

### The Atlassian Rovo MCP Server

Atlassian publishes a standard Model Context Protocol (MCP) server at:

```
https://mcp.atlassian.com/v1/mcp
```

This allows external AI tools to query Rovo via the standard MCP protocol. It is not a Forge application — no Forge development or plugin deployment is required. Authentication uses an Atlassian API token, the same token you already configured for Jira.

### What Rovo MCP Would Enable

When this phase is implemented, the agent pipeline will gain access to:

- Confluence page search (find design docs, runbooks, and architecture pages related to the ticket)
- Related Jira ticket recommendations (surface tickets with similar components or labels)
- Rovo AI queries (ask Rovo questions about your Atlassian workspace in natural language)
- Richer ticket metadata not available through the v3 REST API

### How It Will Be Configured

The Rovo MCP server will be added to Claude Code's MCP settings — no changes to this project's Python code are required. A configuration block similar to the following will be added to Claude Code settings:

```json
{
  "mcpServers": {
    "atlassian": {
      "url": "https://mcp.atlassian.com/v1/mcp",
      "headers": {
        "Authorization": "Bearer your-atlassian-api-token"
      }
    }
  }
}
```

Documentation for this phase will be updated here once the feature is available.

---

[← Previous: Testing Guide](../08-testing/README.md) | [Back to Index →](../README.md)
