#!/usr/bin/env python3
"""Agent SDK Spike — Proof of Concept (Task #104)

Demonstrates how to replace the current AnthropicVertex client.messages.create()
pattern with the Claude Code Agent SDK's query() async iterator.

This script is a SPIKE — it validates the migration pattern without modifying
the actual design agent. See docs/spike-104-findings.md for full research.

Prerequisites:
    pip install claude-code-agent-sdk pydantic

Usage:
    # Dry-run mode (no API calls, validates structure only)
    python scripts/spike_agent_sdk.py --dry-run

    # Live mode (requires CLAUDE_CODE_USE_VERTEX=1 and ADC)
    CLAUDE_CODE_USE_VERTEX=1 python scripts/spike_agent_sdk.py

Environment:
    CLAUDE_CODE_USE_VERTEX=1    Enable Vertex AI authentication
    ANTHROPIC_VERTEX_PROJECT_ID  GCP project ID (inherited from existing config)
    CLOUD_ML_REGION              GCP region (default: us-east5)
"""

import argparse
import asyncio
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field


# --- Structured Output Model ---
# This mirrors models/stage_outputs.py DesignOutput from Task #106
class DesignOutput(BaseModel):
    """Structured output contract for the Design stage."""

    design_analysis: str = Field(
        ..., min_length=50, description="Complete design document in Markdown"
    )
    impacted_components: list[str] = Field(
        default_factory=list, description="List of affected components"
    )
    risks: list[str] = Field(
        default_factory=list, description="Identified risks"
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="Testable acceptance criteria"
    )
    implementation_plan: list[str] = Field(
        ..., min_length=1, description="Step-by-step plan"
    )


# --- Mock for dry-run mode ---
MOCK_DESIGN_OUTPUT = DesignOutput(
    design_analysis=(
        "# Design Analysis: Add timeout support to BuildRun\n\n"
        "## Problem Statement\n"
        "BuildRuns can hang indefinitely when builds encounter issues...\n\n"
        "## Proposed Solution\n"
        "Add a configurable timeout field to the BuildRun spec..."
    ),
    impacted_components=["BuildRun", "BuildRunReconciler", "BuildStrategy"],
    risks=[
        "Timeout value too low may kill legitimate long-running builds",
        "Race condition between timeout handler and build completion",
    ],
    acceptance_criteria=[
        "BuildRun spec accepts optional timeout field",
        "BuildRun terminates after timeout with clear error status",
        "Default timeout is configurable via BuildStrategy",
    ],
    implementation_plan=[
        "Add timeout field to BuildRun CRD spec",
        "Implement timeout watcher in BuildRunReconciler",
        "Add default timeout to BuildStrategy",
        "Write unit tests for timeout logic",
        "Write e2e test for timeout scenario",
    ],
)


async def run_design_with_sdk(
    title: str,
    description: str,
    system_prompt: str,
    dry_run: bool = False,
) -> DesignOutput:
    """Run design analysis using the Claude Code Agent SDK.

    This demonstrates the target migration pattern for agents/design_agent.py.

    Args:
        title: Issue title
        description: Issue description
        system_prompt: System prompt for the design agent
        dry_run: If True, return mock data without API calls

    Returns:
        DesignOutput with structured design analysis
    """
    if dry_run:
        print("[DRY-RUN] Returning mock DesignOutput (no API call)")
        return MOCK_DESIGN_OUTPUT

    # --- Live SDK call ---
    try:
        from claude_agent_sdk import query
    except ImportError:
        print("ERROR: claude_agent_sdk not installed.")
        print("Install with: pip install claude-code-agent-sdk")
        print("Or run with --dry-run to validate structure without API calls.")
        sys.exit(1)

    user_prompt = (
        f"# Design Analysis Request\n\n"
        f"## Issue Title\n{title}\n\n"
        f"## Issue Description\n{description}\n\n"
        f"## Request\n"
        f"Analyze this issue and produce a comprehensive design document.\n"
    )

    result: Optional[DesignOutput] = None
    async for event in query(
        prompt=user_prompt,
        system=system_prompt,
        output_format=DesignOutput,
        max_turns=1,
    ):
        if hasattr(event, "result"):
            result = event.result

    if result is None:
        raise RuntimeError("Agent SDK query() returned no result")

    return result


def run_design_sync(
    title: str,
    description: str,
    system_prompt: str = "You are a software design analyst.",
    dry_run: bool = False,
) -> dict:
    """Synchronous wrapper — drop-in replacement for current run_design().

    This is how the migrated design agent would be called from the existing
    LangGraph orchestrator, which expects a sync function returning a dict.
    """
    output = asyncio.run(
        run_design_with_sdk(title, description, system_prompt, dry_run)
    )

    # Convert Pydantic model to dict (same format as current run_design return)
    return output.model_dump()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent SDK Spike — PoC for Design stage migration"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock data instead of calling the API",
    )
    parser.add_argument(
        "--title",
        default="Add timeout support to BuildRun",
        help="Issue title (default: timeout feature)",
    )
    parser.add_argument(
        "--description",
        default="BuildRuns should support automatic timeout to prevent hanging builds. "
        "Users need to specify a timeout value in the BuildRun spec.",
        help="Issue description",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Agent SDK Spike — Design Stage PoC (Task #104)")
    print("=" * 60)
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"Title: {args.title}")
    print()

    result = run_design_sync(
        title=args.title,
        description=args.description,
        dry_run=args.dry_run,
    )

    print("--- Result ---")
    print(json.dumps(result, indent=2, default=str))
    print()
    print(f"Components: {len(result['impacted_components'])}")
    print(f"Risks: {len(result['risks'])}")
    print(f"Criteria: {len(result['acceptance_criteria'])}")
    print(f"Plan steps: {len(result['implementation_plan'])}")
    print()

    # Validate round-trip: dict -> Pydantic -> dict
    validated = DesignOutput(**result)
    assert validated.model_dump() == result, "Round-trip validation failed!"
    print("Round-trip validation: PASSED")
    print()
    print("Spike complete. See docs/spike-104-findings.md for full analysis.")


if __name__ == "__main__":
    main()
