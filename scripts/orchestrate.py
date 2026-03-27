#!/usr/bin/env python3
"""
Orchestrate the multi-agent workflow.

Runs agents sequentially with output validation between phases.
Set MANUAL_APPROVAL=true in .env to pause for user approval between phases.
"""
import json
import os
import pathlib
import sys
import time
import uuid
import argparse
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MANUAL_APPROVAL = os.getenv("MANUAL_APPROVAL", "false").lower() == "true"

from agents.validators import validate_phase


# -- helpers ------------------------------------------------------------------

def print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_phase_summary(phase: str, result) -> None:
    """Print a formatted summary of a completed phase."""
    status = "PASSED" if result.passed else "FAILED"
    print(f"\n{'-'*60}")
    print(f"  Phase: {phase.upper()}  |  Validation: {status}")
    print(f"{'-'*60}")
    for key, val in result.summary.items():
        print(f"  {key}: {val}")
    if result.warnings:
        print("\n  Warnings:")
        for w in result.warnings:
            print(f"     - {w}")
    if result.issues:
        print("\n  Issues (blocking):")
        for issue in result.issues:
            print(f"     - {issue}")
    print()


def request_approval(phase: str, next_phase: str) -> bool:
    """Ask user for approval to continue. Returns True to continue, False to stop."""
    if not MANUAL_APPROVAL:
        return True
    print(f"  Next phase: {next_phase.upper()}")
    try:
        response = input(f"\n  Continue to {next_phase}? [Y/n]: ").strip().lower()
        return response not in ("n", "no")
    except (EOFError, KeyboardInterrupt):
        print("\n  Interrupted.")
        return False


def print_final_summary(
    completed_phases: list[str],
    state: dict,
    output_dir: str | None = None,
    total_duration: float | None = None,
) -> None:
    print_header("Workflow Complete")
    print(f"  Completed phases: {', '.join(p.upper() for p in completed_phases)}")
    print(f"  Session ID: {state.get('session_id', 'N/A')}")
    print(f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if total_duration is not None:
        mins, secs = divmod(int(total_duration), 60)
        print(f"  Total duration: {mins}m {secs}s")

    # Stats
    code_files = state.get("code_files") or []
    n_code = len(code_files) if isinstance(code_files, list) else len(code_files)
    n_unit = len(state.get("unit_tests") or {})
    n_int = len(state.get("integration_tests") or {})
    if n_code:
        print(f"  Code files: {n_code}  |  Tests: {n_unit} unit, {n_int} integration")

    if output_dir:
        print(f"\n  Artifacts: {output_dir}")
    print(f"  Dashboard: http://localhost:8080")
    print()


# -- artifact saving ----------------------------------------------------------

def _save_artifacts(state: dict, output_dir: str) -> pathlib.Path:
    """Save all pipeline artifacts to a directory structure.

    Args:
        state: The final state dictionary from the orchestrate() workflow.
        output_dir: Path to the root output directory (created if absent).

    Returns:
        The resolved output directory as a ``pathlib.Path``.
    """
    root = pathlib.Path(output_dir).resolve()
    saved: list[str] = []

    if root.exists() and any(root.iterdir()):
        print(f"  WARNING: Output directory already exists and will be overwritten: {root}")

    def _write(rel: pathlib.Path, content: str) -> None:
        target = root / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            saved.append(str(rel))
            print(f"  Saved: {rel}")
        except OSError as e:
            print(f"  ERROR saving {rel}: {e}")

    # design/design_analysis.md
    design_analysis = state.get("design_analysis")
    if design_analysis:
        _write(pathlib.Path("design") / "design_analysis.md", design_analysis)

    # design/implementation_plan.md  (one item per line, prefixed with "- ")
    implementation_plan = state.get("implementation_plan")
    if implementation_plan:
        lines = "\n".join(f"- {step}" for step in implementation_plan)
        _write(pathlib.Path("design") / "implementation_plan.md", lines)

    # code/<original_path>  — support both code_files and code_changes keys
    # code_files from development agent is a list of dicts with "path"/"content" keys;
    # code_changes may be a plain dict mapping path→content.
    code_raw = state.get("code_files") or state.get("code_changes") or {}
    if isinstance(code_raw, list):
        code_items = ((item["path"], item.get("content", "")) for item in code_raw)
    else:
        code_items = code_raw.items()
    for file_path, content in code_items:
        if content:
            target = (root / "code" / file_path).resolve()
            if not str(target).startswith(str(root.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {file_path}")
                continue
            _write(pathlib.Path("code") / file_path, content)

    # tests/unit/<filename>
    for filename, content in (state.get("unit_tests") or {}).items():
        if content:
            target = (root / "tests" / "unit" / filename).resolve()
            if not str(target).startswith(str(root.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {filename}")
                continue
            _write(pathlib.Path("tests") / "unit" / filename, content)

    # tests/integration/<filename>
    for filename, content in (state.get("integration_tests") or {}).items():
        if content:
            target = (root / "tests" / "integration" / filename).resolve()
            if not str(target).startswith(str(root.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {filename}")
                continue
            _write(pathlib.Path("tests") / "integration" / filename, content)

    # tests/e2e/<filename>
    for filename, content in (state.get("e2e_tests") or {}).items():
        if content:
            target = (root / "tests" / "e2e" / filename).resolve()
            if not str(target).startswith(str(root.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {filename}")
                continue
            _write(pathlib.Path("tests") / "e2e" / filename, content)

    # docs/pr_description.md
    pr_description = state.get("pr_description")
    if pr_description:
        _write(pathlib.Path("docs") / "pr_description.md", pr_description)

    # docs/pr_summary.md
    pr_summary = state.get("pr_summary")
    if pr_summary:
        _write(pathlib.Path("docs") / "pr_summary.md", pr_summary)

    # docs/release_notes.md
    release_notes = state.get("release_notes")
    if release_notes:
        _write(pathlib.Path("docs") / "release_notes.md", release_notes)

    # state.json — filter to JSON-serializable primitive fields only
    serializable_state: dict = {}
    for key, value in state.items():
        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
            serializable_state[key] = value
    state_json = json.dumps(serializable_state, indent=2, default=str)
    _write(pathlib.Path("state.json"), state_json)

    print(f"\n  Artifacts written to: {root}  ({len(saved)} files)")
    return root


# -- main workflow ------------------------------------------------------------

def orchestrate(
    title: str | None = None,
    description: str | None = None,
    issue_type: str = "feature",
    repo_path: str | None = None,
    jira_ticket: str | None = None,
    dry_run: bool = False,
    output_dir: str | None = None,
) -> dict:
    """Run the full multi-agent workflow with validation and optional approval.

    Args:
        title: Issue/feature title.
        description: Issue/feature description.
        issue_type: Type of issue ("feature", "bug", or "refactor").
        repo_path: Optional path to the Shipwright repository for code analysis.
        jira_ticket: Optional Jira ticket ID to fetch title/description from.
        dry_run: If True, use mock data instead of real API calls.
        output_dir: Optional path to save all pipeline artifacts after completion.

    Returns:
        Final accumulated state dictionary. The key ``current_phase`` will be
        ``"done"`` on full success, or the last completed phase on early exit.
    """
    session_id = str(uuid.uuid4())[:8]
    completed_phases: list[str] = []
    pipeline_start = time.time()

    state: dict = {
        "session_id": session_id,
        "issue_title": title,
        "issue_description": description,
        "issue_type": issue_type,
        "repo_path": repo_path,
        "current_phase": "init",
    }

    # Propagate orchestrator session_id to the global heartbeat emitter so all
    # emit_heartbeat() calls use the same session throughout the pipeline.
    try:
        from dashboard.heartbeat import get_global_emitter
        emitter = get_global_emitter()
        emitter.session_id = session_id
    except Exception:
        pass  # dashboard unavailable, non-blocking

    print_header(f"Multi-Agent Workflow: {title or jira_ticket or 'TBD'}")
    print(f"  Session: {session_id}")
    print(f"  Manual approval: {'ON' if MANUAL_APPROVAL else 'OFF'}")
    if MANUAL_APPROVAL:
        print("  You will be asked to approve each phase before continuing.")

    try:
        # -- Pre-phase: Jira ticket fetch ----------------------------------------
        if jira_ticket:
            print_header(f"Fetching Jira Ticket: {jira_ticket}")
            _dry_run_set_by_us = False
            if dry_run and os.getenv("DRY_RUN", "").lower() != "true":
                os.environ["DRY_RUN"] = "true"
                _dry_run_set_by_us = True
            try:
                from skills import default_registry
                jira_state = default_registry.get("fetch_jira_ticket").run({"ticket_id": jira_ticket})

                state.update(jira_state)
                title = state["issue_title"]
                description = state["issue_description"]
                issue_type = state["issue_type"]

                print(f"  Ticket:   {jira_ticket}")
                print(f"  Title:    {title}")
                print(f"  Priority: {state.get('jira_priority', 'N/A')}")
                labels = ', '.join(state.get('jira_labels', [])) or 'none'
                print(f"  Labels:   {labels}")
                linked = ', '.join(state.get('jira_linked_issues', [])) or 'none'
                print(f"  Linked:   {linked}")
                print(f"  URL:      {state.get('jira_ticket_url', '')}")

                # -- GitHub PR enrichment (optional) --
                github_pr_urls = state.get("github_pr_urls", [])
                if github_pr_urls:
                    try:
                        github_pr_data_result = default_registry.get("fetch_github_prs").run({"pr_urls": github_pr_urls})
                        github_pr_data = github_pr_data_result["pr_data"]
                        state["github_pr_data"] = github_pr_data
                        print(f"  GitHub PRs: {len(github_pr_data)} PR(s) fetched")
                        for pr in github_pr_data:
                            print(f"    #{pr['pr_number']} [{pr['state']}] {pr['title']}")
                    except Exception as e:
                        print(f"  GitHub PR fetch failed (non-blocking): {e}")
            except ConnectionError as e:
                print(f"\n  ERROR: {e}")
                return state
            except Exception as e:
                print(f"\n  Failed to fetch Jira ticket: {e}")
                return state
            finally:
                if _dry_run_set_by_us:
                    os.environ.pop("DRY_RUN", None)

        # -- Phase 1: Design ------------------------------------------------------
        print_header("Phase 1/5: Design Agent")
        from agents.design_agent import run_design
        try:
            phase_start = time.time()
            design_output = run_design(title, description, repo_path=repo_path)
            phase_duration = time.time() - phase_start
            state.update(design_output)
            state["current_phase"] = "design_complete"
            try:
                from dashboard.heartbeat import emit_heartbeat
                emit_heartbeat("design", state)
            except Exception as e:
                print(f"  [heartbeat] emit failed: {e}")
        except Exception as e:
            print(f"  Design Agent failed: {e}")
            return state

        result = validate_phase("design", state)
        print_phase_summary("Design", result)
        print(f"  Duration: {phase_duration:.1f}s")
        print(f"  Implementation steps: {len(state.get('implementation_plan', []))}")
        print(f"  Risks identified: {len(state.get('risks', []))}")
        print(f"  Acceptance criteria: {len(state.get('acceptance_criteria', []))}")
        if not result.passed:
            print("  Stopping workflow due to validation failure.")
            print("  Fix the issues above before continuing.")
            return state
        completed_phases.append("design")
        if not request_approval("design", "development"):
            print("  Workflow stopped by user after Design phase.")
            print_final_summary(completed_phases, state)
            return state

        # -- Phase 2: Development -------------------------------------------------
        print_header("Phase 2/5: Development Agent")
        from agents.go_k8s_developer import run_development
        try:
            phase_start = time.time()
            develop_output = run_development(state)
            phase_duration = time.time() - phase_start
            state.update(develop_output)
            state["current_phase"] = "develop_complete"
            try:
                from dashboard.heartbeat import emit_heartbeat
                emit_heartbeat("develop", state)
            except Exception as e:
                print(f"  [heartbeat] emit failed: {e}")
        except Exception as e:
            print(f"  Development Agent failed: {e}")
            return state

        result = validate_phase("develop", state)
        print_phase_summary("Development", result)
        print(f"  Duration: {phase_duration:.1f}s")
        _code_files = state.get("code_files") or []
        _total_lines = sum(
            len((f.get("content", "") if isinstance(f, dict) else "").splitlines())
            for f in (_code_files if isinstance(_code_files, list) else [])
        )
        print(f"  Files generated: {len(_code_files) if isinstance(_code_files, list) else len(_code_files)}")
        print(f"  Lines of code: ~{_total_lines}")
        if not result.passed:
            print("  Stopping workflow due to validation failure.")
            return state
        completed_phases.append("develop")
        if not request_approval("develop", "code_review"):
            print("  Workflow stopped by user after Development phase.")
            print_final_summary(completed_phases, state)
            return state

        # -- Phase 2.5: Code Review -----------------------------------------------
        print_header("Phase 2.5/5: Code Review Agent")
        from agents.code_review_agent import run_code_review
        phase_start = time.time()
        try:
            review_output = run_code_review(state)
            state.update(review_output)
            state["current_phase"] = "review_complete"
        except Exception as e:
            print(f"  Code Review Agent failed (non-blocking): {e}")
            # Code review failure is non-blocking — continue to testing
        phase_duration = time.time() - phase_start

        review_result = validate_phase("code_review", state)
        print_phase_summary("Code Review", review_result)
        print(f"  Duration: {phase_duration:.1f}s")
        completed_phases.append("code_review")
        if not request_approval("code_review", "testing"):
            print("  Workflow stopped by user after Code Review phase.")
            print_final_summary(completed_phases, state)
            return state

        # -- Phase 3: Testing -----------------------------------------------------
        print_header("Phase 3/5: Testing Agent")
        from agents.testing_agent import run_testing
        try:
            context = {
                "design_analysis": state.get("design_analysis", ""),
                "impacted_components": state.get("impacted_components", []),
                "acceptance_criteria": state.get("acceptance_criteria", []),
                "risks": state.get("risks", []),
                "implementation_plan": state.get("implementation_plan", []),
                "issue_title": title,
                "issue_description": description,
                "issue_type": issue_type,
                "session_id": session_id,
            }
            phase_start = time.time()
            testing_output = run_testing(context, output_dir=pathlib.Path(output_dir) if output_dir else None)
            phase_duration = time.time() - phase_start
            state.update(testing_output)
            state["current_phase"] = "testing_complete"
            try:
                from dashboard.heartbeat import emit_heartbeat
                emit_heartbeat("testing", state)
            except Exception as e:
                print(f"  [heartbeat] emit failed: {e}")
        except Exception as e:
            print(f"  Testing Agent failed: {e}")
            return state

        result = validate_phase("testing", state)
        print_phase_summary("Testing", result)
        print(f"  Duration: {phase_duration:.1f}s")
        _unit = len(state.get("unit_tests") or {})
        _integration = len(state.get("integration_tests") or {})
        _e2e = len(state.get("e2e_tests") or {})
        print(f"  Tests: {_unit} unit, {_integration} integration, {_e2e} e2e")
        if not result.passed:
            print("  Stopping workflow due to validation failure.")
            return state
        completed_phases.append("testing")
        if not request_approval("testing", "documentation"):
            print("  Workflow stopped by user after Testing phase.")
            print_final_summary(completed_phases, state)
            return state

        # -- Phase 4: Documentation -----------------------------------------------
        print_header("Phase 4/5: Documentation Agent")
        from agents.docs_agent import run_docs
        try:
            context = {
                "issue_title": title,
                "issue_description": description,
                "issue_type": issue_type,
                "design_analysis": state.get("design_analysis", ""),
                "implementation_plan": state.get("implementation_plan", []),
                "impacted_components": state.get("impacted_components", []),
                "risks": state.get("risks", []),
                "acceptance_criteria": state.get("acceptance_criteria", []),
                # development outputs
                "code_changes": state.get("code_changes", {}),
                "files_modified": state.get("files_modified", []),
                "pr_description": state.get("pr_description", ""),
                # testing outputs
                "test_results": state.get("test_results", {}),
                "test_summary": state.get("test_summary", ""),
                "test_plan": state.get("test_plan", ""),
                "coverage_gaps": state.get("coverage_gaps", []),
                "test_failures": state.get("test_failures", []),
                # repo context
                "repo_path": repo_path or ".",
                # github outputs
                "github_pr_urls": state.get("github_pr_urls", []),
                "github_pr_data": state.get("github_pr_data", []),
                # session
                "session_id": session_id,
            }
            phase_start = time.time()
            docs_output = run_docs(context)
            phase_duration = time.time() - phase_start
            state.update(docs_output)
            state["current_phase"] = "done"
            try:
                from dashboard.heartbeat import emit_heartbeat
                emit_heartbeat("docs", state)
            except Exception as e:
                print(f"  [heartbeat] emit failed: {e}")
        except Exception as e:
            print(f"  Documentation Agent failed: {e}")
            return state

        result = validate_phase("docs", state)
        print_phase_summary("Documentation", result)
        print(f"  Duration: {phase_duration:.1f}s")
        completed_phases.append("docs")

        total_duration = time.time() - pipeline_start
        print_final_summary(completed_phases, state, output_dir=output_dir, total_duration=total_duration)
        return state


    finally:
        if output_dir and state.get("current_phase") not in (None, "init"):
            print_header("Saving Artifacts")
            _save_artifacts(state, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the multi-agent OCP builds workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/orchestrate.py --title "Add timeout support" --description "..."
  MANUAL_APPROVAL=true uv run python scripts/orchestrate.py --title "..." --description "..."
  uv run python scripts/orchestrate.py --jira-ticket SHIP-123
  uv run python scripts/orchestrate.py --jira-ticket SHIP-123 --dry-run
        """,
    )
    parser.add_argument("--title", default=None, help="Issue/feature title")
    parser.add_argument("--description", default=None, help="Issue/feature description")
    parser.add_argument(
        "--issue-type",
        default="feature",
        choices=["feature", "bug", "refactor"],
        help="Type of issue",
    )
    parser.add_argument(
        "--repo-path",
        default=None,
        help="Path to Shipwright repository for code analysis",
    )
    parser.add_argument(
        "--jira-ticket",
        default=None,
        metavar="TICKET_ID",
        help="Jira ticket ID to fetch (e.g. SHIP-123). Fetches title, description, and acceptance criteria automatically.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock data instead of real API calls (no Jira or Claude API calls).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("OUTPUT_DIR"),
        metavar="PATH",
        help="Save all pipeline artifacts to this directory after completion.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    if args.debug:
        os.environ["LOG_LEVEL"] = "DEBUG"

    if not args.jira_ticket and not args.title:
        parser.error("either --title or --jira-ticket is required")

    result = orchestrate(
        title=args.title,
        description=args.description,
        issue_type=args.issue_type,
        repo_path=args.repo_path,
        jira_ticket=args.jira_ticket,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )
    sys.exit(0 if result.get("current_phase") == "done" else 1)


if __name__ == "__main__":
    main()
