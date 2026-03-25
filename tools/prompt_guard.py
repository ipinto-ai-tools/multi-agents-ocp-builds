"""Prompt Injection Guard for external data sanitization.

Strips and escapes prompt injection patterns from external data sources
(Jira tickets, GitHub PRs) before they reach Claude prompts.

All sanitization is logged by category and source only — matched content
is NEVER logged to avoid leaking potentially sensitive attack payloads.
"""

import base64
import os
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns (in priority order)
# ---------------------------------------------------------------------------

# 1. Role override instructions
_ROLE_OVERRIDE_RE = re.compile(
    r'(ignore\s+(all\s+)?(previous|prior|above)\s+instructions?'
    r'|you\s+are\s+now\s+a\b'
    r'|your\s+new\s+(task|instructions?|role)\s+is\b'
    r'|act\s+as\s+(a\s+)?(?:different|new|another)\b'
    r'|forget\s+(everything|all)\s+(you\s+)?(know|were\s+told)'
    r'|disregard\s+(all\s+)?(previous|prior)\s+instructions?)',
    re.IGNORECASE | re.MULTILINE,
)

# 2. System prompt escape sequences (newline-prefixed role headers)
_SYSTEM_ESCAPE_RE = re.compile(
    r'(\n+(System|Human|Assistant|User|AI)\s*:)',
    re.IGNORECASE,
)

# 3. Special tokens / jailbreak markers
_JAILBREAK_TOKEN_RE = re.compile(
    r'(\[INST\]|\[/INST\]|</s>|<s>|<\|system\|>|<\|im_start\|>|<\|im_end\|>'
    r'|<\|endoftext\|>|\[SYS\]|\[/SYS\]|<\|user\|>|<\|assistant\|>)',
    re.IGNORECASE,
)

# 4. Base64 encoded commands (>=60 chars of base64)
_BASE64_RE = re.compile(
    r'(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/\-_]{60,}={0,2}(?![A-Za-z0-9+/=_-])'
)

# 5. Delimiter abuse (standalone lines of only dashes/equals >= 10 chars)
_DELIMITER_ABUSE_RE = re.compile(r'^[-=]{10,}\s*$', re.MULTILINE)

# Keywords that flag a decoded base64 payload as injection
_B64_INJECTION_KEYWORDS = frozenset({"ignore", "system", "instructions", "jailbreak"})


def is_guard_enabled() -> bool:
    """Return True when the prompt guard is active.

    Controlled by the PROMPT_GUARD_ENABLED environment variable.
    Defaults to True when the variable is absent or set to any value
    other than a case-insensitive 'false'.
    """
    return os.getenv("PROMPT_GUARD_ENABLED", "true").lower() == "true"


def _sanitize_base64_match(match: re.Match) -> str:  # type: ignore[type-arg]
    """Evaluate a base64 match and return replacement if it decodes to injection content."""
    candidate = match.group(0)
    try:
        # Handle both standard and URL-safe base64 (replace URL-safe chars before decoding)
        normalized = candidate.replace("-", "+").replace("_", "/")
        # Pad to multiple of 4
        padding = (4 - len(normalized) % 4) % 4
        normalized += "=" * padding
        decoded_bytes = base64.b64decode(normalized)
        decoded_text = decoded_bytes.decode("utf-8", errors="ignore").lower()
        if any(kw in decoded_text for kw in _B64_INJECTION_KEYWORDS):
            return "[REDACTED_B64]"
    except Exception:
        pass
    return candidate


def sanitize_external_input(text: Any, source: str) -> Any:
    """Sanitize external input to remove prompt injection patterns.

    Applies a series of regex-based scrubbing rules to strip role overrides,
    system-escape sequences, jailbreak tokens, suspicious base64 payloads,
    and delimiter-abuse patterns.

    Args:
        text: The value to sanitize.  Non-string values are returned unchanged.
        source: A human-readable label identifying where this value came from
                (e.g. ``"design:title"``).  Used only in log messages — never
                logged alongside the matched content.

    Returns:
        Sanitized string, or the original value unchanged when it is not a
        string or when the guard is disabled.
    """
    if not isinstance(text, str):
        return text

    if not is_guard_enabled():
        return text

    result = text

    # 1. Role override instructions -> [REDACTED]
    if _ROLE_OVERRIDE_RE.search(result):
        logger.warning(
            "prompt_guard: sanitized [%s] in field [%s]",
            "role_override",
            source,
        )
        result = _ROLE_OVERRIDE_RE.sub("[REDACTED]", result)

    # 2. System prompt escape sequences -> ' [REDACTED]' (strip leading newlines)
    if _SYSTEM_ESCAPE_RE.search(result):
        logger.warning(
            "prompt_guard: sanitized [%s] in field [%s]",
            "system_escape",
            source,
        )
        result = _SYSTEM_ESCAPE_RE.sub(" [REDACTED]", result)

    # 3. Jailbreak tokens -> [REDACTED]
    if _JAILBREAK_TOKEN_RE.search(result):
        logger.warning(
            "prompt_guard: sanitized [%s] in field [%s]",
            "jailbreak_token",
            source,
        )
        result = _JAILBREAK_TOKEN_RE.sub("[REDACTED]", result)

    # 4. Base64 payloads that decode to injection keywords -> [REDACTED_B64]
    if _BASE64_RE.search(result):
        new_result = _BASE64_RE.sub(_sanitize_base64_match, result)
        if new_result != result:
            logger.warning(
                "prompt_guard: sanitized [%s] in field [%s]",
                "base64_injection",
                source,
            )
        result = new_result

    # 5. Delimiter abuse -> ---
    if _DELIMITER_ABUSE_RE.search(result):
        logger.warning(
            "prompt_guard: sanitized [%s] in field [%s]",
            "delimiter_abuse",
            source,
        )
        result = _DELIMITER_ABUSE_RE.sub("---", result)

    return result


__all__ = ["sanitize_external_input", "is_guard_enabled"]
