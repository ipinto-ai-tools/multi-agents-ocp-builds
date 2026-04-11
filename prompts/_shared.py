"""Shared prompt sections used across all stage prompts."""

from typing import Final


_DATA_PRIVACY_SECTION: Final[str] = """

## Data Privacy and Enterprise Safety

This tool may use Claude Code inside agent workflows, but it must be operated under strict data-minimization and privacy controls.

### Required rules

- Do **not** send enterprise, customer, confidential, regulated, or private data to Claude unless that data flow is explicitly approved.
- Do **not** send secrets of any kind, including:
  - API keys
  - tokens
  - passwords
  - kubeconfigs
  - certificates
  - private URLs
  - internal emails
  - internal tickets
  - customer names
  - personal data
- Default to **local processing first**. Only send the minimum text required for the task.
- Redact or mask sensitive values before any prompt is built.
- Never automatically attach full files, logs, configs, diffs, or environment variables unless explicitly approved and sanitized.
- Never send `.env` contents, secret manifests, credential files, or raw production data.
- Never use Claude as a storage location for enterprise knowledge, customer records, or private artifacts.
- If a task would require sending sensitive data, the agent must **stop and fail closed** unless an approved safe path exists.

### Safe usage policy

Claude Code may be used only for:
- general code generation
- refactoring guidance
- test suggestions
- documentation drafting
- architecture discussion
- summaries of already-sanitized content

Claude Code must **not** be used for:
- processing raw customer data
- processing production secrets
- sending internal incident data without sanitization
- sharing private repositories or proprietary code outside approved boundaries
- copying large internal documents into prompts without approval

### Data minimization requirements

Before sending any prompt to Claude, agents must:
1. remove secrets
2. remove personal data
3. remove customer-identifying information
4. remove internal-only URLs and IDs when not needed
5. truncate unnecessary context
6. send only the smallest useful snippet

### Approval boundaries

Outbound use of Claude is allowed only when all of the following are true:
- the destination is an approved Claude environment/account
- the content is sanitized
- the content is limited to the minimum required
- the request does not include secrets or restricted enterprise data
- the action complies with company policy and legal/security requirements

### Logging and retention

- Log only operational metadata when possible, not full sensitive payloads.
- Do not persist prompts/responses containing confidential material unless explicitly approved.
- Any retained logs must follow company retention and access-control policies.

### Implementation expectation

All agents that call Claude Code must enforce:
- secret redaction
- prompt filtering
- outbound allowlists
- explicit approval for non-sanitized content
- secure local handling of temporary files
- fail-closed behavior when privacy status is unclear

### Human rule

When in doubt, do not send the data.
Prefer blocking the request over exposing enterprise or private information.
"""


def build_jira_context_block(state: dict) -> str:
    """Build a Jira context section for injection into agent prompts.

    Returns empty string if no Jira ticket in state.
    """
    ticket_id = state.get("jira_ticket_id", "")
    if not ticket_id:
        return ""

    lines = [
        "## Jira Ticket Context",
        f"Ticket: {ticket_id}",
        f"URL: {state.get('jira_ticket_url', '')}",
        f"Priority: {state.get('jira_priority', 'N/A')}",
    ]

    labels = state.get("jira_labels", [])
    if labels:
        lines.append(f"Labels: {', '.join(labels)}")

    linked = state.get("jira_linked_issues", [])
    if linked:
        lines.append(f"Linked Issues: {', '.join(linked)}")

    comments = state.get("jira_comments_summary", "")
    if comments:
        lines.append(f"\n### Discussion Summary\n{comments}")

    return "\n".join(lines)
