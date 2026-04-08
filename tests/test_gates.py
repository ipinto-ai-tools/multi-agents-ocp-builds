"""Tests for orchestrator.gates quality gate functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.gates import run_review_gate


class TestRunReviewGate:
    """run_review_gate delegates to run_code_review."""

    @patch("agents.code_review_agent.run_code_review")
    def test_delegates_to_run_code_review(self, mock_review: MagicMock) -> None:
        mock_review.return_value = {
            "review_passed": True,
            "review_findings": [],
            "review_summary": "All good",
            "review_iteration": 1,
        }

        state = {
            "code_files": [{"path": "main.go", "content": "package main"}],
            "design_analysis": "Some analysis",
            "acceptance_criteria": ["ac-1"],
            "session_id": "test",
        }

        result = run_review_gate(state)

        mock_review.assert_called_once_with(state)
        assert result["review_passed"] is True
        assert result["review_findings"] == []
        assert result["review_iteration"] == 1

    @patch("agents.code_review_agent.run_code_review")
    def test_returns_failure_from_review(self, mock_review: MagicMock) -> None:
        mock_review.return_value = {
            "review_passed": False,
            "review_findings": ["[BLOCKING] Security: SQL injection"],
            "review_summary": "1 blocking | FAIL",
            "review_iteration": 1,
        }

        state = {
            "code_files": [{"path": "main.go", "content": "package main"}],
            "session_id": "test",
        }

        result = run_review_gate(state)

        assert result["review_passed"] is False
        assert len(result["review_findings"]) == 1

    @patch("agents.code_review_agent.run_code_review")
    def test_propagates_exception(self, mock_review: MagicMock) -> None:
        mock_review.side_effect = RuntimeError("API down")

        state = {"code_files": [], "session_id": "test"}

        with pytest.raises(RuntimeError, match="API down"):
            run_review_gate(state)

    @patch("agents.code_review_agent.run_code_review")
    def test_passes_full_state_through(self, mock_review: MagicMock) -> None:
        """Ensure the gate passes the entire state dict, not a subset."""
        mock_review.return_value = {
            "review_passed": True,
            "review_findings": [],
            "review_summary": "ok",
            "review_iteration": 1,
        }

        state = {
            "code_files": [{"path": "a.go", "content": ""}],
            "design_analysis": "analysis",
            "acceptance_criteria": ["ac-1", "ac-2"],
            "review_iteration": 0,
            "session_id": "sess-123",
            "extra_field": "should be forwarded",
        }

        run_review_gate(state)

        # The exact same dict object should be passed
        passed_state = mock_review.call_args[0][0]
        assert passed_state is state
