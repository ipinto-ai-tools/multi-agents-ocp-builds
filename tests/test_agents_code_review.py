"""Tests for the Code Review Agent and related components.

Covers:
- _parse_review_output: unit tests for finding parsing and verdict logic
- run_code_review: feature-flag disabled, no code files, dry-run, mocked Claude API,
  and error-resilience scenarios
- _format_code_for_review: unit tests for file formatting and truncation
- validate_review_output (validators.py): passing, failing, and max-iterations cases
- Mock responses: MOCK_CODE_REVIEW_PASS, MOCK_CODE_REVIEW_FAIL, and get_mock_response()

All tests work without API credentials (no @pytest.mark.real_api used).
"""

import importlib
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_state(**overrides: Any) -> dict:
    """Return a minimal AgentState dict suitable for run_code_review."""
    base: dict[str, Any] = {
        "code_files": [
            {"path": "pkg/controller/timeout.go", "content": "package controller\n\nfunc enforce() {}"},
        ],
        "design_analysis": "Add timeout support to BuildRun API.",
        "acceptance_criteria": ["BuildRun accepts timeout field", "Controller enforces timeout"],
        "review_iteration": 0,
        "session_id": "test-session-001",
    }
    base.update(overrides)
    return base


def _make_mock_client(response_text: str) -> MagicMock:
    """Return a mock Anthropic client whose messages.create() returns response_text."""
    mock_content = MagicMock()
    mock_content.text = response_text

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    return mock_client


# ── _parse_review_output ─────────────────────────────────────────────────────


class TestParseReviewOutput:
    """Unit tests for _parse_review_output — no mocking required."""

    @pytest.fixture(autouse=True)
    def import_agent(self):
        from stages.code_review import _parse_review_output
        self._parse = _parse_review_output

    def test_parse_review_output_blocking_finding_parsed(self):
        """[BLOCKING] lines should appear in findings with level 'blocking'."""
        raw = "[BLOCKING] SECURITY: Missing validation for timeout duration\nVERDICT: FAIL"
        result = self._parse(raw)
        assert any("[BLOCKING]" in f for f in result["review_findings"])

    def test_parse_review_output_blocking_verdict_fail(self):
        """A [BLOCKING] finding should produce review_passed=False (via VERDICT: FAIL)."""
        raw = "[BLOCKING] SECURITY: Null pointer dereference\nVERDICT: FAIL"
        result = self._parse(raw)
        assert result["review_passed"] is False

    def test_parse_review_output_warning_finding_parsed(self):
        """[WARNING] lines should appear in findings."""
        raw = "[WARNING] TESTING: Missing table-driven edge case\nVERDICT: PASS"
        result = self._parse(raw)
        assert any("[WARNING]" in f for f in result["review_findings"])

    def test_parse_review_output_warning_verdict_pass(self):
        """VERDICT: PASS with only warnings should produce review_passed=True."""
        raw = "[WARNING] STYLE: Variable name too short\nVERDICT: PASS"
        result = self._parse(raw)
        assert result["review_passed"] is True

    def test_parse_review_output_suggestion_finding_parsed(self):
        """[SUGGESTION] lines should appear in findings."""
        raw = "[SUGGESTION] STYLE: Consider adding inline comments\nVERDICT: PASS"
        result = self._parse(raw)
        assert any("[SUGGESTION]" in f for f in result["review_findings"])

    def test_parse_review_output_suggestion_verdict_pass(self):
        """VERDICT: PASS with only suggestions should produce review_passed=True."""
        raw = "[SUGGESTION] DOCS: Add godoc comment to exported function\nVERDICT: PASS"
        result = self._parse(raw)
        assert result["review_passed"] is True

    def test_parse_review_output_mixed_findings_blocking_drives_verdict_fail(self):
        """When VERDICT: FAIL is present, review_passed=False regardless of other findings."""
        raw = (
            "[SUGGESTION] STYLE: Minor naming issue\n"
            "[WARNING] TESTING: Missing edge case\n"
            "[BLOCKING] SECURITY: Unvalidated input\n"
            "VERDICT: FAIL"
        )
        result = self._parse(raw)
        assert result["review_passed"] is False
        assert len(result["review_findings"]) == 3

    def test_parse_review_output_verdict_pass_overrides_blocking_count(self):
        """VERDICT: PASS in output overrides threshold logic even if [BLOCKING] present."""
        raw = "[BLOCKING] SECURITY: Ignored by explicit PASS verdict\nVERDICT: PASS"
        result = self._parse(raw)
        assert result["review_passed"] is True

    def test_parse_review_output_verdict_fail_overrides_no_blocking(self):
        """VERDICT: FAIL overrides threshold logic even when there are no [BLOCKING] lines."""
        raw = "[WARNING] STYLE: Could be cleaner\nVERDICT: FAIL"
        result = self._parse(raw)
        assert result["review_passed"] is False

    def test_parse_review_output_empty_input_returns_passed_true(self):
        """Empty output should return review_passed=True with no findings."""
        result = self._parse("")
        assert result["review_passed"] is True
        assert result["review_findings"] == []

    def test_parse_review_output_empty_input_findings_list_is_empty(self):
        """Empty output should produce an empty findings list."""
        result = self._parse("")
        assert isinstance(result["review_findings"], list)
        assert len(result["review_findings"]) == 0

    def test_parse_review_output_only_suggestions_high_threshold_passes(self):
        """With QODO_BLOCKING_THRESHOLD=high (default), only suggestions → pass."""
        raw = "[SUGGESTION] STYLE: Consider renaming\n[SUGGESTION] DOCS: Add comments"
        result = self._parse(raw)
        assert result["review_passed"] is True

    def test_parse_review_output_returns_review_passed_key(self):
        """Result must contain 'review_passed' key."""
        result = self._parse("VERDICT: PASS")
        assert "review_passed" in result

    def test_parse_review_output_returns_review_findings_key(self):
        """Result must contain 'review_findings' key as a list."""
        result = self._parse("VERDICT: PASS")
        assert "review_findings" in result
        assert isinstance(result["review_findings"], list)

    def test_parse_review_output_returns_review_summary_key(self):
        """Result must contain 'review_summary' key as a string."""
        result = self._parse("VERDICT: PASS")
        assert "review_summary" in result
        assert isinstance(result["review_summary"], str)

    def test_parse_review_output_does_not_return_review_iteration_key(self):
        """_parse_review_output must NOT include review_iteration in its return dict."""
        result = self._parse("VERDICT: PASS")
        assert "review_iteration" not in result

    def test_parse_review_output_summary_contains_pass_when_passed(self):
        """review_summary should contain 'PASS' when review_passed is True."""
        result = self._parse("VERDICT: PASS")
        assert "PASS" in result["review_summary"]

    def test_parse_review_output_summary_contains_fail_when_failed(self):
        """review_summary should contain 'FAIL' when review_passed is False."""
        result = self._parse("[BLOCKING] SECURITY: Bad thing\nVERDICT: FAIL")
        assert "FAIL" in result["review_summary"]

    def test_parse_review_output_summary_contains_finding_count(self):
        """review_summary should mention the total number of findings."""
        raw = "[BLOCKING] SECURITY: Issue 1\n[WARNING] TESTING: Issue 2\nVERDICT: FAIL"
        result = self._parse(raw)
        assert "2" in result["review_summary"]

    def test_parse_review_output_blocking_count_in_summary(self):
        """When blocking issues exist, their count appears in review_summary."""
        raw = "[BLOCKING] SECURITY: Bad thing\n[BLOCKING] CRASH: Panic risk\nVERDICT: FAIL"
        result = self._parse(raw)
        assert "2" in result["review_summary"] or "blocking" in result["review_summary"].lower()

    def test_parse_review_output_whitespace_lines_ignored(self):
        """Lines that are blank or only whitespace should not produce findings."""
        raw = "   \n\n[SUGGESTION] STYLE: One suggestion\n\n\nVERDICT: PASS"
        result = self._parse(raw)
        assert len(result["review_findings"]) == 1

    def test_parse_review_output_findings_text_matches_input_line(self):
        """Each finding text should match the original tagged line from input."""
        raw = "[BLOCKING] SECURITY: Missing input validation\nVERDICT: FAIL"
        result = self._parse(raw)
        assert result["review_findings"][0] == "[BLOCKING] SECURITY: Missing input validation"


# ── _format_code_for_review ───────────────────────────────────────────────────


class TestFormatCodeForReview:
    """Unit tests for _format_code_for_review."""

    @pytest.fixture(autouse=True)
    def import_func(self):
        from stages.code_review import _format_code_for_review
        self._format = _format_code_for_review

    def test_format_empty_list_returns_empty_string(self):
        """Empty code_files list should produce an empty string."""
        assert self._format([]) == ""

    def test_format_single_file_includes_path(self):
        """Output for a single file should include the file path."""
        files = [{"path": "pkg/foo.go", "content": "package foo"}]
        result = self._format(files)
        assert "pkg/foo.go" in result

    def test_format_single_file_includes_content(self):
        """Output for a single file should include the file content."""
        files = [{"path": "pkg/foo.go", "content": "package foo\n\nfunc Foo() {}"}]
        result = self._format(files)
        assert "package foo" in result

    def test_format_single_file_fenced_code_block(self):
        """Output should wrap content in a Go fenced code block."""
        files = [{"path": "main.go", "content": "package main"}]
        result = self._format(files)
        assert "```go" in result
        assert "```" in result

    def test_format_more_than_10_files_capped_at_10(self):
        """Only the first 10 files should be included when more than 10 are provided."""
        files = [{"path": f"file{i}.go", "content": f"package p{i}"} for i in range(15)]
        result = self._format(files)
        # Files 0-9 should be present; file 10+ should not
        assert "file9.go" in result
        assert "file10.go" not in result

    def test_format_exactly_10_files_all_included(self):
        """Exactly 10 files should all appear in the output."""
        files = [{"path": f"file{i}.go", "content": f"package p"} for i in range(10)]
        result = self._format(files)
        for i in range(10):
            assert f"file{i}.go" in result

    def test_format_content_over_3000_chars_truncated(self):
        """File content exceeding 3000 characters should be truncated with a marker."""
        long_content = "x" * 5000
        files = [{"path": "big.go", "content": long_content}]
        result = self._format(files)
        # The first 3000 chars of content must be present and a truncation marker appended
        assert "x" * 3000 in result
        assert "[TRUNCATED" in result
        # Original full content must NOT be present (i.e. it was actually truncated)
        assert "x" * 5000 not in result

    def test_format_content_at_3000_chars_not_truncated(self):
        """Content of exactly 3000 characters should not be truncated."""
        exact_content = "y" * 3000
        files = [{"path": "exact.go", "content": exact_content}]
        result = self._format(files)
        assert exact_content in result

    def test_format_missing_path_key_uses_default(self):
        """Files missing 'path' key should use 'unknown.go' as default."""
        files = [{"content": "package foo"}]
        result = self._format(files)
        assert "unknown.go" in result

    def test_format_missing_content_key_uses_empty_string(self):
        """Files missing 'content' key should produce an empty code block body."""
        files = [{"path": "empty.go"}]
        result = self._format(files)
        assert "empty.go" in result
        assert "```go" in result

    def test_format_multiple_files_separated(self):
        """Multiple files should be separated in the output string."""
        files = [
            {"path": "a.go", "content": "package a"},
            {"path": "b.go", "content": "package b"},
        ]
        result = self._format(files)
        assert "a.go" in result
        assert "b.go" in result


# ── run_code_review — feature flag disabled ───────────────────────────────────


class TestRunCodeReviewDisabled:
    """Tests for run_code_review when QODO_REVIEW_ENABLED=false."""

    def test_feature_flag_disabled_returns_review_passed_true(self, monkeypatch):
        """When QODO_REVIEW_ENABLED=false, review_passed must be True."""
        monkeypatch.setenv("QODO_REVIEW_ENABLED", "false")
        import importlib
        import stages.code_review as mod
        importlib.reload(mod)

        result = mod.run_code_review(_make_state())
        assert result["review_passed"] is True

        monkeypatch.setenv("QODO_REVIEW_ENABLED", "true")
        importlib.reload(mod)

    def test_feature_flag_disabled_summary_mentions_skipped(self, monkeypatch):
        """When QODO_REVIEW_ENABLED=false, summary should mention 'skipped'."""
        monkeypatch.setenv("QODO_REVIEW_ENABLED", "false")
        import importlib
        import stages.code_review as mod
        importlib.reload(mod)

        result = mod.run_code_review(_make_state())
        assert "skip" in result["review_summary"].lower() or "false" in result["review_summary"].lower()

        monkeypatch.setenv("QODO_REVIEW_ENABLED", "true")
        importlib.reload(mod)

    def test_feature_flag_disabled_does_not_increment_iteration(self, monkeypatch):
        """When QODO_REVIEW_ENABLED=false, review_iteration must NOT be incremented."""
        monkeypatch.setenv("QODO_REVIEW_ENABLED", "false")
        import importlib
        import stages.code_review as mod
        importlib.reload(mod)

        state = _make_state(review_iteration=0)
        result = mod.run_code_review(state)
        assert result["review_iteration"] == 0

        monkeypatch.setenv("QODO_REVIEW_ENABLED", "true")
        importlib.reload(mod)

    def test_feature_flag_disabled_findings_is_empty_list(self, monkeypatch):
        """When QODO_REVIEW_ENABLED=false, review_findings must be an empty list."""
        monkeypatch.setenv("QODO_REVIEW_ENABLED", "false")
        import importlib
        import stages.code_review as mod
        importlib.reload(mod)

        result = mod.run_code_review(_make_state())
        assert result["review_findings"] == []

        monkeypatch.setenv("QODO_REVIEW_ENABLED", "true")
        importlib.reload(mod)


# ── run_code_review — no code files ──────────────────────────────────────────


class TestRunCodeReviewNoFiles:
    """Tests for run_code_review when state has no code files."""

    def test_no_code_files_returns_review_passed_true(self):
        """Empty code_files should short-circuit with review_passed=True."""
        from stages.code_review import run_code_review
        result = run_code_review(_make_state(code_files=[]))
        assert result["review_passed"] is True

    def test_no_code_files_summary_mentions_no_code(self):
        """Empty code_files should produce a summary mentioning 'No code files'."""
        from stages.code_review import run_code_review
        result = run_code_review(_make_state(code_files=[]))
        assert "no code" in result["review_summary"].lower() or "no code files" in result["review_summary"].lower()

    def test_no_code_files_does_not_increment_iteration(self):
        """Empty code_files should not increment review_iteration."""
        from stages.code_review import run_code_review
        result = run_code_review(_make_state(code_files=[], review_iteration=0))
        assert result["review_iteration"] == 0

    def test_no_code_files_returns_empty_findings(self):
        """Empty code_files should return an empty findings list."""
        from stages.code_review import run_code_review
        result = run_code_review(_make_state(code_files=[]))
        assert result["review_findings"] == []

    def test_no_code_files_key_missing_from_state_treated_as_empty(self):
        """State without 'code_files' key should behave the same as empty list."""
        from stages.code_review import run_code_review
        state = {k: v for k, v in _make_state().items() if k != "code_files"}
        result = run_code_review(state)
        assert result["review_passed"] is True


# ── run_code_review — dry-run mode ────────────────────────────────────────────


class TestRunCodeReviewDryRun:
    """Tests for run_code_review with DRY_RUN=true."""

    def test_dry_run_returns_mock_code_review_pass_data(self, monkeypatch):
        """DRY_RUN=true should return MOCK_CODE_REVIEW_PASS contents."""
        monkeypatch.setenv("DRY_RUN", "true")
        from config.mock_responses import MOCK_CODE_REVIEW_PASS

        with patch("dashboard.heartbeat.emit_heartbeat"):
            from stages.code_review import run_code_review
            result = run_code_review(_make_state())

        assert result["review_passed"] == MOCK_CODE_REVIEW_PASS["review_passed"]
        assert result["review_findings"] == MOCK_CODE_REVIEW_PASS["review_findings"]
        assert result["review_summary"] == MOCK_CODE_REVIEW_PASS["review_summary"]

    def test_dry_run_increments_review_iteration_to_1(self, monkeypatch):
        """DRY_RUN mode should increment review_iteration from 0 to 1."""
        monkeypatch.setenv("DRY_RUN", "true")

        with patch("dashboard.heartbeat.emit_heartbeat"):
            from stages.code_review import run_code_review
            result = run_code_review(_make_state(review_iteration=0))

        assert result["review_iteration"] == 1

    def test_dry_run_does_not_call_anthropic_api(self, monkeypatch):
        """DRY_RUN=true should not make any real API calls."""
        monkeypatch.setenv("DRY_RUN", "true")

        with patch("dashboard.heartbeat.emit_heartbeat"), \
             patch("config.auth_config.get_anthropic_client") as mock_get_client:
            from stages.code_review import run_code_review
            run_code_review(_make_state())
            mock_get_client.assert_not_called()

    def test_dry_run_emit_heartbeat_called(self, monkeypatch):
        """DRY_RUN=true should still emit heartbeats for dashboard visibility."""
        monkeypatch.setenv("DRY_RUN", "true")

        with patch("stages.code_review.emit_heartbeat") as mock_emit:
            from stages.code_review import run_code_review
            run_code_review(_make_state())

        assert mock_emit.call_count >= 1


# ── run_code_review — Claude review (mocked API) ──────────────────────────────


class TestRunCodeReviewClaudeApi:
    """Tests for run_code_review using a mocked Claude API client."""

    def _run_with_response(self, response_text: str, state_overrides: dict | None = None) -> dict:
        """Helper: patch get_anthropic_client and emit_heartbeat, run review."""
        state = _make_state(**(state_overrides or {}))
        mock_client = _make_mock_client(response_text)

        with patch("stages.code_review.get_anthropic_client", return_value=mock_client), \
             patch("dashboard.heartbeat.emit_heartbeat"):
            from stages.code_review import run_code_review
            return run_code_review(state)

    def test_claude_blocking_finding_sets_review_passed_false(self, monkeypatch):
        """BLOCKING finding + VERDICT: FAIL → review_passed=False."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        response = "[BLOCKING] SECURITY: Missing input validation\nVERDICT: FAIL"
        result = self._run_with_response(response)
        assert result["review_passed"] is False

    def test_claude_blocking_finding_populates_findings_list(self, monkeypatch):
        """BLOCKING finding should appear in review_findings."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        response = "[BLOCKING] SECURITY: Missing input validation\nVERDICT: FAIL"
        result = self._run_with_response(response)
        assert len(result["review_findings"]) >= 1
        assert any("BLOCKING" in f for f in result["review_findings"])

    def test_claude_blocking_increments_iteration_to_1(self, monkeypatch):
        """After Claude review, review_iteration should be 1 (incremented from 0)."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        response = "[BLOCKING] SECURITY: Bad thing\nVERDICT: FAIL"
        result = self._run_with_response(response)
        assert result["review_iteration"] == 1

    def test_claude_suggestion_only_sets_review_passed_true(self, monkeypatch):
        """Only [SUGGESTION] lines + VERDICT: PASS → review_passed=True."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        response = "[SUGGESTION] STYLE: Add inline comments\nVERDICT: PASS"
        result = self._run_with_response(response)
        assert result["review_passed"] is True

    def test_claude_suggestion_only_increments_iteration_to_1(self, monkeypatch):
        """After a passing Claude review, review_iteration should be 1."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        response = "[SUGGESTION] DOCS: Add godoc\nVERDICT: PASS"
        result = self._run_with_response(response)
        assert result["review_iteration"] == 1

    def test_claude_result_has_required_keys(self, monkeypatch):
        """run_code_review result must always have the four required keys."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        response = "VERDICT: PASS"
        result = self._run_with_response(response)
        for key in ("review_passed", "review_findings", "review_summary", "review_iteration"):
            assert key in result

    def test_claude_second_iteration_increments_correctly(self, monkeypatch):
        """Starting from review_iteration=2 should produce review_iteration=3."""
        monkeypatch.delenv("DRY_RUN", raising=False)
        response = "VERDICT: PASS"
        result = self._run_with_response(response, state_overrides={"review_iteration": 2})
        assert result["review_iteration"] == 3


# ── run_code_review — error resilience ───────────────────────────────────────


class TestRunCodeReviewErrorResilience:
    """Tests for run_code_review when the API or client raises an exception."""

    def test_api_error_returns_review_passed_true(self, monkeypatch):
        """When get_anthropic_client() raises, review_passed should be True (no pipeline block)."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("stages.code_review.get_anthropic_client", side_effect=RuntimeError("auth failed")), \
             patch("dashboard.heartbeat.emit_heartbeat"):
            from stages.code_review import run_code_review
            result = run_code_review(_make_state())

        assert result["review_passed"] is True

    def test_api_error_increments_review_iteration(self, monkeypatch):
        """Even on error, review_iteration should be incremented by 1."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("stages.code_review.get_anthropic_client", side_effect=ConnectionError("network")), \
             patch("dashboard.heartbeat.emit_heartbeat"):
            from stages.code_review import run_code_review
            result = run_code_review(_make_state(review_iteration=0))

        assert result["review_iteration"] == 1

    def test_api_error_returns_empty_findings(self, monkeypatch):
        """On error, review_findings should be an empty list."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("stages.code_review.get_anthropic_client", side_effect=Exception("boom")), \
             patch("dashboard.heartbeat.emit_heartbeat"):
            from stages.code_review import run_code_review
            result = run_code_review(_make_state())

        assert result["review_findings"] == []

    def test_api_error_summary_mentions_error(self, monkeypatch):
        """On error, review_summary should indicate that an error occurred."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("stages.code_review.get_anthropic_client", side_effect=ValueError("bad config")), \
             patch("dashboard.heartbeat.emit_heartbeat"):
            from stages.code_review import run_code_review
            result = run_code_review(_make_state())

        summary = result["review_summary"].lower()
        assert "error" in summary or "proceeding" in summary

    def test_api_error_result_has_all_required_keys(self, monkeypatch):
        """Error path must still return all four required keys."""
        monkeypatch.delenv("DRY_RUN", raising=False)

        with patch("stages.code_review.get_anthropic_client", side_effect=Exception("fail")), \
             patch("dashboard.heartbeat.emit_heartbeat"):
            from stages.code_review import run_code_review
            result = run_code_review(_make_state())

        for key in ("review_passed", "review_findings", "review_summary", "review_iteration"):
            assert key in result


# ── validate_review_output ────────────────────────────────────────────────────


class TestValidateReviewOutput:
    """Tests for validate_review_output from agents/validators.py."""

    @pytest.fixture(autouse=True)
    def import_validator(self):
        from stages.validators import validate_review_output
        self._validate = validate_review_output

    def _make_review_state(self, **overrides: Any) -> dict:
        base = {
            "review_passed": True,
            "review_findings": [],
            "review_summary": "Code review complete: 0 finding(s) | PASS",
            "review_iteration": 1,
        }
        base.update(overrides)
        return base

    def test_passing_review_validation_result_passed_true(self):
        """Passing review should yield ValidationResult.passed=True."""
        state = self._make_review_state(review_passed=True)
        result = self._validate(state)
        assert result.passed is True

    def test_passing_review_no_warnings(self):
        """Passing review should produce no warnings."""
        state = self._make_review_state(review_passed=True)
        result = self._validate(state)
        assert result.warnings == []

    def test_failing_review_validation_result_still_passed_true(self):
        """Failing review must still yield ValidationResult.passed=True (no pipeline block)."""
        state = self._make_review_state(
            review_passed=False,
            review_summary="Code review: 1 blocking | FAIL",
            review_findings=["[BLOCKING] SECURITY: Bad thing"],
            review_iteration=1,
        )
        result = self._validate(state)
        assert result.passed is True

    def test_failing_review_produces_warning(self):
        """Failing review should produce at least one warning message."""
        state = self._make_review_state(
            review_passed=False,
            review_summary="Code review: 1 blocking | FAIL",
            review_findings=["[BLOCKING] SECURITY: Missing validation"],
            review_iteration=1,
        )
        result = self._validate(state)
        assert len(result.warnings) >= 1

    def test_failing_review_warning_contains_summary(self):
        """The warning for a failed review should include the review_summary text."""
        summary = "Code review complete: 1 finding(s) | 1 blocking | FAIL"
        state = self._make_review_state(
            review_passed=False,
            review_summary=summary,
            review_iteration=1,
        )
        result = self._validate(state)
        assert summary in result.warnings[0]

    def test_max_iterations_reached_with_failing_review_adds_warning(self, monkeypatch):
        """When review_iteration >= MAX_REVIEW_ITERATIONS and review_passed=False, an extra warning is added."""
        monkeypatch.setenv("MAX_REVIEW_ITERATIONS", "3")
        state = self._make_review_state(
            review_passed=False,
            review_summary="Code review: blocking | FAIL",
            review_iteration=3,
        )
        result = self._validate(state)
        max_iter_warning = any("max" in w.lower() or "3" in w for w in result.warnings)
        assert max_iter_warning

    def test_max_iterations_warning_mentions_iteration_count(self, monkeypatch):
        """Max iterations warning should mention the configured max count."""
        monkeypatch.setenv("MAX_REVIEW_ITERATIONS", "3")
        state = self._make_review_state(
            review_passed=False,
            review_summary="Code review: blocking | FAIL",
            review_iteration=3,
        )
        result = self._validate(state)
        all_warnings = " ".join(result.warnings)
        assert "3" in all_warnings

    def test_validate_review_output_phase_is_code_review(self):
        """ValidationResult.phase should be 'code_review'."""
        state = self._make_review_state()
        result = self._validate(state)
        assert result.phase == "code_review"

    def test_validate_review_output_summary_contains_verdict(self):
        """ValidationResult.summary should contain review verdict info."""
        state = self._make_review_state(review_passed=True)
        result = self._validate(state)
        assert "Review verdict" in result.summary or "PASS" in str(result.summary)

    def test_validate_review_output_summary_contains_iteration(self):
        """ValidationResult.summary should include the iteration number."""
        state = self._make_review_state(review_passed=True, review_iteration=2)
        result = self._validate(state)
        assert 2 in result.summary.values() or "2" in str(result.summary)

    def test_validate_review_output_iteration_below_max_no_extra_warning(self, monkeypatch):
        """When review_iteration < MAX_REVIEW_ITERATIONS, no max-iterations warning is added."""
        monkeypatch.setenv("MAX_REVIEW_ITERATIONS", "3")
        state = self._make_review_state(
            review_passed=False,
            review_summary="FAIL",
            review_iteration=1,
        )
        result = self._validate(state)
        max_warnings = [w for w in result.warnings if "max" in w.lower()]
        assert len(max_warnings) == 0


# ── Mock responses ────────────────────────────────────────────────────────────


class TestMockResponses:
    """Tests for MOCK_CODE_REVIEW_PASS, MOCK_CODE_REVIEW_FAIL, and get_mock_response."""

    def test_get_mock_response_code_review_returns_pass_mock(self):
        """get_mock_response('code_review') should return MOCK_CODE_REVIEW_PASS."""
        from config.mock_responses import MOCK_CODE_REVIEW_PASS, get_mock_response
        result = get_mock_response("code_review")
        assert result == MOCK_CODE_REVIEW_PASS

    def test_mock_code_review_pass_has_review_passed_true(self):
        """MOCK_CODE_REVIEW_PASS must have review_passed=True."""
        from config.mock_responses import MOCK_CODE_REVIEW_PASS
        assert MOCK_CODE_REVIEW_PASS["review_passed"] is True

    def test_mock_code_review_pass_has_review_findings_key(self):
        """MOCK_CODE_REVIEW_PASS must have 'review_findings' as a list."""
        from config.mock_responses import MOCK_CODE_REVIEW_PASS
        assert "review_findings" in MOCK_CODE_REVIEW_PASS
        assert isinstance(MOCK_CODE_REVIEW_PASS["review_findings"], list)

    def test_mock_code_review_pass_has_review_summary_key(self):
        """MOCK_CODE_REVIEW_PASS must have 'review_summary' as a string."""
        from config.mock_responses import MOCK_CODE_REVIEW_PASS
        assert "review_summary" in MOCK_CODE_REVIEW_PASS
        assert isinstance(MOCK_CODE_REVIEW_PASS["review_summary"], str)

    def test_mock_code_review_pass_summary_contains_pass(self):
        """MOCK_CODE_REVIEW_PASS review_summary should indicate PASS."""
        from config.mock_responses import MOCK_CODE_REVIEW_PASS
        assert "PASS" in MOCK_CODE_REVIEW_PASS["review_summary"]

    def test_mock_code_review_fail_has_review_passed_false(self):
        """MOCK_CODE_REVIEW_FAIL must have review_passed=False."""
        from config.mock_responses import MOCK_CODE_REVIEW_FAIL
        assert MOCK_CODE_REVIEW_FAIL["review_passed"] is False

    def test_mock_code_review_fail_has_findings(self):
        """MOCK_CODE_REVIEW_FAIL must have at least one finding."""
        from config.mock_responses import MOCK_CODE_REVIEW_FAIL
        assert len(MOCK_CODE_REVIEW_FAIL["review_findings"]) >= 1

    def test_mock_code_review_fail_has_blocking_finding(self):
        """MOCK_CODE_REVIEW_FAIL findings should include a [BLOCKING] entry."""
        from config.mock_responses import MOCK_CODE_REVIEW_FAIL
        blocking = [f for f in MOCK_CODE_REVIEW_FAIL["review_findings"] if "[BLOCKING]" in f]
        assert len(blocking) >= 1

    def test_mock_code_review_fail_summary_contains_fail(self):
        """MOCK_CODE_REVIEW_FAIL review_summary should indicate FAIL."""
        from config.mock_responses import MOCK_CODE_REVIEW_FAIL
        assert "FAIL" in MOCK_CODE_REVIEW_FAIL["review_summary"]

    def test_get_mock_response_unknown_type_raises_value_error(self):
        """get_mock_response with unknown agent type should raise ValueError."""
        from config.mock_responses import get_mock_response
        with pytest.raises(ValueError, match="Unknown agent type"):
            get_mock_response("nonexistent_agent")

    def test_mock_code_review_pass_has_three_required_keys_only(self):
        """MOCK_CODE_REVIEW_PASS should have the three keys expected by run_code_review callers."""
        from config.mock_responses import MOCK_CODE_REVIEW_PASS
        for key in ("review_passed", "review_findings", "review_summary"):
            assert key in MOCK_CODE_REVIEW_PASS

    def test_mock_code_review_fail_has_three_required_keys(self):
        """MOCK_CODE_REVIEW_FAIL should have the three core keys."""
        from config.mock_responses import MOCK_CODE_REVIEW_FAIL
        for key in ("review_passed", "review_findings", "review_summary"):
            assert key in MOCK_CODE_REVIEW_FAIL


# ── Main entrypoint ───────────────────────────────────────────────────────────


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
