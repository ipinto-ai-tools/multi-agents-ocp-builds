"""
Output validators for each agent phase.

Validates that agent outputs contain required non-empty fields before
the next phase begins. Prevents silent cascading failures where an agent
returns empty data and subsequent agents produce garbage outputs.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    phase: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def validate_design_output(state: dict) -> ValidationResult:
    """Validate Design Agent outputs."""
    issues = []
    warnings = []

    design_analysis = state.get("design_analysis", "")
    implementation_plan = state.get("implementation_plan", [])
    impacted_components = state.get("impacted_components", [])
    risks = state.get("risks", [])
    acceptance_criteria = state.get("acceptance_criteria", [])

    # Required fields
    if not design_analysis or len(str(design_analysis).strip()) < 50:
        issues.append("design_analysis is empty or too short (< 50 chars)")
    if not implementation_plan:
        issues.append("implementation_plan is empty - development agent needs this")

    # Warnings (non-blocking)
    if not impacted_components:
        warnings.append("No impacted_components identified")
    if not risks:
        warnings.append("No risks identified")
    if not acceptance_criteria:
        warnings.append("No acceptance_criteria defined")

    summary = {
        "Analysis length": f"{len(str(design_analysis))} chars",
        "Implementation plan steps": len(implementation_plan) if isinstance(implementation_plan, list) else "N/A",
        "Impacted components": len(impacted_components) if isinstance(impacted_components, list) else 0,
        "Risks identified": len(risks) if isinstance(risks, list) else 0,
        "Acceptance criteria": len(acceptance_criteria) if isinstance(acceptance_criteria, list) else 0,
    }

    return ValidationResult(
        phase="design",
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        summary=summary,
    )


def validate_develop_output(state: dict) -> ValidationResult:
    """Validate Development Agent outputs."""
    issues = []
    warnings = []

    code_files = state.get("code_files", [])
    pr_description = state.get("pr_description", "")

    if not code_files:
        issues.append("code_files is empty - no Go code was generated")
    if not pr_description or len(str(pr_description).strip()) < 20:
        warnings.append("pr_description is empty or too short")

    summary = {
        "Code files generated": len(code_files) if isinstance(code_files, list) else 0,
        "PR description length": f"{len(str(pr_description))} chars",
    }

    return ValidationResult(
        phase="develop",
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        summary=summary,
    )


def validate_testing_output(state: dict) -> ValidationResult:
    """Validate Testing Agent outputs."""
    issues = []
    warnings = []

    test_plan = state.get("test_plan", "")
    unit_tests = state.get("unit_tests", [])
    integration_tests = state.get("integration_tests", [])

    if not test_plan or len(str(test_plan).strip()) < 20:
        issues.append("test_plan is empty or too short")
    if not unit_tests and not integration_tests:
        warnings.append("No unit or integration tests generated")

    summary = {
        "Test plan length": f"{len(str(test_plan))} chars",
        "Unit tests": len(unit_tests) if isinstance(unit_tests, (list, dict)) else 0,
        "Integration tests": len(integration_tests) if isinstance(integration_tests, (list, dict)) else 0,
    }

    return ValidationResult(
        phase="testing",
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        summary=summary,
    )


def validate_docs_output(state: dict) -> ValidationResult:
    """Validate Docs Agent outputs."""
    issues = []
    warnings = []

    pr_summary = state.get("pr_summary", "")
    release_notes = state.get("release_notes", "")

    if not pr_summary or len(str(pr_summary).strip()) < 20:
        issues.append("pr_summary is empty or too short")
    if not release_notes:
        warnings.append("release_notes is empty")

    summary = {
        "PR summary length": f"{len(str(pr_summary))} chars",
        "Release notes length": f"{len(str(release_notes))} chars",
    }

    return ValidationResult(
        phase="docs",
        passed=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        summary=summary,
    )


def validate_review_output(state: dict) -> ValidationResult:
    """Validate Code Review Agent outputs.

    The review phase itself always 'passes' from a pipeline-blocking perspective —
    routing logic handles retries and max-iteration fallthrough. This validator
    surfaces review results as warnings in the phase summary.

    Args:
        state: Agent state dict after code_review_node runs.

    Returns:
        ValidationResult always with passed=True; review failure shown as warning.
    """
    review_summary = state.get("review_summary", "")
    review_iteration = state.get("review_iteration", 0)
    review_passed = state.get("review_passed", True)
    review_findings = state.get("review_findings", [])

    warnings = []
    if not isinstance(review_findings, list):
        review_findings = []
        warnings.append(f"review_findings has unexpected type: {type(state.get('review_findings')).__name__}")
    if not review_passed:
        warnings.append(f"Review failed: {review_summary}")

    max_iterations = int(os.getenv("MAX_REVIEW_ITERATIONS", "3"))
    if review_iteration >= max_iterations and not review_passed:
        warnings.append(
            f"Max review iterations ({max_iterations}) reached. "
            "Proceeding to testing despite unresolved findings."
        )

    summary = {
        "Review verdict": "PASS" if review_passed else "FAIL",
        "Iteration": review_iteration,
        "Findings": len(review_findings),
        "Summary": review_summary or "N/A",
    }

    return ValidationResult(
        phase="code_review",
        passed=True,
        warnings=warnings,
        summary=summary,
    )


# Map phase name to validator function
VALIDATORS = {
    "design": validate_design_output,
    "develop": validate_develop_output,
    "code_review": validate_review_output,
    "testing": validate_testing_output,
    "docs": validate_docs_output,
}


def validate_phase(phase: str, state: dict) -> ValidationResult:
    """Run the validator for the given phase."""
    validator = VALIDATORS.get(phase)
    if not validator:
        return ValidationResult(
            phase=phase,
            passed=True,
            summary={"note": "No validator for this phase"},
        )
    return validator(state)
