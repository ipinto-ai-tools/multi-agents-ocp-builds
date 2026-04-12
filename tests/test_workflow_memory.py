"""Integration tests for memory in the WorkflowOrchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.workflow import WorkflowOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def orchestrator(tmp_path: Path) -> WorkflowOrchestrator:
    """Return a WorkflowOrchestrator with memory disabled (default)."""
    return WorkflowOrchestrator(
        session_id="test-session",
        repo_path="/tmp/fake-repo",
        output_dir=tmp_path,
    )


# Patch targets
_HEARTBEAT_PATCH = "orchestrator.workflow.WorkflowOrchestrator._emit_heartbeat"
_VALIDATE_PATCH = "orchestrator.workflow.WorkflowOrchestrator._validate"
_DESIGN_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_design"
_DEVELOP_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_develop"
_REVIEW_GATE_PATCH = "orchestrator.gates.run_review_gate"
_TESTING_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_testing"
_DOCS_PATCH = "orchestrator.workflow.WorkflowOrchestrator._run_docs"


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


def _run_kwargs() -> dict:
    return {"title": "Test feature", "description": "A test description"}


# ---------------------------------------------------------------------------
# Tests: MemoryService lifecycle in the orchestrator
# ---------------------------------------------------------------------------

class TestOrchestratorMemoryInit:
    """Memory service initialisation inside WorkflowOrchestrator."""

    def test_orchestrator_no_memory_by_default(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        """Default env has MEMORY_ENABLED unset, so _memory_service is None."""
        assert orchestrator._memory_service is None

    def test_orchestrator_creates_memory_service(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """When MEMORY_ENABLED=true, orchestrator creates a MemoryService."""
        monkeypatch.setenv("MEMORY_ENABLED", "true")
        monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "orch.db"))

        orch = WorkflowOrchestrator(
            session_id="mem-test",
            repo_path="/tmp/fake-repo",
            output_dir=tmp_path,
        )
        assert orch._memory_service is not None
        assert orch._memory_service.enabled is True


# ---------------------------------------------------------------------------
# Tests: Memory context injection into state
# ---------------------------------------------------------------------------

class TestMemoryContextInjection:
    """Memory context is injected before stage calls and removed after."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_memory_context_injected_into_state(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """When memory is enabled, retrieve_for_stage output appears in state
        before _run_design is called, and is cleaned up afterwards."""
        monkeypatch.setenv("MEMORY_ENABLED", "true")
        monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "inject.db"))

        orch = WorkflowOrchestrator(
            session_id="inject-test",
            repo_path="/tmp/fake-repo",
            output_dir=tmp_path,
        )

        memory_text = "## Cross-Session Memory Context\n\n### Best Practices\n- **Tip**: Do X"
        with patch.object(
            orch._memory_service, "retrieve_for_stage", return_value=memory_text
        ) as mock_retrieve:
            # Capture the state dict passed to _run_design
            captured_states: list[dict] = []

            def capture_design(state: dict) -> dict:
                captured_states.append(dict(state))
                return _design_result()

            mock_design.side_effect = capture_design
            mock_develop.return_value = _develop_result()
            mock_review_gate.return_value = _review_pass_result()
            mock_testing.return_value = _testing_result()
            mock_docs.return_value = _docs_result()

            # Also patch store_from_stage so it doesn't error
            with patch.object(orch._memory_service, "store_from_stage", return_value=[]):
                state = orch.run(**_run_kwargs())

            assert state["current_phase"] == "done"
            # retrieve_for_stage should have been called for each stage
            assert mock_retrieve.call_count == 4

            # The state passed to _run_design should have had memory_context
            assert len(captured_states) == 1
            assert captured_states[0]["memory_context"] == memory_text

            # After the run, memory_context should be cleaned up
            assert "memory_context" not in state


# ---------------------------------------------------------------------------
# Tests: Memory stored after each stage
# ---------------------------------------------------------------------------

class TestMemoryStoredAfterStage:
    """store_from_stage is called after each successful stage."""

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DOCS_PATCH)
    @patch(_TESTING_PATCH)
    @patch(_REVIEW_GATE_PATCH)
    @patch(_DEVELOP_PATCH)
    @patch(_DESIGN_PATCH)
    def test_memory_stored_after_stage(
        self,
        mock_design: MagicMock,
        mock_develop: MagicMock,
        mock_review_gate: MagicMock,
        mock_testing: MagicMock,
        mock_docs: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """store_from_stage is called once per stage after successful execution."""
        monkeypatch.setenv("MEMORY_ENABLED", "true")
        monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "store.db"))

        orch = WorkflowOrchestrator(
            session_id="store-test",
            repo_path="/tmp/fake-repo",
            output_dir=tmp_path,
        )

        mock_design.return_value = _design_result()
        mock_develop.return_value = _develop_result()
        mock_review_gate.return_value = _review_pass_result()
        mock_testing.return_value = _testing_result()
        mock_docs.return_value = _docs_result()

        with patch.object(
            orch._memory_service, "retrieve_for_stage", return_value=""
        ), patch.object(
            orch._memory_service, "store_from_stage", return_value=[]
        ) as mock_store:
            state = orch.run(**_run_kwargs())

        assert state["current_phase"] == "done"

        # store_from_stage called for design, develop, testing, docs = 4
        assert mock_store.call_count == 4

        # Verify the stage names passed to store_from_stage
        stage_names = [call.args[0] for call in mock_store.call_args_list]
        assert stage_names == ["design", "develop", "testing", "docs"]

    @patch(_HEARTBEAT_PATCH, return_value=True)
    @patch(_VALIDATE_PATCH, return_value=True)
    @patch(_DESIGN_PATCH, side_effect=RuntimeError("boom"))
    def test_memory_not_stored_on_stage_failure(
        self,
        mock_design: MagicMock,
        mock_validate: MagicMock,
        mock_heartbeat: MagicMock,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """When a stage fails, store_from_stage is NOT called for it."""
        monkeypatch.setenv("MEMORY_ENABLED", "true")
        monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "nofail.db"))

        orch = WorkflowOrchestrator(
            session_id="fail-test",
            repo_path="/tmp/fake-repo",
            output_dir=tmp_path,
        )

        with patch.object(
            orch._memory_service, "retrieve_for_stage", return_value=""
        ), patch.object(
            orch._memory_service, "store_from_stage", return_value=[]
        ) as mock_store:
            state = orch.run(**_run_kwargs())

        assert state["current_phase"] == "error"
        mock_store.assert_not_called()
