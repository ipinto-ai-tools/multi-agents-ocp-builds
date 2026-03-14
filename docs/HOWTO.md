# How To Guide - Multi-Agent OpenShift Builds

A practical guide for installing, configuring, and running the Multi-Agent OpenShift Builds system.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the System](#running-the-system)
5. [Using Each Agent](#using-each-agent)
6. [MCP Servers](#mcp-servers)
7. [Dashboard](#dashboard)
8. [Dry Run Mode](#dry-run-mode)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11 or higher | Required for type hints and performance |
| Git | 2.0 or higher | For repository operations |
| uv | Latest | Recommended Python package installer |
| Google Cloud CLI | Latest | Required for Vertex AI authentication only |

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify the installation:

```bash
uv --version
```

### Verify Python Version

```bash
python --version
# Expected: Python 3.11.x or higher
```

### Claude Authentication

The system uses Google Vertex AI for authentication. No API keys are required.

**Google Vertex AI**

Uses your existing Google Cloud credentials. No API keys required.

```bash
# Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install

# Authenticate your application credentials
gcloud auth application-default login

# Set the quota project
gcloud auth application-default set-quota-project your-gcp-project-id

# Find your project ID if needed
gcloud projects list
```

**Note:** Dry-run mode requires no authentication. See [Dry Run Mode](#dry-run-mode).

### Optional: Shipwright Repository

Providing the Shipwright Build repository enables deeper code analysis. Agents can identify specific files to modify, match existing conventions, and produce more accurate component impact analysis.

```bash
git clone https://github.com/shipwright-io/build.git /path/to/shipwright-build
```

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/muilti-agents-ocp-builds.git
cd muilti-agents-ocp-builds
```

### Step 2: Install Dependencies

**Using uv with a virtual environment (recommended for repeated use):**

```bash
uv venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Using uv sync (if pyproject.toml is configured):**

```bash
uv sync
```

**Activate the virtual environment before running any scripts:**

```bash
source .venv/bin/activate
```

### Step 3: Configure Environment Variables

```bash
cp .env.example .env
# Open .env in your editor and configure authentication
```

### Step 4: Verify Installation

Run these commands with your virtual environment activated:

```bash
python -c "from agents.design_agent import run_design; print('OK design agent')"
python -c "from agents.go_k8s_developer import run_development; print('OK development agent')"
python -c "from agents.testing_agent import run_testing; print('OK testing agent')"
python -c "from agents.docs_agent import run_docs; print('OK docs agent')"
```

Expected output:

```
OK design agent
OK development agent
OK testing agent
OK docs agent
```

---

## Configuration

### Environment File (.env)

Copy `.env.example` to `.env` and configure the settings below.

#### Authentication

```bash
# No API key needed - uses gcloud authentication
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=us-east5   # Optional, defaults to us-east5
```

#### Repository Paths (optional)

Providing these paths enables the agents to analyze actual code:

```bash
SHIPWRIGHT_REPO_PATH=/path/to/shipwright-build
OPENSHIFT_BUILDS_REPO_PATH=/path/to/openshift-builds
```

#### Claude Model Settings

```bash
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=8000
```

#### Logging

```bash
LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=text          # json or text
LOG_FILE_PATH=/tmp/muilti-agents-ocp-builds.log
```

#### Dashboard

```bash
DASHBOARD_URL=http://localhost:8080    # Where agents send updates
DASHBOARD_ENABLED=true                 # Toggle heartbeat emissions
DASHBOARD_DB_PATH=/tmp/claude/dashboard.db
```

#### Performance Tuning

```bash
API_TIMEOUT=60        # API request timeout in seconds
MAX_REPO_FILES=100    # Maximum repository files to analyze
CACHE_DIR=.cache
CACHE_TTL=3600        # Cache lifetime in seconds
```

#### Agent Behavior

```bash
ENABLE_REPO_ANALYSIS=true
DESIGN_OUTPUT_FORMAT=markdown    # markdown or json
```

### Security Practices

- Never commit `.env` to version control (it is already listed in `.gitignore`)
- Set restrictive file permissions: `chmod 600 .env`
- Rotate gcloud credentials regularly

---

## Running the System

### Full Workflow (All Four Agents)

The orchestrator runs Design, Development, Testing, and Documentation agents in sequence. Each agent receives the outputs from previous agents through shared state.

**With virtual environment activated:**

```bash
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds"
```

**One-time use without activating the virtual environment:**

```bash
uv run --with anthropic --with langgraph --with langchain-core \
       --with python-dotenv --with GitPython --with pyyaml \
       python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds"
```

### What the Workflow Produces

Running the orchestrator produces four outputs that print to the console when the workflow completes:

1. **Design Analysis** - Component analysis, risks, acceptance criteria, and implementation plan
2. **Production Code** - Go code for Kubernetes/OpenShift with TLS 1.3 and security best practices
3. **Test Suite** - Ginkgo v2 tests (unit, integration, E2E) with data-driven patterns
4. **Documentation** - PR summary, release notes, and Jobs-to-be-Done user documentation

### Workflow Phases

```text
Issue → Design Agent → Development Agent → Testing Agent → Docs Agent → Done
          |               |                    |               |
          v               v                    v               v
        Plan            Code                 Tests           Docs
```

State transitions:

```
init → design_complete → develop_complete → testing_complete → done
                                                             ↓
                                                           error (on failure)
```

### Workflow with Dashboard

Monitor progress in real-time by starting the dashboard before running the orchestrator:

```bash
# Terminal 1: start the dashboard
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py

# Terminal 2: run the workflow
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds"
```

Open http://localhost:8080 to see real-time progress.

### Real-World Examples

**Analyze a feature request:**

```bash
uv run python scripts/orchestrate.py \
  --title "Implement build output caching" \
  --description "Allow BuildRuns to cache intermediate build layers to speed up subsequent builds. Should support OCI registry-based caching."
```

**Analyze a bug report:**

```bash
uv run python scripts/orchestrate.py \
  --title "BuildRun stuck in Running state" \
  --description "BuildRuns remain Running even after pod completes. Status reconciliation fails."
```

**With repository context for deeper analysis:**

```bash
export SHIPWRIGHT_REPO_PATH=/home/user/git/shipwright-build

uv run python scripts/orchestrate.py \
  --title "Add SSH key support for private Git repos" \
  --description "Users need to build from private Git repos using SSH authentication"
```

---

## Using Each Agent

Agents are normally invoked automatically by `scripts/orchestrate.py`. The sections below describe each agent's purpose, inputs, and outputs for advanced use cases where you need to call an agent directly.

### Design Agent

**File:** `agents/design_agent.py`
**Entry point:** `run_design(title, description, repo_path)`

Analyzes a GitHub issue and produces a comprehensive design document to guide implementation. It identifies impacted components in the Shipwright codebase, assesses risks, and creates a step-by-step implementation plan.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | str | Yes | GitHub issue title |
| `description` | str | Yes | GitHub issue description |
| `repo_path` | str | No | Path to Shipwright repository |

**Outputs:**

```python
{
    "design_analysis": str,           # Full design document in Markdown
    "impacted_components": list[str], # Component names affected
    "risks": list[str],               # Identified risks
    "acceptance_criteria": list[str], # Testable acceptance criteria
    "implementation_plan": list[str]  # Step-by-step implementation
}
```

**Design document sections:**

1. Problem Statement
2. Scope (in/out)
3. Impacted Components
4. Risks and Mitigation
5. Acceptance Criteria
6. Implementation Plan
7. Required Tests
8. Documentation Changes

**Direct invocation example:**

```python
# design_only.py
from agents.design_agent import run_design
import os

result = run_design(
    title="Add retry logic to failed builds",
    description="BuildRuns should support automatic retry on transient failures",
    repo_path=os.getenv("SHIPWRIGHT_REPO_PATH")
)

print(result["design_analysis"])
print("Impacted components:", result["impacted_components"])
print("Risks:", result["risks"])
```

```bash
uv run python design_only.py
```

**Claude API settings:**

- Model: `claude-sonnet-4-20250514`
- Max tokens: 8000
- Temperature: 1.0 (default)

**Error handling:**

- Missing authentication raises `DesignAgentError`
- API failures are logged and raise `DesignAgentError`
- Repository analysis failures fall back to component metadata only

---

### Development Agent

**File:** `agents/go_k8s_developer.py`
**Entry point:** `run_development(context, repo_path)`

Generates production-quality Go code for Kubernetes and OpenShift following strict security and quality standards. All generated code enforces TLS 1.3, avoids hardcoded secrets, and includes Go doc comments.

**Inputs (context dictionary):**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `issue_title` | str | Yes | Feature or bug title |
| `design_analysis` | str | Yes | Design document from Design Agent |
| `implementation_plan` | list[str] | Yes | Implementation steps |
| `impacted_components` | list[str] | No | Components affected |
| `acceptance_criteria` | list[str] | No | Testable criteria |
| `risks` | list[str] | No | Risks from design |

**Outputs:**

```python
{
    "code_files": list[dict],         # [{path, content, description}]
    "test_files": list[dict],         # [{path, content}]
    "code_changes": dict[str, str],   # file path → change description
    "files_modified": list[str],      # list of modified files
    "pr_description": str,            # PR description with AI footer
    "security_notes": list[str],      # Security considerations
    "dependencies": list[str],        # New dependencies required
    "next_steps": list[str]           # Recommended follow-up actions
}
```

**Code quality standards:**

- Idiomatic Go with meaningful names and focused functions
- Go doc comments on all exported methods
- TLS 1.3 enforcement where TLS configuration is added or modified
- No hardcoded secrets, tokens, or credentials
- Structured logging without sensitive data
- Table-driven unit tests with mock dependencies

**Direct invocation example:**

```python
from agents.go_k8s_developer import run_development

context = {
    "issue_title": "Add TLS 1.3 support to build controller",
    "design_analysis": "...",
    "implementation_plan": ["Step 1: ...", "Step 2: ..."]
}

result = run_development(context)

for code_file in result["code_files"]:
    print(f"File: {code_file['path']}")
    print(code_file["content"])
```

**Claude API settings:**

- Model: `claude-sonnet-4-20250514`
- Max tokens: 16000 (larger for code generation)
- Temperature: 0.2 (deterministic for code)

---

### Testing Agent

**File:** `agents/testing_agent.py`
**Entry point:** `run_testing(context)`

Generates comprehensive Ginkgo v2 test suites including unit, integration, and E2E tests with Data-Driven Testing (DDT) patterns. The agent detects Shipwright-specific patterns in the issue and design to generate context-aware tests.

**Inputs (context dictionary):**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `design_analysis` | str | Yes | Design document |
| `impacted_components` | list[str] | Yes | Affected components |
| `acceptance_criteria` | list[str] | Yes | Testable criteria |
| `issue_title` | str | No | Feature or bug title |
| `issue_description` | str | No | Detailed description |
| `implementation_plan` | list[str] | No | Implementation steps |
| `risks` | list[str] | No | Risks to test |

**Outputs:**

```python
{
    "test_plan": str,                    # Human-readable test strategy
    "test_specifications": dict,         # YAML specs with scenario IDs
    "unit_tests": dict[str, str],        # file path → Ginkgo test code
    "integration_tests": dict[str, str], # file path → Ginkgo test code
    "e2e_tests": dict[str, str],         # file path → Ginkgo test code
    "test_summary": str,                 # Summary of generated tests
    "coverage_analysis": str,            # Coverage mapping to acceptance criteria
    "patterns_detected": dict,           # Detected Shipwright-specific patterns
}
```

**Test types:**

| Type | Scope | Typical Duration | Focus |
|------|-------|-----------------|-------|
| Unit | Isolated functions with mocks | Fast (<5s) | Function logic, error handling, edge cases |
| Integration | Real Kubernetes cluster | Medium (~30s) | Controller reconciliation, webhook validation |
| E2E | Full workflow | Slow (~5m) | Complete build workflows with actual execution |

**Pattern detection:**

The agent scans the issue description and design for Shipwright-specific patterns:

```python
patterns_detected = {
    "strategies": ["kaniko", "buildkit"],    # Build strategies found
    "source_types": ["git", "bundle"],       # Source types found
    "output_types": ["image"],               # Output types found
    "security_contexts": ["nonroot"],        # Security contexts found
}
```

**Test ID format:** `BUILD-XXX-NNN` (example: `BUILD-TIMEOUT-001`)

**Generated test features:**

- Ginkgo v2 syntax with modern imports
- `DescribeTable` for parameterized data-driven tests
- Shipwright helpers: `libfactory` and `libk8s` test utilities
- `BeforeEach`/`AfterEach` for proper setup and cleanup
- `Eventually`/`Consistently` for async checks with timeouts

**Direct invocation example:**

```python
from agents.testing_agent import run_testing

context = {
    "design_analysis": "# Design: Add timeout support...",
    "impacted_components": ["buildrun_api", "buildrun_controller"],
    "acceptance_criteria": [
        "BuildRun API accepts timeout field",
        "Controller respects timeout value",
        "Build fails after timeout exceeded"
    ],
    "issue_title": "Add timeout support to BuildRun",
    "issue_description": "Users need to specify max build execution time..."
}

result = run_testing(context)

print("Test Plan:", result["test_plan"])
print("Unit test files:", list(result["unit_tests"].keys()))
print("Integration test files:", list(result["integration_tests"].keys()))
print("E2E test files:", list(result["e2e_tests"].keys()))
print("Patterns detected:", result["patterns_detected"])
```

**Claude API settings:**

- Model: `claude-sonnet-4-20250514`
- Max tokens: 16000 (larger for test code generation)

**Example test specification output:**

```yaml
scenarios:
  - id: BUILD-TIMEOUT-001
    type: unit
    description: Validate timeout field in BuildRun API
    pattern: validation
    expected: Accept valid timeout values, reject invalid

  - id: BUILD-TIMEOUT-002
    type: integration
    description: Controller respects timeout configuration
    helpers:
      - libfactory.NewBuildRun
      - libk8s.WaitForBuildRunCompletion
    expected: Build terminates after timeout exceeded
```

---

### Documentation Agent

**File:** `agents/docs_agent.py`
**Entry point:** `run_docs(context, input_files, output_format, enable_rag)`

Generates documentation artifacts from the outputs of all previous agents. Produces PR summaries, release notes, upgrade guidance, and Jobs-to-be-Done (JTBD) user documentation.

**Inputs (context dictionary):**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `design_analysis` | str | Yes | Design document |
| `code_changes` | dict | Yes | File paths to change descriptions |
| `test_results` | dict | Yes | Test execution results |
| `implementation_plan` | str | No | Implementation approach |
| `files_modified` | list[str] | No | Modified file list |
| `test_summary` | str | No | Test summary |
| `issue_title` | str | No | Original issue title |
| `issue_description` | str | No | Original issue description |
| `issue_type` | str | No | bug, feature, refactor, or docs |

**Outputs:**

```python
{
    "pr_summary": str,               # Pull request description
    "release_notes": str,            # User-facing changelog entry
    "docs_changes": dict[str, str],  # doc file path → change description
    "upgrade_notes": str,            # Version upgrade guidance
    "known_limitations": str,        # Edge cases and current restrictions
    "jtbd_documentation": str,       # Jobs-to-be-Done user documentation
    "ship_document": str,            # SHIP format design document
    "high_level_design": str,        # High-level design summary
}
```

**JTBD documentation format:**

Each job follows this structure:

```markdown
## Job: [What the user wants to accomplish]

**Context:** When [situation], I want to [motivation], so I can [outcome].

**Steps to Complete:**
1. [Concrete action with example]
2. [Concrete action with example]

**Troubleshooting:**
- [Common error and fix]

**Related Jobs:**
- [Related task]
```

**Direct invocation example:**

```python
from agents.docs_agent import run_docs

context = {
    "design_analysis": "# Design: Add timeout...",
    "code_changes": {
        "pkg/apis/build/v1/buildrun_types.go": "Added Timeout field"
    },
    "test_results": {"unit": "passed", "e2e": "passed"},
    "issue_title": "Add timeout support",
    "issue_description": "Users need build timeout configuration",
    "issue_type": "feature"
}

result = run_docs(context)

print("PR Summary:")
print(result["pr_summary"])
print("\nRelease Notes:")
print(result["release_notes"])
print("\nJTBD Documentation:")
print(result["jtbd_documentation"])
```

**Claude API settings:**

- Model: `claude-sonnet-4-20250514`
- Max tokens: 8192
- Temperature: 0.3 (lower for consistent documentation)

---

## MCP Servers

The system includes stub interfaces for future MCP server integrations. These are not yet operational but define the planned API surface.

### Status

| Server | File | Status |
|--------|------|--------|
| GitHub MCP | `mcp/github_stub.py` | Stub (interface defined, not functional) |
| Jira MCP | `mcp/jira_stub.py` | Stub (interface defined, not functional) |

### Planned GitHub MCP Capabilities

- Create and manage GitHub issues
- Create and review pull requests
- Manage GitHub Actions workflows
- Access repository metadata and file content

### Planned Jira MCP Capabilities

- Create and manage issues, stories, and epics
- Update issue status and transitions
- Add comments and attachments
- Search and filter with JQL

### Integration Path

When MCP servers become available:

1. Set up MCP servers for GitHub and Jira
2. Implement MCP client connections in the stub files under `mcp/`
3. Add MCP configuration to the test CLI (`scripts/test_agents.py`)
4. Update dry-run mode to mock MCP responses
5. Add MCP-specific tests to the dashboard testing suite

### Future Usage (Planned)

```bash
# Test with GitHub MCP server
uv run python scripts/test_agents.py \
  --e2e \
  --with-github-mcp \
  --title "Add timeout" \
  --description "..."

# Dry-run with both MCP servers mocked
uv run python scripts/test_agents.py \
  --e2e \
  --dry-run \
  --with-github-mcp \
  --with-jira-mcp
```

---

## Dashboard

### Overview

The dashboard is a web application that shows agent workflow progress in real-time. It auto-refreshes every 3 seconds and displays context window usage, agent phase status, and session history.

Agents send status updates (heartbeats) to the dashboard automatically as they work. No additional configuration is required.

### Starting the Dashboard

```bash
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py
```

The dashboard is then available at:

| Endpoint | URL |
|----------|-----|
| Web UI | http://localhost:8080 |
| API documentation | http://localhost:8080/docs |
| Health check | http://localhost:8080/api/health |

### What the Dashboard Shows

Each session card displays:

- **Phase progress**: Current workflow phase (design, development, testing, docs, done)
- **Context usage**: Percentage of Claude's context window used (watch for >80%)
- **Components**: Shipwright components being analyzed
- **Model**: Claude model in use
- **Last update**: When the agent last reported status

**Example session card:**

```
Session abc123
Issue: Add timeout support to BuildRun
Type: feature

Design Agent     Complete
Development      Complete
Testing          In Progress
Documentation    Waiting

Context: 64%
Model: claude-sonnet-4
Last update: 2s ago
```

### Session Cleanup

The dashboard stores session data in a SQLite database. Sessions are automatically cleaned up every 6 hours (completed sessions older than 24 hours are deleted).

**Manual cleanup:**

```bash
# Delete completed sessions older than 24 hours (default)
curl -X DELETE http://localhost:8080/api/sessions/cleanup

# Delete completed sessions older than a custom age
curl -X DELETE "http://localhost:8080/api/sessions/cleanup?max_age_hours=12"

# Delete all completed sessions immediately (useful before demos)
curl -X DELETE http://localhost:8080/api/sessions/completed
```

**Check database size:**

```bash
ls -lh /tmp/claude/dashboard.db
```

**Count active sessions:**

```bash
curl http://localhost:8080/api/sessions | jq 'length'
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/heartbeat` | Receive agent heartbeat |
| GET | `/api/sessions` | List all sessions |
| GET | `/api/sessions/{id}` | Get specific session details |
| DELETE | `/api/sessions/cleanup` | Clean up old completed sessions |
| DELETE | `/api/sessions/completed` | Clear all completed sessions |
| GET | `/api/health` | Health check |

### Dashboard Configuration

All settings are optional - defaults work for local development.

```bash
DASHBOARD_URL=http://localhost:8080    # Where agents send updates
DASHBOARD_ENABLED=true                 # Toggle heartbeat emissions
DASHBOARD_DB_PATH=/tmp/claude/dashboard.db
```

### Log Locations

```
logs/
├── agents/
│   ├── design_agent.log
│   ├── go_k8s_developer.log
│   ├── testing_agent.log
│   └── docs_agent.log
└── sessions/
    └── {session-id}/
        ├── design_agent.log
        ├── development_agent.log
        ├── testing_agent.log
        └── docs_agent.log
```

---

## Dry Run Mode

Dry run mode lets you test the system without making any Claude API calls. It uses pre-configured mock responses so no authentication is needed.

### When to Use Dry Run Mode

- Development: test code changes without API usage or cost
- CI/CD pipelines: run validation without credentials
- Debugging: isolate logic issues from API behavior
- Learning: understand the workflow without API costs

### What is Mocked

| Component | Behavior in Dry Run |
|-----------|---------------------|
| Design Agent | Returns mock design analysis |
| Testing Agent | Returns mock test plans and Ginkgo code |
| Docs Agent | Returns mock PR summary and release notes |
| Heartbeat emissions | Logged but not sent to dashboard |
| Dashboard API checks | Skipped |

### Running Dry Run

**Test all four agents in sequence:**

```bash
uv run python scripts/test_agents.py --e2e --dry-run
```

**Test all agents with verbose logging:**

```bash
uv run python scripts/test_agents.py --e2e --dry-run --debug
```

**Test a single agent:**

```bash
# Design agent
uv run python scripts/test_agents.py --agent design --dry-run --debug

# Testing agent
uv run python scripts/test_agents.py --agent testing --dry-run --debug

# Docs agent
uv run python scripts/test_agents.py --agent docs --dry-run --debug
```

### Test CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--agent {design\|testing\|docs}` | Test a specific agent | - |
| `--e2e` | Test complete E2E workflow | - |
| `--dashboard` | Test dashboard functionality | - |
| `--title TEXT` | Issue title | Default mock title |
| `--description TEXT` | Issue description | Default mock description |
| `--dry-run` | Use mock responses | false |
| `--debug` | Enable verbose logging | false |
| `--output-dir PATH` | Artifact output directory | `/tmp/claude/agent-tests` |

### Output Artifacts

All test artifacts are saved to the output directory:

| File | Description |
|------|-------------|
| `test_YYYYMMDD_HHMMSS.log` | Complete test log with timestamps |
| `design_output.json` | Design agent structured output |
| `testing_output.json` | Testing agent structured output |
| `docs_output.json` | Docs agent structured output |
| `e2e_result.json` | Complete E2E workflow results |
| `dashboard_test_results.json` | Dashboard test results |

**Inspect artifacts:**

```bash
cat /tmp/claude/agent-tests/design_output.json | jq .
cat /tmp/claude/agent-tests/e2e_result.json | jq .
```

### Dashboard Dry Run

```bash
# Start the dashboard in one terminal
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py

# Test dashboard components in another terminal
uv run python scripts/test_agents.py --dashboard --debug
```

**Without a running dashboard (dry-run skips backend check):**

```bash
uv run python scripts/test_agents.py --dashboard --dry-run
```

### CI/CD Integration

Dry run mode is designed for use in CI pipelines:

```bash
# Returns exit code 0 on success, 1 on failure
uv run python scripts/test_agents.py --e2e --dry-run

# Store results for inspection
uv run python scripts/test_agents.py --e2e --dry-run \
  --output-dir ./ci-results/$(date +%Y%m%d-%H%M%S)
```

---

## Troubleshooting

### Authentication Not Configured

**Error:**

```
DesignAgentError: No Claude authentication configured
```

**Solutions:**

Set up Vertex AI authentication:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project your-gcp-project-id
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
```

Or use dry-run mode (no authentication needed):

```bash
uv run python scripts/test_agents.py --e2e --dry-run
```

---

### Import Errors

**Error:**

```
ImportError: anthropic library is required
```

**Solution:**

```bash
# Install all dependencies
uv venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify a specific package
uv run --with anthropic python -c "import anthropic; print('OK')"
```

---

### Repository Path Not Found

**Error:**

```
RepositorySearchError: Repository path does not exist: /path/to/repo
```

**Solution:**

```bash
# Verify the path exists
ls -la /path/to/repo

# Clone the repository if missing
git clone https://github.com/shipwright-io/build.git /path/to/repo

# Update .env with the correct path
echo "SHIPWRIGHT_REPO_PATH=/path/to/repo" >> .env
```

---

### Rate Limit Errors

**Error:**

```
Claude API call failed: rate_limit_error
```

**Solutions:**

```bash
# Check your quota in the GCP billing console

# Increase timeout in .env
echo "API_TIMEOUT=120" >> .env
```

The system includes built-in retry with exponential backoff.

---

### Missing Context Keys in Docs Agent

**Error:**

```
RuntimeError: Missing required context keys
```

**Solution:**

Ensure all required keys are present in the context:

```python
context = {
    "design_analysis": "...",  # Required
    "code_changes": {},         # Required
    "test_results": {},         # Required
    # Optional: test_summary, issue_title, issue_description, issue_type
}
```

---

### Git Operations Failing

**Error:**

```
GitOpResult.error: Directory already exists: /tmp/claude/repo
```

**Solution:**

```python
from tools.git_ops import GitOps

ops = GitOps()
ops.cleanup_repository("/tmp/claude/repo")
ops.clone_repository("https://github.com/org/repo.git")
```

---

### Dashboard Not Receiving Heartbeats

**Symptoms:** Sessions not appearing in the dashboard UI.

**Checks:**

```bash
# Confirm the dashboard is running
curl http://localhost:8080/api/health

# Verify heartbeats are enabled
grep DASHBOARD_ENABLED .env

# Check the database exists
ls -l /tmp/claude/dashboard.db

# View recent cleanup activity
grep "cleanup" logs/dashboard/dashboard.log | tail -20
```

---

### High Context Usage (>80%)

When agents report context usage above 80%, they may run out of space before completing.

**Solutions:**

- Break the task into smaller, more focused issues
- Reduce the scope of component analysis
- Shorten the issue description
- Reduce the maximum repository files scanned:

```bash
echo "MAX_REPO_FILES=50" >> .env
```

---

### Performance: Slow Repository Analysis or API Timeouts

**Solutions:**

Reduce repository scan scope:

```bash
echo "MAX_REPO_FILES=50" >> .env
```

Enable caching:

```bash
echo "CACHE_DIR=.cache" >> .env
echo "CACHE_TTL=7200" >> .env
```

Use sparse checkout when working with large repositories:

```python
from tools.git_ops import GitOps

ops = GitOps()
ops.clone_repository(
    "https://github.com/org/large-repo.git",
    sparse_checkout=["pkg/apis", "pkg/controller"]
)
```

Increase API timeout:

```bash
echo "API_TIMEOUT=120" >> .env
```

---

### Enabling Debug Logging

Enable verbose output to trace issues through the workflow:

```bash
# Set in .env
LOG_LEVEL=DEBUG
LOG_FILE_PATH=/tmp/muilti-agents-debug.log
```

Then run and inspect the logs:

```bash
uv run python scripts/orchestrate.py --title "Test" --description "Debug run"
tail -f /tmp/muilti-agents-debug.log
```

For test CLI:

```bash
uv run python scripts/test_agents.py --agent design --dry-run --debug
cat /tmp/claude/agent-tests/test_*.log
```
