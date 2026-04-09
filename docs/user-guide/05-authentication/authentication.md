# Authentication

The system supports two authentication methods for Claude API access: Google Vertex AI (recommended for production) and direct API key access via dry run or a contributed code path. All five agents obtain their Claude client through `config/auth_config.get_anthropic_client()`.

---

## Overview

At startup, `config/auth_config.py` reads the `ANTHROPIC_VERTEX_PROJECT_ID` environment variable. If it is set, the system initializes an `AnthropicVertex` client using Application Default Credentials (ADC). If it is not set, the system raises a `ValueError` immediately.

```python
from config.auth_config import validate_authentication

auth_info = validate_authentication()
print(f"Auth type: {auth_info['auth_type']}")
# Returns: "vertex" or "none"
```

Or run the bundled example:

```bash
uv run python examples/auth_example.py
```

The client is shared across all pipeline phases:

```
User Request (issue title + description)
    │
    ▼
Workflow Orchestrator (orchestrator/workflow.py)
    │ Reads ANTHROPIC_VERTEX_PROJECT_ID
    │ Calls get_anthropic_client()
    ▼
Design Agent ──→ AnthropicVertex client ──→ Claude API (via Vertex AI endpoint)
    │
Development Agent ──→ same client
    │
Code Review Agent ──→ same client
    │
Testing Agent ──→ same client
    │
Docs Agent ──→ same client
```

---

## Method 1: Google Vertex AI (Recommended)

Google Vertex AI uses Application Default Credentials (ADC) managed by the Google Cloud CLI. No API key is stored or transmitted. GCP IAM controls access, and token refresh is handled automatically.

### When to Use Vertex AI

- Production environments with GCP access
- Teams that want GCP IAM to control Claude API access
- Organizations that already use Google Cloud services
- When you prefer credential rotation through GCP rather than managing an API key

### Setup Steps

#### Step 1: Install the Google Cloud CLI

Follow the official guide: https://cloud.google.com/sdk/docs/install

Verify installation:

```bash
gcloud --version
```

#### Step 2: Authenticate Your Account

```bash
gcloud auth application-default login
```

This opens a browser window for Google account sign-in. Your credentials are cached locally at `~/.config/gcloud/application_default_credentials.json`.

#### Step 3: Set the Billing Project

```bash
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
```

Find your project ID if you do not have it:

```bash
gcloud projects list
```

#### Step 4: Enable the Vertex AI API

```bash
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

#### Step 5: Grant IAM Permissions

Your account needs the `roles/aiplatform.user` role:

```bash
gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

> **Note:** If using a service account instead of a user account, replace `user:` with `serviceAccount:` in the command above.

#### Step 6: Set the Environment Variable

In your `.env` file:

```bash
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=us-east5   # Optional, defaults to us-east5
```

### Available Regions

| Region | Notes |
|--------|-------|
| `us-east5` | Default, recommended |
| `us-central1` | US central |
| `europe-west1` | EU west |
| `asia-southeast1` | Asia Pacific |

Set the region in `.env` if the default `us-east5` is not available in your GCP project:

```bash
CLOUD_ML_REGION=us-central1
```

### How ADC Works in the System

1. The system reads `ANTHROPIC_VERTEX_PROJECT_ID` from environment variables
2. `config/auth_config.get_anthropic_client()` creates an `AnthropicVertex` client
3. The client uses the ADC token cached by `gcloud auth application-default login`
4. All Claude API requests route through the Vertex AI endpoint in the configured region
5. GCP manages token refresh automatically — no manual rotation needed

### Verify Your Setup

Check that credentials are active:

```bash
gcloud auth application-default print-access-token
gcloud auth application-default describe
```

Run the bundled auth example:

```bash
uv run python examples/auth_example.py
```

### Credential Rotation

ADC tokens expire automatically and are refreshed by the Google Cloud CLI. For long-running environments, re-run the login command periodically:

```bash
gcloud auth application-default login
```

For service accounts in CI/CD environments, use Workload Identity Federation or a service account key file rather than interactive ADC.

### Troubleshooting

#### Token expired

```bash
gcloud auth application-default login
```

#### Wrong project

```bash
gcloud auth application-default set-quota-project CORRECT_PROJECT_ID
```

#### API quota exceeded

Check your quota in the GCP console under Vertex AI > Quotas. You may need to request a quota increase for Claude model requests.

#### "gcloud not authenticated" or ADC errors

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
gcloud auth application-default print-access-token  # Verify it works
```

#### "Vertex AI API not enabled"

```bash
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

#### "Permission denied" on Vertex AI

```bash
gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

---

## Method 2: Direct API Key

The system does not currently ship a direct `ANTHROPIC_API_KEY` path. `config/auth_config.py` raises a `ValueError` when `ANTHROPIC_VERTEX_PROJECT_ID` is not set rather than falling back to a key.

If you need to run without GCP credentials, use one of these approaches:

### Dry Run Mode (No Credentials Required)

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

See [Dry Run Mode](../06-advanced/dry-run-mode.md) for full details.

### Contributing API Key Support

If your environment cannot use GCP at all, `config/auth_config.py` is the right place to add a fallback path. The pattern would be to initialize `anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))` when `ANTHROPIC_VERTEX_PROJECT_ID` is not set. The existing `validate_authentication()` function already returns an `auth_type` field that could be extended to return `"api_key"` for a direct key path.

---

## Additional Tokens

### GitHub Personal Access Token

A GitHub token is used by the GitHub MCP server to read and create issues, open pull requests, and interact with the GitHub API on your behalf.

#### Token Format

| Token type | Prefix | Recommendation |
| --- | --- | --- |
| Fine-grained PAT | `github_pat_` | Recommended — narrower permissions, newer format |
| Classic PAT | `ghp_` | Not recommended — broad permissions, legacy format |

Always use a fine-grained token when possible. Classic tokens grant access to all repositories in your account and cannot be scoped to specific repos.

#### How to Create a Fine-Grained Token

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

### Jira API Token

Used to authenticate with the Jira REST API when passing `--jira-ticket` to the orchestrator.

#### How to Create a Jira API Token

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

## Choosing a Method

| Criteria | Vertex AI | Dry Run / API Key |
|----------|-----------|-------------------|
| GCP project available | Yes | No |
| Production workloads | Yes | No |
| IAM-controlled access | Yes | No |
| No credentials needed | No | Yes (dry run) |
| CI/CD without GCP | No | Yes (dry run) |
| Real Claude responses | Yes | No (dry run) |

For most users, Vertex AI is the recommended path. Use dry run mode for local development and testing when GCP credentials are unavailable. If you need live Claude responses without GCP, consider contributing direct API key support to `config/auth_config.py`.

---

[← Previous: Session Management](../04-dashboard/session-management.md) | [Next: Dry Run Mode →](../06-advanced/dry-run-mode.md)
