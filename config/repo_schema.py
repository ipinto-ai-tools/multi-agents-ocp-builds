"""Pydantic schema for repos.yaml configuration.

Defines the structure and validation rules for repository entries,
including optional language and per-repo build/lint/test/doc commands.
Stages, approvals, and overrides are deferred to a later iteration.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, field_validator


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


class RepoConfig(BaseModel):
    """Top-level repos.yaml schema."""

    repos: list[RepoEntry] = []
