"""Tests for the skills layer.

Each test class is independent. No real API calls are made.
DRY_RUN env-var behaviour is controlled via monkeypatch / patch.
"""

from unittest.mock import MagicMock, patch

import pytest


# ── TestSkillBase ─────────────────────────────────────────────────────────────


class TestSkillBase:
    """Tests for the abstract Skill base class behaviour."""

    def _make_concrete_skill(self, execute_return: dict | None = None):
        """Return a minimal concrete Skill subclass for testing."""
        from skills.base import Skill

        class _ConcreteSkill(Skill):
            name = "concrete_skill"
            description = "A test skill."
            input_schema = {}
            output_schema = {}

            def _execute(self, input: dict) -> dict:
                return execute_return or {"executed": True}

        return _ConcreteSkill()

    def test_dry_run_calls_mock_response(self, monkeypatch):
        """With DRY_RUN=true, run() returns mock response and never calls _execute()."""
        monkeypatch.setenv("DRY_RUN", "true")
        skill = self._make_concrete_skill(execute_return={"executed": True})

        with patch.object(skill, "_execute") as mock_execute:
            with patch.object(skill, "_mock_response", return_value={"mock": True}) as mock_mock:
                result = skill.run({})

        mock_execute.assert_not_called()
        mock_mock.assert_called_once_with({})
        assert result == {"mock": True}

    def test_non_dry_run_calls_execute(self, monkeypatch):
        """With DRY_RUN unset, run() delegates to _execute()."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        skill = self._make_concrete_skill(execute_return={"executed": True})

        with patch.object(skill, "_mock_response") as mock_mock:
            result = skill.run({"key": "val"})

        mock_mock.assert_not_called()
        assert result == {"executed": True}

    def test_is_dry_run_true(self, monkeypatch):
        """_is_dry_run() returns True when DRY_RUN env var is 'true'."""
        monkeypatch.setenv("DRY_RUN", "true")
        skill = self._make_concrete_skill()
        assert skill._is_dry_run() is True

    def test_is_dry_run_false(self, monkeypatch):
        """_is_dry_run() returns False when DRY_RUN env var is not set."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        skill = self._make_concrete_skill()
        assert skill._is_dry_run() is False

    def test_is_dry_run_case_insensitive(self, monkeypatch):
        """_is_dry_run() is case-insensitive: 'TRUE' also returns True."""
        monkeypatch.setenv("DRY_RUN", "TRUE")
        skill = self._make_concrete_skill()
        assert skill._is_dry_run() is True

    def test_is_dry_run_false_for_false_value(self, monkeypatch):
        """_is_dry_run() returns False when DRY_RUN is explicitly 'false'."""
        monkeypatch.setenv("DRY_RUN", "false")
        skill = self._make_concrete_skill()
        assert skill._is_dry_run() is False


# ── TestFetchJiraTicketSkill ──────────────────────────────────────────────────


class TestFetchJiraTicketSkill:
    """Tests for FetchJiraTicketSkill."""

    @pytest.fixture
    def skill(self):
        from skills.jira import FetchJiraTicketSkill
        return FetchJiraTicketSkill()

    def test_execute_calls_fetch_ticket_and_maps_state(self, skill, monkeypatch):
        """_execute() calls fetch_ticket then map_ticket_to_state and returns result."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        fake_raw_ticket = {"ticket_id": "BUILD-42", "summary": "Raw ticket"}
        fake_mapped = {
            "issue_title": "Raw ticket",
            "jira_ticket_id": "BUILD-42",
        }

        with patch("mcp.jira_stub.fetch_ticket", return_value=fake_raw_ticket) as mock_fetch:
            with patch("tools.jira_client.map_ticket_to_state", return_value=fake_mapped) as mock_map:
                result = skill.run({"ticket_id": "BUILD-42"})

        mock_fetch.assert_called_once_with("BUILD-42")
        mock_map.assert_called_once_with(fake_raw_ticket)
        assert result == fake_mapped

    def test_dry_run_returns_mock(self, skill, monkeypatch):
        """With DRY_RUN=true, run() returns dict with issue_title and jira_ticket_id."""
        monkeypatch.setenv("DRY_RUN", "true")

        fixed_mapped = {
            "issue_title": "Mocked title",
            "jira_ticket_id": "MOCK-1",
            "issue_description": "desc",
            "issue_type": "feature",
        }

        with patch("tools.jira_client.map_ticket_to_state", return_value=fixed_mapped):
            result = skill.run({"ticket_id": "MOCK-1"})

        assert "issue_title" in result
        assert "jira_ticket_id" in result

    def test_dry_run_patches_ticket_id_in_mock_data(self, skill, monkeypatch):
        """The ticket_id passed to run() is reflected in the mock data sent to map_ticket_to_state."""
        monkeypatch.setenv("DRY_RUN", "true")

        captured_args = {}

        def capture_map(ticket_data):
            captured_args["ticket_data"] = ticket_data
            return {
                "issue_title": "Captured",
                "jira_ticket_id": ticket_data.get("ticket_id", ""),
            }

        with patch("tools.jira_client.map_ticket_to_state", side_effect=capture_map):
            skill.run({"ticket_id": "BUILD-99"})

        assert captured_args["ticket_data"]["ticket_id"] == "BUILD-99"

    def test_skill_name_and_schemas(self, skill):
        """name == 'fetch_jira_ticket'; input_schema has 'ticket_id'; output_schema is dict."""
        assert skill.name == "fetch_jira_ticket"
        assert "ticket_id" in skill.input_schema
        assert isinstance(skill.output_schema, dict)

    def test_output_schema_has_expected_keys(self, skill):
        """output_schema must contain all fields required by downstream consumers."""
        expected_keys = {
            "ticket_id",
            "ticket_url",
            "issue_title",
            "issue_description",
            "issue_type",
            "issue_priority",
            "issue_labels",
            "issue_components",
            "pr_urls",
        }
        assert expected_keys.issubset(skill.output_schema.keys())


# ── TestUpdateJiraSkill ───────────────────────────────────────────────────────


class TestUpdateJiraSkill:
    """Tests for UpdateJiraSkill."""

    @pytest.fixture
    def skill(self):
        from skills.jira import UpdateJiraSkill
        return UpdateJiraSkill()

    def test_execute_calls_update_ticket(self, skill, monkeypatch):
        """_execute() gets a Jira client and calls update_ticket with ticket_id and comment."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        mock_client = MagicMock()
        mock_client.update_ticket.return_value = True

        with patch("tools.jira_client.get_jira_client", return_value=mock_client) as mock_factory:
            result = skill.run({"ticket_id": "BUILD-1", "comment": "test"})

        mock_factory.assert_called_once()
        mock_client.update_ticket.assert_called_once_with("BUILD-1", "test")
        assert result == {"success": True}

    def test_execute_returns_false_on_client_failure(self, skill, monkeypatch):
        """_execute() returns {'success': False} when the client returns False."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        mock_client = MagicMock()
        mock_client.update_ticket.return_value = False

        with patch("tools.jira_client.get_jira_client", return_value=mock_client):
            result = skill.run({"ticket_id": "BUILD-2", "comment": "failing"})

        assert result == {"success": False}

    def test_dry_run_returns_success(self, skill, monkeypatch):
        """With DRY_RUN=true, run() returns success without calling any Jira client."""
        monkeypatch.setenv("DRY_RUN", "true")

        with patch("tools.jira_client.get_jira_client") as mock_factory:
            result = skill.run({"ticket_id": "BUILD-1", "comment": "test"})

        mock_factory.assert_not_called()
        assert result.get("success") is True
        assert result.get("dry_run") is True

    def test_skill_name_and_schemas(self, skill):
        """name == 'update_jira'; input_schema has ticket_id and comment fields."""
        assert skill.name == "update_jira"
        assert "ticket_id" in skill.input_schema
        assert "comment" in skill.input_schema
        assert isinstance(skill.output_schema, dict)


# ── TestFetchGitHubPRsSkill ───────────────────────────────────────────────────


class TestFetchGitHubPRsSkill:
    """Tests for FetchGitHubPRsSkill."""

    @pytest.fixture
    def skill(self):
        from skills.github import FetchGitHubPRsSkill
        return FetchGitHubPRsSkill()

    def test_execute_fetches_prs(self, skill, monkeypatch):
        """_execute() fetches PR data when GitHub is configured and urls are provided."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        pr_list = [{"pr_number": 1, "title": "Fix bug"}]
        mock_client = MagicMock()
        mock_client.fetch_prs_from_urls.return_value = pr_list

        with patch("tools.github_client.is_github_configured", return_value=True):
            with patch("tools.github_client.get_github_client", return_value=mock_client):
                result = skill.run({"pr_urls": ["https://github.com/org/repo/pull/1"]})

        mock_client.fetch_prs_from_urls.assert_called_once_with(
            ["https://github.com/org/repo/pull/1"]
        )
        assert result == {"pr_data": pr_list}

    def test_execute_returns_empty_when_not_configured(self, skill, monkeypatch):
        """_execute() returns {'pr_data': []} when GitHub is not configured."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("tools.github_client.is_github_configured", return_value=False):
            with patch("tools.github_client.get_github_client") as mock_factory:
                result = skill.run({"pr_urls": ["https://github.com/org/repo/pull/1"]})

        mock_factory.assert_not_called()
        assert result == {"pr_data": []}

    def test_execute_returns_empty_when_no_urls(self, skill, monkeypatch):
        """_execute() returns {'pr_data': []} when pr_urls list is empty."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("tools.github_client.is_github_configured", return_value=True):
            with patch("tools.github_client.get_github_client") as mock_factory:
                result = skill.run({"pr_urls": []})

        mock_factory.assert_not_called()
        assert result == {"pr_data": []}

    def test_execute_returns_empty_when_pr_urls_missing(self, skill, monkeypatch):
        """_execute() returns {'pr_data': []} when 'pr_urls' key is absent from input."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("tools.github_client.is_github_configured", return_value=True):
            with patch("tools.github_client.get_github_client") as mock_factory:
                result = skill.run({})

        mock_factory.assert_not_called()
        assert result == {"pr_data": []}

    def test_dry_run_returns_empty(self, skill, monkeypatch):
        """With DRY_RUN=true, run() returns {'pr_data': []} without calling any client."""
        monkeypatch.setenv("DRY_RUN", "true")

        with patch("tools.github_client.is_github_configured") as mock_configured:
            with patch("tools.github_client.get_github_client") as mock_factory:
                result = skill.run({"pr_urls": ["https://github.com/org/repo/pull/99"]})

        mock_configured.assert_not_called()
        mock_factory.assert_not_called()
        assert result == {"pr_data": []}

    def test_skill_name_and_schemas(self, skill):
        """name == 'fetch_github_prs'; input_schema has 'pr_urls'; output_schema is dict."""
        assert skill.name == "fetch_github_prs"
        assert "pr_urls" in skill.input_schema
        assert isinstance(skill.output_schema, dict)
        assert "pr_data" in skill.output_schema


# ── TestSkillRegistry ─────────────────────────────────────────────────────────


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    @pytest.fixture
    def registry(self):
        from skills.registry import SkillRegistry
        return SkillRegistry()

    def _make_mock_skill(self, name: str):
        """Return a MagicMock that quacks like a Skill with a .name attribute."""
        mock_skill = MagicMock()
        mock_skill.name = name
        return mock_skill

    def test_register_and_get(self, registry):
        """A registered skill can be retrieved by name."""
        skill = self._make_mock_skill("my_skill")
        registry.register(skill)
        assert registry.get("my_skill") is skill

    def test_get_unknown_raises_key_error(self, registry):
        """get() raises KeyError for an unknown skill name."""
        with pytest.raises(KeyError):
            registry.get("does_not_exist")

    def test_key_error_message_contains_name(self, registry):
        """The KeyError message mentions the missing skill name."""
        with pytest.raises(KeyError, match="missing_skill"):
            registry.get("missing_skill")

    def test_list_skills_empty(self, registry):
        """list_skills() returns an empty list on a fresh registry."""
        assert registry.list_skills() == []

    def test_list_skills(self, registry):
        """list_skills() returns the names of all registered skills."""
        registry.register(self._make_mock_skill("skill_a"))
        registry.register(self._make_mock_skill("skill_b"))
        names = registry.list_skills()
        assert "skill_a" in names
        assert "skill_b" in names
        assert len(names) == 2

    def test_register_overwrites_existing(self, registry):
        """Registering a skill with the same name replaces the previous one."""
        skill_v1 = self._make_mock_skill("overwritten")
        skill_v2 = self._make_mock_skill("overwritten")
        registry.register(skill_v1)
        registry.register(skill_v2)
        assert registry.get("overwritten") is skill_v2
        assert len(registry.list_skills()) == 1

    def test_default_registry_has_all_skills(self):
        """default_registry is pre-populated with the three built-in skills."""
        from skills import default_registry

        names = default_registry.list_skills()
        assert "fetch_jira_ticket" in names
        assert "update_jira" in names
        assert "fetch_github_prs" in names

    def test_default_registry_fetch_jira_is_correct_type(self):
        """default_registry returns a FetchJiraTicketSkill instance."""
        from skills.jira import FetchJiraTicketSkill
        from skills import default_registry

        skill = default_registry.get("fetch_jira_ticket")
        assert isinstance(skill, FetchJiraTicketSkill)

    def test_default_registry_update_jira_is_correct_type(self):
        """default_registry returns an UpdateJiraSkill instance."""
        from skills.jira import UpdateJiraSkill
        from skills import default_registry

        skill = default_registry.get("update_jira")
        assert isinstance(skill, UpdateJiraSkill)

    def test_default_registry_fetch_github_prs_is_correct_type(self):
        """default_registry returns a FetchGitHubPRsSkill instance."""
        from skills.github import FetchGitHubPRsSkill
        from skills import default_registry

        skill = default_registry.get("fetch_github_prs")
        assert isinstance(skill, FetchGitHubPRsSkill)


# ── Main entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
