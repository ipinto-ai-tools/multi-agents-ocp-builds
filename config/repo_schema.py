"""Pydantic schema for repos.yaml configuration.

Defines the structure and validation rules for repository entries,
including optional language and per-repo build/lint/test/doc commands,
workflow stage ordering, approval requirements, and prompt overrides.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, field_validator

VALID_STAGES = ["design", "develop", "testing", "docs"]


class RepoCommands(BaseModel):
    """Build / lint / test / doc commands for a repository."""

    build: str | None = None
    lint: str | None = None
    test: str | None = None
    doc: str | None = None


class RepoEntry(BaseModel):
    """A single repository entry in repos.yaml."""

    path: str
    language: str | None = None  # e.g. "go", "python"
    commands: RepoCommands = RepoCommands()

    @field_validator("path")
    @classmethod
    def path_must_be_absolute(cls, v: str) -> str:
        if not Path(v).is_absolute():
            raise ValueError(f"Repository path must be absolute: {v}")
        return v


class ApprovalConfig(BaseModel):
    """Approval requirements for workflow stages."""

    required_stages: list[str] = []
    auto_approve: bool = False

    @field_validator("required_stages")
    @classmethod
    def validate_stage_names(cls, v: list[str]) -> list[str]:
        for stage in v:
            if stage not in VALID_STAGES:
                raise ValueError(
                    f"Invalid stage name '{stage}'. Valid: {VALID_STAGES}"
                )
        return v


class PromptOverrides(BaseModel):
    """Optional prompt overrides per stage.

    When set, these replace the default system prompts.
    """

    design: str | None = None
    develop: str | None = None
    test: str | None = None
    docs: str | None = None


class RepoConfig(BaseModel):
    """Top-level repos.yaml schema."""

    repos: list[RepoEntry] = []
    stages: list[str] = VALID_STAGES.copy()
    approvals: ApprovalConfig = ApprovalConfig()
    prompts: PromptOverrides = PromptOverrides()

    @field_validator("stages")
    @classmethod
    def validate_stages(cls, v: list[str]) -> list[str]:
        for stage in v:
            if stage not in VALID_STAGES:
                raise ValueError(
                    f"Invalid stage '{stage}'. Valid: {VALID_STAGES}"
                )
        if len(v) != len(set(v)):
            raise ValueError("Duplicate stages not allowed")
        return v
