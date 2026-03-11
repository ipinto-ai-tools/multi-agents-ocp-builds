"""Documentation Agent for the OpenShift Build API multi-agent system.

This agent generates documentation artifacts including PR summaries, release notes,
documentation changes, upgrade notes, and high-level design documents.

Enhanced with:
- Agentic RAG for fetching relevant documentation and code examples
- SHIP format output (Solution, Highlight, Impact, Plan)
- Input file support for context-aware documentation
- High-level design generation for implementation guidance
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from anthropic import Anthropic, APIError
from config.agent_prompts import DOCS_AGENT_PROMPT
from tools.rag_search import RAGSearch, RAGSearchError


def run_docs(
    context: Dict[str, Any],
    input_files: Optional[List[str]] = None,
    output_format: str = "standard",
    enable_rag: bool = True
) -> Dict[str, Any]:
    """Generate documentation based on design, development, and test outputs.

    This function uses Claude API to analyze the complete context from previous
    agent phases (design analysis, code changes, test results) and generates
    comprehensive documentation artifacts.

    Enhanced with RAG capabilities to fetch relevant documentation, code examples,
    and API usage patterns from the repository.

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
            - repo_path: str - Path to repository (required for RAG)
        input_files: Optional list of file paths to include as context
        output_format: Output format - "standard", "ship", "jtbd", or "all"
        enable_rag: Enable RAG for fetching relevant documentation

    Returns:
        Dictionary with documentation outputs:
            - pr_summary: str - Pull request description
            - release_notes: str - User-facing release notes
            - docs_changes: dict - Documentation file changes (path: content)
            - upgrade_notes: str - Version upgrade considerations
            - known_limitations: str - Limitations and edge cases
            - jtbd_documentation: str - Jobs-to-be-Done format documentation
            - ship_document: str - SHIP format document (if requested)
            - high_level_design: str - Comprehensive design for implementation
            - input_files_analyzed: list - List of files processed

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

    # Initialize RAG search if enabled
    rag_context = {}
    if enable_rag and "repo_path" in context:
        try:
            rag_context = _fetch_rag_context(context, input_files)
        except RAGSearchError as e:
            print(f"Warning: RAG search failed: {e}. Continuing without RAG context.")

    # Process input files if provided
    input_file_context = {}
    if input_files:
        input_file_context = _process_input_files(
            input_files,
            context.get("repo_path", ".")
        )

    # Build context message for Claude
    context_message = _build_context_message(
        context,
        rag_context,
        input_file_context,
        output_format
    )

    # Initialize Anthropic client
    client = Anthropic(api_key=api_key)

    try:
        # Call Claude API
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,  # Increased for comprehensive documentation
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
        docs_output = _parse_docs_response(response_text, output_format)

        # Add metadata about processing
        docs_output["input_files_analyzed"] = input_files or []
        docs_output["rag_enabled"] = enable_rag
        docs_output["output_format"] = output_format

        return docs_output

    except APIError as e:
        raise RuntimeError(f"Claude API call failed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error in docs agent: {e}") from e


def _fetch_rag_context(
    context: Dict[str, Any],
    input_files: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Fetch relevant context using RAG search.

    Args:
        context: Agent context with repo_path and files_modified
        input_files: Optional input files to analyze

    Returns:
        Dictionary with RAG context:
            - related_docs: List of related documentation
            - code_examples: List of code examples
            - api_patterns: List of API usage patterns
            - similar_implementations: List of similar code
    """
    repo_path = context.get("repo_path")
    if not repo_path:
        return {}

    rag_search = RAGSearch(repo_path)
    rag_context: Dict[str, Any] = {}

    # Search Shipwright documentation
    if "issue_title" in context:
        doc_matches = rag_search.search_shipwright_docs(
            query=context["issue_title"],
            max_results=3
        )
        rag_context["related_docs"] = [
            {
                "file": match.file_path,
                "section": match.section_title,
                "content": match.content[:500]  # First 500 chars
            }
            for match in doc_matches
        ]

    # Extract code examples from modified files or input files
    files_to_analyze = input_files or context.get("files_modified", [])
    if files_to_analyze:
        code_examples = rag_search.extract_code_examples(files_to_analyze)
        rag_context["code_examples"] = [
            {
                "file": ex.file_path,
                "language": ex.language,
                "context": ex.context,
                "code": ex.code[:300]  # First 300 chars
            }
            for ex in code_examples[:5]  # Top 5 examples
        ]

    # Search for similar implementations
    if files_to_analyze:
        similar = rag_search.search_similar_code(
            reference_files=files_to_analyze[:3],  # Top 3 files
            max_results=5
        )
        rag_context["similar_implementations"] = [
            {"file": res.file_path, "line": res.line_number}
            for res in similar
        ]

    # Find API usage patterns (extract from design analysis)
    api_names = _extract_api_names(context.get("design_analysis", ""))
    if api_names:
        api_patterns = rag_search.search_api_patterns(
            api_names=api_names[:3],  # Top 3 APIs
            file_pattern="**/*.go"
        )
        rag_context["api_patterns"] = [
            {
                "api": pattern.api_name,
                "file": pattern.file_path,
                "type": pattern.pattern_type,
                "code": pattern.usage_code[:200]
            }
            for pattern in api_patterns[:5]  # Top 5 patterns
        ]

    return rag_context


def _extract_api_names(design_text: str) -> List[str]:
    """Extract API/type names from design text.

    Args:
        design_text: Design analysis text

    Returns:
        List of API/type names
    """
    import re

    # Look for capitalized identifiers (likely type names)
    # Pattern: words that start with capital letter and have at least 2 more letters
    api_names = re.findall(r'\b([A-Z][a-z]+[A-Z]\w+)\b', design_text)

    # Also look for explicitly mentioned APIs
    # Pattern: "the XYZ API" or "XYZ spec"
    explicit_apis = re.findall(r'\b([A-Z][a-zA-Z0-9]+)\s+(?:API|spec|controller|CRD)\b', design_text)

    # Combine and deduplicate
    all_apis = list(set(api_names + explicit_apis))

    return all_apis[:10]  # Return top 10


def _process_input_files(
    input_files: List[str],
    repo_path: str
) -> Dict[str, Any]:
    """Process input files to extract context.

    Args:
        input_files: List of file paths
        repo_path: Repository root path

    Returns:
        Dictionary with input file context
    """
    repo_root = Path(repo_path)
    input_context: Dict[str, Any] = {}
    file_contents = {}

    for file_path in input_files:
        full_path = repo_root / file_path

        if not full_path.exists():
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Truncate large files
            if len(content) > 5000:
                content = content[:5000] + "\n... (truncated)"

            file_contents[file_path] = content

        except (IOError, UnicodeDecodeError) as e:
            file_contents[file_path] = f"Error reading file: {e}"

    input_context["file_contents"] = file_contents
    return input_context


def _build_context_message(
    context: Dict[str, Any],
    rag_context: Dict[str, Any],
    input_file_context: Dict[str, Any],
    output_format: str
) -> str:
    """Build a comprehensive context message for the documentation agent.

    Args:
        context: Dictionary with outputs from previous agents
        rag_context: RAG search results
        input_file_context: Processed input file context
        output_format: Requested output format

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

    # RAG context
    if rag_context:
        message_parts.append("\n## RAG Context (Retrieved Documentation & Examples)\n")

        if "related_docs" in rag_context and rag_context["related_docs"]:
            message_parts.append("### Related Documentation\n")
            for doc in rag_context["related_docs"]:
                message_parts.append(
                    f"**{doc['file']}** - {doc['section']}\n"
                    f"{doc['content']}\n"
                )

        if "code_examples" in rag_context and rag_context["code_examples"]:
            message_parts.append("### Code Examples\n")
            for example in rag_context["code_examples"]:
                message_parts.append(
                    f"**{example['file']}** ({example['language']}) - {example['context']}\n"
                    f"```{example['language']}\n{example['code']}\n```\n"
                )

        if "api_patterns" in rag_context and rag_context["api_patterns"]:
            message_parts.append("### API Usage Patterns\n")
            for pattern in rag_context["api_patterns"]:
                message_parts.append(
                    f"**{pattern['api']}** - {pattern['type']} in {pattern['file']}\n"
                    f"```go\n{pattern['code']}\n```\n"
                )

    # Input file context
    if input_file_context and "file_contents" in input_file_context:
        message_parts.append("\n## Input Files Provided\n")
        for file_path, content in input_file_context["file_contents"].items():
            message_parts.append(f"### {file_path}\n```\n{content}\n```\n")

    # Request documentation generation based on format
    message_parts.append("\n---\n\n")
    message_parts.append(_get_generation_request(output_format))

    return "\n".join(message_parts)


def _get_generation_request(output_format: str) -> str:
    """Get documentation generation request based on format.

    Args:
        output_format: Requested output format

    Returns:
        Generation request text
    """
    base_request = (
        "Based on the above context, generate comprehensive documentation including:\n"
        "1. PR Summary - concise pull request description\n"
        "2. Release Notes - user-facing changelog entry\n"
        "3. Documentation Changes - specific doc updates needed\n"
        "4. Upgrade Notes - version-specific upgrade guidance\n"
        "5. Known Limitations - edge cases or limitations\n"
        "6. High-Level Design - comprehensive design document for implementation\n"
    )

    jtbd_request = (
        "7. JTBD Documentation - Jobs-to-be-Done format with:\n"
        "   - Job title (what the user wants to accomplish)\n"
        "   - Context (when/why they need this)\n"
        "   - Steps to complete the job (with examples)\n"
        "   - Troubleshooting (common issues and solutions)\n"
        "   - Related jobs (see also)\n"
    )

    ship_request = (
        "8. SHIP Document - Structured as:\n"
        "   - **Solution**: What is being built and why\n"
        "   - **Highlight**: Key features, benefits, and differentiators\n"
        "   - **Impact**: Who is affected and how (users, operators, developers)\n"
        "   - **Plan**: Implementation roadmap with phases and milestones\n"
    )

    if output_format == "standard":
        return base_request + "\nFormat your response with clear section headers."

    elif output_format == "jtbd":
        return base_request + jtbd_request + "\nFormat your response with clear section headers."

    elif output_format == "ship":
        return base_request + ship_request + "\nFormat your response with clear section headers."

    elif output_format == "all":
        return (
            base_request + jtbd_request + ship_request +
            "\nFormat your response with clear section headers."
        )

    else:
        return base_request + "\nFormat your response with clear section headers."


def _parse_docs_response(response_text: str, output_format: str) -> Dict[str, Any]:
    """Parse Claude's response into structured documentation output.

    Args:
        response_text: Raw text response from Claude API
        output_format: Requested output format

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
        "jtbd_documentation": "",
        "ship_document": "",
        "high_level_design": "",
    }

    # Split response into sections
    sections = _split_into_sections(response_text)

    # Extract each section
    output["pr_summary"] = sections.get("pr summary", "").strip()
    output["release_notes"] = sections.get("release note", "").strip()
    output["upgrade_notes"] = sections.get("upgrade note", "").strip()
    output["known_limitations"] = sections.get("known limitation", "").strip()
    output["high_level_design"] = sections.get("high-level design", sections.get("high level design", "")).strip()

    # Format-specific sections
    if output_format in ("jtbd", "all"):
        output["jtbd_documentation"] = sections.get("jtbd documentation", "").strip()

    if output_format in ("ship", "all"):
        output["ship_document"] = sections.get("ship document", "").strip()

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
        # Check if line is a section header (## Header only, not ###)
        if line.startswith("##") and not line.startswith("###"):
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content)
            # Start new section
            current_section = line.lstrip("#").strip().lower()
            current_content = []
        else:
            # Add to current section (including ### subsections)
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
