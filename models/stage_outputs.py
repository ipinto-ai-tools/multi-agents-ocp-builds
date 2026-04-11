"""Pydantic models defining structured output contracts for each pipeline stage.

Each model captures the typed, validated shape of a stage's outputs.
These contracts complement the existing ``AgentState`` TypedDict — agents
continue to write plain dicts into LangGraph state, and the contracts
can be used to validate those dicts at stage boundaries.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CodeFile(BaseModel):
    """A generated code file."""

    path: str
    content: str
    description: str = ""


class DesignOutput(BaseModel):
    """Output contract for the Design stage.

    Required fields mirror the existing validator checks in
    ``agents.validators.validate_design_output``.
    """

    design_analysis: str = Field(..., min_length=50)
    impacted_components: list[str] = []
    risks: list[str] = []
    acceptance_criteria: list[str] = []
    implementation_plan: list[str] = Field(..., min_length=1)


class DevelopOutput(BaseModel):
    """Output contract for the Development stage."""

    code_files: list[CodeFile] = Field(..., min_length=1)
    test_files: list[CodeFile] = []
    pr_description: str = ""
    security_notes: str = ""
    new_dependencies: list[str] = []


class TestingOutput(BaseModel):
    """Output contract for the Testing stage."""

    __test__ = False  # Prevent pytest from collecting this as a test class

    test_plan: str = Field(..., min_length=20)
    test_specifications: dict = {}
    unit_tests: dict[str, str] = {}
    integration_tests: dict[str, str] = {}
    e2e_tests: dict[str, str] = {}
    coverage_analysis: str = ""


class DocsOutput(BaseModel):
    """Output contract for the Documentation stage."""

    pr_summary: str = Field(..., min_length=20)
    release_notes: str = ""
    docs_changes: dict[str, str] = {}
    upgrade_notes: str = ""
    known_limitations: str = ""
    jtbd_documentation: str = ""
    ship_document: str = ""
    high_level_design: str = ""


class ReviewOutput(BaseModel):
    """Output contract for the Code Review gate."""

    review_passed: bool = True
    review_findings: list[str] = []
    review_summary: str = ""
    review_iteration: int = 0
