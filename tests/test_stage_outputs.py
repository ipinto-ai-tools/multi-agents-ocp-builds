"""Tests for structured stage output contracts (Pydantic models).

Covers:
- Valid / invalid construction for every stage model
- The new ``validate_stage_output`` helper in ``agents.validators``
- Backward compatibility: existing ``validate_phase`` still works
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.stage_outputs import (
    CodeFile,
    DesignOutput,
    DevelopOutput,
    DocsOutput,
    ReviewOutput,
    TestingOutput,
)
from agents.validators import ValidationResult, validate_phase, validate_stage_output


# ---------------------------------------------------------------------------
# Helpers — reusable minimal-valid dicts
# ---------------------------------------------------------------------------

def _valid_design_data() -> dict:
    return {
        "design_analysis": "A" * 60,  # > 50 chars
        "impacted_components": ["controller", "api"],
        "risks": ["breaking change"],
        "acceptance_criteria": ["works correctly"],
        "implementation_plan": ["step 1", "step 2"],
    }


def _valid_develop_data() -> dict:
    return {
        "code_files": [
            {"path": "pkg/main.go", "content": "package main", "description": "entry"},
        ],
        "test_files": [],
        "pr_description": "Adds timeout support",
    }


def _valid_test_data() -> dict:
    return {
        "test_plan": "T" * 25,  # > 20 chars
        "unit_tests": {"test_timeout_test.go": "func Test..."},
        "integration_tests": {},
        "e2e_tests": {},
        "coverage_analysis": "80%",
    }


def _valid_docs_data() -> dict:
    return {
        "pr_summary": "S" * 25,  # > 20 chars
        "release_notes": "Added timeout",
        "docs_changes": {"README.md": "updated"},
    }


def _valid_review_data() -> dict:
    return {
        "review_passed": True,
        "review_findings": [],
        "review_summary": "All good",
        "review_iteration": 1,
    }


# ===================================================================
# DesignOutput
# ===================================================================

class TestDesignOutput:
    """Tests for the DesignOutput Pydantic model."""

    def test_valid_all_fields(self) -> None:
        output = DesignOutput(**_valid_design_data())
        assert len(output.design_analysis) >= 50
        assert output.impacted_components == ["controller", "api"]
        assert output.risks == ["breaking change"]
        assert output.acceptance_criteria == ["works correctly"]
        assert output.implementation_plan == ["step 1", "step 2"]

    def test_valid_required_fields_only(self) -> None:
        output = DesignOutput(
            design_analysis="A" * 60,
            implementation_plan=["step 1"],
        )
        assert output.impacted_components == []
        assert output.risks == []
        assert output.acceptance_criteria == []

    def test_invalid_design_analysis_too_short(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            DesignOutput(design_analysis="short", implementation_plan=["step 1"])
        errors = exc_info.value.errors()
        assert any("design_analysis" in str(e["loc"]) for e in errors)

    def test_invalid_missing_implementation_plan(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            DesignOutput(design_analysis="A" * 60)  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any("implementation_plan" in str(e["loc"]) for e in errors)

    def test_invalid_empty_implementation_plan(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            DesignOutput(design_analysis="A" * 60, implementation_plan=[])
        errors = exc_info.value.errors()
        assert any("implementation_plan" in str(e["loc"]) for e in errors)


# ===================================================================
# DevelopOutput
# ===================================================================

class TestDevelopOutput:
    """Tests for the DevelopOutput Pydantic model."""

    def test_valid_with_code_files(self) -> None:
        output = DevelopOutput(**_valid_develop_data())
        assert len(output.code_files) == 1
        assert output.code_files[0].path == "pkg/main.go"
        assert isinstance(output.code_files[0], CodeFile)

    def test_invalid_empty_code_files(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            DevelopOutput(code_files=[])
        errors = exc_info.value.errors()
        assert any("code_files" in str(e["loc"]) for e in errors)

    def test_invalid_missing_code_files(self) -> None:
        with pytest.raises(ValidationError):
            DevelopOutput()  # type: ignore[call-arg]

    def test_code_file_defaults(self) -> None:
        cf = CodeFile(path="a.go", content="pkg a")
        assert cf.description == ""


# ===================================================================
# TestingOutput
# ===================================================================

class TestTestingOutput:
    """Tests for the TestingOutput Pydantic model."""

    def test_valid(self) -> None:
        output = TestingOutput(**_valid_test_data())
        assert len(output.test_plan) >= 20
        assert "test_timeout_test.go" in output.unit_tests

    def test_invalid_test_plan_too_short(self) -> None:
        with pytest.raises(ValidationError):
            TestingOutput(test_plan="short")

    def test_valid_required_only(self) -> None:
        output = TestingOutput(test_plan="T" * 25)
        assert output.unit_tests == {}
        assert output.integration_tests == {}
        assert output.e2e_tests == {}
        assert output.coverage_analysis == ""


# ===================================================================
# DocsOutput
# ===================================================================

class TestDocsOutput:
    """Tests for the DocsOutput Pydantic model."""

    def test_valid(self) -> None:
        output = DocsOutput(**_valid_docs_data())
        assert len(output.pr_summary) >= 20

    def test_invalid_pr_summary_too_short(self) -> None:
        with pytest.raises(ValidationError):
            DocsOutput(pr_summary="short")

    def test_valid_required_only(self) -> None:
        output = DocsOutput(pr_summary="S" * 25)
        assert output.release_notes == ""
        assert output.docs_changes == {}
        assert output.upgrade_notes == ""
        assert output.known_limitations == ""
        assert output.jtbd_documentation == ""
        assert output.ship_document == ""
        assert output.high_level_design == ""


# ===================================================================
# ReviewOutput
# ===================================================================

class TestReviewOutput:
    """Tests for the ReviewOutput Pydantic model."""

    def test_valid(self) -> None:
        output = ReviewOutput(**_valid_review_data())
        assert output.review_passed is True
        assert output.review_iteration == 1

    def test_defaults(self) -> None:
        output = ReviewOutput()
        assert output.review_passed is True
        assert output.review_findings == []
        assert output.review_summary == ""
        assert output.review_iteration == 0


# ===================================================================
# validate_stage_output()
# ===================================================================

class TestValidateStageOutput:
    """Tests for the new ``validate_stage_output`` helper."""

    def test_valid_design(self) -> None:
        result = validate_stage_output("design", _valid_design_data())
        assert result.passed is True
        assert result.phase == "design"
        assert result.issues == []

    def test_invalid_design(self) -> None:
        result = validate_stage_output("design", {"design_analysis": "short"})
        assert result.passed is False
        assert len(result.issues) > 0

    def test_valid_develop(self) -> None:
        result = validate_stage_output("develop", _valid_develop_data())
        assert result.passed is True

    def test_invalid_develop_empty_code_files(self) -> None:
        result = validate_stage_output("develop", {"code_files": []})
        assert result.passed is False

    def test_valid_testing(self) -> None:
        result = validate_stage_output("testing", _valid_test_data())
        assert result.passed is True

    def test_valid_docs(self) -> None:
        result = validate_stage_output("docs", _valid_docs_data())
        assert result.passed is True

    def test_valid_code_review(self) -> None:
        result = validate_stage_output("code_review", _valid_review_data())
        assert result.passed is True

    def test_unknown_phase_passes(self) -> None:
        result = validate_stage_output("unknown_phase", {})
        assert result.passed is True
        assert result.summary == {"note": "No contract for this phase"}

    def test_returns_validation_result_type(self) -> None:
        result = validate_stage_output("design", _valid_design_data())
        assert isinstance(result, ValidationResult)


# ===================================================================
# Backward compatibility — existing validate_phase() still works
# ===================================================================

class TestBackwardCompatibility:
    """Ensure the existing ``validate_phase`` function is unchanged."""

    def test_validate_phase_design_valid(self, sample_design_output: dict) -> None:
        result = validate_phase("design", sample_design_output)
        assert result.passed is True
        assert result.phase == "design"

    def test_validate_phase_design_invalid(self) -> None:
        result = validate_phase("design", {"design_analysis": "short"})
        assert result.passed is False

    def test_validate_phase_develop_valid(self) -> None:
        state = {
            "code_files": [{"path": "a.go", "content": "pkg a"}],
            "pr_description": "A decent PR description here",
        }
        result = validate_phase("develop", state)
        assert result.passed is True

    def test_validate_phase_unknown(self) -> None:
        result = validate_phase("nonexistent", {})
        assert result.passed is True
        assert result.summary == {"note": "No validator for this phase"}

    def test_validate_phase_testing_valid(self) -> None:
        state = {"test_plan": "A comprehensive test plan for the feature"}
        result = validate_phase("testing", state)
        assert result.passed is True

    def test_validate_phase_docs_valid(self) -> None:
        state = {"pr_summary": "A comprehensive PR summary here"}
        result = validate_phase("docs", state)
        assert result.passed is True
