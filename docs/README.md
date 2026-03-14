# Multi-Agents OCP Builds

AI-powered development orchestrator for Shipwright Build and OpenShift projects. The system transforms feature requests and bug reports into design documents, production Go code, Ginkgo v2 test suites, and release documentation - all coordinated through a LangGraph state machine.

---

## Overview

When a developer submits an issue title and description, the system routes it through four specialized agents in sequence. Each agent reads the shared workflow state produced by previous agents, adds its own outputs, and passes the enriched state forward. A real-time web dashboard monitors each session as it progresses.

The result of a single run includes:

- A structured design document with component impact analysis and risk assessment
- Production-ready Go code targeting Kubernetes/OpenShift APIs
- A complete Ginkgo v2 test suite (unit, integration, and E2E)
- A PR summary, release notes, and documentation change recommendations

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    User Request                     │
│            (Issue Title + Description)              │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              LangGraph Orchestrator                 │
│  • State Management  • Phase Coordination           │
│  • Conditional Routing  • Error Handling            │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┼──────────────┬───────────┐
        │            │              │           │
        ▼            ▼              ▼           ▼
┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│    Design    │  │  Develop │  │ Testing  │  │   Docs   │
│    Agent     │─>│  Agent   │─>│  Agent   │─>│  Agent   │
└──────┬───────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
       │               │             │             │
       └───────────────┴─────────────┴─────────────┘
                       │  Heartbeats
                       ▼
┌─────────────────────────────────────────────────────┐
│              Dashboard Backend                      │
│         (FastAPI + SQLite)                          │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              Dashboard Frontend                     │
│     Real-time session cards, phase progress,        │
│     context usage, component impacts                │
└─────────────────────────────────────────────────────┘
```

The agents run sequentially. State accumulated in each phase is available to all subsequent agents, so the Development Agent reads the Design Agent's implementation plan, the Testing Agent reads the acceptance criteria, and the Docs Agent reads outputs from all prior phases.

---

## Components

### Orchestrator (LangGraph)

**File:** `agents/graph.py`

The orchestrator defines the workflow as a LangGraph `StateGraph`. It initializes a shared `AgentState` TypedDict, assigns a unique session ID, and invokes each agent node in order: design, develop, testing, docs.

Each node updates a subset of the shared state and sets `current_phase` to signal completion. The `should_continue()` router function reads `current_phase` to determine the next node. If any node sets `current_phase = "error"`, the workflow terminates early and the error is captured in the final state.

The orchestrator also emits heartbeats at the start and end of each phase, which the dashboard backend stores and displays.

**Input:** Issue title, description, optional repository path
**Output:** Final `AgentState` containing all agent outputs

---

### Design Agent

**File:** `agents/design_agent.py`

The Design Agent is the entry point for every workflow. It receives the issue title and description, optionally examines the Shipwright repository for API types and controller files, and generates a structured design document using Claude API.

The agent identifies which Shipwright components are affected (Build, BuildRun, BuildStrategy, webhooks, controllers), assesses risks such as backward compatibility concerns, defines acceptance criteria, and produces an ordered implementation plan.

**Input:** Issue title, description, optional repository path
**Output:**
- `design_analysis` - Full design document in Markdown
- `impacted_components` - List of affected Shipwright components
- `risks` - Identified risks and compatibility concerns
- `acceptance_criteria` - Testable success criteria
- `implementation_plan` - Ordered implementation steps

---

### Development Agent (Go/K8s)

**File:** `agents/go_k8s_developer.py`

The Development Agent reads the design analysis and implementation plan produced by the Design Agent and generates production-quality Go code for Kubernetes and OpenShift. It follows strict security and quality standards: TLS 1.3 enforcement, no hardcoded secrets, structured logging without sensitive data, context propagation through the call chain, and table-driven unit tests.

The agent outputs code organized into named files with paths matching the Shipwright repository layout, along with a PR description that includes a security considerations section.

**Input:** Design analysis, implementation plan, impacted components, acceptance criteria
**Output:**
- `code_files` - List of Go source files (path, content, description)
- `test_files` - Table-driven unit test files
- `code_changes` - Map of file paths to change descriptions
- `pr_description` - PR body with summary, security notes, and next steps
- `security_notes` - Security considerations applied

---

### Testing Agent

**File:** `agents/testing_agent.py`

The Testing Agent generates a comprehensive Ginkgo v2 test suite by analyzing the design document and acceptance criteria. Before calling Claude API, it scans the issue description and design for Shipwright-specific patterns: build strategies (kaniko, buildkit, buildpacks, buildah, s2i), source types (git, bundle, registry), output types (image, ImageStream), and security contexts (privileged, nonroot, restricted). These detected patterns guide the test scenarios that are generated.

The agent produces three levels of tests. Unit tests are mock-based and run in milliseconds. Integration tests target a real Kubernetes cluster and exercise controller reconciliation and webhook validation. E2E tests execute full build workflows using actual build execution and registry pushes.

Every generated test is mapped back to a specific acceptance criterion, and the agent reports which criteria are covered and whether any gaps exist.

**Input:** Design analysis, impacted components, acceptance criteria, implementation plan
**Output:**
- `test_plan` - Human-readable test strategy document
- `test_specifications` - Structured YAML test specs with scenario IDs
- `unit_tests` - Ginkgo v2 unit test files (file path to code)
- `integration_tests` - Integration test files
- `e2e_tests` - End-to-end test files
- `coverage_analysis` - Mapping of tests to acceptance criteria

---

### Documentation Agent

**File:** `agents/docs_agent.py`

The Documentation Agent runs last and has access to outputs from all prior phases. It generates user-facing and contributor-facing documentation, combining design analysis, code changes, and test results into coherent artifacts.

When a repository path is available, it activates RAG (Retrieval-Augmented Generation) to search existing Shipwright documentation, extract code examples from modified files, and find similar API usage patterns. This ensures generated documentation matches the style and conventions already in the project.

The agent supports multiple output formats: standard documentation, SHIP format (Solution, Highlight, Impact, Plan) for stakeholder communication, JTBD (Jobs-to-be-Done) documentation, or all formats combined.

**Input:** All prior agent outputs (design, code changes, test results), optional repository path and input files
**Output:**
- `pr_summary` - PR description with summary and testing notes
- `release_notes` - User-facing changelog entry
- `docs_changes` - Map of documentation files to recommended changes
- `upgrade_notes` - Backward compatibility and migration guidance
- `high_level_design` - Architecture and implementation design document
- `ship_document` - SHIP format (if requested)

---

### Dashboard

**Files:** `dashboard/backend.py`, `dashboard/frontend/index.html`

The dashboard provides real-time visibility into running and completed agent sessions. It runs as a separate FastAPI server that agents communicate with via HTTP heartbeats.

Each heartbeat carries the full agent state at that moment. The enricher pipeline extracts key metrics from the raw state: which Claude model is active, estimated context token usage and percentage of the context window consumed, and the current workflow phase. Enriched data is stored in a SQLite database and served to the browser frontend.

The frontend polls for session updates every few seconds and displays session cards showing issue title, agent phase badges (Design, Development, Testing, Docs), context usage percentage, impacted components, and timestamps. Completed or errored sessions can be cleared from the view with a single button.

The dashboard is optional. Agents emit heartbeats only when the dashboard is reachable; if it is not running, agents continue normally.

**Technology:** FastAPI, SQLite, vanilla JavaScript, CSS

---

## Quick Links


