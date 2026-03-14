# Authentication & System Flow

This document covers how requests move through the multi-agent pipeline and how to configure
authentication for the Claude AI backend that powers each agent.

## System Flow Overview

A user request enters the system as an issue title and description. The LangGraph orchestrator
initializes a shared state object and routes it through four specialized agents in sequence.
Each agent reads from the shared state, calls the Claude API, and writes its outputs back
to state before passing control to the next agent. The dashboard receives a heartbeat at the
start and end of each phase so you can monitor progress in real time.

```
User Request (issue title + description)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LangGraph Orchestrator                         │
│                         agents/graph.py                             │
│                                                                     │
│  Generate session ID → Initialize AgentState → Emit heartbeat      │
│                                                                     │
│  ┌────────────┐   ┌─────────────┐   ┌───────────┐   ┌──────────┐  │
│  │   Design   │──▶│ Development │──▶│  Testing  │──▶│   Docs   │  │
│  │   Agent    │   │    Agent    │   │   Agent   │   │  Agent   │  │
│  └────────────┘   └─────────────┘   └───────────┘   └──────────┘  │
│        │                │                 │               │         │
│        └────────────────┴─────────────────┴───────────────┘         │
│                           Heartbeats to Dashboard                   │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Dashboard Backend                              │
│                    FastAPI + SQLite                                  │
│                   dashboard/backend.py                              │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Dashboard Frontend                             │
│             HTML + JavaScript (3-second auto-refresh)               │
│             Shows: session list, phase badges, context usage        │
└─────────────────────────────────────────────────────────────────────┘
```

### State Transitions

The `current_phase` field in `AgentState` controls routing between nodes:

```
init → design_complete → develop_complete → testing_complete → done
                                                    │
                                                  error  (any phase)
```

When an agent raises an unhandled exception, the node sets `current_phase = "error"`, emits
an error heartbeat, and the conditional router sends the workflow to `END`. The final state
contains the error string so you can diagnose the failure.

---

## Agent Flow Details

### 1. Orchestrator (LangGraph)

**File:** `agents/graph.py`

**What it receives:** Issue title, description, and optional repository path from the CLI
(`scripts/orchestrate.py`).

**What it does:**
1. Generates a UUID session ID.
2. Initializes `AgentState` with all fields set to empty defaults.
3. Emits an initial heartbeat to the dashboard to register the session.
4. Invokes the compiled `StateGraph`, which drives execution through each node.
5. Returns the final, fully-populated state dictionary to the caller.

**What it passes on:** The complete `AgentState` is passed to the Design node first. Every
subsequent node receives the accumulated state including all prior agents' outputs.

**Key function:**
```python
def orchestrate(title: str, description: str, repo_path: str = None, issue_type: str = "feature") -> Dict[str, Any]:
```

---

### 2. Design Agent

**File:** `agents/design_agent.py`

**What it receives from the orchestrator:**
- `issue_title` - The feature or bug title
- `issue_description` - Full description of what needs to be built or fixed
- `repo_path` - Optional path to the Shipwright repository for code analysis

**What it does:**
1. Initializes the Claude client via `config/auth_config.py`.
2. If `repo_path` is set, searches the repository for API types (`*_types.go`),
   controllers, CRDs, and package structure.
3. Loads Shipwright component definitions from `config/shipwright_components.py`.
4. Calls Claude API (`claude-sonnet-4-20250514`, 8,000 max tokens) with a prompt that
   combines the issue, component context, and repository findings.
5. Parses the response into structured sections.
6. Sets `current_phase = "design_complete"` and emits a heartbeat.

**What it produces:**

| Output field           | Type        | Description                                  |
|------------------------|-------------|----------------------------------------------|
| `design_analysis`      | `str`       | Full design document in Markdown             |
| `impacted_components`  | `list[str]` | Names of Shipwright components affected      |
| `risks`                | `list[str]` | Identified risks from the design             |
| `acceptance_criteria`  | `list[str]` | Testable completion criteria                 |
| `implementation_plan`  | `list[str]` | Ordered implementation steps                 |

---

### 3. Development Agent

**File:** `agents/go_k8s_developer.py`

**What it receives from the Design Agent:**
- `issue_title`, `design_analysis`, `implementation_plan` (required)
- `impacted_components`, `acceptance_criteria`, `risks` (optional but used when present)
- `session_id` for logging

**What it does:**
1. Validates that required context fields are present.
2. Emits a `development_start` heartbeat.
3. Builds a prompt that includes the design analysis, implementation plan, security
   requirements (TLS 1.3, no hardcoded secrets, input validation), and code generation
   instructions.
4. Calls Claude API (`claude-sonnet-4-20250514`, 16,000 max tokens, temperature 0.2 for
   deterministic code output).
5. Parses the response into file paths and Go code blocks.
6. Emits a `development_complete` heartbeat and sets `current_phase = "develop_complete"`.

**What it produces:**

| Output field      | Type             | Description                                        |
|-------------------|------------------|----------------------------------------------------|
| `code_files`      | `list[dict]`     | Each dict has `path`, `content`, `description`     |
| `test_files`      | `list[dict]`     | Each dict has `path` and `content`                 |
| `code_changes`    | `dict[str, str]` | File path mapped to change description             |
| `files_modified`  | `list[str]`      | Flat list of modified file paths                   |
| `pr_description`  | `str`            | Pull request description with "Generated by AI"    |
| `security_notes`  | `list[str]`      | Security considerations from the implementation    |
| `dependencies`    | `list[str]`      | New Go module dependencies required                |
| `next_steps`      | `list[str]`      | Recommended follow-up actions                      |

---

### 4. Testing Agent

**File:** `agents/testing_agent.py`

**What it receives from the Development Agent:**
- `design_analysis`, `impacted_components`, `acceptance_criteria` (required)
- `issue_title`, `issue_description`, `implementation_plan`, `risks` (optional)
- `session_id` for logging

**What it does:**
1. Scans the issue description and design for Shipwright-specific patterns (build
   strategies such as Buildpacks or S2I, source types such as Git or Bundle, output
   types, and security contexts).
2. Builds a testing prompt that maps acceptance criteria to test scenarios and requests
   Ginkgo v2 test code.
3. Calls Claude API (`claude-sonnet-4-20250514`, 16,000 max tokens).
4. Parses the response into a test plan, YAML test specifications, and Go test files
   organized by type (unit, integration, E2E).
5. Sets `current_phase = "testing_complete"` and emits a heartbeat.

**What it produces:**

| Output field          | Type             | Description                                       |
|-----------------------|------------------|---------------------------------------------------|
| `test_plan`           | `str`            | Human-readable test strategy document             |
| `test_specifications` | `dict`           | Structured YAML specs with scenario IDs           |
| `unit_tests`          | `dict[str, str]` | File path mapped to Ginkgo v2 unit test code      |
| `integration_tests`   | `dict[str, str]` | File path mapped to Ginkgo v2 integration tests   |
| `e2e_tests`           | `dict[str, str]` | File path mapped to Ginkgo v2 E2E tests           |
| `test_summary`        | `str`            | Count and summary of generated tests              |
| `coverage_analysis`   | `str`            | Mapping of tests to acceptance criteria           |
| `patterns_detected`   | `dict`           | Detected Shipwright patterns (strategies, etc.)   |

---

### 5. Documentation Agent

**File:** `agents/docs_agent.py`

**What it receives from the Testing Agent:**
All prior outputs are available, including `design_analysis`, `code_changes`,
`files_modified`, `test_results`, `test_summary`, `issue_title`, `issue_description`,
`issue_type`, and `repo_path`.

**What it does:**
1. If `repo_path` and RAG are enabled, searches Shipwright documentation for related
   content, extracts code examples from modified files, and finds API usage patterns.
2. If `input_files` are specified, reads those files from the repository.
3. Builds a combined context message from all previous agent outputs plus RAG results.
4. Calls Claude API (`claude-sonnet-4-20250514`, 8,192 max tokens, temperature 0.3 for
   consistent documentation style).
5. Parses the response into separate documentation sections.
6. Sets `current_phase = "done"` and emits a final heartbeat.

**What it produces (final output):**

| Output field           | Type             | Description                                     |
|------------------------|------------------|-------------------------------------------------|
| `pr_summary`           | `str`            | Pull request description                        |
| `release_notes`        | `str`            | User-facing changelog entry                     |
| `docs_changes`         | `dict[str, str]` | Documentation file paths to change descriptions |
| `upgrade_notes`        | `str`            | Migration guidance for existing users           |
| `known_limitations`    | `str`            | Edge cases and current restrictions             |
| `jtbd_documentation`   | `str`            | Jobs-to-be-Done user documentation              |
| `ship_document`        | `str`            | SHIP design document (if requested)             |
| `high_level_design`    | `str`            | Architectural overview                          |

---

### 6. Dashboard

**Files:** `dashboard/heartbeat.py`, `dashboard/backend.py`, `dashboard/frontend/index.html`

**How it receives heartbeats:**

Each agent calls `emit_heartbeat(agent_name, state)` at the start and end of its phase.
The `HeartbeatEmitter` sends an HTTP POST to `/api/heartbeat` on the dashboard backend.
If the dashboard is unreachable, the heartbeat fails silently so it does not block the
workflow.

```python
# Called inside each agent node
emit_heartbeat("design", {**state, "phase": "design_complete"})
```

**What it monitors:**

- Active sessions (one per `orchestrate()` call)
- Current phase per agent (design, develop, testing, docs, done, error)
- Context window usage percentage
- Model name in use
- Impacted components and risk count
- Timestamp of last update

The frontend polls `/api/sessions` every 3 seconds and re-renders the session list
automatically.

---

## Authentication Methods

The system reads authentication configuration at startup through `config/auth_config.py`.
It checks environment variables in priority order and initializes the appropriate client.

### Authentication

The system uses Google Vertex AI for authentication. Set the `ANTHROPIC_VERTEX_PROJECT_ID`
environment variable and authenticate via gcloud. If the variable is not set, the system
raises a `ValueError`.

---

### Google Vertex AI

Vertex AI uses Application Default Credentials (ADC) managed by the Google Cloud CLI.
No API key is stored or transmitted.

**When to use:** Production environments, teams with GCP access, or when you want GCP
IAM to control access rather than shared API keys.

**Setup:**

```bash
# Step 1: Install Google Cloud CLI (https://cloud.google.com/sdk/docs/install)

# Step 2: Authenticate your account
gcloud auth application-default login

# Step 3: Set your billing project
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID

# Step 4: Enable the Vertex AI API
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID

# Step 5: Grant IAM permissions (if not already granted)
gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

**Environment variables:**

```bash
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=us-east5   # Optional, defaults to us-east5
```

**How the system uses ADC:**

1. Reads `ANTHROPIC_VERTEX_PROJECT_ID` from environment.
2. Uses the ADC token cached by `gcloud auth application-default login`.
3. Routes all Claude API requests through the Vertex AI endpoint in the specified region.
4. GCP manages token refresh automatically.

**Verify your credentials are active:**

```bash
gcloud auth application-default print-access-token
gcloud auth application-default describe
```

**Available regions:**

| Region            | Notes                |
|-------------------|----------------------|
| `us-east5`        | Default, recommended |
| `us-central1`     | US central           |
| `europe-west1`    | EU west              |
| `asia-southeast1` | Asia Pacific         |

---

## Environment Variables Reference

All variables are optional unless marked required. Set them in your `.env` file or export
them before running the orchestrator.

### Authentication

| Variable                       | Required | Description                                    | Example                                        |
|--------------------------------|----------|------------------------------------------------|------------------------------------------------|
| `ANTHROPIC_VERTEX_PROJECT_ID`  | Yes      | Your GCP project ID                            | `my-gcp-project`                               |
| `CLOUD_ML_REGION`              | No       | GCP region (defaults to `us-east5`)            | `us-east5`                                     |

### Claude Model

| Variable           | Default                    | Description                          |
|--------------------|----------------------------|--------------------------------------|
| `CLAUDE_MODEL`     | `claude-sonnet-4-20250514` | Claude model version to use          |
| `CLAUDE_MAX_TOKENS`| `8000`                     | Default max tokens for responses     |

### Repository

| Variable                    | Default | Description                                              |
|-----------------------------|---------|----------------------------------------------------------|
| `SHIPWRIGHT_REPO_PATH`      | (none)  | Path to Shipwright Build repo for code analysis          |
| `OPENSHIFT_BUILDS_REPO_PATH`| (none)  | Path to OpenShift Builds repo for additional context     |

### Dashboard

| Variable             | Default                       | Description                              |
|----------------------|-------------------------------|------------------------------------------|
| `DASHBOARD_URL`      | `http://localhost:8080`       | URL where agents send heartbeats         |
| `DASHBOARD_ENABLED`  | `true`                        | Set to `false` to disable heartbeats     |
| `DASHBOARD_DB_PATH`  | `/tmp/claude/dashboard.db`    | SQLite database path for the dashboard   |

### Logging

| Variable          | Default  | Description                                         |
|-------------------|----------|-----------------------------------------------------|
| `LOG_LEVEL`       | `INFO`   | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT`      | `text`   | Log format (`text` or `json`)                       |
| `LOG_FILE_PATH`   | (none)   | Write logs to a file in addition to stdout          |

### Performance

| Variable          | Default | Description                                    |
|-------------------|---------|------------------------------------------------|
| `API_TIMEOUT`     | `60`    | Seconds before an API call times out           |
| `MAX_REPO_FILES`  | `100`   | Maximum number of repository files to analyze  |
| `CACHE_DIR`       | `.cache`| Directory for caching repository analysis      |
| `CACHE_TTL`       | `3600`  | Seconds before cached data expires             |

---

## State Management

The `AgentState` TypedDict (defined in `graph/state.py`) is the single shared data
structure that flows through the entire workflow. LangGraph merges each node's return
dictionary into the running state, so every agent sees all previous agents' outputs.

### State Fields by Phase

| Category            | Fields                                                                                                 | Set by              |
|---------------------|--------------------------------------------------------------------------------------------------------|---------------------|
| **Input**           | `issue_title`, `issue_description`, `issue_type`                                                       | Orchestrator        |
| **Control**         | `session_id`, `current_phase`, `approval_status`                                                       | Orchestrator        |
| **Repository**      | `repo_path`, `target_branch`                                                                           | Orchestrator        |
| **Design outputs**  | `design_analysis`, `impacted_components`, `risks`, `acceptance_criteria`, `implementation_plan`        | Design Agent        |
| **Dev outputs**     | `code_files`, `test_files`, `code_changes`, `files_modified`, `pr_description`                         | Development Agent   |
| **Test outputs**    | `test_plan`, `test_specifications`, `unit_tests`, `integration_tests`, `e2e_tests`, `coverage_analysis`| Testing Agent       |
| **Test results**    | `test_results`, `test_summary`, `coverage_gaps`, `test_failures`                                       | Testing Agent       |
| **Docs outputs**    | `pr_summary`, `release_notes`, `docs_changes`, `upgrade_notes`, `known_limitations`, `jtbd_documentation`, `ship_document`, `high_level_design` | Docs Agent |
| **Messages**        | `messages` (LangGraph message list)                                                                    | All agents          |

### How State Flows

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
Final state returned to caller (contains all fields)
```

### State Merging

Each node returns only the fields it modifies. LangGraph merges the partial return
dictionary into the full accumulated state:

```python
# Node returns a partial update
def design_node(state: AgentState) -> Dict[str, Any]:
    return {
        "design_analysis": "...",
        "current_phase": "design_complete"
    }
# LangGraph performs: state = {**state, **design_node(state)}
```

This means the Development Agent can read `design_analysis` directly from state without
any explicit handoff — it is already present when `develop_node` is called.

---

## Troubleshooting Authentication

### Error: "No Claude authentication configured"

The `ANTHROPIC_VERTEX_PROJECT_ID` environment variable is not set.

```bash
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
```

### Error: "gcloud not authenticated" or ADC errors

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
gcloud auth application-default print-access-token  # Verify it works
```

### Error: "Vertex AI API not enabled"

```bash
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

### Error: "Permission denied" on Vertex AI

```bash
gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

### Verify current authentication type

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
