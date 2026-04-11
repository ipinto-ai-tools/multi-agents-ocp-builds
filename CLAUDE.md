# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SDLC orchestration layer that automates the full feature development lifecycle for OpenShift/Shipwright Build projects. Uses Claude as the execution engine for stage-based workflows: Design → Development → Code Review → Testing → Documentation.

## Commands

```bash
# Install dependencies
uv venv && uv pip install -r requirements.txt

# Run the orchestration workflow
uv run python scripts/orchestrate.py --title "Feature title" --description "Description"

# Start the real-time monitoring dashboard (port 8080)
uv run python scripts/run_dashboard.py

# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_agents_validator_design.py -v

# Run tests with coverage
uv run pytest tests/ --cov=stages --cov=orchestrator --cov-report=html

# Manual agent testing with dry-run (no API calls)
uv run python scripts/test_agents.py --e2e --dry-run --debug

# Test a specific agent
uv run python scripts/test_agents.py --agent design --dry-run
```

## Architecture

### Workflow Orchestrator (`orchestrator/workflow.py`)

The orchestrator runs stages sequentially. Each stage function is called, its output merged into shared state, and validation runs before proceeding. The review gate runs as part of the develop-with-review loop.

```
Design → Development → Code Review (gate) → Testing → Docs
                           ↑         │ (fail + iter ≤ max)
                           └─────────┘ (auto-fix loop)
```

### Shared State (`models/workflow_state.py`)

`WorkflowState` is a `TypedDict(total=False)` containing all fields shared across stages — inputs (issue title/description/type), outputs from each phase (design analysis, code files, test plans, PR summaries), and control flow (session_id, current_phase, approval_status).

### Stage Pattern

All five stage runners follow the same pattern:
1. Validate context/inputs
2. Get Claude client via `config/auth_config.get_anthropic_client()`
3. Build a prompt using system prompt from `prompts/` package + user context
4. Call `client.messages.create()` with the configured model (`CLAUDE_MODEL` env var, default `claude-sonnet-4-6`)
5. Parse the Markdown-structured response into typed dict outputs
6. Emit heartbeat to dashboard

| Stage | Entry Point | Key Input | Key Output |
|-------|------------|-----------|------------|
| Design | `stages/design.run_design()` | title, description, repo_path | design_analysis, impacted_components, risks, acceptance_criteria |
| Development | `stages/develop.run_development()` | WorkflowState dict (needs implementation_plan as list) | code_files, test_files, pr_description |
| Code Review | `stages/code_review.run_code_review()` | WorkflowState dict (code_files from development) | review_passed, review_findings, review_summary, review_iteration |
| Testing | `stages/test.run_testing()` | context dict (needs design_analysis, impacted_components, acceptance_criteria) | test_plan, unit/integration/e2e_tests, coverage_analysis |
| Docs | `stages/docs.run_docs()` | context dict + optional input_files, output_format, enable_rag | pr_summary, release_notes, docs_changes |

### Authentication (`config/auth_config.py`)

Uses Google Vertex AI (`ANTHROPIC_VERTEX_PROJECT_ID`) for authentication. All stage runners use `get_anthropic_client()` which returns an `AnthropicVertex` client.

### Dashboard (`dashboard/`)

FastAPI backend (`backend.py`) with SQLite storage at `/tmp/claude/dashboard.db`. Stage runners emit heartbeats via HTTP POST to `localhost:8080/api/heartbeat` using the `emit_heartbeat()` convenience function from `dashboard/heartbeat.py`. The `enrichers.py` module enriches raw heartbeat data before storage. Frontend is a single `dashboard/frontend/index.html`.

### Domain Configuration (`config/`)

- `shipwright_components.py`: Shipwright Build component definitions (BuildRun, Build, BuildStrategy, webhooks), CRD types, build strategies, OpenShift integrations
- `prompts/`: System prompts for each stage runner (split into per-stage modules)
- `testing_config.py`: Ginkgo v2 test patterns and templates, pattern detection for build strategies/source types
- `mock_responses.py`: Mock API responses for dry-run mode

### Repository Analysis Tools (`tools/`)

- `repo_search.py`: Code search and Go package analysis for Shipwright repos
- `rag_search.py`: Documentation search with RAG for the docs agent
- `git_ops.py`: Git operations and utilities

## Testing

Tests are in `tests/` and use pytest. The `conftest.py` provides shared fixtures (`sample_issue_data`, `sample_design_output`, `sample_docs_context`, etc.). Tests marked with `@pytest.mark.real_api` are auto-skipped when `ANTHROPIC_VERTEX_PROJECT_ID` is not configured (with google-auth installed). Auth checking logic lives in `tests/auth_helper.py`. Custom markers: `real_api`, `integration`, `slow`.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project ID for Vertex AI auth |
| `CLOUD_ML_REGION` | GCP region (default: `us-east5`) |
| `CLAUDE_MODEL` | Model override (default: `claude-sonnet-4-6`) |
| `CLAUDE_MAX_TOKENS` | Max tokens override |
| `SHIPWRIGHT_REPO_PATH` | Primary repo path for code analysis (used by Design, Development, and Docs agents) |
| `OPENSHIFT_BUILDS_REPO_PATH` | Secondary repo path, merged with primary for additional context |
| `ENABLE_REPO_ANALYSIS` | Enable/disable repo analysis (default: `true`). Set to `false` to skip repo scanning. |
| `DASHBOARD_URL` | Dashboard URL (default: `http://localhost:8080`) |
| `DASHBOARD_ENABLED` | Enable heartbeats (default: `true`) |
| `DASHBOARD_DB_PATH` | SQLite DB path (default: `~/.local/share/flowpilot/dashboard.db`) |
| `PII_REDACTION_ENABLED` | Redact PII from Jira/GitHub data at fetch time (default: `true`). Set to `false` for local dev only. |
| `PROMPT_GUARD_ENABLED` | Sanitize external text for prompt injection patterns before prompt assembly (default: `true`). Set to `false` for local dev only. |
| `OUTPUT_SANITIZER_ENABLED` | Enable/disable output sanitizer (default: `true`) |
