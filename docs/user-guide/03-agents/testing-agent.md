# Testing Agent

The Testing Agent generates comprehensive Ginkgo v2 test suites including unit, integration, and E2E tests. It detects Shipwright-specific patterns in the issue and design to produce targeted, context-aware tests.

**File:** `stages/test.py`
**Entry point:** `run_testing(context)`

---

## System Prompt

The Testing Agent is driven by `TESTING_AGENT_PROMPT` defined in [`prompts/test.py`](../../../prompts/test.py).

The prompt instructs the agent to:

- Detect Shipwright patterns (build strategies: kaniko, buildkit, buildpacks, buildah, s2i; source types: git, bundle, registry; output types: image, imagestream)
- Generate Ginkgo v2 test suites with Data-Driven Testing (DDT) using `DescribeTable` and `Entry`
- Use Gomega assertions and Shipwright test helpers (`libfactory`, `libk8s`)
- Tag each test with a unique `[test_id:BUILD-NNN]` identifier
- Produce unit, integration, and e2e test files as separate Go source files

To customize Testing Agent behavior, edit `TESTING_AGENT_PROMPT` in `prompts/test.py`.

---

## Inputs

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `design_analysis` | str | Yes | Design document from Design Agent |
| `impacted_components` | list[str] | Yes | Affected components |
| `acceptance_criteria` | list[str] | Yes | Testable criteria |
| `issue_title` | str | No | Feature or bug title |
| `issue_description` | str | No | Detailed description |
| `implementation_plan` | list[str] | No | Implementation steps |
| `risks` | list[str] | No | Risks to test against |

---

## Outputs

```python
{
    "test_plan": str,                    # Human-readable test strategy document
    "test_specifications": dict,         # YAML specs with scenario IDs (BUILD-XXX-NNN)
    "unit_tests": dict[str, str],        # file path → Ginkgo v2 test code
    "integration_tests": dict[str, str], # file path → Ginkgo v2 test code
    "e2e_tests": dict[str, str],         # file path → Ginkgo v2 test code
    "test_summary": str,                 # Count and summary of generated tests
    "coverage_analysis": str,            # Coverage mapping to acceptance criteria
    "patterns_detected": dict,           # Detected Shipwright-specific patterns
}
```

---

## Claude API Settings

| Setting | Value |
|---------|-------|
| Model | `claude-sonnet-4-6` |
| Max tokens | 16,000 (larger for test code generation) |

---

## Test Types

| Type | Duration | Scope | Focus |
|------|----------|-------|-------|
| Unit | Fast (<5s) | Isolated functions with mocks | Logic correctness, error handling, edge cases |
| Integration | Medium (~30s) | Real Kubernetes cluster | Controller reconciliation, webhook validation |
| E2E | Slow (~5m) | Full workflow | Complete build execution with actual images |

---

## Pattern Detection

Before generating tests, the agent scans the issue description and design for Shipwright-specific patterns:

**Build strategies:** kaniko, buildkit, buildpacks, buildah, s2i

**Source types:** git (clone from repository), bundle (OCI bundle image), registry (container registry)

**Output types:** image (container registry push), imagestream (OpenShift ImageStream)

**Security contexts:** privileged, nonroot, restricted (OpenShift SCC)

```python
# Example detected patterns
patterns_detected = {
    "strategies": ["kaniko"],
    "source_types": ["git"],
    "output_types": ["image"],
    "security_contexts": []
}
```

The detected patterns determine which strategy-specific test scenarios are generated.

---

## Test ID Format

All test scenarios follow the format `BUILD-XXX-NNN`:

- `XXX` - Feature area (e.g., `TIMEOUT`, `CACHE`, `SSH`)
- `NNN` - Sequential number within the area

Example: `BUILD-TIMEOUT-001`, `BUILD-TIMEOUT-101`, `BUILD-TIMEOUT-201`

---

## Generated Test Features

All generated tests use:

- **Ginkgo v2** syntax (not v1) with modern imports
- **Gomega** assertions
- **DescribeTable** for data-driven parameterized tests
- **Shipwright helpers**: `libfactory` and `libk8s` test utilities
- **BeforeEach/AfterEach** for setup and cleanup
- **Eventually/Consistently** for async assertions with timeouts

---

## Unit Test Example

```go
package v1_test

import (
    . "github.com/onsi/ginkgo/v2"
    . "github.com/onsi/gomega"

    shipwright "github.com/shipwright-io/build/pkg/apis/build/v1beta1"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

var _ = Describe("BuildRun Timeout Validation", func() {
    type TimeoutScenario struct {
        Timeout       string
        ExpectedValid bool
        ExpectedError string
    }

    DescribeTable("timeout field validation",
        func(scenario TimeoutScenario) {
            buildRun := &shipwright.BuildRun{
                Spec: shipwright.BuildRunSpec{
                    Timeout: &metav1.Duration{Duration: parseDuration(scenario.Timeout)},
                },
            }

            err := ValidateBuildRun(buildRun)

            if scenario.ExpectedValid {
                Expect(err).ToNot(HaveOccurred())
            } else {
                Expect(err).To(HaveOccurred())
                Expect(err.Error()).To(ContainSubstring(scenario.ExpectedError))
            }
        },
        Entry("[BUILD-TIMEOUT-001] valid 10 minute timeout", TimeoutScenario{
            Timeout: "10m", ExpectedValid: true,
        }),
        Entry("[BUILD-TIMEOUT-002] invalid timeout format", TimeoutScenario{
            Timeout: "invalid", ExpectedValid: false, ExpectedError: "invalid duration",
        }),
    )
})
```

---

## Integration Test Example

```go
var _ = Describe("BuildRun Timeout Controller Integration", func() {
    var (
        ctx       context.Context
        namespace string
    )

    BeforeEach(func() {
        ctx = context.Background()
        namespace = "test-timeout-" + randomString(5)
        Expect(libk8s.CreateNamespace(ctx, k8sClient, namespace)).To(Succeed())
    })

    AfterEach(func() {
        Expect(libk8s.DeleteNamespace(ctx, k8sClient, namespace)).To(Succeed())
    })

    It("[BUILD-TIMEOUT-101] should terminate build after timeout exceeded", func() {
        build := libfactory.NewBuild(namespace, "timeout-build").
            WithSource("https://github.com/example/repo").
            WithStrategy("kaniko").
            Create()

        buildRun := libfactory.NewBuildRun(namespace, "timeout-buildrun").
            WithBuild(build.Name).
            WithTimeout("1m").
            Create()

        // Wait for timeout to trigger
        Eventually(func() string {
            br, _ := libk8s.GetBuildRun(ctx, k8sClient, namespace, buildRun.Name)
            condition := br.Status.GetCondition(shipwright.Succeeded)
            if condition != nil {
                return condition.Reason
            }
            return ""
        }, 2*time.Minute, 5*time.Second).Should(Equal("Timeout"))
    })
})
```

---

## Direct Invocation

```python
from pathlib import Path
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

# Artifacts written to /tmp/claude/testing-artifacts/ (default)
result = run_testing(context)

# Artifacts written to a custom directory
result = run_testing(context, output_dir=Path("/tmp/my-feature/testing"))

print("Test Plan:", result["test_plan"])
print("Patterns detected:", result["patterns_detected"])
print("Unit test files:", list(result["unit_tests"].keys()))
print("Integration test files:", list(result["integration_tests"].keys()))
print("E2E test files:", list(result["e2e_tests"].keys()))
print("\nCoverage analysis:")
print(result["coverage_analysis"])
```

> **Note:** `run_testing()` always writes `test_plan.md` and `go_tests/` artifacts to `output_dir`. When called via `scripts/orchestrate.py`, artifacts land in `/tmp/claude/testing-artifacts/` by default. Pass `output_dir` explicitly to control the destination.

---

## Coverage Analysis Output

The `coverage_analysis` field maps each acceptance criterion to the test IDs that cover it:

```
AC-1: BuildRun API accepts timeout field
  - BUILD-TIMEOUT-001 (unit test)
  - BUILD-TIMEOUT-002 (unit test)

AC-2: Controller respects timeout value
  - BUILD-TIMEOUT-101 (integration test)

AC-3: Build fails after timeout exceeded
  - BUILD-TIMEOUT-201 (E2E test)

Coverage: 100% (3/3 criteria covered)
```

---

## Test File Organization

Generated test files follow Shipwright repository conventions:

```
shipwright-build/
├── pkg/apis/build/v1/
│   └── buildrun_types_test.go        # Unit tests for API types
├── pkg/controller/buildrun/
│   └── buildrun_controller_test.go   # Unit tests for controller logic
├── test/integration/
│   └── buildrun_timeout_test.go      # Integration tests
└── test/e2e/
    └── timeout_builds_test.go        # E2E tests
```

---

## Output Artifacts

The testing agent always writes three artifacts when `run_testing()` is called. The output directory is:

- **`/tmp/claude/agent-tests/`** — when called via `scripts/test_agents.py` (the default `--output-dir`)
- **`/tmp/claude/testing-artifacts/`** — when called directly or via `scripts/orchestrate.py` (built-in default)
- **Custom path** — when `output_dir` is passed explicitly to `run_testing()`

| Artifact | Description |
|----------|-------------|
| `testing_output.json` | Full structured output from the agent as a JSON file |
| `test_plan.md` | Human-readable test plan with strategy, scenario counts, and coverage analysis |
| `go_tests/<full_path>` | Individual Go test files under a `go_tests/` subdirectory, preserving the full relative path (e.g. `go_tests/pkg/reconciler/buildrun/resources/step_test.go`) |

### test_plan.md structure

```markdown
# Test Plan: <issue title>

## Test Strategy
<agent's test_plan text>

## Test Coverage by Level

### Unit Tests (N scenarios)
- **BUILD-XXX-001**: <description>
  - File: `<path>`
  - Expected: <expected_outcome>

### Integration Tests (N scenarios)
...

### E2E Tests (N scenarios)
...

## Generated Test Files
- `go_tests/pkg/webhook/validation/buildrun_timeout_test.go`
- `go_tests/test/integration/buildrun_timeout_test.go`
- `go_tests/test/e2e/buildrun_timeout_test.go`

## Coverage Analysis
<agent's coverage_analysis text>

## Detected Patterns
- Strategies: ['kaniko']
- Source types: ['git']
- Output types: ['image']
```

### go_tests/ directory

Go test files are written with their full relative path preserved so they can be copied directly into a Shipwright repository checkout:

```
output_dir/
└── go_tests/
    ├── pkg/
    │   └── webhook/
    │       └── validation/
    │           └── buildrun_timeout_test.go
    └── test/
        ├── integration/
        │   └── buildrun_timeout_test.go
        └── e2e/
            └── buildrun_timeout_test.go
```

---

## Best Practices for Better Output

**Provide specific acceptance criteria:**

```python
# Good - testable and specific
"acceptance_criteria": [
    "BuildRun API accepts timeout field as metav1.Duration",
    "Controller terminates build after timeout exceeded",
    "Build status shows timeout failure reason with 'Timeout' reason code",
]

# Avoid - too vague to generate meaningful tests
"acceptance_criteria": [
    "Add timeout",
    "Make it work",
]
```

**Include risks to drive edge case tests:**

```python
"risks": [
    "Race condition during timeout enforcement",
    "Resource leak if cleanup fails after timeout",
    "Grace period handling when controller restarts",
]
```

---

[← Previous: Development Agent](development-agent.md) | [Next: Docs Agent →](docs-agent.md)
