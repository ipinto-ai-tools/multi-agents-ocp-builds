# Multi-Agent OpenShift Builds - HOWTO Manual

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Dashboard](#dashboard)
7. [Architecture](#architecture)
8. [Agent Details](#agent-details)
9. [Jobs-to-be-Done (JTBD) Documentation](#jobs-to-be-done-jtbd-documentation)
10. [Tools Reference](#tools-reference)
11. [Examples](#examples)
12. [Troubleshooting](#troubleshooting)
13. [Development](#development)
14. [FAQ](#faq)

---

## Overview

### What is this system?

The Multi-Agent OpenShift Builds system is a **LangGraph-based orchestration framework** that uses Claude AI to analyze GitHub issues and generate comprehensive design documentation for the Shipwright Build project on OpenShift.

### What does it do?

The system automates the **design analysis and documentation generation** workflow:

1. **Analyzes** feature requests or bug reports
2. **Identifies** impacted components in the Shipwright codebase
3. **Assesses** risks and compatibility concerns
4. **Generates** implementation plans with acceptance criteria
5. **Produces** documentation artifacts (PR summaries, release notes)

### Who should use it?

- **Development teams** working on Shipwright Build
- **Technical leads** planning feature implementations
- **Maintainers** reviewing and documenting changes
- **Contributors** understanding component impact

---

## Prerequisites

### Required Software

- **Python**: 3.11 or higher
- **uv**: Python package installer (recommended)
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Git**: 2.0 or higher
- **Google Cloud CLI**: For Vertex AI authentication (recommended)
  ```bash
  # Install gcloud CLI - see: https://cloud.google.com/sdk/docs/install

  # Authenticate
  gcloud auth application-default login
  gcloud auth application-default set-quota-project your-gcp-project-id
  ```

### Claude Authentication

Choose one of the following authentication methods:

**Option 1: Google Vertex AI (Recommended)**

- **No API keys needed!** Uses gcloud authentication
- **GCP Project ID**: Your Google Cloud project ID
- **Region**: GCP region (optional, defaults to us-east5)
- Authenticate via: `gcloud auth application-default login`
- Find your project ID: `gcloud projects list`

**Option 2: Individual API Key**

- **Anthropic API Key**: Personal API key from [Anthropic Console](https://console.anthropic.com/settings/keys)
- Supports models: `claude-sonnet-4-20250514` (default)

**Option 3: Custom Enterprise Endpoint**

- **Enterprise API endpoint**: Custom base URL for your organization
- **Enterprise auth token**: Organization-specific authentication token
- **Organization ID**: Optional, may be required by your enterprise setup
- Contact your enterprise administrator for these credentials

**Note**: Dry-run mode does not require any authentication

### Optional

- **Shipwright Build repository**: Clone for enhanced code analysis
  ```bash
  git clone https://github.com/shipwright-io/build.git
  ```

---

## Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd muilti-agents-ocp-builds
```

### Step 2: Install Dependencies with uv

Using `uv` (recommended):

```bash
# Install dependencies
uv pip install -r requirements.txt
```

Alternative using standard pip:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your Claude authentication
# Choose either enterprise auth or individual API key
```

### Step 4: Verify Installation

```bash
# Verify agents
python -c "from agents.design_agent import design_agent; print('✓ Design agent')"
python -c "from agents.go_k8s_developer import go_k8s_developer; print('✓ Development agent')"
python -c "from agents.docs_agent import docs_agent; print('✓ Docs agent')"
```

Expected output:
```
✓ Design agent loaded
✓ Docs agent loaded
```

---

## Configuration

### Environment File (.env)

The `.env` file controls all system behavior. Copy from `.env.example` and customize:

#### Required Configuration

Choose one authentication method:

**Option 1: Google Vertex AI (Recommended)**

```bash
# Google Vertex AI Authentication
# Uses gcloud authentication (no API keys needed!)
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=  # Optional, defaults to us-east5
```

Setup steps:
1. Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
2. Authenticate: `gcloud auth application-default login`
3. Set quota project: `gcloud auth application-default set-quota-project your-gcp-project-id`
4. Find your project ID: `gcloud projects list`

**Option 2: Individual API Key**

```bash
# Personal API key
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

Get your API key at [console.anthropic.com](https://console.anthropic.com/settings/keys)

**Option 3: Custom Enterprise Endpoint**

```bash
# Enterprise API endpoint
ANTHROPIC_BASE_URL=https://your-enterprise-endpoint.anthropic.com

# Enterprise authentication token
ANTHROPIC_AUTH_TOKEN=your_enterprise_auth_token

# Optional organization ID
ANTHROPIC_ORG_ID=your_org_id
```

Contact your enterprise administrator for:
- Enterprise API endpoint URL (`ANTHROPIC_BASE_URL`)
- Enterprise authentication token (`ANTHROPIC_AUTH_TOKEN`)
- Organization ID if required (`ANTHROPIC_ORG_ID`)

#### Optional Repository Paths

```bash
# Path to Shipwright Build Repository
# Enables code analysis for better design insights
SHIPWRIGHT_REPO_PATH=/path/to/shipwright-build

# Path to OpenShift Builds Repository
# Optional additional context
OPENSHIFT_BUILDS_REPO_PATH=/path/to/openshift-builds
```

#### Logging Configuration

```bash
# Logging Level
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Log Format
LOG_FORMAT=text  # Options: json, text

# Log File Path (optional)
LOG_FILE_PATH=/tmp/muilti-agents-ocp-builds.log
```

#### Claude Model Configuration

```bash
# Claude Model Version
CLAUDE_MODEL=claude-sonnet-4-20250514

# Maximum Tokens for Response
CLAUDE_MAX_TOKENS=8000
```

#### Agent Configuration

```bash
# Enable Repository Analysis
ENABLE_REPO_ANALYSIS=true

# Design Agent Output Format
DESIGN_OUTPUT_FORMAT=markdown  # Options: markdown, json
```

#### Performance Tuning

```bash
# API Request Timeout (seconds)
API_TIMEOUT=60

# Max Repository Files to Analyze
MAX_REPO_FILES=100

# Cache Directory
CACHE_DIR=.cache

# Cache TTL (seconds)
CACHE_TTL=3600
```

### Security Best Practices

1. **Never commit** `.env` to version control (already in `.gitignore`)
2. **Use `.env.local`** for personal configurations
3. **Rotate credentials** regularly (API keys or enterprise tokens)
4. **Set restrictive permissions**: `chmod 600 .env`
5. **Enterprise users**: Follow your organization's security policies for token management

---

## Usage

### Quick Start: Run the Full Workflow

This runs both Design and Documentation agents:

```bash
uv run scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds"
```

**What you get:**

1. A complete design document with component analysis
2. A PR summary ready to paste into GitHub
3. Release notes for the changelog

All three are printed to the console when the workflow finishes.

### Standalone Agent Execution

**Note:** Agents are typically called automatically by `orchestrate.py`. For advanced use cases, you can call agents programmatically.

**Design agent standalone:**

```python
# design_only.py
from agents.design_agent import run_design
import os

result = run_design(
    title='Add retry logic to failed builds',
    description='BuildRuns should support automatic retry on transient failures',
    repo_path=os.getenv('SHIPWRIGHT_REPO_PATH')
)

print(result['design_analysis'])
```

Then run: `uv run python design_only.py`

**Docs agent standalone:**

```python
# docs_only.py
from agents.docs_agent import run_docs

result = run_docs(
    design_doc='/path/to/design.md',
    code_changes='/path/to/changes.txt'
)

print(result['pr_summary'])
```

Then run: `uv run python docs_only.py`

**For most users:** Use `uv run scripts/orchestrate.py` which handles agent coordination automatically.

### Real-World Examples

**Example 1: Analyze a feature request**

```bash
uv run scripts/orchestrate.py \
  --title "Implement build output caching" \
  --description "Allow BuildRuns to cache intermediate build layers to speed up subsequent builds. Should support OCI registry-based caching."
```

**Example 2: Analyze a bug report**

```bash
uv run scripts/orchestrate.py \
  --title "BuildRun stuck in Running state" \
  --description "BuildRuns remain Running even after pod completes. Status reconciliation fails."
```

**Example 3: With code repository context**

```bash
# Tell agents where to find Shipwright code for deeper analysis
export SHIPWRIGHT_REPO_PATH=/home/user/git/shipwright-build

uv run scripts/orchestrate.py \
  --title "Add SSH key support for private Git repos" \
  --description "Users need to build from private Git repos using SSH authentication"
```

When you provide SHIPWRIGHT_REPO_PATH, agents can analyze actual code structure and identify specific files to modify.

---

## Dashboard

### Overview

The dashboard is a web page that shows you what your agents are doing in real-time. See which phase they're in, how much context they're using, and which components they're analyzing - all updating automatically every 5 seconds.

**Most important feature**: Context usage percentage. When it hits 80%+, you know the agent is running out of space and might need help.

Inspired by [Marc Nuri's AI Coding Agent Dashboard](https://blog.marcnuri.com/ai-coding-agent-dashboard).

### Starting the Dashboard

Run the dashboard server:

```bash
# Start dashboard backend
uv run python scripts/run_dashboard.py
```

The dashboard will be available at:
- **Web UI**: http://localhost:8080
- **API Docs**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/api/health

### What You Can See

**On each session card:**

- **Phase progress**: Where is the workflow? (design → docs → complete)
- **Context usage**: How full is the context window? (0-100%)
- **Components**: Which parts of Shipwright are being analyzed
- **Risks**: How many risks identified and their severity
- **Model**: Which Claude model is running
- **Last update**: How recently the agent reported status

**Page features:**

- Auto-refresh every 5 seconds (can toggle off)
- Manual refresh button
- All active sessions shown simultaneously

### Session Card Example

```
┌─────────────────────────────────────────────┐
│ 🔵 Session abc123                          │
│                                             │
│ Issue: Add timeout support to BuildRun     │
│ Type: feature                               │
│                                             │
│ Design Agent  ✓ Complete                   │
│ Docs Agent    ⏳ In Progress               │
│                                             │
│ Context: ████████░░ 82%                    │
│ Model: claude-sonnet-4                     │
│                                             │
│ Components: build_controller, buildrun_api │
│ Risks: 3 identified - MEDIUM               │
│                                             │
│ Last update: 2s ago                        │
└─────────────────────────────────────────────┘
```

### Configuration

Control dashboard behavior with environment variables (all optional):

```bash
# Where agents send updates (default: http://localhost:8080)
DASHBOARD_URL=http://localhost:8080

# Turn heartbeats on/off (default: true)
DASHBOARD_ENABLED=true

# Where to store session data (default: /tmp/claude/dashboard.db)
DASHBOARD_DB_PATH=/tmp/claude/dashboard.db
```

**Default values work fine for local development.** Only change these if you need custom behavior.

### How It Works

Agents automatically send status updates ("heartbeats") to the dashboard as they work. You don't need to configure anything - it just works.

**Heartbeats are sent:**

1. When the workflow starts (creates a new session)
2. When design phase completes (shows design results)
3. When docs phase completes (shows documentation)
4. If errors occur (shows what went wrong)

The dashboard collects these updates and displays them in real-time.

### API Endpoints

The dashboard backend provides a REST API:

- `POST /api/heartbeat` - Receive agent heartbeat
- `GET /api/sessions` - List all sessions
- `GET /api/sessions/{id}` - Get specific session details
- `GET /api/health` - Health check

### Dashboard Architecture

See [DASHBOARD_ARCHITECTURE.md](DASHBOARD_ARCHITECTURE.md) for detailed technical design including:
- Heartbeat protocol specification
- Enricher framework architecture
- Database schema
- Frontend implementation details

### Troubleshooting Dashboard

**No heartbeats showing up?**

1. Is the dashboard server running? Check <http://localhost:8080/api/health>
2. Is `DASHBOARD_ENABLED=true` in your environment?
3. Is port 8080 available? Try `curl http://localhost:8080/api/health`

**Sessions not appearing?**

1. Try refreshing the page manually
2. Check if the database exists: `ls -l /tmp/claude/dashboard.db`
3. Look at agent logs to confirm they're sending heartbeats

**Context usage is high (>80%)?**

This is important! High context means the agent is running out of room:

- **Break down the task**: Split complex issues into smaller, focused tasks
- **Reduce scope**: Limit which components are analyzed
- **Shorter descriptions**: Keep issue descriptions concise

The dashboard alerts you before context runs out completely.

---

## Architecture

### System Overview

The system uses **LangGraph** for stateful workflow orchestration with specialized AI agents:

```
┌─────────────────────────────────────────────────────────┐
│                    User Input                           │
│  (GitHub Issue: Title + Description)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   LangGraph           │
         │   Orchestrator        │
         │   (agents/graph.py)   │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│ Design Agent   │───▶│ Testing Agent  │───▶│ Docs Agent     │
│ (design_agent) │    │(testing_agent) │    │ (docs_agent)   │
└────────┬───────┘    └────────┬───────┘    └────────┬───────┘
         │                     │                      │
         │ Uses                │ Uses                 │ Uses
         ▼                     ▼                      ▼
┌─────────────────────────────────────────┐
│             Tools                       │
│  • repo_search (code analysis)          │
│  • git_ops (git operations)             │
│  • shipwright_components (domain KB)    │
└─────────────────────────────────────────┘
```

### Agent Roles

| Agent                 | Purpose                                      | Input                     | Output                    |
|-----------------------|----------------------------------------------|---------------------------|---------------------------|
| **Design Agent**      | Analyze requirements and plan implementation | Issue description, repo   | Implementation plan       |
| **Development Agent** | Write production Go code                     | Implementation plan       | Production Go code        |
| **Testing Agent**     | Generate comprehensive test suite            | Implementation plan       | Ginkgo v2 tests           |
| **Docs Agent**        | Create professional documentation            | Changes, context          | PR summary, release notes |

### Tools

| Tool | Purpose | Key Features |
|------|---------|--------------|
| **repo_search** | Code analysis and exploration | File search, content grep, Go-specific searches, CRD detection |
| **git_ops** | Git repository management | Clone, branch, status, diff, commit listing |
| **shipwright_components** | Domain knowledge base | Component definitions, test requirements, build strategies |

### LangGraph Orchestration

The workflow is managed by **LangGraph** with stateful transitions:

```text
┌─────────────────────────────────────────────────────┐
│              LangGraph Orchestrator                 │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │  Design  │ →  │ Develop  │ →  │ Testing  │ →   │
│  │  Agent   │    │  Agent   │    │  Agent   │     │
│  └──────────┘    └──────────┘    └──────────┘     │
│                                        ↓           │
│                                  ┌──────────┐     │
│                                  │   Docs   │     │
│                                  │  Agent   │     │
│                                  └──────────┘     │
└─────────────────────────────────────────────────────┘

State flow:
init → design → design_complete → develop → develop_complete → testing → testing_complete → docs → done
                                                                                              ↓
                                                                                            error
```

**State Schema** (`graph/state.py`):
- Input: issue details, repo path
- Design phase: analysis, components, risks, criteria
- Docs phase: PR summary, release notes, doc changes
- Control flow: current phase, approval status, messages

---

## Agent Details

### Design Agent

**File:** `agents/design_agent.py`

**Purpose:**
Analyzes feature requests or bug reports and produces comprehensive design documents to guide implementation.

**Inputs:**
- `title` (str): GitHub issue title
- `description` (str): GitHub issue description/body
- `repo_path` (Optional[str]): Path to Shipwright repository for code analysis

**Outputs:**
```python
{
    "design_analysis": str,          # Full design document (Markdown)
    "impacted_components": list[str], # Component names affected
    "risks": list[str],               # Identified risks
    "acceptance_criteria": list[str], # Testable acceptance criteria
    "implementation_plan": list[str]  # Step-by-step implementation
}
```

**Analysis Process:**

1. **Context Gathering**
   - Loads Shipwright component definitions
   - Analyzes repository structure (if path provided)
   - Identifies API types, controllers, CRDs

2. **Claude AI Analysis**
   - Model: `claude-sonnet-4-20250514`
   - System prompt: Design-focused with component knowledge
   - Max tokens: 8000

3. **Output Parsing**
   - Extracts structured data from Markdown
   - Identifies mentioned components
   - Categorizes risks and criteria

**Usage Example:**

```python
from agents.design_agent import run_design

result = run_design(
    title="Add timeout support to BuildRun",
    description="Users need to specify build timeout to prevent hanging builds",
    repo_path="/path/to/shipwright-build"
)

print(f"Design Analysis:\n{result['design_analysis']}")
print(f"\nImpacted Components: {result['impacted_components']}")
print(f"\nRisks: {result['risks']}")
```

**Design Document Structure:**

The agent produces documents with these sections:

1. **Problem Statement** - What needs to be solved
2. **Scope** - What's in/out of scope
3. **Impacted Components** - Files, APIs, controllers affected
4. **Risks and Mitigation** - Compatibility, security, performance risks
5. **Acceptance Criteria** - Testable completion criteria
6. **Implementation Plan** - Step-by-step approach
7. **Required Tests** - Unit, integration, E2E test scenarios
8. **Documentation Changes** - User guides, API docs, examples

---

### Testing Agent

**File:** `agents/testing_agent.py`

**Purpose:**
Generates comprehensive Ginkgo v2 test suites for Shipwright Build features, including unit tests, integration tests, and end-to-end tests with Data-Driven Testing (DDT) patterns.

**Inputs:**
```python
context = {
    "design_analysis": str,           # Design document from design_agent
    "impacted_components": list[str], # Components affected
    "acceptance_criteria": list[str], # Testable acceptance criteria
    "issue_title": str,               # Feature/bug title (optional)
    "issue_description": str,         # Detailed description (optional)
    "implementation_plan": list[str], # Implementation steps (optional)
    "risks": list[str],               # Risks to test (optional)
}
```

**Outputs:**
```python
{
    "test_plan": str,                 # Human-readable test strategy
    "test_specifications": dict,      # YAML test specs with scenario IDs
    "unit_tests": dict[str, str],     # File name → Ginkgo test code
    "integration_tests": dict[str, str], # File name → Ginkgo test code
    "e2e_tests": dict[str, str],      # File name → Ginkgo test code
    "test_summary": str,              # Test generation summary
    "coverage_analysis": str,         # Coverage mapping
    "patterns_detected": dict,        # Detected Shipwright patterns
}
```

**Test Generation Process:**

1. **Pattern Detection**
   - Analyzes issue description and design for Shipwright-specific patterns
   - Detects build strategies (kaniko, buildkit, buildpacks, buildah, s2i)
   - Identifies source types (git, bundle, registry)
   - Recognizes output types (image, imagestream)
   - Finds security contexts (privileged, nonroot, restricted)

2. **Test Planning**
   - Creates human-readable test strategy document
   - Maps acceptance criteria to test scenarios
   - Organizes tests by type (unit/integration/E2E)
   - Identifies risk areas requiring extra testing

3. **Test Code Generation**
   - Model: `claude-sonnet-4-20250514`
   - Framework: Ginkgo v2 with Gomega assertions
   - Max tokens: 16000 (larger for code generation)
   - Generates working Go code that compiles

4. **Output Parsing**
   - Extracts test plans, specifications, and code
   - Organizes tests by type and file
   - Generates coverage analysis

**Test Types:**

- **Unit Tests**
  - Scope: Isolated functions with mocks
  - Duration: Fast (<5s)
  - Focus: Function logic, error handling, edge cases
  - Pattern: Table-driven tests with DescribeTable

- **Integration Tests**
  - Scope: Real Kubernetes cluster
  - Duration: Medium (~30s)
  - Focus: Controller reconciliation, webhook validation
  - Pattern: Resource creation and lifecycle tests

- **E2E Tests**
  - Scope: Full workflow
  - Duration: Slow (~5m)
  - Focus: Complete build workflows, strategy-specific scenarios
  - Pattern: Full build lifecycle with actual execution

**Pattern Detection:**

The agent automatically detects Shipwright-specific patterns:

```python
patterns_detected = {
    "strategies": ["kaniko", "buildkit"],       # Build strategies found
    "source_types": ["git", "bundle"],          # Source types found
    "output_types": ["image"],                  # Output types found
    "security_contexts": ["nonroot"],           # Security contexts found
}
```

**Generated Test Features:**

- **Ginkgo v2 Syntax**: Modern Ginkgo with proper imports
- **Data-Driven Testing**: DescribeTable entries for parameterized tests
- **Shipwright Helpers**: Uses libfactory and libk8s test utilities
- **Test IDs**: Structured IDs in format `BUILD-XXX-NNN`
- **Proper Setup/Cleanup**: BeforeEach/AfterEach blocks
- **Async Checks**: Eventually/Consistently with timeouts
- **Real Code**: Compiles and runs in Shipwright test suite

**Usage Example:**

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

print(f"Test Plan:\n{result['test_plan']}")
print(f"\nUnit Tests Generated: {len(result['unit_tests'])} files")
print(f"Integration Tests Generated: {len(result['integration_tests'])} files")
print(f"E2E Tests Generated: {len(result['e2e_tests'])} files")
print(f"\nPatterns Detected: {result['patterns_detected']}")
```

**Test Specifications Example:**

```yaml
scenarios:
  - id: BUILD-TIMEOUT-001
    type: unit
    description: Validate timeout field in BuildRun API
    pattern: validation
    helpers:
      - ValidateBuildRunTimeout
    expected: Accept valid timeout values, reject invalid

  - id: BUILD-TIMEOUT-002
    type: integration
    description: Controller respects timeout configuration
    pattern: controller
    helpers:
      - libfactory.NewBuildRun
      - libk8s.WaitForBuildRunCompletion
    expected: Build terminates after timeout exceeded
```

**Test Code Example:**

```go
var _ = Describe("BuildRun Timeout", func() {
    DescribeTable("timeout validation",
        func(scenario TimeoutScenario) {
            buildRun := libfactory.NewBuildRun(namespace, "test-buildrun").
                WithTimeout(scenario.Timeout).
                Create()

            if scenario.ExpectError {
                Expect(buildRun).To(BeNil())
            } else {
                Expect(buildRun).ToNot(BeNil())
                Expect(buildRun.Spec.Timeout.Duration).To(Equal(scenario.ExpectedTimeout))
            }
        },
        Entry("[BUILD-TIMEOUT-001] valid timeout", TimeoutScenario{
            Timeout: "10m",
            ExpectedTimeout: 10 * time.Minute,
            ExpectError: false,
        }),
        Entry("[BUILD-TIMEOUT-002] invalid timeout", TimeoutScenario{
            Timeout: "invalid",
            ExpectError: true,
        }),
    )
})
```

**Configuration:**

The Testing Agent uses configuration from `config/testing_config.py`:

- **SHIPWRIGHT_TEST_PATTERNS**: Strategy, source, output patterns
- **TEST_TYPES**: Unit, integration, E2E specifications
- **GINKGO_IMPORTS**: Go import templates
- **GINKGO_TEMPLATES**: Test structure templates
- **TEST_HELPERS**: Shipwright test helper snippets
- **DDT_PATTERNS**: Data-driven test data structures

**Quality Features:**

- **Pattern-Aware**: Detects and uses Shipwright-specific patterns
- **Coverage Mapping**: Maps tests to acceptance criteria
- **Test Organization**: Clear separation by type and scope
- **Helper Usage**: Leverages existing Shipwright test utilities
- **Realistic Tests**: Generates tests that match actual Shipwright test patterns
- **Comprehensive**: Covers happy paths, error paths, and edge cases

**Qualityflow Integration:**

The Testing Agent is inspired by Red Hat's qualityflow test generation framework, adapted for:
- Shipwright Build domain-specific patterns
- Ginkgo v2 test framework
- Kubernetes and OpenShift testing patterns
- Data-Driven Testing best practices

---

### Development Agent

**File:** `agents/go_k8s_developer.py`

**Purpose:**
Writes production-quality Go code for Kubernetes and OpenShift projects following strict security and quality standards.

**Key Capabilities:**
- Production-quality Go code generation
- Kubernetes/OpenShift patterns (client-go, controller-runtime)
- TLS 1.3 enforcement
- Secure logging without secret leakage
- Comprehensive error handling
- Go doc comments for all exported methods

**Input:**
- Implementation plan from Design Agent
- Target repository structure
- Existing codebase patterns

**Output:**
- Production Go code files
- Unit tests with table-driven patterns
- PR description with "Generated by AI" footer

**Security Standards:**
- Enforce TLS 1.3 where TLS configuration is added/modified
- No hardcoded secrets, tokens, or credentials
- Input validation and safe error handling
- Structured logging without sensitive data leakage

**Code Quality:**
- Idiomatic Go practices
- Meaningful names and focused functions
- Go doc comments for all exported methods
- Readable and maintainable code

**Testing:**
- Table-driven unit tests
- Mock external dependencies
- Coverage for success, failure, and edge cases

**Usage Example:**

```python
from agents.go_k8s_developer import go_k8s_developer

# Generate production Go code
result = go_k8s_developer.invoke({
    "issue_title": "Add TLS 1.3 support to build controller",
    "implementation_plan": design_output["plan"],
    "repo_path": "/path/to/repo"
})

print(result["code_files"])
print(result["test_files"])
print(result["pr_description"])
```

**Key Features:**
- **Security-First:** TLS 1.3, no secrets in code/logs
- **K8s Patterns:** client-go, controller-runtime, proper RBAC
- **Quality:** Go doc comments, error wrapping, structured logging
- **Testing:** Table-driven tests, mocking, edge case coverage
- **Maintainable:** Follows existing project patterns and conventions

---

### Docs Agent

**File:** `agents/docs_agent.py`

**Purpose:**
Generates documentation artifacts based on design, development, and test outputs.

**Inputs:**
```python
context = {
    "design_analysis": str,           # Design document
    "implementation_plan": str,       # Implementation approach
    "code_changes": dict[str, str],   # File paths to changes
    "files_modified": list[str],      # List of modified files
    "test_results": dict,             # Test execution results
    "test_summary": str,              # Summary of tests
    "issue_title": str,               # Original issue title
    "issue_description": str,         # Original issue description
    "issue_type": str,                # bug/feature/refactor/docs
}
```

**Outputs:**
```python
{
    "pr_summary": str,              # Pull request description
    "release_notes": str,           # User-facing changelog entry
    "docs_changes": dict[str, str], # Doc file updates (path: content)
    "upgrade_notes": str,           # Version upgrade guidance
    "known_limitations": str        # Edge cases/limitations
}
```

**Documentation Generation Process:**

1. **Context Building**
   - Aggregates design, dev, and test outputs
   - Formats for Claude consumption
   - Highlights key changes and impacts

2. **Claude AI Generation**
   - Model: `claude-sonnet-4-20250514`
   - Temperature: 0.3 (consistent documentation)
   - Max tokens: 4096

3. **Output Parsing**
   - Splits response into sections
   - Extracts file-specific doc changes
   - Structures release notes

**Usage Example:**

```python
from agents.docs_agent import run_docs

context = {
    "design_analysis": "# Design: Add timeout...",
    "code_changes": {
        "pkg/apis/build/v1/buildrun_types.go": "Added Timeout field"
    },
    "test_results": {"unit": "passed", "e2e": "passed"},
    "issue_title": "Add timeout support",
    "issue_description": "Users need build timeout configuration"
}

result = run_docs(context)

print(f"PR Summary:\n{result['pr_summary']}")
print(f"\nRelease Notes:\n{result['release_notes']}")
```

**Generated Documentation Types:**

1. **PR Summary** - Concise description for pull requests
2. **Release Notes** - User-facing changelog entries
3. **Documentation Changes** - Specific updates to docs/user-guide.md, etc.
4. **Upgrade Notes** - Version-specific migration guidance
5. **Known Limitations** - Edge cases and current restrictions

---

## Jobs-to-be-Done (JTBD) Documentation

Starting with release 1.8, the Docs Agent generates user-focused Jobs-to-be-Done documentation for every new feature or change.

### What is JTBD Documentation?

JTBD documentation is organized around the specific outcomes users are trying to achieve, rather than technical features. This structure allows users to quickly identify the necessary steps, examples, and troubleshooting information required to complete their tasks effectively.

### JTBD Structure

Each job includes:

1. **Job Title** - Clear statement of what the user wants to accomplish
   - Format: "When [situation], I want to [motivation], so I can [expected outcome]"

2. **Context** - When and why users need this
   - User persona
   - Common scenarios
   - Prerequisites

3. **Steps to Complete** - Concrete, actionable steps
   - Numbered steps with examples
   - Code snippets
   - Expected outputs

4. **Troubleshooting** - Common issues and solutions
   - Error messages and fixes
   - Edge cases
   - Validation steps

5. **Related Jobs** - See also
   - Related tasks
   - Next steps

### Using JTBD Output

When you run the Docs Agent (or full orchestration), the output includes JTBD documentation:

```python
from agents.graph import orchestrate

result = orchestrate(
    title="Add timeout support to BuildRun",
    description="Users need to specify build timeout to prevent hanging builds"
)

# Access JTBD documentation
print(result["jtbd_documentation"])
```

### Example JTBD Output

The JTBD documentation will look like:

```markdown
## Job: Prevent Build Runs from Hanging Indefinitely

**Context:** When running long-running builds, I want to set a maximum timeout, so I can prevent builds from consuming resources indefinitely and ensure my CI/CD pipeline completes in a predictable timeframe.

**Steps to Complete:**
1. Update your BuildRun spec to include timeout field...
2. Apply the configuration...
3. Verify the timeout is enforced...

**Troubleshooting:**
- If timeout is ignored, check...
- If builds terminate prematurely, increase...

**Related Jobs:**
- Configure build retries
- Set up build notifications
```

### For Contributors

When adding new features or changes:
1. The Docs Agent will automatically generate JTBD documentation
2. Review the generated JTBD content for accuracy
3. Ensure all required sections are present
4. Validate examples are runnable

---

## Tools Reference

### repo_search - Code Analysis Tool

**File:** `tools/repo_search.py`

**Purpose:**
Provides comprehensive repository analysis capabilities including file pattern matching, content searching, and Go-specific code exploration.

#### Class: `RepoSearch`

**Initialization:**

```python
from tools.repo_search import RepoSearch

searcher = RepoSearch("/path/to/repository")
```

#### Methods

##### `search_files(pattern, exclude_dirs=None)`

Search for files matching a glob pattern.

```python
# Find all Go files
results = searcher.search_files("**/*.go")

# Find API type files
results = searcher.search_files("pkg/apis/**/*_types.go")

# Find YAML files, excluding vendor
results = searcher.search_files("**/*.yaml", exclude_dirs=["vendor", ".git"])

# Each result is a SearchResult object
for result in results:
    print(result.file_path)  # Relative path from repo root
```

##### `search_content(pattern, file_pattern=None, case_sensitive=True, regex=False)`

Search for content within files.

```python
# Find all references to "BuildRun"
results = searcher.search_content("BuildRun")

# Case-insensitive search in Go files
results = searcher.search_content(
    "timeout",
    file_pattern="**/*.go",
    case_sensitive=False
)

# Regex search for function definitions
results = searcher.search_content(
    r"func\s+\w+Controller",
    regex=True
)

# Results include line numbers and content
for result in results:
    print(f"{result.file_path}:{result.line_number}: {result.content}")
```

##### `find_go_functions(package_pattern=None)`

Find Go function definitions.

```python
# Find all exported functions in controller package
results = searcher.find_go_functions("pkg/controller")

# Results match: func FunctionName(...) or func (receiver) MethodName(...)
for result in results:
    print(result)  # pkg/controller/build_controller.go:45: func Reconcile(...)
```

##### `find_go_types(package_pattern=None)`

Find Go type definitions.

```python
# Find all types in API package
results = searcher.find_go_types("pkg/apis")

# Matches: type TypeName struct/interface/...
```

##### `find_go_structs(package_pattern=None)`

Find Go struct definitions specifically.

```python
# Find all struct definitions
results = searcher.find_go_structs()

# Matches: type StructName struct { ... }
```

##### `find_kubernetes_crds()`

Find Kubernetes Custom Resource Definitions.

```python
# Find all CRD YAML files
results = searcher.find_kubernetes_crds()

# Searches for files with "kind: CustomResourceDefinition"
for result in results:
    print(f"CRD: {result.file_path}")
```

##### `analyze_go_packages(base_path=None)`

Analyze Go package structure.

```python
# Analyze all packages under pkg/
packages = searcher.analyze_go_packages("pkg")

for pkg in packages:
    print(f"Package: {pkg.name}")
    print(f"Path: {pkg.path}")
    print(f"Files: {len(pkg.files)}")
    print(f"Subpackages: {pkg.subpackages}")
```

##### `get_file_content(file_path, start_line=None, end_line=None, show_line_numbers=True)`

Get file content with optional line numbers.

```python
# Get full file with line numbers
content = searcher.get_file_content("pkg/apis/build/v1/build_types.go")

# Get specific line range
content = searcher.get_file_content(
    "pkg/controller/build_controller.go",
    start_line=100,
    end_line=150
)

# Get content without line numbers
content = searcher.get_file_content(
    "README.md",
    show_line_numbers=False
)
```

#### Convenience Function

```python
from tools.repo_search import search_repository

# Quick content search
results = search_repository(
    "/path/to/repo",
    "BuildRun",
    search_type="content"
)

# Search types: "content", "files", "go_functions", "go_types", "go_structs", "crds"
results = search_repository(
    "/path/to/repo",
    "pkg/controller",
    search_type="go_functions"
)
```

---

### git_ops - Git Operations Tool

**File:** `tools/git_ops.py`

**Purpose:**
Provides Git repository management using GitPython for cloning, branch management, and repository inspection.

#### Class: `GitOps`

**Initialization:**

```python
from tools.git_ops import GitOps

ops = GitOps()  # Clones to /tmp/claude by default
```

#### Methods

##### `clone_repository(repo_url, target_name=None, depth=1, branch=None, sparse_checkout=None)`

Clone a repository to `/tmp/claude/`.

```python
# Shallow clone (depth=1)
result = ops.clone_repository(
    "https://github.com/shipwright-io/build.git",
    target_name="shipwright-build",
    depth=1
)

if result.success:
    print(f"Cloned to: {result.data['path']}")
else:
    print(f"Error: {result.message}")

# Clone specific branch
result = ops.clone_repository(
    "https://github.com/org/repo.git",
    branch="release-v1.0"
)

# Sparse checkout (only specific paths)
result = ops.clone_repository(
    "https://github.com/org/repo.git",
    sparse_checkout=["pkg/apis", "docs"]
)
```

##### `create_branch(repo_path, branch_name, start_point=None, checkout=True)`

Create a new branch.

```python
# Create and checkout new branch
result = ops.create_branch(
    "/tmp/claude/shipwright-build",
    "feature/add-timeout"
)

# Create branch from specific commit
result = ops.create_branch(
    "/tmp/claude/shipwright-build",
    "feature/new-feature",
    start_point="origin/main"
)

# Create without checking out
result = ops.create_branch(
    "/tmp/claude/shipwright-build",
    "hotfix/bug-123",
    checkout=False
)
```

##### `get_status(repo_path)`

Get repository status.

```python
result = ops.get_status("/tmp/claude/shipwright-build")

if result.success:
    print(f"Branch: {result.data['current_branch']}")
    print(f"Dirty: {result.data['is_dirty']}")
    print(f"Modified files: {result.data['modified_files']}")
    print(f"Staged files: {result.data['staged_files']}")
    print(f"Untracked files: {result.data['untracked_files']}")
```

##### `get_diff(repo_path, commit1=None, commit2=None, path=None)`

Get diff information.

```python
# Diff of unstaged changes
result = ops.get_diff("/tmp/claude/shipwright-build")

# Diff between commits
result = ops.get_diff(
    "/tmp/claude/shipwright-build",
    commit1="HEAD~1",
    commit2="HEAD"
)

# Diff for specific file
result = ops.get_diff(
    "/tmp/claude/shipwright-build",
    path="pkg/apis/build/v1/build_types.go"
)

if result.success:
    print(result.data['diff'])
```

##### `list_commits(repo_path, max_count=10, branch=None)`

List recent commits.

```python
result = ops.list_commits("/tmp/claude/shipwright-build", max_count=5)

if result.success:
    for commit in result.data['commits']:
        print(f"{commit['sha']} - {commit['message']}")
        print(f"  Author: {commit['author']}")
        print(f"  Date: {commit['date']}")
```

##### `list_branches(repo_path)`

List all branches.

```python
result = ops.list_branches("/tmp/claude/shipwright-build")

if result.success:
    for branch in result.data['branches']:
        current = "* " if branch['is_current'] else "  "
        print(f"{current}{branch['name']} ({branch['commit']})")
```

##### `cleanup_repository(repo_path)`

Remove a cloned repository (safety: only in `/tmp/claude`).

```python
result = ops.cleanup_repository("/tmp/claude/shipwright-build")

if result.success:
    print(f"Removed: {result.data['removed_path']}")
```

---

### shipwright_components - Domain Knowledge

**File:** `config/shipwright_components.py`

**Purpose:**
Defines Shipwright Build component structure, requirements, and domain knowledge.

#### Constants

##### `COMPONENTS`

Dictionary of component names to their purposes:

```python
from config.shipwright_components import COMPONENTS

# Available components:
# - build_api, buildrun_api, buildstrategy_api, clusterbuildstrategy_api
# - build_controller, buildrun_controller, etc.
# - webhook_validation, webhook_mutation, webhook_conversion
# - source_handler, registry_handler, strategy_resolver
# - rbac_manager, secret_manager, pod_security
# - metrics_exporter, event_recorder

for component, purpose in COMPONENTS.items():
    print(f"{component}: {purpose}")
```

##### `CRD_TYPES`

List of Custom Resource Definition types:

```python
from config.shipwright_components import CRD_TYPES

# ["Build", "BuildRun", "BuildStrategy", "ClusterBuildStrategy"]
```

##### `BUILD_STRATEGIES`

Dictionary of build strategies:

```python
from config.shipwright_components import BUILD_STRATEGIES

for strategy_name, info in BUILD_STRATEGIES.items():
    print(f"{strategy_name}:")
    print(f"  Type: {info['type']}")
    print(f"  Builder: {info['builder']}")
    print(f"  Use Case: {info['use_case']}")

# Available: buildpacks, buildah, kaniko, buildkit
```

##### `OPENSHIFT_INTEGRATIONS`

OpenShift integration points:

```python
from config.shipwright_components import OPENSHIFT_INTEGRATIONS

# Image streams, S2I compatibility, internal registry, etc.
```

#### Functions

##### `get_component_info(component_name)`

Get detailed component information:

```python
from config.shipwright_components import get_component_info

info = get_component_info("build_controller")

print(f"Test Requirements: {info['test_requirements']}")
print(f"Dependencies: {info['dependencies']}")
print(f"File Patterns: {info['file_patterns']}")
```

##### `validate_component(component_name)`

Validate if a component exists:

```python
from config.shipwright_components import validate_component

if validate_component("build_api"):
    print("Valid component")
else:
    print("Invalid component")
```

---

## Examples

### Example 1: Analyzing a Feature Request

**Scenario:** User wants to add retry logic to failed builds.

**Input:**

```bash
uv run scripts/orchestrate.py \
  --title "Add automatic retry for failed BuildRuns" \
  --description "BuildRuns should support configurable retry logic for transient failures. Allow users to specify maxRetries and retryBackoff in BuildRun spec."
```

**Process:**

1. **Design Agent analyzes the request:**
   - Identifies impacted components: `buildrun_api`, `buildrun_controller`
   - Assesses compatibility risks (backward compatible if optional)
   - Generates acceptance criteria:
     - BuildRun API accepts `maxRetries` field
     - Controller retries failed builds up to maxRetries
     - Each retry is recorded in BuildRun status

2. **Docs Agent generates documentation:**
   - PR Summary: "Adds retry support to BuildRun API..."
   - Release Notes: "**Enhancement:** BuildRuns now support automatic retries..."
   - Doc Changes: Update `docs/buildrun.md` with retry examples

**Expected Output:**

```markdown
DESIGN_ANALYSIS
# Design: Add automatic retry for failed BuildRuns

## Problem Statement
BuildRuns currently fail permanently on transient errors...

## Impacted Components
- **buildrun_api**: Add Retry field to BuildRunSpec
- **buildrun_controller**: Implement retry logic in reconciliation
- **webhook_validation**: Validate retry configuration

## Risks and Mitigation
- **Risk**: Infinite retry loops
  **Mitigation**: Enforce maximum retry limit (e.g., 10)
...

PR_SUMMARY
This PR adds configurable retry logic to the BuildRun API...

RELEASE_NOTES
**Enhancement:** BuildRuns now support automatic retries for transient failures...
```

---

### Example 2: Analyzing a Bug Report

**Scenario:** BuildRun gets stuck in Running state.

**Input:**

```bash
uv run scripts/orchestrate.py \
  --title "BuildRun stuck in Running state after pod completion" \
  --description "Observed in production: BuildRun status remains 'Running' even after the Tekton TaskRun completes successfully. The controller appears to miss the completion event."
```

**Process:**

1. **Design Agent identifies the issue:**
   - Impacted: `buildrun_controller` (reconciliation logic)
   - Root cause hypothesis: Event watch issues or race condition
   - Suggests adding reconciliation retry and status validation

2. **Docs Agent prepares bug fix documentation:**
   - PR Summary focuses on the fix
   - Release Notes mention bug fix
   - Upgrade notes: none (backward compatible fix)

**Expected Output:**

```markdown
DESIGN_ANALYSIS
# Design: Fix BuildRun stuck in Running state

## Problem Statement
BuildRun controller fails to update status when Tekton TaskRun completes...

## Root Cause Analysis
Likely causes:
1. Missed watch event from Tekton
2. Race condition in status update
3. Error in reconciliation retry logic

## Implementation Plan
1. Add defensive status check in reconciliation loop
2. Implement periodic status sync (every 30s)
3. Add metrics for stuck BuildRuns
...
```

---

### Example 3: Full Workflow from Issue to Documentation

**Scenario:** Complete workflow with repository analysis.

**Setup:**

```bash
# Set environment variables
export SHIPWRIGHT_REPO_PATH=/home/user/git/shipwright-build
export ANTHROPIC_API_KEY=sk-ant-...

# Ensure repository is cloned
cd /home/user/git
git clone https://github.com/shipwright-io/build.git shipwright-build
```

**Command:**

```bash
uv run scripts/orchestrate.py \
  --title "Support OCI artifact sources for builds" \
  --description "Allow builds to use OCI artifacts (not just container images) as source input. This enables building from Helm charts, WASM modules, and other OCI artifacts stored in registries."
```

**Workflow:**

1. **Design Agent:**
   - Analyzes Shipwright repo structure
   - Finds existing source handlers in `pkg/source/`
   - Identifies OCI registry code in `pkg/registry/`
   - Generates design considering existing patterns

2. **LangGraph State Management:**
   - State: `init` → `design` → `design_complete` → `docs` → `done`
   - Passes design outputs to docs agent

3. **Docs Agent:**
   - Receives design analysis
   - Generates comprehensive PR description
   - Creates release notes highlighting new capability
   - Suggests doc updates for user guide

**Output Structure:**

```python
result = {
    "design_analysis": "# Design: Support OCI artifact sources...",
    "impacted_components": [
        "source_handler",
        "registry_handler",
        "build_api"
    ],
    "risks": [
        "Backward compatibility with existing source types",
        "Authentication differences for OCI artifacts"
    ],
    "acceptance_criteria": [
        "Build API accepts OCI artifact source type",
        "Source handler downloads OCI artifacts",
        "E2E test with Helm chart source"
    ],
    "pr_summary": "This PR adds support for OCI artifacts...",
    "release_notes": "**New Feature:** Builds can now use OCI artifacts...",
    "docs_changes": {
        "docs/build.md": "Add section on OCI artifact sources",
        "examples/oci-source-build.yaml": "Example Build using Helm chart"
    }
}
```

---

## Troubleshooting

### Authentication Not Configured

**Error:**
```
DesignAgentError: No Claude authentication configured
```

**Solution:**

Choose one authentication method:

**For Google Vertex AI (Recommended):**
```bash
# Authenticate with gcloud
gcloud auth application-default login
gcloud auth application-default set-quota-project your-gcp-project-id

# Check if .env file exists
ls -la .env

# Ensure Vertex AI project ID is set
grep ANTHROPIC_VERTEX_PROJECT_ID .env

# Or export directly
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
export CLOUD_ML_REGION=  # Optional
```

**For Individual API Key:**
```bash
# Check if .env file exists
ls -la .env

# Ensure API key is set
grep ANTHROPIC_API_KEY .env

# Or export directly
export ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

**For Custom Enterprise Endpoint:**
```bash
# Check if .env file exists
ls -la .env

# Ensure enterprise auth is set
grep ANTHROPIC_BASE_URL .env
grep ANTHROPIC_AUTH_TOKEN .env

# Or export directly
export ANTHROPIC_BASE_URL=https://your-enterprise-endpoint.anthropic.com
export ANTHROPIC_AUTH_TOKEN=your_enterprise_auth_token
```

**For Dry-Run Mode (No Authentication Needed):**
```bash
# Use dry-run mode for testing without authentication
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
# Install missing dependencies
uv pip install -r requirements.txt

# Or install specific package
uv pip install anthropic

# Verify installation
uv run python -c "import anthropic; print('✓ anthropic installed')"
```

---

### Repository Not Found

**Error:**
```
RepositorySearchError: Repository path does not exist: /path/to/repo
```

**Solution:**
```bash
# Check if path is correct
ls -la /path/to/repo

# Clone repository if missing
git clone https://github.com/shipwright-io/build.git /path/to/repo

# Update .env with correct path
echo "SHIPWRIGHT_REPO_PATH=/path/to/repo" >> .env
```

---

### Agent Failures

**Error:**
```
Claude API call failed: rate_limit_error
```

**Solution:**
```bash
# Check API quota at https://console.anthropic.com/

# Increase timeout in .env
echo "API_TIMEOUT=120" >> .env

# Retry with exponential backoff (built-in)
```

**Error:**
```
RuntimeError: Unexpected error in docs agent: Missing required context keys
```

**Solution:**
```python
# Ensure all required context keys are provided
context = {
    "design_analysis": "...",  # Required
    "code_changes": {},         # Required
    "test_results": {},         # Required
    # Optional: test_summary, issue_title, etc.
}
```

---

### Git Operations Failures

**Error:**
```
GitOpResult.error: Directory already exists: /tmp/claude/repo
```

**Solution:**
```python
from tools.git_ops import GitOps

ops = GitOps()

# Cleanup existing clone
ops.cleanup_repository("/tmp/claude/repo")

# Now clone again
ops.clone_repository("https://github.com/org/repo.git")
```

---

### Performance Issues

**Symptom:** Slow repository analysis or API calls timing out.

**Solutions:**

1. **Reduce repository scan scope:**
   ```bash
   echo "MAX_REPO_FILES=50" >> .env
   ```

2. **Enable caching:**
   ```bash
   echo "CACHE_DIR=.cache" >> .env
   echo "CACHE_TTL=7200" >> .env
   ```

3. **Use sparse checkout:**
   ```python
   ops.clone_repository(
       "https://github.com/org/large-repo.git",
       sparse_checkout=["pkg/apis", "pkg/controller"]
   )
   ```

4. **Increase API timeout:**
   ```bash
   echo "API_TIMEOUT=120" >> .env
   ```

---

## Development

### Adding New Agents

Create a new agent in `agents/`:

```python
# agents/my_agent.py
from anthropic import Anthropic
import os

def run_my_agent(input_data):
    """My agent implementation."""
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system="You are a specialized agent for...",
        messages=[{"role": "user", "content": input_data}]
    )

    return {"output": response.content[0].text}
```

**Integrate with LangGraph:**

```python
# agents/graph.py
from agents.my_agent import run_my_agent

def my_agent_node(state: AgentState) -> Dict[str, Any]:
    result = run_my_agent(state["some_input"])
    return {"my_output": result["output"]}

# Add to workflow
workflow.add_node("my_agent", my_agent_node)
workflow.add_edge("design", "my_agent")
workflow.add_edge("my_agent", "docs")
```

---

### Adding New Tools

Create a new tool in `tools/`:

```python
# tools/my_tool.py
from dataclasses import dataclass
from typing import Any

@dataclass
class MyToolResult:
    success: bool
    data: Any
    message: str

class MyTool:
    def __init__(self):
        pass

    def do_something(self, input_param: str) -> MyToolResult:
        """Tool implementation."""
        try:
            # Tool logic here
            result_data = {"processed": input_param}
            return MyToolResult(
                success=True,
                data=result_data,
                message="Success"
            )
        except Exception as e:
            return MyToolResult(
                success=False,
                data=None,
                message=f"Error: {e}"
            )
```

**Use in agents:**

```python
from tools.my_tool import MyTool

def my_agent(state):
    tool = MyTool()
    result = tool.do_something(state["input"])

    if result.success:
        return {"output": result.data}
    else:
        return {"error": result.message}
```

---

### Testing Changes

**Unit Tests:**

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_design_agent.py

# Run with coverage
uv run pytest --cov=agents --cov=tools tests/
```

**Integration Tests:**

```bash
# Test with actual API (requires authentication)
# Option 1: Google Vertex AI (recommended)
export ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
# Ensure gcloud auth is configured: gcloud auth application-default login

# Option 2: Individual API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run tests
uv run pytest tests/integration/
```

**Manual Testing:**

```python
# Test design agent
uv run python -c "
from agents.design_agent import run_design

result = run_design(
    title='Test feature',
    description='Test description'
)
print(result['design_analysis'])
"

# Test docs agent
uv run python -c "
from agents.docs_agent import run_docs

context = {
    'design_analysis': 'Test design',
    'code_changes': {},
    'test_results': {}
}
result = run_docs(context)
print(result['pr_summary'])
"
```

---

### Code Structure

```
muilti-agents-ocp-builds/
├── agents/               # AI agents
│   ├── design_agent.py  # Design analysis agent
│   ├── docs_agent.py    # Documentation agent
│   └── graph.py         # LangGraph orchestration
├── config/              # Configuration
│   ├── agent_prompts.py # System prompts for agents
│   └── shipwright_components.py  # Domain knowledge
├── tools/               # Utility tools
│   ├── repo_search.py   # Code analysis
│   ├── git_ops.py       # Git operations
│   └── __init__.py
├── graph/               # LangGraph state
│   ├── state.py         # State schema
│   └── __init__.py
├── scripts/             # Entry points
│   └── orchestrate.py   # Main orchestration script
├── tests/               # Test suite
│   ├── test_design_agent.py
│   ├── test_docs_agent.py
│   └── integration/
├── docs/                # Documentation
│   ├── HOWTO.md         # This file
│   └── ARCHITECTURE.md  # System architecture
├── .env.example         # Environment template
├── requirements.txt     # Python dependencies
└── README.md            # Project overview
```

---

## FAQ

### Q: Do I need a Shipwright repository clone?

**A:** No, it's optional. The system works without it but provides better analysis with repository access. Set `SHIPWRIGHT_REPO_PATH` in `.env` to enable code analysis.

---

### Q: Can I use a different Claude model?

**A:** Yes, set `CLAUDE_MODEL` in `.env`:

```bash
# Use Claude Opus for more complex analysis
CLAUDE_MODEL=claude-opus-4-20250514

# Use older Sonnet version
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

---

### Q: How much does this cost per run?

**A:** Costs depend on the Claude model and input size:

- **Design Agent**: ~8,000 tokens output + input (component info + issue)
- **Docs Agent**: ~4,000 tokens output + input (design + test results)
- **Estimated cost per run**: $0.05-0.20 (Sonnet 4)

**Monitoring usage:**
- **Vertex AI**: Check GCP billing console and quotas
- **Individual API Key**: Monitor at [Anthropic Console](https://console.anthropic.com/usage)

---

### Q: Can I run agents in parallel?

**A:** The current LangGraph workflow is sequential (Design → Docs). For parallel execution, modify `agents/graph.py`:

```python
# Add parallel branches
workflow.add_conditional_edges(
    "design",
    should_split,
    {
        "path_a": "agent_a",
        "path_b": "agent_b",
    }
)
```

---

### Q: How do I customize agent prompts?

**A:** Edit `config/agent_prompts.py`:

```python
DESIGN_AGENT_PROMPT = """You are a Design Agent with focus on...

## Custom Instructions
- Your specific requirements
- Domain-specific guidelines
...
"""
```

---

### Q: Can I add custom component definitions?

**A:** Yes, edit `config/shipwright_components.py`:

```python
COMPONENTS = {
    # Existing components...
    "my_custom_component": "Description of custom component",
}

# Add test requirements
TEST_REQUIREMENTS["my_custom_component"] = {"unit", "integration"}
```

---

### Q: How do I debug agent failures?

**A:** Enable debug logging:

```bash
# In .env
LOG_LEVEL=DEBUG
LOG_FILE_PATH=/tmp/muilti-agents-debug.log

# Run and check logs
uv run scripts/orchestrate.py --title "Test" --description "Test"
tail -f /tmp/muilti-agents-debug.log
```

---

### Q: Can I use this for other projects (not Shipwright)?

**A:** Yes, with modifications:

1. Replace `config/shipwright_components.py` with your domain knowledge
2. Update `config/agent_prompts.py` with project-specific context
3. Adjust repository analysis in `agents/design_agent.py`
4. Update state schema in `graph/state.py` if needed

---

### Q: How do I contribute improvements?

**A:** Follow standard GitHub workflow:

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-improvement`
3. Make changes and add tests
4. Run test suite: `uv run pytest`
5. Submit pull request with description

---

### Q: What Python version is required?

**A:** Python 3.11+ is required for modern type hints and performance improvements. Check with:

```bash
python --version  # Should show 3.11.0 or higher
```

---

### Q: How do I handle rate limits?

**A:** Anthropic API has rate limits. Best practices:

1. **Check quota**: [Anthropic Console](https://console.anthropic.com/usage)
2. **Increase timeout**: Set `API_TIMEOUT=120` in `.env`
3. **Implement retry**: Built-in with exponential backoff
4. **Batch requests**: Process multiple issues in sequence with delays

---

### Q: Can I export results to files?

**A:** Yes, modify `scripts/orchestrate.py`:

```python
import json
from pathlib import Path

result = orchestrate(args.title, args.description)

# Save as JSON
output_file = Path("output") / f"{args.title.replace(' ', '-')}.json"
output_file.parent.mkdir(exist_ok=True)
output_file.write_text(json.dumps(result, indent=2))

# Save design doc as Markdown
design_file = Path("output") / f"{args.title.replace(' ', '-')}-design.md"
design_file.write_text(result["design_analysis"])
```

---

## Summary

The Multi-Agent OpenShift Builds system streamlines the **design and documentation workflow** for Shipwright Build development:

1. **Install** with `uv pip install -r requirements.txt`
2. **Configure** `.env` with your `ANTHROPIC_API_KEY`
3. **Run** `uv run scripts/orchestrate.py --title "..." --description "..."`
4. **Get** comprehensive design analysis and documentation artifacts

For questions or issues, refer to the [Troubleshooting](#troubleshooting) section or check the project repository.
