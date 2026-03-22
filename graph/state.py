"""LangGraph state schema for multi-agent orchestration."""

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import add_messages


class AgentState(TypedDict, total=False):
    """State shared across all agents in the workflow.

    Using total=False makes all fields optional, which is required for LangGraph's
    StateGraph to properly handle partial state updates during workflow execution.
    """

    # Input
    issue_title: str
    issue_description: str
    issue_type: str  # "bug", "feature", "refactor", "docs"

    # Design phase outputs
    design_analysis: str
    impacted_components: list[str]
    risks: list[str]
    acceptance_criteria: list[str]
    implementation_plan: list[str]

    # Testing phase outputs
    test_plan: str
    test_specifications: dict
    unit_tests: dict[str, str]  # file_path: test_code
    integration_tests: dict[str, str]  # file_path: test_code
    e2e_tests: dict[str, str]  # file_path: test_code
    coverage_analysis: str

    # Development phase outputs
    code_files: list  # List of code file dicts with path, content, description
    test_files: list  # List of test file dicts with path, content
    code_changes: dict[str, str]  # file_path: changes
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
    current_phase: str  # "design", "development", "test", "docs", "done"
    approval_status: str  # "pending", "approved", "rejected"

    # Messages for agent communication
    messages: Annotated[Sequence[dict], add_messages]

    # Repository context
    repo_path: str
    target_branch: str

    # Jira integration
    jira_ticket_id: str             # e.g. "SHIP-123"
    jira_ticket_url: str            # e.g. "https://issues.redhat.com/browse/SHIP-123"
    jira_priority: str              # e.g. "Critical", "Major"
    jira_labels: list[str]          # ticket labels
    jira_linked_issues: list[str]   # related ticket IDs
    jira_comments_summary: str      # concatenated comments (capped at 10)

    # GitHub integration
    github_pr_urls: list[str]   # GitHub PR URLs extracted from Jira remotelinks
    github_pr_data: list[dict]  # Full PR metadata from GitHub API

    # Code Review phase
    review_passed: bool         # True if review found no blocking issues
    review_findings: list[str]  # Structured findings: "[BLOCKING] ...", "[WARNING] ..."
    review_summary: str         # Human-readable verdict, e.g. "2 findings | 1 blocking | FAIL"
    review_iteration: int       # Current iteration count (0 = not yet reviewed)
