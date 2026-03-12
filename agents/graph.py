"""LangGraph orchestrator for multi-agent workflow.

This module implements the main orchestration workflow using LangGraph to coordinate
the Design, Development, Testing, and Documentation agents in a stateful workflow.

Workflow phases:
1. Design: Analyze requirements and create implementation plan
2. Development: Generate production-quality Go code
3. Testing: Generate Ginkgo v2 test suite
4. Documentation: Create PR summaries and release notes
"""

from typing import Any, Dict, Literal
import uuid

from langgraph.graph import StateGraph, END
from graph.state import AgentState
from agents.design_agent import run_design
from agents.go_k8s_developer import run_development
from agents.testing_agent import run_testing
from agents.docs_agent import run_docs
from dashboard.heartbeat import emit_heartbeat


def design_node(state: AgentState) -> Dict[str, Any]:
    """Execute the Design Agent phase.

    Args:
        state: Current agent state

    Returns:
        Updated state with design analysis outputs
    """
    try:
        # Run design agent
        design_output = run_design(
            title=state["issue_title"],
            description=state["issue_description"],
            repo_path=state.get("repo_path"),
        )

        # Update state with design outputs
        updated_state = {
            "design_analysis": design_output["design_analysis"],
            "impacted_components": design_output["impacted_components"],
            "risks": design_output["risks"],
            "acceptance_criteria": design_output["acceptance_criteria"],
            "implementation_plan": design_output.get("implementation_plan", []),
            "current_phase": "design_complete",
        }

        # Emit heartbeat to dashboard
        complete_state = {**state, **updated_state}
        emit_heartbeat("design", complete_state)

        return updated_state
    except Exception as e:
        error_state = {
            "design_analysis": f"Error in design phase: {str(e)}",
            "current_phase": "error",
        }

        # Emit error heartbeat
        complete_state = {**state, **error_state}
        emit_heartbeat("design", complete_state)

        return error_state


def develop_node(state: AgentState) -> Dict[str, Any]:
    """Execute the Development Agent phase.

    Takes implementation plan from Design Agent and generates:
    - Production-quality Go code
    - Unit tests with table-driven patterns
    - PR description with security notes

    Args:
        state: Current agent state with design outputs

    Returns:
        Updated state with development outputs
    """
    try:
        # Run development agent
        development_output = run_development(state)

        # Update state with development outputs
        updated_state = {
            "code_files": development_output.get("code_files", []),
            "test_files": development_output.get("test_files", []),
            "code_changes": development_output.get("code_changes", {}),
            "files_modified": development_output.get("files_modified", []),
            "pr_description": development_output.get("pr_description", ""),
            "current_phase": "develop_complete",
        }

        # Emit heartbeat to dashboard
        complete_state = {**state, **updated_state}
        emit_heartbeat("develop", complete_state)

        return updated_state
    except Exception as e:
        error_state = {
            "code_files": [],
            "current_phase": "error",
            "error": f"Error in development phase: {str(e)}",
        }

        # Emit error heartbeat
        complete_state = {**state, **error_state}
        emit_heartbeat("develop", complete_state)

        return error_state


def testing_node(state: AgentState) -> Dict[str, Any]:
    """Execute the Testing Agent phase.

    Args:
        state: Current agent state with design outputs

    Returns:
        Updated state with testing outputs
    """
    try:
        # Prepare context for testing agent
        context = {
            "design_analysis": state.get("design_analysis", ""),
            "impacted_components": state.get("impacted_components", []),
            "acceptance_criteria": state.get("acceptance_criteria", []),
            "risks": state.get("risks", []),
            "implementation_plan": state.get("implementation_plan", ""),
            "issue_title": state.get("issue_title", ""),
            "issue_description": state.get("issue_description", ""),
            "issue_type": state.get("issue_type", "feature"),
        }

        # Run testing agent
        testing_output = run_testing(context)

        # Update state with testing outputs
        updated_state = {
            "test_plan": testing_output["test_plan"],
            "test_specifications": testing_output["test_specifications"],
            "unit_tests": testing_output["unit_tests"],
            "integration_tests": testing_output["integration_tests"],
            "e2e_tests": testing_output["e2e_tests"],
            "test_summary": testing_output["test_summary"],
            "coverage_analysis": testing_output["coverage_analysis"],
            "current_phase": "testing_complete",
        }

        # Emit heartbeat to dashboard
        complete_state = {**state, **updated_state}
        emit_heartbeat("testing", complete_state)

        return updated_state
    except Exception as e:
        error_state = {
            "test_plan": f"Error in testing phase: {str(e)}",
            "current_phase": "error",
        }

        # Emit error heartbeat
        complete_state = {**state, **error_state}
        emit_heartbeat("testing", complete_state)

        return error_state


def docs_node(state: AgentState) -> Dict[str, Any]:
    """Execute the Documentation Agent phase.

    Args:
        state: Current agent state with design, dev, and test outputs

    Returns:
        Updated state with documentation outputs
    """
    try:
        # Prepare context for docs agent (includes repo_path for RAG)
        context = {
            "design_analysis": state.get("design_analysis", ""),
            "implementation_plan": state.get("implementation_plan", ""),
            "impacted_components": state.get("impacted_components", []),
            "risks": state.get("risks", []),
            "acceptance_criteria": state.get("acceptance_criteria", []),
            "code_changes": state.get("code_changes", {}),
            "files_modified": state.get("files_modified", []),
            "test_results": state.get("test_results", {}),
            "test_summary": state.get("test_summary", ""),
            "coverage_gaps": state.get("coverage_gaps", []),
            "test_failures": state.get("test_failures", []),
            "test_plan": state.get("test_plan", ""),
            "test_specifications": state.get("test_specifications", {}),
            "unit_tests": state.get("unit_tests", {}),
            "integration_tests": state.get("integration_tests", {}),
            "e2e_tests": state.get("e2e_tests", {}),
            "coverage_analysis": state.get("coverage_analysis", ""),
            "issue_title": state.get("issue_title", ""),
            "issue_description": state.get("issue_description", ""),
            "issue_type": state.get("issue_type", "feature"),
            "repo_path": state.get("repo_path", "."),
        }

        # Run docs agent
        docs_output = run_docs(context)

        # Update state with documentation outputs
        updated_state = {
            "pr_summary": docs_output["pr_summary"],
            "release_notes": docs_output["release_notes"],
            "docs_changes": docs_output["docs_changes"],
            "current_phase": "done",
        }

        # Emit heartbeat to dashboard
        complete_state = {**state, **updated_state}
        emit_heartbeat("docs", complete_state)

        return updated_state
    except Exception as e:
        error_state = {
            "pr_summary": f"Error in docs phase: {str(e)}",
            "current_phase": "error",
        }

        # Emit error heartbeat
        complete_state = {**state, **error_state}
        emit_heartbeat("docs", complete_state)

        return error_state


def should_continue(state: AgentState) -> Literal["develop", "testing", "docs", "end"]:
    """Determine if workflow should continue to next phase.

    Workflow: Design → Development → Testing → Docs

    Args:
        state: Current agent state

    Returns:
        Next node name or END
    """
    phase = state.get("current_phase", "")

    # If design completed successfully, proceed to development
    if phase == "design_complete":
        return "develop"

    # If development completed successfully, proceed to testing
    if phase == "develop_complete":
        return "testing"

    # If testing completed successfully, proceed to docs
    if phase == "testing_complete":
        return "docs"

    # Otherwise, end the workflow
    return "end"


def build_workflow() -> StateGraph:
    """Build the LangGraph workflow.

    Returns:
        Compiled LangGraph workflow
    """
    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("design", design_node)
    workflow.add_node("develop", develop_node)
    workflow.add_node("testing", testing_node)
    workflow.add_node("docs", docs_node)

    # Set entry point
    workflow.set_entry_point("design")

    # Add conditional edges from design
    workflow.add_conditional_edges(
        "design",
        should_continue,
        {
            "develop": "develop",
            "end": END,
        }
    )

    # Add conditional edges from develop
    workflow.add_conditional_edges(
        "develop",
        should_continue,
        {
            "testing": "testing",
            "end": END,
        }
    )

    # Add conditional edges from testing
    workflow.add_conditional_edges(
        "testing",
        should_continue,
        {
            "docs": "docs",
            "end": END,
        }
    )

    # Add edge from docs to END
    workflow.add_edge("docs", END)

    # Compile the graph
    return workflow.compile()


# Create the compiled graph
graph = build_workflow()


def orchestrate(
    title: str,
    description: str,
    repo_path: str = None,
    issue_type: str = "feature",
) -> Dict[str, Any]:
    """Orchestrate the multi-agent workflow.

    This function runs the complete workflow from design analysis through
    documentation generation using LangGraph state management.

    Args:
        title: GitHub issue title
        description: GitHub issue description
        repo_path: Optional path to the repository for code analysis
        issue_type: Type of issue (bug, feature, refactor, docs)

    Returns:
        Final state containing all agent outputs

    Example:
        >>> result = orchestrate(
        ...     title="Add timeout support",
        ...     description="Users need build timeout configuration",
        ...     repo_path="/path/to/repo"
        ... )
        >>> print(result["design_analysis"])
        >>> print(result["pr_summary"])
    """
    # Generate session ID for dashboard tracking
    session_id = str(uuid.uuid4())

    # Initialize state
    initial_state = {
        "session_id": session_id,
        "issue_title": title,
        "issue_description": description,
        "issue_type": issue_type,
        "repo_path": repo_path or "",
        "target_branch": "main",
        "current_phase": "init",
        "approval_status": "pending",
        "messages": [],
        # Initialize optional fields
        "design_analysis": "",
        "impacted_components": [],
        "risks": [],
        "acceptance_criteria": [],
        "implementation_plan": "",
        "test_plan": "",
        "test_specifications": {},
        "unit_tests": {},
        "integration_tests": {},
        "e2e_tests": {},
        "coverage_analysis": "",
        "code_files": [],
        "test_files": [],
        "code_changes": {},
        "files_modified": [],
        "pr_description": "",
        "test_results": {},
        "test_summary": "",
        "coverage_gaps": [],
        "test_failures": [],
        "pr_summary": "",
        "release_notes": "",
        "docs_changes": {},
    }

    # Emit initial heartbeat
    emit_heartbeat("orchestrator", initial_state)

    # Run the workflow
    final_state = graph.invoke(initial_state)

    return final_state
