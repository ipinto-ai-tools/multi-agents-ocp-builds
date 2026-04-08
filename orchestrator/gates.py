"""Quality gates for the SDLC workflow.

Gates run between stages to enforce quality standards. Unlike stages,
gates don't produce new artifacts --- they validate existing outputs
and return pass/fail decisions.

Two kinds of gates:

1. **Review gate** --- delegates to the code-review agent.
2. **Command gates** --- run shell commands (build / lint / test) defined
   in ``repos.yaml`` via :class:`config.repo_schema.RepoCommands`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from utils.file_logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Result of running a single command-based quality gate."""

    gate_name: str
    passed: bool
    output: str = ""
    error: str = ""
    command: str = ""


# ---------------------------------------------------------------------------
# Review gate (unchanged)
# ---------------------------------------------------------------------------

def run_review_gate(state: dict[str, Any]) -> dict[str, Any]:
    """Run code review as a quality gate after the Develop stage.

    Wraps the existing code_review_agent logic. This is a gate, not a stage.

    Args:
        state: Workflow state with code_files, design_analysis, etc.

    Returns:
        Dict with review_passed, review_findings, review_summary, review_iteration
    """
    from agents.code_review_agent import run_code_review

    return run_code_review(state)


# ---------------------------------------------------------------------------
# Command-based quality gates
# ---------------------------------------------------------------------------

_COMMAND_TIMEOUT_SECONDS = 300


def run_command_gate(
    command: str,
    gate_name: str,
    cwd: str | None = None,
) -> GateResult:
    """Run a shell command as a quality gate.

    Args:
        command: Shell command to execute (e.g. ``go build ./...``).
        gate_name: Human-readable gate name (e.g. ``"build"``, ``"lint"``).
        cwd: Working directory for the command.

    Returns:
        :class:`GateResult` with pass/fail status and captured output.
    """
    logger.info("Running %s gate: %s", gate_name, command)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_COMMAND_TIMEOUT_SECONDS,
            cwd=cwd,
        )
        passed = result.returncode == 0
        return GateResult(
            gate_name=gate_name,
            passed=passed,
            output=result.stdout,
            error=result.stderr,
            command=command,
        )
    except subprocess.TimeoutExpired:
        return GateResult(
            gate_name=gate_name,
            passed=False,
            error=f"Command timed out after {_COMMAND_TIMEOUT_SECONDS} seconds",
            command=command,
        )
    except Exception as exc:
        return GateResult(
            gate_name=gate_name,
            passed=False,
            error=str(exc),
            command=command,
        )


def run_post_develop_gates(
    repo_path: str | None,
    commands: dict[str, str] | None = None,
) -> list[GateResult]:
    """Run quality gates after the Develop stage.

    Executes ``build`` and ``lint`` commands from ``repos.yaml`` when
    configured.

    Args:
        repo_path: Working directory for the commands.
        commands: Dict with optional ``"build"`` and ``"lint"`` command strings.

    Returns:
        List of :class:`GateResult` instances (may be empty).
    """
    results: list[GateResult] = []
    if not commands:
        return results

    for gate_name in ("build", "lint"):
        cmd = commands.get(gate_name)
        if cmd:
            result = run_command_gate(cmd, gate_name, cwd=repo_path)
            results.append(result)
            if not result.passed:
                logger.warning("%s gate failed: %s", gate_name, result.error)

    return results


def run_post_test_gates(
    repo_path: str | None,
    commands: dict[str, str] | None = None,
) -> list[GateResult]:
    """Run quality gates after the Testing stage.

    Executes the ``test`` command from ``repos.yaml`` when configured.

    Args:
        repo_path: Working directory for the commands.
        commands: Dict with an optional ``"test"`` command string.

    Returns:
        List of :class:`GateResult` instances (may be empty).
    """
    results: list[GateResult] = []
    if not commands:
        return results

    cmd = commands.get("test")
    if cmd:
        result = run_command_gate(cmd, "test", cwd=repo_path)
        results.append(result)
        if not result.passed:
            logger.warning("test gate failed: %s", result.error)

    return results
