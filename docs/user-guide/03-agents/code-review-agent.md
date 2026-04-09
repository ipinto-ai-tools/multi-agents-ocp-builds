# Code Review Agent

The Code Review Agent inspects generated Go code for security vulnerabilities, correctness issues, and Kubernetes/Shipwright standards compliance. It runs between the Development and Testing phases and can automatically route failing code back to the Development Agent for fixes.

**File:** `stages/code_review.py`
**Entry point:** `run_code_review(state)`

---

## System Prompt

The Code Review Agent is driven by `CODE_REVIEW_AGENT_PROMPT` defined in [`prompts/code_review.py`](../../../prompts/code_review.py).

The prompt instructs the agent to:

- Scan all generated Go files for security, correctness, and quality issues
- Classify each finding with a severity tag (`[BLOCKING]`, `[WARNING]`, or `[SUGGESTION]`)
- Produce a structured findings list and a human-readable verdict
- When Qodo CLI is available, delegate static analysis to it and supplement with Claude review

To customize Code Review Agent behavior, edit `CODE_REVIEW_AGENT_PROMPT` in `prompts/code_review.py`.

---

## Position in the Pipeline

The Code Review Agent sits between the Development and Testing phases. When blocking issues are found, it routes execution back to the Development Agent with its findings injected into the prompt. The loop repeats until the review passes or the iteration limit is reached.

```
Design → Development → Code Review ⟲ Development (auto-fix)
                           ↓ (pass OR max iterations reached)
                         Testing → Docs
```

The pipeline never blocks indefinitely. When `MAX_REVIEW_ITERATIONS` is exhausted, the workflow continues to Testing with a warning recorded in the state.

---

## Auto-Fix Loop

Each iteration of the loop follows this sequence:

1. The Development Agent produces (or re-produces) Go source and test files.
2. The Code Review Agent scans the output.
3. If one or more `[BLOCKING]` findings exist, the agent writes the structured findings list back into the shared state.
4. The orchestrator routes execution back to the Development Agent, which receives the findings as additional context in its next prompt.
5. The Development Agent applies fixes and emits a new set of files.
6. Steps 2-5 repeat until no blocking findings remain or `MAX_REVIEW_ITERATIONS` is reached.
7. On success or max-iterations, execution continues to the Testing Agent.

The `review_iteration` counter in state tracks progress. The dashboard shows each pass as a `develop` → `code_review` heartbeat pair, making the loop visible in real time.

---

## Finding Severity Levels

| Level | Tag | Effect | Example |
|-------|-----|--------|---------|
| Blocking | `[BLOCKING]` | Triggers auto-fix loop | Hardcoded secret in source file |
| Warning | `[WARNING]` | Logged, pipeline continues | Missing Go doc comment on exported function |
| Suggestion | `[SUGGESTION]` | Logged, pipeline continues | Consider adding inline comments to complex logic |

Only `[BLOCKING]` findings trigger a return to the Development Agent. `[WARNING]` and `[SUGGESTION]` findings are preserved in `review_findings` and surfaced in the dashboard, but do not alter the pipeline route.

---

## Review Areas

The agent evaluates generated code across five domains:

**Security**
- Hardcoded secrets, tokens, or credentials in source files
- TLS configuration (minimum TLS 1.3 enforced)
- Input validation before use in API calls or exec commands
- Safe logging (no secrets or PII written to logs)

**Correctness**
- Error handling: all returned errors checked and wrapped with context
- Context propagation: `context.Context` threaded through call chains
- Resource cleanup: `defer` used for file handles, connections, and locks

**Code quality**
- Go doc comments on all exported types, functions, and methods
- Idiomatic Go patterns (no unnecessary type assertions, prefer table-driven logic)
- Single-responsibility: functions perform one coherent operation

**Testing**
- Table-driven test structure using `[]struct{ name, input, expected }`
- Coverage of both success paths and error/failure paths
- Ginkgo v2 `Describe`/`It` blocks used where applicable

**Kubernetes and Shipwright standards**
- Controller-runtime reconciliation patterns (result, error return)
- Status conditions updated using `meta.SetStatusCondition`
- Finalizer lifecycle managed correctly (add on creation, remove before deletion)

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `QODO_REVIEW_ENABLED` | `true` | Set to `false` to skip code review entirely |
| `MAX_REVIEW_ITERATIONS` | `3` | Maximum auto-fix attempts before continuing to Testing |
| `QODO_BLOCKING_THRESHOLD` | `high` | Severity level that triggers auto-fix: `high` (BLOCKING only) / `medium` (BLOCKING + WARNING) / `low` (any finding) |
| `QODO_CLI_PATH` | (none) | Optional absolute path to the Qodo CLI binary for enhanced static analysis |

---

## Using Qodo CLI (Optional Enhancement)

By default, the Code Review Agent uses Claude to perform the review. No additional tools are required.

To enable enhanced static analysis via Qodo CLI:

1. Install the Qodo CLI: `npm install -g @qodo/command`
2. Authenticate with Qodo (see [Qodo Authentication](#qodo-authentication) below).
3. Set `QODO_CLI_PATH` in your `.env` file to the absolute path of the binary, for example: `QODO_CLI_PATH=/home/user/.npm-global/bin/qodo`
4. Optionally set `QODO_API_KEY` for CI or headless environments (see below).

When `QODO_CLI_PATH` is set, the agent runs the Qodo CLI against each generated file and merges its output with Claude's review before classifying findings. If the Qodo CLI is unavailable, exits with an error, or times out, the agent automatically falls back to Claude-only review and logs a warning. The pipeline is never blocked by a Qodo CLI failure.

### Qodo Authentication

Qodo supports two authentication methods:

#### Browser OAuth (recommended for local development)

Run `qodo login` once before using the CLI. This opens a browser window, completes the OAuth flow, and stores the token at `~/.qodo/auth.key`. No API key is required after this step.

```bash
qodo login
```

#### API key (for CI and headless environments)

Generate an API key at <https://app.qodo.ai/settings/api-keys> and set it as an environment variable:

```bash
export QODO_API_KEY=your-api-key-here
```

Add `QODO_API_KEY` to your `.env` file or CI secrets so it is available at runtime.

### Running in Non-TTY Environments (Claude Code, CI)

Qodo's default interface is an interactive TUI that requires a real terminal. When invoked from Claude Code or a CI pipeline, use the `--ci` flag to run in headless mode:

```bash
qodo review --ci -y --model claude-sonnet-4-6 <path>
```

The `QODO_CLI_PATH` configuration in this project automatically appends `--ci` when invoking Qodo from the orchestrator, so no manual flag is needed during normal workflow execution.

---

## Disabling Code Review

To skip the code review phase entirely, set `QODO_REVIEW_ENABLED=false`:

```bash
QODO_REVIEW_ENABLED=false uv run python scripts/orchestrate.py \
  --title "Quick feature" \
  --description "Simple change" \
  --output-dir ./output
```

When disabled, the pipeline routes directly from Development to Testing with no review state written.

---

## Dry Run Mode

In dry-run mode, the agent does not call the Claude API or the Qodo CLI. It reads the `MOCK_CODE_REVIEW_PASS` environment variable to determine the mock verdict:

```bash
# Simulate a passing review (default dry-run behavior)
uv run python scripts/orchestrate.py \
  --jira-ticket SHIP-123 \
  --output-dir ./output \
  --dry-run

# Simulate a blocking review (triggers mock auto-fix loop)
MOCK_CODE_REVIEW_PASS=false uv run python scripts/orchestrate.py \
  --jira-ticket SHIP-123 \
  --output-dir ./output \
  --dry-run
```

---

## Dashboard

The Code Review Agent emits a heartbeat at the start and end of each review pass. Dashboard fields during the review phase:

- **Phase**: `code_review`
- **Iteration**: current value of `review_iteration`
- **Verdict**: `pass`, `blocking`, or `max_iterations_reached`

Auto-fix loops appear in the dashboard timeline as alternating `develop` and `code_review` heartbeat pairs. This makes it straightforward to identify how many correction cycles were needed for a given workflow run.

---

## State Fields

The agent reads from and writes to the shared `AgentState`. Fields managed by this agent:

| Field | Type | Description |
|-------|------|-------------|
| `review_passed` | bool | `True` if no blocking issues were found in the latest pass |
| `review_findings` | list[str] | Structured finding strings, e.g. `[BLOCKING] SECURITY: hardcoded token in controller.go:42` |
| `review_summary` | str | Human-readable verdict: pass message or summary of blocking issues |
| `review_iteration` | int | Current iteration count; `0` means the review has not yet run |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `QODO_REVIEW_ENABLED=false` | Review phase skipped; state fields left unset |
| Qodo CLI not found or exits with error | Logs warning, falls back to Claude-only review |
| Claude API call failure | Logs error, raises `CodeReviewAgentError` |
| `MAX_REVIEW_ITERATIONS` reached | Logs warning, sets `review_passed=False`, pipeline continues to Testing |

---

[← Previous: Testing Agent](testing-agent.md) | [Next: Docs Agent →](docs-agent.md)
