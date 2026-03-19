# State Management

The `AgentState` TypedDict is the single shared data structure that flows through the entire workflow. Understanding it explains how agents hand off data to each other.

---

## AgentState

Defined in `graph/state.py`, `AgentState` is a `TypedDict(total=False)`, meaning all fields are optional at initialization. LangGraph merges each node's partial return dictionary into the running state.

```python
# Node returns only the fields it modifies
def design_node(state: AgentState) -> Dict[str, Any]:
    return {
        "design_analysis": "...",
        "current_phase": "design_complete"
    }
# LangGraph performs: state = {**state, **design_node(state)}
```

Because of this merge behavior, the Development Agent can read `design_analysis` directly from state without any explicit handoff.

---

## State Fields by Phase

| Category | Fields | Set by |
| -------- | ------ | ------ |
| **Input** | `issue_title`, `issue_description`, `issue_type` | Orchestrator |
| **Control** | `session_id`, `current_phase`, `approval_status` | Orchestrator |
| **Repository** | `repo_path`, `target_branch` | Orchestrator |
| **Design outputs** | `design_analysis`, `impacted_components`, `risks`, `acceptance_criteria`, `implementation_plan` | Design Agent |
| **Dev outputs** | `code_files`, `test_files`, `code_changes`, `files_modified`, `pr_description` | Development Agent |
| **Code Review outputs** | `review_passed`, `review_findings`, `review_summary`, `review_iteration` | Code Review Agent |
| **Test outputs** | `test_plan`, `test_specifications`, `unit_tests`, `integration_tests`, `e2e_tests`, `coverage_analysis` | Testing Agent |
| **Test results** | `test_results`, `test_summary`, `coverage_gaps`, `test_failures` | Testing Agent |
| **Docs outputs** | `pr_summary`, `release_notes`, `docs_changes`, `upgrade_notes`, `known_limitations`, `jtbd_documentation`, `ship_document`, `high_level_design` | Docs Agent |
| **Messages** | `messages` (LangGraph message list with `add_messages` annotation) | All agents |

---

## Phase Transitions

The `current_phase` field controls the conditional router in the graph. The router reads this field after each node completes and decides which node to invoke next.

```text
init
  │
  ▼ (design_node runs)
design_complete
  │
  ▼ (develop_node runs)
develop_complete
  │
  ▼ (code_review_node runs)
review_complete ──── review_passed=False + iteration ≤ max ───→ develop_complete (loop)
  │
  ▼ (review_passed=True OR iteration > max)
  ▼ (testing_node runs)
testing_complete
  │
  ▼ (docs_node runs)
done
```

Any unhandled exception in a node sets `current_phase = "error"` and routes the graph to `END`. The error message is available in the final state for diagnosis.

---

## How State Flows Through the Workflow

```text
orchestrate() creates initial state with:
  - issue_title, issue_description, issue_type
  - session_id (UUID)
  - current_phase = "init"
  - repo_path (if provided)
    │
    ▼
Design node adds:
    design_analysis       → str (full Markdown document)
    impacted_components   → list[str]
    risks                 → list[str]
    acceptance_criteria   → list[str]
    implementation_plan   → list[str]
    current_phase = "design_complete"
    │
    ▼
Development node reads design fields, adds:
    code_files            → list[dict] (path, content, description)
    test_files            → list[dict] (path, content)
    code_changes          → dict[str, str] (file path → change description)
    files_modified        → list[str]
    pr_description        → str
    security_notes        → list[str]
    dependencies          → list[str]
    current_phase = "develop_complete"
    │
    ▼
Code Review node reads code_files + design fields, adds:
    review_passed         → bool (True if no blocking issues)
    review_findings       → list[str] ("[BLOCKING] SECURITY: ...", ...)
    review_summary        → str ("2 findings | 1 blocking | FAIL")
    review_iteration      → int (increments each cycle; starts at 0)
    current_phase = "review_complete"

    If review_passed=False AND review_iteration ≤ MAX_REVIEW_ITERATIONS:
        → Graph loops back to Development node (inject findings into prompt)
    Else:
        → Continues to Testing node
    │
    ▼
Testing node reads design + dev fields, adds:
    test_plan             → str
    test_specifications   → dict (YAML specs with scenario IDs)
    unit_tests            → dict[str, str] (file path → Ginkgo code)
    integration_tests     → dict[str, str]
    e2e_tests             → dict[str, str]
    test_summary          → str
    coverage_analysis     → str
    patterns_detected     → dict
    current_phase = "testing_complete"
    │
    ▼
Docs node reads everything, adds:
    pr_summary            → str
    release_notes         → str
    docs_changes          → dict[str, str]
    upgrade_notes         → str
    known_limitations     → str
    jtbd_documentation    → str
    ship_document         → str
    high_level_design     → str
    current_phase = "done"
    │
    ▼
Final state returned to caller (contains all fields from all phases)
```

---

## Accessing State After a Run

The `orchestrate()` function returns the complete final state:

```python
from agents.graph import orchestrate

state = orchestrate(
    title="Add timeout support to BuildRun",
    description="Users need to specify build timeout to prevent hanging builds"
)

# Access any field from any phase
print(state["design_analysis"])
print(state["impacted_components"])
print(state["unit_tests"])
print(state["pr_summary"])
print(state["current_phase"])  # "done" on success, "error" on failure
```

---

[← Previous: Agents Overview](agents-overview.md) | [Next: Design Agent →](../03-agents/design-agent.md)
