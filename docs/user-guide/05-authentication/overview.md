# Authentication Overview

The system uses Google Vertex AI to authenticate with the Claude API. Authentication is handled through Application Default Credentials (ADC) managed by the Google Cloud CLI. No API keys are stored or transmitted.

---

## How Authentication Works

At startup, `config/auth_config.py` reads the `ANTHROPIC_VERTEX_PROJECT_ID` environment variable. If it is set, the system initializes an `AnthropicVertex` client using ADC. If it is not set, the system raises a `ValueError` immediately.

All four agents obtain their Claude client through `config/auth_config.get_anthropic_client()`, which returns the same configured `AnthropicVertex` instance.

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

---

## Authentication Method

| Method | Variable Required | Setup |
|--------|------------------|-------|
| Google Vertex AI | `ANTHROPIC_VERTEX_PROJECT_ID` | `gcloud auth application-default login` |

The system currently supports only Vertex AI. If you need to use a direct Anthropic API key, see [API Key](api-key.md).

---

## System Flow with Authentication

```
User Request (issue title + description)
    │
    ▼
LangGraph Orchestrator (agents/graph.py)
    │ Reads ANTHROPIC_VERTEX_PROJECT_ID
    │ Calls get_anthropic_client()
    ▼
Design Agent ──→ AnthropicVertex client ──→ Claude API (via Vertex AI endpoint)
    │
Development Agent ──→ same client
    │
Testing Agent ──→ same client
    │
Docs Agent ──→ same client
```

---

## No Authentication: Dry Run Mode

If you do not have Google Cloud credentials, use dry run mode. All Claude API calls are replaced with pre-configured mock responses.

```bash
uv run python scripts/test_agents.py --e2e --dry-run
```

See [Dry Run Mode](../06-advanced/dry-run-mode.md) for full details.

---

## Troubleshooting Authentication Errors

### "No Claude authentication configured"

```bash
# Set the project ID and authenticate
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
gcloud auth application-default login
gcloud auth application-default set-quota-project your-gcp-project-id
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

[← Previous: Session Management](../04-dashboard/session-management.md) | [Next: Vertex AI Setup →](vertex-ai.md)
