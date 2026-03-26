"""Tests for scripts/publish.py --push-jira functionality.

All HTTP calls are mocked via unittest.mock.patch — no real Jira connection needed.
"""

import json
import pathlib
import sys
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(ticket_id: str = "SHIP-123") -> dict:
    return {
        "session_id": "abc12345",
        "jira_ticket_id": ticket_id,
        "current_phase": "done",
    }


def _write_state(tmp_path: pathlib.Path, state: dict) -> None:
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_design(tmp_path: pathlib.Path, content: str = "# Design Analysis\n\nSome design.") -> None:
    design_dir = tmp_path / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    (design_dir / "design_analysis.md").write_text(content, encoding="utf-8")


def _write_pr_summary(tmp_path: pathlib.Path, content: str = "# PR Summary\n\nDetails here.") -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "pr_summary.md").write_text(content, encoding="utf-8")


def _write_release_notes(tmp_path: pathlib.Path, content: str = "# Release Notes\n\nChanges.") -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "release_notes.md").write_text(content, encoding="utf-8")


def _mock_ok_response(status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.ok = True
    resp.status_code = status_code
    return resp


def _mock_error_response(status_code: int = 500) -> MagicMock:
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status_code
    resp.text = "Internal Server Error"
    return resp


def _jira_config(
    base_url: str = "https://test.atlassian.net",
    email: str = "user@example.com",
    api_token: str = "test-token",
) -> dict:
    return {"base_url": base_url, "email": email, "api_token": api_token}


# ---------------------------------------------------------------------------
# Import helper — always import from the project root
# ---------------------------------------------------------------------------

def _import_push_jira():
    """Return the _push_jira callable from scripts/publish.py."""
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "publish",
        os.path.join(os.path.dirname(__file__), "..", "scripts", "publish.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._push_jira


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPushJiraReadsStateJson:
    """_push_jira reads jira_ticket_id from state.json."""

    def test_push_jira_reads_state_json(self, tmp_path, monkeypatch):
        """_push_jira extracts ticket_id from state.json without error."""
        _write_state(tmp_path, _make_state("BUILD-1707"))
        _write_design(tmp_path)
        _write_pr_summary(tmp_path)

        _push_jira = _import_push_jira()

        with patch("requests.Session") as mock_session_cls:
            session = MagicMock()
            session.post.return_value = _mock_ok_response(201)
            mock_session_cls.return_value = session

            # Should not raise
            _push_jira(tmp_path, _jira_config(), dry_run=False)

        # Confirm the ticket ID was used in at least one call
        calls_str = str(session.post.call_args_list)
        assert "BUILD-1707" in calls_str


class TestPushJiraAttachesDesignAnalysis:
    """_push_jira attaches design/design_analysis.md to the Jira ticket."""

    def test_push_jira_attaches_design_analysis(self, tmp_path, monkeypatch):
        """POST to /attachments endpoint is made with the design file."""
        _write_state(tmp_path, _make_state("SHIP-42"))
        _write_design(tmp_path, "# Design\n\nDetailed analysis.")
        _write_pr_summary(tmp_path)

        _push_jira = _import_push_jira()

        with patch("requests.Session") as mock_session_cls:
            session = MagicMock()
            session.post.return_value = _mock_ok_response(200)
            mock_session_cls.return_value = session

            _push_jira(tmp_path, _jira_config(), dry_run=False)

        # Find the attachment call
        attachment_calls = [
            c for c in session.post.call_args_list
            if "attachments" in str(c)
        ]
        assert len(attachment_calls) == 1, "Expected exactly one attachments POST call"

        call_kwargs = attachment_calls[0].kwargs
        assert "X-Atlassian-Token" in call_kwargs.get("headers", {})
        assert call_kwargs["headers"]["X-Atlassian-Token"] == "no-check"
        assert "files" in call_kwargs
        filename, _, mime = call_kwargs["files"]["file"]
        assert filename == "design_analysis.md"
        assert mime == "text/markdown"


class TestPushJiraPostsPrSummaryComment:
    """_push_jira posts pr_summary.md content as a Jira comment."""

    def test_push_jira_posts_pr_summary_comment(self, tmp_path):
        """POST to /comment endpoint includes PR Summary header and content."""
        _write_state(tmp_path, _make_state("SHIP-100"))
        _write_design(tmp_path)
        _write_pr_summary(tmp_path, "Fixes the timeout issue.")

        _push_jira = _import_push_jira()

        with patch("requests.Session") as mock_session_cls:
            session = MagicMock()
            session.post.return_value = _mock_ok_response(201)
            mock_session_cls.return_value = session

            _push_jira(tmp_path, _jira_config(), dry_run=False)

        comment_calls = [
            c for c in session.post.call_args_list
            if "comment" in str(c) and "attachments" not in str(c)
        ]
        # At minimum a PR summary comment should have been posted
        assert any(
            "PR Summary" in str(c) and "Fixes the timeout issue" in str(c)
            for c in comment_calls
        ), "PR Summary comment not found in session.post calls"


class TestPushJiraPostsReleaseNotesComment:
    """_push_jira posts release_notes.md as a separate comment when non-empty."""

    def test_push_jira_posts_release_notes_comment(self, tmp_path):
        """When release_notes.md has content, a Release Notes comment is posted."""
        _write_state(tmp_path, _make_state("SHIP-200"))
        _write_design(tmp_path)
        _write_pr_summary(tmp_path)
        _write_release_notes(tmp_path, "## v1.2.0\n\n- Added timeout support.")

        _push_jira = _import_push_jira()

        with patch("requests.Session") as mock_session_cls:
            session = MagicMock()
            session.post.return_value = _mock_ok_response(201)
            mock_session_cls.return_value = session

            _push_jira(tmp_path, _jira_config(), dry_run=False)

        calls_str = str(session.post.call_args_list)
        assert "Release Notes" in calls_str
        assert "timeout support" in calls_str


class TestPushJiraSkipsMissingReleaseNotes:
    """_push_jira skips the release notes comment when the file is absent."""

    def test_push_jira_skips_missing_release_notes(self, tmp_path, capsys):
        """No release-notes comment is posted when release_notes.md is missing."""
        _write_state(tmp_path, _make_state("SHIP-300"))
        _write_design(tmp_path)
        _write_pr_summary(tmp_path)
        # release_notes.md intentionally NOT written

        _push_jira = _import_push_jira()

        with patch("requests.Session") as mock_session_cls:
            session = MagicMock()
            session.post.return_value = _mock_ok_response(201)
            mock_session_cls.return_value = session

            _push_jira(tmp_path, _jira_config(), dry_run=False)

        calls_str = str(session.post.call_args_list)
        assert "Release Notes" not in calls_str

        captured = capsys.readouterr()
        assert "WARNING" in captured.out  # warning about missing file


class TestPushJiraSkipsMissingDesignFile:
    """_push_jira skips attachment when design_analysis.md is absent."""

    def test_push_jira_skips_missing_design_file(self, tmp_path, capsys):
        """No attachment POST is made when design_analysis.md is missing."""
        _write_state(tmp_path, _make_state("SHIP-400"))
        _write_pr_summary(tmp_path)
        # design/design_analysis.md intentionally NOT written

        _push_jira = _import_push_jira()

        with patch("requests.Session") as mock_session_cls:
            session = MagicMock()
            session.post.return_value = _mock_ok_response(201)
            mock_session_cls.return_value = session

            _push_jira(tmp_path, _jira_config(), dry_run=False)

        attachment_calls = [
            c for c in session.post.call_args_list
            if "attachments" in str(c)
        ]
        assert len(attachment_calls) == 0, "No attachment call expected when file is missing"

        captured = capsys.readouterr()
        assert "WARNING" in captured.out


class TestPushJiraDryRunSkipsApiCalls:
    """--dry-run must not make any HTTP requests."""

    def test_push_jira_dry_run_skips_api_calls(self, tmp_path, capsys):
        """With dry_run=True, no requests.Session is created and no POSTs are made."""
        _write_state(tmp_path, _make_state("SHIP-500"))
        _write_design(tmp_path)
        _write_pr_summary(tmp_path)
        _write_release_notes(tmp_path)

        _push_jira = _import_push_jira()

        with patch("requests.Session") as mock_session_cls:
            _push_jira(tmp_path, _jira_config(), dry_run=True)
            mock_session_cls.assert_not_called()

        captured = capsys.readouterr()
        assert "dry-run" in captured.out
        assert "SHIP-500" in captured.out


class TestPushJiraMissingCredentialsExits:
    """Missing JIRA_BASE_URL or JIRA_API_TOKEN causes sys.exit(1)."""

    def test_push_jira_missing_credentials_exits(self, tmp_path):
        """sys.exit(1) raised when base_url is absent from config."""
        _write_state(tmp_path, _make_state("SHIP-600"))

        _push_jira = _import_push_jira()

        with pytest.raises(SystemExit) as exc_info:
            _push_jira(tmp_path, {"base_url": "", "email": "u@e.com", "api_token": "tok"}, dry_run=False)

        assert exc_info.value.code == 1

    def test_push_jira_missing_api_token_exits(self, tmp_path):
        """sys.exit(1) raised when api_token is absent from config."""
        _write_state(tmp_path, _make_state("SHIP-601"))

        _push_jira = _import_push_jira()

        with pytest.raises(SystemExit) as exc_info:
            _push_jira(tmp_path, {"base_url": "https://x.atlassian.net", "email": "u@e.com", "api_token": ""}, dry_run=False)

        assert exc_info.value.code == 1


class TestPushJiraHttpErrorContinues:
    """HTTP errors on individual actions are logged as warnings; execution continues."""

    def test_push_jira_http_error_continues(self, tmp_path, capsys):
        """When attachment POST fails, the comment POST is still attempted."""
        _write_state(tmp_path, _make_state("SHIP-700"))
        _write_design(tmp_path)
        _write_pr_summary(tmp_path)

        _push_jira = _import_push_jira()

        with patch("requests.Session") as mock_session_cls:
            session = MagicMock()
            # First call (attachment) fails, second (comment) succeeds
            session.post.side_effect = [
                _mock_error_response(500),
                _mock_ok_response(201),
            ]
            mock_session_cls.return_value = session

            # Must not raise
            _push_jira(tmp_path, _jira_config(), dry_run=False)

        assert session.post.call_count == 2

        captured = capsys.readouterr()
        assert "WARNING" in captured.out  # failure warning
        assert "Posted" in captured.out   # success message for comment


class TestPushJiraMissingTicketIdExits:
    """Missing jira_ticket_id in state.json causes sys.exit(1)."""

    def test_push_jira_missing_ticket_id_exits(self, tmp_path, capsys):
        """sys.exit(1) raised when state.json has no jira_ticket_id."""
        state_without_ticket = {"session_id": "abc", "current_phase": "done"}
        _write_state(tmp_path, state_without_ticket)

        _push_jira = _import_push_jira()

        with pytest.raises(SystemExit) as exc_info:
            _push_jira(tmp_path, _jira_config(), dry_run=False)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "jira_ticket_id" in captured.err


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
