# Output Validation & Manual Approval

Each agent phase now validates its outputs before the next phase begins, preventing silent cascading failures where empty or incomplete data flows through the entire pipeline undetected.

---

## The Silent Failure Problem

Without validation, a failure in one phase silently degrades every downstream phase. Consider this failure chain:

1. Design Agent returns an empty `design_analysis` string due to a parsing error
2. Development Agent receives empty context and generates generic, low-quality code
3. Testing Agent writes tests against code that does not reflect the actual feature
4. Docs Agent produces a PR summary with no substance

The entire pipeline completes with exit code 0. Nothing indicates that anything went wrong.

**How we solve it:** after each phase completes, a validator checks that all required output fields are non-empty and meet minimum quality thresholds. If validation fails, the workflow stops immediately with a descriptive error message pointing to the failing field and phase.

---

## Validation Rules

Validation is split into two categories:

- **Blocking** - required fields that must be present and non-empty. A failure here stops the workflow.
- **Warnings** - fields that are expected but not strictly required. The workflow continues, but a warning is printed to stdout.

| Phase | Required Fields (blocking) | Optional Fields (warnings) |
|-------|---------------------------|---------------------------|
| Design | `design_analysis` (minimum 50 characters), `implementation_plan` (non-empty list) | Missing `impacted_components`, `risks`, or `acceptance_criteria` |
| Development | `code_files` (non-empty list) | Empty `pr_description` |
| Testing | `test_plan` (non-empty string) | Missing `unit_tests` or `integration_tests` |
| Documentation | `pr_summary` (non-empty string) | Empty `release_notes` |

---

## The Validators Module (`stages/validators.py`)

The validation logic lives entirely in `stages/validators.py`. Understanding this module is useful when you need to add a new agent phase or tighten quality thresholds.

### `ValidationResult` dataclass

Every validator returns a `ValidationResult`:

```python
@dataclass
class ValidationResult:
    phase: str           # Which phase was validated (design, develop, testing, docs)
    passed: bool         # True if no blocking issues found
    issues: list[str]    # Blocking failures that stop the workflow
    warnings: list[str]  # Non-blocking issues printed as warnings
    summary: dict        # Key metrics from the phase output (e.g. "Code files generated: 3")
```

`passed` is `True` only when `issues` is empty. Warnings do not affect `passed`.

### Per-phase validator functions

| Function | Blocking checks | Warning checks |
| -------- | --------------- | -------------- |
| `validate_design_output(state)` | `design_analysis` >= 50 chars, `implementation_plan` non-empty list | Missing `impacted_components`, `risks`, `acceptance_criteria` |
| `validate_develop_output(state)` | `code_files` non-empty list | `pr_description` < 20 chars |
| `validate_testing_output(state)` | `test_plan` non-empty string | No `unit_tests` or `integration_tests` |
| `validate_docs_output(state)` | `pr_summary` non-empty string | Empty `release_notes` |

Each function accepts the full LangGraph `state` dict and reads only the fields it needs.

### `validate_phase(phase, state)` — the unified entry point

The orchestrator always calls `validate_phase()` rather than individual validator functions directly:

```python
from stages.validators import validate_phase

result = validate_phase("design", state)
if not result.passed:
    print(result.issues)   # Blocking failures
print(result.warnings)     # Non-blocking issues
print(result.summary)      # Metrics for the phase summary block
```

If no validator is registered for the given phase name, `validate_phase()` returns a passing result with a `"No validator for this phase"` note in `summary`, so unregistered phases never block the workflow unexpectedly.

### `VALIDATORS` registry

```python
VALIDATORS = {
    "design":   validate_design_output,
    "develop":  validate_develop_output,
    "testing":  validate_testing_output,
    "docs":     validate_docs_output,
}
```

`validate_phase()` looks up the phase name in this dict at runtime. Adding a new agent means adding one entry here — the orchestrator picks it up automatically with no other changes required.

### Configuration (validation thresholds)

Minimum character thresholds are defined as inline constants inside `stages/validators.py`:

| Field | Threshold | Location in source |
| ----- | --------- | ------------------ |
| `design_analysis` | 50 chars | `validate_design_output` |
| `pr_description` | 20 chars | `validate_develop_output` |
| `test_plan` | 20 chars | `validate_testing_output` |
| `pr_summary` | 20 chars | `validate_docs_output` |

To tighten or relax a threshold, edit the integer literal directly in the corresponding function in `stages/validators.py`.

### How to extend

When adding a new agent phase:

1. Add a `validate_<phase>_output(state)` function in `stages/validators.py` that returns a `ValidationResult`.
2. Register it in the `VALIDATORS` dict using the phase name string as the key.
3. The orchestrator calls `validate_phase("<phase>", state)` automatically — no other changes needed.

---

## Phase Summary Output

After each phase, a summary block is printed to stdout regardless of whether manual approval is enabled. This gives you visibility into what each agent produced without having to inspect raw state.

```
----------------------------------------------------------
  Phase: DESIGN  |  Validation: PASSED
----------------------------------------------------------
  Analysis length: 1243 chars
  Implementation plan steps: 5
  Impacted components: 3
  Risks identified: 2
  Acceptance criteria: 4
```

If a warning was triggered, it appears in the summary:

```
----------------------------------------------------------
  Phase: TESTING  |  Validation: PASSED (with warnings)
----------------------------------------------------------
  Test plan length: 892 chars
  WARNING: No unit_tests field found in output
```

If validation fails, the summary shows what blocked the workflow:

```
----------------------------------------------------------
  Phase: DESIGN  |  Validation: FAILED
----------------------------------------------------------
  BLOCKING: design_analysis is empty (minimum 50 characters required)

  Workflow stopped. Fix the Design Agent output before continuing.
```

---

## Manual Approval Mode

Manual approval mode pauses the workflow after each successful phase and asks whether to continue. This is useful when you want to review what one agent produced before spending API tokens on the next.

### Enabling Manual Approval

Set `MANUAL_APPROVAL=true` in your `.env` file:

```bash
# .env
MANUAL_APPROVAL=true
```

Or pass it inline for a single run:

```bash
MANUAL_APPROVAL=true uv run python scripts/orchestrate.py \
  --title "Add SSH key support for private Git repos" \
  --description "Users need to build from private Git repos using SSH authentication" \
  --output-dir ./output
```

### What It Looks Like

After each phase passes validation, you see the summary followed by an approval prompt:

```
============================================================
  Phase 1: Design Agent
============================================================
...
----------------------------------------------------------
  Phase: DESIGN  |  Validation: PASSED
----------------------------------------------------------
  Analysis length: 1243 chars
  Implementation plan steps: 5
  Impacted components: 3
  Risks identified: 2
  Acceptance criteria: 4

  Next phase: DEVELOPMENT

  Continue to development? [Y/n]:
```

Press Enter or type `y` to continue. Type `n` to stop the workflow.

### Stopping the Workflow

If you type `n` at an approval prompt, the workflow stops cleanly:

- Prints a summary of all phases that completed successfully
- Exits with a non-zero exit code (so scripts and CI pipelines can detect the early exit)
- Does not make any further API calls

This is particularly useful for cost control: approve the Design phase output, decide the direction is wrong, and stop before the Development Agent incurs further API usage.

### When to Use Manual Approval

| Scenario | Benefit |
|----------|---------|
| Reviewing design before code generation | Catch wrong direction early, save API costs |
| Production quality-gate | A human verifies each phase before committing to the next |
| Step-by-step pipeline debugging | Inspect intermediate state at each boundary |
| Onboarding and learning | Understand what each agent produces before moving on |

---

## Auto Mode (Default)

When `MANUAL_APPROVAL=false` (the default), the workflow runs fully automated:

- Validation still runs after every phase
- The workflow still stops immediately if a blocking validation check fails
- Phase summaries are still printed to stdout
- No user prompts are shown

This is the right mode for CI/CD pipelines and unattended runs where you want automatic failure on bad output but no human in the loop.

```bash
# Auto mode (default - no changes needed)
uv run python scripts/orchestrate.py \
  --title "Add SSH key support for private Git repos" \
  --description "Users need to build from private Git repos using SSH authentication" \
  --output-dir ./output
```

---

[← Logging](logging.md) | [Troubleshooting →](troubleshooting.md)
