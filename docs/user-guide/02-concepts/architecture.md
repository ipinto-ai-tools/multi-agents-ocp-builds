# Architecture

## Feature SDLC Pipeline

FlowPilot is an SDLC orchestration layer that drives a feature from Jira ticket or issue description through to deployable artifacts — without manual handoffs between stages. Claude serves as the execution engine for every stage; FlowPilot supervises the workflow, validates outputs, and manages state transitions.

Each run of `scripts/orchestrate.py` executes a fixed sequence of SDLC stages:

```
Requirements → Design → Development → Code Review → Testing → Documentation → Publish
```

The first stage (Requirements) is provided by the caller as an issue title and description. The remaining stages are carried out by stage runners — each powered by Claude — coordinated by the workflow orchestrator (currently implemented using LangGraph). The final Publish step writes artifacts to disk via `publish.py`.

### SDLC Stage Overview

| Phase | SDLC Stage | Stage Runner | Duration (typical) |
| ----- | ---------- | ------------ | ------------------ |
| 1 | Design & Architecture | Design Agent | ~90s |
| 2 | Development | Development Agent | ~3min |
| 2.5 | Code Review | Code Review Agent | ~45s (+ retry loop) |
| 3 | Testing | Testing Agent | ~3min |
| 4 | Documentation | Documentation Agent | ~2min |
| — | Publish | publish.py | ~30s |

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
│                      Workflow Orchestrator                           │
│                   (orchestrator/workflow.py)                        │
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

## Pipeline Implementation

The orchestrator (`orchestrator/workflow.py`) implements the SDLC stage sequence as a sequential runner. Each stage runs, updates the shared `WorkflowState`, and emits a heartbeat to the dashboard. The orchestrator reads `current_phase` from state to decide which SDLC stage runs next.

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

When a stage runner raises an unhandled exception, the node sets `current_phase = "error"`, emits an error heartbeat, and the conditional router sends the workflow to `END`.

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

## Stage Runners at a Glance

| Stage | File | Input | Output |
|-------|------|-------|--------|
| Design | `stages/design.py` | Issue title, description, optional repo path | Design document, component list, risks, acceptance criteria, implementation plan |
| Development | `stages/develop.py` | Design outputs from state | Go code files, test files, PR description |
| Code Review | `stages/code_review.py` | Generated code files from state | Review verdict, findings list, review summary |
| Testing | `stages/test.py` | Design outputs from state | Ginkgo v2 test suites, test plan, coverage analysis |
| Documentation | `stages/docs.py` | All prior outputs from state | PR summary, release notes, JTBD docs, SHIP document |

---

## Data Flow

Each node returns a partial state dictionary. The orchestrator merges it into the accumulated state so every subsequent stage automatically sees all prior outputs.

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

After each stage completes, its outputs are validated before the next stage begins.
This prevents silent cascading failures where a stage returns empty data and
subsequent stages produce garbage outputs.

**Validation flow:**

```text
Stage completes
     ↓
validate_phase(phase, state)
     ↓
  ┌──┴──┐
PASS    FAIL
  ↓      ↓
Next   Stop workflow with
Stage  clear error message
```

**Validation rules per phase:**

| Phase | Blocks on (required) | Warns on (optional) |
|-------|---------------------|---------------------|
| Design | Empty `design_analysis`, empty `implementation_plan` | No risks, components, or criteria |
| Development | Empty `code_files` | Short `pr_description` |
| Code Review | (never blocks — loop handles retries) | Review failures surfaced as warnings |
| Testing | Empty `test_plan` | No unit/integration tests |
| Documentation | Empty `pr_summary` | No `release_notes` |

Validation logic lives in `stages/validators.py`. Each phase has its own validator
that returns a `ValidationResult` with `passed`, `issues` (blocking), `warnings`
(non-blocking), and a `summary` dict of key metrics.

```python
from stages.validators import validate_phase

result = validate_phase("design", state)
# result.passed   → bool
# result.issues   → list[str]  (blocking - stops workflow)
# result.warnings → list[str]  (non-blocking - printed as warning)
# result.summary  → dict       (key metrics, e.g. "Code files generated: 3")
```

**Extending validation:** To add a validator for a new stage, add a
`validate_<phase>_output(state)` function in `stages/validators.py` and register
it in the `VALIDATORS` dict. The orchestrator picks it up automatically via
`validate_phase()`.

→ See [Output Validation & Manual Approval](../06-advanced/output-validation.md)
for the full reference, including `ValidationResult` fields, per-phase threshold
configuration, and manual approval mode.

---

## Security Layers

### PII Redaction

All data fetched from external sources (Jira tickets, GitHub PRs) is redacted before it enters the pipeline. Redaction happens inside the fetch functions themselves — `JiraClient.fetch_ticket()` and `GitHubClient.fetch_pr()` — so PII never appears in workflow state, agent prompts, or dashboard heartbeats.

**What is redacted:**

- Personal name fields (`reporter`, `assignee`, `author`, `reviewers`) are replaced with `[CUSTOMER_REDACTED]`
- Free-text fields (`summary`, `description`, `title`, `body`, `comments`, `acceptance_criteria`) are scanned for IPv4/IPv6 addresses, email addresses, phone numbers, and internal hostnames

**Public domain allowlist:** URLs and email addresses belonging to known public domains (such as `github.com`, `redhat.com`, `kubernetes.io`) are preserved. The full list is defined in `config/redaction_config.py`.

**Disabling:** Set `PII_REDACTION_ENABLED=false` to bypass redaction during local development. This setting must not be used in production.

See [PII Redaction](../07-security/pii-redaction.md) for the full reference.

### Prompt Injection Guard

External free-text fields (issue titles, descriptions, PR bodies) are sanitized inside each stage runner before the text is embedded into a Claude prompt. The guard strips five categories of injection patterns: role overrides, system-escape sequences, jailbreak tokens, base64-encoded payloads, and delimiter abuse.

Sanitization runs at the stage-runner layer — after PII redaction but before prompt assembly — so injected instructions in external content never reach the model.

**Audit logging:** When a pattern is matched, a `WARNING` log line records the category and source field only. The matched content is never logged.

**Disabling:** Set `PROMPT_GUARD_ENABLED=false` to bypass sanitization during local development. This setting must not be used in production.

See [Prompt Injection Guard](../07-security/prompt-injection-guard.md) for the full reference.

### Output Sanitizer

The Output Sanitizer (Layer 3) protects all egress channels from containing PII. Where Layers 1 and 2 guard data entering the pipeline, Layer 3 guards data leaving it.

**Protected channels:**

- **Python logging** — `SanitizingFilter` is attached to every handler (file and console). It pre-formats log records to resolve `%s`/`%d` placeholders before sanitizing, preventing a bypass where a clean format string is combined with a PII-containing argument.
- **Generated artifacts** — `test_plan.md` and Go test files written by the Testing Agent are sanitized before being written to disk.
- **Dashboard heartbeat payloads** — the full heartbeat dict is recursively sanitized before the HTTP POST to the dashboard.

The sanitizer reuses `_redact_text` from `pii_redactor.py`, so the same patterns and replacement tokens apply at both layers. Sanitization is idempotent — running it on already-redacted text is safe.

**Disabling:** Set `OUTPUT_SANITIZER_ENABLED=false` to bypass sanitization during local development. This setting must not be used in production.

See [Output Sanitizer](../07-security/output-sanitizer.md) for the full reference.

### Claude Hooks — PostToolUse Defender

The PostToolUse Prompt Injection Defender (Layer 4) operates at the Claude Code host level, outside the Python application. After every tool call (`Read`, `WebFetch`, `Bash`, `Grep`, `Task`, `mcp__*`), the hook scans the tool output for injection patterns using the same categories as the Prompt Injection Guard plus a custom Jira-specific category.

The hook is warn-only: it always exits with code 0 so tool execution is never blocked. When a pattern is detected, Claude receives a warning alongside the tool output, giving it the context to evaluate the content critically.

**Pattern categories (59+ total):** instruction override, role-playing/DAN, encoding obfuscation, context manipulation, and Jira-specific injection patterns.

See [Claude Hooks](../07-security/claude-hooks.md) for the full reference, including how to add custom patterns.

---

## Terminal Output

When you run the pipeline via `scripts/orchestrate.py`, each phase prints a numbered header so you can track progress at a glance. After every phase completes, the elapsed time for that phase is printed. When all phases finish, a summary is printed containing the total duration, the path to the saved output artifacts, and the dashboard URL.

**Phase headers:**

```text
Phase 1/5 · Design
Phase 2/5 · Development
Phase 2.5/5 · Code Review
Phase 3/5 · Testing
Phase 4/5 · Documentation
```

**Per-phase completion line (example):**

```text
Design completed in 45.2s
```

**Final summary (example):**

```text
Pipeline completed in 3m 12s
Artifacts: ./output/session-abc123/
Dashboard: http://localhost:8080
```

---

## Supporting Components

### Dashboard

The dashboard (`dashboard/backend.py`) is an optional FastAPI server with SQLite storage. Stage runners emit heartbeats via HTTP POST to `/api/heartbeat`. If the dashboard is unreachable, heartbeats fail silently so the workflow is not blocked.

See [Dashboard Overview](../04-dashboard/overview.md).

### Skills Layer

The `skills/` package is a thin, uniform wrapper over the external integrations in `tools/`. Skills are called exclusively from entry points (`scripts/orchestrate.py`, `scripts/test_agents.py`) — stage runners in the pipeline do not call skills directly.

**Key design properties:**

- Skills do not replace `tools/` — all business logic remains in `tools/` unchanged.
- `DRY_RUN` handling is centralized: `Skill.run()` checks the `DRY_RUN` environment variable and automatically routes to `_mock_response()` instead of `_execute()`, so every skill gets offline mode for free.
- Each skill declares `input_schema` and `output_schema` as JSON Schema dicts, making them MCP-ready without additional glue code.
- `__init_subclass__` enforces required class attributes (`name`, `description`, `input_schema`, `output_schema`) at class definition time, catching misconfigured skills before runtime.

**Registered skills (`skills/default_registry` via `skills/__init__.py`):**

| Skill name | Wraps | Input | Output |
| --- | --- | --- | --- |
| `fetch_jira_ticket` | `mcp.jira_stub.fetch_ticket()` + `tools.jira_client.map_ticket_to_state()` | `{"ticket_id": str}` | AgentState Jira fields |
| `update_jira` | `tools.jira_client.JiraClient.update_ticket()` | `{"ticket_id": str, "comment": str}` | `{"success": bool}` |
| `fetch_github_prs` | `tools.github_client.GitHubClient.fetch_prs_from_urls()` | `{"pr_urls": list[str]}` | `{"pr_data": list[dict]}` |

### Repository Analysis Tools

Optional tools in `tools/` that stage runners can use when a repository path is provided:

- `tools/repo_search.py` - Code search and Go package analysis
- `tools/rag_search.py` - Documentation search with RAG for the docs agent
- `tools/git_ops.py` - Git operations and repository utilities
- `tools/github_client.py` - GitHub REST API client for fetching PR metadata linked to Jira tickets via remote links
- `tools/pii_redactor.py` - PII redaction applied at fetch time to all Jira and GitHub data

### Configuration

- `config/shipwright_components.py` - Shipwright Build component definitions (BuildRun, Build, BuildStrategy, webhooks), CRD types, build strategies, OpenShift integrations
- `prompts/` - System prompts for each stage runner (one file per stage)
- `config/testing_config.py` - Ginkgo v2 test patterns and templates
- `config/mock_responses.py` - Mock API responses for dry run mode
- `config/redaction_config.py` - Public domain allowlist for PII redaction

### Stage Prompts (`prompts/`)

Each stage runner has a dedicated system prompt stored as a `Final[str]` constant in its own file under `prompts/`. The prompt defines the stage's role, responsibilities, output format, and guardrails.

| Constant | Prompt file | Used by | Purpose |
| -------- | ----------- | ------- | ------- |
| `DESIGN_AGENT_PROMPT` | `prompts/design.py` | `stages/design.py` | Instructs Claude to produce design documents: problem statement, scope, impacted components, risks, acceptance criteria, implementation plan |
| `DEVELOPMENT_AGENT_PROMPT` | `prompts/develop.py` | `stages/develop.py` | Instructs Claude to generate idiomatic Go code, table-driven tests, and a PR description ending with "Generated by AI" |
| `CODE_REVIEW_AGENT_PROMPT` | `prompts/code_review.py` | `stages/code_review.py` | Instructs Claude to review generated Go code using machine-parseable `[BLOCKING]`/`[WARNING]`/`[SUGGESTION]` format, ending with `VERDICT: PASS` or `VERDICT: FAIL` |
| `TESTING_AGENT_PROMPT` | `prompts/test.py` | `stages/test.py` | Instructs Claude to generate Ginkgo v2 test suites with DDT patterns, Gomega assertions, and Shipwright test helpers |
| `DOCS_AGENT_PROMPT` | `prompts/docs.py` | `stages/docs.py` | Instructs Claude to produce PR summaries, release notes, JTBD documentation, SHIP documents, and high-level design documents |

**How stage runners load their prompt:**

Each stage runner imports its constant at the top of the module and passes it as the `system` parameter of the Claude API call:

```python
from prompts.design import DESIGN_AGENT_PROMPT

response = client.messages.create(
    model=model,
    system=DESIGN_AGENT_PROMPT,
    messages=[{"role": "user", "content": user_prompt}],
)
```

**Customizing prompts:**

To adjust stage behavior, edit the relevant constant in the corresponding `prompts/*.py` file. Common reasons to customize:

- Change the output format (e.g., switch from Markdown to JSON)
- Add project-specific guardrails (e.g., enforce a naming convention)
- Adjust the level of detail in generated output
- Add or remove sections from the design/docs template

Changes take effect immediately on the next run — no code changes required.

---

## Repository Structure

```text
muilti-agents-ocp-builds/
├── orchestrator/    # Workflow sequencer and quality gates
├── stages/          # Stage runner implementations and output validators
├── prompts/         # System prompts for each pipeline stage
├── models/          # Pydantic output contracts and WorkflowState TypedDict
├── config/          # Auth, patterns, mock data
├── dashboard/       # FastAPI backend, enrichers, heartbeat, frontend
├── integrations/    # Jira and GitHub integration modules
├── mcp/             # MCP server stubs (future integrations)
├── scripts/         # orchestrate.py, run_dashboard.py, test_agents.py
├── tests/           # pytest test suite
├── tools/           # repo_search, rag_search, git_ops, github_client, pii_redactor
└── utils/           # logging_config.py
```

---

[← Previous: Configuration](../01-getting-started/configuration.md) | [Next: Agents Overview →](agents-overview.md)
