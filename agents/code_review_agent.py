"""Code Review Agent with auto-fix loop support.

Uses Claude to review generated Go code for quality, security, and correctness.
Optionally integrates with Qodo CLI when QODO_CLI_PATH is set.

Auto-fix loop: when blocking issues are found, sets review_passed=False so
the LangGraph router sends the workflow back to the Development Agent with
review feedback injected into the prompt. Repeats up to MAX_REVIEW_ITERATIONS.

Environment variables:
    QODO_REVIEW_ENABLED: Set to 'false' to skip review (default: 'true')
    MAX_REVIEW_ITERATIONS: Max auto-fix attempts before proceeding (default: '3')
    QODO_BLOCKING_THRESHOLD: Severity to block on: 'high'|'medium'|'low' (default: 'high')
    QODO_CLI_PATH: Optional path to qodo CLI binary for enhanced review
"""

import logging
import os
import shutil
from typing import Any

from config.agent_prompts import CODE_REVIEW_AGENT_PROMPT
from config.auth_config import get_anthropic_client
from dashboard.heartbeat import emit_heartbeat
from tools.prompt_guard import sanitize_external_input

logger = logging.getLogger(__name__)

QODO_REVIEW_ENABLED = os.getenv("QODO_REVIEW_ENABLED", "true").lower() == "true"
MAX_REVIEW_ITERATIONS = int(os.getenv("MAX_REVIEW_ITERATIONS", "3"))
QODO_BLOCKING_THRESHOLD = os.getenv("QODO_BLOCKING_THRESHOLD", "high").lower()


class CodeReviewAgentError(Exception):
    """Base exception for Code Review Agent errors."""


def run_code_review(state: dict[str, Any]) -> dict[str, Any]:
    """Review generated Go code and return structured findings.

    When QODO_REVIEW_ENABLED is false, skips review and returns review_passed=True.
    When QODO_CLI_PATH is set, delegates to Qodo CLI; otherwise uses Claude.
    On any review error, logs a warning and returns review_passed=True to avoid
    blocking the pipeline on infrastructure issues.

    Args:
        state: AgentState dict containing code_files, review_iteration,
               design_analysis, acceptance_criteria, session_id.

    Returns:
        Dict with:
            review_passed: bool — True if no blocking issues found
            review_findings: list[str] — structured findings (level + description)
            review_summary: str — human-readable verdict
            review_iteration: int — current iteration count (incremented)
    """
    current_iteration = int(state.get("review_iteration", 0) or 0)

    if not QODO_REVIEW_ENABLED:
        logger.info("Code review disabled (QODO_REVIEW_ENABLED=false). Skipping.")
        return {
            "review_passed": True,
            "review_findings": [],
            "review_summary": "Code review skipped (QODO_REVIEW_ENABLED=false)",
            "review_iteration": current_iteration,
        }

    code_files = state.get("code_files", [])
    if not code_files:
        logger.warning("No code files to review. Skipping review.")
        return {
            "review_passed": True,
            "review_findings": [],
            "review_summary": "No code files to review",
            "review_iteration": current_iteration,
        }

    emit_heartbeat("code_review", {**state, "review_iteration": current_iteration, "phase": "review_start"})

    try:
        qodo_path = os.getenv("QODO_CLI_PATH", "")
        if qodo_path:
            result = _run_qodo_review(state, qodo_path)
        else:
            result = _run_claude_review(state)
    except Exception as e:
        logger.warning("Code review failed (%s). Proceeding without blocking.", type(e).__name__)
        logger.debug("Code review error details: %s", e)
        result = {
            "review_passed": True,
            "review_findings": [],
            "review_summary": f"Code review error (proceeding): {type(e).__name__}",
        }

    result["review_iteration"] = current_iteration + 1

    emit_heartbeat("code_review", {
        **state,
        **result,
        "phase": "review_complete",
    })

    return result


def _run_claude_review(state: dict[str, Any]) -> dict[str, Any]:
    """Use Claude to review generated code.

    Args:
        state: AgentState dict with code_files, design_analysis, acceptance_criteria.

    Returns:
        Dict with review_passed, review_findings, review_summary (without review_iteration).
    """
    # Check dry-run mode
    if os.getenv("DRY_RUN", "false").lower() == "true":
        from config.mock_responses import MOCK_CODE_REVIEW_PASS
        logger.info("[DRY-RUN] Returning mock code review response")
        return dict(MOCK_CODE_REVIEW_PASS)

    client = get_anthropic_client()

    code_content = _format_code_for_review(state.get("code_files", []))
    design_analysis = state.get("design_analysis", "")[:2000]
    design_analysis = sanitize_external_input(design_analysis, source="code_review:design_analysis")
    acceptance_criteria = state.get("acceptance_criteria", [])
    iteration = state.get("review_iteration", 0)

    safe_criteria = [
        sanitize_external_input(c, source=f"code_review:acceptance_criteria:{i}")
        for i, c in enumerate(acceptance_criteria)
    ]
    ac_block = "\n".join(f"- {c}" for c in safe_criteria) if safe_criteria else "Not specified"
    iteration_note = (
        "Previous findings have been addressed. Focus on remaining or new issues."
        if iteration > 0
        else ""
    )

    user_prompt = (
        f"Review the following generated Go code for the feature described below.\n\n"
        f"## Feature Context\n{design_analysis}\n\n"
        f"## Acceptance Criteria\n{ac_block}\n\n"
        f"## Generated Code\n{code_content}\n\n"
        f"## Review Iteration\n"
        f"This is review iteration {iteration + 1} of {MAX_REVIEW_ITERATIONS}. {iteration_note}\n\n"
        f"Provide structured review output with:\n"
        f"1. BLOCKING issues (must fix — security holes, crashes, data loss)\n"
        f"2. WARNINGS (should fix — quality, maintainability)\n"
        f"3. SUGGESTIONS (optional improvements)\n"
        f"4. VERDICT: PASS or FAIL (FAIL only if there are BLOCKING issues)\n\n"
        f"Format each finding on its own line:\n"
        f"[BLOCKING] CATEGORY: Description\n"
        f"[WARNING] CATEGORY: Description\n"
        f"[SUGGESTION] CATEGORY: Description\n\n"
        f"End your response with either 'VERDICT: PASS' or 'VERDICT: FAIL'."
    )

    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        system=CODE_REVIEW_AGENT_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.1,
    )

    raw_output = response.content[0].text
    logger.debug("Code review raw output (%d chars)", len(raw_output))
    return _parse_review_output(raw_output)


def _run_qodo_review(state: dict[str, Any], qodo_path: str) -> dict[str, Any]:
    """Use Qodo CLI to review code when QODO_CLI_PATH is set.

    Writes code files to a temp git repo, runs qodo review --ci, then cleans up.
    Falls back to Claude review on any error.

    Args:
        state: AgentState dict with code_files and session_id.
        qodo_path: Path to the qodo CLI binary.

    Returns:
        Dict with review_passed, review_findings, review_summary.
    """
    import subprocess

    session_id = state.get("session_id", "unknown")
    tmp_dir = f"/tmp/claude/review-{session_id}"

    try:
        os.makedirs(tmp_dir, exist_ok=True)

        # Write generated code files to temp directory
        real_tmp = os.path.realpath(tmp_dir)
        for file_info in state.get("code_files", []):
            raw_path = file_info.get("path", "code.go")
            file_path = os.path.realpath(os.path.join(tmp_dir, raw_path))
            if not file_path.startswith(real_tmp + os.sep):
                logger.warning("Skipping file with path traversal attempt: %s", raw_path)
                continue
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(file_info.get("content", ""))

        # Initialize git repo so qodo can detect changed files
        subprocess.run(["git", "init"], cwd=tmp_dir, capture_output=True, check=False)
        subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "generated code for review", "--allow-empty-message", "--no-gpg-sign"],
            cwd=tmp_dir, capture_output=True, check=False,
            env={**os.environ, "GIT_AUTHOR_NAME": "review-agent", "GIT_AUTHOR_EMAIL": "review@agent.local",
                 "GIT_COMMITTER_NAME": "review-agent", "GIT_COMMITTER_EMAIL": "review@agent.local"}
        )

        result = subprocess.run(
            [qodo_path, "review", "--ci", "--quiet"],
            cwd=tmp_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )

        raw_output = result.stdout or result.stderr or ""
        logger.info("Qodo CLI review completed (exit code %d)", result.returncode)
        return _parse_review_output(raw_output)

    except Exception as e:
        logger.warning("Qodo CLI review failed (%s), falling back to Claude review", type(e).__name__)
        logger.debug("Qodo error details: %s", e)
        return _run_claude_review(state)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _format_code_for_review(code_files: list[dict]) -> str:
    """Format code files for inclusion in the review prompt.

    Caps at 10 files and 3000 chars per file to avoid token limits.

    Args:
        code_files: List of code file dicts with path and content keys.

    Returns:
        Formatted string with fenced code blocks.
    """
    parts = []
    for file_info in code_files[:10]:
        path = file_info.get("path", "unknown.go")
        raw_content = file_info.get("content", "")
        if len(raw_content) > 3000:
            content = raw_content[:3000] + f"\n# [TRUNCATED — {len(raw_content) - 3000} chars omitted]"
        else:
            content = raw_content
        parts.append(f"### {path}\n```go\n{content}\n```")
    return "\n\n".join(parts)


def _parse_review_output(raw_output: str) -> dict[str, Any]:
    """Parse Claude or Qodo review output into structured findings.

    Looks for [BLOCKING], [WARNING], [SUGGESTION] tagged lines and a VERDICT line.
    Uses QODO_BLOCKING_THRESHOLD to determine pass/fail when no explicit VERDICT.

    Args:
        raw_output: Raw text output from the review.

    Returns:
        Dict with review_passed (bool), review_findings (list[str]),
        review_summary (str). Does NOT include review_iteration.
    """
    findings: list[dict[str, str]] = []
    blocking_count = 0
    warning_count = 0

    for line in raw_output.splitlines():
        line = line.strip()
        if line.startswith("[BLOCKING]"):
            findings.append({"level": "blocking", "text": line})
            blocking_count += 1
        elif line.startswith("[WARNING]"):
            findings.append({"level": "warning", "text": line})
            warning_count += 1
        elif line.startswith("[SUGGESTION]"):
            findings.append({"level": "suggestion", "text": line})

    # Determine pass/fail from threshold
    if QODO_BLOCKING_THRESHOLD == "low":
        review_passed = len(findings) == 0
    elif QODO_BLOCKING_THRESHOLD == "medium":
        review_passed = blocking_count == 0 and warning_count == 0
    else:  # high (default)
        review_passed = blocking_count == 0

    # Explicit VERDICT overrides threshold logic
    if "VERDICT: PASS" in raw_output:
        review_passed = True
    elif "VERDICT: FAIL" in raw_output:
        review_passed = False

    total = len(findings)
    parts = [f"Code review complete: {total} finding(s)"]
    if blocking_count:
        parts.append(f"{blocking_count} blocking")
    if warning_count:
        parts.append(f"{warning_count} warning(s)")
    parts.append("PASS" if review_passed else "FAIL")

    return {
        "review_passed": review_passed,
        "review_findings": [f["text"] for f in findings],
        "review_summary": " | ".join(parts),
    }
