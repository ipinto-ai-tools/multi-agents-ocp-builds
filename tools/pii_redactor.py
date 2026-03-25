"""PII redaction layer for Jira ticket and GitHub PR data.

Strips personally identifiable information from the structured dicts returned
by JiraClient and GitHubClient before they are passed into the agent pipeline.

Two categories of redaction are applied:

1. **Personal name fields** — ``reporter``, ``assignee``, ``author``, and
   ``reviewers`` are replaced wholesale with placeholder strings.  No regex
   inspection is required; the field values are always names.

2. **Free-text fields** — ``summary``, ``description``, ``title``, ``body``,
   ``comments``, and ``acceptance_criteria`` are scanned with regex patterns
   that detect IPv4/IPv6 addresses, email addresses, phone numbers, and
   internal hostnames.  Matches that belong to the public-domain allowlist
   (e.g. ``github.com`` URLs) are left intact.

Redaction can be disabled entirely for local development by setting the
environment variable ``PII_REDACTION_ENABLED=false``.

Usage::

    from tools.pii_redactor import redact_pii

    clean_ticket = redact_pii(raw_ticket, source="SHIP-123")
    clean_pr = redact_pii(raw_pr, source="github-pr-1234")
"""

import os
import re
import logging
from typing import Any

from config.redaction_config import PUBLIC_DOMAIN_ALLOWLIST

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# IPv4: matches dotted-quad addresses (e.g. 192.168.1.1)
_IPV4_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')

# IPv6: matches full and compressed forms (including ::1, fe80::1, 2001:db8::1)
_IPV6_RE = re.compile(
    r'\b('
    r'(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}'           # full 8 groups
    r'|(?:[0-9a-fA-F]{1,4}:){1,7}:'                         # trailing ::
    r'|:(?::[0-9a-fA-F]{1,4}){1,7}'                         # leading ::
    r'|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}'        # 6 groups + ::1
    r'|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}'
    r'|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}'
    r'|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}'
    r'|::(?:[fF]{4}(?::0{1,4})?:)?(?:\d{1,3}\.){3}\d{1,3}' # IPv4-mapped
    r'|::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}'       # :: prefix
    r'|[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}'
    r')\b'
)

# Email addresses
_EMAIL_RE = re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b')

# Phone numbers (international + US formats)
_PHONE_RE = re.compile(
    r'\b(?:\+\d{1,3}[\s\-]?)?'
    r'(?:\(?\d{3}\)?[\s\-]?)'
    r'\d{3}[\s\-]?\d{4}\b'
)

# Internal hostnames: one or more label segments followed by a TLD or
# well-known internal suffix.  Matches things like ``prod-db-01.internal``
# and ``server.company.net`` but NOT bare words.
_HOSTNAME_RE = re.compile(
    r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)'
    r'+(?:internal|local|corp|intranet|lan|[a-zA-Z]{2,6})\b'
)

# Placeholder tokens used in redacted output
_REDACTED_IP = "[IP_REDACTED]"
_REDACTED_EMAIL = "[EMAIL_REDACTED]"
_REDACTED_PHONE = "[PHONE_REDACTED]"
_REDACTED_HOSTNAME = "[HOSTNAME_REDACTED]"
_REDACTED_PERSON = "[CUSTOMER_REDACTED]"

# Track whether the "redaction disabled" warning has been emitted so we only
# log it once per process lifetime.
_redaction_disabled_warned = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_allowlisted(text: str) -> bool:
    """Return True if *text* equals or ends with a domain from the public allowlist.

    A suffix match requires a leading dot so that ``evil-github.com.corp`` is
    NOT considered allowlisted even though it contains ``github.com`` as a
    substring.

    For email addresses (containing ``@``), only the domain part (after ``@``)
    is compared against the allowlist, so ``admin@redhat.com`` is preserved
    while ``admin@evil-redhat.com.corp`` is still redacted.

    Args:
        text: The candidate match string to test.

    Returns:
        ``True`` if the text should be preserved (not redacted).
    """
    lower = text.lower()
    # For email addresses, check only the domain portion after '@'
    if "@" in lower:
        lower = lower.split("@", 1)[1]
    for domain in PUBLIC_DOMAIN_ALLOWLIST:
        if lower == domain or lower.endswith("." + domain):
            return True
    return False


def _redact_text(text: str, source_field: str) -> tuple[str, dict[str, int]]:
    """Apply all PII regex patterns to *text* and return the redacted result.

    Matches that are covered by the public-domain allowlist are skipped so
    that legitimate public URLs (e.g. GitHub PR links) are preserved.

    The patterns are applied in this order: IPv4, IPv6, email, phone,
    hostname.

    Args:
        text: The raw string to scan.
        source_field: A label used in audit log messages (e.g. ``"summary"``).

    Returns:
        A 2-tuple of ``(redacted_text, counts)`` where *counts* is a dict
        with keys ``"ip"``, ``"email"``, ``"phone"``, and ``"hostname"``
        mapping to the number of replacements made for each category.
    """
    counts: dict[str, int] = {"ip": 0, "email": 0, "phone": 0, "hostname": 0}

    def _replace(pattern: re.Pattern, placeholder: str, key: str, s: str) -> str:
        def _sub(m: re.Match) -> str:
            matched = m.group()
            if _is_allowlisted(matched):
                return matched
            counts[key] += 1
            return placeholder

        return pattern.sub(_sub, s)

    text = _replace(_IPV4_RE, _REDACTED_IP, "ip", text)
    text = _replace(_IPV6_RE, _REDACTED_IP, "ip", text)
    text = _replace(_EMAIL_RE, _REDACTED_EMAIL, "email", text)
    text = _replace(_PHONE_RE, _REDACTED_PHONE, "phone", text)
    text = _replace(_HOSTNAME_RE, _REDACTED_HOSTNAME, "hostname", text)

    total = sum(counts.values())
    if total > 0:
        logger.info("PII redacted from %s: %s", source_field, counts)

    return text, counts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_redaction_enabled() -> bool:
    """Return whether PII redaction is active.

    Reads the ``PII_REDACTION_ENABLED`` environment variable (default
    ``"true"``).  Set it to ``"false"`` to bypass redaction during local
    development.

    Returns:
        ``False`` only when the variable is explicitly set to ``"false"``
        (case-insensitive); ``True`` in all other cases.
    """
    return os.getenv("PII_REDACTION_ENABLED", "true").lower() != "false"


def redact_pii(data: dict[str, Any], source: str = "unknown") -> dict[str, Any]:
    """Redact PII from a Jira ticket or GitHub PR data dict.

    Returns a **new** dict with the same keys as *data* but with PII removed.
    The original dict is never mutated.

    Personal name fields (``reporter``, ``assignee``, ``author``,
    ``reviewers``) are replaced with placeholder strings unconditionally.

    Free-text fields (``summary``, ``description``, ``title``, ``body``,
    ``comments``, ``acceptance_criteria``) are scanned with regex patterns
    for IP addresses, email addresses, phone numbers, and internal hostnames.
    Matches covered by the public-domain allowlist are preserved.

    All other fields are copied through unchanged.

    Args:
        data: Raw dict from ``JiraClient.fetch_ticket()`` or
            ``GitHubClient.fetch_pr()``.
        source: A label for audit log messages, e.g. the Jira ticket ID or
            GitHub PR URL.

    Returns:
        A new dict with PII redacted.  If redaction is disabled (see
        :func:`is_redaction_enabled`), *data* is returned unchanged.
    """
    global _redaction_disabled_warned  # noqa: PLW0603

    if not is_redaction_enabled():
        if not _redaction_disabled_warned:
            logger.warning(
                "PII_REDACTION_ENABLED=false — skipping PII redaction. "
                "Do NOT use this setting in production."
            )
            _redaction_disabled_warned = True
        return data

    result: dict[str, Any] = {}
    name_count = 0
    text_redaction_count = 0

    # Fields that receive simple string free-text scanning
    _TEXT_FIELDS = {"summary", "description", "title", "body"}
    # Fields that are lists of strings to scan element-by-element
    _LIST_TEXT_FIELDS = {"comments", "acceptance_criteria"}

    for key, value in data.items():
        # --- Personal name fields: replace wholesale ---
        if key == "reporter" and value:
            result[key] = _REDACTED_PERSON
            name_count += 1

        elif key == "assignee" and value:
            result[key] = _REDACTED_PERSON
            name_count += 1

        elif key == "author" and value:
            result[key] = _REDACTED_PERSON
            name_count += 1

        elif key == "reviewers" and isinstance(value, list) and value:
            result[key] = [_REDACTED_PERSON] * len(value)
            name_count += len(value)

        # --- Single free-text string fields ---
        elif key in _TEXT_FIELDS and isinstance(value, str):
            redacted, counts = _redact_text(value, f"{source}.{key}")
            result[key] = redacted
            text_redaction_count += sum(counts.values())

        # --- List-of-strings fields ---
        elif key in _LIST_TEXT_FIELDS and isinstance(value, list):
            redacted_list: list[str] = []
            for i, item in enumerate(value):
                if isinstance(item, str):
                    redacted_item, counts = _redact_text(
                        item, f"{source}.{key}[{i}]"
                    )
                    redacted_list.append(redacted_item)
                    text_redaction_count += sum(counts.values())
                else:
                    # Non-string elements (shouldn't happen, but be safe)
                    redacted_list.append(item)
            result[key] = redacted_list

        # --- All other fields: pass through unchanged ---
        else:
            result[key] = value

    logger.info(
        "redact_pii(%s): replaced %d personal name fields, %d text redactions",
        source,
        name_count,
        text_redaction_count,
    )

    return result
