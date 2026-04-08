"""Quality gates for the SDLC workflow.

Gates run between stages to enforce quality standards. Unlike stages,
gates don't produce new artifacts --- they validate existing outputs
and return pass/fail decisions.
"""

from __future__ import annotations

from typing import Any

from utils.file_logger import get_logger

logger = get_logger(__name__)


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
