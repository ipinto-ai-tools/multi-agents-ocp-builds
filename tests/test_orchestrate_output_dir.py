"""Tests for _save_artifacts() in scripts/orchestrate.py and the --output-dir CLI arg.

Covers:
  - All artifact categories (design, code, tests, docs, state.json)
  - Edge cases: empty/None fields, path traversal, write errors, partial state
  - CLI argument wiring via orchestrate() mock
"""

import json
import os
import sys
import pathlib
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Make scripts/ importable without installing the package.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = pathlib.Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from orchestrate import _save_artifacts  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _files_under(directory: pathlib.Path) -> set[str]:
    """Return relative POSIX paths of all files under *directory*."""
    return {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}


# ---------------------------------------------------------------------------
# TestSaveArtifacts
# ---------------------------------------------------------------------------


class TestSaveArtifacts:
    """Unit tests for _save_artifacts()."""

    # ------------------------------------------------------------------
    # 1. design_analysis → design/design_analysis.md
    # ------------------------------------------------------------------

    def test_design_analysis_saved(self, tmp_path):
        state = {"design_analysis": "# My Design\n\nSome content.", "current_phase": "design_complete"}
        _save_artifacts(state, str(tmp_path))

        target = tmp_path / "design" / "design_analysis.md"
        assert target.exists(), "design/design_analysis.md should be written"
        assert _read(target) == "# My Design\n\nSome content."

    # ------------------------------------------------------------------
    # 2. implementation_plan list → design/implementation_plan.md with "- " bullets
    # ------------------------------------------------------------------

    def test_implementation_plan_saved_as_bullets(self, tmp_path):
        steps = ["Update API types", "Add webhook validation", "Write tests"]
        state = {"implementation_plan": steps, "current_phase": "design_complete"}
        _save_artifacts(state, str(tmp_path))

        target = tmp_path / "design" / "implementation_plan.md"
        assert target.exists(), "design/implementation_plan.md should be written"
        content = _read(target)
        for step in steps:
            assert f"- {step}" in content

    # ------------------------------------------------------------------
    # 3. code_files preserve sub-directory paths under code/
    # ------------------------------------------------------------------

    def test_code_files_preserve_paths(self, tmp_path):
        state = {
            "code_files": {
                "pkg/webhook/handler.go": "package webhook\n",
            },
            "current_phase": "develop_complete",
        }
        _save_artifacts(state, str(tmp_path))

        target = tmp_path / "code" / "pkg" / "webhook" / "handler.go"
        assert target.exists(), "code/pkg/webhook/handler.go should be written"
        assert _read(target) == "package webhook\n"

    # ------------------------------------------------------------------
    # 4. unit_tests → tests/unit/
    # ------------------------------------------------------------------

    def test_unit_tests_saved(self, tmp_path):
        state = {
            "unit_tests": {
                "buildrun_test.go": "package buildrun_test\n",
                "webhook_test.go": "package webhook_test\n",
            },
            "current_phase": "testing_complete",
        }
        _save_artifacts(state, str(tmp_path))

        assert (tmp_path / "tests" / "unit" / "buildrun_test.go").exists()
        assert (tmp_path / "tests" / "unit" / "webhook_test.go").exists()
        assert _read(tmp_path / "tests" / "unit" / "buildrun_test.go") == "package buildrun_test\n"

    # ------------------------------------------------------------------
    # 5. integration_tests → tests/integration/
    # ------------------------------------------------------------------

    def test_integration_tests_saved(self, tmp_path):
        state = {
            "integration_tests": {
                "e2e_suite_test.go": "package integration_test\n",
            },
            "current_phase": "testing_complete",
        }
        _save_artifacts(state, str(tmp_path))

        target = tmp_path / "tests" / "integration" / "e2e_suite_test.go"
        assert target.exists()
        assert _read(target) == "package integration_test\n"

    # ------------------------------------------------------------------
    # 6. e2e_tests → tests/e2e/
    # ------------------------------------------------------------------

    def test_e2e_tests_saved(self, tmp_path):
        state = {
            "e2e_tests": {
                "smoke_test.go": "package e2e_test\n",
            },
            "current_phase": "testing_complete",
        }
        _save_artifacts(state, str(tmp_path))

        target = tmp_path / "tests" / "e2e" / "smoke_test.go"
        assert target.exists()
        assert _read(target) == "package e2e_test\n"

    # ------------------------------------------------------------------
    # 7. docs artifacts → docs/
    # ------------------------------------------------------------------

    def test_docs_artifacts_saved(self, tmp_path):
        state = {
            "pr_description": "## PR description",
            "pr_summary": "Short summary",
            "release_notes": "## v1.0.0 release notes",
            "current_phase": "done",
        }
        _save_artifacts(state, str(tmp_path))

        assert (tmp_path / "docs" / "pr_description.md").exists()
        assert (tmp_path / "docs" / "pr_summary.md").exists()
        assert (tmp_path / "docs" / "release_notes.md").exists()

        assert _read(tmp_path / "docs" / "pr_description.md") == "## PR description"
        assert _read(tmp_path / "docs" / "pr_summary.md") == "Short summary"
        assert _read(tmp_path / "docs" / "release_notes.md") == "## v1.0.0 release notes"

    # ------------------------------------------------------------------
    # 8. state.json always written with JSON-serializable fields
    # ------------------------------------------------------------------

    def test_state_json_written(self, tmp_path):
        state = {
            "session_id": "abc123",
            "current_phase": "done",
            "issue_title": "Add timeout",
            "non_serializable": object(),  # should be excluded or stringified
        }
        _save_artifacts(state, str(tmp_path))

        state_file = tmp_path / "state.json"
        assert state_file.exists(), "state.json must always be written"

        data = json.loads(_read(state_file))
        assert data["session_id"] == "abc123"
        assert data["current_phase"] == "done"
        assert data["issue_title"] == "Add timeout"
        # non_serializable is not a primitive type, so it should be absent
        assert "non_serializable" not in data

    # ------------------------------------------------------------------
    # 9. empty string/list/dict fields produce no extra files
    # ------------------------------------------------------------------

    def test_empty_fields_not_written(self, tmp_path):
        state = {
            "design_analysis": "",          # empty string
            "implementation_plan": [],       # empty list
            "code_files": {},               # empty dict
            "unit_tests": {},
            "integration_tests": {},
            "e2e_tests": {},
            "pr_description": "",
            "pr_summary": "",
            "release_notes": "",
            "current_phase": "init",
        }
        _save_artifacts(state, str(tmp_path))

        files = _files_under(tmp_path)
        # Only state.json should be written
        assert files == {"state.json"}, (
            f"Only state.json expected, but found: {files}"
        )

    # ------------------------------------------------------------------
    # 10. None fields produce no files
    # ------------------------------------------------------------------

    def test_none_fields_not_written(self, tmp_path):
        state = {
            "design_analysis": None,
            "implementation_plan": None,
            "code_files": None,
            "unit_tests": None,
            "integration_tests": None,
            "e2e_tests": None,
            "pr_description": None,
            "pr_summary": None,
            "release_notes": None,
            "current_phase": "init",
        }
        _save_artifacts(state, str(tmp_path))

        files = _files_under(tmp_path)
        assert files == {"state.json"}, (
            f"Only state.json expected, but found: {files}"
        )

    # ------------------------------------------------------------------
    # 11. path traversal blocked
    # ------------------------------------------------------------------

    def test_path_traversal_blocked(self, tmp_path):
        evil_key = "../../evil.txt"
        state = {
            "code_files": {evil_key: "malicious content"},
            "current_phase": "develop_complete",
        }
        _save_artifacts(state, str(tmp_path))

        # The file must NOT appear outside the output root
        evil_target = (tmp_path / "code" / evil_key).resolve()
        assert not evil_target.exists(), "Path traversal file must not be created"

        # Nothing outside tmp_path should have been created
        outside = tmp_path.parent / "evil.txt"
        assert not outside.exists(), "evil.txt must not appear outside output dir"

    # ------------------------------------------------------------------
    # 12. existing dir with files prints a warning
    # ------------------------------------------------------------------

    def test_existing_dir_warns(self, tmp_path):
        # Pre-populate the directory
        existing_file = tmp_path / "old_artifact.txt"
        existing_file.write_text("old data")

        state = {"design_analysis": "new content", "current_phase": "design_complete"}

        captured = StringIO()
        with patch("sys.stdout", captured):
            _save_artifacts(state, str(tmp_path))

        output = captured.getvalue()
        assert "WARNING" in output or "already exists" in output.lower(), (
            "Expected a warning about existing output directory, got: " + output
        )

    # ------------------------------------------------------------------
    # 13. OSError on one file does not abort remaining files
    # ------------------------------------------------------------------

    def test_write_error_does_not_abort(self, tmp_path):
        state = {
            "design_analysis": "design content",
            "pr_summary": "summary content",
            "current_phase": "done",
        }

        original_write_text = pathlib.Path.write_text
        call_count = {"n": 0}

        def _selective_fail(self, content, **kwargs):
            call_count["n"] += 1
            # Fail only on the first write (design_analysis.md)
            if "design_analysis" in str(self):
                raise OSError("Simulated disk error")
            return original_write_text(self, content, **kwargs)

        with patch.object(pathlib.Path, "write_text", _selective_fail):
            _save_artifacts(state, str(tmp_path))

        # pr_summary.md should still have been written despite earlier failure
        assert (tmp_path / "docs" / "pr_summary.md").exists(), (
            "Remaining files must be saved even after a single write failure"
        )

    # ------------------------------------------------------------------
    # 14. partial pipeline state (only design_analysis, no code/tests/docs)
    # ------------------------------------------------------------------

    def test_partial_pipeline_state(self, tmp_path):
        state = {
            "design_analysis": "# Partial design",
            "current_phase": "design_complete",
            # No code_files, no tests, no docs fields at all
        }
        _save_artifacts(state, str(tmp_path))

        files = _files_under(tmp_path)
        assert "design/design_analysis.md" in files
        # No code/, tests/, or docs/ directories should have been created
        assert not any(f.startswith("code/") for f in files)
        assert not any(f.startswith("tests/") for f in files)
        assert not any(f.startswith("docs/") for f in files)

    # ------------------------------------------------------------------
    # 15. code_changes fallback when code_files absent
    # ------------------------------------------------------------------

    def test_code_changes_fallback(self, tmp_path):
        state = {
            # No "code_files" key
            "code_changes": {
                "pkg/api/types.go": "package api\n",
            },
            "current_phase": "develop_complete",
        }
        _save_artifacts(state, str(tmp_path))

        target = tmp_path / "code" / "pkg" / "api" / "types.go"
        assert target.exists(), (
            "code_changes should be used as fallback when code_files is absent"
        )
        assert _read(target) == "package api\n"


# ---------------------------------------------------------------------------
# TestOrchestrateOutputDirArg
# ---------------------------------------------------------------------------


class TestOrchestrateOutputDirArg:
    """Tests that --output-dir is correctly wired through the CLI to orchestrate()."""

    # Patch target: orchestrate() as imported inside scripts/orchestrate.py main()
    _PATCH_TARGET = "orchestrate.orchestrate"

    def _run_main(self, argv: list[str]) -> None:
        """Run main() with the given argv list, suppressing SystemExit."""
        import orchestrate as _mod

        with patch.object(_mod, "orchestrate", return_value={"current_phase": "done"}) as mock_orch:
            with patch("sys.argv", ["orchestrate.py"] + argv):
                try:
                    _mod.main()
                except SystemExit:
                    pass
            return mock_orch

    # ------------------------------------------------------------------
    # 16. --output-dir /tmp/x → orchestrate(output_dir="/tmp/x")
    # ------------------------------------------------------------------

    def test_output_dir_passed_to_orchestrate(self, tmp_path):
        import orchestrate as _mod

        with patch.object(_mod, "orchestrate", return_value={"current_phase": "done"}) as mock_orch:
            with patch("sys.argv", [
                "orchestrate.py",
                "--title", "Test feature",
                "--output-dir", str(tmp_path),
            ]):
                try:
                    _mod.main()
                except SystemExit:
                    pass

        mock_orch.assert_called_once()
        _, kwargs = mock_orch.call_args
        assert kwargs.get("output_dir") == str(tmp_path), (
            f"Expected output_dir={str(tmp_path)!r}, got {kwargs.get('output_dir')!r}"
        )

    # ------------------------------------------------------------------
    # 17. no --output-dir → orchestrate(output_dir=None)
    # ------------------------------------------------------------------

    def test_no_output_dir_by_default(self, tmp_path):
        import orchestrate as _mod

        with patch.object(_mod, "orchestrate", return_value={"current_phase": "done"}) as mock_orch:
            with patch("sys.argv", [
                "orchestrate.py",
                "--title", "Test feature",
            ]):
                try:
                    _mod.main()
                except SystemExit:
                    pass

        mock_orch.assert_called_once()
        _, kwargs = mock_orch.call_args
        assert kwargs.get("output_dir") is None, (
            f"Expected output_dir=None when flag omitted, got {kwargs.get('output_dir')!r}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
