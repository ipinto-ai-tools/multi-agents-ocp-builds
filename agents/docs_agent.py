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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from anthropic import APIError

from config.agent_prompts import DOCS_AGENT_PROMPT
from config.auth_config import get_anthropic_client
from tools.prompt_guard import sanitize_external_input
from tools.rag_search import RAGSearch, RAGSearchError
from utils.file_logger import get_logger, get_session_logger

# Initialize logger
logger = get_logger(__name__)


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
    # Get session-specific logger
    session_id = context.get("session_id", "unknown")
    session_logger = get_session_logger(session_id, "docs_agent")

    logger.info(f"Starting documentation generation for session {session_id}: {context.get('issue_title', 'N/A')}")
    session_logger.info(f"Docs agent started - format: {output_format}, RAG: {enable_rag}")

    # Validate required context
    required_keys = ["design_analysis", "code_changes", "test_results"]
    missing_keys = [key for key in required_keys if key not in context]
    if missing_keys:
        logger.error(f"Missing required context keys: {missing_keys}")
        session_logger.error(f"Missing required keys: {missing_keys}")
        raise ValueError(f"Missing required context keys: {missing_keys}")

    logger.debug("Context validation passed")

    # Initialize RAG search if enabled
    rag_context = {}
    if enable_rag and "repo_path" in context:
        logger.info(f"RAG search enabled for repo: {context['repo_path']}")
        try:
            rag_context = _fetch_rag_context(context, input_files)
            logger.info(f"RAG context fetched: {list(rag_context.keys())}")
            session_logger.info(f"RAG context: {len(rag_context.get('related_docs', []))} docs, {len(rag_context.get('code_examples', []))} examples")
        except RAGSearchError as e:
            logger.warning(f"RAG search failed: {e}. Continuing without RAG context.", exc_info=True)
            session_logger.warning(f"RAG search failed: {e}")

    # Process input files if provided
    input_file_context = {}
    if input_files:
        logger.info(f"Processing {len(input_files)} input files")
        input_file_context = _process_input_files(
            input_files,
            context.get("repo_path", ".")
        )
        session_logger.info(f"Processed {len(input_file_context.get('file_contents', {}))} input files")

    # Build context message for Claude
    logger.debug("Building context message for Claude")
    context_message = _build_context_message(
        context,
        rag_context,
        input_file_context,
        output_format
    )
    session_logger.debug(f"Context message length: {len(context_message)} chars")

    # Get configured client (handles both API key and enterprise auth)
    try:
        client = get_anthropic_client()
        logger.info("Claude client initialized successfully")
        session_logger.info("Claude client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Claude client: {e}", exc_info=True)
        session_logger.error(f"Failed to initialize Claude client: {e}")
        raise RuntimeError(f"Failed to initialize Claude client: {e}") from e

    try:
        # Call Claude API
        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
        logger.info(f"Calling Claude API with model: {model}, max_tokens: 8192, temperature: 0.3")
        session_logger.info(f"API Request: model={model}, max_tokens=8192, temperature=0.3")

        response = client.messages.create(
            model=model,
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
        logger.info(f"Received response from Claude API ({len(response_text)} chars)")
        session_logger.info(f"Response length: {len(response_text)} chars")

        # Parse structured output
        logger.debug("Parsing documentation response")
        docs_output = _parse_docs_response(response_text, output_format)

        # Add metadata about processing
        docs_output["input_files_analyzed"] = input_files or []
        docs_output["rag_enabled"] = enable_rag
        docs_output["output_format"] = output_format

        logger.info(f"Documentation generation completed successfully. Format: {output_format}")
        session_logger.info(f"Docs generation complete - sections: {list(docs_output.keys())}")

        return docs_output

    except APIError as e:
        logger.error(f"Claude API call failed: {e}", exc_info=True)
        session_logger.error(f"Claude API call failed: {e}")
        raise RuntimeError(f"Claude API call failed: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error in docs agent: {e}", exc_info=True)
        session_logger.error(f"Unexpected error: {e}")
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
        logger.debug("No repo_path in context, skipping RAG")
        return {}

    logger.debug(f"Initializing RAG search for repo: {repo_path}")
    rag_search = RAGSearch(repo_path)
    rag_context: Dict[str, Any] = {}

    # Search Shipwright documentation
    if "issue_title" in context:
        logger.debug(f"Searching Shipwright docs for: {context['issue_title']}")
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
        logger.debug(f"Found {len(doc_matches)} related docs")

    # Extract code examples from modified files or input files
    files_to_analyze = input_files or context.get("files_modified", [])
    if files_to_analyze:
        logger.debug(f"Extracting code examples from {len(files_to_analyze)} files")
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
        logger.debug(f"Extracted {len(code_examples)} code examples")

    # Search for similar implementations
    if files_to_analyze:
        logger.debug("Searching for similar code implementations")
        similar = rag_search.search_similar_code(
            reference_files=files_to_analyze[:3],  # Top 3 files
            max_results=5
        )
        rag_context["similar_implementations"] = [
            {"file": res.file_path, "line": res.line_number}
            for res in similar
        ]
        logger.debug(f"Found {len(similar)} similar implementations")

    # Find API usage patterns (extract from design analysis)
    api_names = _extract_api_names(context.get("design_analysis", ""))
    if api_names:
        logger.debug(f"Searching API patterns for: {api_names[:3]}")
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
        logger.debug(f"Found {len(api_patterns)} API patterns")

    return rag_context


def _extract_api_names(design_text: str) -> List[str]:
    """Extract API/type names from design text.

    Args:
        design_text: Design analysis text

    Returns:
        List of API/type names
    """
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
            logger.warning(f"Input file does not exist: {file_path}")
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Truncate large files
            if len(content) > 5000:
                logger.debug(f"Truncating large input file: {file_path} ({len(content)} chars)")
                content = content[:5000] + "\n... (truncated)"

            file_contents[file_path] = content
            logger.debug(f"Processed input file: {file_path} ({len(content)} chars)")

        except (IOError, UnicodeDecodeError) as e:
            logger.warning(f"Error reading input file {file_path}: {e}")
            file_contents[file_path] = f"Error reading file: {e}"

    input_context["file_contents"] = file_contents
    logger.info(f"Processed {len(file_contents)} input files")
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

    # Issue information (sanitize external-origin fields before injection)
    if "issue_title" in context:
        issue_title = sanitize_external_input(context["issue_title"], source="docs:issue_title")
        message_parts.append(f"## Issue Title\n{issue_title}\n")
    if "issue_description" in context:
        issue_description = sanitize_external_input(context["issue_description"], source="docs:issue_description")
        message_parts.append(f"## Issue Description\n{issue_description}\n")
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

    # Upstream GitHub PRs (from Jira remote links)
    github_pr_data = context.get("github_pr_data", [])
    if github_pr_data:
        message_parts.append("\n## Upstream GitHub Pull Requests\n")
        message_parts.append(
            "These are the upstream community PRs linked to this Jira ticket. "
            "Use the PR titles, descriptions, and metadata to enrich the documentation.\n"
        )
        for pr in github_pr_data:
            pr_url = pr.get("pr_url", "unknown")
            state_label = pr.get("state", "unknown").upper()
            pr_title = sanitize_external_input(pr.get("title", "N/A"), source=f"docs:github_pr:title:{pr_url}")
            pr_author = sanitize_external_input(pr.get("author", "N/A"), source=f"docs:github_pr:author:{pr_url}")
            pr_base_branch = sanitize_external_input(pr.get("base_branch", "N/A"), source=f"docs:github_pr:base_branch:{pr_url}")
            reviewers = [
                sanitize_external_input(r, source=f"docs:github_pr:reviewer:{pr_url}")
                for r in pr.get("reviewers", [])
            ]
            labels = [
                sanitize_external_input(l, source=f"docs:github_pr:label:{pr_url}")
                for l in pr.get("labels", [])
            ]
            message_parts.append(
                f"### PR #{pr.get('pr_number')} — {pr_title} [{state_label}]\n"
                f"**URL**: {pr_url}\n"
                f"**Repository**: {pr.get('repo_full_name', 'N/A')}\n"
                f"**Author**: {pr_author}\n"
                f"**Base branch**: {pr_base_branch}\n"
                f"**Files changed**: {pr.get('files_changed', 0)} "
                f"(+{pr.get('additions', 0)} / -{pr.get('deletions', 0)})\n"
            )
            if reviewers:
                message_parts.append(f"**Reviewers**: {', '.join(reviewers)}\n")
            if labels:
                message_parts.append(f"**Labels**: {', '.join(labels)}\n")
            if pr.get("merged_at"):
                message_parts.append(f"**Merged**: {pr['merged_at']}\n")
            body = pr.get("body", "").strip()
            if body:
                # Cap PR body at 2000 chars to avoid token bloat, then sanitize
                truncated = body[:2000] + ("\n...[truncated]" if len(body) > 2000 else "")
                safe_body = sanitize_external_input(truncated, source=f"docs:github_pr:{pr_url}")
                message_parts.append(f"\n**PR Description**:\n{safe_body}\n")
            message_parts.append("\n")
    elif context.get("github_pr_urls"):
        # URLs were found but GitHub token not set — mention them for reference
        message_parts.append("\n## Upstream GitHub Pull Requests (URLs only — token not set)\n")
        for url in context["github_pr_urls"]:
            message_parts.append(f"- {url}\n")
        message_parts.append("\n")

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
        return base_request + jtbd_request + "\nFormat your response with clear section headers."

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
    output["release_notes"] = (sections.get("release notes") or sections.get("release note") or "").strip()
    output["upgrade_notes"] = (sections.get("upgrade notes") or sections.get("upgrade note") or "").strip()
    output["known_limitations"] = (sections.get("known limitations") or sections.get("known limitation") or "").strip()
    output["high_level_design"] = sections.get("high-level design", sections.get("high level design", "")).strip()

    # Format-specific sections
    if output_format in ("standard", "jtbd", "all"):
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
