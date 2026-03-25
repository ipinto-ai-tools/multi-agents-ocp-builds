"""Unit tests for the PII redaction layer.

Covers:
- tools/pii_redactor.py  (_redact_text, redact_pii, is_redaction_enabled)
- Integration with JiraClient.fetch_ticket()
- Integration with GitHubClient.fetch_pr()

No real API calls are made.  All HTTP interactions are mocked via
unittest.mock.patch.  Environment variable overrides are applied with
pytest's monkeypatch fixture so they are automatically restored after
each test.
"""

import importlib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, body: Any) -> MagicMock:
    """Build a mock requests.Response with a given status code and JSON body."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = body
    mock.raise_for_status = MagicMock()  # no-op by default (success path)
    mock.headers = {"Content-Type": "application/json"}
    return mock


def _reset_redaction_warned_flag():
    """Reset the module-level _redaction_disabled_warned flag to False.

    The flag is intentionally module-global so the "disabled" warning is only
    emitted once per process.  Between tests we must reset it so tests that
    disable redaction do not interfere with each other.
    """
    import tools.pii_redactor as _m
    _m._redaction_disabled_warned = False


@pytest.fixture(autouse=True)
def _reset_warned(monkeypatch):
    """Auto-use fixture: reset the one-shot warning flag before every test."""
    _reset_redaction_warned_flag()
    yield
    _reset_redaction_warned_flag()


# ---------------------------------------------------------------------------
# TestRedactText — unit tests for the internal _redact_text helper
# ---------------------------------------------------------------------------

class TestRedactText:
    """Tests for the regex-based _redact_text() internal function."""

    @pytest.fixture
    def redact_text(self):
        from tools.pii_redactor import _redact_text
        return _redact_text

    def test_ipv4_redacted(self, redact_text):
        """IPv4 address should be replaced with [IP_REDACTED]."""
        result, counts = redact_text("Server at 192.168.1.100", "test")
        assert "[IP_REDACTED]" in result
        assert "192.168.1.100" not in result
        assert counts["ip"] == 1

    def test_ipv6_redacted(self, redact_text):
        """Full IPv6 address should be replaced with [IP_REDACTED]."""
        ipv6 = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        result, counts = redact_text(f"Host: {ipv6}", "test")
        assert "[IP_REDACTED]" in result
        assert ipv6 not in result
        assert counts["ip"] == 1

    def test_email_redacted(self, redact_text):
        """Internal email address should be replaced with [EMAIL_REDACTED]."""
        result, counts = redact_text("Contact john@internal.corp for help", "test")
        assert "[EMAIL_REDACTED]" in result
        assert "john@internal.corp" not in result
        assert counts["email"] == 1

    def test_email_allowlisted_preserved(self, redact_text):
        """Email with an allowlisted domain (redhat.com) must NOT be redacted."""
        result, counts = redact_text("admin@redhat.com is the contact", "test")
        assert "admin@redhat.com" in result
        assert "[EMAIL_REDACTED]" not in result
        assert counts["email"] == 0

    def test_phone_redacted(self, redact_text):
        """Phone number in international format should be replaced with [PHONE_REDACTED]."""
        result, counts = redact_text("Call +1-555-123-4567 for support", "test")
        assert "[PHONE_REDACTED]" in result
        assert "555-123-4567" not in result
        assert counts["phone"] == 1

    def test_internal_hostname_redacted(self, redact_text):
        """Internal hostname (*.internal TLD) should be replaced with [HOSTNAME_REDACTED]."""
        result, counts = redact_text("Database at prod-db-01.internal is down", "test")
        assert "[HOSTNAME_REDACTED]" in result
        assert "prod-db-01.internal" not in result
        assert counts["hostname"] == 1

    def test_public_hostname_preserved(self, redact_text):
        """Public allowlisted hostname (github.com) must NOT be redacted."""
        result, counts = redact_text("See github.com for details", "test")
        assert "github.com" in result
        assert "[HOSTNAME_REDACTED]" not in result
        assert counts["hostname"] == 0

    def test_multiple_pii_in_same_string(self, redact_text):
        """A string containing both an IP and an email should have both redacted."""
        text = "Server 10.0.0.5 contacted by user@secret.org"
        result, counts = redact_text(text, "test")
        assert "[IP_REDACTED]" in result
        assert "[EMAIL_REDACTED]" in result
        assert "10.0.0.5" not in result
        assert "user@secret.org" not in result
        assert counts["ip"] == 1
        assert counts["email"] == 1

    def test_clean_text_unchanged(self, redact_text):
        """Text with no PII should be returned exactly as received."""
        clean = "This is a perfectly clean string with no sensitive data."
        result, counts = redact_text(clean, "test")
        assert result == clean
        assert sum(counts.values()) == 0

    def test_empty_string(self, redact_text):
        """An empty string input should produce an empty string output."""
        result, counts = redact_text("", "test")
        assert result == ""
        assert sum(counts.values()) == 0

    def test_allowlist_bypass_hostname_still_redacted(self):
        """A hostname containing an allowlist domain as substring must still be redacted."""
        from tools.pii_redactor import _redact_text
        text = "Connect to evil-github.com.corp for access"
        result, _ = _redact_text(text, "test")
        assert "[HOSTNAME_REDACTED]" in result
        assert "evil-github.com.corp" not in result


# ---------------------------------------------------------------------------
# TestRedactPiiPersonalNames — personal name field replacement
# ---------------------------------------------------------------------------

class TestRedactPiiPersonalNames:
    """Tests for personal name field redaction inside redact_pii()."""

    @pytest.fixture
    def redact_pii(self):
        from tools.pii_redactor import redact_pii
        return redact_pii

    def test_reporter_replaced(self, redact_pii):
        """reporter field with a non-empty value must become [CUSTOMER_REDACTED]."""
        result = redact_pii({"reporter": "Jane Smith"}, source="test")
        assert result["reporter"] == "[CUSTOMER_REDACTED]"

    def test_assignee_replaced(self, redact_pii):
        """assignee field with a non-empty value must become [CUSTOMER_REDACTED]."""
        result = redact_pii({"assignee": "John Doe"}, source="test")
        assert result["assignee"] == "[CUSTOMER_REDACTED]"

    def test_author_replaced(self, redact_pii):
        """author field with a non-empty value must become [CUSTOMER_REDACTED]."""
        result = redact_pii({"author": "octocat"}, source="test")
        assert result["author"] == "[CUSTOMER_REDACTED]"

    def test_reviewers_replaced(self, redact_pii):
        """Each element in reviewers list must be replaced with [CUSTOMER_REDACTED]."""
        result = redact_pii({"reviewers": ["alice", "bob", "carol"]}, source="test")
        assert result["reviewers"] == ["[CUSTOMER_REDACTED]"] * 3

    def test_empty_reporter_not_replaced(self, redact_pii):
        """Empty string reporter must be left as-is (falsy guard in redact_pii)."""
        result = redact_pii({"reporter": ""}, source="test")
        assert result["reporter"] == ""

    def test_none_reporter_not_replaced(self, redact_pii):
        """None reporter must be left as None (falsy guard in redact_pii)."""
        result = redact_pii({"reporter": None}, source="test")
        assert result["reporter"] is None


# ---------------------------------------------------------------------------
# TestRedactPiiTextFields — free-text field scanning
# ---------------------------------------------------------------------------

class TestRedactPiiTextFields:
    """Tests for free-text field PII scanning inside redact_pii()."""

    @pytest.fixture
    def redact_pii(self):
        from tools.pii_redactor import redact_pii
        return redact_pii

    def test_summary_redacted(self, redact_pii):
        """IP address inside the summary field must be redacted."""
        result = redact_pii({"summary": "Crash on 10.20.30.40 endpoint"}, source="test")
        assert "[IP_REDACTED]" in result["summary"]
        assert "10.20.30.40" not in result["summary"]

    def test_description_redacted(self, redact_pii):
        """Internal hostname inside the description field must be redacted."""
        result = redact_pii(
            {"description": "Connect to db.corp to reproduce the issue"},
            source="test",
        )
        assert "[HOSTNAME_REDACTED]" in result["description"]
        assert "db.corp" not in result["description"]

    def test_title_redacted(self, redact_pii):
        """Email address inside the title field must be redacted."""
        result = redact_pii(
            {"title": "PR from dev@secret.io filed today"},
            source="test",
        )
        assert "[EMAIL_REDACTED]" in result["title"]
        assert "dev@secret.io" not in result["title"]

    def test_body_redacted(self, redact_pii):
        """Phone number inside the body field must be redacted."""
        result = redact_pii(
            {"body": "Call 555-867-5309 to confirm the deploy"},
            source="test",
        )
        assert "[PHONE_REDACTED]" in result["body"]
        assert "867-5309" not in result["body"]

    def test_comments_list_redacted(self, redact_pii):
        """Each comment string in the comments list must be individually scanned."""
        comments = [
            "Deployed from 172.16.0.1 successfully",
            "No issues found",
            "Rollback initiated by ops@company.net",
        ]
        result = redact_pii({"comments": comments}, source="test")
        assert "[IP_REDACTED]" in result["comments"][0]
        assert "172.16.0.1" not in result["comments"][0]
        assert result["comments"][1] == "No issues found"
        assert "[EMAIL_REDACTED]" in result["comments"][2]
        assert "ops@company.net" not in result["comments"][2]

    def test_acceptance_criteria_list_redacted(self, redact_pii):
        """Each acceptance criterion string must be individually scanned."""
        ac = [
            "System must not log 192.0.2.50 in output",
            "Approval required from admin@internal.org",
        ]
        result = redact_pii({"acceptance_criteria": ac}, source="test")
        assert "[IP_REDACTED]" in result["acceptance_criteria"][0]
        assert "[EMAIL_REDACTED]" in result["acceptance_criteria"][1]


# ---------------------------------------------------------------------------
# TestRedactPiiPreservesOtherFields — pass-through fields
# ---------------------------------------------------------------------------

class TestRedactPiiPreservesOtherFields:
    """Fields not in the redaction categories must be copied through unchanged."""

    @pytest.fixture
    def redact_pii(self):
        from tools.pii_redactor import redact_pii
        return redact_pii

    def test_ticket_id_preserved(self, redact_pii):
        """ticket_id must be passed through without modification."""
        result = redact_pii({"ticket_id": "SHIP-123"}, source="test")
        assert result["ticket_id"] == "SHIP-123"

    def test_ticket_url_preserved(self, redact_pii):
        """ticket_url containing github.com must pass through unchanged."""
        url = "https://jira.atlassian.net/browse/SHIP-123"
        result = redact_pii({"ticket_url": url}, source="test")
        assert result["ticket_url"] == url

    def test_github_pr_urls_preserved(self, redact_pii):
        """github_pr_urls list must be passed through unchanged."""
        urls = [
            "https://github.com/openshift/builds/pull/42",
            "https://github.com/shipwright-io/build/pull/99",
        ]
        result = redact_pii({"github_pr_urls": urls}, source="test")
        assert result["github_pr_urls"] == urls

    def test_labels_preserved(self, redact_pii):
        """labels list must be passed through unchanged."""
        labels = ["buildrun", "timeout", "high-priority"]
        result = redact_pii({"labels": labels}, source="test")
        assert result["labels"] == labels

    def test_status_preserved(self, redact_pii):
        """status string must be passed through unchanged."""
        result = redact_pii({"status": "In Progress"}, source="test")
        assert result["status"] == "In Progress"

    def test_pr_url_preserved(self, redact_pii):
        """pr_url (a pass-through field) must be copied unchanged."""
        url = "https://github.com/openshift/builds/pull/1"
        result = redact_pii({"pr_url": url}, source="test")
        assert result["pr_url"] == url


# ---------------------------------------------------------------------------
# TestRedactPiiDisabled — PII_REDACTION_ENABLED env var behaviour
# ---------------------------------------------------------------------------

class TestRedactPiiDisabled:
    """Tests for the PII_REDACTION_ENABLED kill-switch."""

    def test_disabled_returns_original(self, monkeypatch):
        """When PII_REDACTION_ENABLED=false, redact_pii must return the original dict."""
        monkeypatch.setenv("PII_REDACTION_ENABLED", "false")
        from tools.pii_redactor import redact_pii

        original = {
            "reporter": "John Doe",
            "summary": "Issue from 192.168.99.1",
            "status": "Open",
        }
        result = redact_pii(original, source="test")
        # Identity check: the exact same object must be returned
        assert result is original

    def test_enabled_by_default(self, monkeypatch):
        """When PII_REDACTION_ENABLED is not set, redaction should be active."""
        monkeypatch.delenv("PII_REDACTION_ENABLED", raising=False)
        from tools.pii_redactor import redact_pii

        data = {
            "reporter": "Jane Doe",
            "summary": "Server at 10.0.0.1 crashed",
        }
        result = redact_pii(data, source="test")
        assert result["reporter"] == "[CUSTOMER_REDACTED]"
        assert "[IP_REDACTED]" in result["summary"]

    def test_disabled_case_insensitive(self, monkeypatch):
        """PII_REDACTION_ENABLED=FALSE (uppercase) should also disable redaction."""
        monkeypatch.setenv("PII_REDACTION_ENABLED", "FALSE")
        from tools.pii_redactor import redact_pii

        original = {"reporter": "Someone", "summary": "test"}
        result = redact_pii(original, source="test")
        assert result is original

    def test_is_redaction_enabled_true_by_default(self, monkeypatch):
        """is_redaction_enabled() returns True when env var is absent."""
        monkeypatch.delenv("PII_REDACTION_ENABLED", raising=False)
        from tools.pii_redactor import is_redaction_enabled
        assert is_redaction_enabled() is True

    def test_is_redaction_enabled_false_when_set(self, monkeypatch):
        """is_redaction_enabled() returns False when PII_REDACTION_ENABLED=false."""
        monkeypatch.setenv("PII_REDACTION_ENABLED", "false")
        from tools.pii_redactor import is_redaction_enabled
        assert is_redaction_enabled() is False


# ---------------------------------------------------------------------------
# TestJiraClientIntegration — redaction applied inside fetch_ticket()
# ---------------------------------------------------------------------------

class TestJiraClientIntegration:
    """Integration tests verifying redact_pii is applied by JiraClient.fetch_ticket()."""

    @pytest.fixture
    def client(self):
        from tools.jira_client import JiraClient
        return JiraClient(
            base_url="https://test.atlassian.net",
            email="service@example.com",
            api_token="secret-token",
        )

    def _make_issue_response(
        self,
        *,
        reporter: str = "Real Person",
        summary: str = "Test summary",
        description: str = "Test description",
    ) -> dict[str, Any]:
        """Build a minimal Jira REST API issue response dict."""
        return {
            "key": "SHIP-1",
            "fields": {
                "summary": summary,
                "description": description,
                "issuetype": {"name": "Story"},
                "status": {"name": "Open"},
                "priority": {"name": "Major"},
                "labels": [],
                "assignee": None,
                "reporter": {"displayName": reporter},
                "components": [],
                "fixVersions": [],
                "issuelinks": [],
                "subtasks": [],
            },
        }

    def test_fetch_ticket_reporter_redacted(self, client):
        """fetch_ticket() must replace the reporter name with [CUSTOMER_REDACTED]."""
        issue = self._make_issue_response(reporter="Alice Johnson")

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, issue),
                _mock_response(200, {"comments": []}),
                _mock_response(200, []),   # remotelinks
            ]
            result = client.fetch_ticket("SHIP-1")

        assert result["reporter"] == "[CUSTOMER_REDACTED]"

    def test_fetch_ticket_ip_in_description_redacted(self, client):
        """fetch_ticket() must redact IP addresses found in the description field."""
        description = "Connect to 10.5.5.100 to reproduce the crash"
        issue = self._make_issue_response(description=description)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, issue),
                _mock_response(200, {"comments": []}),
                _mock_response(200, []),   # remotelinks
            ]
            result = client.fetch_ticket("SHIP-1")

        assert "[IP_REDACTED]" in result["description"]
        assert "10.5.5.100" not in result["description"]

    def test_fetch_ticket_email_in_summary_redacted(self, client):
        """fetch_ticket() must redact email addresses found in the summary field."""
        summary = "Bug reported by bob@internal.corp on prod"
        issue = self._make_issue_response(summary=summary)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, issue),
                _mock_response(200, {"comments": []}),
                _mock_response(200, []),   # remotelinks
            ]
            result = client.fetch_ticket("SHIP-1")

        assert "[EMAIL_REDACTED]" in result["summary"]
        assert "bob@internal.corp" not in result["summary"]

    def test_fetch_ticket_ticket_id_preserved(self, client):
        """fetch_ticket() must not alter the ticket_id pass-through field."""
        issue = self._make_issue_response()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, issue),
                _mock_response(200, {"comments": []}),
                _mock_response(200, []),   # remotelinks
            ]
            result = client.fetch_ticket("SHIP-42")

        assert result["ticket_id"] == "SHIP-42"


# ---------------------------------------------------------------------------
# TestGitHubClientIntegration — redaction applied inside fetch_pr()
# ---------------------------------------------------------------------------

class TestGitHubClientIntegration:
    """Integration tests verifying redact_pii is applied by GitHubClient.fetch_pr()."""

    @pytest.fixture
    def client(self):
        from tools.github_client import GitHubClient
        return GitHubClient(token="ghp_fake_token_for_testing")

    def _make_pr_response(
        self,
        *,
        author_login: str = "octocat",
        title: str = "Fix timeout issue",
        body: str = "This PR resolves the issue.",
        state: str = "open",
        merged: bool = False,
    ) -> dict[str, Any]:
        """Build a minimal GitHub REST API pull request response dict."""
        return {
            "number": 1,
            "html_url": "https://github.com/openshift/builds/pull/1",
            "title": title,
            "body": body,
            "state": state,
            "merged": merged,
            "merged_at": None,
            "user": {"login": author_login},
            "requested_reviewers": [],
            "labels": [],
            "base": {
                "ref": "main",
                "repo": {"full_name": "openshift/builds"},
            },
            "head": {"ref": "feat/timeout"},
            "changed_files": 3,
            "additions": 50,
            "deletions": 10,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }

    def test_fetch_pr_author_redacted(self, client):
        """fetch_pr() must replace the PR author login with [CUSTOMER_REDACTED]."""
        pr = self._make_pr_response(author_login="real-developer-handle")

        with patch("requests.get", return_value=_mock_response(200, pr)):
            result = client.fetch_pr("openshift", "builds", 1)

        assert result["author"] == "[CUSTOMER_REDACTED]"

    def test_fetch_pr_body_email_redacted(self, client):
        """fetch_pr() must redact email addresses found in the PR body."""
        body = "Reviewed by qa@internal.corp before merging. LGTM."
        pr = self._make_pr_response(body=body)

        with patch("requests.get", return_value=_mock_response(200, pr)):
            result = client.fetch_pr("openshift", "builds", 1)

        assert "[EMAIL_REDACTED]" in result["body"]
        assert "qa@internal.corp" not in result["body"]

    def test_fetch_pr_title_ip_redacted(self, client):
        """fetch_pr() must redact IP addresses found in the PR title."""
        title = "Fix crash when connecting to 192.168.0.255"
        pr = self._make_pr_response(title=title)

        with patch("requests.get", return_value=_mock_response(200, pr)):
            result = client.fetch_pr("openshift", "builds", 1)

        assert "[IP_REDACTED]" in result["title"]
        assert "192.168.0.255" not in result["title"]

    def test_fetch_pr_pr_url_preserved(self, client):
        """fetch_pr() must not alter the pr_url pass-through field."""
        pr = self._make_pr_response()

        with patch("requests.get", return_value=_mock_response(200, pr)):
            result = client.fetch_pr("openshift", "builds", 1)

        assert result["pr_url"] == "https://github.com/openshift/builds/pull/1"

    def test_fetch_pr_labels_preserved(self, client):
        """fetch_pr() must not alter the labels pass-through field."""
        pr = self._make_pr_response()
        pr["labels"] = [{"name": "bug"}, {"name": "needs-review"}]

        with patch("requests.get", return_value=_mock_response(200, pr)):
            result = client.fetch_pr("openshift", "builds", 1)

        assert result["labels"] == ["bug", "needs-review"]


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
