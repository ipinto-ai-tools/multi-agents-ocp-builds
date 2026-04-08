"""Tests for orchestrator.workflow.WorkflowOrchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from orchestrator.workflow import WorkflowOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def orchestrator(tmp_path: Path) -> WorkflowOrchestrator:
    """Return a WorkflowOrchestrator with manual approval disabled."""
    return WorkflowOrchestrator(
        session_id="test-session",
        repo_path="/tmp/fake-repo",
        output_dir=tmp_path,
    )


def _design_result() -> dict:
    return {
        "design_analysis": "A" * 100,
        "impacted_components": ["comp-a"],
        "risks": ["risk-a"],
        "acceptance_criteria": ["ac-1"],
        "implementation_plan": ["step-1", "step-2"],
    }


def _develop_result() -> dict:
    return {
        "code_files": [{"path": "main.go", "content": "package main"}],
        "test_files": [],
        "code_changes": {},
        "files_modified": ["main.go"],
        "pr_description": "Added main.go with core logic.",
    }


def _review_pass_result() -> dict:
    return {
        "review_passed": True,
        "review_findings": [],
        "review_summary": "All good",
        "review_iteration": 1,
    }


def _review_fail_result(iteration: int = 1) -> dict:
    return {
        "review_passed": False,
        "review_findings": ["[BLOCKING] issue found"],
        "review_summary": "1 blocking issue",
        "review_iteration": iteration,
    }


def _testing_result() -> dict:
    return {
        "test_plan": "A" * 50,
        "test_specifications": {},
        "unit_tests": {"main_test.go": "package main"},
        "integration_tests": {},
        "e2e_tests": {},
        "test_summary": "All tests pass",
        "coverage_analysis": "80%",
    }


def _docs_result() -> dict:
    return {
        "pr_summary": "A" * 50,
        "release_notes": "Release v1.0",
        "docs_changes": {},
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DESIGN_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_design"
_DEVELOP_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_develop"
_REVIEW_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_code_review"
_TESTING_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_testing"
_DOCS_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_docs"
_HEARTBEAT_PATCH = "orchestrator.workflow.WorkflowOrchestrator._emit_heartbeat"
_VALIDATE_PATCH = "orchestrator.workflow.WorkflowOrchestrator._validate"


def _run_kwargs() -> dict:
    return {"title": "Test feature", "description": "A test description"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSequentialExecution:
    """Full pipeline runs all stages in order when everything succeeds."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_all_stages_run_sequentially(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        mock_design.assert_called_once()
        # develop called once (no retry needed)
        mock_develop.assert_called_once()
        mock_review.assert_called_once()
        mock_testing.assert_called_once()
        mock_docs.assert_called_once()


class TestReviewAutoFixRetry:
    """Code review failure triggers develop -> review retry loop."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_review_fail_then_pass(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        # First review fails, second passes
        mock_review.side_effect = [_review_fail_result(1), _review_pass_result()]
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        # develop: 1 initial + 1 retry = 2
        assert mock_develop.call_count == 2
        assert mock_review.call_count == 2


class TestMaxReviewIterations:
    """When max review iterations is reached, pipeline proceeds to testing."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_max_iterations_reached(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        # All reviews fail
        mock_review.return_value = _review_fail_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        with patch.dict("os.environ", {"MAX_REVIEW_ITERATIONS": "2"}):
            state = orchestrator.run(**_run_kwargs())

        # Pipeline continues to docs (done) even though review never passed
        assert state["current_phase"] == "done"
        # develop: 1 initial + 1 retry = 2
        assert mock_develop.call_count == 2
        # review called twice (max iterations = 2)
        assert mock_review.call_count == 2
        mock_testing.assert_called_once()


class TestStageFailure:
    """A stage exception stops the workflow with current_phase='error'."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DESIGN_PATCH, side_effect=RuntimeError("boom"))
    def test_design_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        state = orchestrator.run(**_run_kwargs())
        assert state["current_phase"] == "error"
        assert "Design stage failed" in state["error"]

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DEVELOP_PATCH, side_effect=RuntimeError("dev crash"))
    @patch(_DESIGN_PATCH)
    def test_develop_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        state = orchestrator.run(**_run_kwargs())
        assert state["current_phase"] == "error"
        assert "Development stage failed" in state["error"]

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_TESTING_PATCH, side_effect=RuntimeError("test crash"))
    @patch(_REVIEW_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_testing_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review: MagicMock,
        mock_testing: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review.return_value = _review_pass_result()
        state = orchestrator.run(**_run_kwargs())
        assert state["current_phase"] == "error"
        assert "Testing stage failed" in state["error"]


class TestValidationFailure:
    """Validation failure between stages stops the workflow."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_DESIGN_PATCH)
    def test_design_validation_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()

        with patch(_VALIDATE_PATCH, side_effect=lambda self, phase, state: phase != "design"):
            # Re-bind since we need the method mock to work correctly
            pass

        # Simpler approach: patch _validate to return False for design
        with patch.object(orchestrator, "_validate", return_value=False):
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        assert "Design validation failed" in state["error"]

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_DESIGN_PATCH)
    @patch(_DEVELOP_PATCH)
    def test_develop_validation_failure_stops_workflow(
        self,
        mock_develop: MagicMock,
        mock_design: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()

        def selective_validate(phase: str, state: dict) -> bool:
            return phase != "develop"

        with patch.object(orchestrator, "_validate", side_effect=selective_validate):
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        assert "Development validation failed" in state["error"]

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_testing_validation_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        def selective_validate(phase: str, state: dict) -> bool:
            return phase != "testing"

        with patch.object(orchestrator, "_validate", side_effect=selective_validate):
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        assert "Testing validation failed" in state["error"]


class TestHeartbeatEmission:
    """Heartbeat is emitted after each stage."""

    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_heartbeat_emitted_for_each_stage(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        with patch.object(orchestrator, "_emit_heartbeat", return_value=True) as mock_hb:
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"

        # Collect agent names from heartbeat calls
        agents_called = [c.args[0] for c in mock_hb.call_args_list]
        assert "orchestrator" in agents_called
        assert "design" in agents_called
        assert "develop" in agents_called
        assert "code_review" in agents_called
        assert "testing" in agents_called
        assert "docs" in agents_called

    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DESIGN_PATCH, side_effect=RuntimeError("fail"))
    def test_heartbeat_emitted_on_error(
        self,
        mock_design: MagicMock,
        mock_validate: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        with patch.object(orchestrator, "_emit_heartbeat", return_value=True) as mock_hb:
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        # At least orchestrator init + design error heartbeats
        agents_called = [c.args[0] for c in mock_hb.call_args_list]
        assert "orchestrator" in agents_called
        assert "design" in agents_called


class TestCodeReviewRetryDevelopFailure:
    """Development retry failure during code review loop stops workflow."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_REVIEW_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_develop_retry_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        # First develop succeeds, retry fails
        mock_develop.side_effect = [_develop_result(), RuntimeError("retry crash")]
        mock_review.return_value = _review_fail_result()

        with patch.dict("os.environ", {"MAX_REVIEW_ITERATIONS": "2"}):
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        assert "Development retry stage failed" in state["error"]
