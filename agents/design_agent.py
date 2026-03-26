"""Design Agent for OpenShift Build API.

This module implements the Design Agent which analyzes feature requests or bug reports
and produces comprehensive design documents to guide implementation.

The agent uses Claude API to perform deep analysis of requirements and generate
structured design documentation including impact analysis, risk assessment, and
implementation planning.
"""

import os
import re
from typing import Dict, Any, Optional

from config.agent_prompts import DESIGN_AGENT_PROMPT
from config.auth_config import get_anthropic_client
from utils.file_logger import get_logger
from config.shipwright_components import (
    get_component_info,
    COMPONENTS,
    CRD_TYPES,
    BUILD_STRATEGIES,
    OPENSHIFT_INTEGRATIONS,
)
from tools.repo_search import RepoSearch
from tools.prompt_guard import sanitize_external_input

# Initialize logger
logger = get_logger(__name__)


class DesignAgentError(Exception):
    """Base exception for Design Agent errors."""


def run_design(title: str, description: str, repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Run design analysis on a GitHub issue.

    This function analyzes a feature request or bug report and produces a comprehensive
    design document using Claude AI. It gathers context from the repository and
    Shipwright component definitions to provide informed design recommendations.

    Args:
        title: GitHub issue title
        description: GitHub issue description/body
        repo_path: Optional path to the Shipwright repository for code analysis.
                  If not provided, analysis is based on component metadata only.

    Returns:
        Dictionary containing:
            - design_analysis: Complete design document in Markdown format
            - impacted_components: List of component names that will be affected
            - risks: List of identified risks and mitigation strategies
            - acceptance_criteria: List of testable acceptance criteria
            - implementation_plan: Step-by-step implementation approach

    Raises:
        DesignAgentError: If API key is missing or analysis fails

    Example:
        result = run_design(
             title="Add timeout support to BuildRun",
             description="Users need to specify build timeout to prevent hanging builds",
             repo_path="/path/to/shipwright-build"
        )
        print(result["design_analysis"])
    """
    logger.info(f"Starting design analysis for issue: {title}")

    # Get configured client (handles both API key and enterprise auth)
    try:
        client = get_anthropic_client()
        logger.info("Claude client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Claude client: {e}", exc_info=True)
        raise DesignAgentError(f"Failed to initialize Claude client: {e}") from e

    # Gather repository context if path provided
    if repo_path:
        logger.info(f"Gathering repository context from: {repo_path}")
        repo_context = _gather_repo_context(repo_path)
    else:
        logger.info("No repository path provided, skipping repository context")
        repo_context = None

    # Build component information context
    logger.debug("Building component context")
    component_context = _build_component_context()

    # Construct the analysis prompt
    logger.debug("Constructing analysis prompt")
    user_prompt = _build_analysis_prompt(
        title=title,
        description=description,
        component_context=component_context,
        repo_context=repo_context,
    )

    # Call Claude API
    try:
        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
        logger.info(f"Calling Claude API with model: {model}")

        response = client.messages.create(
            model=model,
            max_tokens=8000,
            system=DESIGN_AGENT_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        # Extract the design analysis from response
        design_text = response.content[0].text
        logger.info(f"Received response from Claude API ({len(design_text)} chars)")

    except Exception as e:
        logger.error(f"Claude API call failed: {e}", exc_info=True)
        if "google.auth" in str(e) or "anthropic[vertex]" in str(e):
            raise DesignAgentError(
                f"Claude API call failed: Missing Vertex AI dependencies. "
                f"Set ANTHROPIC_VERTEX_PROJECT_ID and install: pip install anthropic[vertex]"
            ) from e
        raise DesignAgentError(f"Claude API call failed: {e}") from e

    # Parse the structured output from the design document
    logger.debug("Parsing design output")
    parsed_result = _parse_design_output(design_text)
    logger.info(f"Design analysis completed successfully. Found {len(parsed_result.get('impacted_components', []))} impacted components")

    return {
        "design_analysis": design_text,
        "impacted_components": parsed_result.get("impacted_components", []),
        "risks": parsed_result.get("risks", []),
        "acceptance_criteria": parsed_result.get("acceptance_criteria", []),
        "implementation_plan": parsed_result.get("implementation_plan", []),
    }


def _gather_repo_context(repo_path: str) -> Dict[str, Any]:
    """Gather relevant context from the repository.

    Args:
        repo_path: Path to the repository

    Returns:
        Dictionary containing repository insights
    """
    context = {
        "package_structure": [],
        "api_files": [],
        "controller_files": [],
        "crd_files": [],
    }

    try:
        searcher = RepoSearch(repo_path)

        # Find API types
        logger.debug("Searching for API types")
        api_results = searcher.search_files("pkg/apis/**/*_types.go")
        context["api_files"] = [r.file_path for r in api_results[:10]]
        logger.debug(f"Found {len(api_results)} API files")

        # Find controllers
        logger.debug("Searching for controllers")
        controller_results = searcher.search_files("pkg/controller/**/*.go")
        context["controller_files"] = [r.file_path for r in controller_results[:10]]
        logger.debug(f"Found {len(controller_results)} controller files")

        # Find CRD definitions
        logger.debug("Searching for CRD definitions")
        crd_results = searcher.find_kubernetes_crds()
        context["crd_files"] = [r.file_path for r in crd_results[:10]]
        logger.debug(f"Found {len(crd_results)} CRD files")

        # Analyze package structure
        logger.debug("Analyzing package structure")
        packages = searcher.analyze_go_packages("pkg")
        context["package_structure"] = [
            {"name": pkg.name, "path": pkg.path, "file_count": len(pkg.files)}
            for pkg in packages[:20]
        ]
        logger.debug(f"Analyzed {len(packages)} packages")

    except Exception as e:
        # If repository analysis fails, continue with component metadata only
        logger.warning(f"Repository analysis failed: {e}", exc_info=True)
        context["error"] = f"Repository analysis failed: {str(e)}"

    return context


def _build_component_context() -> str:
    """Build component information context for the agent.

    Returns:
        Formatted string containing component information
    """
    lines = [
        "# Shipwright Build Components\n",
        "## Available Components:",
    ]

    for component_name, purpose in COMPONENTS.items():
        info = get_component_info(component_name)
        lines.append(f"\n### {component_name}")
        lines.append(f"**Purpose:** {purpose}")
        lines.append(f"**Tests Required:** {', '.join(info['test_requirements'])}")
        if info["dependencies"]:
            lines.append(f"**Dependencies:** {', '.join(info['dependencies'])}")
        if info["file_patterns"]:
            lines.append(f"**File Patterns:** {', '.join(info['file_patterns'][:3])}")

    lines.append("\n## Custom Resource Definitions:")
    for crd in CRD_TYPES:
        lines.append(f"- {crd}")

    lines.append("\n## Build Strategies:")
    for strategy_name, strategy_info in BUILD_STRATEGIES.items():
        lines.append(f"\n### {strategy_name}")
        lines.append(f"- Type: {strategy_info['type']}")
        lines.append(f"- Builder: {strategy_info['builder']}")
        lines.append(f"- Use Case: {strategy_info['use_case']}")

    lines.append("\n## OpenShift Integrations:")
    for integration, description in OPENSHIFT_INTEGRATIONS.items():
        lines.append(f"- **{integration}**: {description}")

    return "\n".join(lines)


def _build_analysis_prompt(
    title: str,
    description: str,
    component_context: str,
    repo_context: Optional[Dict[str, Any]],
) -> str:
    """Build the user prompt for design analysis.

    Args:
        title: Issue title
        description: Issue description
        component_context: Component information
        repo_context: Repository context (if available)

    Returns:
        Formatted prompt string
    """
    title = sanitize_external_input(title, source="design:title")
    description = sanitize_external_input(description, source="design:description")

    prompt_parts = [
        "# Design Analysis Request\n",
        f"## Issue Title\n{title}\n",
        f"## Issue Description\n{description}\n",
        f"## Component Information\n{component_context}\n",
    ]

    if repo_context:
        prompt_parts.append("\n## Repository Context\n")
        if "error" in repo_context:
            prompt_parts.append(f"Note: {repo_context['error']}\n")
        else:
            if repo_context.get("api_files"):
                prompt_parts.append(
                    f"**API Files Found:** {len(repo_context['api_files'])}\n"
                )
            if repo_context.get("controller_files"):
                prompt_parts.append(
                    f"**Controller Files Found:** {len(repo_context['controller_files'])}\n"
                )
            if repo_context.get("crd_files"):
                prompt_parts.append(
                    f"**CRD Files Found:** {len(repo_context['crd_files'])}\n"
                )
            if repo_context.get("package_structure"):
                prompt_parts.append("\n**Package Structure (sample):**\n")
                for pkg in repo_context["package_structure"][:5]:
                    prompt_parts.append(
                        f"- {pkg['path']}: {pkg['file_count']} files\n"
                    )

    prompt_parts.append(
        "\n## Request\n"
        "Please analyze this issue and produce a comprehensive design document "
        "following the structure defined in your system prompt. Focus on:\n"
        "1. Clearly identifying the problem or feature request\n"
        "2. Listing all impacted components with specific file paths where possible\n"
        "3. Identifying risks and proposing mitigation strategies\n"
        "4. Defining concrete acceptance criteria\n"
        "5. Creating a step-by-step implementation plan\n"
    )

    return "".join(prompt_parts)


def _parse_design_output(design_text: str) -> Dict[str, Any]:
    """Parse structured information from the design document.

    Extracts key elements from the Markdown design document for programmatic use.

    Args:
        design_text: The complete design document in Markdown format

    Returns:
        Dictionary with extracted structured data
    """
    result = {
        "impacted_components": [],
        "risks": [],
        "acceptance_criteria": [],
        "implementation_plan": [],
    }

    lines = design_text.split("\n")
    current_section = None

    for line in lines:
        line_stripped = line.strip()

        # Detect sections
        if "### Impacted Components" in line or "## Impacted Components" in line:
            current_section = "impacted_components"
            continue
        elif "### Risks" in line or "## Risks" in line:
            current_section = "risks"
            continue
        elif "### Acceptance Criteria" in line or "## Acceptance Criteria" in line:
            current_section = "acceptance_criteria"
            continue
        elif "### Implementation Plan" in line or "## Implementation Plan" in line:
            current_section = "implementation_plan"
            continue
        elif line_stripped.startswith("##") and not line_stripped.startswith("###"):
            # New ## section that we're not tracking; ### subheadings do NOT reset
            current_section = None
            continue

        # Extract bullet points from current section
        if current_section and line_stripped.startswith("-"):
            item = line_stripped[1:].strip()
            if item:
                result[current_section].append(item)
        elif current_section:
            numbered = re.match(r'^\d+\.\s+(.*)', line_stripped)
            if numbered:
                item = numbered.group(1).strip()
                if item:
                    result[current_section].append(item)

    # Also extract component names mentioned in the document
    for component_name in COMPONENTS.keys():
        if component_name in design_text or component_name.replace("_", " ") in design_text:
            if component_name not in result["impacted_components"]:
                # Add as structured reference
                result["impacted_components"].append(component_name)

    return result
