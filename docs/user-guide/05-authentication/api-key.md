# API Key Authentication

> **Note:** The system currently uses Google Vertex AI as its authentication method. This page describes the intended future configuration if direct API key support is added, and also covers third-party API tokens used by MCP integrations.

---

## Current State

The system initializes an `AnthropicVertex` client in `config/auth_config.py`. The `get_anthropic_client()` function checks for `ANTHROPIC_VERTEX_PROJECT_ID` and raises a `ValueError` if it is not set.

If you need to run without a GCP project, use [Dry Run Mode](../06-advanced/dry-run-mode.md) instead.

---

## Using Dry Run as an Alternative

Dry run mode replaces all Claude API calls with pre-configured mock responses. It requires no credentials of any kind.

```bash
# Run the full workflow with mock responses
uv run python scripts/test_agents.py --e2e --dry-run

# Test a single agent with debug output
uv run python scripts/test_agents.py --agent design --dry-run --debug
```

Dry run mode is suitable for:

- Development and local testing
- CI/CD pipelines without GCP credentials
- Understanding the workflow before obtaining credentials
- Isolating logic bugs from API behavior

---

## When Vertex AI Is Not an Option

If your environment cannot use GCP, consider these alternatives:

1. **Dry run mode** - For testing and development
2. **Contribute API key support** - The `config/auth_config.py` module is the right place to add a fallback path that initializes `anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))` when `ANTHROPIC_VERTEX_PROJECT_ID` is not set

The existing validation function in `auth_config.py` already returns an `auth_type` field that could be extended to return `"api_key"` for a direct key path.

---

## Setting Up Vertex AI Instead

For most users, Vertex AI is the recommended path. See [Vertex AI Setup](vertex-ai.md) for complete instructions.

---

## GitHub Personal Access Token

A GitHub token is used by the GitHub MCP server to read and create issues, open pull requests, and interact with the GitHub API on your behalf.

### Token Format

| Token type | Prefix | Recommendation |
| --- | --- | --- |
| Fine-grained PAT | `github_pat_` | Recommended — narrower permissions, newer format |
| Classic PAT | `ghp_` | Not recommended — broad permissions, legacy format |

Always use a fine-grained token when possible. Classic tokens grant access to all repositories in your account and cannot be scoped to specific repos.

### How to Create a Fine-Grained Token

1. Go to **GitHub** → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. Click **Generate new token**
3. Set a token name, expiration date, and the repository scope (select only the repos this system needs)
4. Under **Permissions**, grant:
   - **Repository permissions**: `Contents` (Read), `Issues` (Read and write), `Pull requests` (Read and write)
5. Click **Generate token** and copy the value — it will start with `github_pat_`
6. Add it to your `.env` file:

```bash
GITHUB_TOKEN=github_pat_your_token_here
```

> **Note:** Fine-grained tokens expire. Set a reminder to rotate yours before it lapses.

---

## Jira API Token

Used to authenticate with the Jira REST API when passing `--jira-ticket` to the orchestrator.

### How to Create a Jira API Token

1. Go to your Atlassian Cloud account's Security tab:
   [https://id.atlassian.com/manage-profile/security](https://id.atlassian.com/manage-profile/security)
   > **Note:** You need VPN access to reach this URL
2. Follow the prompts on that screen to generate your token
3. Copy the token and add it to your `.env` file:

```bash
JIRA_API_TOKEN=your-generated-token
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
```

See [Jira & Rovo Integration](../09-integrations/jira-rovo.md) for full setup and usage.

---

[← Previous: Vertex AI](vertex-ai.md) | [Next: Dry Run Mode →](../06-advanced/dry-run-mode.md)
