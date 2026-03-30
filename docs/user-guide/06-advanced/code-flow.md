# Code Flow Reference

This document maps every major function call in the system, showing who calls what and in which file it lives. Use it when you need to trace a bug, understand how data moves between phases, or onboard to the codebase without reading every file top to bottom.

---

## 1. Top-Level Entry Points

The system has two entry points depending on how you invoke it:

| Entry point | File | When used |
| --- | --- | --- |
| `orchestrate()` | `scripts/orchestrate.py` | CLI invocation by a user or CI job. Runs each phase sequentially, calls validators between phases, and supports manual approval gates. Accepts `--output-dir <path>` to save all pipeline artifacts (JSON state, per-phase markdown files) to a local directory. |
| `build_workflow()` | `agents/graph.py` | LangGraph pipeline invocation. Builds a `StateGraph` where nodes are the five agents and routing is driven by `state["current_phase"]`. Used when you want LangGraph to manage state and edges rather than imperative Python. |

Both paths call the same five agent functions (`run_design`, `run_development`, `run_code_review`, `run_testing`, `run_docs`) and emit heartbeats to the dashboard after each phase.

---

## 2. Orchestrate Flow (`scripts/orchestrate.py`)

`orchestrate()` is the primary user-facing entry point. It runs each agent in order, validates the output, and (when enabled) pauses for manual approval before continuing.

```
orchestrate(title, description, repo_path, issue_type)
  │
  ├─ Pre-flight: Skills registry calls
  │   ├─ default_registry.get("fetch_jira_ticket").run({"ticket_id": jira_ticket})
  │   │   → resolves via SkillRegistry [skills/registry.py]
  │   │   → FetchJiraTicketSkill._execute() [skills/jira.py]
  │   │       ├─ fetch_ticket() [mcp/jira_stub.py]
  │   │       └─ map_ticket_to_state() [tools/jira_client.py]
  │   │           └─ redact_pii(ticket_dict, source="jira:<id>") [tools/pii_redactor.py]
  │   │               ← PII redacted here before data enters state
  │   │   → returns merged AgentState Jira fields (already redacted)
  │   └─ default_registry.get("fetch_github_prs").run({"pr_urls": urls})
  │       → FetchGitHubPRsSkill._execute() [skills/github.py]
  │           └─ GitHubClient.fetch_prs_from_urls() [tools/github_client.py]
  │               └─ GitHubClient.fetch_pr() per URL
  │                   └─ redact_pii(pr_dict, source="github:owner/repo#N") [tools/pii_redactor.py]
  │                       ← PII redacted here before data enters state
  │       → returns {"pr_data": [...]} (already redacted)
  │
  │   Note: both skills check DRY_RUN via Skill.run() [skills/base.py] before
  │   dispatching. In dry-run mode _mock_response() is called instead of _execute().
  │
  ├─ Phase 1: Design
  │   ├─ run_design() [agents/design_agent.py]
  │   │   ├─ get_anthropic_client() [config/auth_config.py]
  │   │   ├─ _gather_repo_context()
  │   │   │   └─ RepoSearch() [tools/repo_search.py]
  │   │   │       ├─ search_files()
  │   │   │       ├─ find_kubernetes_crds()
  │   │   │       └─ analyze_go_packages()
  │   │   ├─ _build_component_context()
  │   │   │   └─ get_component_info() [config/shipwright_components.py]
  │   │   ├─ _build_analysis_prompt()
  │   │   ├─ client.messages.create() → Claude API
  │   │   ├─ _parse_design_output()
  │   │   └─ emit_heartbeat() [dashboard/heartbeat.py]
  │   └─ validate_phase("design", state) [agents/validators.py]
  │       └─ validate_design_output()
  │
  ├─ Phase 2: Development
  │   ├─ run_development() [agents/go_k8s_developer.py]
  │   │   ├─ _validate_context()
  │   │   ├─ get_anthropic_client() [config/auth_config.py]
  │   │   ├─ emit_heartbeat() [dashboard/heartbeat.py]
  │   │   ├─ _build_development_prompt()
  │   │   ├─ client.messages.create() → Claude API
  │   │   ├─ _parse_development_output()
  │   │   │   ├─ _split_into_sections()
  │   │   │   ├─ _extract_code_files()
  │   │   │   │   ├─ _extract_file_path()
  │   │   │   │   └─ _extract_first_code_block()
  │   │   │   └─ _extract_bullet_points()
  │   │   ├─ _synthesize_file_tracking()
  │   │   └─ emit_heartbeat() [dashboard/heartbeat.py]
  │   └─ validate_phase("develop", state) [agents/validators.py]
  │       └─ validate_develop_output()
  │
  ├─ Phase 2.5: Code Review
  │   ├─ run_code_review() [agents/code_review_agent.py]
  │   │   ├─ get_anthropic_client() [config/auth_config.py]
  │   │   ├─ _format_code_for_review()
  │   │   ├─ client.messages.create() → Claude API  (or _run_qodo_review() if QODO_CLI_PATH set)
  │   │   ├─ _parse_review_output()
  │   │   └─ emit_heartbeat() [dashboard/heartbeat.py]
  │   └─ validate_phase("code_review", state) [agents/validators.py]
  │       └─ validate_review_output()
  │           └─ (never blocks — surfaces FAIL as warning, loop handled by graph router)
  │
  ├─ Phase 3: Testing
  │   ├─ run_testing() [agents/testing_agent.py]
  │   │   ├─ _validate_context()
  │   │   ├─ get_anthropic_client() [config/auth_config.py]
  │   │   ├─ detect_patterns_in_description() [config/testing_config.py]
  │   │   ├─ _build_testing_prompt()
  │   │   ├─ client.messages.create() → Claude API
  │   │   └─ _parse_test_output()
  │   │       ├─ _split_into_sections()
  │   │       ├─ _extract_code_block()
  │   │       ├─ yaml.safe_load()
  │   │       └─ _extract_test_code()
  │   └─ validate_phase("testing", state) [agents/validators.py]
  │       └─ validate_testing_output()
  │
  └─ Phase 4: Documentation
      ├─ run_docs() [agents/docs_agent.py]
      │   ├─ _validate_context()
      │   ├─ _fetch_rag_context()
      │   │   └─ RAGSearch() [tools/rag_search.py]
      │   │       ├─ search_shipwright_docs()
      │   │       ├─ extract_code_examples()
      │   │       ├─ search_similar_code()
      │   │       └─ search_api_patterns()
      │   ├─ _extract_api_names()
      │   ├─ _process_input_files()
      │   ├─ _build_context_message()
      │   ├─ get_anthropic_client() [config/auth_config.py]
      │   ├─ client.messages.create() → Claude API
      │   ├─ _parse_docs_response()
      │   │   ├─ _split_into_sections()
      │   │   └─ _parse_docs_changes()
      │   └─ emit_heartbeat() [dashboard/heartbeat.py]
      └─ validate_phase("docs", state) [agents/validators.py]
          └─ validate_docs_output()
```

### Notes on the orchestrate flow

- `_validate_context()` runs at the start of phases 2, 3, and 4. It checks that required fields from the previous phase are non-empty before spending tokens on an API call.
- `validate_phase()` runs after each agent returns. If validation fails, `orchestrate()` raises an exception and halts the pipeline rather than passing bad data downstream.
- `emit_heartbeat()` is called at least once per phase. The development agent calls it twice — once before the API call (to signal the phase has started) and once after (to signal completion with token counts).
- `detect_patterns_in_description()` in the testing phase scans the issue description for keywords (build strategy names, source types) and injects matching Ginkgo v2 templates into the prompt.
- Each phase prints a numbered header to the terminal when it starts (e.g., `Phase 1/5 · Design`, `Phase 2.5/5 · Code Review`) and prints its elapsed duration when it completes (e.g., `Design completed in 45.2s`).
- After all phases finish, a final summary is printed containing the total pipeline duration, the path to saved output artifacts, and the dashboard URL. Pass `--output-dir <path>` to control where artifacts are written; without this flag, artifacts are not saved to disk.

---

## 3. LangGraph Pipeline (`agents/graph.py`)

`build_workflow()` constructs a compiled LangGraph `StateGraph`. Each node wraps one agent function and emits a heartbeat. The `should_continue` router reads `state["current_phase"]` after each node to decide what runs next.

```
build_workflow()
  └─ StateGraph(AgentState)
      ├─ design_node()
      │   ├─ run_design() [agents/design_agent.py]
      │   └─ emit_heartbeat() [dashboard/heartbeat.py]
      ├─ develop_node()
      │   ├─ run_development() [agents/go_k8s_developer.py]
      │   └─ emit_heartbeat() [dashboard/heartbeat.py]
      ├─ code_review_node()
      │   ├─ run_code_review() [agents/code_review_agent.py]
      │   └─ emit_heartbeat() [dashboard/heartbeat.py]
      ├─ testing_node()
      │   ├─ run_testing() [agents/testing_agent.py]
      │   └─ emit_heartbeat() [dashboard/heartbeat.py]
      ├─ docs_node()
      │   ├─ run_docs() [agents/docs_agent.py]
      │   └─ emit_heartbeat() [dashboard/heartbeat.py]
      └─ should_continue() [router]
          └─ reads state["current_phase"] → routes to next node or END
```

### Routing logic

`should_continue()` maps phase values to the next node:

| `current_phase` value | Next node |
|-----------------------|-----------|
| `design_complete` | `develop_node` |
| `develop_complete` | `code_review_node` |
| `review_complete` + `review_passed=True` or `review_iteration ≥ MAX_REVIEW_ITERATIONS` | `testing_node` |
| `review_complete` + `review_passed=False` + `review_iteration < MAX_REVIEW_ITERATIONS` | `develop_node` (auto-fix loop) |
| `testing_complete` | `docs_node` |
| `docs_complete` | `END` |
| any error value | `END` |

Each node updates `state["current_phase"]` before returning, which is what `should_continue` reads on the next evaluation. State is stored in `graph/state.py` as `AgentState`, a `TypedDict(total=False)` with an `add_messages` annotation on the `messages` field.

---

## 4. Dashboard Backend (`dashboard/backend.py`)

The dashboard is a FastAPI application. A background task runs periodic cleanup on startup. The main data path is the `POST /api/heartbeat` route, which enriches incoming payloads before writing them to SQLite.

```
FastAPI app
  ├─ startup: periodic_cleanup() [background task]
  │   └─ db.cleanup_old_sessions()
  │
  └─ Routes:
      ├─ POST /api/heartbeat → receive_heartbeat()
      │   ├─ enrich_heartbeat() [dashboard/enrichers.py]
      │   │   └─ EnricherPipeline.run()
      │   │       ├─ ModelInfoEnricher.enrich()
      │   │       ├─ TokenCountEnricher.enrich()
      │   │       ├─ PhaseStatusEnricher.enrich()
      │   │       ├─ ComponentsEnricher.enrich()
      │   │       ├─ RisksEnricher.enrich()
      │   │       ├─ IssueInfoEnricher.enrich()
      │   │       └─ TimestampEnricher.enrich()
      │   ├─ db.upsert_session()
      │   └─ db.insert_heartbeat()
      │
      ├─ GET /api/sessions → get_sessions()
      │   └─ db.get_sessions()
      ├─ GET /api/sessions/{id} → get_session()
      │   └─ db.get_session()
      ├─ DELETE /api/sessions/completed → clear_completed_sessions()
      │   └─ db.clear_completed_sessions()
      └─ GET /api/health → health()
```

### Notes on the enricher pipeline

Each enricher receives the raw heartbeat dict and returns an augmented copy. They run in the fixed order shown above. The pipeline is additive — a failing enricher logs a warning and passes the dict through unchanged rather than crashing the request.

The SQLite database is stored at `/tmp/claude/dashboard.db` by default (overridden by the `DASHBOARD_DB_PATH` environment variable). `db.upsert_session()` creates or updates the session row; `db.insert_heartbeat()` appends the individual heartbeat event.

---

## 5. Heartbeat Flow (`dashboard/heartbeat.py`)

Agents do not write to the database directly. They call `emit_heartbeat()`, which sends an HTTP POST to the running dashboard process. If the dashboard is not running, the failure is silently swallowed so agents are never blocked by dashboard availability.

```
emit_heartbeat(agent_name, state, event, details)
  └─ HeartbeatEmitter.emit_from_state()
      └─ requests.post("http://localhost:8080/api/heartbeat", json=payload)
          └─ [silently ignored if dashboard unreachable]
```

The payload includes the `session_id` from `state`, the agent name, the event type, token usage, and any additional details passed by the caller. The dashboard backend's enricher pipeline then augments this payload before storage.

---

## 6. Logging (`utils/file_logger.py`)

Two functions cover the two logging patterns used in the codebase.

```
get_logger(name)
  ├─ logging.getLogger(name)
  ├─ RotatingFileHandler → logs/agents/<name>.log
  └─ StreamHandler → stdout

get_session_logger(session_id, agent_name)
  └─ get_logger() with session-specific log path
      └─ logs/sessions/<session_id>/<agent_name>.log
```

`get_logger()` is used for module-level loggers (dashboard, graph). `get_session_logger()` is used inside agent functions so that each workflow run gets its own log directory, making it easy to isolate logs for a specific `session_id` when debugging.

---

## 7. Shared Dependencies

These modules are consumed by multiple callers across the codebase. When modifying them, check all listed consumers for impact.

| Module | Exported symbol | Used by |
|--------|----------------|---------|
| `config/auth_config.py` | `get_anthropic_client()` | All 5 agents (`design_agent`, `go_k8s_developer`, `code_review_agent`, `testing_agent`, `docs_agent`) |
| `dashboard/heartbeat.py` | `emit_heartbeat()` | All 5 agents + all 5 graph nodes in `agents/graph.py` |
| `agents/validators.py` | `validate_phase()` | `scripts/orchestrate.py` (called after each phase) |
| `config/agent_prompts.py` | System prompt constants | All 5 agents (injected as the `system` argument to `client.messages.create()`) |
| `utils/file_logger.py` | `get_logger()`, `get_session_logger()` | All 5 agents, `dashboard/backend.py`, `agents/graph.py` |
| `skills/__init__.py` | `default_registry` | `scripts/orchestrate.py`, `scripts/test_agents.py` (entry points only — agents do not import from `skills/`) |
| `tools/pii_redactor.py` | `redact_pii()`, `is_redaction_enabled()` | `tools/jira_client.py`, `tools/github_client.py` (called at the end of each fetch function) |

---

[← Dry Run Mode](dry-run-mode.md) | [Output Validation →](output-validation.md)
