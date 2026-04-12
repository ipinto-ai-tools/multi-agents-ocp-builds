"""Rule-based extraction of memory entries from stage outputs.

Purely deterministic -- no Claude API calls.  Each stage has a small
helper that inspects the stage output dict and yields ``MemoryEntry``
objects according to hard-coded rules.
"""

from __future__ import annotations

from typing import Callable

from memory.models import MemoryEntry, MemoryType

_MAX_CONTENT_LEN = 500

# Type alias for per-stage extractor functions.
_Extractor = Callable[[dict, dict], list[MemoryEntry]]


def extract_memories(
    stage: str,
    context: dict,
    stage_output: dict,
) -> list[MemoryEntry]:
    """Extract memory entries from a stage's output.

    Uses rule-based extraction -- no API calls.

    Parameters
    ----------
    stage:
        Pipeline stage name (``design``, ``develop``, ``testing``, ``docs``).
    context:
        Shared pipeline context dict carrying ``session_id``,
        ``issue_title``, ``issue_type``, ``impacted_components``, etc.
    stage_output:
        The dict returned by the stage runner.

    Returns
    -------
    list[MemoryEntry]
        Zero or more memory entries extracted from *stage_output*.
    """
    extractors: dict[str, _Extractor] = {
        "design": _extract_design,
        "develop": _extract_develop,
        "testing": _extract_testing,
        "docs": _extract_docs,
    }
    extractor = extractors.get(stage)
    if extractor is None:
        return []
    return extractor(context, stage_output)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _common_fields(context: dict, stage: str) -> dict:
    """Return the fields shared by every ``MemoryEntry`` we create."""
    return {
        "session_id": context.get("session_id", ""),
        "stage": stage,
        "issue_title": context.get("issue_title", "") or None,
        "issue_type": context.get("issue_type", "") or None,
        "tags": list(context.get("impacted_components", [])),
    }


def _make_entry(
    context: dict,
    stage: str,
    memory_type: MemoryType,
    title: str,
    content: str,
) -> MemoryEntry | None:
    """Build a ``MemoryEntry`` if *content* is non-empty."""
    content = content.strip()
    if not content:
        return None
    return MemoryEntry(
        memory_type=memory_type,
        title=title,
        content=content,
        **_common_fields(context, stage),
    )


# ---------------------------------------------------------------------------
# Per-stage extractors
# ---------------------------------------------------------------------------

def _extract_design(context: dict, output: dict) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    issue_title = context.get("issue_title", "")

    # Reusable context from design_analysis (truncated)
    design_analysis: str = output.get("design_analysis", "")
    entry = _make_entry(
        context,
        "design",
        MemoryType.reusable_context,
        f"Design: {issue_title}",
        design_analysis[:_MAX_CONTENT_LEN],
    )
    if entry:
        entries.append(entry)

    # Heuristic for each risk
    risks: list[str] = output.get("risks", [])
    for risk in risks:
        entry = _make_entry(
            context,
            "design",
            MemoryType.heuristic,
            f"Risk: {risk[:80]}",
            risk,
        )
        if entry:
            entries.append(entry)

    # Best practice summarising implementation plan
    plan: list[str] = output.get("implementation_plan", [])
    if plan:
        plan_summary = "\n".join(f"- {step}" for step in plan)
        entry = _make_entry(
            context,
            "design",
            MemoryType.best_practice,
            f"Implementation approach for {issue_title}",
            plan_summary,
        )
        if entry:
            entries.append(entry)

    return entries


def _extract_develop(context: dict, output: dict) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    issue_title = context.get("issue_title", "")

    # Execution note listing generated files
    code_files: list[dict] = output.get("code_files", [])
    test_files: list[dict] = output.get("test_files", [])
    all_paths = [f.get("path", "") for f in code_files + test_files if f.get("path")]
    if all_paths:
        content = "\n".join(all_paths)
        entry = _make_entry(
            context,
            "develop",
            MemoryType.execution_note,
            f"Dev output: {issue_title}",
            content,
        )
        if entry:
            entries.append(entry)

    # Anti-patterns from review findings when review failed
    review_passed: bool = output.get("review_passed", True)
    review_findings: list[str] = output.get("review_findings", [])
    if not review_passed and review_findings:
        for finding in review_findings:
            entry = _make_entry(
                context,
                "develop",
                MemoryType.anti_pattern,
                f"Review finding: {finding[:80]}",
                finding,
            )
            if entry:
                entries.append(entry)

    # Security best practice
    security_notes: str = output.get("security_notes", "")
    if security_notes.strip():
        entry = _make_entry(
            context,
            "develop",
            MemoryType.best_practice,
            f"Security: {issue_title}",
            security_notes,
        )
        if entry:
            entries.append(entry)

    return entries


def _extract_testing(context: dict, output: dict) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    issue_title = context.get("issue_title", "")

    # Reusable context from test plan (truncated)
    test_plan: str = output.get("test_plan", "")
    entry = _make_entry(
        context,
        "testing",
        MemoryType.reusable_context,
        f"Test plan: {issue_title}",
        test_plan[:_MAX_CONTENT_LEN],
    )
    if entry:
        entries.append(entry)

    # Heuristic from coverage analysis
    coverage: str = output.get("coverage_analysis", "")
    if coverage.strip():
        entry = _make_entry(
            context,
            "testing",
            MemoryType.heuristic,
            f"Coverage: {issue_title}",
            coverage,
        )
        if entry:
            entries.append(entry)

    return entries


def _extract_docs(context: dict, output: dict) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    issue_title = context.get("issue_title", "")

    # Reusable context from PR summary
    pr_summary: str = output.get("pr_summary", "")
    entry = _make_entry(
        context,
        "docs",
        MemoryType.reusable_context,
        f"PR summary: {issue_title}",
        pr_summary,
    )
    if entry:
        entries.append(entry)

    return entries
