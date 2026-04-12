"""Thin sequential stage runner replacing the LangGraph StateGraph orchestrator.

Executes the pipeline: Design -> Develop (with review gate) -> Testing -> Docs.
Each stage merges its result into shared state, emits a heartbeat, and validates output
before proceeding to the next stage.

Code Review is not a standalone stage; it runs as a quality gate after
Develop via :func:`orchestrator.gates.run_review_gate`.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# Maximum code-review retry iterations (develop -> review loop).
_DEFAULT_MAX_REVIEW_ITERATIONS = 2

_SIGNAL_DIR = Path("/tmp/claude/signals")
_PAUSE_POLL_INTERVAL = 2  # seconds
_MAX_PAUSE_SECONDS = int(os.getenv("MAX_PAUSE_SECONDS", "3600"))


def _get_max_review_iterations() -> int:
    """Return the configured maximum review iterations."""
    return int(os.getenv("MAX_REVIEW_ITERATIONS", str(_DEFAULT_MAX_REVIEW_ITERATIONS)))


def _prompt_approval(phase: str, next_phase: str) -> bool:
    """Prompt the user for manual approval between stages.

    Args:
        phase: Name of the just-completed phase.
        next_phase: Name of the upcoming phase.

    Returns:
        True if the user approves (or presses Enter), False otherwise.
    """
    print(f"\n  Completed: {phase.upper()}")
    print(f"  Next phase: {next_phase.upper()}")
    try:
        response = input(f"\n  Continue to {next_phase}? [Y/n]: ").strip().lower()
        return response not in ("n", "no")
    except (EOFError, KeyboardInterrupt):
        print("\n  Interrupted.")
        return False


class WorkflowOrchestrator:
    """Sequential stage runner for the multi-agent pipeline.

    Args:
        session_id: Unique session identifier for dashboard tracking.
        repo_path: Optional path to the repository for code analysis.
        output_dir: Optional directory for saving test artifacts.
    """

    def __init__(
        self,
        session_id: str,
        repo_path: Optional[str] = None,
        repo_paths: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.session_id = session_id
        self.repo_paths = repo_paths or ([repo_path] if repo_path else [])
        self.repo_path = repo_path or (self.repo_paths[0] if self.repo_paths else None)
        self.output_dir = output_dir
        self._manual_approval = os.getenv("MANUAL_APPROVAL", "false").lower() == "true"
        self._repo_config = self._load_repo_config()
        self._repo_commands = self._extract_repo_commands()
        self._active_stages = self._repo_config.stages

    def _load_repo_config(self) -> "RepoConfig":  # noqa: F821
        """Load the full RepoConfig from repos.yaml.

        Returns an empty ``RepoConfig()`` when the file is missing or invalid,
        preserving backward-compatible defaults (all stages, no approvals).
        """
        from config.repo_config import load_repo_config
        from config.repo_schema import RepoConfig

        project_root = Path(__file__).resolve().parent.parent
        yaml_path = project_root / "repos.yaml"
        if not yaml_path.exists():
            return RepoConfig()
        try:
            return load_repo_config(yaml_path)
        except Exception as e:
            from utils.file_logger import get_logger
            get_logger(__name__).warning("Failed to load repo config: %s", e)
            return RepoConfig()

    def _extract_repo_commands(self) -> Optional[Dict[str, str]]:
        """Extract commands for the configured repo_path from the loaded config."""
        if not self.repo_path:
            return None
        for repo in self._repo_config.repos:
            if repo.path == self.repo_path:
                return repo.commands.model_dump(exclude_none=True)
        return None

    # -- internal helpers -----------------------------------------------------

    def _emit_heartbeat(self, agent: str, state: Dict[str, Any]) -> bool:
        """Emit a heartbeat to the dashboard.  Non-blocking on failure."""
        try:
            from dashboard.heartbeat import emit_heartbeat
            return emit_heartbeat(agent, state)
        except Exception:
            return False

    def _validate(self, phase: str, state: Dict[str, Any]) -> bool:
        """Run the phase validator.  Returns True when validation passes."""
        from stages.validators import validate_phase
        result = validate_phase(phase, state)
        return result.passed

    def _should_run_stage(self, stage: str) -> bool:
        """Check if a stage should run based on repos.yaml configuration."""
        return stage in self._active_stages

    def _check_pause_signal(self, state: Dict[str, Any]) -> None:
        """Check for pause signal and block until resumed or timeout."""
        pause_file = _SIGNAL_DIR / f"pause-{self.session_id}"
        if not pause_file.exists():
            return

        previous_phase = state.get("current_phase", "init")
        state["current_phase"] = "paused"
        state["paused_at_phase"] = previous_phase
        self._emit_heartbeat("orchestrator", state)

        elapsed = 0
        while pause_file.exists():
            if elapsed >= _MAX_PAUSE_SECONDS:
                state["current_phase"] = "error"
                state["error"] = f"Pause timeout after {_MAX_PAUSE_SECONDS}s"
                self._emit_heartbeat("orchestrator", state)
                pause_file.unlink(missing_ok=True)
                return
            time.sleep(_PAUSE_POLL_INTERVAL)
            elapsed += _PAUSE_POLL_INTERVAL

        # Resumed — restore previous phase
        state["current_phase"] = previous_phase
        del state["paused_at_phase"]
        self._emit_heartbeat("orchestrator", state)

    def _check_approval(self, phase: str, next_phase: str) -> bool:
        """Check if approval is needed based on repos.yaml or env var.

        Approval is required when:
        - ``approvals.auto_approve`` is ``False`` **and** the phase appears
          in ``approvals.required_stages``, or
        - The ``MANUAL_APPROVAL`` env var is set to ``true`` (backward compat).

        Returns:
            ``True`` if the user approves (or no approval needed),
            ``False`` if the user declines.
        """
        approvals = self._repo_config.approvals

        # auto_approve overrides everything
        if approvals.auto_approve:
            return True

        # Check if this phase requires approval (from repos.yaml)
        needs_approval = phase in approvals.required_stages

        # Also check env var for backward compatibility
        if self._manual_approval:
            needs_approval = True

        if needs_approval:
            return _prompt_approval(phase, next_phase)
        return True

    # -- stage runners (deferred imports to avoid circular deps) ---------------

    def _run_design(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from stages.design import run_design
        return run_design(
            title=state["issue_title"],
            description=state["issue_description"],
            repo_path=state.get("repo_path"),
            repo_paths=state.get("repo_paths", []),
        )

    def _run_develop(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from stages.develop import run_development
        return run_development(
            state,
            repo_path=state.get("repo_path"),
            repo_paths=state.get("repo_paths", []),
        )

    def _run_develop_with_review_gate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run development followed by the review quality gate.

        Implements the develop + review-gate loop:
        1. Run development stage
        2. Run review gate
        3. If review fails and iterations remain, re-run develop with findings
        4. After review passes, run post-develop command gates (build/lint)
        5. Return combined state updates

        Args:
            state: Current workflow state (mutated in-place).

        Returns:
            The mutated *state* dict.  On error ``state["current_phase"]``
            is set to ``"error"``.
        """
        from orchestrator.gates import run_post_develop_gates, run_review_gate

        # --- initial development run ---
        try:
            result = self._run_develop(state)
            state.update(result)
            state["current_phase"] = "develop_complete"
            self._emit_heartbeat("develop", state)
        except Exception as e:
            state["current_phase"] = "error"
            state["error"] = f"Development stage failed: {e}"
            self._emit_heartbeat("develop", state)
            return state

        if not self._validate("develop", state):
            state["current_phase"] = "error"
            state["error"] = "Development validation failed"
            self._emit_heartbeat("develop", state)
            return state

        # --- review gate with retry loop ---
        max_iterations = _get_max_review_iterations()
        review_iteration = 0

        while review_iteration < max_iterations:
            review_iteration += 1

            try:
                result = run_review_gate(state)
                state.update(result)
                state["current_phase"] = "review_complete"
                self._emit_heartbeat("review_gate", state)
            except Exception as e:
                state["current_phase"] = "error"
                state["error"] = f"Review gate failed: {e}"
                self._emit_heartbeat("review_gate", state)
                return state

            self._validate("code_review", state)

            if state.get("review_passed", True):
                break

            # Review failed -- re-run development with findings if iterations remain
            if review_iteration < max_iterations:
                try:
                    result = self._run_develop(state)
                    state.update(result)
                    state["current_phase"] = "develop_complete"
                    self._emit_heartbeat("develop", state)
                except Exception as e:
                    state["current_phase"] = "error"
                    state["error"] = f"Development retry stage failed: {e}"
                    self._emit_heartbeat("develop", state)
                    return state

                self._validate("develop", state)

        # --- post-develop command gates (build / lint) ---
        gate_results = run_post_develop_gates(self.repo_path, self._repo_commands)
        state["develop_gate_results"] = [
            {"gate": g.gate_name, "passed": g.passed, "output": g.output, "error": g.error}
            for g in gate_results
        ]

        return state

    def _run_testing(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from stages.test import run_testing
        return run_testing(state, output_dir=self.output_dir)

    def _run_docs(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from stages.docs import run_docs
        return run_docs(state)

    # -- main entry point -----------------------------------------------------

    def run(
        self,
        title: str,
        description: str,
        issue_type: str = "feature",
        extra_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the full sequential pipeline.

        Args:
            title: Issue / feature title.
            description: Issue / feature description.
            issue_type: One of ``"feature"``, ``"bug"``, ``"refactor"``.
            extra_state: Optional additional fields to merge into the
                initial pipeline state (e.g. Jira enrichment data).

        Returns:
            Final accumulated state dict.  ``current_phase`` will be
            ``"done"`` on success, ``"error"`` on failure.
        """
        state: Dict[str, Any] = {
            "session_id": self.session_id,
            "issue_title": title,
            "issue_description": description,
            "issue_type": issue_type,
            "repo_path": self.repo_paths[0] if self.repo_paths else "",
            "repo_paths": self.repo_paths,
            "current_phase": "init",
        }

        if extra_state:
            _protected = {"session_id", "issue_title", "issue_description",
                          "issue_type", "repo_path", "current_phase"}
            state.update({k: v for k, v in extra_state.items()
                          if k not in _protected})

        self._emit_heartbeat("orchestrator", state)

        # -- Stage 1: Design --------------------------------------------------
        if self._should_run_stage("design"):
            try:
                result = self._run_design(state)
                state.update(result)
                state["current_phase"] = "design_complete"
                self._emit_heartbeat("design", state)
            except Exception as e:
                state["current_phase"] = "error"
                state["error"] = f"Design stage failed: {e}"
                self._emit_heartbeat("design", state)
                return state

            if not self._validate("design", state):
                state["current_phase"] = "error"
                state["error"] = "Design validation failed"
                self._emit_heartbeat("design", state)
                return state

            self._check_pause_signal(state)
            if not self._check_approval("design", "develop"):
                return state
        else:
            self._emit_heartbeat("design", {**state, "skipped": True})

        # -- Stage 2: Development (with review gate) ----------------------------
        if self._should_run_stage("develop"):
            # _run_develop_with_review_gate mutates *state* in-place.
            self._run_develop_with_review_gate(state)
            if state.get("current_phase") == "error":
                return state

            self._check_pause_signal(state)
            if not self._check_approval("develop", "testing"):
                return state
        else:
            self._emit_heartbeat("develop", {**state, "skipped": True})

        # -- Stage 3: Testing --------------------------------------------------
        if self._should_run_stage("testing"):
            try:
                result = self._run_testing(state)
                state.update(result)
                state["current_phase"] = "testing_complete"
                self._emit_heartbeat("testing", state)
            except Exception as e:
                state["current_phase"] = "error"
                state["error"] = f"Testing stage failed: {e}"
                self._emit_heartbeat("testing", state)
                return state

            if not self._validate("testing", state):
                state["current_phase"] = "error"
                state["error"] = "Testing validation failed"
                self._emit_heartbeat("testing", state)
                return state

            # -- Post-test command gates (test) --------------------------------
            from orchestrator.gates import run_post_test_gates

            test_gate_results = run_post_test_gates(self.repo_path, self._repo_commands)
            state["test_gate_results"] = [
                {"gate": g.gate_name, "passed": g.passed, "output": g.output, "error": g.error}
                for g in test_gate_results
            ]

            self._check_pause_signal(state)
            if not self._check_approval("testing", "docs"):
                return state
        else:
            self._emit_heartbeat("testing", {**state, "skipped": True})

        # -- Stage 4: Documentation --------------------------------------------
        if self._should_run_stage("docs"):
            try:
                result = self._run_docs(state)
                state.update(result)
                state["current_phase"] = "done"
                self._emit_heartbeat("docs", state)
            except Exception as e:
                state["current_phase"] = "error"
                state["error"] = f"Docs stage failed: {e}"
                self._emit_heartbeat("docs", state)
                return state

            if not self._validate("docs", state):
                state["current_phase"] = "error"
                state["error"] = "Docs validation failed"
                self._emit_heartbeat("docs", state)
                return state
        else:
            self._emit_heartbeat("docs", {**state, "skipped": True})

        # If we haven't reached "done" via the docs stage (e.g. docs was skipped),
        # mark the workflow as complete now.
        if state["current_phase"] != "done":
            state["current_phase"] = "done"

        return state
