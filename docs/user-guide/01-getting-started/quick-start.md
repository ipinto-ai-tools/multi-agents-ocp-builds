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

The orchestrator runs all four agents (Design → Development → Testing → Documentation) in sequence and prints the results to the console.

```bash
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun" \
  --description "Users need ability to specify build timeout to prevent hanging builds"
```

### What Happens

The workflow runs through four sequential phases:

```text
Issue → Design Agent → Development Agent → Testing Agent → Docs Agent → Done
          |               |                    |               |
          v               v                    v               v
        Plan            Code                 Tests           Docs
```

State transitions:

```
init → design_complete → develop_complete → testing_complete → done
```

If an agent raises an unhandled exception, the workflow sets `current_phase = "error"` and stops early. The final state contains the error message.

> **Note:** After each phase, outputs are automatically validated. If required fields
> are missing or empty, the workflow stops immediately with a clear error rather than
> silently passing bad data to the next agent.

### What You Get

When the workflow completes, four outputs are printed to the console:

1. **Design Analysis** - Component analysis, risks, acceptance criteria, and implementation plan
2. **Production Code** - Go code for Kubernetes/OpenShift with TLS 1.3 and security best practices
3. **Test Suite** - Ginkgo v2 tests (unit, integration, E2E) with data-driven patterns
4. **Documentation** - PR summary, release notes, and Jobs-to-be-Done user documentation

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
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py
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
