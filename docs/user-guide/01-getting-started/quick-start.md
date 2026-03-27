# Quick Start

Run your first multi-agent workflow in under five minutes.

---

## Prerequisites

Before running the workflow, confirm you have:

- [Installed the system](installation.md)
- Authenticated with Google Cloud: `gcloud auth application-default login`
- Set `ANTHROPIC_VERTEX_PROJECT_ID` in your `.env` file

If you want to try the system without credentials, skip to [Dry Run](#dry-run-no-credentials-needed) below.

---

## Run Your First Workflow

The orchestrator runs all five agents (Design → Development → Code Review → Testing → Documentation) in sequence and prints the results to the console.

```bash
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds"
```

To save artifacts to a local directory, add `--output-dir`:

```bash
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds" \
  --output-dir ./my-output
```

The directory is created if it does not exist. Artifacts saved include `state.json`, generated code under `code/`, tests under `tests/`, design analysis under `design/`, and documentation under `docs/`. The `--output-dir` path is required by `scripts/publish.py` when pushing artifacts to GitHub or Jira.

### What Happens

The workflow runs through five sequential phases:

```text
Issue → Design Agent → Development Agent → Code Review → Testing Agent → Docs Agent → Done
          |               |                    |               |               |
          v               v                    v               v               v
        Plan            Code               Pass/Fix         Tests           Docs
```

State transitions:

```
init → design_complete → develop_complete → review_complete → testing_complete → done
```

While the workflow runs, the terminal prints a header for each phase showing its position in the sequence and a per-phase timer:

```text
Phase 1/5 · Design
Phase 2/5 · Development
Phase 3/5 · Code Review
Phase 4/5 · Testing
Phase 5/5 · Documentation
```

When all phases finish, a summary block is printed:

```text
Run complete
  Duration:   3m 42s
  Artifacts:  ./my-output
  Dashboard:  http://localhost:8080
```

The dashboard URL is omitted if `DASHBOARD_ENABLED` is set to `false`.

If an agent raises an unhandled exception, the workflow sets `current_phase = "error"` and stops early. The final state contains the error message.

> **Note:** After each phase, outputs are automatically validated. If required fields
> are missing or empty, the workflow stops immediately with a clear error rather than
> silently passing bad data to the next agent.

### What You Get

When the workflow completes, five outputs are printed to the console:

1. **Design Analysis** - Component analysis, risks, acceptance criteria, and implementation plan
2. **Production Code** - Go code for Kubernetes/OpenShift with TLS 1.3 and security best practices
3. **Code Review** - Automated review findings with blocking/warning severity and auto-fix loop (up to 3 iterations)
4. **Test Suite** - Ginkgo v2 tests (unit, integration, E2E) with data-driven patterns
5. **Documentation** - PR summary, release notes, and Jobs-to-be-Done user documentation

---

## Run from a Jira Ticket

If your team tracks work in Jira, pass a ticket ID instead of `--title` and `--description`. The system fetches all ticket data automatically.

> **Requires:** Jira configured in `.env` and VPN access. See [Jira & Rovo Integration](../09-integrations/jira-rovo.md).

```bash
uv run python scripts/orchestrate.py --jira-ticket SHIP-123
```

To test without VPN, add `--dry-run` — it returns a mock SHIP-123 ticket with no credentials needed:

```bash
uv run python scripts/orchestrate.py --jira-ticket SHIP-123 --dry-run
```

---

## Run with Manual Approval

Set `MANUAL_APPROVAL=true` to pause after each phase and review the output before continuing:

```bash
MANUAL_APPROVAL=true uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun API" \
  --description "Users need to specify timeouts for build execution"
```

After each phase completes, you'll see a summary and a prompt:

```text
──────────────────────────────────────────────────────────
  Phase: DESIGN  |  Validation: PASSED
──────────────────────────────────────────────────────────
  Analysis length: 1243 chars
  Implementation plan steps: 5
  Impacted components: 3
  Risks identified: 2
  Acceptance criteria: 4

  Next phase: DEVELOPMENT

  Continue to development? [Y/n]:
```

Type `Y` (or press Enter) to continue, or `n` to stop the workflow. The completed phases are kept.

> **When to use manual approval:**
>
> - Reviewing design analysis before committing to code generation (saves API costs)
> - Quality-checking in sensitive environments
> - Step-by-step debugging of the agent pipeline

---

## Monitor Progress in Real Time

Start the dashboard before running the orchestrator to watch each agent's progress as it runs.

**Terminal 1 - Start the dashboard:**

```bash
uv run python scripts/run_dashboard.py
```

Open http://localhost:8080 in your browser.

**Terminal 2 - Run the workflow:**

```bash
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds"
```

The dashboard shows each agent's current phase, context window usage, and impacted components updating in real time.

---

## Dry Run (No Credentials Needed)

Dry run mode uses pre-configured mock responses. No authentication is needed and no API calls are made.

```bash
uv run python scripts/test_agents.py --e2e --dry-run
```

To see verbose output:

```bash
uv run python scripts/test_agents.py --e2e --dry-run --debug
```

Test a single agent:

```bash
uv run python scripts/test_agents.py --agent design --dry-run --debug
```

---

## More Examples

**Analyze a bug report:**

```bash
uv run python scripts/orchestrate.py \
  --title "BuildRun stuck in Running state" \
  --description "BuildRuns remain Running even after pod completes. Status reconciliation fails."
```

**Analyze a feature with repository context for deeper analysis:**

```bash
export SHIPWRIGHT_REPO_PATH=/home/user/git/shipwright-build

uv run python scripts/orchestrate.py \
  --title "Add SSH key support for private Git repos" \
  --description "Users need to build from private Git repos using SSH authentication"
```

**Analyze a caching feature:**

```bash
uv run python scripts/orchestrate.py \
  --title "Implement build output caching" \
  --description "Allow BuildRuns to cache intermediate build layers to speed up subsequent builds. Should support OCI registry-based caching."
```

---

## Next Steps

- [Configuration](configuration.md) - Tune environment variables, logging, and performance
- [Agents Overview](../02-concepts/agents-overview.md) - Understand what each agent does
- [Dashboard Overview](../04-dashboard/overview.md) - Learn what the dashboard shows

---

[← Previous: Installation](installation.md) | [Next: Configuration →](configuration.md)
