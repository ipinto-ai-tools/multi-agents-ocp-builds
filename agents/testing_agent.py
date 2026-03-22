"""Testing Agent for Shipwright Build.

This module implements the Testing Agent which generates comprehensive Ginkgo v2
tests for Shipwright Build features based on design analysis and acceptance criteria.

The agent analyzes design documents, detects patterns (build strategies, source types,
output types), and generates structured test plans along with working Ginkgo v2 test code.
"""

import os
from typing import Dict, Any, List, Optional

import yaml

from config.agent_prompts import TESTING_AGENT_PROMPT
from config.auth_config import get_anthropic_client
from utils.file_logger import get_logger, get_session_logger
from config.testing_config import (
    detect_patterns_in_description,
)

# Initialize logger
logger = get_logger(__name__)


class TestingAgentError(Exception):
    """Base exception for Testing Agent errors."""


def run_testing(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Ginkgo tests for Shipwright features.

    This function analyzes design documents and generates comprehensive test suites
    including test plans, specifications, and working Ginkgo v2 test code.

    Args:
        context: Dictionary containing:
            - design_analysis: Design document from design_agent (required)
            - impacted_components: List of components affected (required)
            - acceptance_criteria: List of acceptance criteria (required)
            - issue_type: bug/feature/refactor (optional)
            - issue_title: Feature/bug title (optional)
            - issue_description: Detailed description (optional)
            - implementation_plan: Implementation steps (optional)
            - risks: List of risks (optional)

    Returns:
        Dictionary containing:
            - test_plan: Human-readable test plan (STP-like)
            - test_specifications: YAML test specs (STD-like)
            - unit_tests: Generated Ginkgo unit test code
            - integration_tests: Generated Ginkgo integration test code
            - e2e_tests: Generated Ginkgo E2E test code
            - test_summary: Summary of generated tests
            - coverage_analysis: What's tested vs requirements
            - patterns_detected: Detected Shipwright patterns

    Raises:
        TestingAgentError: If API key is missing or generation fails

    Example:
        >>> context = {
        ...     "design_analysis": "# Design for timeout feature...",
        ...     "impacted_components": ["buildrun_api", "buildrun_controller"],
        ...     "acceptance_criteria": ["BuildRun accepts timeout field", ...],
        ...     "issue_title": "Add timeout support",
        ...     "issue_description": "Users need build timeout...",
        ... }
        >>> result = run_testing(context)
        >>> print(result["test_plan"])
    """
    # Get session-specific logger
    session_id = context.get("session_id", "unknown")
    session_logger = get_session_logger(session_id, "testing_agent")

    logger.info(f"Starting test generation for session {session_id}: {context.get('issue_title', 'N/A')}")
    session_logger.info(f"Testing agent started with context: {context.get('issue_title', 'N/A')}")

    # Validate required context
    try:
        _validate_context(context)
        logger.debug("Context validation passed")
    except TestingAgentError as e:
        logger.error(f"Context validation failed: {e}", exc_info=True)
        session_logger.error(f"Context validation failed: {e}")
        raise

    # Get configured client (handles both API key and enterprise auth)
    try:
        client = get_anthropic_client()
        logger.info("Claude client initialized successfully")
        session_logger.info("Claude client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Claude client: {e}", exc_info=True)
        session_logger.error(f"Failed to initialize Claude client: {e}")
        raise TestingAgentError(f"Failed to initialize Claude client: {e}") from e

    # Detect patterns in the issue description
    patterns_detected = {}
    if context.get("issue_description"):
        logger.debug("Detecting patterns in issue description")
        patterns_detected = detect_patterns_in_description(
            context["issue_description"] + "\n" + context.get("design_analysis", "")
        )
        logger.info(f"Detected patterns: {list(patterns_detected.keys())}")
        session_logger.info(f"Patterns detected: {patterns_detected}")

    # Build the test generation prompt
    logger.debug("Building test generation prompt")
    user_prompt = _build_testing_prompt(context, patterns_detected)
    session_logger.debug(f"Prompt length: {len(user_prompt)} chars")

    # Call Claude API
    try:
        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
        logger.info(f"Calling Claude API with model: {model}, max_tokens: 16000")
        session_logger.info(f"API Request: model={model}, max_tokens=16000")

        response = client.messages.create(
            model=model,
            max_tokens=16000,  # Larger for code generation
            system=TESTING_AGENT_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        # Extract the test output from response
        test_output = response.content[0].text
        logger.info(f"Received response from Claude API ({len(test_output)} chars)")
        session_logger.info(f"Response length: {len(test_output)} chars")

    except Exception as e:
        logger.error(f"Claude API call failed: {e}", exc_info=True)
        session_logger.error(f"Claude API call failed: {e}")
        raise TestingAgentError(f"Claude API call failed: {e}") from e

    # Parse the structured output
    logger.debug("Parsing test output")
    parsed_result = _parse_test_output(test_output)

    unit_count = len(parsed_result.get("unit_tests", {}))
    integration_count = len(parsed_result.get("integration_tests", {}))
    e2e_count = len(parsed_result.get("e2e_tests", {}))
    total_count = unit_count + integration_count + e2e_count

    logger.info(f"Test generation completed: {unit_count} unit, {integration_count} integration, {e2e_count} e2e tests")
    session_logger.info(f"Generated {total_count} test files (unit: {unit_count}, integration: {integration_count}, e2e: {e2e_count})")

    return {
        "test_plan": parsed_result.get("test_plan", ""),
        "test_specifications": parsed_result.get("test_specifications", {}),
        "unit_tests": parsed_result.get("unit_tests", {}),
        "integration_tests": parsed_result.get("integration_tests", {}),
        "e2e_tests": parsed_result.get("e2e_tests", {}),
        "test_summary": parsed_result.get("test_summary", ""),
        "coverage_analysis": parsed_result.get("coverage_analysis", ""),
        "patterns_detected": patterns_detected,
        "raw_output": test_output,  # Include raw output for debugging
    }


def _validate_context(context: Dict[str, Any]) -> None:
    """Validate that required context fields are present.

    Args:
        context: The context dictionary to validate

    Raises:
        TestingAgentError: If required fields are missing
    """
    required_fields = ["design_analysis", "impacted_components", "acceptance_criteria"]

    # Check for missing fields (fields not in dict at all)
    missing_fields = [field for field in required_fields if field not in context]

    if missing_fields:
        raise TestingAgentError(
            f"Missing required context fields: {', '.join(missing_fields)}. "
            f"Required fields are: {', '.join(required_fields)}"
        )

    # Validate types
    if not isinstance(context.get("impacted_components"), list):
        raise TestingAgentError("impacted_components must be a list")

    if not isinstance(context.get("acceptance_criteria"), list):
        raise TestingAgentError("acceptance_criteria must be a list")


def _build_testing_prompt(
    context: Dict[str, Any], patterns_detected: Dict[str, List[str]]
) -> str:
    """Build the user prompt for test generation.

    Args:
        context: Context containing design analysis and requirements
        patterns_detected: Detected Shipwright patterns

    Returns:
        Formatted prompt string
    """
    prompt_parts = [
        "# Test Generation Request\n",
        "## Feature/Bug Information\n",
    ]

    if context.get("issue_title"):
        prompt_parts.append(f"**Title:** {context['issue_title']}\n")

    if context.get("issue_type"):
        prompt_parts.append(f"**Type:** {context['issue_type']}\n")

    if context.get("issue_description"):
        prompt_parts.append(f"\n**Description:**\n{context['issue_description']}\n")

    prompt_parts.append("\n## Design Analysis\n")
    prompt_parts.append(f"{context['design_analysis']}\n")

    prompt_parts.append("\n## Impacted Components\n")
    for component in context["impacted_components"]:
        prompt_parts.append(f"- {component}\n")

    prompt_parts.append("\n## Acceptance Criteria\n")
    for idx, criterion in enumerate(context["acceptance_criteria"], 1):
        prompt_parts.append(f"{idx}. {criterion}\n")

    if context.get("implementation_plan"):
        prompt_parts.append("\n## Implementation Plan\n")
        if isinstance(context["implementation_plan"], list):
            for step in context["implementation_plan"]:
                prompt_parts.append(f"- {step}\n")
        else:
            prompt_parts.append(f"{context['implementation_plan']}\n")

    if context.get("risks"):
        prompt_parts.append("\n## Risks to Test\n")
        for risk in context["risks"]:
            prompt_parts.append(f"- {risk}\n")

    # Add detected patterns
    if patterns_detected:
        prompt_parts.append("\n## Detected Patterns\n")

        if patterns_detected.get("strategies"):
            prompt_parts.append(
                f"**Build Strategies:** {', '.join(patterns_detected['strategies'])}\n"
            )

        if patterns_detected.get("source_types"):
            prompt_parts.append(
                f"**Source Types:** {', '.join(patterns_detected['source_types'])}\n"
            )

        if patterns_detected.get("output_types"):
            prompt_parts.append(
                f"**Output Types:** {', '.join(patterns_detected['output_types'])}\n"
            )

        if patterns_detected.get("security_contexts"):
            prompt_parts.append(
                f"**Security Contexts:** {', '.join(patterns_detected['security_contexts'])}\n"
            )

    # Add test generation instructions
    prompt_parts.append(
        "\n## Test Generation Instructions\n\n"
        "Please generate comprehensive tests following these requirements:\n\n"
        "1. **Test Plan**: Create a human-readable test strategy document covering:\n"
        "   - Test approach and strategy\n"
        "   - Coverage mapping (each acceptance criterion to test cases)\n"
        "   - Test organization structure\n"
        "   - Risk areas requiring extra testing\n\n"
        "2. **Test Specifications**: Generate YAML specifications with:\n"
        "   - Test scenario IDs (format: BUILD-XXX-NNN)\n"
        "   - Test types (unit/integration/e2e)\n"
        "   - Pattern associations\n"
        "   - Helper functions needed\n"
        "   - Expected outcomes\n\n"
        "3. **Test Code**: Generate working Ginkgo v2 test code for:\n"
        "   - **Unit tests**: Mock-based, fast, isolated function tests\n"
        "   - **Integration tests**: Real k8s cluster, controller/webhook tests\n"
        "   - **E2E tests**: Full workflow, actual build execution\n\n"
        "4. **Test Summary**: Provide statistics on:\n"
        "   - Number of tests by type\n"
        "   - Coverage percentage of acceptance criteria\n"
        "   - Pattern coverage\n"
        "   - Recommendations for additional testing\n\n"
        "**Important Guidelines:**\n"
        "- Use Ginkgo v2 syntax (not v1)\n"
        "- Include proper imports (see GINKGO_IMPORTS in config)\n"
        "- Use Shipwright test helpers (libfactory, libk8s)\n"
        "- Apply Data-Driven Testing (DescribeTable) where appropriate\n"
        "- Include test IDs in format [test_id:BUILD-123]\n"
        "- Add BeforeEach/AfterEach for setup/cleanup\n"
        "- Use Eventually/Consistently with timeouts for async checks\n"
        "- Generate actual working Go code that compiles\n\n"
        "**Output Structure:**\n"
        "Please structure your output with clear section headers:\n"
        "- ## Test Plan\n"
        "- ## Test Specifications\n"
        "- ## Unit Tests\n"
        "- ## Integration Tests\n"
        "- ## E2E Tests\n"
        "- ## Test Summary\n"
    )

    return "".join(prompt_parts)


def _parse_test_output(test_output: str) -> Dict[str, Any]:
    """Parse structured information from the test generation output.

    Extracts test plans, specifications, and code from the LLM output.

    Args:
        test_output: The complete test generation output in Markdown format

    Returns:
        Dictionary with extracted structured data
    """
    result = {
        "test_plan": "",
        "test_specifications": {},
        "unit_tests": {},
        "integration_tests": {},
        "e2e_tests": {},
        "test_summary": "",
        "coverage_analysis": "",
    }

    sections = _split_into_sections(test_output)

    # Extract test plan
    if "test plan" in sections:
        result["test_plan"] = sections["test plan"]

    # Extract test specifications (try to parse as YAML)
    if "test specifications" in sections:
        spec_content = sections["test specifications"]
        try:
            # Try to extract YAML code blocks
            yaml_content = _extract_code_block(spec_content, "yaml")
            if yaml_content:
                result["test_specifications"] = yaml.safe_load(yaml_content)
            else:
                result["test_specifications"] = {"raw": spec_content}
        except yaml.YAMLError:
            result["test_specifications"] = {"raw": spec_content}

    # Extract test code sections
    result["unit_tests"] = _extract_test_code(sections.get("unit tests", ""))
    result["integration_tests"] = _extract_test_code(
        sections.get("integration tests", "")
    )
    result["e2e_tests"] = _extract_test_code(sections.get("e2e tests", ""))

    # Extract test summary
    if "test summary" in sections:
        result["test_summary"] = sections["test summary"]

    # Extract coverage analysis (might be in summary or separate)
    if "coverage" in test_output.lower():
        # Extract coverage information from various sections
        coverage_lines = []
        for line in test_output.split("\n"):
            if "coverage" in line.lower() or "%" in line:
                coverage_lines.append(line)
        result["coverage_analysis"] = "\n".join(coverage_lines)

    return result


def _split_into_sections(text: str) -> Dict[str, str]:
    """Split the output text into sections based on headers.

    Args:
        text: The text to split

    Returns:
        Dictionary mapping section names to content
    """
    sections = {}
    current_section = None
    current_content = []

    for line in text.split("\n"):
        # Check for section headers (## Header)
        if line.strip().startswith("##"):
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content)

            # Start new section
            current_section = line.strip("# ").lower().strip()
            current_content = []
        else:
            if current_section:
                current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content)

    return sections


def _extract_code_block(text: str, language: Optional[str] = None) -> str:
    """Extract code from markdown code blocks.

    Args:
        text: Text containing code blocks
        language: Optional language filter (go, yaml, etc.)

    Returns:
        Extracted code or empty string
    """
    in_code_block = False
    code_lines = []
    current_language = None

    for line in text.split("\n"):
        if line.strip().startswith("```"):
            if in_code_block:
                # End of code block
                if language is None or current_language == language:
                    break
                code_lines = []  # Reset if language doesn't match
                in_code_block = False
            else:
                # Start of code block
                in_code_block = True
                current_language = line.strip("`").strip() or None
                code_lines = []
        elif in_code_block:
            code_lines.append(line)

    return "\n".join(code_lines)


def _extract_test_code(section_text: str) -> Dict[str, str]:
    """Extract test code from a section.

    Args:
        section_text: Section text containing test code

    Returns:
        Dictionary mapping file names to code content
    """
    tests = {}

    # Look for multiple code blocks with file path indicators
    lines = section_text.split("\n")
    current_file = None
    current_code = []
    in_code_block = False

    for line in lines:
        # Check for file path indicators
        if "file:" in line.lower() or "_test.go" in line:
            # Extract file path
            if "_test.go" in line:
                # Try to extract the file path
                parts = line.split("_test.go")
                if parts:
                    potential_path = parts[0].strip().strip("`").strip("*").strip()
                    if potential_path:
                        current_file = potential_path + "_test.go"

        # Handle code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                # End of code block - save it
                if current_file:
                    tests[current_file] = "\n".join(current_code)
                else:
                    # Generate a default file name
                    tests[f"generated_test_{len(tests)+1}.go"] = "\n".join(
                        current_code
                    )
                current_code = []
                in_code_block = False
            else:
                # Start of code block
                in_code_block = True
                current_code = []
        elif in_code_block:
            current_code.append(line)

    # Save any remaining code
    if current_code:
        if current_file:
            tests[current_file] = "\n".join(current_code)
        else:
            tests[f"generated_test_{len(tests)+1}.go"] = "\n".join(current_code)

    # If no specific files found, extract the first Go code block
    if not tests:
        go_code = _extract_code_block(section_text, "go")
        if go_code:
            tests["generated_test.go"] = go_code

    return tests


def generate_test_summary(test_results: Dict[str, Any]) -> str:
    """Generate a summary of test generation results.

    Args:
        test_results: Results from run_testing

    Returns:
        Formatted summary string
    """
    summary_lines = [
        "# Test Generation Summary\n",
        f"\n## Tests Generated\n",
    ]

    # Count tests
    unit_count = len(test_results.get("unit_tests", {}))
    integration_count = len(test_results.get("integration_tests", {}))
    e2e_count = len(test_results.get("e2e_tests", {}))
    total_count = unit_count + integration_count + e2e_count

    summary_lines.append(f"- **Unit Tests:** {unit_count} file(s)\n")
    summary_lines.append(f"- **Integration Tests:** {integration_count} file(s)\n")
    summary_lines.append(f"- **E2E Tests:** {e2e_count} file(s)\n")
    summary_lines.append(f"- **Total:** {total_count} test file(s)\n")

    # Add patterns detected
    patterns = test_results.get("patterns_detected", {})
    if patterns:
        summary_lines.append(f"\n## Patterns Detected\n")
        if patterns.get("strategies"):
            summary_lines.append(
                f"- **Strategies:** {', '.join(patterns['strategies'])}\n"
            )
        if patterns.get("source_types"):
            summary_lines.append(
                f"- **Source Types:** {', '.join(patterns['source_types'])}\n"
            )
        if patterns.get("output_types"):
            summary_lines.append(
                f"- **Output Types:** {', '.join(patterns['output_types'])}\n"
            )

    # Add coverage if available
    if test_results.get("coverage_analysis"):
        summary_lines.append(f"\n## Coverage Analysis\n")
        summary_lines.append(f"{test_results['coverage_analysis']}\n")

    return "".join(summary_lines)
