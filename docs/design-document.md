# Agentic SDLC Automation -- Design Document

> A pipeline that turns a feature request into design analysis, production code,
> tests, and documentation -- all driven by Claude AI as the execution engine.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture Overview](#2-architecture-overview)
3. [Directory Structure](#3-directory-structure)
4. [Core Concepts](#4-core-concepts)
5. [Configuration (repos.yaml)](#5-configuration-reposyaml)
6. [Security and Data Protection](#6-security-and-data-protection)
7. [Dashboard and Monitoring](#7-dashboard-and-monitoring)
8. [Running the Pipeline](#8-running-the-pipeline)
9. [Output Artifacts](#9-output-artifacts)
10. [Key Design Decisions](#10-key-design-decisions)
11. [Extending the System](#11-extending-the-system)
12. [MVP Validation Results](#12-mvp-validation-results)
13. [Future Roadmap](#13-future-roadmap)

---

## 1. Introduction

### What This Project Does

This project is an SDLC orchestration layer that automates the full feature
development lifecycle. Given a feature request (from a title/description, a Jira
ticket, or a GitHub issue), the pipeline produces:

- Architectural design analysis and implementation plan
- Production code (Go/Kubernetes focused, but configurable)
- AI-powered code review with automated fix loops
- Comprehensive test suites (unit, integration, e2e)
- Documentation artifacts (PR summaries, release notes)

### The Pipeline

```
Feature Request --> Design --> Development --> Code Review --> Testing --> Docs --> Artifacts
```

Each stage is a standalone Claude-powered runner with explicit input/output
contracts. A thin sequential orchestrator chains them together, passing state
through a shared dictionary. There is no complex graph framework -- just
straightforward sequential execution with validation between stages.

### Key Insight

The architecture separates three concerns cleanly:

| Concern              | Component                 | Changes When...                    |
|----------------------|---------------------------|------------------------------------|
| Execution order      | `orchestrator/workflow.py`| You add/remove/reorder stages      |
| Domain knowledge     | `prompts/*.py`            | You target a different language/domain |
| Data shape           | `models/*.py`             | You need new fields in stage I/O   |

This separation means you can retarget the pipeline to a different language,
framework, or domain by changing prompt files alone -- without touching the
orchestrator or stage runner code.

### Target Domain

Originally built for OpenShift/Shipwright Build projects (Go, Kubernetes CRDs,
Ginkgo tests), but the architecture is project-agnostic. The `repos.yaml`
configuration makes it adaptable to any codebase with its own build, lint, and
test commands.

---

## 2. Architecture Overview

### High-Level Flow

```
                    +-----------+
                    |  Design   |
                    +-----+-----+
                          |
                    +-----v-----+
                    |  Develop  |<-------+
                    +-----+-----+        |
                          |              | retry (blocking findings)
                    +-----v-----+        |
                    |  Review   |--------+
                    |  (gate)   |
                    +-----+-----+
                          | PASS
                    +-----v-----+
                    |  Testing  |
                    +-----+-----+
                          |
                    +-----v-----+
                    |   Docs    |
                    +-----------+
```

After each stage, the orchestrator:

1. Merges the stage output into shared state
2. Validates the output (required fields, minimum lengths)
3. Emits a heartbeat to the monitoring dashboard
4. Checks approval gates (if configured)
5. Proceeds to the next stage or terminates on error

### Stage Lifecycle

Every stage invocation follows the same lifecycle:

```
  Input state
       |
       v
  +--------------------+
  | Validate inputs    |  Fail fast on missing prerequisites
  +--------------------+
       |
       v
  +--------------------+
  | Build prompt       |  System prompt (from prompts/) + user context
  +--------------------+
       |
       v
  +--------------------+
  | Call Claude API    |  client.messages.create() via Vertex AI
  +--------------------+
       |
       v
  +--------------------+
  | Parse response     |  Markdown -> typed dict fields
  +--------------------+
       |
       v
  +--------------------+
  | Validate output    |  Pydantic contract + field-level checks
  +--------------------+
       |
       v
  +--------------------+
  | Emit heartbeat     |  HTTP POST to dashboard (non-blocking)
  +--------------------+
       |
       v
  Output dict (merged into shared state)
```

---

## 3. Directory Structure

```
orchestrator/              # Pipeline orchestration
  workflow.py              # WorkflowOrchestrator -- sequential stage runner
  gates.py                 # Quality gates (review gate + shell command gates)

stages/                    # Stage runners (one per SDLC phase)
  design.py                # Architectural analysis, impact assessment
  develop.py               # Code generation (Go/K8s focused)
  test.py                  # Test plan + Ginkgo/Go test generation
  docs.py                  # PR summaries, release notes, SHIP docs
  code_review.py           # AI-powered code review
  validators.py            # Output validation per stage (field + Pydantic)

prompts/                   # System prompts (one file per stage)
  _shared.py               # Shared sections (data privacy policy)
  design.py                # Design stage system prompt
  develop.py               # Development stage system prompt
  test.py                  # Testing stage system prompt
  docs.py                  # Documentation stage system prompt
  code_review.py           # Code review system prompt

models/                    # Data contracts
  stage_outputs.py         # Pydantic models (DesignOutput, DevelopOutput, etc.)
  workflow_state.py        # WorkflowState TypedDict

config/                    # Configuration
  repo_schema.py           # repos.yaml Pydantic schema (RepoConfig, RepoEntry, etc.)
  repo_config.py           # Config loading + env var merging
  auth_config.py           # Google Vertex AI authentication
  shipwright_components.py # Domain-specific component definitions
  testing_config.py        # Ginkgo v2 test patterns and templates
  mock_responses.py        # Mock API responses for dry-run mode

integrations/              # External service connectors
  jira.py                  # Jira ticket fetch/update (thin wrapper)
  github.py                # GitHub PR metadata fetch (thin wrapper)

tools/                     # Analysis and safety tooling
  repo_search.py           # Code search and Go package analysis
  rag_search.py            # Documentation search with RAG (docs stage)
  git_ops.py               # Git operations and utilities
  pii_redactor.py          # PII redaction before prompt assembly
  prompt_guard.py          # Prompt injection detection/sanitization
  output_sanitizer.py      # Output sanitization (no secrets in generated code)

dashboard/                 # Real-time monitoring
  backend.py               # FastAPI + SQLite backend
  heartbeat.py             # Heartbeat protocol (emitter, config, session context)
  enrichers.py             # Heartbeat data enrichment before storage
  frontend/                # Single-page dashboard UI

scripts/                   # CLI entry points
  orchestrate.py           # Main pipeline runner
  run_dashboard.py         # Dashboard server launcher
  test_agents.py           # Manual agent testing with dry-run support
```

---

## 4. Core Concepts

### 4.1 The Orchestrator

The `WorkflowOrchestrator` class in `orchestrator/workflow.py` is a thin
sequential stage runner. It replaced an earlier LangGraph-based `StateGraph`
implementation with a simpler, more explicit design.

**What it does:**

- Manages a shared state dictionary (`Dict[str, Any]`)
- Calls each stage function in order, merging outputs into state
- Runs output validation between stages
- Emits dashboard heartbeats after each stage
- Supports stage skipping via the `repos.yaml` `stages` list
- Supports manual approval gates between stages

**What it does not do:**

- No graph traversal or conditional routing (stages run in fixed order)
- No retry logic outside the develop-review loop
- No state persistence (state lives in memory for the pipeline duration)

```python
# Simplified view of the orchestrator's run() method:
def run(self, title, description, issue_type="feature"):
    state = {"issue_title": title, "issue_description": description, ...}

    if self._should_run_stage("design"):
        result = self._run_design(state)
        state.update(result)
        self._validate("design", state)

    if self._should_run_stage("develop"):
        self._run_develop_with_review_gate(state)  # includes retry loop

    if self._should_run_stage("testing"):
        result = self._run_testing(state)
        state.update(result)

    if self._should_run_stage("docs"):
        result = self._run_docs(state)
        state.update(result)

    return state
```

### 4.2 Stage Runner Pattern

Every stage runner follows the same implementation pattern. Here is a condensed
example showing the structure:

```python
# stages/design.py (simplified)

def run_design(title, description, repo_path=None):
    # 1. Validate inputs
    if not title or not description:
        raise ValueError("Title and description are required")

    # 2. Get Claude client
    client = get_anthropic_client()

    # 3. Build prompt
    system_prompt = DESIGN_AGENT_PROMPT  # from prompts/design.py
    user_message = f"Feature: {title}\n\nDescription: {description}"

    # 4. Call Claude API
    response = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "8192")),
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    # 5. Parse response into typed dict
    result = parse_design_response(response.content[0].text)

    # 6. Emit heartbeat
    emit_heartbeat("design", {"current_phase": "design_complete", **result})

    return result
```

**Stage summary table:**

| Stage       | Entry Point                       | Key Input                             | Key Output                                            |
|-------------|-----------------------------------|---------------------------------------|-------------------------------------------------------|
| Design      | `stages/design.run_design()`      | title, description, repo_path         | design_analysis, impacted_components, risks, implementation_plan |
| Development | `stages/develop.run_development()`| WorkflowState (needs implementation_plan) | code_files, test_files, pr_description               |
| Code Review | `stages/code_review.run_code_review()` | WorkflowState (needs code_files) | review_passed, review_findings, review_summary        |
| Testing     | `stages/test.run_testing()`       | WorkflowState (needs design_analysis, acceptance_criteria) | test_plan, unit/integration/e2e_tests, coverage_analysis |
| Docs        | `stages/docs.run_docs()`          | WorkflowState + optional config       | pr_summary, release_notes, docs_changes               |

### 4.3 Quality Gates

Quality gates run between stages to enforce standards. Unlike stages, gates do
not produce new artifacts -- they validate existing outputs and return pass/fail
decisions. The pipeline uses two kinds of gates.

#### Review Gate (AI-Driven)

The review gate delegates to the code review stage runner, which uses Claude to
analyze the generated code. Findings are classified by severity:

| Severity   | Effect                                           |
|------------|--------------------------------------------------|
| BLOCKING   | Triggers a develop-review retry loop (max 2 iterations) |
| WARNING    | Logged but does not block progression             |
| SUGGESTION | Informational only                                |

The retry loop works as follows:

```
  Develop (initial)
       |
       v
  Review gate
       |
       +--- PASS --> continue to Testing
       |
       +--- FAIL (blocking findings) + iterations remain
       |         |
       |         v
       |    Develop (retry with findings in context)
       |         |
       |         v
       |    Review gate (re-evaluate)
       |         |
       |         +--- PASS or max iterations reached --> continue
       |
       +--- FAIL + max iterations reached --> continue with warnings
```

After the maximum number of review iterations (default: 2), the pipeline
continues regardless, logging unresolved findings as warnings.

#### Command Gates (Shell-Based)

Command gates run build, lint, and test commands defined in `repos.yaml`. These
are non-blocking -- results are stored in state for visibility, but failures do
not halt the pipeline.

```
  Post-develop gates:     build command, lint command
  Post-testing gates:     test command
```

Example from `repos.yaml`:

```yaml
repos:
  - path: /home/user/git/my-project
    commands:
      build: "go build ./..."
      lint: "golangci-lint run"
      test: "go test ./..."
```

### 4.4 Data Contracts

The pipeline uses a hybrid approach for data contracts that balances flexibility
with safety.

#### WorkflowState (TypedDict)

`WorkflowState` in `models/workflow_state.py` defines the shared state shape as
a `TypedDict(total=False)`. All fields are optional, which allows stages to
contribute only the fields they produce.

```python
class WorkflowState(TypedDict, total=False):
    # Input
    issue_title: str
    issue_description: str
    issue_type: str

    # Design outputs
    design_analysis: str
    impacted_components: list[str]
    implementation_plan: list[str]

    # Development outputs
    code_files: list
    pr_description: str

    # Control flow
    session_id: str
    current_phase: str

    # ... (50+ fields total across all stages and integrations)
```

#### Pydantic Output Models

`models/stage_outputs.py` defines Pydantic models for each stage's output.
These provide strict validation at stage boundaries:

```python
class DesignOutput(BaseModel):
    design_analysis: str = Field(..., min_length=50)
    impacted_components: list[str] = []
    risks: list[str] = []
    acceptance_criteria: list[str] = []
    implementation_plan: list[str] = Field(..., min_length=1)

class DevelopOutput(BaseModel):
    code_files: list[CodeFile] = Field(..., min_length=1)
    test_files: list[CodeFile] = []
    pr_description: str = ""

# Similarly: TestingOutput, DocsOutput, ReviewOutput
```

**Why both?**

| Mechanism      | Purpose                                    | Enforcement  |
|----------------|--------------------------------------------|--------------|
| TypedDict      | Flexible state passing between stages      | Type hints   |
| Pydantic model | Strict boundary validation (catch malformed output) | Runtime |

The TypedDict keeps the orchestrator simple (plain dict operations), while
Pydantic models catch malformed outputs before they propagate to downstream
stages. Both validation paths run at each stage boundary in `validators.py`.

---

## 5. Configuration (repos.yaml)

All pipeline behavior is configurable through a single `repos.yaml` file at the
project root. The schema is defined and validated by Pydantic in
`config/repo_schema.py`.

### Full Schema

```yaml
# ---------------------------------------------------------------
# Repository definitions
# ---------------------------------------------------------------
repos:
  - path: /home/user/git/my-project     # Must be absolute
    language: go                         # Optional: go, python, etc.
    commands:                            # Optional: shell commands for quality gates
      build: "go build ./..."
      lint: "golangci-lint run"
      test: "go test ./..."
      doc: "godoc -http=:6060"           # Optional: doc generation command

  - path: /home/user/git/another-project
    language: python
    commands:
      lint: "ruff check ."
      test: "pytest tests/ -v"

# ---------------------------------------------------------------
# Stage configuration
# ---------------------------------------------------------------
stages:                                  # Which stages to run (order matters)
  - design
  - develop
  - testing
  - docs

# ---------------------------------------------------------------
# Approval configuration
# ---------------------------------------------------------------
approvals:
  required_stages:                       # Stages that pause for user confirmation
    - develop
    - testing
  auto_approve: false                    # Set true to skip all approval prompts

# ---------------------------------------------------------------
# Prompt overrides
# ---------------------------------------------------------------
prompts:                                 # Replace default system prompts per stage
  design: "You are a security-focused design analyst..."
  develop: "You are a Python developer. Generate Django code..."
  test: "Generate pytest tests with 90% coverage target..."
  docs: "Generate documentation in AsciiDoc format..."
```

### Configuration Precedence

Repository paths are resolved with the following priority:

```
1. CLI argument (--repo-path)       Highest priority
2. repos.yaml entries               Merged with CLI
3. Environment variables            Fallback
   (SHIPWRIGHT_REPO_PATH,
    OPENSHIFT_BUILDS_REPO_PATH)
```

Duplicates are removed after path resolution. Non-existent paths are skipped
with a warning.

### Stage Skipping

Remove a stage from the `stages` list to skip it entirely:

```yaml
# Run only design and docs (skip development and testing)
stages:
  - design
  - docs
```

Skipped stages emit a heartbeat with `skipped: true` so the dashboard can
distinguish between "not run" and "failed".

### Defaults

When `repos.yaml` is missing or unparseable, the pipeline uses safe defaults:

| Setting          | Default Value                         |
|------------------|---------------------------------------|
| `stages`         | `["design", "develop", "testing", "docs"]` |
| `approvals`      | No required stages, auto_approve off  |
| `prompts`        | Built-in prompts from `prompts/*.py`  |
| `repos`          | Empty list (env vars used as fallback)|

---

## 6. Security and Data Protection

The pipeline processes feature requests that may originate from Jira tickets or
GitHub issues containing sensitive information. Three defense layers ensure that
confidential data does not leak into AI prompts or generated outputs.

### Defense-in-Depth Architecture

```
  External Data (Jira / GitHub)
           |
           v
  +------------------------+
  | PII Redactor           |   Layer 1: Strip names, emails, internal URLs
  | (tools/pii_redactor.py)|   before data enters the pipeline
  +------------------------+
           |
           v
  +------------------------+
  | Prompt Guard           |   Layer 2: Detect and neutralize prompt injection
  | (tools/prompt_guard.py)|   patterns from external text
  +------------------------+
           |
           v
  +--- Claude API call ---+
           |
           v
  +------------------------+
  | Output Sanitizer       |   Layer 3: Ensure no secrets or PII appear
  | (tools/output_         |   in generated code, tests, or documentation
  |  sanitizer.py)         |
  +------------------------+
           |
           v
  Clean output artifacts
```

### Configuration

Each layer can be independently toggled via environment variables:

| Variable                  | Default  | Purpose                                      |
|---------------------------|----------|----------------------------------------------|
| `PII_REDACTION_ENABLED`   | `true`   | Strip PII from Jira/GitHub data at fetch time |
| `PROMPT_GUARD_ENABLED`    | `true`   | Sanitize external text for injection patterns |
| `OUTPUT_SANITIZER_ENABLED`| `true`   | Scan generated output for secret patterns     |

All three default to enabled. Disable only for local development with
non-sensitive test data.

### Shared Data Privacy Policy

All stage prompts include a shared data privacy section (defined in
`prompts/_shared.py`) that instructs Claude to:

- Never include secrets, API keys, or credentials in generated code
- Prefer local processing over sending sensitive data
- Redact or mask sensitive values in examples
- Fail closed when privacy status is unclear

---

## 7. Dashboard and Monitoring

### Architecture

The dashboard provides real-time visibility into pipeline execution. It is
intentionally decoupled from the pipeline itself -- dashboard downtime does not
affect pipeline execution.

```
  Stage runners                    Dashboard
  +-------------+                  +------------------+
  |  Design     |--- heartbeat -->|  FastAPI backend  |
  |  Develop    |--- heartbeat -->|  (backend.py)     |
  |  Review     |--- heartbeat -->|       |           |
  |  Testing    |--- heartbeat -->|       v           |
  |  Docs       |--- heartbeat -->|  SQLite storage   |
  +-------------+                  |  (/tmp/claude/    |
                                   |   dashboard.db)   |
                                   |       |           |
                                   |       v           |
                                   |  Web frontend     |
                                   |  (index.html)     |
                                   +------------------+
```

### Heartbeat Protocol

Each stage emits heartbeats via HTTP POST to the dashboard API. The heartbeat
payload includes:

| Field        | Type   | Description                              |
|--------------|--------|------------------------------------------|
| `session_id` | string | Unique pipeline run identifier           |
| `agent`      | string | Stage name (design, develop, etc.)       |
| `phase`      | string | Current workflow phase                   |
| `timestamp`  | string | ISO 8601 timestamp                       |
| `raw_state`  | object | Sanitized snapshot of current state       |

Heartbeats are non-blocking: if the dashboard is unavailable, the emission
silently fails and the pipeline continues. The output sanitizer runs on
heartbeat payloads before transmission.

### Dashboard Features

- Pipeline progress tracking per session
- Stage status visualization (running, complete, skipped, error)
- Artifact inspection
- Multi-session history (SQLite persistence)

### Configuration

| Variable          | Default                          | Purpose                     |
|-------------------|----------------------------------|-----------------------------|
| `DASHBOARD_URL`   | `http://localhost:8080`          | Dashboard API endpoint      |
| `DASHBOARD_ENABLED` | `true`                        | Enable/disable heartbeats   |
| `DASHBOARD_DB_PATH`| `/tmp/claude/dashboard.db`      | SQLite database location    |

---

## 8. Running the Pipeline

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Cloud credentials with Vertex AI access (for Claude API)
- Optional: Jira API credentials, GitHub token

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/multi-agents-ocp-builds.git
cd multi-agents-ocp-builds

# Create virtual environment and install dependencies
uv venv && uv pip install -r requirements.txt

# Configure your repositories
cp repos.yaml.example repos.yaml
# Edit repos.yaml with your local repo paths and commands
```

### CLI Usage

```bash
# Basic execution with title and description
uv run python scripts/orchestrate.py \
  --title "Add timeout support for BuildRun" \
  --description "Allow configurable timeouts so builds don't run indefinitely" \
  --output-dir ./output

# From a Jira ticket (auto-fetches title, description, priority)
uv run python scripts/orchestrate.py \
  --jira-ticket SHIP-123 \
  --output-dir ./output

# From a GitHub issue
uv run python scripts/orchestrate.py \
  --github-issue "shipwright-io/build#456" \
  --output-dir ./output

# Dry-run mode (mock API responses, no Claude/Jira calls)
uv run python scripts/orchestrate.py \
  --title "Test feature" \
  --description "Testing the pipeline" \
  --dry-run

# With manual approval gates between stages
MANUAL_APPROVAL=true uv run python scripts/orchestrate.py \
  --title "Sensitive feature" \
  --description "Requires human review between stages"

# Start the monitoring dashboard
uv run python scripts/run_dashboard.py
# Open http://localhost:8080
```

### CLI Options

| Flag               | Description                                         |
|--------------------|-----------------------------------------------------|
| `--title`          | Feature/issue title                                 |
| `--description`    | Feature/issue description                           |
| `--issue-type`     | `feature`, `bug`, or `refactor` (default: `feature`)|
| `--repo-path`      | Path to target repository for code analysis         |
| `--jira-ticket`    | Jira ticket ID (e.g., `SHIP-123`)                   |
| `--github-issue`   | GitHub issue ref (URL, `owner/repo#N`)              |
| `--dry-run`        | Use mock data instead of real API calls             |
| `--output-dir`     | Save all artifacts to this directory                |
| `--session-id`     | Session ID (used by dashboard web UI)               |
| `--debug`          | Enable debug logging                                |

---

## 9. Output Artifacts

When `--output-dir` is specified, the pipeline saves all generated artifacts to
a structured directory:

```
output/
+-- design/
|   +-- design_analysis.md        # Architectural analysis and impact assessment
|   +-- implementation_plan.md    # Step-by-step implementation plan
|
+-- code/
|   +-- pkg/
|       +-- timeout/
|           +-- timeout.go        # Generated production code
|           +-- types.go          # Type definitions
|
+-- tests/
|   +-- unit/
|   |   +-- timeout_test.go       # Unit tests
|   +-- integration/
|   |   +-- timeout_suite_test.go # Integration tests (Ginkgo)
|   +-- e2e/
|       +-- timeout_e2e_test.go   # End-to-end tests
|
+-- docs/
|   +-- pr_description.md         # Pull request description
|   +-- pr_summary.md             # PR summary for reviewers
|   +-- release_notes.md          # Release notes entry
|
+-- state.json                    # Complete pipeline state (JSON-serializable fields)
```

The `state.json` file contains the full pipeline state at completion, useful for
debugging or post-processing. Path traversal in artifact names is detected and
rejected (files with unsafe paths are skipped with a warning).

---

## 10. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Sequential orchestrator over LangGraph | Simpler, explicit control flow, fewer dependencies. The earlier LangGraph implementation added complexity without proportional benefit for a linear pipeline. |
| TypedDict + Pydantic hybrid | TypedDict gives flexibility for state passing between stages (not all fields are present at all times). Pydantic enforces strict validation at stage boundaries to catch malformed outputs early. |
| Per-stage prompt files | Each stage has its own prompt file in `prompts/`. This makes prompts maintainable, diff-friendly, and independently overridable via `repos.yaml`. Replaced a monolithic 43KB prompt file. |
| Heartbeat-based dashboard | Decoupled, non-blocking, resilient. Dashboard failures never affect pipeline execution. The push model (stages emit heartbeats) is simpler than polling. |
| Review gate with retry loop | Automated quality improvement without human intervention. Max iterations prevent infinite loops. Unresolved findings are logged, not swallowed. |
| Multi-layer security | Defense in depth: PII redaction at input, prompt injection detection at prompt assembly, output sanitization at output. Each layer can be independently toggled. |
| Code review as gate, not stage | Code review validates development output rather than producing new artifacts. Modeling it as a gate makes the retry loop (develop -> review -> develop) natural. |
| Shell command gates from repos.yaml | Build/lint/test commands are project-specific. Defining them in repos.yaml makes the pipeline portable across projects without code changes. |
| Deferred imports in orchestrator | Stage runner imports happen inside methods, not at module level. This avoids circular dependencies and keeps startup fast. |
| Fail-closed security defaults | All security layers (PII, prompt guard, output sanitizer) default to enabled. Developers must explicitly opt out, reducing the risk of accidental data exposure. |

---

## 11. Extending the System

### Adding a New Stage

1. **Create the stage runner** in `stages/mystage.py`:

   ```python
   def run_mystage(state: dict, **kwargs) -> dict:
       client = get_anthropic_client()
       response = client.messages.create(
           model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
           system=MY_STAGE_PROMPT,
           messages=[{"role": "user", "content": build_context(state)}],
       )
       return parse_response(response.content[0].text)
   ```

2. **Create the prompt** in `prompts/mystage.py`:

   ```python
   MY_STAGE_PROMPT = """You are a ... [stage-specific instructions]"""
   ```

3. **Add a Pydantic output model** in `models/stage_outputs.py`:

   ```python
   class MyStageOutput(BaseModel):
       result_field: str = Field(..., min_length=10)
   ```

4. **Add a validator** in `stages/validators.py`:

   ```python
   def validate_mystage_output(state: dict) -> ValidationResult:
       # Validate required fields
       ...
   ```

5. **Wire into the orchestrator** in `orchestrator/workflow.py`:

   - Add a `_run_mystage()` method
   - Add the stage call in `run()` with validation and heartbeat
   - Add `"mystage"` to `VALID_STAGES` in `config/repo_schema.py`

### Supporting a New Language

The pipeline's language awareness comes from two places:

1. **Prompt files** -- Change the system prompts to target a different language:

   ```yaml
   # repos.yaml
   prompts:
     develop: "You are a Python developer. Generate Django code..."
     test: "Generate pytest tests with fixtures and parametrize..."
   ```

2. **Command gates** -- Define language-appropriate build/lint/test commands:

   ```yaml
   repos:
     - path: /home/user/git/my-python-project
       language: python
       commands:
         lint: "ruff check ."
         test: "pytest tests/ -v --cov=src"
   ```

### Adding an Integration

Follow the thin-wrapper pattern used by the existing integrations:

```python
# integrations/my_service.py

def fetch_data(identifier: str) -> dict[str, Any]:
    """Fetch data and map to pipeline state fields."""
    if os.getenv("DRY_RUN", "").lower() == "true":
        return _mock_fetch(identifier)
    return _live_fetch(identifier)

def _live_fetch(identifier: str) -> dict[str, Any]:
    # Actual API call
    ...

def _mock_fetch(identifier: str) -> dict[str, Any]:
    # Return mock data for dry-run mode
    ...
```

Key integration patterns:

- Always support `DRY_RUN` mode with mock data
- Return a dict that maps directly to `WorkflowState` fields
- Keep the integration module thin -- business logic belongs in stage runners
- Handle connection errors gracefully (integrations should be non-blocking where possible)

---

## 12. MVP Validation Results

The following results were captured during the MVP proof run validating the
refactored pipeline architecture.

### Pipeline Execution (Dry-Run Mode)

| Metric              | Result                                                  |
|---------------------|---------------------------------------------------------|
| Pipeline stages     | 5/5 complete (Design, Develop, Review gate, Testing, Docs) |
| Artifacts produced  | 21+ files (design analysis, 11 code files, 5 test files, docs) |
| Review gate         | PASS (1 suggestion-level finding, non-blocking)          |
| Command gates       | Build/lint/test commands loaded from repos.yaml          |
| Stage skipping      | Verified (6/6 configuration tests pass)                  |
| Approval config     | Working (required_stages and auto_approve from repos.yaml)|
| Duration            | ~7 minutes (dry-run with mock API responses)             |

### Test Coverage

| Metric               | Count                                      |
|----------------------|--------------------------------------------|
| Total tests          | 781+                                       |
| Workflow tests       | 26 (stage skipping, approvals, config)     |
| Quality gate tests   | 25                                         |
| Docs stage tests     | 46                                         |
| Import errors        | 0 (after full restructure)                 |

### Architecture Components Verified

| Component          | Path                      | Status    |
|--------------------|---------------------------|-----------|
| Workflow runner    | `orchestrator/workflow.py` | Verified  |
| Stage runners      | `stages/`                  | Verified  |
| Prompts            | `prompts/`                 | Verified  |
| Quality gates      | `orchestrator/gates.py`    | Verified  |
| Output contracts   | `models/`                  | Verified  |
| Integrations       | `integrations/`            | Verified  |
| Repo config        | `config/repo_schema.py`    | Verified  |

---

## 13. Future Roadmap

| Item                                  | Status         | Notes                                            |
|---------------------------------------|----------------|--------------------------------------------------|
| Claude Code Agent SDK integration     | Spike complete | Replace direct API calls with Agent SDK for better tool use and streaming |
| Token usage tracking and cost analysis| Planned        | Instrument API calls with token counts and cost estimates |
| Prompt overrides from repos.yaml      | Schema ready   | `PromptOverrides` model defined; not yet consumed by stage runners |
| Enhanced RAG for all stages           | Planned        | Currently docs-only; extend to design and development stages |
| Multi-language support beyond Go      | In progress    | Architecture supports it via repos.yaml; needs language-specific prompt libraries |
| Dashboard live verification           | Deferred       | Heartbeat emission code exists; needs end-to-end verification with live dashboard |
| Parallel stage execution              | Evaluating     | Testing and docs stages could run in parallel after review gate passes |
| Artifact persistence and versioning   | Future         | Store artifacts in a durable location with version tracking |

---

## License

This project is developed as part of the OpenShift Builds ecosystem. See the
repository root for license details.
