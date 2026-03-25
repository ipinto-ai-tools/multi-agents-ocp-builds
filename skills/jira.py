from typing import Any

from skills.base import Skill


class FetchJiraTicketSkill(Skill):
    name = "fetch_jira_ticket"
    description = "Fetch a Jira ticket and map it to agent state fields."
    input_schema = {"ticket_id": {"type": "string"}}
    output_schema = {
        "ticket_id": {"type": "string"},
        "ticket_url": {"type": "string"},
        "issue_title": {"type": "string"},
        "issue_description": {"type": "string"},
        "issue_type": {"type": "string"},
        "issue_priority": {"type": "string"},
        "issue_labels": {"type": "array", "items": {"type": "string"}},
        "issue_components": {"type": "array", "items": {"type": "string"}},
        "pr_urls": {"type": "array", "items": {"type": "string"}},
    }

    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        from mcp.jira_stub import fetch_ticket
        from tools.jira_client import map_ticket_to_state

        ticket_data = fetch_ticket(input["ticket_id"])
        return map_ticket_to_state(ticket_data)

    def _mock_response(self, input: dict[str, Any]) -> dict[str, Any]:
        from config.mock_responses import MOCK_JIRA_TICKET
        from tools.jira_client import map_ticket_to_state

        mock_data = dict(MOCK_JIRA_TICKET)
        ticket_id = input.get("ticket_id", mock_data.get("ticket_id", ""))
        mock_data["ticket_id"] = ticket_id
        mock_data["ticket_url"] = f"https://issues.redhat.com/browse/{ticket_id}"
        return map_ticket_to_state(mock_data)


class UpdateJiraSkill(Skill):
    name = "update_jira"
    description = "Post a comment to a Jira ticket."
    input_schema = {
        "ticket_id": {"type": "string"},
        "comment": {"type": "string"},
    }
    output_schema = {"success": {"type": "boolean"}}

    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        from tools.jira_client import get_jira_client

        client = get_jira_client()
        success = client.update_ticket(input["ticket_id"], input["comment"])
        return {"success": success}

    def _mock_response(self, input: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "dry_run": True}
