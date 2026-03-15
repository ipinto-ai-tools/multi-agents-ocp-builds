# Design Agent

The Design Agent analyzes a GitHub issue and produces a comprehensive design document for the Shipwright Build project. It identifies impacted components, assesses risks, and creates a step-by-step implementation plan.

**File:** `agents/design_agent.py`
**Entry point:** `run_design(title, description, repo_path)`

---

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | str | Yes | GitHub issue title |
| `description` | str | Yes | GitHub issue description |
| `repo_path` | str | No | Path to the Shipwright Build repository |

When `repo_path` is provided, the agent searches the repository for API types (`*_types.go`), controllers, CRDs, and package structure before constructing the design prompt. This produces more accurate component impact analysis.

---

## Outputs

```python
{
    "design_analysis": str,           # Full design document in Markdown
    "impacted_components": list[str], # Shipwright component names affected
    "risks": list[str],               # Identified risks
    "acceptance_criteria": list[str], # Testable acceptance criteria
    "implementation_plan": list[str]  # Step-by-step implementation
}
```

### Design Document Sections

The `design_analysis` field is a structured Markdown document containing:

1. Problem Statement
2. Scope (what is in and out of scope)
3. Impacted Components
4. Risks and Mitigation
5. Acceptance Criteria
6. Implementation Plan
7. Required Tests
8. Documentation Changes

---

## Claude API Settings

| Setting | Value |
|---------|-------|
| Model | `claude-sonnet-4-20250514` |
| Max tokens | 8,000 |
| Temperature | 1.0 (default) |

---

## Direct Invocation

The Design Agent is normally invoked by the orchestrator. For standalone use:

```python
# design_only.py
from agents.design_agent import run_design
import os

result = run_design(
    title="Add retry logic to failed builds",
    description="BuildRuns should support automatic retry on transient failures",
    repo_path=os.getenv("SHIPWRIGHT_REPO_PATH")  # optional
)

print(result["design_analysis"])
print("Impacted components:", result["impacted_components"])
print("Risks:", result["risks"])
print("Acceptance criteria:", result["acceptance_criteria"])
```

Run with:

```bash
uv run python design_only.py
```

---

## Repository Analysis

When a Shipwright repository path is set, the agent performs these searches before calling the Claude API:

- **API types** (`pkg/apis/**/*_types.go`) - Finds struct definitions and field names
- **Controllers** (`pkg/controller/**/*.go`) - Finds reconciliation logic
- **CRDs** (YAML files) - Finds Custom Resource Definitions
- **Package structure** - Analyzes Go module and package dependencies

If repository analysis fails (path not found, permission error, etc.), the agent falls back to component metadata from `config/shipwright_components.py` only.

---

## Shipwright Component Context

Even without a repository path, the agent loads Shipwright domain knowledge from `config/shipwright_components.py`:

- **Components**: BuildRun, Build, BuildStrategy, webhooks and their dependencies
- **CRD types**: Known CRD names and API versions
- **Build strategies**: Kaniko, Buildpacks, Buildah, BuildKit, S2I
- **OpenShift integrations**: ImageStream, OpenShift Build API compatibility

This context helps Claude produce Shipwright-specific analysis without needing the full source.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Missing authentication | Raises `DesignAgentError: No Claude authentication configured` |
| API call failure | Logs error, raises `DesignAgentError` |
| Repository path not found | Logs warning, continues with component metadata only |
| Repository analysis error | Logs warning, continues with component metadata only |

---

## Example Output

```python
{
    "design_analysis": "# Design: Add timeout support to BuildRun\n\n## Problem Statement\nUsers need...",
    "impacted_components": [
        "buildrun_api",
        "buildrun_controller",
        "buildrun_webhook"
    ],
    "risks": [
        "Backward compatibility with existing BuildRuns that have no timeout set",
        "Race conditions during timeout enforcement in the controller reconciliation loop"
    ],
    "acceptance_criteria": [
        "BuildRun API accepts a timeout field as metav1.Duration",
        "Controller terminates build after timeout exceeded",
        "Build status shows timeout failure reason"
    ],
    "implementation_plan": [
        "Add Timeout field to BuildRunSpec struct in pkg/apis/build/v1beta1/buildrun_types.go",
        "Update webhook validation to validate timeout format and reject negative values",
        "Implement timeout monitoring in the buildrun reconciliation loop"
    ]
}
```

---

[← Previous: State Management](../02-concepts/state-management.md) | [Next: Development Agent →](development-agent.md)
