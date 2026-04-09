"""Tests for orchestrator.gates quality gate functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.gates import (
    GateResult,
    run_command_gate,
    run_post_develop_gates,
    run_post_test_gates,
    run_review_gate,
)


class TestRunReviewGate:
    """run_review_gate delegates to run_code_review."""

    @patch("stages.code_review.run_code_review")
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

    @patch("stages.code_review.run_code_review")
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

    @patch("stages.code_review.run_code_review")
    def test_propagates_exception(self, mock_review: MagicMock) -> None:
        mock_review.side_effect = RuntimeError("API down")

        state = {"code_files": [], "session_id": "test"}

        with pytest.raises(RuntimeError, match="API down"):
            run_review_gate(state)

    @patch("stages.code_review.run_code_review")
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


# ---------------------------------------------------------------------------
# GateResult dataclass
# ---------------------------------------------------------------------------


class TestGateResult:
    """GateResult stores gate execution metadata."""

    def test_defaults(self) -> None:
        result = GateResult(gate_name="build", passed=True)
        assert result.gate_name == "build"
        assert result.passed is True
        assert result.output == ""
        assert result.error == ""
        assert result.command == ""

    def test_with_all_fields(self) -> None:
        result = GateResult(
            gate_name="lint",
            passed=False,
            output="stdout text",
            error="stderr text",
            command="golangci-lint run",
        )
        assert result.gate_name == "lint"
        assert result.passed is False
        assert result.output == "stdout text"
        assert result.error == "stderr text"
        assert result.command == "golangci-lint run"


# ---------------------------------------------------------------------------
# run_command_gate
# ---------------------------------------------------------------------------


class TestRunCommandGate:
    """run_command_gate executes a shell command and returns GateResult."""

    def test_successful_command(self) -> None:
        result = run_command_gate("echo hello", "test_gate")
        assert result.passed is True
        assert "hello" in result.output
        assert result.gate_name == "test_gate"
        assert result.command == "echo hello"

    def test_failing_command(self) -> None:
        result = run_command_gate("exit 1", "test_gate")
        assert result.passed is False
        assert result.gate_name == "test_gate"

    def test_command_with_cwd(self, tmp_path) -> None:
        result = run_command_gate("pwd", "test_gate", cwd=str(tmp_path))
        assert result.passed is True
        assert str(tmp_path) in result.output

    def test_command_captures_stderr(self) -> None:
        result = run_command_gate("echo err >&2 && exit 1", "test_gate")
        assert result.passed is False
        assert "err" in result.error

    def test_command_timeout(self) -> None:
        with patch("orchestrator.gates._COMMAND_TIMEOUT_SECONDS", 0):
            # subprocess.run with timeout=0 should raise TimeoutExpired
            # for any non-trivial command
            with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("cmd", 0)):
                result = run_command_gate("sleep 999", "test_gate")
                assert result.passed is False
                assert "timed out" in result.error

    def test_command_unexpected_exception(self) -> None:
        with patch("subprocess.run", side_effect=OSError("no such file")):
            result = run_command_gate("nonexistent", "test_gate")
            assert result.passed is False
            assert "no such file" in result.error

    def test_command_with_no_output(self) -> None:
        result = run_command_gate("true", "test_gate")
        assert result.passed is True
        assert result.output == ""


# ---------------------------------------------------------------------------
# run_post_develop_gates
# ---------------------------------------------------------------------------


class TestRunPostDevelopGates:
    """run_post_develop_gates runs build and lint commands."""

    def test_with_both_commands(self) -> None:
        commands = {"build": "echo build_ok", "lint": "echo lint_ok"}
        results = run_post_develop_gates("/tmp", commands)
        assert len(results) == 2
        assert all(r.passed for r in results)
        assert results[0].gate_name == "build"
        assert results[1].gate_name == "lint"

    def test_with_no_commands(self) -> None:
        results = run_post_develop_gates("/tmp", None)
        assert results == []

    def test_with_empty_dict(self) -> None:
        results = run_post_develop_gates("/tmp", {})
        assert results == []

    def test_build_fails_lint_still_runs(self) -> None:
        commands = {"build": "exit 1", "lint": "echo ok"}
        results = run_post_develop_gates("/tmp", commands)
        assert len(results) == 2
        assert not results[0].passed  # build failed
        assert results[1].passed  # lint passed

    def test_only_build_configured(self) -> None:
        commands = {"build": "echo build_ok"}
        results = run_post_develop_gates("/tmp", commands)
        assert len(results) == 1
        assert results[0].gate_name == "build"
        assert results[0].passed is True

    def test_only_lint_configured(self) -> None:
        commands = {"lint": "echo lint_ok"}
        results = run_post_develop_gates("/tmp", commands)
        assert len(results) == 1
        assert results[0].gate_name == "lint"
        assert results[0].passed is True

    def test_ignores_unrelated_commands(self) -> None:
        commands = {"test": "echo ignored", "doc": "echo also_ignored"}
        results = run_post_develop_gates("/tmp", commands)
        assert results == []


# ---------------------------------------------------------------------------
# run_post_test_gates
# ---------------------------------------------------------------------------


class TestRunPostTestGates:
    """run_post_test_gates runs the test command."""

    def test_with_test_command(self) -> None:
        commands = {"test": "echo tests_pass"}
        results = run_post_test_gates("/tmp", commands)
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].gate_name == "test"

    def test_with_no_commands(self) -> None:
        results = run_post_test_gates("/tmp", None)
        assert results == []

    def test_with_empty_dict(self) -> None:
        results = run_post_test_gates("/tmp", {})
        assert results == []

    def test_test_command_fails(self) -> None:
        commands = {"test": "exit 1"}
        results = run_post_test_gates("/tmp", commands)
        assert len(results) == 1
        assert not results[0].passed

    def test_ignores_build_and_lint(self) -> None:
        commands = {"build": "echo ignored", "lint": "echo ignored"}
        results = run_post_test_gates("/tmp", commands)
        assert results == []
