"""Tests for Jira client and integration.

These tests use mocked HTTP requests (no real Jira connection required).
All test classes are independent and do not require environment variables
unless specifically testing environment-variable-driven behaviour.
"""

import base64
import importlib
import json
import os
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_jira_api_response(
    ticket_id: str = "SHIP-123",
    summary: str = "Test summary",
    description_text: str = "Test description",
    issue_type: str = "Story",
    status: str = "In Progress",
    priority: str = "Major",
    labels: list[str] | None = None,
    assignee: str = "Dev User",
    reporter: str = "PM User",
    linked_keys: list[str] | None = None,
    custom_ac: str | None = None,
) -> dict[str, Any]:
    """Return a dict that mimics a Jira REST API v3 issue response."""
    fields: dict[str, Any] = {
        "summary": summary,
        "description": description_text,  # plain string for simplicity
        "issuetype": {"name": issue_type},
        "status": {"name": status},
        "priority": {"name": priority},
        "labels": labels or [],
        "assignee": {"displayName": assignee},
        "reporter": {"displayName": reporter},
        "components": [],
        "fixVersions": [],
        "issuelinks": [],
        "subtasks": [],
    }
    if linked_keys:
        fields["issuelinks"] = [
            {"outwardIssue": {"key": k}} for k in linked_keys
        ]
    if custom_ac is not None:
        from config.jira_config import ACCEPTANCE_CRITERIA_FIELD_ID
        fields[ACCEPTANCE_CRITERIA_FIELD_ID] = custom_ac
    return {"key": ticket_id, "fields": fields}


def _make_comments_response(comments: list[tuple[str, str]]) -> dict[str, Any]:
    """Return a dict that mimics a Jira comments API response.

    Args:
        comments: List of (author_display_name, body_text) pairs.
    """
    return {
        "comments": [
            {
                "author": {"displayName": author},
                "body": body,
            }
            for author, body in comments
        ]
    }


# ── JiraClient unit tests ────────────────────────────────────────────────────

class TestJiraClientInit:
    """Test JiraClient initialisation and authentication header creation."""

    def _make_client(self, **kwargs: Any):
        from tools.jira_client import JiraClient
        defaults = {
            "base_url": "https://test.atlassian.net",
            "email": "user@example.com",
            "api_token": "token-abc",
        }
        defaults.update(kwargs)
        return JiraClient(**defaults)

    def test_creates_basic_auth_header(self):
        """JiraClient should encode credentials as Base64 Basic auth."""
        client = self._make_client(email="alice@example.com", api_token="secret")
        expected_creds = base64.b64encode(b"alice@example.com:secret").decode()
        assert client.headers["Authorization"] == f"Basic {expected_creds}"

    def test_auth_header_accept_and_content_type(self):
        """Headers should include Accept and Content-Type as JSON."""
        client = self._make_client()
        assert client.headers["Accept"] == "application/json"
        assert client.headers["Content-Type"] == "application/json"

    def test_base_url_trailing_slash_stripped(self):
        """Trailing slashes on base_url should be stripped."""
        client = self._make_client(base_url="https://test.atlassian.net///")
        assert not client.base_url.endswith("/")
        assert client.base_url == "https://test.atlassian.net"

    def test_raises_on_missing_base_url(self):
        """Empty base_url should raise ValueError with helpful message."""
        from tools.jira_client import JiraClient
        with pytest.raises(ValueError, match="JIRA_BASE_URL"):
            JiraClient(base_url="", email="a@b.com", api_token="tok")

    def test_raises_on_missing_email(self):
        """Empty email should raise ValueError with helpful message."""
        from tools.jira_client import JiraClient
        with pytest.raises(ValueError, match="JIRA_USER_EMAIL"):
            JiraClient(base_url="https://test.atlassian.net", email="", api_token="tok")

    def test_raises_on_missing_api_token(self):
        """Empty api_token should raise ValueError with helpful message."""
        from tools.jira_client import JiraClient
        with pytest.raises(ValueError, match="JIRA_API_TOKEN"):
            JiraClient(base_url="https://test.atlassian.net", email="a@b.com", api_token="")


# ── ADF conversion tests ──────────────────────────────────────────────────────

class TestJiraClientAdfToText:
    """Test Atlassian Document Format (ADF) conversion to plain text."""

    @pytest.fixture
    def client(self):
        from tools.jira_client import JiraClient
        return JiraClient(
            base_url="https://test.atlassian.net",
            email="u@example.com",
            api_token="tok",
        )

    def test_plain_text_passthrough(self, client):
        """A plain Python string should be returned unchanged."""
        assert client._extract_text("hello world") == "hello world"

    def test_none_returns_empty_string(self, client):
        """None content should return an empty string."""
        assert client._extract_text(None) == ""

    def test_adf_paragraph_extraction(self, client):
        """ADF paragraph nodes should be converted to plain text with newline."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello paragraph"}],
                }
            ],
        }
        result = client._extract_text(adf)
        assert "Hello paragraph" in result

    def test_adf_bullet_list(self, client):
        """ADF bulletList should be rendered with dash prefixes."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "item one"}],
                                }
                            ],
                        },
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "item two"}],
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        result = client._extract_text(adf)
        assert "- item one" in result
        assert "- item two" in result

    def test_adf_heading(self, client):
        """ADF heading nodes should be rendered with # prefixes matching level."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "My Heading"}],
                }
            ],
        }
        result = client._extract_text(adf)
        assert "## My Heading" in result

    def test_adf_hard_break(self, client):
        """ADF hardBreak nodes should produce a newline character."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "line one"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": "line two"},
                    ],
                }
            ],
        }
        result = client._extract_text(adf)
        assert "line one" in result
        assert "line two" in result
        assert "\n" in result

    def test_unknown_node_type_recurses(self, client):
        """Unknown ADF node types should fall back to recursing into children."""
        adf = {
            "type": "unknownNode",
            "content": [{"type": "text", "text": "deep text"}],
        }
        result = client._adf_to_text(adf)
        assert "deep text" in result


# ── fetch_ticket tests ────────────────────────────────────────────────────────

class TestFetchTicket:
    """Test ticket fetching with mocked HTTP responses."""

    @pytest.fixture
    def client(self):
        from tools.jira_client import JiraClient
        return JiraClient(
            base_url="https://test.atlassian.net",
            email="u@example.com",
            api_token="tok",
        )

    def _mock_get(self, issue_response: dict, comments_response: dict | None = None):
        """Return a side_effect callable for requests.get that serves issue then comments."""
        if comments_response is None:
            comments_response = {"comments": []}

        responses = [
            _mock_response(200, issue_response),
            _mock_response(200, comments_response),
        ]
        return responses

    def test_fetch_ticket_success(self, client):
        """fetch_ticket should return a structured dict on a successful 200 response."""
        api_response = _make_jira_api_response(
            ticket_id="SHIP-200",
            summary="Implement timeout",
            issue_type="Story",
            priority="High",
            labels=["buildrun", "timeout"],
        )
        comments_response = {"comments": []}

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, api_response),
                _mock_response(200, comments_response),
                _mock_response(200, []),   # remotelinks — no GitHub PRs linked
            ]
            result = client.fetch_ticket("SHIP-200")

        assert result["ticket_id"] == "SHIP-200"
        assert result["summary"] == "Implement timeout"
        assert result["issue_type"] == "Story"
        assert result["priority"] == "High"
        assert result["labels"] == ["buildrun", "timeout"]
        assert result["ticket_url"] == "https://test.atlassian.net/browse/SHIP-200"
        assert "github_pr_urls" in result
        assert result["github_pr_urls"] == []

    def test_fetch_ticket_raises_on_http_error(self, client):
        """fetch_ticket should propagate HTTPError on non-2xx responses."""
        error_response = _mock_response(404, {"errorMessages": ["Issue not found"]})
        error_response.raise_for_status.side_effect = requests.HTTPError("404")

        with patch("requests.get", return_value=error_response):
            with pytest.raises(requests.HTTPError):
                client.fetch_ticket("SHIP-MISSING")

    def test_fetch_ticket_includes_comments(self, client):
        """fetch_ticket should include comments fetched from the comments endpoint."""
        api_response = _make_jira_api_response(ticket_id="SHIP-300")
        comments_response = _make_comments_response([
            ("Alice Dev", "Started implementation."),
            ("Bob PM", "Please prioritize this."),
        ])

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, api_response),
                _mock_response(200, comments_response),
                _mock_response(200, []),   # remotelinks — no GitHub PRs linked
            ]
            result = client.fetch_ticket("SHIP-300")

        assert len(result["comments"]) == 2
        assert "[CUSTOMER_REDACTED]" in result["comments"][0]
        assert "Started implementation." in result["comments"][0]
        assert "[CUSTOMER_REDACTED]" in result["comments"][1]

    def test_fetch_ticket_comments_failure_is_graceful(self, client):
        """If the comments endpoint fails, fetch_ticket should still succeed."""
        api_response = _make_jira_api_response(ticket_id="SHIP-400")
        error_response = _mock_response(500, {})
        error_response.raise_for_status.side_effect = requests.HTTPError("500")

        with patch("requests.get") as mock_get:
            # First call (issue) succeeds; second call (comments) fails
            mock_get.side_effect = [
                _mock_response(200, api_response),
                error_response,
                _mock_response(200, []),   # remotelinks — no GitHub PRs linked
            ]
            result = client.fetch_ticket("SHIP-400")

        assert result["ticket_id"] == "SHIP-400"
        assert result["comments"] == []  # graceful empty list

    def test_fetch_ticket_extracts_linked_issues(self, client):
        """fetch_ticket should extract both inward and outward linked issue keys."""
        api_response = _make_jira_api_response(
            ticket_id="SHIP-500",
            linked_keys=["SHIP-100", "SHIP-101"],
        )

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, api_response),
                _mock_response(200, {"comments": []}),
                _mock_response(200, []),   # remotelinks — no GitHub PRs linked
            ]
            result = client.fetch_ticket("SHIP-500")

        assert "SHIP-100" in result["linked_issues"]
        assert "SHIP-101" in result["linked_issues"]

    def test_fetch_ticket_extracts_acceptance_criteria_from_custom_field(self, client):
        """Custom AC field (when present) should populate acceptance_criteria."""
        ac_text = "- Users can set timeout\n- Builds are cancelled on timeout"
        api_response = _make_jira_api_response(ticket_id="SHIP-600", custom_ac=ac_text)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, api_response),
                _mock_response(200, {"comments": []}),
                _mock_response(200, []),   # remotelinks — no GitHub PRs linked
            ]
            result = client.fetch_ticket("SHIP-600")

        assert len(result["acceptance_criteria"]) >= 1
        # At least one criterion should contain meaningful text
        joined = " ".join(result["acceptance_criteria"])
        assert "timeout" in joined.lower()

    def test_fetch_ticket_raises_value_error_on_non_json_content_type(self, client):
        """fetch_ticket should raise ValueError with a clear message when Jira returns HTML."""
        html_response = MagicMock()
        html_response.status_code = 200
        html_response.raise_for_status = MagicMock()
        html_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        html_response.text = "<html><body>Login required</body></html>"

        with patch("requests.get", return_value=html_response):
            with pytest.raises(ValueError, match="non-JSON response"):
                client.fetch_ticket("SHIP-HTML")

    def test_fetch_ticket_raises_value_error_on_json_decode_error(self, client):
        """fetch_ticket should raise ValueError with a clear message on malformed JSON."""
        bad_json_response = MagicMock()
        bad_json_response.status_code = 200
        bad_json_response.raise_for_status = MagicMock()
        bad_json_response.headers = {"Content-Type": "application/json"}
        bad_json_response.text = "<not-json>"
        bad_json_response.json.side_effect = json.JSONDecodeError("Expecting value", "<not-json>", 0)

        with patch("requests.get", return_value=bad_json_response):
            with pytest.raises(ValueError, match="invalid JSON"):
                client.fetch_ticket("SHIP-BADJSON")

    def test_fetch_ticket_extracts_github_pr_urls(self, client):
        """fetch_ticket returns GitHub PR URLs from remotelinks."""
        api_response = {
            "fields": {
                "summary": "Test ticket",
                "description": None,
                "issuetype": {"name": "Story"},
                "status": {"name": "Open"},
                "priority": {"name": "Major"},
                "labels": [],
                "assignee": None,
                "reporter": None,
                "components": [],
                "fixVersions": [],
                "issuelinks": [],
                "subtasks": [],
            }
        }
        comments_response = {"comments": []}
        remotelinks_response = [
            {
                "object": {
                    "url": "https://github.com/shipwright-io/build/pull/1234",
                    "title": "Add timeout support"
                }
            },
            {
                "object": {
                    "url": "https://github.com/shipwright-io/build/issues/999",  # issue, not PR — should be excluded
                    "title": "Related issue"
                }
            }
        ]
        remotelinks_mock = _mock_response(200, remotelinks_response)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, api_response),
                _mock_response(200, comments_response),
                remotelinks_mock,
            ]
            result = client.fetch_ticket("SHIP-123")
        assert result["github_pr_urls"] == ["https://github.com/shipwright-io/build/pull/1234"]


# ── map_to_agent_state tests ──────────────────────────────────────────────────

class TestMapToAgentState:
    """Test Jira data mapping to AgentState fields."""

    @pytest.fixture
    def client(self):
        from tools.jira_client import JiraClient
        return JiraClient(
            base_url="https://test.atlassian.net",
            email="u@example.com",
            api_token="tok",
        )

    def _make_ticket(self, **overrides) -> dict:
        base = {
            "ticket_id": "SHIP-1",
            "ticket_url": "https://test.atlassian.net/browse/SHIP-1",
            "summary": "My ticket summary",
            "description": "My ticket description",
            "issue_type": "Story",
            "status": "Open",
            "priority": "Major",
            "labels": ["label-a"],
            "assignee": "Dev",
            "reporter": "PM",
            "acceptance_criteria": ["AC1", "AC2"],
            "comments": [],
            "linked_issues": [],
            "components": [],
            "fix_versions": [],
        }
        base.update(overrides)
        return base

    def test_maps_story_to_feature(self, client):
        """Jira Story issue type should map to internal 'feature' type."""
        result = client.map_to_agent_state(self._make_ticket(issue_type="Story"))
        assert result["issue_type"] == "feature"

    def test_maps_bug_to_bug(self, client):
        """Jira Bug issue type should map to internal 'bug' type."""
        result = client.map_to_agent_state(self._make_ticket(issue_type="Bug"))
        assert result["issue_type"] == "bug"

    def test_maps_task_to_feature(self, client):
        """Jira Task issue type should map to internal 'feature' type."""
        result = client.map_to_agent_state(self._make_ticket(issue_type="Task"))
        assert result["issue_type"] == "feature"

    def test_maps_epic_to_feature(self, client):
        """Jira Epic should map to internal 'feature' type."""
        result = client.map_to_agent_state(self._make_ticket(issue_type="Epic"))
        assert result["issue_type"] == "feature"

    def test_unknown_issue_type_defaults_to_feature(self, client):
        """Unmapped Jira issue types should default to 'feature'."""
        result = client.map_to_agent_state(self._make_ticket(issue_type="SomeCustomType"))
        assert result["issue_type"] == "feature"

    def test_maps_summary_to_issue_title(self, client):
        """Jira summary field should become issue_title in AgentState."""
        result = client.map_to_agent_state(self._make_ticket(summary="My Feature Title"))
        assert result["issue_title"] == "My Feature Title"

    def test_maps_description_to_issue_description(self, client):
        """Jira description field should become issue_description in AgentState."""
        result = client.map_to_agent_state(self._make_ticket(description="Detailed desc"))
        assert result["issue_description"] == "Detailed desc"

    def test_maps_acceptance_criteria(self, client):
        """Acceptance criteria list should pass through to AgentState unchanged."""
        ac = ["AC-one", "AC-two", "AC-three"]
        result = client.map_to_agent_state(self._make_ticket(acceptance_criteria=ac))
        assert result["acceptance_criteria"] == ac

    def test_maps_all_jira_fields(self, client):
        """All 6 Jira-specific AgentState fields must be present."""
        ticket = self._make_ticket(
            ticket_id="SHIP-42",
            ticket_url="https://test.atlassian.net/browse/SHIP-42",
            priority="Critical",
            labels=["buildrun"],
            linked_issues=["SHIP-10"],
            comments=["Jane: done"],
        )
        result = client.map_to_agent_state(ticket)

        assert result["jira_ticket_id"] == "SHIP-42"
        assert result["jira_ticket_url"] == "https://test.atlassian.net/browse/SHIP-42"
        assert result["jira_priority"] == "Critical"
        assert result["jira_labels"] == ["buildrun"]
        assert result["jira_linked_issues"] == ["SHIP-10"]
        assert "Jane: done" in result["jira_comments_summary"]

    def test_comments_capped_at_ten(self, client):
        """jira_comments_summary should include at most 10 comments."""
        many_comments = [f"User{i}: comment {i}" for i in range(20)]
        ticket = self._make_ticket(comments=many_comments)
        result = client.map_to_agent_state(ticket)

        lines = [l for l in result["jira_comments_summary"].splitlines() if l.strip()]
        assert len(lines) <= 10

    def test_empty_comments_gives_empty_summary(self, client):
        """An empty comments list should produce an empty comments_summary string."""
        result = client.map_to_agent_state(self._make_ticket(comments=[]))
        assert result["jira_comments_summary"] == ""

    def test_issue_type_matching_is_case_insensitive(self, client):
        """Issue type lookup should be case-insensitive (e.g. 'BUG' -> 'bug')."""
        result = client.map_to_agent_state(self._make_ticket(issue_type="BUG"))
        assert result["issue_type"] == "bug"


# ── get_jira_client factory tests ─────────────────────────────────────────────

class TestGetJiraClient:
    """Test get_jira_client() factory function."""

    def test_returns_client_when_configured(self, monkeypatch):
        """All env vars present: should return a JiraClient instance."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_USER_EMAIL", "test@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

        from tools.jira_client import get_jira_client
        client = get_jira_client()
        assert client is not None

    def test_raises_when_missing_base_url(self, monkeypatch):
        """Missing JIRA_BASE_URL should raise ValueError mentioning the var name."""
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.setenv("JIRA_USER_EMAIL", "u@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "tok")

        from tools.jira_client import get_jira_client
        with pytest.raises(ValueError, match="JIRA_BASE_URL"):
            get_jira_client()

    def test_raises_when_missing_email(self, monkeypatch):
        """Missing JIRA_USER_EMAIL should raise ValueError mentioning the var name."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.delenv("JIRA_USER_EMAIL", raising=False)
        monkeypatch.setenv("JIRA_API_TOKEN", "tok")

        from tools.jira_client import get_jira_client
        with pytest.raises(ValueError, match="JIRA_USER_EMAIL"):
            get_jira_client()

    def test_raises_when_missing_token(self, monkeypatch):
        """Missing JIRA_API_TOKEN should raise ValueError mentioning the var name."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_USER_EMAIL", "u@example.com")
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        from tools.jira_client import get_jira_client
        with pytest.raises(ValueError, match="JIRA_API_TOKEN"):
            get_jira_client()

    def test_error_message_lists_all_missing_vars(self, monkeypatch):
        """When multiple vars are missing, the error should mention all of them."""
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER_EMAIL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        from tools.jira_client import get_jira_client
        with pytest.raises(ValueError) as exc_info:
            get_jira_client()

        message = str(exc_info.value)
        assert "JIRA_BASE_URL" in message
        assert "JIRA_USER_EMAIL" in message
        assert "JIRA_API_TOKEN" in message


# ── is_jira_configured helper tests ──────────────────────────────────────────

class TestIsJiraConfigured:
    """Test is_jira_configured() helper."""

    def test_returns_true_when_all_vars_set(self, monkeypatch):
        """All three env vars present: should return True."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_USER_EMAIL", "u@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "tok")

        from tools.jira_client import is_jira_configured
        assert is_jira_configured() is True

    def test_returns_false_when_missing_base_url(self, monkeypatch):
        """Missing JIRA_BASE_URL: should return False."""
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.setenv("JIRA_USER_EMAIL", "u@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "tok")

        from tools.jira_client import is_jira_configured
        assert is_jira_configured() is False

    def test_returns_false_when_missing_email(self, monkeypatch):
        """Missing JIRA_USER_EMAIL: should return False."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.delenv("JIRA_USER_EMAIL", raising=False)
        monkeypatch.setenv("JIRA_API_TOKEN", "tok")

        from tools.jira_client import is_jira_configured
        assert is_jira_configured() is False

    def test_returns_false_when_missing_token(self, monkeypatch):
        """Missing JIRA_API_TOKEN: should return False."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_USER_EMAIL", "u@example.com")
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        from tools.jira_client import is_jira_configured
        assert is_jira_configured() is False

    def test_returns_false_when_no_vars(self, monkeypatch):
        """No env vars set: should return False."""
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER_EMAIL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        from tools.jira_client import is_jira_configured
        assert is_jira_configured() is False


# ── MOCK_JIRA_TICKET tests ────────────────────────────────────────────────────

class TestMockJiraTicket:
    """Test the mock ticket used for dry-run mode."""

    def test_mock_ticket_has_required_fields(self):
        """MOCK_JIRA_TICKET must contain all fields expected by JiraClient consumers."""
        from config.mock_responses import MOCK_JIRA_TICKET

        required = [
            "ticket_id",
            "summary",
            "description",
            "issue_type",
            "priority",
            "labels",
            "acceptance_criteria",
            "comments",
            "linked_issues",
            "ticket_url",
        ]
        for field in required:
            assert field in MOCK_JIRA_TICKET, f"Missing required field: {field}"

    def test_mock_ticket_labels_is_list(self):
        """labels field should be a list."""
        from config.mock_responses import MOCK_JIRA_TICKET
        assert isinstance(MOCK_JIRA_TICKET["labels"], list)

    def test_mock_ticket_acceptance_criteria_is_list(self):
        """acceptance_criteria field should be a non-empty list."""
        from config.mock_responses import MOCK_JIRA_TICKET
        assert isinstance(MOCK_JIRA_TICKET["acceptance_criteria"], list)
        assert len(MOCK_JIRA_TICKET["acceptance_criteria"]) > 0

    def test_mock_ticket_ticket_url_is_valid_url(self):
        """ticket_url should look like an absolute URL."""
        from config.mock_responses import MOCK_JIRA_TICKET
        url = MOCK_JIRA_TICKET["ticket_url"]
        assert url.startswith("http"), f"Expected URL, got: {url}"
        assert MOCK_JIRA_TICKET["ticket_id"] in url

    def test_mock_ticket_maps_to_agent_state(self):
        """Mock ticket should map cleanly to AgentState fields without errors."""
        from config.mock_responses import MOCK_JIRA_TICKET
        from tools.jira_client import JiraClient

        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="u@example.com",
            api_token="tok",
        )
        result = client.map_to_agent_state(MOCK_JIRA_TICKET)

        # Primary fields must be populated
        assert result["issue_title"] == MOCK_JIRA_TICKET["summary"]
        assert result["issue_description"] == MOCK_JIRA_TICKET["description"]
        assert result["issue_type"] in ("feature", "bug", "refactor", "docs")

        # All 6 Jira-specific fields must be present
        for key in (
            "jira_ticket_id",
            "jira_ticket_url",
            "jira_priority",
            "jira_labels",
            "jira_linked_issues",
            "jira_comments_summary",
        ):
            assert key in result, f"Missing AgentState key: {key}"


# ── jira_config tests ─────────────────────────────────────────────────────────

class TestJiraConfig:
    """Test jira_config.py mappings and constants."""

    def test_issue_type_map_covers_common_types(self):
        """ISSUE_TYPE_MAP must cover the most common Jira issue types."""
        from config.jira_config import ISSUE_TYPE_MAP

        assert ISSUE_TYPE_MAP["bug"] == "bug"
        assert ISSUE_TYPE_MAP["story"] == "feature"
        assert ISSUE_TYPE_MAP["task"] == "feature"
        assert ISSUE_TYPE_MAP["epic"] == "feature"

    def test_issue_type_map_covers_defect_and_incident(self):
        """'defect' and 'incident' should both map to 'bug'."""
        from config.jira_config import ISSUE_TYPE_MAP

        assert ISSUE_TYPE_MAP["defect"] == "bug"
        assert ISSUE_TYPE_MAP["incident"] == "bug"

    def test_issue_type_map_covers_docs_types(self):
        """Documentation-related issue types should map to 'docs'."""
        from config.jira_config import ISSUE_TYPE_MAP

        assert ISSUE_TYPE_MAP["documentation"] == "docs"
        assert ISSUE_TYPE_MAP["docs"] == "docs"

    def test_issue_type_map_covers_refactor_types(self):
        """Refactoring-related issue types should map to 'refactor'."""
        from config.jira_config import ISSUE_TYPE_MAP

        assert ISSUE_TYPE_MAP["refactor"] == "refactor"
        assert ISSUE_TYPE_MAP["chore"] == "refactor"

    def test_acceptance_criteria_field_id_default(self):
        """ACCEPTANCE_CRITERIA_FIELD_ID should have a non-empty default value."""
        from config.jira_config import ACCEPTANCE_CRITERIA_FIELD_ID

        assert ACCEPTANCE_CRITERIA_FIELD_ID  # truthy (not empty)
        assert isinstance(ACCEPTANCE_CRITERIA_FIELD_ID, str)

    def test_acceptance_criteria_field_id_env_override(self, monkeypatch):
        """JIRA_AC_FIELD_ID env var should override ACCEPTANCE_CRITERIA_FIELD_ID."""
        monkeypatch.setenv("JIRA_AC_FIELD_ID", "customfield_99999")
        import config.jira_config as jc
        importlib.reload(jc)
        assert jc.ACCEPTANCE_CRITERIA_FIELD_ID == "customfield_99999"
        # Reload with no override to restore default for other tests
        monkeypatch.delenv("JIRA_AC_FIELD_ID", raising=False)
        importlib.reload(jc)

    def test_priority_badges_covers_common_priorities(self):
        """PRIORITY_BADGES should include commonly used Jira priorities."""
        from config.jira_config import PRIORITY_BADGES

        for priority in ("blocker", "critical", "major", "minor", "trivial"):
            assert priority in PRIORITY_BADGES

    def test_default_project_key_is_non_empty(self):
        """DEFAULT_PROJECT_KEY should resolve to a non-empty string."""
        from config.jira_config import DEFAULT_PROJECT_KEY

        assert DEFAULT_PROJECT_KEY
        assert isinstance(DEFAULT_PROJECT_KEY, str)


# ── fetch_ticket dry-run (mcp.jira_stub) tests ───────────────────────────────

class TestFetchTicketDryRun:
    """Test dry-run mode for mcp.jira_stub.fetch_ticket."""

    def test_dry_run_returns_mock_ticket(self, monkeypatch):
        """With DRY_RUN=true the stub should return a ticket without HTTP calls."""
        monkeypatch.setenv("DRY_RUN", "true")
        from mcp import jira_stub

        with patch("requests.get") as mock_get:
            result = jira_stub.fetch_ticket("SHIP-999")
            mock_get.assert_not_called()  # no real HTTP request

        assert result is not None
        assert "ticket_id" in result

    def test_dry_run_patches_ticket_id(self, monkeypatch):
        """The requested ticket ID should replace the mock's default ID."""
        monkeypatch.setenv("DRY_RUN", "true")
        from mcp.jira_stub import fetch_ticket

        result = fetch_ticket("CUSTOM-456")
        assert result["ticket_id"] == "CUSTOM-456"

    def test_dry_run_patches_ticket_url(self, monkeypatch):
        """The ticket URL should contain the requested ticket ID."""
        monkeypatch.setenv("DRY_RUN", "true")
        from mcp.jira_stub import fetch_ticket

        result = fetch_ticket("CUSTOM-789")
        assert "CUSTOM-789" in result["ticket_url"]

    def test_non_dry_run_attempts_real_client(self, monkeypatch):
        """Without DRY_RUN, the stub should attempt to use the real Jira client."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_USER_EMAIL", "u@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "tok")

        from mcp import jira_stub

        with patch("tools.jira_client.JiraClient.fetch_ticket") as mock_fetch:
            mock_fetch.return_value = {"ticket_id": "REAL-1", "summary": "real ticket"}
            result = jira_stub.fetch_ticket("REAL-1")

        assert result["ticket_id"] == "REAL-1"

    def test_dry_run_does_not_mutate_original_mock(self, monkeypatch):
        """Calling fetch_ticket in dry-run mode must not mutate MOCK_JIRA_TICKET."""
        from config.mock_responses import MOCK_JIRA_TICKET

        original_id = MOCK_JIRA_TICKET["ticket_id"]
        monkeypatch.setenv("DRY_RUN", "true")

        from mcp.jira_stub import fetch_ticket
        fetch_ticket("DIFFERENT-001")

        # The original mock should be untouched
        assert MOCK_JIRA_TICKET["ticket_id"] == original_id


# ── update_ticket tests ───────────────────────────────────────────────────────

class TestUpdateTicket:
    """Test JiraClient.update_ticket() posting ADF comments."""

    @pytest.fixture
    def client(self):
        from tools.jira_client import JiraClient
        return JiraClient(
            base_url="https://test.atlassian.net",
            email="u@example.com",
            api_token="tok",
        )

    def test_update_ticket_returns_true_on_success(self, client):
        """update_ticket should return True when the POST succeeds."""
        mock_resp = _mock_response(201, {"id": "comment-001"})

        with patch("requests.post", return_value=mock_resp):
            result = client.update_ticket("SHIP-1", "Workflow completed successfully.")

        assert result is True

    def test_update_ticket_returns_false_on_error(self, client):
        """update_ticket should return False (not raise) when POST fails."""
        mock_resp = _mock_response(403, {})
        mock_resp.raise_for_status.side_effect = requests.HTTPError("403")

        with patch("requests.post", return_value=mock_resp):
            result = client.update_ticket("SHIP-2", "Some comment.")

        assert result is False

    def test_update_ticket_posts_adf_body(self, client):
        """update_ticket should send an ADF-formatted body to the comments endpoint."""
        mock_resp = _mock_response(201, {})

        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_resp
            client.update_ticket("SHIP-3", "Hello Jira!")

        call_kwargs = mock_post.call_args.kwargs
        body = call_kwargs["json"]["body"]
        assert body["type"] == "doc"
        # The text should be embedded inside the ADF structure
        paragraph = body["content"][0]
        assert paragraph["type"] == "paragraph"
        assert paragraph["content"][0]["text"] == "Hello Jira!"


# ── Internal private helpers ──────────────────────────────────────────────────

class TestExtractLinkedIssues:
    """Test _extract_linked_issues for various link structures."""

    @pytest.fixture
    def client(self):
        from tools.jira_client import JiraClient
        return JiraClient(
            base_url="https://test.atlassian.net",
            email="u@example.com",
            api_token="tok",
        )

    def test_extracts_inward_links(self, client):
        fields = {"issuelinks": [{"inwardIssue": {"key": "SHIP-10"}}], "subtasks": []}
        assert "SHIP-10" in client._extract_linked_issues(fields)

    def test_extracts_outward_links(self, client):
        fields = {"issuelinks": [{"outwardIssue": {"key": "SHIP-20"}}], "subtasks": []}
        assert "SHIP-20" in client._extract_linked_issues(fields)

    def test_extracts_subtasks(self, client):
        fields = {"issuelinks": [], "subtasks": [{"key": "SHIP-30"}]}
        assert "SHIP-30" in client._extract_linked_issues(fields)

    def test_returns_empty_list_when_no_links(self, client):
        fields = {"issuelinks": [], "subtasks": []}
        assert client._extract_linked_issues(fields) == []

    def test_filters_empty_keys(self, client):
        fields = {"issuelinks": [], "subtasks": [{"key": ""}]}
        assert client._extract_linked_issues(fields) == []


# ── Private utility ───────────────────────────────────────────────────────────

def _mock_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock requests.Response with a given status code and JSON body."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = body
    mock.raise_for_status = MagicMock()  # no-op by default (success)
    mock.headers = {"Content-Type": "application/json"}
    return mock


# ── Main entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
