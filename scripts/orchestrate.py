#!/usr/bin/env python3
"""
Orchestrate the multi-agent workflow.

Runs agents sequentially with output validation between phases.
Set MANUAL_APPROVAL=true in .env to pause for user approval between phases.
"""
import os
import sys
import uuid
import argparse
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

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


def print_final_summary(completed_phases: list[str], state: dict) -> None:
    print_header("Workflow Complete")
    print(f"  Completed phases: {', '.join(p.upper() for p in completed_phases)}")
    print(f"  Session ID: {state.get('session_id', 'N/A')}")
    print(f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


# -- main workflow ------------------------------------------------------------

def orchestrate(
    title: str,
    description: str,
    issue_type: str = "feature",
    repo_path: str = None,
) -> dict:
    """Run the full multi-agent workflow with validation and optional approval.

    Args:
        title: Issue/feature title.
        description: Issue/feature description.
        issue_type: Type of issue ("feature", "bug", or "refactor").
        repo_path: Optional path to the Shipwright repository for code analysis.

    Returns:
        Final accumulated state dictionary. The key ``current_phase`` will be
        ``"done"`` on full success, or the last completed phase on early exit.
    """
    session_id = str(uuid.uuid4())[:8]
    completed_phases: list[str] = []

    state: dict = {
        "session_id": session_id,
        "issue_title": title,
        "issue_description": description,
        "issue_type": issue_type,
        "repo_path": repo_path,
        "current_phase": "init",
    }

    print_header(f"Multi-Agent Workflow: {title}")
    print(f"  Session: {session_id}")
    print(f"  Manual approval: {'ON' if MANUAL_APPROVAL else 'OFF'}")
    if MANUAL_APPROVAL:
        print("  You will be asked to approve each phase before continuing.")

    # -- Phase 1: Design ------------------------------------------------------
    print_header("Phase 1: Design Agent")
    from agents.design_agent import run_design
    try:
        design_output = run_design(title, description, repo_path=repo_path)
        state.update(design_output)
        state["current_phase"] = "design_complete"
    except Exception as e:
        print(f"  Design Agent failed: {e}")
        return state

    result = validate_phase("design", state)
    print_phase_summary("Design", result)
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
    print_header("Phase 2: Development Agent")
    from agents.go_k8s_developer import run_development
    try:
        develop_output = run_development(state)
        state.update(develop_output)
        state["current_phase"] = "develop_complete"
    except Exception as e:
        print(f"  Development Agent failed: {e}")
        return state

    result = validate_phase("develop", state)
    print_phase_summary("Development", result)
    if not result.passed:
        print("  Stopping workflow due to validation failure.")
        return state
    completed_phases.append("develop")
    if not request_approval("develop", "testing"):
        print("  Workflow stopped by user after Development phase.")
        print_final_summary(completed_phases, state)
        return state

    # -- Phase 3: Testing -----------------------------------------------------
    print_header("Phase 3: Testing Agent")
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
        }
        testing_output = run_testing(context)
        state.update(testing_output)
        state["current_phase"] = "testing_complete"
    except Exception as e:
        print(f"  Testing Agent failed: {e}")
        return state

    result = validate_phase("testing", state)
    print_phase_summary("Testing", result)
    if not result.passed:
        print("  Stopping workflow due to validation failure.")
        return state
    completed_phases.append("testing")
    if not request_approval("testing", "documentation"):
        print("  Workflow stopped by user after Testing phase.")
        print_final_summary(completed_phases, state)
        return state

    # -- Phase 4: Documentation -----------------------------------------------
    print_header("Phase 4: Documentation Agent")
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
        }
        docs_output = run_docs(context)
        state.update(docs_output)
        state["current_phase"] = "done"
    except Exception as e:
        print(f"  Documentation Agent failed: {e}")
        return state

    result = validate_phase("docs", state)
    print_phase_summary("Documentation", result)
    completed_phases.append("docs")

    print_final_summary(completed_phases, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the multi-agent OCP builds workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/orchestrate.py --title "Add timeout support" --description "..."
  MANUAL_APPROVAL=true uv run python scripts/orchestrate.py --title "..." --description "..."
        """,
    )
    parser.add_argument("--title", required=True, help="Issue/feature title")
    parser.add_argument("--description", required=True, help="Issue/feature description")
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
    args = parser.parse_args()

    result = orchestrate(
        title=args.title,
        description=args.description,
        issue_type=args.issue_type,
        repo_path=args.repo_path,
    )
    sys.exit(0 if result.get("current_phase") == "done" else 1)


if __name__ == "__main__":
    main()
