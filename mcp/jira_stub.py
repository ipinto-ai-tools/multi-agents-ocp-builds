"""Jira MCP Server stub for future integration.

This module provides a stub implementation for Jira integration via MCP server.
When fully implemented, this will enable agents to interact with Jira for:
- Creating and managing issues/stories/epics
- Updating issue status and transitions
- Adding comments and attachments
- Searching and filtering issues
- Managing sprints and boards

Current Status: STUB - delegates to tools.jira_client when configured
Future Implementation: Will use MCP protocol to communicate with Jira MCP server
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JiraMCPClient:
    """Stub client for Jira MCP server integration.

    This class will be implemented to communicate with a Jira MCP server
    that provides tools for Jira operations.

    Future capabilities:
    - Issue management (create, update, search, transition)
    - Comment management (add, update, delete)
    - Sprint and board operations
    - Custom field handling
    - JQL query support
    """

    def __init__(self, mcp_endpoint: str = "http://localhost:3001"):
        """Initialize Jira MCP client.

        Args:
            mcp_endpoint: MCP server endpoint URL
        """
        self.mcp_endpoint = mcp_endpoint
        self.connected = False

    def connect(self) -> bool:
        """Connect to Jira MCP server.

        Returns:
            True if connection successful, False otherwise
        """
        # TODO: Implement MCP connection
        # This will use the MCP protocol to establish connection
        # with the Jira MCP server (e.g., via mcpl)
        return False

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Story",
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Jira issue.

        Args:
            project_key: Jira project key (e.g., "SHIP")
            summary: Issue summary/title
            description: Issue description
            issue_type: Type of issue (Story, Bug, Epic, Task)
            labels: Optional list of labels
            assignee: Optional assignee username
            priority: Optional priority (Highest, High, Medium, Low, Lowest)

        Returns:
            Issue data including key, URL, etc.

        Raises:
            NotImplementedError: This is a stub implementation
        """
        raise NotImplementedError(
            "Jira MCP integration not yet implemented. "
            "This is a stub for future integration."
        )

    def update_issue(
        self,
        issue_key: str,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update Jira issue fields.

        Args:
            issue_key: Issue key (e.g., "SHIP-123")
            fields: Dictionary of fields to update

        Returns:
            Updated issue data

        Raises:
            NotImplementedError: This is a stub implementation
        """
        raise NotImplementedError(
            "Jira MCP integration not yet implemented. "
            "This is a stub for future integration."
        )

    def transition_issue(
        self,
        issue_key: str,
        transition_name: str,
    ) -> Dict[str, Any]:
        """Transition issue to new status.

        Args:
            issue_key: Issue key (e.g., "SHIP-123")
            transition_name: Name of transition (e.g., "In Progress", "Done")

        Returns:
            Updated issue data

        Raises:
            NotImplementedError: This is a stub implementation
        """
        raise NotImplementedError(
            "Jira MCP integration not yet implemented. "
            "This is a stub for future integration."
        )

    def search_issues(
        self,
        jql: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search for issues using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results to return

        Returns:
            List of matching issues

        Raises:
            NotImplementedError: This is a stub implementation
        """
        raise NotImplementedError(
            "Jira MCP integration not yet implemented. "
            "This is a stub for future integration."
        )

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get issue details.

        Args:
            issue_key: Issue key (e.g., "SHIP-123")

        Returns:
            Issue data

        Raises:
            NotImplementedError: This is a stub implementation
        """
        raise NotImplementedError(
            "Jira MCP integration not yet implemented. "
            "This is a stub for future integration."
        )

    def add_comment(self, issue_key: str, body: str) -> Dict[str, Any]:
        """Add comment to issue.

        Args:
            issue_key: Issue key (e.g., "SHIP-123")
            body: Comment text

        Returns:
            Comment data

        Raises:
            NotImplementedError: This is a stub implementation
        """
        raise NotImplementedError(
            "Jira MCP integration not yet implemented. "
            "This is a stub for future integration."
        )

    def get_sprint_issues(
        self,
        board_id: int,
        sprint_id: int,
    ) -> List[Dict[str, Any]]:
        """Get issues in a sprint.

        Args:
            board_id: Jira board ID
            sprint_id: Sprint ID

        Returns:
            List of issues in sprint

        Raises:
            NotImplementedError: This is a stub implementation
        """
        raise NotImplementedError(
            "Jira MCP integration not yet implemented. "
            "This is a stub for future integration."
        )


# Integration points for agents
def get_jira_client():
    """Get Jira client instance.

    Tries to use the real tools.jira_client when Jira is configured,
    falling back to the stub JiraMCPClient when not configured.

    Returns:
        Real JiraClient if configured, otherwise stub JiraMCPClient

    Example:
        >>> client = get_jira_client()
        >>> # Future: client.create_issue("SHIP", "Title", "Description")
    """
    try:
        from tools.jira_client import get_jira_client as _real_get_jira_client
        return _real_get_jira_client()
    except (ImportError, Exception):
        logger.debug("tools.jira_client not available, falling back to stub JiraMCPClient")
        return JiraMCPClient()


def is_jira_configured() -> bool:
    """Check if Jira is configured and accessible.

    Delegates to tools.jira_client.is_jira_configured when available,
    otherwise returns False.

    Returns:
        True if Jira is configured and reachable, False otherwise

    Example:
        >>> if is_jira_configured():
        ...     client = get_jira_client()
        ...     # Use client
    """
    try:
        from tools.jira_client import is_jira_configured as _real_is_configured
        return _real_is_configured()
    except (ImportError, Exception):
        return False


def is_jira_mcp_available() -> bool:
    """Check if Jira MCP server is available.

    Deprecated alias for is_jira_configured(). Kept for backward compatibility.

    Returns:
        True if Jira is configured and reachable, False otherwise
    """
    return is_jira_configured()


def fetch_ticket(ticket_id: str) -> dict:
    """Fetch a Jira ticket, using mock data in dry-run mode.

    Args:
        ticket_id: Jira ticket ID, e.g. "SHIP-123"

    Returns:
        Dictionary with ticket fields matching JiraClient.fetch_ticket() schema

    Raises:
        ConnectionError: If Jira is unreachable (not on VPN, etc.)
    """
    import os
    import requests

    if os.getenv("DRY_RUN", "false").lower() == "true":
        from config.mock_responses import MOCK_JIRA_TICKET
        mock = dict(MOCK_JIRA_TICKET)
        mock["ticket_id"] = ticket_id
        mock["ticket_url"] = f"{mock['ticket_url'].rsplit('/', 1)[0]}/{ticket_id}"
        logger.info(f"[DRY-RUN] Returning mock Jira ticket for {ticket_id}")
        return mock

    try:
        from tools.jira_client import get_jira_client as _real_get_jira_client
        client = _real_get_jira_client()
        return client.fetch_ticket(ticket_id)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Cannot reach Jira. Are you connected to VPN?\n"
            f"To test without VPN, use --dry-run flag."
        )
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        if status == 404:
            raise ValueError(f"Jira ticket '{ticket_id}' not found. Check the ticket ID.")
        if status in (401, 403):
            raise ValueError(
                f"Jira authentication failed (HTTP {status}). "
                "Check JIRA_USER_EMAIL and JIRA_API_TOKEN in your .env file."
            )
        raise
