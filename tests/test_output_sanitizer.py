"""Unit tests for the output sanitizer layer.

Covers:
- tools/output_sanitizer.py  (sanitize, sanitize_dict, SanitizingFilter, is_sanitizer_enabled)
- Integration: heartbeat payload sanitization (dashboard/heartbeat.py)
- Integration: file write sanitization (stages/test.py)

No real API calls are made.  All filesystem and HTTP interactions are mocked
via unittest.mock.patch.  Environment variable overrides are applied with
pytest's monkeypatch fixture so they are automatically restored after each test.
"""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from tools.output_sanitizer import (
    SanitizingFilter,
    is_sanitizer_enabled,
    sanitize,
    sanitize_dict,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_sanitizer_enabled(monkeypatch):
    """Ensure OUTPUT_SANITIZER_ENABLED is unset (defaults to true) before every test."""
    monkeypatch.delenv("OUTPUT_SANITIZER_ENABLED", raising=False)
    yield


# ---------------------------------------------------------------------------
# TestIsSanitizerEnabled
# ---------------------------------------------------------------------------


class TestIsSanitizerEnabled:
    """Tests for is_sanitizer_enabled() env-var gate."""

    def test_enabled_by_default(self):
        assert is_sanitizer_enabled() is True

    def test_enabled_when_set_to_true(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "true")
        assert is_sanitizer_enabled() is True

    def test_enabled_when_set_to_TRUE_uppercase(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "TRUE")
        assert is_sanitizer_enabled() is True

    def test_disabled_when_set_to_false(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "false")
        assert is_sanitizer_enabled() is False

    def test_disabled_when_set_to_FALSE_uppercase(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "FALSE")
        assert is_sanitizer_enabled() is False

    def test_enabled_for_any_other_value(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "yes")
        assert is_sanitizer_enabled() is True


# ---------------------------------------------------------------------------
# TestSanitizeText
# ---------------------------------------------------------------------------


class TestSanitizeText:
    """Tests for sanitize() on plain text strings."""

    def test_ipv4_is_redacted(self):
        result = sanitize("Server at 192.168.1.100 is down", source="test")
        assert "192.168.1.100" not in result
        assert "[IP_REDACTED]" in result

    def test_email_is_redacted(self):
        result = sanitize("Contact user@internal.corp for help", source="test")
        assert "user@internal.corp" not in result
        assert "[EMAIL_REDACTED]" in result

    def test_hostname_is_redacted(self):
        result = sanitize("Connect to db-prod.internal", source="test")
        assert "db-prod.internal" not in result
        assert "[HOSTNAME_REDACTED]" in result

    def test_non_pii_text_unchanged(self):
        text = "Build completed successfully in 3 seconds."
        assert sanitize(text, source="test") == text

    def test_allowlisted_domain_preserved(self):
        # github.com is on the public allowlist and must be preserved
        text = "See https://github.com/org/repo for details"
        result = sanitize(text, source="test")
        assert "github.com" in result

    def test_non_string_passed_through(self):
        assert sanitize(None, source="test") is None  # type: ignore[arg-type]
        assert sanitize(42, source="test") == 42  # type: ignore[arg-type]

    def test_empty_string_unchanged(self):
        assert sanitize("", source="test") == ""

    def test_multiple_pii_items_all_redacted(self):
        text = "User admin@corp.local at 10.0.0.1 called from (555) 867-5309"
        result = sanitize(text, source="test")
        assert "admin@corp.local" not in result
        assert "10.0.0.1" not in result

    def test_default_source_label(self):
        # Should not raise — default source="output" is used
        result = sanitize("hello 1.2.3.4 world")
        assert "[IP_REDACTED]" in result


# ---------------------------------------------------------------------------
# TestSanitizerDisabled
# ---------------------------------------------------------------------------


class TestSanitizerDisabled:
    """Tests that disabled sanitizer passes data through unchanged."""

    def test_sanitize_passthrough_when_disabled(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "false")
        text = "Server 192.168.0.1 and user admin@corp.local"
        assert sanitize(text, source="test") == text

    def test_sanitize_dict_passthrough_when_disabled(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "false")
        data = {"ip": "10.0.0.1", "email": "admin@secret.corp"}
        assert sanitize_dict(data, source="test") is data

    def test_sanitizing_filter_passthrough_when_disabled(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "false")
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="IP is 192.168.1.1",
            args=("extra_arg",),
            exc_info=None,
        )
        f = SanitizingFilter()
        result = f.filter(record)
        assert result is True
        # Message should be untouched
        assert "192.168.1.1" in record.msg
        # args should NOT have been cleared
        assert record.args == ("extra_arg",)


# ---------------------------------------------------------------------------
# TestSanitizeDict
# ---------------------------------------------------------------------------


class TestSanitizeDict:
    """Tests for sanitize_dict() on structured data."""

    def test_flat_dict_string_values_redacted(self):
        data = {"host": "db.internal", "note": "safe text"}
        result = sanitize_dict(data, source="test")
        assert "[HOSTNAME_REDACTED]" in result["host"]
        assert result["note"] == "safe text"

    def test_original_dict_not_mutated(self):
        data = {"ip": "192.168.0.1"}
        result = sanitize_dict(data, source="test")
        assert data["ip"] == "192.168.0.1"  # original untouched
        assert "[IP_REDACTED]" in result["ip"]

    def test_non_string_values_preserved(self):
        data = {"count": 42, "flag": True, "nothing": None, "ratio": 3.14}
        result = sanitize_dict(data, source="test")
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["nothing"] is None
        assert result["ratio"] == 3.14

    def test_nested_dict_recursively_sanitized(self):
        data = {
            "outer": "safe",
            "inner": {
                "deep": {
                    "ip": "10.1.2.3"
                }
            },
        }
        result = sanitize_dict(data, source="test")
        assert result["outer"] == "safe"
        assert "[IP_REDACTED]" in result["inner"]["deep"]["ip"]

    def test_list_of_strings_sanitized(self):
        data = {"hosts": ["192.168.1.1", "safe-host", "admin@corp.local"]}
        result = sanitize_dict(data, source="test")
        assert "[IP_REDACTED]" in result["hosts"][0]
        assert result["hosts"][1] == "safe-host"
        assert "[EMAIL_REDACTED]" in result["hosts"][2]

    def test_list_of_dicts_sanitized(self):
        data = {
            "servers": [
                {"ip": "10.0.0.1", "name": "server-a"},
                {"ip": "10.0.0.2", "name": "server-b"},
            ]
        }
        result = sanitize_dict(data, source="test")
        assert "[IP_REDACTED]" in result["servers"][0]["ip"]
        assert "[IP_REDACTED]" in result["servers"][1]["ip"]
        assert result["servers"][0]["name"] == "server-a"

    def test_list_with_mixed_types_non_str_unchanged(self):
        data = {"mixed": [1, "192.168.0.1", True, None]}
        result = sanitize_dict(data, source="test")
        assert result["mixed"][0] == 1
        assert "[IP_REDACTED]" in result["mixed"][1]
        assert result["mixed"][2] is True
        assert result["mixed"][3] is None

    def test_non_dict_input_returned_unchanged(self):
        assert sanitize_dict("not a dict", source="test") == "not a dict"  # type: ignore[arg-type]
        assert sanitize_dict(42, source="test") == 42  # type: ignore[arg-type]

    def test_empty_dict_returns_empty_dict(self):
        assert sanitize_dict({}, source="test") == {}

    def test_sanitize_dict_nested_list_of_lists(self, monkeypatch):
        """Nested lists of lists must be recursed into."""
        monkeypatch.setenv("OUTPUT_SANITIZER_ENABLED", "true")
        data = {"matrix": [["10.0.0.1", "safe-value"], ["admin@corp.local", 42]]}
        result = sanitize_dict(data, source="test")
        assert result["matrix"][0][0] == "[IP_REDACTED]"
        assert result["matrix"][0][1] == "safe-value"
        assert "[EMAIL_REDACTED]" in result["matrix"][1][0]
        assert result["matrix"][1][1] == 42  # int passthrough


# ---------------------------------------------------------------------------
# TestSanitizeDictPreservesNonString
# ---------------------------------------------------------------------------


class TestSanitizeDictPreservesNonString:
    """Dedicated coverage for non-string scalar pass-through."""

    def test_integer_preserved(self):
        result = sanitize_dict({"x": 0}, source="t")
        assert result["x"] == 0

    def test_bool_true_preserved(self):
        result = sanitize_dict({"x": True}, source="t")
        assert result["x"] is True

    def test_bool_false_preserved(self):
        result = sanitize_dict({"x": False}, source="t")
        assert result["x"] is False

    def test_none_preserved(self):
        result = sanitize_dict({"x": None}, source="t")
        assert result["x"] is None

    def test_float_preserved(self):
        result = sanitize_dict({"x": 2.718}, source="t")
        assert result["x"] == pytest.approx(2.718)


# ---------------------------------------------------------------------------
# TestSanitizeDictRecursive
# ---------------------------------------------------------------------------


class TestSanitizeDictRecursive:
    """Deeply nested dict sanitization."""

    def test_five_levels_deep(self):
        data = {"l1": {"l2": {"l3": {"l4": {"l5": "email@deep.internal"}}}}}
        result = sanitize_dict(data, source="test")
        assert "[EMAIL_REDACTED]" in result["l1"]["l2"]["l3"]["l4"]["l5"]

    def test_sibling_keys_both_sanitized(self):
        data = {
            "a": "192.168.1.1",
            "b": "admin@corp.local",
        }
        result = sanitize_dict(data, source="test")
        assert "[IP_REDACTED]" in result["a"]
        assert "[EMAIL_REDACTED]" in result["b"]


# ---------------------------------------------------------------------------
# TestSanitizingFilter
# ---------------------------------------------------------------------------


class TestSanitizingFilter:
    """Tests for the SanitizingFilter logging.Filter subclass."""

    def _make_record(self, msg: str, args: Any = None) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=args or (),
            exc_info=None,
        )
        return record

    def test_filter_always_returns_true(self):
        f = SanitizingFilter()
        record = self._make_record("hello world")
        assert f.filter(record) is True

    def test_pii_in_message_is_redacted(self):
        f = SanitizingFilter()
        record = self._make_record("Connected to 10.0.0.5")
        f.filter(record)
        assert "10.0.0.5" not in record.msg
        assert "[IP_REDACTED]" in record.msg

    def test_email_in_message_is_redacted(self):
        f = SanitizingFilter()
        record = self._make_record("Sent to user@internal.corp")
        f.filter(record)
        assert "user@internal.corp" not in record.msg
        assert "[EMAIL_REDACTED]" in record.msg

    def test_args_are_cleared_to_prevent_bypass(self):
        f = SanitizingFilter()
        record = self._make_record("value is %s", args=("192.168.1.1",))
        f.filter(record)
        assert record.args == ()

    def test_clean_message_unchanged(self):
        f = SanitizingFilter()
        record = self._make_record("Build completed in 5 seconds")
        f.filter(record)
        assert record.msg == "Build completed in 5 seconds"

    def test_non_string_msg_converted_and_sanitized(self):
        f = SanitizingFilter()
        record = self._make_record.__func__(self, 12345)  # type: ignore[attr-defined]
        # Build the record manually with a non-string msg
        record2 = logging.LogRecord(
            name="t", level=logging.INFO,
            pathname="", lineno=0,
            msg=42,
            args=(),
            exc_info=None,
        )
        result = f.filter(record2)
        assert result is True
        # msg should now be the string representation
        assert isinstance(record2.msg, str)

    def test_args_merged_into_msg_before_clearing(self):
        """Pre-format record before sanitising so %-placeholders are resolved first."""
        f = SanitizingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="server is %s and ip is %s",
            args=("myserver", "10.0.0.1"),
            exc_info=None,
        )
        f.filter(record)
        msg = record.getMessage()  # args are now () so this just returns record.msg
        assert "10.0.0.1" not in msg
        assert "[IP_REDACTED]" in msg
        assert record.args == ()

    def test_filter_integration_with_handler(self):
        """SanitizingFilter attached to a handler redacts log output."""
        handler = logging.StreamHandler()
        handler.addFilter(SanitizingFilter())

        test_logger = logging.getLogger("sanitizer_test_handler")
        test_logger.handlers = []
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        # Just verify no exception is raised and message is processed
        test_logger.info("IP is 192.168.99.1 and email is admin@corp.local")
        # (We cannot easily intercept StreamHandler output in this test, but
        # the filter is tested directly in other tests above.)


# ---------------------------------------------------------------------------
# TestSanitizingFilterSafe
# ---------------------------------------------------------------------------


class TestSanitizingFilterSafe:
    """Tests that SanitizingFilter never raises, even on pathological input."""

    def test_filter_survives_exception_in_sanitize(self, monkeypatch):
        """If sanitize() raises, the filter must still return True."""
        import tools.output_sanitizer as mod

        def _boom(text, source="output"):
            raise RuntimeError("unexpected error")

        monkeypatch.setattr(mod, "sanitize", _boom)

        f = SanitizingFilter()
        record = logging.LogRecord(
            name="t", level=logging.INFO,
            pathname="", lineno=0,
            msg="some message",
            args=(),
            exc_info=None,
        )
        # Must not raise
        result = f.filter(record)
        assert result is True

    def test_filter_on_empty_message(self):
        f = SanitizingFilter()
        record = logging.LogRecord(
            name="t", level=logging.INFO,
            pathname="", lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        result = f.filter(record)
        assert result is True
        assert record.msg == ""


# ---------------------------------------------------------------------------
# TestSanitizerIdempotent
# ---------------------------------------------------------------------------


class TestSanitizerIdempotent:
    """Already-redacted placeholders must not be double-redacted."""

    def test_ip_placeholder_unchanged(self):
        text = "Server at [IP_REDACTED] is unreachable"
        result = sanitize(text, source="test")
        assert result == text

    def test_email_placeholder_unchanged(self):
        text = "Contact [EMAIL_REDACTED] for support"
        result = sanitize(text, source="test")
        assert result == text

    def test_hostname_placeholder_unchanged(self):
        text = "Host [HOSTNAME_REDACTED] timed out"
        result = sanitize(text, source="test")
        assert result == text

    def test_idempotent_on_dict(self):
        data = {"ip": "[IP_REDACTED]", "note": "clean"}
        result = sanitize_dict(data, source="test")
        assert result["ip"] == "[IP_REDACTED]"
        assert result["note"] == "clean"


# ---------------------------------------------------------------------------
# TestHeartbeatIntegration
# ---------------------------------------------------------------------------


class TestHeartbeatIntegration:
    """Integration tests: heartbeat emit() sanitizes raw_state before POST."""

    def test_raw_state_pii_sanitized_before_post(self):
        from dashboard.heartbeat import Heartbeat, HeartbeatConfig, HeartbeatEmitter

        raw_state = {
            "session_id": "abc-123",
            "server_ip": "10.0.0.5",
            "user_email": "admin@corp.internal",
            "phase": "design_complete",
        }

        heartbeat = Heartbeat(
            session_id="abc-123",
            agent="design",
            phase="design_complete",
            raw_state=raw_state,
        )

        config = HeartbeatConfig(enabled=True)

        captured_payload: dict = {}

        def _fake_post(url, json=None, timeout=None):
            captured_payload.update(json or {})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        emitter = HeartbeatEmitter(config=config)

        with patch("dashboard.heartbeat.requests.post", side_effect=_fake_post):
            emitter.emit(heartbeat)

        sent_state = captured_payload.get("raw_state", {})
        assert "10.0.0.5" not in sent_state.get("server_ip", "")
        assert "[IP_REDACTED]" in sent_state.get("server_ip", "")
        assert "admin@corp.internal" not in sent_state.get("user_email", "")
        assert "[EMAIL_REDACTED]" in sent_state.get("user_email", "")
        # Non-PII fields should pass through
        assert sent_state.get("session_id") == "abc-123"
        assert sent_state.get("phase") == "design_complete"

    def test_raw_state_without_pii_unchanged(self):
        from dashboard.heartbeat import Heartbeat, HeartbeatConfig, HeartbeatEmitter

        raw_state = {
            "phase": "testing_complete",
            "status": "success",
            "count": 5,
        }

        heartbeat = Heartbeat(
            session_id="xyz-999",
            agent="testing",
            phase="testing_complete",
            raw_state=raw_state,
        )

        config = HeartbeatConfig(enabled=True)
        captured_payload: dict = {}

        def _fake_post(url, json=None, timeout=None):
            captured_payload.update(json or {})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        emitter = HeartbeatEmitter(config=config)

        with patch("dashboard.heartbeat.requests.post", side_effect=_fake_post):
            emitter.emit(heartbeat)

        sent_state = captured_payload.get("raw_state", {})
        assert sent_state["phase"] == "testing_complete"
        assert sent_state["status"] == "success"
        assert sent_state["count"] == 5

    def test_emit_disabled_skips_post(self):
        from dashboard.heartbeat import Heartbeat, HeartbeatConfig, HeartbeatEmitter

        config = HeartbeatConfig(enabled=False)
        emitter = HeartbeatEmitter(config=config)
        heartbeat = Heartbeat(
            session_id="s1", agent="docs", phase="docs_complete",
            raw_state={"ip": "10.0.0.1"},
        )

        with patch("dashboard.heartbeat.requests.post") as mock_post:
            result = emitter.emit(heartbeat)

        mock_post.assert_not_called()
        assert result is False

    def test_raw_state_none_value_skips_sanitize(self):
        """If raw_state is not a dict, emit() should not call sanitize_dict."""
        from dashboard.heartbeat import Heartbeat, HeartbeatConfig, HeartbeatEmitter

        heartbeat = Heartbeat(
            session_id="s2", agent="design", phase="design_complete",
            raw_state={"nested": None, "ip": "10.0.1.2"},
        )
        config = HeartbeatConfig(enabled=True)
        emitter = HeartbeatEmitter(config=config)

        captured: dict = {}

        def _fake_post(url, json=None, timeout=None):
            captured.update(json or {})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp

        with patch("dashboard.heartbeat.requests.post", side_effect=_fake_post):
            emitter.emit(heartbeat)

        sent_state = captured.get("raw_state", {})
        assert sent_state["nested"] is None
        assert "[IP_REDACTED]" in sent_state["ip"]


# ---------------------------------------------------------------------------
# TestFileWriteIntegration
# ---------------------------------------------------------------------------


class TestFileWriteIntegration:
    """Integration tests: testing_agent write functions sanitize file content."""

    def test_write_test_plan_md_sanitizes_content(self, tmp_path):
        """_write_test_plan_md should sanitize PII in the generated content."""
        from stages.test import _write_test_plan_md

        output = {
            "issue_title": "Add timeout support",
            "test_plan": "Testing plan for server at 192.168.1.5",
            "test_specifications": {},
            "unit_tests": {},
            "integration_tests": {},
            "e2e_tests": {},
            "coverage_analysis": "Contact admin@corp.local for info",
            "patterns_detected": {},
        }

        _write_test_plan_md(output, tmp_path)

        md_path = tmp_path / "test_plan.md"
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "192.168.1.5" not in content
        assert "[IP_REDACTED]" in content
        assert "admin@corp.local" not in content
        assert "[EMAIL_REDACTED]" in content

    def test_write_go_test_files_sanitizes_code(self, tmp_path):
        """_write_go_test_files should sanitize PII embedded in generated Go code."""
        from stages.test import _write_go_test_files

        go_code_with_pii = (
            "package mytest\n\n"
            "// Server endpoint: 10.0.0.99\n"
            "// Contact: dev@corp.internal\n"
            "func TestSomething(t *testing.T) {}\n"
        )

        output = {
            "unit_tests": {"pkg/foo/foo_test.go": go_code_with_pii},
            "integration_tests": {},
            "e2e_tests": {},
        }

        _write_go_test_files(output, tmp_path)

        dest = tmp_path / "tests" / "unit" / "pkg" / "foo" / "foo_test.go"
        assert dest.exists()
        content = dest.read_text(encoding="utf-8")
        assert "10.0.0.99" not in content
        assert "[IP_REDACTED]" in content
        assert "dev@corp.internal" not in content
        assert "[EMAIL_REDACTED]" in content

    def test_write_test_plan_md_clean_content_unchanged(self, tmp_path):
        """Content with no PII must not be altered."""
        from stages.test import _write_test_plan_md

        output = {
            "issue_title": "Timeout feature",
            "test_plan": "Standard timeout test plan",
            "test_specifications": {},
            "unit_tests": {},
            "integration_tests": {},
            "e2e_tests": {},
            "coverage_analysis": "100% coverage of all criteria",
            "patterns_detected": {},
        }

        _write_test_plan_md(output, tmp_path)

        content = (tmp_path / "test_plan.md").read_text(encoding="utf-8")
        assert "Standard timeout test plan" in content
        assert "100% coverage of all criteria" in content
