"""Tests for orchestrator.workflow.WorkflowOrchestrator."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.repo_schema import ApprovalConfig, RepoConfig
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
_REVIEW_GATE_PATCH = "orchestrator.gates.run_review_gate"
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
    """Full pipeline runs all 4 stages in order when everything succeeds."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_all_stages_run_sequentially(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        mock_design.assert_called_once()
        # develop called once (no retry needed)
        mock_develop.assert_called_once()
        # review gate called once (passed first time)
        mock_review_gate.assert_called_once()
        mock_testing.assert_called_once()
        mock_docs.assert_called_once()


class TestReviewGateRetry:
    """Review gate failure triggers develop -> review retry loop."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_review_fail_then_pass(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        # First review fails, second passes
        mock_review_gate.side_effect = [_review_fail_result(1), _review_pass_result()]
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        # develop: 1 initial + 1 retry = 2
        assert mock_develop.call_count == 2
        assert mock_review_gate.call_count == 2


class TestMaxReviewIterations:
    """When max review iterations is reached, pipeline proceeds to testing."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_max_iterations_reached(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        # All reviews fail
        mock_review_gate.return_value = _review_fail_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        with patch.dict("os.environ", {"MAX_REVIEW_ITERATIONS": "2"}):
            state = orchestrator.run(**_run_kwargs())

        # Pipeline continues to docs (done) even though review never passed
        assert state["current_phase"] == "done"
        # develop: 1 initial + 1 retry = 2
        assert mock_develop.call_count == 2
        # review gate called twice (max iterations = 2)
        assert mock_review_gate.call_count == 2
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
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_testing_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
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
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_testing_validation_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        def selective_validate(phase: str, state: dict) -> bool:
            return phase != "testing"

        with patch.object(orchestrator, "_validate", side_effect=selective_validate):
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        assert "Testing validation failed" in state["error"]


class TestHeartbeatEmission:
    """Heartbeat is emitted after each stage and the review gate."""

    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_heartbeat_emitted_for_each_stage(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
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
        # Review is now a gate, not a standalone stage
        assert "review_gate" in agents_called
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


class TestReviewGateRetryDevelopFailure:
    """Development retry failure during review gate loop stops workflow."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_develop_retry_failure_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        # First develop succeeds, retry fails
        mock_develop.side_effect = [_develop_result(), RuntimeError("retry crash")]
        mock_review_gate.return_value = _review_fail_result()

        with patch.dict("os.environ", {"MAX_REVIEW_ITERATIONS": "2"}):
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        assert "Development retry stage failed" in state["error"]


class TestReviewGateFailure:
    """Review gate exception stops the workflow."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_REVIEW_GATE_PATCH, side_effect=RuntimeError("gate crash"))
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_review_gate_exception_stops_workflow(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        assert "Review gate failed" in state["error"]


class TestStageSkipping:
    """Stages not listed in repos.yaml ``stages`` are skipped."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_DESIGN_PATCH)
    def test_only_design_and_docs_stages(
        self,
        mock_design: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When stages=['design', 'docs'], develop and testing are skipped."""
        orchestrator._active_stages = ["design", "docs"]
        mock_design.return_value = _design_result()
        mock_docs.return_value = _docs_result()

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        mock_design.assert_called_once()
        mock_docs.assert_called_once()

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_skipped_stages_emit_heartbeat(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """Skipped stages still emit a heartbeat with skipped=True."""
        orchestrator._active_stages = ["design", "docs"]
        mock_design.return_value = _design_result()
        mock_docs.return_value = _docs_result()

        orchestrator.run(**_run_kwargs())

        # Collect heartbeat calls: (agent_name, state_dict)
        hb_calls = [(c.args[0], c.args[1]) for c in mock_heartbeat.call_args_list]

        # develop and testing should have heartbeats with skipped=True
        develop_hb = [s for agent, s in hb_calls if agent == "develop"]
        testing_hb = [s for agent, s in hb_calls if agent == "testing"]
        assert len(develop_hb) == 1
        assert develop_hb[0].get("skipped") is True
        assert len(testing_hb) == 1
        assert testing_hb[0].get("skipped") is True

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_skipped_stages_not_called(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """Skipped stage runners must not be called."""
        orchestrator._active_stages = ["design", "docs"]
        mock_design.return_value = _design_result()
        mock_docs.return_value = _docs_result()

        orchestrator.run(**_run_kwargs())

        mock_develop.assert_not_called()
        mock_review_gate.assert_not_called()
        mock_testing.assert_not_called()

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    def test_all_stages_skipped_still_completes(
        self,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When stages=[], the workflow completes with current_phase='done'."""
        orchestrator._active_stages = []

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    def test_only_develop_and_testing(
        self,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When stages=['develop', 'testing'], design and docs are skipped."""
        orchestrator._active_stages = ["develop", "testing"]
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        mock_develop.assert_called_once()
        mock_testing.assert_called_once()


class TestApprovalConfig:
    """Approval behavior driven by repos.yaml approvals config."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_auto_approve_skips_prompt(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When auto_approve=True, no approval prompt is shown even with MANUAL_APPROVAL."""
        orchestrator._repo_config = RepoConfig(
            approvals=ApprovalConfig(auto_approve=True),
        )
        orchestrator._manual_approval = True  # should be overridden by auto_approve

        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        with patch("orchestrator.workflow._prompt_approval") as mock_prompt:
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        mock_prompt.assert_not_called()

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_required_stages_prompts_for_listed_phases(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When required_stages=['design'], only design->develop transition prompts."""
        orchestrator._repo_config = RepoConfig(
            approvals=ApprovalConfig(required_stages=["design"]),
        )
        orchestrator._manual_approval = False

        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        with patch("orchestrator.workflow._prompt_approval", return_value=True) as mock_prompt:
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        # Only design->develop should trigger a prompt
        assert mock_prompt.call_count == 1
        mock_prompt.assert_called_once_with("design", "develop")

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DESIGN_PATCH)
    def test_required_stages_user_declines(
        self,
        mock_design: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When required_stages=['design'] and user declines, workflow stops."""
        orchestrator._repo_config = RepoConfig(
            approvals=ApprovalConfig(required_stages=["design"]),
        )
        orchestrator._manual_approval = False

        mock_design.return_value = _design_result()

        with patch("orchestrator.workflow._prompt_approval", return_value=False):
            state = orchestrator.run(**_run_kwargs())

        # Workflow stops after design since user declined
        assert state["current_phase"] == "design_complete"

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_manual_approval_env_backward_compat(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """MANUAL_APPROVAL env var still triggers prompts (backward compat)."""
        orchestrator._repo_config = RepoConfig(
            approvals=ApprovalConfig(required_stages=[]),
        )
        orchestrator._manual_approval = True

        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        with patch("orchestrator.workflow._prompt_approval", return_value=True) as mock_prompt:
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        # All three inter-stage transitions should prompt
        assert mock_prompt.call_count == 3

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_no_approvals_no_prompt(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """Default config (no required_stages, no env var) never prompts."""
        orchestrator._repo_config = RepoConfig()
        orchestrator._manual_approval = False

        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        with patch("orchestrator.workflow._prompt_approval") as mock_prompt:
            state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        mock_prompt.assert_not_called()


class TestRepoConfigLoading:
    """WorkflowOrchestrator correctly loads and uses RepoConfig."""

    def test_default_active_stages(self, orchestrator: WorkflowOrchestrator) -> None:
        """Without custom config, all four stages are active."""
        assert orchestrator._active_stages == ["design", "develop", "testing", "docs"]

    def test_should_run_stage_respects_active_stages(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        """_should_run_stage returns True only for stages in _active_stages."""
        orchestrator._active_stages = ["design", "docs"]
        assert orchestrator._should_run_stage("design") is True
        assert orchestrator._should_run_stage("develop") is False
        assert orchestrator._should_run_stage("testing") is False
        assert orchestrator._should_run_stage("docs") is True

    def test_repo_config_has_default_approvals(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        """Default RepoConfig has empty required_stages and auto_approve=False."""
        approvals = orchestrator._repo_config.approvals
        assert approvals.required_stages == []
        assert approvals.auto_approve is False


class TestPauseSignal:
    """Pause signal file blocks workflow until removed or timeout."""

    @pytest.fixture(autouse=True)
    def _signal_dir(self, tmp_path: Path) -> None:
        """Redirect _SIGNAL_DIR to a temp directory and clean up after each test."""
        self.signal_dir = tmp_path / "signals"
        self.signal_dir.mkdir()

    @pytest.fixture()
    def paused_orchestrator(self) -> WorkflowOrchestrator:
        """Return a WorkflowOrchestrator using the temp signal directory."""
        orch = WorkflowOrchestrator(
            session_id="pause-test",
            repo_path="/tmp/fake-repo",
        )
        return orch

    def _pause_file(self) -> Path:
        return self.signal_dir / "pause-pause-test"

    @patch(_HEARTBEAT_PATCH, return_value=True)
    def test_no_pause_file_is_noop(
        self,
        mock_heartbeat: MagicMock,
        paused_orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When no pause file exists, the method returns immediately without modifying state."""
        state = {"current_phase": "design_complete", "session_id": "pause-test"}
        original_state = state.copy()

        with patch("orchestrator.workflow._SIGNAL_DIR", self.signal_dir):
            paused_orchestrator._check_pause_signal(state)

        assert state == original_state
        mock_heartbeat.assert_not_called()

    def test_pause_blocks_until_file_removed(
        self,
        paused_orchestrator: WorkflowOrchestrator,
    ) -> None:
        """Pause file blocks execution; heartbeats show 'paused' phase; previous phase restored."""
        pause_file = self._pause_file()
        pause_file.touch()
        state = {"current_phase": "design_complete", "session_id": "pause-test"}

        # Capture snapshots of state at each heartbeat call (state is mutated in place)
        heartbeat_snapshots: list[tuple[str, dict]] = []

        def capture_heartbeat(agent: str, st: dict) -> bool:
            heartbeat_snapshots.append((agent, dict(st)))
            return True

        def remove_after_delay() -> None:
            import time
            time.sleep(0.3)
            pause_file.unlink()

        remover = threading.Thread(target=remove_after_delay)
        remover.start()

        with (
            patch("orchestrator.workflow._SIGNAL_DIR", self.signal_dir),
            patch("orchestrator.workflow._PAUSE_POLL_INTERVAL", 0.1),
            patch.object(paused_orchestrator, "_emit_heartbeat", side_effect=capture_heartbeat),
        ):
            paused_orchestrator._check_pause_signal(state)

        remover.join()

        # Previous phase should be restored after resume
        assert state["current_phase"] == "design_complete"
        assert "paused_at_phase" not in state

        # At least two heartbeats: one for entering paused, one for resuming
        assert len(heartbeat_snapshots) >= 2

        # First heartbeat should show paused phase
        first_agent, first_hb_state = heartbeat_snapshots[0]
        assert first_agent == "orchestrator"
        assert first_hb_state["current_phase"] == "paused"
        assert first_hb_state["paused_at_phase"] == "design_complete"

        # Last heartbeat should show restored phase
        last_agent, last_hb_state = heartbeat_snapshots[-1]
        assert last_agent == "orchestrator"
        assert last_hb_state["current_phase"] == "design_complete"

    @patch(_HEARTBEAT_PATCH, return_value=True)
    def test_pause_preserves_previous_phase(
        self,
        mock_heartbeat: MagicMock,
        paused_orchestrator: WorkflowOrchestrator,
    ) -> None:
        """current_phase is restored to the exact value before pause after file removal."""
        pause_file = self._pause_file()
        pause_file.touch()
        state = {"current_phase": "testing_complete", "session_id": "pause-test"}

        def remove_after_delay() -> None:
            import time
            time.sleep(0.2)
            pause_file.unlink()

        remover = threading.Thread(target=remove_after_delay)
        remover.start()

        with (
            patch("orchestrator.workflow._SIGNAL_DIR", self.signal_dir),
            patch("orchestrator.workflow._PAUSE_POLL_INTERVAL", 0.1),
        ):
            paused_orchestrator._check_pause_signal(state)

        remover.join()

        assert state["current_phase"] == "testing_complete"
        assert "paused_at_phase" not in state

    @patch(_HEARTBEAT_PATCH, return_value=True)
    def test_pause_timeout(
        self,
        mock_heartbeat: MagicMock,
        paused_orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When timeout expires, current_phase becomes 'error' and pause file is removed."""
        pause_file = self._pause_file()
        pause_file.touch()
        state = {"current_phase": "develop_complete", "session_id": "pause-test"}

        with (
            patch("orchestrator.workflow._SIGNAL_DIR", self.signal_dir),
            patch("orchestrator.workflow._MAX_PAUSE_SECONDS", 2),
            patch("orchestrator.workflow._PAUSE_POLL_INTERVAL", 0.1),
        ):
            paused_orchestrator._check_pause_signal(state)

        assert state["current_phase"] == "error"
        assert "Pause timeout" in state["error"]
        # Pause file should be cleaned up on timeout
        assert not pause_file.exists()


class TestSmartStageSkipping:
    """Smart skip logic based on issue_type and code_files content."""

    # -- _should_skip_testing unit tests --------------------------------------

    def test_should_skip_testing_no_code_files(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        """_should_skip_testing returns 'no code files produced' when code_files is empty or missing."""
        # Missing key
        assert orchestrator._should_skip_testing({}) == "no code files produced"
        # Empty list
        assert orchestrator._should_skip_testing({"code_files": []}) == "no code files produced"
        # Explicitly None
        assert orchestrator._should_skip_testing({"code_files": None}) == "no code files produced"

    def test_should_skip_testing_with_code_files(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        """_should_skip_testing returns empty string when code_files has items."""
        state = {"code_files": [{"path": "main.go", "content": "package main"}]}
        assert orchestrator._should_skip_testing(state) == ""

    def test_should_skip_testing_docs_type(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        """_should_skip_testing returns 'docs-only task' when issue_type is 'docs'."""
        state = {"issue_type": "docs", "code_files": [{"path": "f.go", "content": "x"}]}
        assert orchestrator._should_skip_testing(state) == "docs-only task"

    # -- _should_skip_develop unit tests --------------------------------------

    def test_should_skip_develop_docs_type(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        """_should_skip_develop returns 'docs-only task' when issue_type is 'docs'."""
        assert orchestrator._should_skip_develop({"issue_type": "docs"}) == "docs-only task"

    def test_should_skip_develop_feature_type(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        """_should_skip_develop returns empty string for issue_type 'feature'."""
        assert orchestrator._should_skip_develop({"issue_type": "feature"}) == ""

    # -- full pipeline integration tests --------------------------------------

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_run_skips_testing_when_no_code_files(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When develop produces no code_files, testing stage is NOT called."""
        mock_design.return_value = _design_result()
        # Develop returns empty code_files
        develop_result = _develop_result()
        develop_result["code_files"] = []
        mock_develop.return_value = develop_result
        mock_review_gate.return_value = _review_pass_result()
        mock_docs.return_value = _docs_result()

        state = orchestrator.run(**_run_kwargs())

        assert state["current_phase"] == "done"
        mock_design.assert_called_once()
        mock_develop.assert_called_once()
        mock_review_gate.assert_called_once()
        mock_testing.assert_not_called()
        mock_docs.assert_called_once()

        # Verify testing heartbeat was emitted with skipped=True and skip_reason
        hb_calls = [(c.args[0], c.args[1]) for c in mock_heartbeat.call_args_list]
        testing_hb = [s for agent, s in hb_calls if agent == "testing"]
        assert len(testing_hb) == 1
        assert testing_hb[0].get("skipped") is True
        assert testing_hb[0].get("skip_reason") == "no code files produced"

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_run_skips_develop_and_testing_for_docs(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        orchestrator: WorkflowOrchestrator,
    ) -> None:
        """When issue_type='docs', develop and testing are NOT called but design and docs ARE."""
        mock_design.return_value = _design_result()
        mock_docs.return_value = _docs_result()

        state = orchestrator.run(
            title="Update README",
            description="Add installation instructions",
            issue_type="docs",
        )

        assert state["current_phase"] == "done"
        mock_design.assert_called_once()
        mock_develop.assert_not_called()
        mock_review_gate.assert_not_called()
        mock_testing.assert_not_called()
        mock_docs.assert_called_once()

        # Verify both develop and testing heartbeats were emitted with skipped=True
        hb_calls = [(c.args[0], c.args[1]) for c in mock_heartbeat.call_args_list]
        develop_hb = [s for agent, s in hb_calls if agent == "develop"]
        testing_hb = [s for agent, s in hb_calls if agent == "testing"]
        assert len(develop_hb) == 1
        assert develop_hb[0].get("skipped") is True
        assert develop_hb[0].get("skip_reason") == "docs-only task"
        assert len(testing_hb) == 1
        assert testing_hb[0].get("skipped") is True
        assert testing_hb[0].get("skip_reason") == "docs-only task"
