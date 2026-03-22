# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent AI system that automates design analysis and documentation generation for OpenShift/Shipwright Build projects. Uses Claude AI agents orchestrated by LangGraph in a sequential pipeline: Design → Development → Testing → Documentation.

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
uv run pytest tests/ --cov=agents --cov=graph --cov-report=html

# Manual agent testing with dry-run (no API calls)
uv run python scripts/test_agents.py --e2e --dry-run --debug

# Test a specific agent
uv run python scripts/test_agents.py --agent design --dry-run
```

## Architecture

### LangGraph Workflow Pipeline (`agents/graph.py`)

The orchestrator builds a `StateGraph` with four sequential nodes connected by conditional edges. Each node calls its agent, updates shared state, and emits a heartbeat to the dashboard. The `should_continue` function routes based on `current_phase` in state (e.g., `design_complete` → `develop`, `develop_complete` → `testing`). On error, the workflow terminates early via the `END` edge.

```
design_node → develop_node → code_review_node → testing_node → docs_node → END
                                  ↑         │ (fail + iter ≤ max)
                                  └─────────┘ (auto-fix loop)
```

### Shared State (`graph/state.py`)

`AgentState` is a `TypedDict(total=False)` containing all fields shared across agents — inputs (issue title/description/type), outputs from each phase (design analysis, code files, test plans, PR summaries), control flow (session_id, current_phase, approval_status), and LangGraph messages with `add_messages` annotation.

### Agent Pattern

All five agents follow the same pattern:
1. Validate context/inputs
2. Get Claude client via `config/auth_config.get_anthropic_client()`
3. Build a prompt using system prompt from `config/agent_prompts.py` + user context
4. Call `client.messages.create()` with the configured model (`CLAUDE_MODEL` env var, default `claude-sonnet-4-20250514`)
5. Parse the Markdown-structured response into typed dict outputs
6. Emit heartbeat to dashboard

| Agent | Entry Point | Key Input | Key Output |
|-------|------------|-----------|------------|
| Design | `agents/design_agent.run_design()` | title, description, repo_path | design_analysis, impacted_components, risks, acceptance_criteria |
| Development | `agents/go_k8s_developer.run_development()` | AgentState dict (needs implementation_plan as list) | code_files, test_files, pr_description |
| Code Review | `agents/code_review_agent.run_code_review()` | AgentState dict (code_files from development) | review_passed, review_findings, review_summary, review_iteration |
| Testing | `agents/testing_agent.run_testing()` | context dict (needs design_analysis, impacted_components, acceptance_criteria) | test_plan, unit/integration/e2e_tests, coverage_analysis |
| Docs | `agents/docs_agent.run_docs()` | context dict + optional input_files, output_format, enable_rag | pr_summary, release_notes, docs_changes |

### Authentication (`config/auth_config.py`)

Uses Google Vertex AI (`ANTHROPIC_VERTEX_PROJECT_ID`) for authentication. All agents use `get_anthropic_client()` which returns an `AnthropicVertex` client.

### Dashboard (`dashboard/`)

FastAPI backend (`backend.py`) with SQLite storage at `/tmp/claude/dashboard.db`. Agents emit heartbeats via HTTP POST to `localhost:8080/api/heartbeat` using the `emit_heartbeat()` convenience function from `dashboard/heartbeat.py`. The `enrichers.py` module enriches raw heartbeat data before storage. Frontend is a single `dashboard/frontend/index.html`.

### Domain Configuration (`config/`)

- `shipwright_components.py`: Shipwright Build component definitions (BuildRun, Build, BuildStrategy, webhooks), CRD types, build strategies, OpenShift integrations
- `agent_prompts.py`: System prompts for each agent
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
| `CLAUDE_MODEL` | Model override (default: `claude-sonnet-4-20250514`) |
| `CLAUDE_MAX_TOKENS` | Max tokens override |
| `SHIPWRIGHT_REPO_PATH` / `OPENSHIFT_BUILDS_REPO_PATH` | Repo paths for code analysis |
| `DASHBOARD_URL` | Dashboard URL (default: `http://localhost:8080`) |
| `DASHBOARD_ENABLED` | Enable heartbeats (default: `true`) |
| `DASHBOARD_DB_PATH` | SQLite DB path (default: `/tmp/claude/dashboard.db`) |
