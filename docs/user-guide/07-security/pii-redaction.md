# PII Redaction

All external data fetched from Jira and GitHub is automatically redacted before it enters the agent pipeline. This prevents personally identifiable information (PII) from being included in prompts sent to Claude or stored in workflow state.

---

## What Gets Redacted

Redaction is applied to two categories of data:

### Personal Name Fields

The following fields are replaced wholesale with `[CUSTOMER_REDACTED]` regardless of their content:

| Field | Source |
|-------|--------|
| `reporter` | Jira ticket |
| `assignee` | Jira ticket |
| `author` | GitHub PR |
| `reviewers` | GitHub PR (each entry in the list) |

These fields always contain names — no regex inspection is needed.

### Free-Text Fields

The following fields are scanned with regex patterns that detect and replace specific PII types:

| Field | Source |
|-------|--------|
| `summary` | Jira ticket |
| `description` | Jira ticket |
| `acceptance_criteria` | Jira ticket (list of strings) |
| `title` | GitHub PR |
| `body` | GitHub PR |
| `comments` | GitHub PR (list of strings) |

The regex patterns and their replacement tokens:

| PII Type | Example | Replacement |
|----------|---------|-------------|
| IPv4 address | `192.168.1.100` | `[IP_REDACTED]` |
| IPv6 address | `fe80::1`, `2001:db8::1` | `[IP_REDACTED]` |
| Email address | `dev@company.internal` | `[EMAIL_REDACTED]` |
| Phone number | `+1 (555) 867-5309` | `[PHONE_REDACTED]` |
| Internal hostname | `prod-db-01.internal` | `[HOSTNAME_REDACTED]` |

All other fields (ticket ID, issue type, status, labels, linked URLs, etc.) pass through unchanged.

---

## When Redaction Happens

Redaction is applied at fetch time — immediately before the raw dict is returned to the caller. This means PII never enters the agent pipeline, workflow state, or dashboard heartbeats.

```
External API
    │
    ▼
JiraClient.fetch_ticket()        GitHubClient.fetch_pr()
    │                                    │
    ▼                                    ▼
redact_pii(ticket_dict,          redact_pii(pr_dict,
  source="jira:SHIP-123")          source="github:org/repo#42")
    │                                    │
    ▼                                    ▼
Redacted dict returned           Redacted dict returned
    │                                    │
    └──────────────┬─────────────────────┘
                   ▼
          Agent pipeline (Design → Development → ...)
```

The redactor is implemented in `tools/pii_redactor.py`. It is called unconditionally in both `tools/jira_client.py` and `tools/github_client.py` at the end of each fetch function.

---

## Public Domain Allowlist

Not every hostname or email-looking string should be redacted. The public domain allowlist in `config/redaction_config.py` defines domains whose URLs and addresses are safe to preserve. Matches belonging to an allowlisted domain are left intact.

**Allowlisted domains (15 total):**

```
github.com          githubusercontent.com
redhat.com          openshift.com
kubernetes.io       google.com
googleapis.com      anthropic.com
atlassian.com       atlassian.net
jira.com            confluence.com
pypi.org            python.org
golang.org
```

**Example behavior:**

| Text in field | Redacted? |
|---------------|-----------|
| `https://github.com/shipwright-io/build/pull/1234` | No — `github.com` is allowlisted |
| `admin@redhat.com` | No — `redhat.com` is allowlisted |
| `10.0.1.52` | Yes — private IP |
| `dev@internal.corp` | Yes — not allowlisted |
| `prod-api.company.net` | Yes — not allowlisted |

### Suffix Matching Prevents Bypass

The allowlist check uses suffix matching with a required leading dot. A string like `evil-github.com.corp` contains `github.com` as a substring but is NOT allowlisted, because it does not equal `github.com` and does not end with `.github.com`.

For email addresses, only the domain portion after `@` is compared. `admin@redhat.com` is preserved; `admin@evil-redhat.com.corp` is still redacted.

---

## Disabling Redaction

Redaction can be disabled for local development by setting:

```bash
PII_REDACTION_ENABLED=false
```

When disabled, a one-time warning is emitted to the log:

```
WARNING PII_REDACTION_ENABLED=false — skipping PII redaction. Do NOT use this setting in production.
```

The warning is emitted only once per process lifetime regardless of how many tickets or PRs are fetched.

Do not set `PII_REDACTION_ENABLED=false` in any environment that processes real customer data.

---

## Audit Logging

The redactor logs a summary for every fetch. At `INFO` level you will see:

```
INFO redact_pii(jira:SHIP-123): replaced 2 personal name fields, 3 text redactions
INFO PII redacted from jira:SHIP-123.description: {'ip': 1, 'email': 0, 'phone': 0, 'hostname': 2}
```

These log lines appear in the agent log files under `logs/stages/`. They let you verify what was redacted without exposing the original values.

---

## Configuration Reference

| File | Purpose |
|------|---------|
| `tools/pii_redactor.py` | Core redaction logic: regex patterns, field routing, allowlist check |
| `config/redaction_config.py` | `PUBLIC_DOMAIN_ALLOWLIST` list |
| `tools/jira_client.py` | Calls `redact_pii()` on every `fetch_ticket()` result |
| `tools/github_client.py` | Calls `redact_pii()` on every `fetch_pr()` result |

### Adding a Domain to the Allowlist

Edit `config/redaction_config.py` and append the domain to `PUBLIC_DOMAIN_ALLOWLIST`:

```python
PUBLIC_DOMAIN_ALLOWLIST = [
    "github.com",
    # ... existing entries ...
    "your-public-domain.com",   # add here
]
```

Use the bare domain without scheme or trailing slash. Subdomain matching is automatic — adding `example.com` also preserves `docs.example.com` and `api.example.com`.

---

[← Integrations](../09-integrations/jira-rovo.md) | [Back to Index](../README.md)
