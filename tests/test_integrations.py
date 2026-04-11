"""Tests for the integrations layer.

Each test is independent. No real API calls are made.
DRY_RUN env-var behaviour is controlled via monkeypatch / patch.
"""

from unittest.mock import MagicMock, patch

import pytest


# -- Jira integration ---------------------------------------------------------


class TestFetchJiraTicket:
    """Tests for integrations.jira.fetch_jira_ticket."""

    def test_dry_run_returns_mock_data(self, monkeypatch):
        """With DRY_RUN=true, returns mapped mock Jira data without API calls."""
        monkeypatch.setenv("DRY_RUN", "true")

        fixed_mapped = {
            "issue_title": "Mocked title",
            "jira_ticket_id": "MOCK-1",
            "issue_description": "desc",
            "issue_type": "feature",
        }

        with patch("tools.jira_client.map_ticket_to_state", return_value=fixed_mapped):
            from integrations.jira import fetch_jira_ticket

            result = fetch_jira_ticket("MOCK-1")

        assert "issue_title" in result
        assert "jira_ticket_id" in result

    def test_dry_run_patches_ticket_id(self, monkeypatch):
        """The ticket_id is reflected in mock data sent to map_ticket_to_state."""
        monkeypatch.setenv("DRY_RUN", "true")

        captured_args: dict = {}

        def capture_map(ticket_data):
            captured_args["ticket_data"] = ticket_data
            return {
                "issue_title": "Captured",
                "jira_ticket_id": ticket_data.get("ticket_id", ""),
            }

        with patch("tools.jira_client.map_ticket_to_state", side_effect=capture_map):
            from integrations.jira import fetch_jira_ticket

            fetch_jira_ticket("BUILD-99")

        assert captured_args["ticket_data"]["ticket_id"] == "BUILD-99"

    def test_live_calls_fetch_and_map(self, monkeypatch):
        """Without DRY_RUN, calls fetch_ticket then map_ticket_to_state."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        fake_raw = {"ticket_id": "BUILD-42", "summary": "Raw ticket"}
        fake_mapped = {"issue_title": "Raw ticket", "jira_ticket_id": "BUILD-42"}

        with patch("mcp.jira_stub.fetch_ticket", return_value=fake_raw) as mock_fetch:
            with patch(
                "tools.jira_client.map_ticket_to_state", return_value=fake_mapped
            ) as mock_map:
                from integrations.jira import fetch_jira_ticket

                result = fetch_jira_ticket("BUILD-42")

        mock_fetch.assert_called_once_with("BUILD-42")
        mock_map.assert_called_once_with(fake_raw)
        assert result == fake_mapped


class TestUpdateJiraTicket:
    """Tests for integrations.jira.update_jira_ticket."""

    def test_dry_run_returns_success(self, monkeypatch):
        """With DRY_RUN=true, returns success without calling Jira client."""
        monkeypatch.setenv("DRY_RUN", "true")

        with patch("tools.jira_client.get_jira_client") as mock_factory:
            from integrations.jira import update_jira_ticket

            result = update_jira_ticket("BUILD-1", "test comment")

        mock_factory.assert_not_called()
        assert result["success"] is True
        assert result["dry_run"] is True

    def test_live_calls_client(self, monkeypatch):
        """Without DRY_RUN, calls client.update_ticket and returns result."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        mock_client = MagicMock()
        mock_client.update_ticket.return_value = True

        with patch(
            "tools.jira_client.get_jira_client", return_value=mock_client
        ) as mock_factory:
            from integrations.jira import update_jira_ticket

            result = update_jira_ticket("BUILD-1", "test comment")

        mock_factory.assert_called_once()
        mock_client.update_ticket.assert_called_once_with("BUILD-1", "test comment")
        assert result == {"success": True}


# -- GitHub integration --------------------------------------------------------


class TestFetchGitHubPRs:
    """Tests for integrations.github.fetch_github_prs."""

    def test_dry_run_returns_empty(self, monkeypatch):
        """With DRY_RUN=true, returns empty pr_data without calling any client."""
        monkeypatch.setenv("DRY_RUN", "true")

        with patch("tools.github_client.is_github_configured") as mock_conf:
            with patch("tools.github_client.get_github_client") as mock_factory:
                from integrations.github import fetch_github_prs

                result = fetch_github_prs(
                    ["https://github.com/org/repo/pull/99"]
                )

        mock_conf.assert_not_called()
        mock_factory.assert_not_called()
        assert result == {"pr_data": []}

    def test_empty_urls_returns_empty(self, monkeypatch):
        """Returns empty pr_data when pr_urls list is empty."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        from integrations.github import fetch_github_prs

        result = fetch_github_prs([])
        assert result == {"pr_data": []}

    def test_not_configured_returns_empty(self, monkeypatch):
        """Returns empty pr_data when GitHub is not configured."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("tools.github_client.is_github_configured", return_value=False):
            with patch("tools.github_client.get_github_client") as mock_factory:
                from integrations.github import fetch_github_prs

                result = fetch_github_prs(
                    ["https://github.com/org/repo/pull/1"]
                )

        mock_factory.assert_not_called()
        assert result == {"pr_data": []}

    def test_live_fetches_prs(self, monkeypatch):
        """Fetches PR data when GitHub is configured and urls are provided."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        pr_list = [{"pr_number": 1, "title": "Fix bug"}]
        mock_client = MagicMock()
        mock_client.fetch_prs_from_urls.return_value = pr_list

        with patch("tools.github_client.is_github_configured", return_value=True):
            with patch(
                "tools.github_client.get_github_client", return_value=mock_client
            ):
                from integrations.github import fetch_github_prs

                result = fetch_github_prs(
                    ["https://github.com/org/repo/pull/1"]
                )

        mock_client.fetch_prs_from_urls.assert_called_once_with(
            ["https://github.com/org/repo/pull/1"]
        )
        assert result == {"pr_data": pr_list}


# -- Main entrypoint ----------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
