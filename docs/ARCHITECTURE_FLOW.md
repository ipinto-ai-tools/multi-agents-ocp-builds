# Multi-Agent System Architecture & Flow

## Table of Contents
- [System Overview](#system-overview)
- [The 4 Agents - Detailed Flow](#the-4-agents---detailed-flow)
- [LangGraph Orchestrator](#langgraph-orchestrator)
- [Dashboard Integration](#dashboard-integration)
- [Complete Flow Example](#complete-flow-example)
- [State Management](#state-management)
- [Logging System](#logging-system)
- [Error Handling](#error-handling)
- [Configuration](#configuration)
- [Code File Reference](#code-file-reference)

---

## System Overview

### High-Level Architecture

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
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │
│  │   Design    │──>│  Develop    │──>│   Testing   │──> Docs      │
│  │   Agent     │   │   Agent     │   │   Agent     │    Agent     │
│  └─────────────┘   └─────────────┘   └─────────────┘              │
│         │                 │                 │              │        │
│         └─────────────────┴─────────────────┴──────────────┘        │
│                           Heartbeats                                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Dashboard Backend                              │
│                   (FastAPI + SQLite)                                │
│                   dashboard/backend.py                              │
│                                                                      │
│  ┌──────────────┐         ┌──────────────┐                         │
│  │   Sessions   │         │  Heartbeats  │                         │
│  │    Table     │◄────────│    Table     │                         │
│  └──────────────┘         └──────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Dashboard Frontend                             │
│                  (HTML + JavaScript + Auto-Refresh)                 │
│                  dashboard/frontend/index.html                      │
│                                                                      │
│  Shows:                                                              │
│  - Active Sessions                                                   │
│  - Agent Progress (Design → Dev → Test → Docs)                     │
│  - Status Badges                                                     │
│  - Real-time Updates (3s refresh)                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Main Components

1. **4 Specialized Agents**: Design, Development, Testing, Documentation
2. **LangGraph Orchestrator**: Stateful workflow coordination using state machine
3. **Dashboard System**: Real-time monitoring with heartbeat protocol
4. **State Management**: Shared state across all agents via `AgentState` TypedDict
5. **Logging System**: Session-specific and module-level logging

### Data Flow Summary

```
User Request
    ↓
Generate Session ID
    ↓
Initialize AgentState
    ↓
Design Agent (analyzes requirements)
    ↓ (emits heartbeat)
Development Agent (generates code)
    ↓ (emits heartbeat)
Testing Agent (creates tests)
    ↓ (emits heartbeat)
Documentation Agent (writes docs)
    ↓ (emits heartbeat)
Final State (all outputs combined)
```

---

## The 4 Agents - Detailed Flow

### 1. Design Agent

**File**: `agents/design_agent.py`

**Purpose**: Analyzes feature requests and produces comprehensive design documents.

**Entry Point**: `run_design(title: str, description: str, repo_path: Optional[str]) -> Dict[str, Any]`

#### Flow Diagram

```
START: run_design()
    │
    ├─> Initialize Claude client (config/auth_config.py)
    │
    ├─> Gather repository context (optional)
    │   │
    │   ├─> RepoSearch: Find API types (pkg/apis/**/*_types.go)
    │   ├─> RepoSearch: Find controllers (pkg/controller/**/*.go)
    │   ├─> RepoSearch: Find CRDs (YAML files)
    │   └─> RepoSearch: Analyze Go packages
    │
    ├─> Build component context
    │   │
    │   ├─> Load COMPONENTS dictionary
    │   ├─> Load CRD_TYPES list
    │   ├─> Load BUILD_STRATEGIES
    │   └─> Load OPENSHIFT_INTEGRATIONS
    │
    ├─> Construct analysis prompt
    │   │
    │   └─> Combine: Issue + Component Info + Repo Context
    │
    ├─> Call Claude API
    │   │
    │   ├─> Model: claude-sonnet-4-20250514
    │   ├─> Max Tokens: 8000
    │   ├─> System Prompt: DESIGN_AGENT_PROMPT
    │   └─> User Prompt: Analysis request
    │
    ├─> Parse response
    │   │
    │   ├─> Extract "Impacted Components" section
    │   ├─> Extract "Risks" section
    │   ├─> Extract "Acceptance Criteria" section
    │   ├─> Extract "Implementation Plan" section
    │   └─> Match component names from text
    │
    └─> Return design_output
        │
        ├─> design_analysis: Complete Markdown document
        ├─> impacted_components: List[str]
        ├─> risks: List[str]
        ├─> acceptance_criteria: List[str]
        └─> implementation_plan: List[str]
```

#### Input

```python
{
    "title": "Add timeout support to BuildRun",
    "description": "Users need to specify build timeout to prevent hanging builds",
    "repo_path": "/path/to/shipwright-build"  # Optional
}
```

#### Processing Steps

1. **Client Initialization**: Get Anthropic client (handles API key or Vertex AI)
2. **Repository Analysis** (if repo_path provided):
   - Search for API types (`*_types.go`)
   - Find controllers
   - Locate CRD definitions
   - Analyze package structure
3. **Context Building**:
   - Load Shipwright component definitions
   - Format component purposes and dependencies
   - Include build strategies and OpenShift integrations
4. **Prompt Construction**:
   - Combine issue details + component info + repo context
   - Request structured design output
5. **API Call**:
   - Model: `claude-sonnet-4-20250514`
   - Max tokens: 8000
   - Temperature: default (1.0)
6. **Response Parsing**:
   - Extract sections using markdown headers
   - Parse bullet points into lists
   - Identify component mentions in text

#### Output

```python
{
    "design_analysis": "# Design for Timeout Support\n\n## Problem Statement\n...",
    "impacted_components": ["buildrun_api", "buildrun_controller", "buildrun_webhook"],
    "risks": ["Backward compatibility with existing BuildRuns", ...],
    "acceptance_criteria": ["BuildRun accepts timeout field", ...],
    "implementation_plan": ["Add timeout field to BuildRunSpec", ...]
}
```

#### Error Handling

- **Missing API Key**: Raises `DesignAgentError`
- **API Call Failure**: Logs error, raises `DesignAgentError`
- **Repository Analysis Failure**: Continues with component metadata only

---

### 2. Development Agent

**File**: `agents/go_k8s_developer.py`

**Purpose**: Generates production-quality Go code, unit tests, and PR descriptions.

**Entry Point**: `run_development(context: Dict[str, Any], repo_path: Optional[str]) -> Dict[str, Any]`

#### Flow Diagram

```
START: run_development(context)
    │
    ├─> Validate context
    │   │
    │   ├─> Required: issue_title, design_analysis, implementation_plan
    │   └─> Optional: impacted_components, acceptance_criteria, risks
    │
    ├─> Emit heartbeat (development_start)
    │
    ├─> Initialize Claude client
    │
    ├─> Build development prompt
    │   │
    │   ├─> Include: Issue info, design analysis, implementation plan
    │   ├─> Include: Acceptance criteria, risks
    │   ├─> Add: Security requirements (TLS 1.3, no hardcoded secrets)
    │   ├─> Add: Code generation instructions (Go docs, error handling)
    │   └─> Add: Test generation instructions (table-driven tests)
    │
    ├─> Call Claude API
    │   │
    │   ├─> Model: claude-sonnet-4-20250514
    │   ├─> Max Tokens: 16000 (larger for code)
    │   ├─> Temperature: 0.2 (deterministic)
    │   └─> System Prompt: DEVELOPMENT_AGENT_PROMPT
    │
    ├─> Parse development output
    │   │
    │   ├─> Extract "Code Files" section
    │   │   └─> Parse file paths and code blocks
    │   │
    │   ├─> Extract "Test Files" section
    │   │   └─> Parse test file paths and code blocks
    │   │
    │   ├─> Extract "PR Description" section
    │   │   └─> Ensure "Generated by AI" footer
    │   │
    │   ├─> Extract "Security Notes" section
    │   ├─> Extract "Dependencies" section
    │   └─> Extract "Next Steps" section
    │
    ├─> Synthesize file tracking
    │   │
    │   ├─> Build code_changes dict (path → description)
    │   └─> Build files_modified list
    │
    ├─> Emit heartbeat (development_complete)
    │
    └─> Return development_output
        │
        ├─> code_files: List[dict] (path, content, description)
        ├─> test_files: List[dict] (path, content)
        ├─> code_changes: Dict[str, str]
        ├─> files_modified: List[str]
        ├─> pr_description: str
        ├─> security_notes: List[str]
        ├─> dependencies: List[str]
        ├─> next_steps: List[str]
        └─> raw_output: str (for debugging)
```

#### Input (Context)

```python
{
    "issue_title": "Add timeout support to BuildRun",
    "implementation_plan": ["Add timeout field to BuildRunSpec", ...],
    "design_analysis": "# Design document...",
    "impacted_components": ["buildrun_api", "buildrun_controller"],
    "acceptance_criteria": ["BuildRun accepts timeout field", ...],
    "risks": ["Backward compatibility", ...],
    "session_id": "abc-123"  # For logging
}
```

#### Processing Steps

1. **Validation**: Check required fields exist and are correct types
2. **Heartbeat**: Emit `development_start` to dashboard
3. **Prompt Building**:
   - Format issue information
   - Include design analysis and implementation plan
   - Add security requirements (TLS 1.3, input validation, no secrets)
   - Specify output structure (Code Files, Tests, PR Description)
4. **API Call**:
   - Model: `claude-sonnet-4-20250514`
   - Max tokens: 16000
   - Temperature: 0.2 (more deterministic for code)
5. **Parsing**:
   - Split response into sections by `##` headers
   - Extract Go code from code blocks
   - Parse file paths from headers or `**File:**` markers
   - Ensure PR description has "Generated by AI" footer
6. **File Tracking**: Create mappings for orchestrator consumption
7. **Heartbeat**: Emit `development_complete`

#### Output

```python
{
    "code_files": [
        {
            "path": "pkg/apis/build/v1beta1/buildrun_types.go",
            "content": "package v1beta1\n\n// BuildRunSpec defines...",
            "description": "Add Timeout field to BuildRunSpec"
        }
    ],
    "test_files": [
        {
            "path": "pkg/apis/build/v1beta1/buildrun_types_test.go",
            "content": "package v1beta1\n\nfunc TestBuildRunTimeout(t *testing.T) {...}"
        }
    ],
    "code_changes": {
        "pkg/apis/build/v1beta1/buildrun_types.go": "Add Timeout field to BuildRunSpec",
        "pkg/apis/build/v1beta1/buildrun_types_test.go": "Test implementation"
    },
    "files_modified": ["pkg/apis/build/v1beta1/buildrun_types.go", ...],
    "pr_description": "## Summary\n\nAdds timeout support...\n\n---\nGenerated by AI",
    "security_notes": ["Uses TLS 1.3 for secure connections", ...],
    "dependencies": [],
    "next_steps": ["Add integration tests", ...]
}
```

---

### 3. Testing Agent

**File**: `agents/testing_agent.py`

**Purpose**: Generates comprehensive Ginkgo v2 test suites with test plans and specifications.

**Entry Point**: `run_testing(context: Dict[str, Any]) -> Dict[str, Any]`

#### Flow Diagram

```
START: run_testing(context)
    │
    ├─> Validate context
    │   │
    │   └─> Required: design_analysis, impacted_components, acceptance_criteria
    │
    ├─> Initialize Claude client
    │
    ├─> Detect patterns
    │   │
    │   ├─> Scan issue description + design for:
    │   │   ├─> Build strategies (Buildpacks, S2I, Buildah, Kaniko)
    │   │   ├─> Source types (Git, Bundle, OCI Artifact)
    │   │   ├─> Output types (Image, OCI Artifact)
    │   │   └─> Security contexts (Restricted, Baseline)
    │   │
    │   └─> Return patterns_detected dict
    │
    ├─> Build testing prompt
    │   │
    │   ├─> Include: Issue info, design analysis
    │   ├─> Include: Impacted components, acceptance criteria
    │   ├─> Include: Detected patterns
    │   ├─> Add: Test generation instructions
    │   │   ├─> Test Plan (human-readable strategy)
    │   │   ├─> Test Specifications (YAML format)
    │   │   ├─> Unit Tests (mock-based, fast)
    │   │   ├─> Integration Tests (real k8s cluster)
    │   │   └─> E2E Tests (full workflow)
    │   │
    │   └─> Add: Ginkgo v2 guidelines
    │
    ├─> Call Claude API
    │   │
    │   ├─> Model: claude-sonnet-4-20250514
    │   ├─> Max Tokens: 16000 (for test code)
    │   └─> System Prompt: TESTING_AGENT_PROMPT
    │
    ├─> Parse test output
    │   │
    │   ├─> Extract "Test Plan" section
    │   │
    │   ├─> Extract "Test Specifications" section
    │   │   └─> Parse YAML from code blocks
    │   │
    │   ├─> Extract "Unit Tests" section
    │   │   └─> Extract Go test code
    │   │
    │   ├─> Extract "Integration Tests" section
    │   │   └─> Extract Ginkgo test code
    │   │
    │   ├─> Extract "E2E Tests" section
    │   │   └─> Extract E2E test code
    │   │
    │   └─> Extract "Test Summary" section
    │
    └─> Return testing_output
        │
        ├─> test_plan: str (human-readable plan)
        ├─> test_specifications: dict (YAML specs)
        ├─> unit_tests: Dict[str, str] (file → code)
        ├─> integration_tests: Dict[str, str] (file → code)
        ├─> e2e_tests: Dict[str, str] (file → code)
        ├─> test_summary: str
        ├─> coverage_analysis: str
        ├─> patterns_detected: dict
        └─> raw_output: str
```

#### Input (Context)

```python
{
    "design_analysis": "# Design document...",
    "impacted_components": ["buildrun_api", "buildrun_controller"],
    "acceptance_criteria": ["BuildRun accepts timeout field", ...],
    "issue_title": "Add timeout support",
    "issue_description": "Users need build timeout configuration",
    "implementation_plan": ["Add timeout field...", ...],
    "risks": ["Backward compatibility", ...],
    "session_id": "abc-123"
}
```

#### Processing Steps

1. **Validation**: Check required fields
2. **Pattern Detection**: Scan description/design for:
   - Build strategies (Buildpacks, S2I, etc.)
   - Source types (Git, Bundle, etc.)
   - Output types (Image, OCI Artifact)
   - Security contexts
3. **Prompt Building**:
   - Include design analysis and acceptance criteria
   - Add detected patterns for context-aware test generation
   - Specify Ginkgo v2 syntax requirements
   - Request data-driven tests (DescribeTable)
4. **API Call**: Similar to other agents
5. **Parsing**:
   - Extract test plan (strategy document)
   - Parse YAML test specifications
   - Extract test code from code blocks
   - Detect file paths from headers

#### Output

```python
{
    "test_plan": "# Test Strategy\n\n## Approach\n...",
    "test_specifications": {
        "tests": [
            {
                "id": "BUILD-TIMEOUT-001",
                "type": "unit",
                "scenario": "Timeout field validation",
                "pattern": "buildrun_api"
            }
        ]
    },
    "unit_tests": {
        "pkg/apis/build/v1beta1/buildrun_timeout_test.go": "package v1beta1\n\n..."
    },
    "integration_tests": {
        "test/integration/buildrun_timeout_test.go": "package integration\n\n..."
    },
    "e2e_tests": {
        "test/e2e/buildrun_timeout_test.go": "package e2e\n\n..."
    },
    "test_summary": "Generated 3 unit tests, 2 integration tests, 1 E2E test",
    "coverage_analysis": "Coverage: 100% of acceptance criteria",
    "patterns_detected": {
        "strategies": ["Buildpacks"],
        "source_types": ["Git"]
    }
}
```

---

### 4. Documentation Agent

**File**: `agents/docs_agent.py`

**Purpose**: Generates PR summaries, release notes, documentation changes, and high-level designs.

**Entry Point**: `run_docs(context: Dict[str, Any], input_files: Optional[List[str]], output_format: str, enable_rag: bool) -> Dict[str, Any]`

#### Flow Diagram

```
START: run_docs(context)
    │
    ├─> Validate context
    │   │
    │   └─> Required: design_analysis, code_changes, test_results
    │
    ├─> Initialize RAG search (if enabled and repo_path provided)
    │   │
    │   ├─> Search Shipwright docs for related content
    │   │   └─> Query: issue_title
    │   │
    │   ├─> Extract code examples from modified files
    │   │
    │   ├─> Search for similar code implementations
    │   │
    │   └─> Find API usage patterns
    │       └─> Extract API names from design analysis
    │
    ├─> Process input files (if provided)
    │   │
    │   ├─> Read each file from repo_path
    │   ├─> Truncate if > 5000 chars
    │   └─> Store in file_contents dict
    │
    ├─> Build context message
    │   │
    │   ├─> Issue information (title, description, type)
    │   ├─> Design phase outputs (analysis, plan, components, risks)
    │   ├─> Development phase outputs (code changes, files modified)
    │   ├─> Test phase outputs (results, summary, coverage gaps)
    │   ├─> RAG context (related docs, code examples, API patterns)
    │   ├─> Input file context
    │   └─> Generation request (based on output_format)
    │
    ├─> Call Claude API
    │   │
    │   ├─> Model: claude-sonnet-4-20250514
    │   ├─> Max Tokens: 8192 (increased for comprehensive docs)
    │   ├─> Temperature: 0.3 (consistent documentation)
    │   └─> System Prompt: DOCS_AGENT_PROMPT
    │
    ├─> Parse docs response
    │   │
    │   ├─> Split into sections by ## headers
    │   │
    │   ├─> Extract "PR Summary"
    │   ├─> Extract "Release Notes"
    │   ├─> Extract "Documentation Changes"
    │   │   └─> Parse file paths and change descriptions
    │   ├─> Extract "Upgrade Notes"
    │   ├─> Extract "Known Limitations"
    │   ├─> Extract "High-Level Design"
    │   ├─> Extract "JTBD Documentation" (if format=jtbd or all)
    │   └─> Extract "SHIP Document" (if format=ship or all)
    │
    └─> Return docs_output
        │
        ├─> pr_summary: str
        ├─> release_notes: str
        ├─> docs_changes: Dict[str, str]
        ├─> upgrade_notes: str
        ├─> known_limitations: str
        ├─> jtbd_documentation: str
        ├─> ship_document: str
        ├─> high_level_design: str
        ├─> input_files_analyzed: List[str]
        ├─> rag_enabled: bool
        └─> output_format: str
```

#### Input (Context)

```python
{
    "design_analysis": "# Design document...",
    "implementation_plan": ["Add timeout field...", ...],
    "code_changes": {"pkg/apis/build/v1beta1/buildrun_types.go": "Add Timeout field"},
    "files_modified": ["pkg/apis/build/v1beta1/buildrun_types.go"],
    "test_results": {"passed": 10, "failed": 0},
    "test_summary": "All tests passed",
    "issue_title": "Add timeout support",
    "issue_description": "Users need build timeout",
    "issue_type": "feature",
    "repo_path": "/path/to/repo",  # For RAG
    "session_id": "abc-123"
}
```

#### Processing Steps

1. **Validation**: Check required fields
2. **RAG Search** (if enabled):
   - Search Shipwright documentation for related content
   - Extract code examples from modified files
   - Find similar implementations
   - Identify API usage patterns
3. **Input File Processing**:
   - Read specified files from repository
   - Include their content in context
4. **Context Building**:
   - Combine all agent outputs
   - Add RAG-retrieved documentation
   - Add input file contents
   - Format according to output_format
5. **API Call**: Lower temperature for consistency
6. **Parsing**: Extract structured sections

#### Output

```python
{
    "pr_summary": "## Summary\n\nAdds timeout support to BuildRun CRD...",
    "release_notes": "### Features\n- Add timeout configuration to BuildRun",
    "docs_changes": {
        "docs/buildrun.md": "Add timeout field documentation",
        "docs/api-reference.md": "Update BuildRunSpec with Timeout"
    },
    "upgrade_notes": "No breaking changes. Timeout field is optional.",
    "known_limitations": "Timeout only applies to build execution, not cleanup.",
    "jtbd_documentation": "# Job: Configure build timeout\n...",
    "ship_document": "# SHIP: BuildRun Timeout\n\n## Solution\n...",
    "high_level_design": "# High-Level Design\n\n## Architecture\n...",
    "input_files_analyzed": ["pkg/apis/build/v1beta1/buildrun_types.go"],
    "rag_enabled": true,
    "output_format": "all"
}
```

---

## LangGraph Orchestrator

**File**: `agents/graph.py`

### Purpose

Coordinates the multi-agent workflow using LangGraph's state machine, managing:
- State transitions between phases
- Conditional routing based on completion status
- Error handling and recovery
- Heartbeat emission for dashboard tracking

### State Schema

**File**: `graph/state.py`

```python
class AgentState(TypedDict):
    """State shared across all agents in the workflow."""

    # Input
    issue_title: str
    issue_description: str
    issue_type: str  # "bug", "feature", "refactor", "docs"

    # Design phase outputs
    design_analysis: str
    impacted_components: list[str]
    risks: list[str]
    acceptance_criteria: list[str]
    implementation_plan: list[str]

    # Testing phase outputs
    test_plan: str
    test_specifications: dict
    unit_tests: dict[str, str]
    integration_tests: dict[str, str]
    e2e_tests: dict[str, str]
    coverage_analysis: str

    # Development phase outputs
    code_files: list
    test_files: list
    code_changes: dict[str, str]
    files_modified: list[str]
    pr_description: str
    test_results: dict

    # Test execution outputs
    test_summary: str
    coverage_gaps: list[str]
    test_failures: list[str]

    # Documentation phase outputs
    pr_summary: str
    release_notes: str
    docs_changes: dict[str, str]
    upgrade_notes: str
    known_limitations: str
    jtbd_documentation: str
    ship_document: str
    high_level_design: str

    # Control flow
    session_id: str
    current_phase: str  # "design", "development", "test", "docs", "done"
    approval_status: str  # "pending", "approved", "rejected"

    # Messages for agent communication
    messages: Annotated[Sequence[dict], add_messages]

    # Repository context
    repo_path: str
    target_branch: str
```

### Workflow Graph Construction

```python
def build_workflow() -> StateGraph:
    """Build the LangGraph workflow."""

    # Create the graph with AgentState schema
    workflow = StateGraph(AgentState)

    # Add nodes (agent execution functions)
    workflow.add_node("design", design_node)
    workflow.add_node("develop", develop_node)
    workflow.add_node("testing", testing_node)
    workflow.add_node("docs", docs_node)

    # Set entry point
    workflow.set_entry_point("design")

    # Add conditional edges from design
    workflow.add_conditional_edges(
        "design",
        should_continue,
        {
            "develop": "develop",
            "end": END,
        }
    )

    # Add conditional edges from develop
    workflow.add_conditional_edges(
        "develop",
        should_continue,
        {
            "testing": "testing",
            "end": END,
        }
    )

    # Add conditional edges from testing
    workflow.add_conditional_edges(
        "testing",
        should_continue,
        {
            "docs": "docs",
            "end": END,
        }
    )

    # Add edge from docs to END
    workflow.add_edge("docs", END)

    # Compile the graph
    return workflow.compile()
```

### Workflow Phases

#### 1. Design Node

```python
def design_node(state: AgentState) -> Dict[str, Any]:
    """Execute the Design Agent phase."""
    try:
        # Run design agent
        design_output = run_design(
            title=state["issue_title"],
            description=state["issue_description"],
            repo_path=state.get("repo_path"),
        )

        # Update state with design outputs
        updated_state = {
            "design_analysis": design_output["design_analysis"],
            "impacted_components": design_output["impacted_components"],
            "risks": design_output["risks"],
            "acceptance_criteria": design_output["acceptance_criteria"],
            "implementation_plan": design_output.get("implementation_plan", []),
            "current_phase": "design_complete",
        }

        # Emit heartbeat to dashboard
        complete_state = {**state, **updated_state}
        emit_heartbeat("design", complete_state)

        return updated_state

    except Exception as e:
        error_state = {
            "design_analysis": f"Error in design phase: {str(e)}",
            "current_phase": "error",
        }
        emit_heartbeat("design", {**state, **error_state})
        return error_state
```

**Flow**:
1. Call `run_design()` with issue title and description
2. Extract design outputs
3. Update state with `current_phase="design_complete"`
4. Emit heartbeat to dashboard
5. Return updated state (merged by LangGraph)

#### 2. Development Node

Similar structure, calls `run_development(state)`.

**Key Differences**:
- Takes full state as input (needs design outputs)
- Emits `develop` heartbeat
- Sets `current_phase="develop_complete"`

#### 3. Testing Node

Similar structure, calls `run_testing(context)`.

**Key Differences**:
- Prepares context from state
- Emits `testing` heartbeat
- Sets `current_phase="testing_complete"`

#### 4. Documentation Node

Similar structure, calls `run_docs(context)`.

**Key Differences**:
- Emits `docs` heartbeat
- Sets `current_phase="done"`

### Conditional Routing

```python
def should_continue(state: AgentState) -> Literal["develop", "testing", "docs", "end"]:
    """Determine if workflow should continue to next phase."""
    phase = state.get("current_phase", "")

    # Design → Development
    if phase == "design_complete":
        return "develop"

    # Development → Testing
    if phase == "develop_complete":
        return "testing"

    # Testing → Docs
    if phase == "testing_complete":
        return "docs"

    # Otherwise, end
    return "end"
```

**Logic**:
- Checks `current_phase` field in state
- Routes to next agent based on completion status
- Returns `"end"` if phase is `"done"` or `"error"`

### Error Handling

Each node has try-except block:

```python
try:
    # Run agent
    output = run_agent(...)
    updated_state = {
        "agent_output": output,
        "current_phase": "phase_complete"
    }
    emit_heartbeat("agent", {**state, **updated_state})
    return updated_state

except Exception as e:
    error_state = {
        "error": str(e),
        "current_phase": "error"
    }
    emit_heartbeat("agent", {**state, **error_state})
    return error_state
```

**Error Flow**:
1. Exception caught in node
2. State updated with `current_phase="error"`
3. Error heartbeat emitted
4. `should_continue()` routes to END
5. Final state contains error information

### Entry Point: orchestrate()

```python
def orchestrate(
    title: str,
    description: str,
    repo_path: str = None,
    issue_type: str = "feature",
) -> Dict[str, Any]:
    """Orchestrate the multi-agent workflow."""

    # Generate session ID for dashboard tracking
    session_id = str(uuid.uuid4())

    # Initialize state
    initial_state = {
        "session_id": session_id,
        "issue_title": title,
        "issue_description": description,
        "issue_type": issue_type,
        "repo_path": repo_path or "",
        "target_branch": "main",
        "current_phase": "init",
        "approval_status": "pending",
        "messages": [],
        # Initialize all optional fields to empty values
        "design_analysis": "",
        "impacted_components": [],
        # ... (all other fields)
    }

    # Emit initial heartbeat
    emit_heartbeat("orchestrator", initial_state)

    # Run the workflow
    final_state = graph.invoke(initial_state)

    return final_state
```

**Steps**:
1. Generate unique session ID
2. Create initial state with minimal data
3. Emit heartbeat to register session in dashboard
4. Invoke compiled graph with initial state
5. Return final state (contains all agent outputs)

---

## Dashboard Integration

### Heartbeat System

**File**: `dashboard/heartbeat.py`

#### Purpose

Provides a protocol for agents to report their state to the dashboard in real-time.

#### Key Classes

**HeartbeatConfig**:
```python
class HeartbeatConfig:
    dashboard_url: str = "http://localhost:8080"
    enabled: bool = True
    interval_seconds: int = 3
    timeout_seconds: int = 2
```

**Heartbeat**:
```python
class Heartbeat:
    session_id: str
    agent: str  # "design", "develop", "testing", "docs"
    phase: str  # Current workflow phase
    raw_state: Dict[str, Any]  # Complete agent state
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-ready dictionary."""
```

**HeartbeatEmitter**:
```python
class HeartbeatEmitter:
    def emit(self, heartbeat: Heartbeat) -> bool:
        """Send heartbeat to dashboard API."""
        response = requests.post(
            f"{dashboard_url}/api/heartbeat",
            json=heartbeat.to_dict(),
            timeout=timeout_seconds
        )
        return response.status_code == 200
```

#### Usage in Agents

```python
from dashboard.heartbeat import emit_heartbeat

# In agent code
emit_heartbeat("design", {
    **state,
    "phase": "design_complete"
})
```

**When Heartbeats are Emitted**:
- Start of each agent phase
- Completion of each agent phase
- On errors

### Dashboard Backend

**File**: `dashboard/backend.py`

#### Architecture

```
FastAPI Application
    │
    ├─> SQLite Database
    │   ├─> sessions table
    │   └─> heartbeats table
    │
    ├─> Enrichers Pipeline
    │   └─> dashboard/enrichers.py
    │
    └─> REST API Endpoints
        ├─> POST /api/heartbeat
        ├─> GET /api/sessions
        ├─> GET /api/sessions/{session_id}
        ├─> DELETE /api/sessions/cleanup
        ├─> DELETE /api/sessions/completed
        └─> GET /api/health
```

#### Database Schema

**sessions table**:
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    issue_title TEXT,
    issue_type TEXT,
    status TEXT DEFAULT 'active'
)
```

**heartbeats table**:
```sql
CREATE TABLE heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    phase TEXT,
    timestamp TIMESTAMP NOT NULL,
    model TEXT,
    context_tokens INTEGER,
    context_percent REAL,
    status TEXT,
    raw_state TEXT,  -- JSON
    enriched_data TEXT,  -- JSON
    FOREIGN KEY (session_id) REFERENCES sessions(id)
)
```

#### API Endpoints

**POST /api/heartbeat**:
```python
@app.post("/api/heartbeat")
async def receive_heartbeat(heartbeat: HeartbeatRequest):
    # Convert to dict
    heartbeat_dict = heartbeat.model_dump()

    # Enrich heartbeat (add metadata)
    enriched = enrich_heartbeat(heartbeat_dict)

    # Upsert session
    db.upsert_session(
        session_id=enriched["session_id"],
        issue_title=enriched.get("issue_title", "Unknown Task"),
        issue_type=enriched.get("issue_type", "feature")
    )

    # Insert heartbeat
    db.insert_heartbeat(enriched)

    return {"status": "ok"}
```

**GET /api/sessions**:
```python
@app.get("/api/sessions")
async def get_sessions(limit: int = 100):
    """Get all sessions with latest heartbeat."""
    sessions = db.get_sessions(limit=limit)
    return sessions
```

**DELETE /api/sessions/completed**:
```python
@app.delete("/api/sessions/completed")
async def clear_completed_sessions():
    """Clear all sessions with phase='done' or 'error'."""
    result = db.clear_completed_sessions()
    return result
```

#### Enrichers Pipeline

**File**: `dashboard/enrichers.py`

Enriches raw heartbeat data with additional metadata:
- Extract model information from raw_state
- Calculate context usage percentages
- Determine status badges (running, success, error)
- Format timestamps

### Dashboard Frontend

**File**: `dashboard/frontend/index.html`

#### Features

1. **Auto-Refresh**: Polls `/api/sessions` every 3 seconds
2. **Session List**: Displays all active and completed sessions
3. **Agent Status**: Shows progress through phases with badges
4. **Clear Button**: Calls `/api/sessions/completed` to clear finished sessions

#### Data Flow

```
Frontend (JavaScript)
    │
    ├─> setInterval(() => fetchSessions(), 3000)
    │
    ├─> fetch('/api/sessions')
    │       │
    │       └─> Returns: List[SessionResponse]
    │
    ├─> renderSessions(sessions)
    │   │
    │   ├─> For each session:
    │   │   ├─> Display issue title
    │   │   ├─> Display agent status badges
    │   │   │   └─> Check latest_heartbeat.agent and latest_heartbeat.phase
    │   │   └─> Display timestamp
    │   │
    │   └─> Update DOM
    │
    └─> Clear Sessions Button
        │
        └─> fetch('/api/sessions/completed', {method: 'DELETE'})
            └─> Refresh session list
```

---

## Complete Flow Example

Let's trace a full workflow from start to finish:

### User Input

```bash
python scripts/orchestrate.py \
    --title "Add timeout support to BuildRun" \
    --description "Users need to configure build timeout to prevent hanging builds"
```

### Step-by-Step Execution

#### 1. Orchestrator Initialization

**File**: `scripts/orchestrate.py` → `agents/graph.py:orchestrate()`

```python
# Generate session ID
session_id = "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"

# Initialize state
initial_state = {
    "session_id": session_id,
    "issue_title": "Add timeout support to BuildRun",
    "issue_description": "Users need to configure build timeout...",
    "issue_type": "feature",
    "repo_path": "",
    "current_phase": "init",
    # ... all other fields initialized to empty
}

# Emit initial heartbeat
emit_heartbeat("orchestrator", initial_state)
# → POST /api/heartbeat with session_id, phase="init"
```

**Dashboard Effect**:
- Session created in database
- Frontend shows new session with "init" phase

#### 2. Design Phase

**File**: `agents/graph.py:design_node()` → `agents/design_agent.py:run_design()`

```python
# design_node() calls run_design()
design_output = run_design(
    title="Add timeout support to BuildRun",
    description="Users need to configure build timeout...",
    repo_path=None
)

# run_design() process:
# 1. Initialize Claude client
# 2. Skip repo context (no repo_path)
# 3. Build component context (from config/shipwright_components.py)
# 4. Construct prompt
# 5. Call Claude API (8000 tokens)
# 6. Parse response

# Response parsed into:
design_output = {
    "design_analysis": """
# Design: BuildRun Timeout Support

## Problem Statement
Users need the ability to configure a timeout for BuildRun executions...

## Impacted Components
- buildrun_api: Add Timeout field to BuildRunSpec
- buildrun_controller: Implement timeout logic
- buildrun_webhook: Validate timeout values

## Risks
- Backward compatibility with existing BuildRuns
- Default timeout value selection
- Timeout enforcement during cleanup phase

## Acceptance Criteria
- BuildRun CRD accepts optional Timeout field
- Timeout value validated as positive duration
- Running BuildRun terminates after timeout expires
- Timeout event logged and reported in status

## Implementation Plan
1. Add Timeout field to BuildRunSpec (metav1.Duration)
2. Update validation webhook to check timeout format
3. Modify controller reconciliation loop to monitor timeout
4. Add timeout context to build pod execution
5. Update status conditions to report timeout events
""",
    "impacted_components": ["buildrun_api", "buildrun_controller", "buildrun_webhook"],
    "risks": ["Backward compatibility...", "Default timeout...", "Timeout enforcement..."],
    "acceptance_criteria": ["BuildRun CRD accepts...", "Timeout value validated...", ...],
    "implementation_plan": ["Add Timeout field...", "Update validation webhook...", ...]
}

# Update state
updated_state = {
    "design_analysis": design_output["design_analysis"],
    "impacted_components": design_output["impacted_components"],
    "risks": design_output["risks"],
    "acceptance_criteria": design_output["acceptance_criteria"],
    "implementation_plan": design_output["implementation_plan"],
    "current_phase": "design_complete"
}

# Emit heartbeat
emit_heartbeat("design", {**state, **updated_state})
# → POST /api/heartbeat with phase="design_complete"
```

**Dashboard Effect**:
- Session updated with `phase="design_complete"`
- Frontend shows "Design: ✅ Complete"

#### 3. Development Phase

**File**: `agents/graph.py:develop_node()` → `agents/go_k8s_developer.py:run_development()`

```python
# should_continue() routes to "develop"

# develop_node() calls run_development()
development_output = run_development(state)

# Emit start heartbeat
emit_heartbeat("development", {**context, "phase": "development_start"})

# run_development() process:
# 1. Validate context (has required fields)
# 2. Build prompt with design analysis + implementation plan
# 3. Add security requirements to prompt
# 4. Call Claude API (16000 tokens, temp=0.2)
# 5. Parse code files, test files, PR description

# Response parsed into:
development_output = {
    "code_files": [
        {
            "path": "pkg/apis/build/v1beta1/buildrun_types.go",
            "content": """package v1beta1
import metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

// BuildRunSpec defines the desired state of BuildRun
type BuildRunSpec struct {
    // ... existing fields ...

    // Timeout defines the maximum duration for the build execution.
    // If the build does not complete within this time, it will be terminated.
    // +optional
    Timeout *metav1.Duration `json:"timeout,omitempty"`
}
""",
            "description": "Add Timeout field to BuildRunSpec"
        },
        {
            "path": "pkg/webhook/buildrun/validate.go",
            "content": """package buildrun
// Validation logic for timeout field
func validateTimeout(timeout *metav1.Duration) error {
    if timeout != nil && timeout.Duration <= 0 {
        return fmt.Errorf("timeout must be positive")
    }
    return nil
}
""",
            "description": "Add timeout validation"
        }
    ],
    "test_files": [
        {
            "path": "pkg/apis/build/v1beta1/buildrun_types_test.go",
            "content": """package v1beta1_test
func TestBuildRunTimeout(t *testing.T) {
    tests := []struct{
        name string
        timeout *metav1.Duration
        wantErr bool
    }{
        {name: "valid timeout", timeout: &metav1.Duration{Duration: 5*time.Minute}, wantErr: false},
        {name: "zero timeout", timeout: &metav1.Duration{Duration: 0}, wantErr: true},
    }
    // ...
}
"""
        }
    ],
    "pr_description": """## Summary
Adds timeout support to BuildRun CRD...

## Security Considerations
- Input validation ensures positive duration
- No hardcoded values or secrets

---
Generated by AI""",
    "security_notes": ["Input validation for timeout values", ...],
    "dependencies": [],
    "next_steps": ["Add integration tests", "Update API documentation"]
}

# Emit complete heartbeat
emit_heartbeat("development", {**context, "phase": "development_complete"})
```

**Dashboard Effect**:
- Session updated with `phase="development_complete"`
- Frontend shows "Design: ✅, Development: ✅"

#### 4. Testing Phase

**File**: `agents/graph.py:testing_node()` → `agents/testing_agent.py:run_testing()`

```python
# should_continue() routes to "testing"

# testing_node() prepares context and calls run_testing()
testing_output = run_testing(context)

# run_testing() process:
# 1. Detect patterns in description (no specific patterns in this case)
# 2. Build prompt with design + acceptance criteria
# 3. Call Claude API (16000 tokens)
# 4. Parse test plan, specifications, and code

# Response parsed into:
testing_output = {
    "test_plan": """# Test Strategy for BuildRun Timeout

## Approach
- Unit tests: API field validation
- Integration tests: Controller timeout enforcement
- E2E tests: Full build with timeout

## Coverage Mapping
- AC1 "BuildRun accepts timeout" → Unit test BUILD-TIMEOUT-001
- AC2 "Timeout validated" → Unit test BUILD-TIMEOUT-002
- AC3 "Build terminates after timeout" → Integration test BUILD-TIMEOUT-003
""",
    "test_specifications": {
        "tests": [
            {"id": "BUILD-TIMEOUT-001", "type": "unit", "scenario": "Timeout field accepts valid duration"},
            {"id": "BUILD-TIMEOUT-002", "type": "unit", "scenario": "Timeout field rejects invalid duration"},
            {"id": "BUILD-TIMEOUT-003", "type": "integration", "scenario": "BuildRun terminates after timeout"}
        ]
    },
    "unit_tests": {
        "pkg/apis/build/v1beta1/buildrun_timeout_test.go": """...Ginkgo test code..."""
    },
    "integration_tests": {
        "test/integration/buildrun_timeout_test.go": """...Ginkgo integration test..."""
    },
    "e2e_tests": {
        "test/e2e/buildrun_timeout_test.go": """...E2E test code..."""
    },
    "test_summary": "Generated 2 unit tests, 1 integration test, 1 E2E test",
    "coverage_analysis": "100% of acceptance criteria covered"
}
```

**Dashboard Effect**:
- Session updated with `phase="testing_complete"`
- Frontend shows "Design: ✅, Development: ✅, Testing: ✅"

#### 5. Documentation Phase

**File**: `agents/graph.py:docs_node()` → `agents/docs_agent.py:run_docs()`

```python
# should_continue() routes to "docs"

# docs_node() calls run_docs()
docs_output = run_docs(context)

# run_docs() process:
# 1. Skip RAG (no repo_path)
# 2. Build context message with all previous outputs
# 3. Call Claude API (8192 tokens, temp=0.3)
# 4. Parse PR summary, release notes, etc.

# Response parsed into:
docs_output = {
    "pr_summary": """## Summary
Adds timeout support to BuildRun CRD, allowing users to configure maximum build duration.

## Changes
- Added `Timeout` field to `BuildRunSpec`
- Implemented validation webhook for timeout values
- Controller monitors and enforces timeout

## Testing
- 2 unit tests for API validation
- 1 integration test for timeout enforcement
- 1 E2E test for full workflow
""",
    "release_notes": """### Features
- **BuildRun Timeout**: BuildRun now accepts an optional `timeout` field to limit build execution time
""",
    "docs_changes": {
        "docs/buildrun.md": "Add timeout field documentation with examples",
        "docs/api-reference.md": "Update BuildRunSpec with Timeout field"
    },
    "upgrade_notes": "No breaking changes. The timeout field is optional and backward compatible.",
    "known_limitations": "Timeout only applies to build execution phase, not cleanup.",
    "high_level_design": """# High-Level Design: BuildRun Timeout

## Architecture
...detailed design for implementation..."""
}

# Update state with docs outputs and phase="done"
updated_state = {
    "pr_summary": docs_output["pr_summary"],
    "release_notes": docs_output["release_notes"],
    "docs_changes": docs_output["docs_changes"],
    "current_phase": "done"
}

# Emit heartbeat
emit_heartbeat("docs", {**state, **updated_state})
```

**Dashboard Effect**:
- Session updated with `phase="done"`
- Frontend shows "Design: ✅, Development: ✅, Testing: ✅, Docs: ✅, Status: Done"

#### 6. Workflow Completion

```python
# should_continue() returns "end"
# Graph execution completes

# Final state returned to orchestrate()
final_state = {
    "session_id": "a1b2c3d4-...",
    "issue_title": "Add timeout support to BuildRun",
    "issue_description": "Users need to configure...",
    "current_phase": "done",

    # Design outputs
    "design_analysis": "# Design: BuildRun Timeout...",
    "impacted_components": ["buildrun_api", ...],
    "implementation_plan": ["Add Timeout field...", ...],

    # Development outputs
    "code_files": [{...}, {...}],
    "test_files": [{...}],
    "pr_description": "## Summary\n...",

    # Testing outputs
    "test_plan": "# Test Strategy...",
    "unit_tests": {...},
    "integration_tests": {...},

    # Documentation outputs
    "pr_summary": "## Summary\n...",
    "release_notes": "### Features\n...",
    "docs_changes": {...}
}

# scripts/orchestrate.py prints final state
print("\n--- RESULT ---")
for k, v in final_state.items():
    print(f"\n{k.upper()}")
    print(v)
```

---

## State Management

### AgentState Fields

The `AgentState` TypedDict (defined in `graph/state.py`) contains all fields that flow through the workflow:

| Field Category | Fields | Type | Set By |
|----------------|--------|------|---------|
| **Input** | `issue_title`, `issue_description`, `issue_type` | str | Orchestrator (initial) |
| **Control** | `session_id`, `current_phase`, `approval_status` | str | Orchestrator |
| **Repository** | `repo_path`, `target_branch` | str | Orchestrator |
| **Design** | `design_analysis`, `impacted_components`, `risks`, `acceptance_criteria`, `implementation_plan` | str/list | Design Agent |
| **Development** | `code_files`, `test_files`, `code_changes`, `files_modified`, `pr_description` | list/dict/str | Development Agent |
| **Testing** | `test_plan`, `test_specifications`, `unit_tests`, `integration_tests`, `e2e_tests`, `coverage_analysis` | str/dict | Testing Agent |
| **Test Results** | `test_results`, `test_summary`, `coverage_gaps`, `test_failures` | dict/str/list | Testing Agent |
| **Documentation** | `pr_summary`, `release_notes`, `docs_changes`, `upgrade_notes`, `known_limitations`, `jtbd_documentation`, `ship_document`, `high_level_design` | str/dict | Docs Agent |
| **Messages** | `messages` | Annotated[Sequence[dict], add_messages] | Agents (LangGraph) |

### State Flow

```
Initial State (orchestrate())
    ↓
Design Node adds:
    - design_analysis
    - impacted_components
    - risks
    - acceptance_criteria
    - implementation_plan
    - current_phase = "design_complete"
    ↓
Development Node adds:
    - code_files
    - test_files
    - code_changes
    - files_modified
    - pr_description
    - current_phase = "develop_complete"
    ↓
Testing Node adds:
    - test_plan
    - test_specifications
    - unit_tests
    - integration_tests
    - e2e_tests
    - test_summary
    - coverage_analysis
    - current_phase = "testing_complete"
    ↓
Documentation Node adds:
    - pr_summary
    - release_notes
    - docs_changes
    - upgrade_notes
    - known_limitations
    - jtbd_documentation
    - ship_document
    - high_level_design
    - current_phase = "done"
    ↓
Final State (contains all fields)
```

### State Merging

LangGraph automatically merges the dictionaries returned by each node:

```python
# Node returns partial state update
def design_node(state: AgentState) -> Dict[str, Any]:
    return {
        "design_analysis": "...",
        "current_phase": "design_complete"
    }

# LangGraph merges with existing state
# state = {**state, **design_node(state)}
```

---

## Logging System

**File**: `utils/file_logger.py`

### Logger Types

1. **Module-Level Loggers**: One per Python module
2. **Session-Specific Loggers**: One per session, per agent

### Usage

```python
from utils.file_logger import get_logger, get_session_logger

# Module logger (logs to logs/agents/design_agent.log)
logger = get_logger(__name__)
logger.info("Starting design analysis")

# Session logger (logs to logs/sessions/{session_id}/design_agent.log)
session_id = context.get("session_id", "unknown")
session_logger = get_session_logger(session_id, "design_agent")
session_logger.info(f"Design analysis for: {context.get('issue_title')}")
```

### Log Locations

```
logs/
├── agents/
│   ├── design_agent.log
│   ├── go_k8s_developer.log
│   ├── testing_agent.log
│   └── docs_agent.log
│
└── sessions/
    ├── a1b2c3d4-e5f6.../
    │   ├── design_agent.log
    │   ├── development_agent.log
    │   ├── testing_agent.log
    │   └── docs_agent.log
    │
    └── f9g8h7i6-j5k4.../
        └── ...
```

### Log Content

**Module logger** records:
- Agent lifecycle events (start, complete)
- API calls and response sizes
- Errors and warnings
- Configuration details

**Session logger** records:
- Session-specific events
- Context details for debugging
- Agent outputs and decisions

---

## Error Handling

### Error Flow

```
Agent Error Occurs
    ↓
Caught in try-except block
    ↓
Log error with stack trace
    ↓
Create error_state:
    - error: str(exception)
    - current_phase: "error"
    ↓
Emit error heartbeat to dashboard
    ↓
Return error_state
    ↓
should_continue() checks phase
    ↓
phase == "error" → return "end"
    ↓
Workflow terminates
    ↓
Final state contains error information
```

### Example

```python
def design_node(state: AgentState) -> Dict[str, Any]:
    try:
        design_output = run_design(...)
        # ... success path

    except Exception as e:
        logger.error(f"Design phase failed: {e}", exc_info=True)

        error_state = {
            "design_analysis": f"Error in design phase: {str(e)}",
            "current_phase": "error",
        }

        emit_heartbeat("design", {**state, **error_state})

        return error_state
```

### Dashboard Behavior

When `current_phase="error"`:
- Frontend shows error badge
- Session marked as failed
- Can be cleared with "Clear Sessions" button

---

## Configuration

### Authentication Configuration

**File**: `config/auth_config.py`

```python
def get_anthropic_client() -> AnthropicVertex:
    """Get configured Anthropic client via Google Vertex AI."""
    from anthropic import AnthropicVertex

    project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
    if not project_id:
        raise ValueError("ANTHROPIC_VERTEX_PROJECT_ID environment variable not set")

    return AnthropicVertex(
        project_id=project_id,
        region=os.getenv("CLOUD_ML_REGION", "us-east5")
    )
```

**Authentication Backend**:
- **Google Vertex AI**: Set `ANTHROPIC_VERTEX_PROJECT_ID` and authenticate via `gcloud auth application-default login`

### Agent Prompts

**File**: `config/agent_prompts.py`

Contains system prompts for each agent:
- `DESIGN_AGENT_PROMPT`: Defines design analysis structure
- `DEVELOPMENT_AGENT_PROMPT`: Specifies Go code generation requirements
- `TESTING_AGENT_PROMPT`: Defines Ginkgo v2 test generation
- `DOCS_AGENT_PROMPT`: Specifies documentation formats

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project ID for Vertex AI | (required) |
| `CLOUD_ML_REGION` | GCP region for Vertex AI | `us-east5` |
| `CLAUDE_MODEL` | Model version | `claude-sonnet-4-20250514` |
| `DASHBOARD_URL` | Dashboard backend URL | `http://localhost:8080` |
| `DASHBOARD_ENABLED` | Enable heartbeats | `true` |
| `DASHBOARD_DB_PATH` | SQLite database path | `/tmp/claude/dashboard.db` |

---

## Code File Reference

### Core System

| File | Purpose | Key Functions/Classes |
|------|---------|----------------------|
| `agents/graph.py` | LangGraph orchestrator | `orchestrate()`, `build_workflow()`, `design_node()`, `develop_node()`, `testing_node()`, `docs_node()`, `should_continue()` |
| `graph/state.py` | State schema definition | `AgentState` TypedDict |
| `scripts/orchestrate.py` | CLI entry point | Argument parsing, result printing |

### Agents

| File | Purpose | Key Functions |
|------|---------|---------------|
| `agents/design_agent.py` | Design analysis agent | `run_design()`, `_gather_repo_context()`, `_build_component_context()`, `_parse_design_output()` |
| `agents/go_k8s_developer.py` | Code generation agent | `run_development()`, `_build_development_prompt()`, `_parse_development_output()`, `_extract_code_files()` |
| `agents/testing_agent.py` | Test generation agent | `run_testing()`, `_build_testing_prompt()`, `_parse_test_output()`, `_extract_test_code()` |
| `agents/docs_agent.py` | Documentation agent | `run_docs()`, `_fetch_rag_context()`, `_process_input_files()`, `_parse_docs_response()` |

### Dashboard

| File | Purpose | Key Components |
|------|---------|----------------|
| `dashboard/heartbeat.py` | Heartbeat protocol | `Heartbeat`, `HeartbeatEmitter`, `emit_heartbeat()` |
| `dashboard/backend.py` | FastAPI server | `Database`, API endpoints (`/api/heartbeat`, `/api/sessions`) |
| `dashboard/enrichers.py` | Heartbeat enrichment | `enrich_heartbeat()` |
| `dashboard/frontend/index.html` | Web UI | Session list, auto-refresh, clear button |

### Utilities

| File | Purpose | Key Functions |
|------|---------|---------------|
| `utils/file_logger.py` | Logging system | `get_logger()`, `get_session_logger()` |
| `tools/repo_search.py` | Repository search | `RepoSearch` class, `search_files()`, `find_kubernetes_crds()` |
| `tools/rag_search.py` | RAG search | `RAGSearch` class, `search_shipwright_docs()`, `extract_code_examples()` |

### Configuration

| File | Purpose | Contents |
|------|---------|----------|
| `config/auth_config.py` | API authentication | `get_anthropic_client()` |
| `config/agent_prompts.py` | System prompts | `DESIGN_AGENT_PROMPT`, `DEVELOPMENT_AGENT_PROMPT`, `TESTING_AGENT_PROMPT`, `DOCS_AGENT_PROMPT` |
| `config/shipwright_components.py` | Component metadata | `COMPONENTS`, `CRD_TYPES`, `BUILD_STRATEGIES`, `OPENSHIFT_INTEGRATIONS` |
| `config/testing_config.py` | Testing patterns | `detect_patterns_in_description()`, `get_strategy_pattern()`, `GINKGO_IMPORTS` |

---

## Summary

This multi-agent system orchestrates four specialized agents (Design, Development, Testing, Documentation) using LangGraph's state machine to generate comprehensive outputs for Shipwright Build features. The system provides:

1. **Stateful Workflow**: Agents pass state through phases with clear transitions
2. **Real-Time Monitoring**: Dashboard tracks progress via heartbeat protocol
3. **Comprehensive Logging**: Session-specific and module-level logs for debugging
4. **Error Handling**: Graceful error recovery with dashboard notifications
5. **Flexible Configuration**: Supports multiple Claude API backends and output formats

The architecture enables parallel development, testing, and documentation generation while maintaining visibility into the entire process through the web dashboard.
