"""Output sanitizer — strips PII from all output channels (logs, files, heartbeats).

Layer 3 in the protection stack (after PII Redactor and Prompt Guard).
Works in conjunction with tools/pii_redactor.py — shares the same regex patterns
but applies them to output channels rather than input data.

Usage::

    from tools.output_sanitizer import sanitize, sanitize_dict, SanitizingFilter

    # Sanitize a plain string before writing to a file
    safe_content = sanitize(content, source="agent:test_plan_md")

    # Sanitize an entire dict before sending as a heartbeat payload
    safe_payload = sanitize_dict(raw_state, source="heartbeat:raw_state")

    # Install the logging filter so all log messages are sanitized automatically
    import logging
    logging.getLogger("my_agent").addFilter(SanitizingFilter())
"""

import logging
import os
from typing import Any

from tools.pii_redactor import _redact_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_sanitizer_enabled() -> bool:
    """Return whether the output sanitizer is active.

    Reads the ``OUTPUT_SANITIZER_ENABLED`` environment variable (default
    ``"true"``).  Set it to ``"false"`` to bypass sanitization during local
    development.

    Returns:
        ``False`` only when the variable is explicitly set to ``"false"``
        (case-insensitive); ``True`` in all other cases.
    """
    return os.getenv("OUTPUT_SANITIZER_ENABLED", "true").lower() != "false"


def sanitize(text: str, source: str = "output") -> str:
    """Strip PII from a text string for safe output to logs, files, or heartbeats.

    Reuses the same regex patterns as :func:`tools.pii_redactor._redact_text`
    so IPv4/IPv6 addresses, email addresses, phone numbers, and internal
    hostnames are all redacted in the same way as the input layer.

    Args:
        text: The string to sanitize.  Non-string values are returned unchanged.
        source: A label used in audit log messages (e.g. ``"testing_agent:test_plan_md"``).

    Returns:
        Sanitized string.  If the sanitizer is disabled or *text* is not a
        string, the original value is returned unchanged.
    """
    if not is_sanitizer_enabled():
        return text
    if not isinstance(text, str):
        return text  # type: ignore[return-value]
    sanitized, counts = _redact_text(text, source)
    active = {k: v for k, v in counts.items() if v > 0}
    if active:
        logger.info(
            "output_sanitizer: redacted %s from [%s]",
            active,
            source,
        )
    return sanitized


def _sanitize_list(items: list, source: str) -> list:
    """Recursively sanitize a list, handling strings, dicts, and nested lists.

    Args:
        items: The list to sanitize.
        source: A label prefix used in audit log messages.

    Returns:
        A new list with PII removed from all string values.
    """
    sanitized = []
    for i, item in enumerate(items):
        item_source = f"{source}[{i}]"
        if isinstance(item, str):
            sanitized.append(sanitize(item, source=item_source))
        elif isinstance(item, dict):
            sanitized.append(sanitize_dict(item, source=item_source))
        elif isinstance(item, list):
            sanitized.append(_sanitize_list(item, source=item_source))
        else:
            sanitized.append(item)
    return sanitized


def sanitize_dict(data: dict[str, Any], source: str = "output") -> dict[str, Any]:
    """Recursively strip PII from all string values in a dict.

    The original dict is **never** mutated; a new dict is returned.  Lists
    of strings and dicts are also recursively sanitized.  Non-string scalar
    values (int, float, bool, None, …) are copied through unchanged.

    Args:
        data: The dictionary to sanitize.  Non-dict values are returned
            unchanged.
        source: A label prefix used in audit log messages.  Nested keys and
            list indices are appended automatically (e.g. ``"heartbeat:raw_state:field_name"``).

    Returns:
        A new dict with PII removed from all string values.
    """
    if not is_sanitizer_enabled():
        return data
    if not isinstance(data, dict):
        return data  # type: ignore[return-value]
    result: dict[str, Any] = {}
    for key, value in data.items():
        field_source = f"{source}:{key}"
        if isinstance(value, str):
            result[key] = sanitize(value, source=field_source)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, source=field_source)
        elif isinstance(value, list):
            result[key] = _sanitize_list(value, source=f"{field_source}")
        else:
            result[key] = value
    return result


class SanitizingFilter(logging.Filter):
    """Logging filter that strips PII from all log messages before persistence.

    Attach this filter to any :class:`logging.Handler` to ensure that PII
    (IP addresses, email addresses, phone numbers, internal hostnames) is
    redacted from log records before they are written to files or any other
    sink.

    Example::

        handler = logging.FileHandler("agent.log")
        handler.addFilter(SanitizingFilter())

    The filter always returns ``True`` so that log records are never dropped —
    it only mutates the message.  If sanitization raises an unexpected
    exception the record is passed through unmodified so that logging is
    never disrupted.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize the log record message in-place.

        Args:
            record: The log record to sanitize.

        Returns:
            Always ``True`` — the record is always emitted.
        """
        if is_sanitizer_enabled():
            try:
                # Pre-format so %-placeholders are resolved before sanitisation
                try:
                    formatted = record.getMessage()
                except Exception:
                    formatted = str(record.msg)
                record.msg = sanitize(formatted, source=f"log:{record.name}")
                record.args = ()  # prevent double %-formatting after sanitisation
            except Exception:
                pass  # never break logging
        return True


__all__ = ["sanitize", "sanitize_dict", "SanitizingFilter", "is_sanitizer_enabled"]
