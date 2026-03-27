# Feature SDLC Automation for Shipwright / OpenShift Builds

AI-powered pipeline that automates the full feature development lifecycle — from Jira ticket to production-ready Go code, tests, and documentation.

---

## What It Does

You provide a Jira ticket (or a plain feature description). The system runs five AI agents through each phase of the software development lifecycle and delivers a complete set of artifacts: architecture design documents, production Go code, code review findings with an auto-fix loop, Ginkgo v2 test files, and PR-ready documentation. Each phase validates its outputs before passing state to the next agent, so failures surface immediately rather than propagating silently through the pipeline.

---

## The SDLC Flow

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    Feature SDLC Pipeline                            │
├──────────┬──────────┬─────────────┬──────────┬──────────────────────┤
│  Phase 1 │  Phase 2 │   Phase 2.5 │  Phase 3 │       Phase 4        │
│  DESIGN  │  DEVELOP │ CODE REVIEW │  TESTING │   DOCUMENTATION      │
├──────────┼──────────┼─────────────┼──────────┼──────────────────────┤
│ Arch     │ Go code  │ Blocking /  │ Unit     │ PR Summary           │
│ analysis │ PR desc  │ Warning     │ Integr.  │ Release Notes        │
│ Risks    │ API types│ findings    │ E2E      │ SHIP / JTBD docs     │
│ Impl plan│ Tests    │ Auto-fix ↺  │ Ginkgo v2│                      │
└──────────┴──────────┴─────────────┴──────────┴──────────────────────┘
         Input: Jira Ticket or Feature Description
         Output: /output-dir with code/, tests/, design/, docs/
```

The code review phase includes an auto-fix loop. Blocking findings route the pipeline back to the development agent for a retry, up to `MAX_REVIEW_ITERATIONS`:

```text
Development → Code Review ──PASS──→ Testing
                   │
                  FAIL (blocking findings)
                   │
                   └──→ Development (retry, max MAX_REVIEW_ITERATIONS)
```

---

## SDLC Phase Details

| Phase              | Agent               | Key Inputs                            | Key Outputs                                                                                 |
| ------------------ | ------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------- |
| 1 · Design         | Design Agent        | Jira ticket, repo paths               | Architecture analysis, impacted components, risks, acceptance criteria, implementation plan |
| 2 · Development    | Development Agent   | Design analysis, implementation plan  | Go source files, PR description, API types                                                  |
| 2.5 · Code Review  | Code Review Agent   | Generated code                        | BLOCKING/WARNING findings, pass/fail verdict, auto-fix loop                                 |
| 3 · Testing        | Testing Agent       | Design + code                         | Unit, integration, e2e Ginkgo v2 test files, test plan                                     |
| 4 · Documentation  | Documentation Agent | All phase outputs                     | PR summary, release notes, SHIP docs, JTBD docs                                             |
| Publish            | publish.py          | Output directory                      | GitHub PR, Jira comments/attachments                                                        |

---

## Repository Support

- **Upstream (Shipwright)**: configured via `SHIPWRIGHT_REPO_PATH` — the open-source Shipwright Build repository, used for design context and component analysis.
- **Downstream (OpenShift Builds)**: configured via `OPENSHIFT_BUILDS_REPO_PATH` — the Red Hat downstream fork, used for integration context and downstream-specific concerns.

---

## Quick Start

```bash
# 1. Install
git clone <repo> && cd muilti-agents-ocp-builds
uv venv && uv pip install -r requirements.txt
cp .env.example .env  # fill in credentials

# 2. Run from a Jira ticket
uv run python scripts/orchestrate.py \
  --jira-ticket BUILD-1707 \
  --output-dir ./output/BUILD-1707

# 3. Monitor in real time
uv run python scripts/run_dashboard.py  # http://localhost:8080

# 4. Publish artifacts
uv run python scripts/publish.py \
  --output-dir ./output/BUILD-1707 \
  --push-code --push-jira
```

See [Setup and Quick Start](docs/user-guide/01-getting-started/quick-start.md) for full configuration — Jira, GitHub, Qodo, and Vertex AI.

---

## Output Structure

```text
output/BUILD-1707/
├── design/
│   ├── design_analysis.md      # Architecture decisions, impacted components
│   └── implementation_plan.md  # Step-by-step implementation guide
├── code/                       # Production Go source files
├── tests/
│   ├── unit/                   # Ginkgo v2 unit tests
│   ├── integration/            # Integration test files
│   └── e2e/                    # End-to-end test files
├── docs/
│   ├── pr_description.md       # Ready-to-use GitHub PR description
│   └── release_notes.md        # Release notes for the feature
└── state.json                  # Full pipeline state snapshot
```

---

## Documentation

[User Guide](docs/user-guide/README.md) — full reference

| Section | Content |
|---------|---------|
| [Setup & Quick Start](docs/user-guide/01-getting-started/quick-start.md) | All integrations: Jira, GitHub, Qodo, Vertex AI, repo paths |
| [Architecture](docs/user-guide/02-concepts/architecture.md) | Pipeline design, state management, security layers |
| [Agents](docs/user-guide/03-agents/design-agent.md) | Per-agent reference |
| [Dashboard](docs/user-guide/04-dashboard/overview.md) | Real-time monitoring |
| [Authentication](docs/user-guide/05-authentication/authentication.md) | Vertex AI setup |
| [Publishing](docs/user-guide/09-integrations/publish.md) | Push to GitHub / Jira |

---

## Requirements

| Requirement | Detail |
|-------------|--------|
| Python | 3.11+ |
| Claude | Google Vertex AI (Application Default Credentials) |
| Jira | API token for ticket fetching |
| GitHub | PAT for PR enrichment and publishing |
| Qodo | Optional — Claude is used as fallback if not installed |
