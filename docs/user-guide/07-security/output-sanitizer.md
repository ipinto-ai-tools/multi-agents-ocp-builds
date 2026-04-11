# Output Sanitizer

The Output Sanitizer is Layer 3 of the security stack. It prevents PII and sensitive data from leaving the system through output channels — log files, generated artifacts, and dashboard heartbeat payloads. Where Layers 1 and 2 protect data entering the agent pipeline, Layer 3 protects data leaving it.

---

## What It Protects

Five output channels are sanitized:

| Channel | Mechanism | Where applied |
|---------|-----------|---------------|
| Python logging (all handlers) | `SanitizingFilter` attached to every handler | `utils/file_logger.py` |
| `test_plan.md` artifact | `sanitize()` before `write_text()` | `stages/test.py` |
| `go_tests/*.go` artifacts | `sanitize()` before `write_text()` | `stages/test.py` |
| Dashboard heartbeat payloads | `sanitize_dict()` on full payload before HTTP POST | `dashboard/heartbeat.py` |
| Session log files | `SanitizingFilter` on file handler | `utils/file_logger.py` |

All five channels use the same sanitization logic from `tools/output_sanitizer.py`.

---

## How It Works

### `sanitize(text, source)`

Applies the PII regex patterns from `pii_redactor.py` to a single string and returns the cleaned result. The `source` parameter is a label used in audit log lines — it does not affect which patterns are applied.

```python
from tools.output_sanitizer import sanitize

clean = sanitize("Assigned to dev@internal.corp", source="test_plan.md")
# clean → "Assigned to [EMAIL_REDACTED]"
```

### `sanitize_dict(data, source)`

Recursively walks a dict or list and calls `sanitize()` on every string value it finds. Non-string values (integers, booleans, `None`) are left unchanged. Nested structures — including lists of lists — are fully traversed.

```python
from tools.output_sanitizer import sanitize_dict

payload = {
    "phase": "testing",
    "agent": "testing_agent",
    "details": {
        "message": "Running tests for 10.0.1.52",
        "tags": ["env:prod-db-01.internal", "status:ok"],
    },
}

clean = sanitize_dict(payload, source="heartbeat")
# clean["details"]["message"] → "Running tests for [IP_REDACTED]"
# clean["details"]["tags"][0] → "env:[HOSTNAME_REDACTED]"
```

### `SanitizingFilter` (logging)

`SanitizingFilter` is a `logging.Filter` subclass that intercepts log records before they are written to any handler.

The Python `logging` module resolves `%s`/`%d` placeholders lazily — only at formatting time. A naive sanitizer applied to `record.msg` alone can be bypassed if the sensitive value lives in `record.args` rather than the already-formatted message string. `SanitizingFilter` closes this gap with a three-step sequence:

1. **Pre-format** — calls `record.getMessage()` to resolve all placeholders into the final string, then stores the result back in `record.msg`.
2. **Sanitize** — applies `sanitize()` to the fully resolved `record.msg`.
3. **Clear args** — sets `record.args` to an empty tuple so the logging machinery does not attempt to format the already-resolved message a second time.

This sequence ensures that a log call such as:

```python
logger.info("Connecting to %s as %s", "prod-db-01.internal", "admin@corp.internal")
```

is emitted as:

```text
INFO Connecting to [HOSTNAME_REDACTED] as [EMAIL_REDACTED]
```

The filter is attached to every handler (both file handler and console handler) so that all output paths are covered regardless of which handler processes a given record. Both `utils/file_logger.py` and the root logger setup attach the filter automatically. You do not need to add it manually in agent code.

---

## Idempotency

Sanitization is idempotent. The replacement tokens produced by `_redact_text` (for example, `[IP_REDACTED]`, `[EMAIL_REDACTED]`, `[CUSTOMER_REDACTED]`) do not match any of the detection patterns. Passing a value through `sanitize()` a second time returns the same string.

This property means it is safe to call `sanitize()` defensively at multiple points in a code path without risk of double-processing or corruption. It also means sanitizing content that has already passed through Layer 1 (PII Redaction) is harmless.

---

## Relationship to PII Redactor (Layer 1)

The output sanitizer reuses `_redact_text` from `tools/pii_redactor.py`. This means the same regex patterns and replacement tokens apply at both layers:

| PII type          | Replacement          |
|-------------------|----------------------|
| IPv4 address      | `[IP_REDACTED]`      |
| IPv6 address      | `[IP_REDACTED]`      |
| Email address     | `[EMAIL_REDACTED]`   |
| Phone number      | `[PHONE_REDACTED]`   |
| Internal hostname | `[HOSTNAME_REDACTED]`|

The two layers operate at different points:

| Layer | Where | When |
| --- | --- | --- |
| Layer 1 (PII Redactor) | Fetch functions in `jira_client.py` / `github_client.py` | Before data enters the pipeline |
| Layer 3 (Output Sanitizer) | Logging handlers, artifact writers, heartbeat | Before data leaves the system |

Layers 1 and 2 protect the pipeline at ingress. Layer 3 protects at egress. Together they ensure PII has no path in or out of the system in plaintext.

The public domain allowlist defined in `config/redaction_config.py` applies at both layers — URLs and email addresses belonging to allowlisted domains such as `github.com` and `redhat.com` are preserved by both the PII Redactor and the Output Sanitizer.

---

## Disabling the Output Sanitizer

The sanitizer can be disabled for local development by setting:

```bash
OUTPUT_SANITIZER_ENABLED=false
```

When disabled:

- `sanitize()` returns its input unchanged
- `sanitize_dict()` returns its input unchanged
- `SanitizingFilter` still attaches to handlers but passes log records through without modification

Do not set `OUTPUT_SANITIZER_ENABLED=false` in any environment that writes logs or artifacts that leave the local machine.

---

## Audit Logging

When `sanitize()` replaces a value, it emits a `DEBUG` log line containing the source label and replacement token type. The original value is never logged.

```text
DEBUG output_sanitizer: [EMAIL_REDACTED] applied in source='test_plan.md'
DEBUG output_sanitizer: [IP_REDACTED] applied in source='heartbeat'
```

---

## Configuration Reference

| File | Purpose |
| --- | --- |
| `tools/output_sanitizer.py` | `sanitize()`, `sanitize_dict()`, `SanitizingFilter`, `is_sanitizer_enabled()` |
| `tools/pii_redactor.py` | Shared regex patterns and replacement logic (`_redact_text`) |
| `config/redaction_config.py` | `PUBLIC_DOMAIN_ALLOWLIST` — applies to both Layer 1 and Layer 3 |
| `utils/file_logger.py` | Attaches `SanitizingFilter` to all logging handlers |
| `stages/test.py` | Calls `sanitize()` before writing `test_plan.md` and Go test files |
| `dashboard/heartbeat.py` | Calls `sanitize_dict()` on the full heartbeat payload before HTTP POST |
| `tests/test_output_sanitizer.py` | 56 tests covering all functions, edge cases, and env var toggle |

---

[← Prompt Injection Guard](prompt-injection-guard.md) | [Back to Index](../README.md)
