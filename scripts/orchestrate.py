#!/usr/bin/env python3
"""
Orchestrate the multi-agent workflow.

Runs agents sequentially with output validation between phases.
Set MANUAL_APPROVAL=true in .env to pause for user approval between phases.
"""
import json
import logging
import os
import pathlib
import re
import sys
import time
import uuid
import argparse
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

MANUAL_APPROVAL = os.getenv("MANUAL_APPROVAL", "false").lower() == "true"

from orchestrator.workflow import WorkflowOrchestrator

# Keys that WorkflowOrchestrator.run() sets from its explicit parameters.
# Excluded from extra_state to avoid duplication.
_CORE_STATE_KEYS = frozenset({
    "session_id", "issue_title", "issue_description", "issue_type",
    "repo_path", "repo_paths", "current_phase",
})


# -- helpers ------------------------------------------------------------------

def print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_final_summary(
    state: dict,
    output_dir: str | None = None,
    total_duration: float | None = None,
) -> None:
    print_header("Workflow Complete")
    print(f"  Session ID: {state.get('session_id', 'N/A')}")
    print(f"  Final phase: {state.get('current_phase', 'N/A')}")
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

    def _strip_test_prefix(path: str) -> str:
        """Remove leading test category prefix from Claude-generated paths."""
        stripped = re.sub(r'^test/(unit|integration|e2e|e2e_tests)/', '', path)
        stripped = re.sub(r'^test/', '', stripped)
        return stripped

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
            clean_name = _strip_test_prefix(filename)
            target = (root / "tests" / "unit" / clean_name).resolve()
            if not str(target).startswith(str(root.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {filename}")
                continue
            _write(pathlib.Path("tests") / "unit" / clean_name, content)

    # tests/integration/<filename>
    for filename, content in (state.get("integration_tests") or {}).items():
        if content:
            clean_name = _strip_test_prefix(filename)
            target = (root / "tests" / "integration" / clean_name).resolve()
            if not str(target).startswith(str(root.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {filename}")
                continue
            _write(pathlib.Path("tests") / "integration" / clean_name, content)

    # tests/e2e/<filename>
    for filename, content in (state.get("e2e_tests") or {}).items():
        if content:
            clean_name = _strip_test_prefix(filename)
            target = (root / "tests" / "e2e" / clean_name).resolve()
            if not str(target).startswith(str(root.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {filename}")
                continue
            _write(pathlib.Path("tests") / "e2e" / clean_name, content)

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
    github_issue: str | None = None,
    dry_run: bool = False,
    output_dir: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Run the full multi-agent workflow with validation and optional approval.

    Args:
        title: Issue/feature title.
        description: Issue/feature description.
        issue_type: Type of issue ("feature", "bug", or "refactor").
        repo_path: Optional path to the Shipwright repository for code analysis.
        jira_ticket: Optional Jira ticket ID to fetch title/description from.
        github_issue: Optional GitHub issue reference (URL, owner/repo#N, or SHIP-NNN).
        dry_run: If True, use mock data instead of real API calls.
        output_dir: Optional path to save all pipeline artifacts after completion.
        session_id: Optional session ID to use (set by web UI when launching from dashboard).

    Returns:
        Final accumulated state dictionary. The key ``current_phase`` will be
        ``"done"`` on full success, or the last completed phase on early exit.
    """
    session_id = session_id or str(uuid.uuid4())[:8]
    pipeline_start = time.time()

    # Build repo_paths from repos.yaml, env vars, and CLI arg
    from config.repo_config import load_repo_paths
    repo_paths = load_repo_paths(cli_repo_path=repo_path)
    # Use first repo_path as primary for backward compatibility
    repo_path = repo_paths[0] if repo_paths else None

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

    # Placeholder state for pre-phase enrichments and artifact saving
    state: dict = {
        "session_id": session_id,
        "issue_title": title,
        "issue_description": description,
        "issue_type": issue_type,
        "repo_path": repo_path,
        "repo_paths": repo_paths,
        "current_phase": "init",
    }

    try:
        # -- Pre-phase: Jira ticket fetch ----------------------------------------
        if jira_ticket:
            print_header(f"Fetching Jira Ticket: {jira_ticket}")
            _dry_run_set_by_us = False
            if dry_run and os.getenv("DRY_RUN", "").lower() != "true":
                os.environ["DRY_RUN"] = "true"
                _dry_run_set_by_us = True
            try:
                from integrations.jira import fetch_jira_ticket as _fetch_jira
                jira_state = _fetch_jira(jira_ticket)

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
                        from integrations.github import fetch_github_prs
                        github_pr_data_result = fetch_github_prs(github_pr_urls)
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

        # -- Pre-phase: GitHub issue fetch ----------------------------------------
        if github_issue:
            from tools.github_client import parse_github_issue_ref, GitHubClient, get_github_client
            parsed = parse_github_issue_ref(github_issue)
            if parsed:
                owner, repo, number = parsed
                gh_client = get_github_client()
                issue_data = gh_client.fetch_issue(owner, repo, number)
                if issue_data:
                    if not title:
                        title = issue_data["title"]
                    if not description:
                        description = issue_data["body"]
                    elif issue_data["body"]:
                        description = f"{description}\n\n---\n**GitHub Issue {owner}/{repo}#{number}:**\n{issue_data['body']}"
                    logger.info(f"Loaded GitHub issue {owner}/{repo}#{number}: {issue_data['title']}")
                else:
                    logger.warning(f"Could not fetch GitHub issue: {github_issue}")
            else:
                logger.warning(f"Could not parse GitHub issue reference: {github_issue}")

        # -- Run the pipeline via WorkflowOrchestrator ---------------------------
        orchestrator = WorkflowOrchestrator(
            session_id=session_id,
            repo_path=repo_path,
            repo_paths=repo_paths,
            output_dir=pathlib.Path(output_dir) if output_dir else None,
        )

        extra_state = {k: v for k, v in state.items() if k not in _CORE_STATE_KEYS}

        state = orchestrator.run(
            title=title,
            description=description,
            issue_type=issue_type,
            extra_state=extra_state if extra_state else None,
        )

        total_duration = time.time() - pipeline_start
        print_final_summary(state, output_dir=output_dir, total_duration=total_duration)
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
        "--github-issue",
        help="GitHub issue reference (URL, owner/repo#N, or SHIP-NNN). "
             "Fetches title and description from GitHub.",
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
    parser.add_argument(
        "--session-id",
        default=None,
        metavar="SESSION_ID",
        help="Session ID to use (set by web UI when launching from dashboard).",
    )
    args = parser.parse_args()

    if args.debug:
        os.environ["LOG_LEVEL"] = "DEBUG"

    if not args.jira_ticket and not args.title and not args.github_issue:
        parser.error("either --title, --jira-ticket, or --github-issue is required")

    result = orchestrate(
        title=args.title,
        description=args.description,
        issue_type=args.issue_type,
        repo_path=args.repo_path,
        jira_ticket=args.jira_ticket,
        github_issue=args.github_issue,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        session_id=args.session_id,
    )
    sys.exit(0 if result.get("current_phase") == "done" else 1)


if __name__ == "__main__":
    main()
