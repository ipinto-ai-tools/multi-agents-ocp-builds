# Testing Agent Documentation

## Overview

The Testing Agent is an intelligent test generation component that creates comprehensive Ginkgo v2 test suites for Shipwright Build features. It analyzes design documents and acceptance criteria to generate unit tests, integration tests, and end-to-end tests with Data-Driven Testing (DDT) patterns.

**Key Capabilities:**

- Generates working Ginkgo v2 test code that compiles
- Detects Shipwright-specific patterns (strategies, sources, outputs)
- Creates test plans and structured test specifications
- Produces multi-level tests (unit, integration, E2E)
- Uses Data-Driven Testing with DescribeTable
- Includes Shipwright test helpers (libfactory, libk8s)

## Architecture

### Integration with Workflow

The Testing Agent fits into the multi-agent workflow between Design and Docs agents:

```
Design Agent → Testing Agent → Docs Agent
     ↓              ↓              ↓
  Analysis     Test Code      Documentation
```

**Input from Design Agent:**

- Design analysis document
- Impacted components
- Acceptance criteria
- Implementation plan
- Risk assessment

**Output to Docs Agent:**

- Test plans and specifications
- Generated test code files
- Coverage analysis
- Test summary statistics

### How It Works

```
┌─────────────────────────────────────────┐
│  1. Pattern Detection                   │
│     - Analyze issue description         │
│     - Detect build strategies           │
│     - Identify source/output types      │
│     - Find security contexts            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  2. Test Planning                       │
│     - Map acceptance criteria           │
│     - Organize by test type             │
│     - Identify risk areas               │
│     - Create test strategy              │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  3. Test Code Generation (Claude API)  │
│     - Model: claude-sonnet-4            │
│     - Framework: Ginkgo v2              │
│     - Max tokens: 16000                 │
│     - Generates compilable Go code      │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  4. Output Parsing                      │
│     - Extract test plans                │
│     - Parse test specifications         │
│     - Organize test code by file        │
│     - Generate coverage analysis        │
└─────────────────────────────────────────┘
```

## Pattern Detection System

The Testing Agent automatically detects Shipwright-specific patterns to generate targeted tests.

### Build Strategies

**Detected Strategies:**

- **kaniko**: Registry-based builds with Dockerfile
- **buildkit**: Multi-stage builds with cache optimization
- **buildpacks**: Cloud Native Buildpacks with auto-detection
- **buildah**: Rootless OCI builds
- **s2i**: Source-to-Image (legacy)

**Example Pattern Detection:**

```python
# Issue description: "Add kaniko build support with registry push"
patterns_detected = {
    "strategies": ["kaniko"],
    "source_types": ["git"],
    "output_types": ["image"]
}
```

**Generated Tests:**

- Strategy-specific configuration tests
- Build execution with strategy
- Registry integration tests
- Error handling for strategy failures

### Source Types

**Detected Source Types:**

- **git**: Clone from repository (branch, tag, commit)
- **bundle**: OCI bundle image
- **registry**: Container registry image

**Common Test Scenarios:**

- Source retrieval and validation
- Authentication and credentials
- Context directory handling
- Submodule support (git)

### Output Types

**Detected Output Types:**

- **image**: Container registry push
- **imagestream**: OpenShift ImageStream

**Common Test Scenarios:**

- Output destination validation
- Push credentials handling
- Tag management
- Label application

### Security Contexts

**Detected Contexts:**

- **privileged**: Elevated permissions
- **nonroot**: Rootless execution
- **restricted**: OpenShift SCC compliance

**Test Focus:**

- Security validation
- Permission boundary testing
- SCC compliance verification

## Test Generation Pipeline

### 1. Test Planning

**Output: Human-Readable Test Strategy**

The test plan is a document that explains:

- **Test Approach**: Overall strategy and methodology
- **Coverage Mapping**: Which tests cover which acceptance criteria
- **Test Organization**: How tests are structured and grouped
- **Risk Areas**: Scenarios requiring extra attention

**Example Test Plan Structure:**

```markdown
# Test Plan: BuildRun Timeout Support

## Test Approach
Validate timeout functionality across all test levels:
- Unit: API validation and field parsing
- Integration: Controller timeout enforcement
- E2E: Full build lifecycle with timeout

## Coverage Mapping
AC-1: BuildRun accepts timeout field → Unit tests (BUILD-TIMEOUT-001, 002)
AC-2: Controller respects timeout → Integration tests (BUILD-TIMEOUT-101, 102)
AC-3: Build fails after timeout → E2E tests (BUILD-TIMEOUT-201)

## Test Organization
- pkg/apis/build/v1/buildrun_types_test.go (unit)
- test/integration/buildrun_timeout_test.go (integration)
- test/e2e/timeout_builds_test.go (E2E)

## Risk Areas
- Race conditions during timeout enforcement
- Grace period handling
- Resource cleanup after timeout
```

### 2. Test Specifications

**Output: YAML Test Specifications**

Structured test metadata for tracking and automation.

**Example Specification:**

```yaml
test_scenarios:
  - id: BUILD-TIMEOUT-001
    type: unit
    description: Validate timeout field accepts valid duration formats
    component: buildrun_api
    pattern: validation
    data_driven: true
    test_data:
      - input: "10m"
        expected: valid
      - input: "1h"
        expected: valid
      - input: "invalid"
        expected: error
    helpers:
      - ValidateBuildRunTimeout

  - id: BUILD-TIMEOUT-101
    type: integration
    description: Controller terminates build after timeout exceeded
    component: buildrun_controller
    pattern: controller_behavior
    data_driven: false
    prerequisites:
      - Real Kubernetes cluster
      - BuildRun controller running
    helpers:
      - libfactory.NewBuildRun
      - libk8s.WaitForBuildRunCompletion
    expected_behavior: BuildRun status shows timeout failure
```

### 3. Test Code Generation

**Output: Working Ginkgo v2 Test Code**

The agent generates compilable Go test files using:

- **Ginkgo v2** syntax (not v1)
- **Gomega** assertions
- **Shipwright test helpers** (libfactory, libk8s)
- **Data-Driven Testing** patterns
- **Proper imports** and package structure

## Test Types

### Unit Tests

**Scope:** Isolated function testing with mocks

**Duration:** Fast (<5 seconds)

**Focus Areas:**

- Function logic correctness
- Input validation
- Error handling
- Edge cases and boundary conditions

**Characteristics:**

- No external dependencies (mocked)
- Deterministic and repeatable
- Fast execution
- High test coverage

**Example Unit Test:**

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
        Timeout         string
        ExpectedValid   bool
        ExpectedError   string
    }

    DescribeTable("timeout field validation",
        func(scenario TimeoutScenario) {
            buildRun := &shipwright.BuildRun{
                ObjectMeta: metav1.ObjectMeta{
                    Name:      "test-buildrun",
                    Namespace: "default",
                },
                Spec: shipwright.BuildRunSpec{
                    Timeout: &metav1.Duration{
                        Duration: parseDuration(scenario.Timeout),
                    },
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
            Timeout:       "10m",
            ExpectedValid: true,
        }),
        Entry("[BUILD-TIMEOUT-002] valid 1 hour timeout", TimeoutScenario{
            Timeout:       "1h",
            ExpectedValid: true,
        }),
        Entry("[BUILD-TIMEOUT-003] invalid timeout format", TimeoutScenario{
            Timeout:       "invalid",
            ExpectedValid: false,
            ExpectedError: "invalid duration",
        }),
        Entry("[BUILD-TIMEOUT-004] negative timeout", TimeoutScenario{
            Timeout:       "-10m",
            ExpectedValid: false,
            ExpectedError: "timeout must be positive",
        }),
    )
})
```

### Integration Tests

**Scope:** Real Kubernetes cluster interactions

**Duration:** Medium (~30 seconds)

**Focus Areas:**

- Controller reconciliation logic
- Webhook validation
- API interactions
- Resource lifecycle management

**Characteristics:**

- Requires running Kubernetes cluster
- Real controller and webhook instances
- Tests actual API behavior
- Validates component integration

**Example Integration Test:**

```go
package integration_test

import (
    "context"
    "time"

    . "github.com/onsi/ginkgo/v2"
    . "github.com/onsi/gomega"

    shipwright "github.com/shipwright-io/build/pkg/apis/build/v1beta1"
    "github.com/shipwright-io/build/test/libfactory"
    "github.com/shipwright-io/build/test/libk8s"

    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

var _ = Describe("BuildRun Timeout Controller Integration", func() {
    var (
        ctx       context.Context
        namespace string
    )

    BeforeEach(func() {
        ctx = context.Background()
        namespace = "test-timeout-" + randomString(5)

        // Create test namespace
        err := libk8s.CreateNamespace(ctx, k8sClient, namespace)
        Expect(err).ToNot(HaveOccurred())
    })

    AfterEach(func() {
        // Cleanup namespace
        err := libk8s.DeleteNamespace(ctx, k8sClient, namespace)
        Expect(err).ToNot(HaveOccurred())
    })

    It("[BUILD-TIMEOUT-101] should terminate build after timeout exceeded", func() {
        // Create Build
        build := libfactory.NewBuild(namespace, "timeout-build").
            WithSource("https://github.com/example/repo").
            WithStrategy("kaniko").
            WithOutput("registry.example.com/image:tag").
            Create()

        Expect(build).ToNot(BeNil())

        // Create BuildRun with 1 minute timeout
        buildRun := libfactory.NewBuildRun(namespace, "timeout-buildrun").
            WithBuild(build.Name).
            WithTimeout("1m").
            Create()

        Expect(buildRun).ToNot(BeNil())

        // Wait for BuildRun to start
        Eventually(func() bool {
            br, err := libk8s.GetBuildRun(ctx, k8sClient, namespace, buildRun.Name)
            if err != nil {
                return false
            }
            return br.Status.StartTime != nil
        }, 30*time.Second, 1*time.Second).Should(BeTrue())

        // Wait for timeout (plus grace period)
        time.Sleep(90 * time.Second)

        // Verify BuildRun failed due to timeout
        br, err := libk8s.GetBuildRun(ctx, k8sClient, namespace, buildRun.Name)
        Expect(err).ToNot(HaveOccurred())

        condition := br.Status.GetCondition(shipwright.Succeeded)
        Expect(condition).ToNot(BeNil())
        Expect(condition.Status).To(Equal(metav1.ConditionFalse))
        Expect(condition.Reason).To(Equal("Timeout"))
    })
})
```

### End-to-End (E2E) Tests

**Scope:** Full workflow from start to finish

**Duration:** Slow (~5 minutes)

**Focus Areas:**

- Complete build workflows
- Strategy-specific scenarios
- Source to image pipelines
- Registry integration

**Characteristics:**

- Full stack testing
- Real build execution
- Actual container images
- Production-like environment

**Example E2E Test:**

```go
package e2e_test

import (
    "context"
    "time"

    . "github.com/onsi/ginkgo/v2"
    . "github.com/onsi/gomega"

    "github.com/shipwright-io/build/test/libfactory"
    "github.com/shipwright-io/build/test/libk8s"
)

var _ = Describe("End-to-End Build with Timeout", func() {
    var (
        ctx       context.Context
        namespace string
    )

    BeforeEach(func() {
        ctx = context.Background()
        namespace = "e2e-timeout-" + randomString(5)

        err := libk8s.CreateNamespace(ctx, k8sClient, namespace)
        Expect(err).ToNot(HaveOccurred())
    })

    AfterEach(func() {
        err := libk8s.DeleteNamespace(ctx, k8sClient, namespace)
        Expect(err).ToNot(HaveOccurred())
    })

    It("[BUILD-TIMEOUT-201] should build successfully within timeout", func() {
        // Create Build with kaniko strategy
        build := libfactory.NewBuild(namespace, "e2e-build").
            WithSource("https://github.com/shipwright-io/sample-nodejs").
            WithStrategy("kaniko").
            WithOutput("registry.example.com/e2e-test:latest").
            Create()

        // Create BuildRun with sufficient timeout
        buildRun := libfactory.NewBuildRun(namespace, "e2e-buildrun").
            WithBuild(build.Name).
            WithTimeout("10m").
            Create()

        // Wait for build completion
        completedBuildRun, err := libk8s.WaitForBuildRunCompletion(
            ctx,
            k8sClient,
            namespace,
            buildRun.Name,
            15*time.Minute, // Wait longer than timeout
        )

        Expect(err).ToNot(HaveOccurred())
        Expect(completedBuildRun.Status.CompletionTime).ToNot(BeNil())

        // Verify build succeeded
        condition := completedBuildRun.Status.GetCondition(shipwright.Succeeded)
        Expect(condition.Status).To(Equal(metav1.ConditionTrue))

        // Verify image was pushed
        image, err := libk8s.GetImageFromRegistry("registry.example.com/e2e-test:latest")
        Expect(err).ToNot(HaveOccurred())
        Expect(image).ToNot(BeNil())
    })
})
```

## Configuration

The Testing Agent uses `config/testing_config.py` for Shipwright-specific patterns and templates.

### SHIPWRIGHT_TEST_PATTERNS

Defines patterns for strategies, sources, outputs, and security contexts.

```python
SHIPWRIGHT_TEST_PATTERNS = {
    "strategies": {
        "kaniko": {
            "keywords": ["kaniko", "registry", "image", "dockerfile"],
            "helpers": ["libfactory.NewKanikoStrategy"],
            "test_template": "kaniko_build_test",
            "common_scenarios": [
                "basic kaniko build with registry push",
                "kaniko build with custom dockerfile path",
                "kaniko build with build args",
            ],
        },
        # ... other strategies
    },
    "source_types": { ... },
    "output_types": { ... },
    "security_contexts": { ... },
}
```

### TEST_TYPES

Specifications for each test type (unit, integration, E2E).

```python
TEST_TYPES = {
    "unit": {
        "framework": "ginkgo-v2",
        "scope": "isolated_with_mocks",
        "duration": "fast",
        "focus_areas": ["function logic", "error handling", ...],
    },
    # ... other types
}
```

### GINKGO_IMPORTS

Go import templates for test files.

```python
GINKGO_IMPORTS = {
    "dot_imports": [
        "github.com/onsi/ginkgo/v2",
        "github.com/onsi/gomega",
    ],
    "shipwright_api": [
        "shipwright \"github.com/shipwright-io/build/pkg/apis/build/v1beta1\"",
    ],
    "test_helpers": [
        "\"github.com/shipwright-io/build/test/libfactory\"",
        "\"github.com/shipwright-io/build/test/libk8s\"",
    ],
}
```

### GINKGO_TEMPLATES

Test structure templates for consistent formatting.

```python
GINKGO_TEMPLATES = {
    "describe_block": 'var _ = Describe("{description}", func() {{ {content} }})',
    "describe_table": 'DescribeTable("{description}", func(scenario {scenario_type}) {{ {test_logic} }}, {entries})',
    # ... other templates
}
```

## Output Structure

### Complete Output Dictionary

```python
{
    "test_plan": str,                 # Human-readable strategy document
    "test_specifications": dict,      # YAML structured specs
    "unit_tests": {                   # File name → code
        "buildrun_types_test.go": "...",
        "validation_test.go": "...",
    },
    "integration_tests": {
        "controller_timeout_test.go": "...",
    },
    "e2e_tests": {
        "timeout_builds_test.go": "...",
    },
    "test_summary": str,              # Statistics and metrics
    "coverage_analysis": str,         # Acceptance criteria mapping
    "patterns_detected": {            # Detected Shipwright patterns
        "strategies": ["kaniko"],
        "source_types": ["git"],
        "output_types": ["image"],
        "security_contexts": [],
    },
}
```

### Test Files Organization

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

## Usage Examples

### Basic Usage

```python
from agents.testing_agent import run_testing

context = {
    "design_analysis": "# Design Document\n...",
    "impacted_components": ["buildrun_api", "buildrun_controller"],
    "acceptance_criteria": [
        "BuildRun API accepts timeout field",
        "Controller enforces timeout",
        "Build fails gracefully after timeout",
    ],
    "issue_title": "Add timeout support to BuildRun",
    "issue_description": "Users need to configure max build execution time",
}

result = run_testing(context)

print(f"Test Plan:\n{result['test_plan']}\n")
print(f"Unit Tests Generated: {len(result['unit_tests'])} files")
print(f"Integration Tests: {len(result['integration_tests'])} files")
print(f"E2E Tests: {len(result['e2e_tests'])} files")
```

### With Pattern Detection

```python
context = {
    "design_analysis": "Add kaniko build support with git source",
    "impacted_components": ["build_api", "buildrun_controller"],
    "acceptance_criteria": [
        "Build accepts kaniko strategy configuration",
        "BuildRun executes kaniko build from git source",
    ],
    "issue_description": "Implement kaniko strategy for building from git repositories",
}

result = run_testing(context)

# Patterns automatically detected
print(f"Detected Patterns: {result['patterns_detected']}")
# Output: {'strategies': ['kaniko'], 'source_types': ['git'], ...}
```

### Coverage Analysis

```python
result = run_testing(context)

# Coverage mapping shows which tests cover which criteria
print(result['coverage_analysis'])

# Example output:
# AC-1: BuildRun accepts timeout field
#   - BUILD-TIMEOUT-001 (unit test)
#   - BUILD-TIMEOUT-002 (unit test)
# AC-2: Controller enforces timeout
#   - BUILD-TIMEOUT-101 (integration test)
# AC-3: Build fails gracefully
#   - BUILD-TIMEOUT-201 (E2E test)
#
# Coverage: 100% (3/3 criteria covered)
```

## API Reference

### run_testing()

Main entry point for test generation.

**Signature:**

```python
def run_testing(context: Dict[str, Any]) -> Dict[str, Any]
```

**Parameters:**

- `context` (Dict[str, Any]): Test generation context
  - `design_analysis` (str, required): Design document
  - `impacted_components` (List[str], required): Affected components
  - `acceptance_criteria` (List[str], required): Testable criteria
  - `issue_title` (str, optional): Feature/bug title
  - `issue_description` (str, optional): Detailed description
  - `implementation_plan` (List[str], optional): Implementation steps
  - `risks` (List[str], optional): Identified risks

**Returns:**

Dictionary containing:
- `test_plan`: Human-readable test strategy
- `test_specifications`: YAML test specs
- `unit_tests`: Generated unit test code
- `integration_tests`: Generated integration test code
- `e2e_tests`: Generated E2E test code
- `test_summary`: Summary statistics
- `coverage_analysis`: Coverage mapping
- `patterns_detected`: Detected patterns

**Raises:**

- `TestingAgentError`: If API key is missing or required context fields are missing

### generate_test_summary()

Generate a summary of test generation results.

**Signature:**

```python
def generate_test_summary(test_results: Dict[str, Any]) -> str
```

**Parameters:**

- `test_results`: Results from `run_testing()`

**Returns:**

Formatted summary string with:
- Test count by type
- Patterns detected
- Coverage analysis

## Quality Features

### Pattern-Aware Testing

The agent detects and generates tests specific to Shipwright patterns:

- **Strategy-specific tests**: Different scenarios for each build strategy
- **Source type tests**: Appropriate tests for git, bundle, registry sources
- **Output validation**: Registry push, ImageStream tests
- **Security context tests**: Privileged, nonroot, restricted scenarios

### Coverage Mapping

Every test is mapped back to acceptance criteria:

- Shows which criteria are covered
- Identifies gaps in test coverage
- Provides coverage percentage
- Recommends additional tests

### Realistic Test Generation

Tests match actual Shipwright patterns:

- Uses real Shipwright test helpers
- Follows existing test structure
- Imports match project conventions
- Test IDs follow Shipwright format

### Comprehensive Test Scenarios

Generated tests cover:

- **Happy paths**: Expected successful scenarios
- **Error paths**: Failure modes and error handling
- **Edge cases**: Boundary conditions and limits
- **Integration points**: Cross-component interactions

## Qualityflow Integration

The Testing Agent is inspired by Red Hat's qualityflow test generation framework, adapted for Shipwright Build:

**From Qualityflow:**
- Test planning methodology
- Structured test specifications
- Data-Driven Testing patterns
- Coverage analysis approach

**Adapted for Shipwright:**
- Ginkgo v2 framework
- Shipwright domain patterns
- Kubernetes testing patterns
- Build-specific scenarios

## Troubleshooting

### Common Issues

**Issue: Generated tests don't compile**

- Check Go imports are correct
- Verify Shipwright API version matches
- Ensure test helpers are available
- Review Go syntax in generated code

**Issue: Pattern detection misses patterns**

- Add keywords to `testing_config.py`
- Update `SHIPWRIGHT_TEST_PATTERNS`
- Provide more detailed issue descriptions
- Check pattern detection logic

**Issue: Tests missing for some acceptance criteria**

- Review coverage analysis output
- Check if criteria are testable
- Add more context to acceptance criteria
- Request additional test generation

**Issue: Test IDs not following format**

- Check `generate_test_id()` function
- Verify component names are correct
- Update test ID generation logic

### Debugging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

result = run_testing(context)
```

Check raw output:

```python
result = run_testing(context)
print(result['raw_output'])  # See full Claude API response
```

## Best Practices

### 1. Provide Clear Acceptance Criteria

**Good:**
```python
"acceptance_criteria": [
    "BuildRun API accepts timeout field as metav1.Duration",
    "Controller terminates build after timeout exceeded",
    "Build status shows timeout failure reason",
]
```

**Poor:**
```python
"acceptance_criteria": [
    "Add timeout",
    "Make it work",
]
```

### 2. Include Comprehensive Design Analysis

Provide detailed design context:
- Component impacts
- API changes
- Controller behavior
- Expected outcomes

### 3. Specify Risks to Test

```python
"risks": [
    "Race condition during timeout enforcement",
    "Resource leak if cleanup fails",
    "Grace period handling complexity",
]
```

### 4. Use Descriptive Issue Descriptions

Include:
- Problem statement
- Proposed solution
- Technical details
- Examples

### 5. Review Generated Tests

- Verify test logic matches requirements
- Check test data coverage
- Validate assertions
- Ensure proper cleanup

## Future Enhancements

Planned improvements:

- **Test execution integration**: Run generated tests automatically
- **Coverage reporting**: Detailed code coverage analysis
- **Performance tests**: Generate performance and load tests
- **Mutation testing**: Test quality validation
- **Test data generation**: Realistic test data creation
- **Visual test reports**: Graphical coverage and results display

---

**For questions or issues with the Testing Agent, see the main [HOWTO.md](HOWTO.md) guide or open an issue.**
