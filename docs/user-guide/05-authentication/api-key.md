# API Key Authentication

> **Note:** The system currently uses Google Vertex AI as its authentication method. Direct Anthropic API key authentication is not yet implemented in the codebase. This page describes the intended future configuration if direct API key support is added.

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

[← Previous: Vertex AI](vertex-ai.md) | [Next: Dry Run Mode →](../06-advanced/dry-run-mode.md)
