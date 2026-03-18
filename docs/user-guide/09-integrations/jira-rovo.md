# Jira & Rovo Integration

Feed a Jira ticket directly into the agent pipeline. Instead of writing `--title` and `--description` by hand, pass a ticket ID and the system fetches the title, description, acceptance criteria, priority, labels, linked issues, and recent comments automatically — then makes all of that context available to every agent.

---

## Prerequisites

Before using this integration, confirm you have:

- The system installed and working (see [Installation](../01-getting-started/installation.md))
- VPN access to reach your internal Jira instance
- A Jira API token (see [Jira API Token](../05-authentication/api-key.md#jira-api-token))

The three required environment variables are:

| Variable | Purpose |
|----------|---------|
| `JIRA_BASE_URL` | Your Atlassian Cloud base URL |
| `JIRA_USER_EMAIL` | The email address tied to your API token |
| `JIRA_API_TOKEN` | Your Atlassian API token |

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

The orchestrator fetches the ticket data, builds the agent context, and runs the full four-phase pipeline.

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

| Field | Jira Source | Used by |
|-------|-------------|---------|
| Title | Summary | All agents |
| Description | Description (ADF converted to plain text) | Design agent |
| Acceptance Criteria | Custom AC field or AC section in description | Design, Testing agents |
| Priority | Priority field | Design agent |
| Labels | Labels | All agents |
| Linked Issues | Issue links | Design agent |
| Recent Comments | Last 5 comments (summarized) | Design agent |

The acceptance criteria are extracted from the Jira custom field if present, or parsed from an "Acceptance Criteria" section in the description body if not. This allows the Testing agent to generate test cases directly from the ticket requirements without any manual copy-paste.

---

## Jira Badge in the Dashboard

When a workflow is started with `--jira-ticket`, a blue **Jira** badge appears on the session card in the dashboard. Clicking the badge opens the Jira ticket directly in a new browser tab.

Start the dashboard before running the orchestrator:

```bash
# Terminal 1
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py

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
