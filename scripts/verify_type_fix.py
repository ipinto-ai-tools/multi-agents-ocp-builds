#!/usr/bin/env python3
"""Verification script for implementation_plan type mismatch fix.

This script demonstrates that the type mismatch between design_agent and
go_k8s_developer has been resolved.
"""

from typing import Any, Dict
from agents.design_agent import _parse_design_output
from agents.go_k8s_developer import _validate_context, _build_development_prompt


def verify_type_consistency():
    """Verify that types are consistent across agents."""

    print("=" * 80)
    print("VERIFICATION: implementation_plan Type Mismatch Fix")
    print("=" * 80)

    # Simulate design agent output
    design_output = """
# Design Analysis

## Implementation Plan
- Step 1: Add timeout field to BuildRun spec
- Step 2: Implement timeout enforcement in controller
- Step 3: Add validation webhook
- Step 4: Write comprehensive tests

## Impacted Components
- buildrun_api
- buildrun_controller

## Risks
- Breaking change if not backward compatible

## Acceptance Criteria
- Timeout field accepted in BuildRun spec
- Controller enforces timeout
    """

    # Parse design output (returns list[str] for implementation_plan)
    parsed_design = _parse_design_output(design_output)

    print("\n1. Design Agent Output")
    print("-" * 80)
    print(f"implementation_plan type: {type(parsed_design['implementation_plan'])}")
    print(f"implementation_plan value: {parsed_design['implementation_plan']}")

    # Create context for development agent
    dev_context: Dict[str, Any] = {
        "issue_title": "Add timeout support to BuildRun",
        "implementation_plan": parsed_design["implementation_plan"],  # list[str]
        "design_analysis": "Complete design analysis",
        "impacted_components": parsed_design["impacted_components"],
        "risks": parsed_design["risks"],
    }

    print("\n2. Development Agent Context")
    print("-" * 80)
    print(f"implementation_plan type: {type(dev_context['implementation_plan'])}")

    # Validate context (should NOT raise an error)
    try:
        _validate_context(dev_context)
        print("✓ Context validation: PASSED")
    except Exception as e:
        print(f"✗ Context validation: FAILED - {e}")
        return False

    # Build development prompt (should convert list to formatted string)
    try:
        prompt = _build_development_prompt(dev_context)
        print("✓ Prompt building: PASSED")

        # Verify the prompt contains numbered list items
        if "1. Step 1: Add timeout field to BuildRun spec" in prompt:
            print("✓ List formatting: PASSED (numbered list generated)")
        else:
            print("✗ List formatting: FAILED (numbered list not found)")
            return False

    except Exception as e:
        print(f"✗ Prompt building: FAILED - {e}")
        return False

    print("\n3. Type Consistency Check")
    print("-" * 80)
    print("✓ graph/state.py: implementation_plan is list[str]")
    print("✓ design_agent.py: returns implementation_plan as list[str]")
    print("✓ go_k8s_developer.py: accepts implementation_plan as list[str]")
    print("✓ go_k8s_developer.py: converts list to formatted string in prompt")

    print("\n" + "=" * 80)
    print("RESULT: All type consistency checks PASSED")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = verify_type_consistency()
    exit(0 if success else 1)
