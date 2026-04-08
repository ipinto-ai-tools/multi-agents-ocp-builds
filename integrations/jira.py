"""Jira integration — fetch and update tickets."""
import os
from typing import Any

from utils.file_logger import get_logger

logger = get_logger(__name__)


def fetch_jira_ticket(ticket_id: str) -> dict[str, Any]:
    """Fetch a Jira ticket and map it to pipeline state fields.

    In DRY_RUN mode, returns mock data without API calls.

    Returns dict with: ticket_id, ticket_url, issue_title, issue_description,
    issue_type, issue_priority, issue_labels, issue_components, pr_urls
    """
    if os.getenv("DRY_RUN", "").lower() == "true":
        return _mock_fetch(ticket_id)
    return _live_fetch(ticket_id)


def _live_fetch(ticket_id: str) -> dict[str, Any]:
    from mcp.jira_stub import fetch_ticket
    from tools.jira_client import map_ticket_to_state

    ticket_data = fetch_ticket(ticket_id)
    return map_ticket_to_state(ticket_data)


def _mock_fetch(ticket_id: str) -> dict[str, Any]:
    from config.mock_responses import MOCK_JIRA_TICKET
    from tools.jira_client import map_ticket_to_state

    mock_data = dict(MOCK_JIRA_TICKET)
    mock_data["ticket_id"] = ticket_id
    mock_data["ticket_url"] = f"https://issues.redhat.com/browse/{ticket_id}"
    return map_ticket_to_state(mock_data)


def update_jira_ticket(ticket_id: str, comment: str) -> dict[str, Any]:
    """Post a comment to a Jira ticket.

    In DRY_RUN mode, returns success without API calls.
    """
    if os.getenv("DRY_RUN", "").lower() == "true":
        return {"success": True, "dry_run": True}

    from tools.jira_client import get_jira_client

    client = get_jira_client()
    result = client.update_ticket(ticket_id, comment)
    return {"success": result}
