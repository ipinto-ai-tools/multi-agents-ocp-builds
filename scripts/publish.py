#!/usr/bin/env python3
"""Publish pipeline artifacts to external systems.

Usage:
    uv run python scripts/publish.py --output-dir PATH [--push-code] [--push-jira] [--dry-run]
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


# -- helpers ------------------------------------------------------------------


def _safe_str(value: str) -> str:
    """Strip control characters and newlines from a string for safe use in git args."""
    import unicodedata
    return "".join(c for c in value if not unicodedata.category(c).startswith("C"))


def _slug(text: str, max_len: int = 40) -> str:
    """Convert text to a URL-safe slug.

    Lowercases the text, replaces whitespace with hyphens, strips any character
    that is not alphanumeric or a hyphen, collapses consecutive hyphens, and
    trims to *max_len* characters.
    """
    text = text.lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9-]", "", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")
    return text[:max_len]


def _run(cmd: list[str], cwd: str | None = None, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess command, capturing output, and return the result."""
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True, env=env)


def _collect_files(directory: pathlib.Path) -> dict[str, str]:
    """Return a mapping of relative-path-string -> file-content for all files under directory."""
    files: dict[str, str] = {}
    if not directory.exists():
        return files
    for path in directory.rglob("*"):
        if path.is_file():
            rel = path.relative_to(directory)
            try:
                files[str(rel)] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                print(f"  SKIPPED (binary file): {rel}")
            except OSError as exc:
                print(f"  WARNING: could not read {path}: {exc}")
    return files


def _load_state(output_dir: pathlib.Path) -> dict:
    """Load state.json from output_dir.

    Raises SystemExit if the file is missing or not valid JSON.
    """
    state_path = output_dir / "state.json"
    if not state_path.exists():
        print(f"ERROR: state.json not found in {output_dir}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: Failed to parse state.json: {exc}", file=sys.stderr)
        sys.exit(1)


def _read_file_optional(path: pathlib.Path) -> str | None:
    """Return file contents or None (with a warning) if the file does not exist."""
    if not path.exists():
        print(f"  WARNING: {path} not found — skipping.")
        return None
    return path.read_text(encoding="utf-8")


# -- sub-commands -------------------------------------------------------------

def _push_code(output_dir: pathlib.Path, config: dict, dry_run: bool) -> None:
    """Push generated Go code and tests to a target GitHub repository as a PR.

    Steps:
    1. Read state.json — extract jira_ticket_id and issue_title.
    2. Read all files under output_dir/code/ and output_dir/tests/.
    3. Shallow-clone TARGET_GITHUB_REPO into a temp dir.
    4. Create branch feat/<jira_ticket_id_lower>-<slug-of-issue-title> from TARGET_GITHUB_BASE_BRANCH.
    5. Copy files preserving relative paths (code/ and tests/ subtrees map to the repo root).
    6. Commit and push branch.
    7. Create PR via gh pr create using docs/pr_description.md as body.
    8. Print the PR URL.
    9. Clean up temp dir in a finally block.

    Args:
        output_dir: Directory produced by orchestrate.py (contains state.json).
        config: Dict with TARGET_GITHUB_REPO, TARGET_GITHUB_BASE_BRANCH, GITHUB_TOKEN.
        dry_run: When True, print what would be done without executing any git/gh commands.
    """
    target_repo = config.get("TARGET_GITHUB_REPO", "").strip()
    if not target_repo:
        print(
            "ERROR: TARGET_GITHUB_REPO is not set. "
            "Add it to .env or set it in the environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    github_token = config.get("GITHUB_TOKEN", "").strip()
    if not github_token:
        print(
            "ERROR: GITHUB_TOKEN is not set. "
            "Add it to .env or set it in the environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    base_branch = config.get("TARGET_GITHUB_BASE_BRANCH", "main").strip() or "main"

    if not re.fullmatch(r'[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+', target_repo):
        print(f"  ERROR: TARGET_GITHUB_REPO has invalid format: {target_repo!r}")
        print("  Expected format: org/repo (e.g. openshift-builds/builds)")
        sys.exit(1)

    if not re.fullmatch(r'[a-zA-Z0-9/_.-]+', base_branch):
        print(f"  ERROR: TARGET_GITHUB_BASE_BRANCH has invalid format: {base_branch!r}")
        sys.exit(1)

    # -- read state -----------------------------------------------------------
    state = _load_state(output_dir)
    jira_ticket_id: str = _safe_str(state.get("jira_ticket_id", "unknown"))
    issue_title: str = _safe_str(
        state.get("issue_title")
        or state.get("title")
        or "untitled"
    )

    branch_name = f"feat/{jira_ticket_id.lower()}-{_slug(issue_title)}"
    commit_msg = f"feat({jira_ticket_id}): {issue_title}"

    # -- collect files --------------------------------------------------------
    code_files = _collect_files(output_dir / "code")
    test_files = _collect_files(output_dir / "tests")

    # -- PR body --------------------------------------------------------------
    pr_body_path = output_dir / "docs" / "pr_description.md"
    if pr_body_path.exists():
        pr_body = pr_body_path.read_text(encoding="utf-8")
    else:
        pr_body = (
            f"## {issue_title}\n\n"
            "Auto-generated by multi-agent pipeline.\n\n"
            f"Jira ticket: {jira_ticket_id}"
        )

    print(f"  Target repo:   {target_repo}")
    print(f"  Base branch:   {base_branch}")
    print(f"  New branch:    {branch_name}")
    print(f"  Commit msg:    {commit_msg}")
    print(f"  Code files:    {len(code_files)}")
    print(f"  Test files:    {len(test_files)}")

    if dry_run:
        print("\n  [dry-run] Would clone, copy files, commit, push, and open a PR.")
        print(f"  [dry-run] Branch:  {branch_name}")
        print(f"  [dry-run] Commit:  {commit_msg}")
        print(f"  [dry-run] Repo:    https://github.com/{target_repo}")
        return

    # -- clone + push ---------------------------------------------------------
    os.makedirs("/tmp/claude", exist_ok=True)
    tmp_dir = pathlib.Path(
        tempfile.mkdtemp(dir="/tmp/claude", prefix=f"publish-{uuid.uuid4().hex[:8]}-")
    )
    clone_dir = tmp_dir / "repo"

    # Build credential helper script so the token never appears in the clone URL.
    # The token is passed via GIT_TOKEN env var to avoid single-quote embedding issues.
    cred_script = tmp_dir / "git-askpass.sh"
    cred_script.write_text("#!/bin/sh\nprintf '%s' \"$GIT_TOKEN\"\n")
    cred_script.chmod(0o700)

    env = {
        **os.environ,
        "GIT_ASKPASS": str(cred_script),
        "GIT_USERNAME": "x-token",
        "GIT_TOKEN": github_token,
    }

    try:
        clone_url = f"https://github.com/{target_repo}.git"
        print(f"\n  Cloning {target_repo} (depth=1) …")
        _run(["git", "clone", "--depth", "1", "--branch", base_branch, clone_url, str(clone_dir)], env=env)

        # configure git identity inside the clone (required for commits)
        _run(["git", "config", "user.email", "publish-bot@ci"], cwd=str(clone_dir))
        _run(["git", "config", "user.name", "Publish Bot"], cwd=str(clone_dir))

        # create feature branch
        _run(["git", "checkout", "-b", branch_name], cwd=str(clone_dir))

        # copy code files preserving relative paths to repo root
        for rel_path, content in code_files.items():
            dest = (clone_dir / rel_path).resolve()
            if not str(dest).startswith(str(clone_dir.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {rel_path}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            print(f"  Copied (code):  {rel_path}")

        # copy test files preserving relative paths to repo root
        for rel_path, content in test_files.items():
            dest = (clone_dir / rel_path).resolve()
            if not str(dest).startswith(str(clone_dir.resolve()) + os.sep):
                print(f"  SKIPPED (unsafe path): {rel_path}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            print(f"  Copied (tests): {rel_path}")

        if not code_files and not test_files:
            print("  WARNING: No code or test files found — committing an empty branch.")

        # stage and commit
        _run(["git", "add", "-A"], cwd=str(clone_dir))
        _run(["git", "commit", "--allow-empty", "-m", commit_msg], cwd=str(clone_dir))

        # push branch
        print(f"  Pushing branch {branch_name} …")
        try:
            _run(["git", "push", "-u", "origin", branch_name], cwd=str(clone_dir), env=env)
        except subprocess.CalledProcessError as e:
            print(f"  ERROR: git push failed — branch '{branch_name}' may already exist on remote.")
            print(f"  Details: {e.stderr}")
            raise

        # open PR
        print("  Creating PR …")
        body_file = tmp_dir / "pr_body.md"
        body_file.write_text(pr_body, encoding="utf-8")
        pr_result = _run(
            [
                "gh", "pr", "create",
                "--repo", target_repo,
                "--head", branch_name,
                "--base", base_branch,
                "--title", commit_msg,
                "--body-file", str(body_file),
            ],
            cwd=str(clone_dir),
        )
        pr_url = pr_result.stdout.strip()
        print(f"\n  PR created: {pr_url}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _push_jira(output_dir: pathlib.Path, config: dict, dry_run: bool) -> None:
    """Upload design and docs artifacts back to the originating Jira ticket.

    Actions performed:
    1. Attach design/design_analysis.md as a file attachment.
    2. Post docs/pr_summary.md as a comment.
    3. Post docs/release_notes.md as a comment (if non-empty).

    Args:
        output_dir: Directory produced by orchestrate.py (contains state.json).
        config: Dict with Jira credentials (base_url, email, api_token).
        dry_run: When True, print what would be done without making API calls.
    """
    # -- credentials ----------------------------------------------------------
    base_url = config.get("base_url", "")
    email = config.get("email", "")
    api_token = config.get("api_token", "")

    missing = []
    if not base_url:
        missing.append("JIRA_BASE_URL")
    if not api_token:
        missing.append("JIRA_API_TOKEN")

    if missing:
        print(
            f"ERROR: Missing required environment variable(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # -- ticket ID ------------------------------------------------------------
    state = _load_state(output_dir)
    ticket_id = state.get("jira_ticket_id", "")
    if not ticket_id:
        print(
            "ERROR: jira_ticket_id not found in state.json. "
            "Run the pipeline with --jira-ticket to populate this field.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"  Ticket: {ticket_id}")

    # -- build session --------------------------------------------------------
    session = None
    if not dry_run:
        import base64
        import requests

        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        })

    # -- 1. Attach design_analysis.md -----------------------------------------
    design_path = output_dir / "design" / "design_analysis.md"
    design_content = _read_file_optional(design_path)
    if design_content is not None:
        if dry_run:
            print(f"  [dry-run] Would attach {design_path} to {ticket_id}")
        else:
            attach_url = f"{base_url.rstrip('/')}/rest/api/2/issue/{ticket_id}/attachments"
            try:
                resp = session.post(
                    attach_url,
                    headers={"X-Atlassian-Token": "no-check"},
                    files={"file": ("design_analysis.md", design_content.encode("utf-8"), "text/markdown")},
                )
                if resp.ok:
                    print(f"  Attached design_analysis.md to {ticket_id}")
                else:
                    print(
                        f"  WARNING: Failed to attach design_analysis.md "
                        f"(HTTP {resp.status_code}): {resp.text[:200]}"
                    )
            except Exception as exc:
                print(f"  WARNING: Could not attach design_analysis.md: {exc}")

    # -- 2. Post pr_summary.md as comment -------------------------------------
    pr_summary_path = output_dir / "docs" / "pr_summary.md"
    pr_summary = _read_file_optional(pr_summary_path)
    if pr_summary is not None:
        comment_body = f"## PR Summary\n\n{pr_summary}"
        if dry_run:
            print(f"  [dry-run] Would post PR summary comment to {ticket_id}")
        else:
            _post_comment(session, base_url, ticket_id, comment_body, label="PR summary")

    # -- 3. Post release_notes.md as comment (if non-empty) -------------------
    release_notes_path = output_dir / "docs" / "release_notes.md"
    release_notes = _read_file_optional(release_notes_path)
    if release_notes is not None and release_notes.strip():
        comment_body = f"## Release Notes\n\n{release_notes}"
        if dry_run:
            print(f"  [dry-run] Would post release notes comment to {ticket_id}")
        else:
            _post_comment(session, base_url, ticket_id, comment_body, label="release notes")
    elif release_notes is not None and not release_notes.strip():
        print("  release_notes.md is empty — skipping release notes comment.")


def _post_comment(session, base_url: str, ticket_id: str, body: str, label: str = "comment") -> None:
    """POST a plain-text comment to a Jira ticket (REST API v2).

    Prints a confirmation or warning; never raises.
    """
    import requests

    url = f"{base_url.rstrip('/')}/rest/api/2/issue/{ticket_id}/comment"
    try:
        resp = session.post(url, json={"body": body})
        if resp.ok:
            print(f"  Posted {label} comment to {ticket_id}")
        else:
            print(
                f"  WARNING: Failed to post {label} comment "
                f"(HTTP {resp.status_code}): {resp.text[:200]}"
            )
    except Exception as exc:
        print(f"  WARNING: Could not post {label} comment: {exc}")


# -- main ---------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish pipeline artifacts to external systems.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/publish.py --output-dir ./output/BUILD-1707 --push-jira
  uv run python scripts/publish.py --output-dir ./output/BUILD-1707 --push-jira --dry-run
  uv run python scripts/publish.py --output-dir ./output/BUILD-1707 --push-code
        """,
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        metavar="PATH",
        help="Directory containing pipeline artifacts (state.json, design/, docs/).",
    )
    parser.add_argument(
        "--push-code",
        action="store_true",
        help="Push generated code and test files to the target GitHub repository as a PR.",
    )
    parser.add_argument(
        "--push-jira",
        action="store_true",
        help="Attach design analysis and post docs summaries back to the originating Jira ticket.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making any API calls.",
    )
    args = parser.parse_args()

    if not args.push_code and not args.push_jira:
        parser.error("at least one of --push-code or --push-jira is required")

    output_dir = pathlib.Path(args.output_dir).resolve()
    if not output_dir.exists():
        print(f"ERROR: Output directory does not exist: {output_dir}", file=sys.stderr)
        sys.exit(1)

    jira_config = {
        "base_url": os.getenv("JIRA_BASE_URL", ""),
        "email": os.getenv("JIRA_USER_EMAIL", ""),
        "api_token": os.getenv("JIRA_API_TOKEN", ""),
    }

    github_config = {
        "TARGET_GITHUB_REPO": os.getenv("TARGET_GITHUB_REPO", ""),
        "TARGET_GITHUB_BASE_BRANCH": os.getenv("TARGET_GITHUB_BASE_BRANCH", "main"),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
    }

    if args.push_code:
        print("\n-- push-code -------------------------------------------------------")
        _push_code(output_dir, github_config, args.dry_run)

    if args.push_jira:
        print("\n-- push-jira -------------------------------------------------------")
        _push_jira(output_dir, jira_config, args.dry_run)


if __name__ == "__main__":
    main()
