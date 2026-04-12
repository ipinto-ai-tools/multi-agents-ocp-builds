"""Data models for the persistent memory layer."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, field_validator


VALID_STAGES = ["design", "develop", "testing", "docs"]


class MemoryType(StrEnum):
    """Categories of memories captured during pipeline execution."""

    best_practice = "best_practice"
    anti_pattern = "anti_pattern"
    heuristic = "heuristic"
    execution_note = "execution_note"
    reusable_context = "reusable_context"


class MemoryEntry(BaseModel):
    """A single memory captured during a pipeline run."""

    id: int | None = None
    session_id: str
    stage: str
    memory_type: MemoryType
    title: str
    content: str
    tags: list[str] = []
    issue_title: str | None = None
    issue_type: str | None = None
    created_at: str | None = None
    relevance_score: float = 1.0

    @field_validator("stage")
    @classmethod
    def _validate_stage(cls, value: str) -> str:
        if value not in VALID_STAGES:
            msg = f"stage must be one of {VALID_STAGES}, got '{value}'"
            raise ValueError(msg)
        return value


class MemoryQuery(BaseModel):
    """Query parameters for retrieving memories."""

    query_text: str
    stage: str | None = None
    memory_types: list[MemoryType] | None = None
    issue_type: str | None = None
    max_results: int = 5
