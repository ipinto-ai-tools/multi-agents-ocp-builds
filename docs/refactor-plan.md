# FlowPilot Refactor Plan

Refactor FlowPilot from a custom multi-agent framework into a **repository-aware SDLC orchestration layer** that wraps the Claude Code Agent SDK.

---

## Motivation

External feedback:

> "Using Claude Code or opencode directly (or wrapping their SDKs) is the way to go, rather than implementing a framework of our own for skill and tool use. Those tools are going to improve faster than we can keep up with."

The current codebase has strong product pieces (dashboard, sessions, repo-aware analysis, validation, artifacts) but also framework pieces (LangGraph orchestration, skills layer, custom Anthropic client management) that duplicate what the Claude Code Agent SDK already provides.

**Strategy:** Keep the product, replace the framework plumbing with Agent SDK calls.

---

## What We Keep

| Asset | Why |
| --- | --- |
| Dashboard (React + FastAPI) | No CLI tool gives you real-time visibility, approvals, artifact downloads |
| Session / heartbeat system | Run tracking, audit trail, stuck session cleanup |
| Domain knowledge | Shipwright prompts, Ginkgo v2 patterns, Go/K8s code standards |
| repos.yaml + repo analysis | Multi-repo awareness is a differentiator |
| SDLC stage concept | Design → Develop → Review → Test → Docs |
| Validation between stages | Structured handoffs, not "agent chatter" |
| CLI + API | Product assets for scripting and integration |

## What We Replace

| Current Layer | Replacement |
| --- | --- |
| LangGraph `StateGraph` orchestration | Thin sequential stage runner |
| Custom `AnthropicVertex` client in each agent | Claude Code Agent SDK |
| Skills layer (`skills/base.py`, registry) | Agent SDK tool definitions |
| Free-form `AgentState` TypedDict | Structured stage output contracts (JSON schemas) |
| Code Review as full stage | Quality gate after Develop |

---

## Target Architecture

```text
+-----------------------------+
|   Dashboard / CLI / API     |
+-------------+---------------+
              |
              v
+-----------------------------+
|   Workflow Orchestrator      |
|   (thin stage sequencer)    |
|   - stage ordering          |
|   - retries / approvals     |
|   - structured handoffs     |
+-------------+---------------+
              |
    +---------+---------+---------+
    |         |         |         |
    v         v         v         v
 Design    Develop     Test      Docs
 Stage     Stage       Stage     Stage
    |         |         |         |
    |     [review gate] |         |
    |         |         |         |
    v         v         v         v
     Claude Code Agent SDK
              |
              v
    repo.yaml + Tools + Repos
              |
              v
    Structured Outputs / Artifacts
```

---

## Refactor Tasks

### Phase 1: Foundation

| Task | Title | Goal |
| --- | --- | --- |
| 1 | Reposition project messaging | Remove "multi-agent framework" language, position as SDLC orchestration |
| 2 | Agent SDK spike — replace Design stage | Prove Agent SDK works by migrating one stage |
| 3 | Define repo.yaml schema and validation | Formalize the primary reuse/config mechanism |

### Phase 2: Core Migration

| Task | Title | Goal |
| --- | --- | --- |
| 4 | Define structured stage output contracts | JSON schema per stage for deterministic handoffs |
| 5 | Replace LangGraph with thin stage sequencer | Remove framework dependency, keep simple control flow |
| 6 | Migrate remaining stages to Agent SDK | Develop, Test, Docs stages use Agent SDK |

### Phase 3: Simplification

| Task | Title | Goal |
| --- | --- | --- |
| 7 | Remove skills layer | Replace with Agent SDK tools or thin integration wrappers |
| 8 | Demote Code Review to quality gate | Simplify SDLC flow, keep retry loop |
| 9 | Implement quality gates | repo.yaml commands + Qodo as enforceable gates |

### Phase 4: Polish

| Task | Title | Goal |
| --- | --- | --- |
| 10 | Align repository structure | Move files to match new architecture |
| 11 | MVP end-to-end proof | Full SDLC flow with new architecture, repo.yaml driven |

---

## Task Details

### Refactor Task 1: Reposition project messaging

**Goal:** Align README, docs, and code comments with SDLC orchestration identity.

**Changes:**
- Remove "multi-agent framework" / "agent platform" language from README, docs, and docstrings
- Replace "LangGraph orchestrator" references with "workflow orchestrator"
- Clarify Claude as execution engine, FlowPilot as supervisor
- Update architecture diagrams to show stage-based flow

**Files affected:** `README.md`, `docs/user-guide/02-concepts/architecture.md`, `docs/user-guide/02-concepts/agents-overview.md`, `CLAUDE.md`

**Out of scope:** Code changes (this is messaging only).

---

### Refactor Task 2: Agent SDK spike — replace Design stage

**Goal:** Prove the Claude Code Agent SDK can replace the custom Anthropic client by migrating one stage.

**Changes:**
- Replace `AnthropicVertex` client in `agents/design_agent.py` with Agent SDK call
- Define design-specific tools as Agent SDK tool definitions
- Remove LangGraph node wrapper for design
- Validate: structured output works, heartbeats still emit, dashboard still tracks
- Benchmark: token usage, latency, output quality vs current implementation

**Success criteria:**
- Design stage produces identical output format
- Dashboard shows heartbeats from the new implementation
- No regression in output quality

**Files affected:** `agents/design_agent.py`, `config/auth_config.py` (may become unused)

---

### Refactor Task 3: Define repo.yaml schema and validation

**Goal:** Make repo.yaml the primary configuration and reuse mechanism.

**Changes:**
- Define formal JSON schema for repo.yaml
- Add schema validation on load in `config/repo_config.py`
- Support fields: language, stages, commands (build/lint/test/doc), paths, approval requirements, prompt overrides
- Add 2-3 example repo.yaml configs for different project types (Go/K8s, Python, generic)
- Integrate validated config into stage runners

**Files affected:** `config/repo_config.py`, `repos.yaml.example`, new `config/repo_schema.py`

---

### Refactor Task 4: Define structured stage output contracts

**Goal:** Replace free-form `AgentState` dict with typed, validated stage outputs.

**Changes:**
- Define JSON schema per stage output:
  - Design: summary, impacted_files, risks, acceptance_criteria, implementation_plan
  - Develop: code_files, test_files, pr_description, security_notes, new_dependencies
  - Test: test_plan, unit_tests, integration_tests, e2e_tests, coverage_analysis
  - Docs: pr_summary, release_notes, docs_changes
- Validate outputs against schema between stages
- Replace `AgentState` TypedDict with dataclass or Pydantic models

**Files affected:** `graph/state.py`, `agents/validators.py`, new `models/stage_outputs.py`

---

### Refactor Task 5: Replace LangGraph with thin stage sequencer

**Goal:** Remove LangGraph dependency, replace with a simple sequential runner.

**Changes:**
- Remove `langgraph` from `requirements.txt`
- Replace `StateGraph` in `agents/graph.py` with a simple stage sequencer:
  - Stage ordering (configurable via repo.yaml)
  - Retry logic (configurable max retries)
  - Pause/approval points (`MANUAL_APPROVAL`)
  - Error handling and early termination
- Keep heartbeat emissions to dashboard
- Pass structured outputs between stages (from Task 4)

**Files affected:** `agents/graph.py` → `orchestrator/workflow.py`, `requirements.txt`

**Depends on:** Task 4 (structured outputs)

---

### Refactor Task 6: Migrate remaining stages to Agent SDK

**Goal:** All four stages use Agent SDK instead of custom Anthropic client.

**Changes:**
- Migrate `agents/go_k8s_developer.py` (Development)
- Migrate `agents/testing_agent.py` (Testing)
- Migrate `agents/docs_agent.py` (Documentation)
- Each stage: prompt template + tool definitions + output schema
- Remove all direct `client.messages.create()` calls
- Remove `config/auth_config.py` if no longer needed

**Depends on:** Task 2 (spike proves viability), Task 4 (output contracts)

---

### Refactor Task 7: Remove skills layer

**Goal:** Eliminate the skills abstraction; use Agent SDK tools or thin wrappers.

**Changes:**
- Remove `skills/` directory and skill registry (`skills/base.py`)
- Move Jira integration → `integrations/jira.py`
- Move GitHub integration → `integrations/github.py`
- Define as Agent SDK tools where the agent needs to call them
- Keep as direct function calls where the orchestrator calls them (e.g., fetching Jira ticket at startup)

**Files affected:** `skills/`, new `integrations/`

**Depends on:** Task 6 (stages migrated)

---

### Refactor Task 8: Demote Code Review to quality gate

**Goal:** Simplify the SDLC flow by making review a gate, not a stage.

**Changes:**
- Move `agents/code_review_agent.py` logic into a gate/validator
- Keep the auto-fix retry loop: Develop → review gate → retry if blocking findings
- Remove Code Review from the stage sequence visible to users
- The SDLC flow becomes: Design → Develop (with review gate) → Test → Docs

**Files affected:** `agents/code_review_agent.py` → `orchestrator/gates.py`

**Depends on:** Task 5 (new orchestrator)

---

### Refactor Task 9: Implement quality gates

**Goal:** Enforce quality via repo.yaml commands and tools.

**Changes:**
- Run repo.yaml commands (build, lint, test) as gates after relevant stages
- Integrate Qodo as optional gate (already partially implemented)
- Parse gate results: pass/fail/block decision
- Gates run after: Develop (build + lint + review), Test (test commands)
- Configurable via repo.yaml: which gates, blocking threshold

**Files affected:** New `orchestrator/gates.py`, `config/repo_config.py`

**Depends on:** Task 3 (repo.yaml schema), Task 5 (orchestrator), Task 8 (review gate)

---

### Refactor Task 10: Align repository structure

**Goal:** Directory layout matches the new architecture.

**Target structure:**
```text
orchestrator/
  workflow.py           # stage sequencer (was agents/graph.py)
  gates.py              # quality gates + review
  transitions.py        # stage transition rules

stages/
  design.py             # was agents/design_agent.py
  develop.py            # was agents/go_k8s_developer.py
  test.py               # was agents/testing_agent.py
  docs.py               # was agents/docs_agent.py

config/
  repo_schema.py        # repo.yaml schema + validation
  repo_config.py        # repo.yaml loader
  defaults.py           # default configurations

prompts/
  design.md             # was in config/agent_prompts.py
  develop.md
  test.md
  docs.md

models/
  stage_outputs.py      # structured output contracts
  workflow_state.py     # workflow state (run metadata, not agent state)

integrations/
  jira.py               # was skills/
  github.py

dashboard/              # unchanged
api/                    # if separated from dashboard
scripts/                # unchanged
tests/                  # updated imports
```

**Changes:**
- Rename/move files as shown above
- Update all imports across codebase
- Update all tests
- Remove empty/unused directories

**Depends on:** Tasks 5-9 (all structural changes complete)

---

### Refactor Task 11: MVP end-to-end proof

**Goal:** Prove the new architecture works with a full SDLC run.

**Changes:**
- Run full pipeline: Design → Develop (with review gate) → Test → Docs
- Driven by repo.yaml configuration
- All stages use Agent SDK
- Quality gates enforced
- Dashboard integration verified (heartbeats, sessions, artifacts, downloads)
- Document: performance comparison vs old architecture, token usage delta

**Success criteria:**
- Full pipeline completes successfully
- Dashboard shows all phases with correct status
- Artifacts downloadable from UI
- No regression in output quality
- repo.yaml for a second project type works without code changes

**Depends on:** All previous tasks

---

## Dependency Graph

```text
Task 1 (messaging)          ← no dependencies, do first
Task 2 (SDK spike)          ← no dependencies, do first
Task 3 (repo.yaml schema)   ← no dependencies, do first

Task 4 (output contracts)   ← after Task 2 (spike informs contract shape)
Task 5 (stage sequencer)    ← after Task 4

Task 6 (migrate stages)     ← after Task 2 + Task 4
Task 7 (remove skills)      ← after Task 6
Task 8 (review gate)        ← after Task 5
Task 9 (quality gates)      ← after Task 3 + Task 5 + Task 8

Task 10 (repo structure)    ← after Tasks 5-9
Task 11 (MVP proof)         ← after all
```

```text
[1] [2] [3]           ← Phase 1 (parallel)
     |    \
    [4]   |           ← Phase 2
     |    |
    [5]  [6]
     |    |
    [8]  [7]          ← Phase 3
     |
    [9]
     |
   [10]               ← Phase 4
     |
   [11]
```

---

## Principles

1. **Claude is the worker; FlowPilot is the supervisor** — don't rebuild what the SDK does
2. **Configuration over framework** — repo.yaml drives behavior, not code changes
3. **Explicit stages over autonomous agents** — predictable, auditable, debuggable
4. **Structured handoffs over free-form state** — JSON schemas between stages
5. **Quality gates over AI confidence** — enforce with real commands and tools
6. **Refactor, not rewrite** — keep working product pieces, replace plumbing incrementally

---

## Risk Register

| Risk | Mitigation |
| --- | --- |
| Agent SDK doesn't support Vertex AI auth | Task 2 spike validates this before committing |
| Structured outputs reduce flexibility | Design schemas with optional fields; validate required only |
| LangGraph removal breaks dashboard integration | Heartbeat emissions are independent of LangGraph; verify in Task 5 |
| Skills removal breaks Jira/GitHub integration | Move to integrations/ first, keep same interface; swap internals |
| Performance regression from SDK overhead | Benchmark in Task 2 spike; abort if unacceptable |

---

## Timeline Estimate

Phase 1 (Tasks 1-3) can start immediately and run in parallel.
Phase 2 (Tasks 4-6) depends on the spike result from Task 2.
Phase 3 (Tasks 7-9) depends on core migration.
Phase 4 (Tasks 10-11) is cleanup and validation.

Each task is scoped for 1-3 sessions of focused work.
