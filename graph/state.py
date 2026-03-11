"""LangGraph state schema for multi-agent orchestration."""

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """State shared across all agents in the workflow."""

    # Input
    issue_title: str
    issue_description: str
    issue_type: str  # "bug", "feature", "refactor", "docs"

    # Design phase outputs
    design_analysis: str
    impacted_components: list[str]
    risks: list[str]
    acceptance_criteria: list[str]
    implementation_plan: str

    # Development phase outputs
    code_changes: dict[str, str]  # file_path: changes
    files_modified: list[str]
    test_results: dict

    # Test phase outputs
    test_summary: str
    coverage_gaps: list[str]
    test_failures: list[str]

    # Documentation phase outputs
    pr_summary: str
    release_notes: str
    docs_changes: dict[str, str]

    # Control flow
    current_phase: str  # "design", "development", "test", "docs", "done"
    approval_status: str  # "pending", "approved", "rejected"

    # Messages for agent communication
    messages: Annotated[Sequence[dict], add_messages]

    # Repository context
    repo_path: str
    target_branch: str
