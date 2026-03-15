# Architecture

The multi-agent system is a LangGraph pipeline of four specialized AI agents that process a feature request or bug report end-to-end.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Request                                │
│                    (Issue Title + Description)                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LangGraph Orchestrator                         │
│                      (agents/graph.py)                              │
│                                                                     │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │
│  │   Design    │──>│  Develop    │──>│   Testing   │──> Docs       │
│  │   Agent     │   │   Agent     │   │   Agent     │    Agent      │
│  └─────────────┘   └─────────────┘   └─────────────┘              │
│         │                 │                 │              │        │
│         └─────────────────┴─────────────────┴──────────────┘        │
│                           Heartbeats to Dashboard                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Dashboard Backend                              │
│                    FastAPI + SQLite                                  │
│                   dashboard/backend.py                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph Pipeline

The orchestrator (`agents/graph.py`) builds a `StateGraph` with four sequential nodes. Each node calls its agent, updates the shared `AgentState`, and emits a heartbeat to the dashboard. The `should_continue` router function reads `current_phase` from state to decide which node runs next.

```
design_node → develop_node → testing_node → docs_node → END
```

### Phase Transitions

The `current_phase` field in `AgentState` controls routing:

```
init → design_complete → develop_complete → testing_complete → done
                                                          ↓
                                                        error  (any phase)
```

When an agent raises an unhandled exception, the node sets `current_phase = "error"`, emits an error heartbeat, and the conditional router sends the workflow to `END`.

### Key Orchestrator Function

```python
def orchestrate(title: str, description: str, repo_path: str = None, issue_type: str = "feature") -> Dict[str, Any]:
```

The orchestrator:
1. Generates a UUID session ID
2. Initializes `AgentState` with all fields set to empty defaults
3. Emits an initial heartbeat to register the session in the dashboard
4. Invokes the compiled `StateGraph`
5. Returns the final fully-populated state dictionary

---

## Agents at a Glance

| Agent | File | Input | Output |
|-------|------|-------|--------|
| Design | `agents/design_agent.py` | Issue title, description, optional repo path | Design document, component list, risks, acceptance criteria, implementation plan |
| Development | `agents/go_k8s_developer.py` | Design outputs from state | Go code files, test files, PR description |
| Testing | `agents/testing_agent.py` | Design outputs from state | Ginkgo v2 test suites, test plan, coverage analysis |
| Documentation | `agents/docs_agent.py` | All prior outputs from state | PR summary, release notes, JTBD docs, SHIP document |

---

## Data Flow

Each node returns a partial state dictionary. LangGraph merges it into the accumulated state so every subsequent agent automatically sees all prior outputs.

```
orchestrate() creates initial state
    │
    ▼
Design node adds:
    design_analysis, impacted_components, risks,
    acceptance_criteria, implementation_plan
    current_phase = "design_complete"
    │
    ▼
Development node adds:
    code_files, test_files, code_changes,
    files_modified, pr_description
    current_phase = "develop_complete"
    │
    ▼
Testing node adds:
    test_plan, test_specifications,
    unit_tests, integration_tests, e2e_tests,
    test_summary, coverage_analysis
    current_phase = "testing_complete"
    │
    ▼
Docs node adds:
    pr_summary, release_notes, docs_changes,
    upgrade_notes, known_limitations,
    jtbd_documentation, ship_document, high_level_design
    current_phase = "done"
    │
    ▼
Final state returned to caller
```

---

## Supporting Components

### Dashboard

The dashboard (`dashboard/backend.py`) is an optional FastAPI server with SQLite storage. Agents emit heartbeats via HTTP POST to `/api/heartbeat`. If the dashboard is unreachable, heartbeats fail silently so the workflow is not blocked.

See [Dashboard Overview](../04-dashboard/overview.md).

### Repository Analysis Tools

Optional tools in `tools/` that agents can use when a repository path is provided:

- `tools/repo_search.py` - Code search and Go package analysis
- `tools/rag_search.py` - Documentation search with RAG for the docs agent
- `tools/git_ops.py` - Git operations and repository utilities

### Configuration

- `config/shipwright_components.py` - Shipwright Build component definitions (BuildRun, Build, BuildStrategy, webhooks), CRD types, build strategies, OpenShift integrations
- `config/agent_prompts.py` - System prompts for each agent
- `config/testing_config.py` - Ginkgo v2 test patterns and templates
- `config/mock_responses.py` - Mock API responses for dry run mode

---

## Repository Structure

```text
muilti-agents-ocp-builds/
├── agents/          # Agent implementations + LangGraph graph
├── config/          # Prompts, auth, patterns, mock data
├── dashboard/       # FastAPI backend, enrichers, heartbeat, frontend
├── graph/           # AgentState schema (state.py)
├── mcp/             # MCP server stubs (future integrations)
├── scripts/         # orchestrate.py, run_dashboard.py, test_agents.py
├── tests/           # pytest test suite
├── tools/           # repo_search, rag_search, git_ops
└── utils/           # logging_config.py
```

---

[← Previous: Configuration](../01-getting-started/configuration.md) | [Next: Agents Overview →](agents-overview.md)
