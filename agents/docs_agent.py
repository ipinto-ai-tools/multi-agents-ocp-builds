"""Documentation Agent for the OpenShift Build API multi-agent system.

This agent generates documentation artifacts including PR summaries, release notes,
documentation changes, and upgrade notes based on design, development, and test outputs.
"""

import json
import os
from typing import Any, Dict, Optional

from anthropic import Anthropic, APIError
from config.agent_prompts import DOCS_AGENT_PROMPT


def run_docs(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate documentation based on design, development, and test outputs.

    This function uses Claude API to analyze the complete context from previous
    agent phases (design analysis, code changes, test results) and generates
    comprehensive documentation artifacts.

    Args:
        context: Dictionary containing outputs from previous agents with keys:
            - design_analysis: str - Design document from design agent
            - implementation_plan: str - Implementation plan
            - code_changes: dict - File paths to changes
            - files_modified: list - List of modified files
            - test_results: dict - Test execution results
            - test_summary: str - Summary of test results
            - issue_title: str - Original issue title
            - issue_description: str - Original issue description
            - issue_type: str - Type of issue (bug, feature, etc.)

    Returns:
        Dictionary with documentation outputs:
            - pr_summary: str - Pull request description
            - release_notes: str - User-facing release notes
            - docs_changes: dict - Documentation file changes (path: content)
            - upgrade_notes: str - Version upgrade considerations
            - known_limitations: str - Limitations and edge cases

    Raises:
        ValueError: If required context is missing
        RuntimeError: If Claude API call fails
    """
    # Validate required context
    required_keys = ["design_analysis", "code_changes", "test_results"]
    missing_keys = [key for key in required_keys if key not in context]
    if missing_keys:
        raise ValueError(f"Missing required context keys: {missing_keys}")

    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it to use the Documentation Agent."
        )

    # Build context message for Claude
    context_message = _build_context_message(context)

    # Initialize Anthropic client
    client = Anthropic(api_key=api_key)

    try:
        # Call Claude API
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=DOCS_AGENT_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": context_message,
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent documentation
        )

        # Extract response text
        response_text = response.content[0].text

        # Parse structured output
        docs_output = _parse_docs_response(response_text)

        return docs_output

    except APIError as e:
        raise RuntimeError(f"Claude API call failed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error in docs agent: {e}") from e


def _build_context_message(context: Dict[str, Any]) -> str:
    """Build a comprehensive context message for the documentation agent.

    Args:
        context: Dictionary with outputs from previous agents

    Returns:
        Formatted context message for Claude
    """
    message_parts = []

    # Issue information
    if "issue_title" in context:
        message_parts.append(f"## Issue Title\n{context['issue_title']}\n")
    if "issue_description" in context:
        message_parts.append(f"## Issue Description\n{context['issue_description']}\n")
    if "issue_type" in context:
        message_parts.append(f"## Issue Type\n{context['issue_type']}\n")

    # Design phase outputs
    message_parts.append(f"## Design Analysis\n{context['design_analysis']}\n")

    if "implementation_plan" in context:
        message_parts.append(f"## Implementation Plan\n{context['implementation_plan']}\n")

    if "impacted_components" in context and context["impacted_components"]:
        components = "\n".join(f"- {comp}" for comp in context["impacted_components"])
        message_parts.append(f"## Impacted Components\n{components}\n")

    if "risks" in context and context["risks"]:
        risks = "\n".join(f"- {risk}" for risk in context["risks"])
        message_parts.append(f"## Identified Risks\n{risks}\n")

    if "acceptance_criteria" in context and context["acceptance_criteria"]:
        criteria = "\n".join(f"- {c}" for c in context["acceptance_criteria"])
        message_parts.append(f"## Acceptance Criteria\n{criteria}\n")

    # Development phase outputs
    if "code_changes" in context:
        files_changed = list(context["code_changes"].keys())
        message_parts.append(
            f"## Code Changes\n"
            f"Modified {len(files_changed)} file(s):\n"
            + "\n".join(f"- {file}" for file in files_changed)
            + "\n"
        )

    # Test phase outputs
    test_results = context.get("test_results", {})
    message_parts.append(
        f"## Test Results\n{json.dumps(test_results, indent=2)}\n"
    )

    if "test_summary" in context:
        message_parts.append(f"## Test Summary\n{context['test_summary']}\n")

    if "coverage_gaps" in context and context["coverage_gaps"]:
        gaps = "\n".join(f"- {gap}" for gap in context["coverage_gaps"])
        message_parts.append(f"## Coverage Gaps\n{gaps}\n")

    if "test_failures" in context and context["test_failures"]:
        failures = "\n".join(f"- {failure}" for failure in context["test_failures"])
        message_parts.append(f"## Test Failures\n{failures}\n")

    # Request documentation generation
    message_parts.append(
        "\n---\n\n"
        "Based on the above context, generate comprehensive documentation including:\n"
        "1. PR Summary - concise pull request description\n"
        "2. Release Notes - user-facing changelog entry\n"
        "3. Documentation Changes - specific doc updates needed\n"
        "4. Upgrade Notes - version-specific upgrade guidance\n"
        "5. Known Limitations - edge cases or limitations\n\n"
        "Format your response with clear section headers."
    )

    return "\n".join(message_parts)


def _parse_docs_response(response_text: str) -> Dict[str, Any]:
    """Parse Claude's response into structured documentation output.

    Args:
        response_text: Raw text response from Claude API

    Returns:
        Dictionary with structured documentation sections
    """
    # Initialize output structure
    output = {
        "pr_summary": "",
        "release_notes": "",
        "docs_changes": {},
        "upgrade_notes": "",
        "known_limitations": "",
    }

    # Split response into sections
    sections = _split_into_sections(response_text)

    # Extract each section
    output["pr_summary"] = sections.get("pr summary", "").strip()
    output["release_notes"] = sections.get("release note", "").strip()
    output["upgrade_notes"] = sections.get("upgrade note", "").strip()
    output["known_limitations"] = sections.get("known limitation", "").strip()

    # Parse documentation changes
    docs_section = sections.get("documentation change", "")
    if docs_section:
        output["docs_changes"] = _parse_docs_changes(docs_section)

    # If no structured sections found, put everything in pr_summary
    if not any(output.values()):
        output["pr_summary"] = response_text.strip()

    return output


def _split_into_sections(text: str) -> Dict[str, str]:
    """Split response text into sections based on headers.

    Args:
        text: Raw response text with section headers

    Returns:
        Dictionary mapping section names to content
    """
    sections = {}
    current_section = None
    current_content = []

    for line in text.split("\n"):
        # Check if line is a section header (## Header or ### Header)
        if line.startswith("##"):
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content)
            # Start new section
            current_section = line.lstrip("#").strip().lower()
            current_content = []
        else:
            # Add to current section
            if current_section:
                current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content)

    return sections


def _parse_docs_changes(docs_section: str) -> Dict[str, str]:
    """Parse documentation changes section into file mappings.

    Args:
        docs_section: Text describing documentation changes

    Returns:
        Dictionary mapping file paths to change descriptions
    """
    docs_changes = {}

    # Look for file paths and their associated changes
    # This is a simple parser that looks for markdown-style file references
    current_file = None
    current_changes = []

    for line in docs_section.split("\n"):
        line = line.strip()

        # Check if line contains a file path (e.g., `docs/user-guide.md`)
        if "`" in line and (".md" in line or ".yaml" in line or ".yml" in line):
            # Save previous file changes
            if current_file:
                docs_changes[current_file] = "\n".join(current_changes)

            # Extract file path
            start = line.find("`") + 1
            end = line.find("`", start)
            if end > start:
                current_file = line[start:end]
                current_changes = []
        elif current_file and line:
            # Add to current file changes
            current_changes.append(line)

    # Save last file
    if current_file:
        docs_changes[current_file] = "\n".join(current_changes)

    # If no specific files found, return the whole section as a generic entry
    if not docs_changes:
        docs_changes["documentation_updates"] = docs_section.strip()

    return docs_changes
