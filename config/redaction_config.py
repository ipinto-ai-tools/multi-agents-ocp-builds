"""Redaction configuration for the PII redactor layer.

Defines the public domain allowlist — URLs and hostnames containing any of
these domains are considered safe and will NOT be redacted by the PII
redactor.
"""

# Domains whose hostnames/URLs are safe and should NOT be redacted
PUBLIC_DOMAIN_ALLOWLIST = [
    "github.com",
    "githubusercontent.com",
    "redhat.com",
    "openshift.com",
    "kubernetes.io",
    "google.com",
    "googleapis.com",
    "anthropic.com",
    "atlassian.com",
    "atlassian.net",
    "jira.com",
    "confluence.com",
    "pypi.org",
    "python.org",
    "golang.org",
]
