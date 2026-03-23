"""Jira REST API client for fetching ticket data.

Uses Jira Cloud REST API v3 with Basic authentication (email + API token).
No Forge or Rovo required — standard REST API access.

Auth: Base64(email:api_token) via JIRA_USER_EMAIL + JIRA_API_TOKEN env vars.
"""

import json
import os
import base64
import logging
from typing import Any

import requests

from config.jira_config import ACCEPTANCE_CRITERIA_FIELD_ID, ISSUE_TYPE_MAP

logger = logging.getLogger(__name__)

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_USER_EMAIL = os.getenv("JIRA_USER_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_REQUEST_TIMEOUT = int(os.getenv("JIRA_REQUEST_TIMEOUT", "10"))


class JiraClient:
    """Fetch Jira ticket data via REST API v3."""

    def __init__(self, base_url: str, email: str, api_token: str):
        if not base_url:
            raise ValueError("JIRA_BASE_URL is required")
        if not email:
            raise ValueError("JIRA_USER_EMAIL is required")
        if not api_token:
            raise ValueError("JIRA_API_TOKEN is required")

        self.base_url = base_url.rstrip("/")
        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def fetch_ticket(self, ticket_id: str) -> dict[str, Any]:
        """Fetch full ticket data from Jira.

        Returns a dict with all relevant ticket fields.
        Raises requests.HTTPError on API errors.
        """
        url = f"{self.base_url}/rest/api/3/issue/{ticket_id}"
        params = {"expand": "renderedFields,names"}

        logger.info(f"Fetching Jira ticket: {ticket_id}")
        response = requests.get(url, headers=self.headers, params=params, timeout=JIRA_REQUEST_TIMEOUT)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            snippet = response.text[:300]
            logger.warning(
                "Jira returned non-JSON response (status=%s, content-type=%s): %s",
                response.status_code, content_type, snippet
            )
            raise ValueError(
                f"Jira API returned non-JSON response (status={response.status_code}). "
                "Check JIRA_BASE_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN env vars."
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            snippet = response.text[:300]
            logger.warning(
                "Jira returned invalid JSON (status=%s, content-type=%s): %s",
                response.status_code, content_type, snippet
            )
            raise ValueError(
                f"Jira API returned invalid JSON (status={response.status_code}). "
                "Check JIRA_BASE_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN env vars."
            ) from exc

        fields = data.get("fields", {})

        # Fetch comments separately for cleaner parsing
        comments = self._fetch_comments(ticket_id)

        # Fetch linked issues
        linked_issues = self._extract_linked_issues(fields)
        github_pr_urls = self._fetch_remotelinks(ticket_id)

        return {
            "ticket_id": ticket_id,
            "ticket_url": f"{self.base_url}/browse/{ticket_id}",
            "summary": fields.get("summary", ""),
            "description": self._extract_text(fields.get("description")),
            "issue_type": fields.get("issuetype", {}).get("name", ""),
            "status": fields.get("status", {}).get("name", ""),
            "priority": fields.get("priority", {}).get("name", ""),
            "labels": fields.get("labels", []),
            "assignee": (fields.get("assignee") or {}).get("displayName", ""),
            "reporter": (fields.get("reporter") or {}).get("displayName", ""),
            "acceptance_criteria": self._extract_acceptance_criteria(fields),
            "comments": comments,
            "linked_issues": linked_issues,
            "components": [c.get("name") for c in fields.get("components", [])],
            "fix_versions": [v.get("name") for v in fields.get("fixVersions", [])],
            "github_pr_urls": github_pr_urls,
        }

    def _fetch_comments(self, ticket_id: str) -> list[str]:
        """Fetch all comments for a ticket, return as plain text list."""
        url = f"{self.base_url}/rest/api/3/issue/{ticket_id}/comment"
        try:
            response = requests.get(url, headers=self.headers, timeout=JIRA_REQUEST_TIMEOUT)
            response.raise_for_status()
            comments_data = response.json().get("comments", [])
            return [
                f"{c.get('author', {}).get('displayName', 'Unknown')}: {self._extract_text(c.get('body'))}"
                for c in comments_data
            ]
        except Exception as e:
            logger.warning("Could not fetch comments for %s: %s", ticket_id, type(e).__name__)
            logger.debug("Full error: %s", e)
            return []

    def _extract_linked_issues(self, fields: dict) -> list[str]:
        """Extract linked issue keys from ticket fields."""
        linked = []
        for link in fields.get("issuelinks", []):
            if "inwardIssue" in link:
                linked.append(link["inwardIssue"]["key"])
            if "outwardIssue" in link:
                linked.append(link["outwardIssue"]["key"])
        # Also check subtasks
        for subtask in fields.get("subtasks", []):
            linked.append(subtask.get("key", ""))
        return [k for k in linked if k]

    def _fetch_remotelinks(self, ticket_id: str) -> list[str]:
        """Fetch remote links for a ticket and return GitHub PR URLs."""
        url = f"{self.base_url}/rest/api/3/issue/{ticket_id}/remotelink"
        try:
            response = requests.get(url, headers=self.headers, timeout=JIRA_REQUEST_TIMEOUT)
            response.raise_for_status()
            links = response.json()
            github_pr_urls = []
            for link in links:
                obj = link.get("object", {})
                link_url = obj.get("url", "")
                if "github.com" in link_url and "/pull/" in link_url:
                    github_pr_urls.append(link_url)
            logger.info("Found %d GitHub PR link(s) in remotelinks for %s", len(github_pr_urls), ticket_id)
            return github_pr_urls
        except Exception as e:
            logger.warning("Could not fetch remotelinks for %s: %s", ticket_id, type(e).__name__)
            logger.debug("Full error: %s", e)
            return []

    def _extract_acceptance_criteria(self, fields: dict) -> list[str]:
        """Extract acceptance criteria from custom field or description."""
        # Try custom field first
        custom = fields.get(ACCEPTANCE_CRITERIA_FIELD_ID)
        if custom:
            text = self._extract_text(custom)
            if text:
                return [line.lstrip("- ").lstrip("* ").strip() for line in text.splitlines() if line.strip()]

        # Fall back to parsing description for acceptance criteria section
        description = self._extract_text(fields.get("description"))
        if description:
            lines = description.splitlines()
            in_ac_section = False
            criteria = []
            for line in lines:
                lower = line.lower()
                if any(kw in lower for kw in ["acceptance criteria", "acceptance criterion", "definition of done"]):
                    in_ac_section = True
                    continue
                if in_ac_section:
                    if line.strip().startswith("#"):  # next section heading
                        break
                    stripped = line.lstrip("- ").lstrip("* ").strip()
                    if stripped:
                        criteria.append(stripped)
            if criteria:
                return criteria

        return []

    def _extract_text(self, content: Any) -> str:
        """Convert Jira document format (ADF) or plain string to plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            # Atlassian Document Format (ADF)
            return self._adf_to_text(content)
        return str(content)

    def _adf_to_text(self, node: dict, depth: int = 0) -> str:
        """Recursively convert ADF node to plain text."""
        if depth > 50:
            return ""
        node_type = node.get("type", "")
        content = node.get("content", [])
        text = node.get("text", "")

        if node_type == "text":
            return text
        if node_type in ("paragraph", "blockquote"):
            inner = "".join(self._adf_to_text(c, depth) for c in content)
            return inner + "\n"
        if node_type in ("bulletList", "orderedList"):
            items = []
            for i, item in enumerate(content):
                prefix = "-" if node_type == "bulletList" else f"{i+1}."
                inner = "".join(self._adf_to_text(c, depth + 1) for c in item.get("content", []))
                items.append(f"{'  ' * depth}{prefix} {inner.strip()}")
            return "\n".join(items) + "\n"
        if node_type == "listItem":
            return "".join(self._adf_to_text(c, depth) for c in content)
        if node_type in ("heading",):
            level = node.get("attrs", {}).get("level", 2)
            inner = "".join(self._adf_to_text(c, depth) for c in content)
            return f"{'#' * level} {inner}\n"
        if node_type == "hardBreak":
            return "\n"
        if node_type == "doc":
            return "".join(self._adf_to_text(c, depth) for c in content)

        # fallback: recurse into children
        return "".join(self._adf_to_text(c, depth) for c in content)

    def map_to_agent_state(self, ticket_data: dict) -> dict[str, Any]:
        """Map Jira ticket data to AgentState fields.

        Returns a dict ready to merge into AgentState.
        """
        return map_ticket_to_state(ticket_data)

    def update_ticket(self, ticket_id: str, comment: str) -> bool:
        """Post a comment back to the Jira ticket with workflow results.

        Returns True on success, False on failure.
        """
        url = f"{self.base_url}/rest/api/3/issue/{ticket_id}/comment"
        body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}],
                    }
                ],
            }
        }
        try:
            response = requests.post(url, json=body, headers=self.headers, timeout=JIRA_REQUEST_TIMEOUT)
            response.raise_for_status()
            logger.info(f"Posted comment to {ticket_id}")
            return True
        except Exception as e:
            logger.warning("Could not post comment to %s: %s", ticket_id, type(e).__name__)
            logger.debug("Full error: %s", e)
            return False


def get_jira_client() -> JiraClient:
    """Factory: create JiraClient from environment variables.

    Raises ValueError with a helpful message if env vars are missing.
    """
    base_url = os.getenv("JIRA_BASE_URL", "")
    email = os.getenv("JIRA_USER_EMAIL", "")
    api_token = os.getenv("JIRA_API_TOKEN", "")

    missing = []
    if not base_url:
        missing.append("JIRA_BASE_URL (e.g. https://your-org.atlassian.net)")
    if not email:
        missing.append("JIRA_USER_EMAIL (your Atlassian account email)")
    if not api_token:
        missing.append("JIRA_API_TOKEN (from https://id.atlassian.com/manage-profile/security — VPN required)")

    if missing:
        raise ValueError(
            "Jira authentication not configured. Set these environment variables:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    return JiraClient(base_url=base_url, email=email, api_token=api_token)


def is_jira_configured() -> bool:
    """Return True if all Jira env vars are set."""
    return all([
        os.getenv("JIRA_BASE_URL"),
        os.getenv("JIRA_USER_EMAIL"),
        os.getenv("JIRA_API_TOKEN"),
    ])


def map_ticket_to_state(ticket_data: dict) -> dict[str, Any]:
    """Standalone mapping function (no client instance needed).

    Maps raw Jira ticket data to AgentState fields.
    """
    issue_type_raw = ticket_data.get("issue_type", "")
    issue_type = ISSUE_TYPE_MAP.get(issue_type_raw.lower(), "feature")
    comments = ticket_data.get("comments", [])
    return {
        "issue_title": ticket_data["summary"],
        "issue_description": ticket_data["description"],
        "issue_type": issue_type,
        "acceptance_criteria": ticket_data.get("acceptance_criteria", []),
        "jira_ticket_id": ticket_data["ticket_id"],
        "jira_ticket_url": ticket_data["ticket_url"],
        "jira_priority": ticket_data.get("priority", ""),
        "jira_labels": ticket_data.get("labels", []),
        "jira_linked_issues": ticket_data.get("linked_issues", []),
        "jira_comments_summary": "\n".join(comments[:10]),
        "github_pr_urls": ticket_data.get("github_pr_urls", []),
    }
