# Architecture

The multi-agent system is a LangGraph pipeline of five specialized AI agents that process a feature request or bug report end-to-end.

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
│  ┌──────────┐  ┌──────────┐  ┌─────────────┐  ┌──────────┐  ┌──────┐  │
│  │  Design  │─>│  Develop │─>│ Code Review │─>│ Testing  │─>│ Docs │  │
│  │  Agent   │  │  Agent   │  │   Agent     │  │  Agent   │  │Agent │  │
│  └──────────┘  └──────────┘  └─────────────┘  └──────────┘  └──────┘  │
│                     ↑              │ (fail: blocking issues found)      │
│                     └──────────────┘ auto-fix loop (≤ MAX_REVIEW_ITER) │
│         └───────────────────────────────────────────────────────┘      │
│                           Heartbeats to Dashboard                       │
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

The orchestrator (`agents/graph.py`) builds a `StateGraph` with five sequential nodes. Each node calls its agent, updates the shared `AgentState`, and emits a heartbeat to the dashboard. The `should_continue` router function reads `current_phase` from state to decide which node runs next.

```
design_node → develop_node → code_review_node → testing_node → docs_node → END
                                  ↑         │ (fail + iter ≤ max)
                                  └─────────┘ (auto-fix loop)
```

### Phase Transitions

The `current_phase` field in `AgentState` controls routing:

```
init → design_complete → develop_complete → review_complete → testing_complete → done
                                                  ↑       │
                                                  └───────┘  (auto-fix loop when
                                                              review_passed=False and
                                                              review_iteration ≤ MAX_REVIEW_ITERATIONS)
                                            ↓ (any phase)
                                          error
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
| Code Review | `agents/code_review_agent.py` | Generated code files from state | Review verdict, findings list, review summary |
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
Code Review node adds:
    review_passed         (bool: True if no blocking issues)
    review_findings       (list[str]: "[BLOCKING] SECURITY: ...")
    review_summary        (str: "2 findings | 1 blocking | FAIL")
    review_iteration      (int: increments each review cycle)
    current_phase = "review_complete"
    → if review_passed=False and iteration ≤ max: loops back to Development
    → if review_passed=True or iteration > max: continues to Testing
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

## Output Validation Gates

After each agent completes, its outputs are validated before the next phase begins.
This prevents silent cascading failures where an agent returns empty data and
subsequent agents produce garbage outputs.

**Validation flow:**

```text
Agent completes
     ↓
validate_phase(phase, state)
     ↓
  ┌──┴──┐
PASS    FAIL
  ↓      ↓
Next   Stop workflow with
Phase  clear error message
```

**Validation rules per phase:**

| Phase | Blocks on (required) | Warns on (optional) |
|-------|---------------------|---------------------|
| Design | Empty `design_analysis`, empty `implementation_plan` | No risks, components, or criteria |
| Development | Empty `code_files` | Short `pr_description` |
| Code Review | (never blocks — loop handles retries) | Review failures surfaced as warnings |
| Testing | Empty `test_plan` | No unit/integration tests |
| Documentation | Empty `pr_summary` | No `release_notes` |

Validation logic lives in `agents/validators.py`. Each phase has its own validator
that returns a `ValidationResult` with `passed`, `issues` (blocking), `warnings`
(non-blocking), and a `summary` dict of key metrics.

```python
from agents.validators import validate_phase

result = validate_phase("design", state)
# result.passed   → bool
# result.issues   → list[str]  (blocking - stops workflow)
# result.warnings → list[str]  (non-blocking - printed as warning)
# result.summary  → dict       (key metrics, e.g. "Code files generated: 3")
```

**Extending validation:** To add a validator for a new agent phase, add a
`validate_<phase>_output(state)` function in `agents/validators.py` and register
it in the `VALIDATORS` dict. The orchestrator picks it up automatically via
`validate_phase()`.

→ See [Output Validation & Manual Approval](../06-advanced/output-validation.md)
for the full reference, including `ValidationResult` fields, per-phase threshold
configuration, and manual approval mode.

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

### Agent Prompts (`config/agent_prompts.py`)

Each agent has a dedicated system prompt stored as a `Final[str]` constant in `config/agent_prompts.py`. The prompt defines the agent's role, responsibilities, output format, and guardrails.

| Constant | Used by | Purpose |
| -------- | ------- | ------- |
| `DESIGN_AGENT_PROMPT` | `agents/design_agent.py` | Instructs the agent to produce design documents: problem statement, scope, impacted components, risks, acceptance criteria, implementation plan |
| `DEVELOPMENT_AGENT_PROMPT` | `agents/go_k8s_developer.py` | Instructs the agent to generate idiomatic Go code, table-driven tests, and a PR description ending with "Generated by AI" |
| `CODE_REVIEW_AGENT_PROMPT` | `agents/code_review_agent.py` | Instructs Claude to review generated Go code using machine-parseable `[BLOCKING]`/`[WARNING]`/`[SUGGESTION]` format, ending with `VERDICT: PASS` or `VERDICT: FAIL` |
| `TESTING_AGENT_PROMPT` | `agents/testing_agent.py` | Instructs the agent to generate Ginkgo v2 test suites with DDT patterns, Gomega assertions, and Shipwright test helpers |
| `DOCS_AGENT_PROMPT` | `agents/docs_agent.py` | Instructs the agent to produce PR summaries, release notes, JTBD documentation, SHIP documents, and high-level design documents |

**How agents load their prompt:**

Each agent imports its constant at the top of the module and passes it as the `system` parameter of the Claude API call:

```python
from config.agent_prompts import DESIGN_AGENT_PROMPT

response = client.messages.create(
    model=model,
    system=DESIGN_AGENT_PROMPT,
    messages=[{"role": "user", "content": user_prompt}],
)
```

**Customizing prompts:**

To adjust agent behavior, edit the relevant constant in `config/agent_prompts.py`. Common reasons to customize:

- Change the output format (e.g., switch from Markdown to JSON)
- Add project-specific guardrails (e.g., enforce a naming convention)
- Adjust the level of detail in generated output
- Add or remove sections from the design/docs template

Changes take effect immediately on the next run — no code changes required.

---

## Repository Structure

```text
muilti-agents-ocp-builds/
├── agents/          # Agent implementations, LangGraph graph, output validators
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
