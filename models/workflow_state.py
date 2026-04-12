"""Workflow state schema for the SDLC pipeline.

Plain TypedDict replacing the former LangGraph-based AgentState.
The orchestrator passes this state dict between stages.
"""

from typing import TypedDict


class WorkflowState(TypedDict, total=False):
    """State shared across all stages in the workflow."""

    # Input
    issue_title: str
    issue_description: str
    issue_type: str

    # Design phase outputs
    design_analysis: str
    impacted_components: list[str]
    risks: list[str]
    acceptance_criteria: list[str]
    implementation_plan: list[str]

    # Testing phase outputs
    test_plan: str
    test_specifications: dict
    unit_tests: dict[str, str]
    integration_tests: dict[str, str]
    e2e_tests: dict[str, str]
    coverage_analysis: str

    # Development phase outputs
    code_files: list
    test_files: list
    code_changes: dict[str, str]
    files_modified: list[str]
    pr_description: str
    test_results: dict

    # Test execution outputs
    test_summary: str
    coverage_gaps: list[str]
    test_failures: list[str]

    # Documentation phase outputs
    pr_summary: str
    release_notes: str
    docs_changes: dict[str, str]
    upgrade_notes: str
    known_limitations: str
    jtbd_documentation: str
    ship_document: str
    high_level_design: str

    # Control flow
    session_id: str
    current_phase: str
    approval_status: str
    memory_context: str

    # Repository context
    repo_path: str
    repo_paths: list[str]
    repo_entries: list[dict]
    target_branch: str

    # Jira integration
    jira_ticket_id: str
    jira_ticket_url: str
    jira_priority: str
    jira_labels: list[str]
    jira_linked_issues: list[str]
    jira_comments_summary: str

    # GitHub integration
    github_pr_urls: list[str]
    github_pr_data: list[dict]

    # Code Review phase
    review_passed: bool
    review_findings: list[str]
    review_summary: str
    review_iteration: int
