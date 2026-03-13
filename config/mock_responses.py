"""Mock responses for dry-run mode testing.

This module provides mock Claude API responses for testing agents without
making actual API calls. Used when --dry-run flag is enabled.
"""

# Mock response for Design Agent
MOCK_DESIGN_RESPONSE = """# Design Analysis: Add Timeout Support to BuildRun

## Overview
This feature adds timeout configuration to BuildRun resources to prevent builds from running indefinitely.

## Impacted Components

### 1. BuildRun API (`pkg/apis/build/v1beta1/buildrun_types.go`)
- Add `Timeout` field to BuildRunSpec
- Validation for timeout values (must be positive duration)
- Default timeout handling

### 2. BuildRun Controller (`pkg/reconciler/buildrun/buildrun.go`)
- Implement timeout enforcement in reconciliation loop
- Handle timeout expiration and cleanup
- Update BuildRun status when timeout occurs

### 3. BuildRun Webhook (`pkg/webhook/conversion/buildrun.go`)
- Validate timeout field in admission webhook
- Conversion between API versions if needed

## Risks

### High Priority
- **Risk**: Existing builds might be terminated if default timeout is too aggressive
  **Mitigation**: Make timeout optional, no default value initially

### Medium Priority
- **Risk**: Timeout cleanup could leave orphaned pods
  **Mitigation**: Ensure proper cascade deletion in controller

### Low Priority
- **Risk**: Timeout precision depends on reconciliation interval
  **Mitigation**: Document that timeout is approximate (+/- reconciliation interval)

## Acceptance Criteria

1. BuildRun accepts `timeout` field in spec (duration format: "30m", "1h")
2. Controller enforces timeout and terminates build when exceeded
3. BuildRun status shows timeout reason when build is terminated
4. Existing BuildRuns without timeout continue to work (backward compatible)
5. Webhook validates timeout is positive duration
6. Documentation updated with timeout usage examples

## Implementation Plan

1. **Phase 1: API Changes**
   - Add Timeout field to BuildRunSpec
   - Add validation for timeout format
   - Update CRD with new field

2. **Phase 2: Controller Logic**
   - Implement timeout tracking in reconciler
   - Add timeout enforcement logic
   - Update status conditions for timeout

3. **Phase 3: Webhook Validation**
   - Add admission validation for timeout field
   - Ensure conversion compatibility

4. **Phase 4: Testing**
   - Unit tests for timeout validation
   - Integration tests for timeout enforcement
   - E2E tests for timeout scenarios

5. **Phase 5: Documentation**
   - Update API documentation
   - Add usage examples
   - Update troubleshooting guide

## Test Strategy

- **Unit Tests**: Validation logic, timeout calculation
- **Integration Tests**: Controller timeout enforcement
- **E2E Tests**: Full BuildRun lifecycle with timeout
"""

# Extracted structured data from design
MOCK_DESIGN_STRUCTURED = {
    "design_analysis": MOCK_DESIGN_RESPONSE,
    "impacted_components": [
        "buildrun_api",
        "buildrun_controller",
        "buildrun_webhook"
    ],
    "risks": [
        {
            "level": "high",
            "description": "Existing builds might be terminated if default timeout is too aggressive",
            "mitigation": "Make timeout optional, no default value initially"
        },
        {
            "level": "medium",
            "description": "Timeout cleanup could leave orphaned pods",
            "mitigation": "Ensure proper cascade deletion in controller"
        },
        {
            "level": "low",
            "description": "Timeout precision depends on reconciliation interval",
            "mitigation": "Document that timeout is approximate (+/- reconciliation interval)"
        }
    ],
    "acceptance_criteria": [
        "BuildRun accepts timeout field in spec (duration format: 30m, 1h)",
        "Controller enforces timeout and terminates build when exceeded",
        "BuildRun status shows timeout reason when build is terminated",
        "Existing BuildRuns without timeout continue to work (backward compatible)",
        "Webhook validates timeout is positive duration",
        "Documentation updated with timeout usage examples"
    ],
    "implementation_plan": [
        "Phase 1: API Changes - Add Timeout field to BuildRunSpec",
        "Phase 2: Controller Logic - Implement timeout tracking",
        "Phase 3: Webhook Validation - Add admission validation",
        "Phase 4: Testing - Unit, integration, and E2E tests",
        "Phase 5: Documentation - Update API docs and examples"
    ]
}

# Mock response for Testing Agent
MOCK_TESTING_RESPONSE = """# Test Plan: BuildRun Timeout Support

## Test Strategy

### Unit Tests (pkg/apis/build/v1beta1/)
- Test timeout field validation
- Test timeout parsing from string to duration
- Test default timeout behavior

### Integration Tests (test/integration/)
- Test controller timeout enforcement
- Test timeout with various build strategies
- Test timeout status updates

### E2E Tests (test/e2e/)
- Test complete BuildRun lifecycle with timeout
- Test timeout with real build execution
- Test timeout cleanup and pod deletion

## Test Specifications

### TS-TIMEOUT-001: Timeout Field Validation
**Type**: Unit Test
**Component**: BuildRun API
**Description**: Validate timeout field accepts valid durations and rejects invalid ones

**Test Cases**:
- Valid: "30m", "1h", "90s"
- Invalid: "-5m", "invalid", "0s"

### TS-TIMEOUT-002: Controller Timeout Enforcement
**Type**: Integration Test
**Component**: BuildRun Controller
**Description**: Verify controller terminates builds that exceed timeout

**Test Cases**:
- BuildRun with 30s timeout should terminate after 30s
- BuildRun status should show "Timeout" condition
- Build pod should be deleted after timeout

### TS-TIMEOUT-003: Timeout E2E Workflow
**Type**: E2E Test
**Component**: Full System
**Description**: End-to-end test of timeout feature with real builds

**Test Cases**:
- Create BuildRun with short timeout
- Verify build starts
- Wait for timeout to occur
- Verify build is terminated
- Verify status reflects timeout reason
"""

MOCK_TESTING_STRUCTURED = {
    "test_plan": MOCK_TESTING_RESPONSE,
    "test_specifications": {
        "TS-TIMEOUT-001": {
            "id": "TS-TIMEOUT-001",
            "type": "unit",
            "component": "buildrun_api",
            "description": "Validate timeout field accepts valid durations",
            "scenarios": [
                {"input": "30m", "expected": "valid"},
                {"input": "1h", "expected": "valid"},
                {"input": "-5m", "expected": "invalid"}
            ]
        },
        "TS-TIMEOUT-002": {
            "id": "TS-TIMEOUT-002",
            "type": "integration",
            "component": "buildrun_controller",
            "description": "Verify controller terminates builds that exceed timeout",
            "scenarios": [
                {"timeout": "30s", "expected": "terminated after 30s"},
                {"timeout": "1m", "expected": "status shows Timeout condition"}
            ]
        }
    },
    "unit_tests": {
        "test/unit/buildrun_timeout_test.go": """package v1beta1_test

import (
\t. "github.com/onsi/ginkgo/v2"
\t. "github.com/onsi/gomega"
\tmetav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
\tbuildv1beta1 "github.com/shipwright-io/build/pkg/apis/build/v1beta1"
)

var _ = Describe("BuildRun Timeout Validation", func() {
\tDescribeTable("timeout field validation",
\t\tfunc(timeout string, shouldBeValid bool) {
\t\t\tbr := &buildv1beta1.BuildRun{
\t\t\t\tObjectMeta: metav1.ObjectMeta{
\t\t\t\t\tName: "test-buildrun",
\t\t\t\t},
\t\t\t\tSpec: buildv1beta1.BuildRunSpec{
\t\t\t\t\tTimeout: &metav1.Duration{Duration: timeout},
\t\t\t\t},
\t\t\t}
\t\t\terr := br.Validate()
\t\t\tif shouldBeValid {
\t\t\t\tExpect(err).ToNot(HaveOccurred())
\t\t\t} else {
\t\t\t\tExpect(err).To(HaveOccurred())
\t\t\t}
\t\t},
\t\tEntry("accepts 30 minutes", "30m", true),
\t\tEntry("accepts 1 hour", "1h", true),
\t\tEntry("rejects negative duration", "-5m", false),
\t\tEntry("rejects zero duration", "0s", false),
\t)
})
"""
    },
    "integration_tests": {
        "test/integration/buildrun_timeout_test.go": """package integration_test

import (
\t. "github.com/onsi/ginkgo/v2"
\t. "github.com/onsi/gomega"
\tmetav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

var _ = Describe("BuildRun Timeout Enforcement", func() {
\tIt("should terminate build after timeout", func() {
\t\t// Create BuildRun with 30s timeout
\t\tbr := createBuildRunWithTimeout("30s")
\t\t
\t\t// Wait for build to start
\t\tEventually(func() bool {
\t\t\treturn isBuildRunning(br)
\t\t}).Should(BeTrue())
\t\t
\t\t// Wait for timeout + buffer
\t\tEventually(func() bool {
\t\t\treturn isBuildTerminated(br)
\t\t}, "45s").Should(BeTrue())
\t\t
\t\t// Verify timeout condition
\t\tcondition := getBuildRunCondition(br, "Timeout")
\t\tExpect(condition.Status).To(Equal("True"))
\t})
})
"""
    },
    "e2e_tests": {
        "test/e2e/buildrun_timeout_test.go": """package e2e_test

import (
\t. "github.com/onsi/ginkgo/v2"
\t. "github.com/onsi/gomega"
)

var _ = Describe("E2E: BuildRun Timeout", func() {
\tIt("should handle complete timeout workflow", func() {
\t\t// Setup: Create Build and BuildRun with timeout
\t\tbuild := createBuild("kaniko-build")
\t\tbr := createBuildRunWithTimeout(build, "1m")
\t\t
\t\t// Execute: Wait for timeout
\t\tEventually(func() string {
\t\t\treturn getBuildRunPhase(br)
\t\t}, "90s").Should(Equal("Failed"))
\t\t
\t\t// Verify: Check timeout reason
\t\tcondition := getBuildRunCondition(br, "Succeeded")
\t\tExpect(condition.Reason).To(Equal("BuildRunTimeout"))
\t\t
\t\t// Cleanup: Verify pod is deleted
\t\tEventually(func() bool {
\t\t\treturn isPodDeleted(br)
\t\t}).Should(BeTrue())
\t})
})
"""
    },
    "test_summary": "Generated 3 test files covering unit, integration, and E2E scenarios for timeout feature",
    "coverage_analysis": "All acceptance criteria covered: API validation (unit), timeout enforcement (integration), full workflow (E2E)"
}

# Mock response for Docs Agent
MOCK_DOCS_RESPONSE = """# Pull Request Summary

## Overview
This PR adds timeout support to BuildRun resources, allowing users to specify a maximum execution time for builds.

## Changes
- Added `Timeout` field to BuildRunSpec API
- Implemented timeout enforcement in BuildRun controller
- Added webhook validation for timeout values
- Comprehensive test coverage (unit, integration, E2E)

## Acceptance Criteria
✅ BuildRun accepts timeout field in spec
✅ Controller enforces timeout and terminates builds
✅ BuildRun status reflects timeout condition
✅ Backward compatible with existing BuildRuns
✅ Webhook validation for positive durations
✅ Documentation updated

## Testing
- Unit tests: Timeout validation logic
- Integration tests: Controller timeout enforcement
- E2E tests: Full timeout workflow

## Documentation
- Updated API reference with timeout field
- Added usage examples to user guide
- Updated troubleshooting section
"""

MOCK_DOCS_STRUCTURED = {
    "pr_summary": MOCK_DOCS_RESPONSE,
    "release_notes": """## New Features

### BuildRun Timeout Support
BuildRuns now support a `timeout` field to prevent builds from running indefinitely.

**Usage**:
```yaml
apiVersion: shipwright.io/v1beta1
kind: BuildRun
metadata:
  name: my-buildrun
spec:
  timeout: 30m  # Build will timeout after 30 minutes
```

**Breaking Changes**: None - timeout is optional and backward compatible.
""",
    "docs_changes": {
        "docs/buildrun.md": """# BuildRun API

## Timeout Configuration

BuildRuns support an optional `timeout` field to limit build execution time.

### Example
```yaml
spec:
  timeout: 30m  # Accepts duration format: 30s, 5m, 1h
```

### Behavior
- When timeout is reached, the build is terminated
- BuildRun status will show "Timeout" condition
- Pod is cleaned up automatically
""",
        "docs/troubleshooting.md": """## Timeout Issues

### Build Terminated Early
If your build is being terminated before completion:
1. Check BuildRun timeout value
2. Increase timeout if needed
3. Verify build doesn't hang indefinitely
"""
    }
}


def get_mock_response(agent_type: str) -> dict:
    """Get mock response for specified agent type.

    Args:
        agent_type: One of 'design', 'testing', 'docs'

    Returns:
        Dictionary with mock agent output

    Raises:
        ValueError: If agent_type is unknown
    """
    mock_responses = {
        "design": MOCK_DESIGN_STRUCTURED,
        "testing": MOCK_TESTING_STRUCTURED,
        "docs": MOCK_DOCS_STRUCTURED
    }

    if agent_type not in mock_responses:
        raise ValueError(f"Unknown agent type: {agent_type}. Must be one of: {list(mock_responses.keys())}")

    return mock_responses[agent_type]
