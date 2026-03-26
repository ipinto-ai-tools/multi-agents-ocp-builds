"""Tests for scripts/publish.py -- _push_code functionality.

Subprocess (git, gh) calls are mocked; file-system operations use real
temporary directories so path.mkdir() / write_text() work naturally.
"""
import json
import pathlib
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure scripts/ is importable as a top-level module
# ---------------------------------------------------------------------------
SCRIPTS_DIR = pathlib.Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import publish  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_run_result(stdout: str = "", returncode: int = 0) -> MagicMock:
    """Return a mock that looks like subprocess.CompletedProcess."""
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result


def _make_fake_run(pr_url: str = "https://github.com/my-org/my-repo/pull/1"):
    """Return a side_effect function that records calls and returns a fake result."""
    captured: list[list[str]] = []

    def _fake(cmd, cwd=None, check=True, env=None):
        captured.append(cmd)
        return _fake_run_result(pr_url)

    return _fake, captured


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def output_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Populate a temporary output directory with minimal pipeline artifacts."""
    state = {
        "jira_ticket_id": "BUILD-1707",
        "issue_title": "Add timeout support to webhook handler",
        "current_phase": "done",
    }
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")

    # code/pkg/webhook/handler.go
    code_root = tmp_path / "code"
    (code_root / "pkg" / "webhook").mkdir(parents=True)
    (code_root / "pkg" / "webhook" / "handler.go").write_text(
        "package webhook\n", encoding="utf-8"
    )

    # tests/unit/handler_test.go
    tests_root = tmp_path / "tests"
    (tests_root / "unit").mkdir(parents=True)
    (tests_root / "unit" / "handler_test.go").write_text(
        "package webhook_test\n", encoding="utf-8"
    )

    # docs/pr_description.md
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "pr_description.md").write_text(
        "## PR Description\n\nFixes timeout.", encoding="utf-8"
    )

    return tmp_path


@pytest.fixture()
def github_config() -> dict:
    """Valid GitHub config with all required keys populated."""
    return {
        "TARGET_GITHUB_REPO": "my-org/my-repo",
        "TARGET_GITHUB_BASE_BRANCH": "main",
        "GITHUB_TOKEN": "ghp_testtoken123",
    }


@pytest.fixture()
def clone_root(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real temp directory that acts as the shallow-cloned repo root."""
    d = tmp_path / "clone"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Helper: run _push_code with _run mocked and a real clone_root directory
# ---------------------------------------------------------------------------


def _run_push_code(
    output_dir: pathlib.Path,
    github_config: dict,
    clone_root: pathlib.Path,
    *,
    dry_run: bool = False,
) -> tuple[list[list[str]], pathlib.Path]:
    """Call _push_code with subprocess calls mocked; return (captured_cmds, clone_root)."""
    fake_run, captured = _make_fake_run()

    # tempfile.mkdtemp returns the parent of clone_root so that
    # tmp_dir / "repo" == clone_root (matching the implementation).
    tmp_parent = clone_root.parent
    # The implementation does: clone_dir = tmp_dir / "repo"
    # We need mkdtemp to return tmp_parent so clone_dir = tmp_parent / "repo" = clone_root.
    clone_root.rename(tmp_parent / "repo")
    clone_root_real = tmp_parent / "repo"

    with patch("publish._run", side_effect=fake_run):
        with patch("shutil.rmtree"):  # suppress cleanup so we can inspect files
            with patch("tempfile.mkdtemp", return_value=str(tmp_parent)):
                with patch("os.makedirs"):  # suppress /tmp/claude mkdir
                    publish._push_code(output_dir, github_config, dry_run=dry_run)

    return captured, clone_root_real


# ---------------------------------------------------------------------------
# 1. test_push_code_reads_state_json
# ---------------------------------------------------------------------------


def test_push_code_reads_state_json(
    output_dir: pathlib.Path, github_config: dict, clone_root: pathlib.Path
) -> None:
    """_push_code derives branch name from jira_ticket_id + issue_title in state.json."""
    captured, _ = _run_push_code(output_dir, github_config, clone_root)

    checkout_cmds = [c for c in captured if "checkout" in c and "-b" in c]
    assert checkout_cmds, "Expected git checkout -b command"
    branch = checkout_cmds[0][-1]
    assert "build-1707" in branch, f"Branch should contain jira ticket slug; got: {branch}"
    assert "add-timeout" in branch, f"Branch should contain issue title slug; got: {branch}"


# ---------------------------------------------------------------------------
# 2. test_push_code_clones_target_repo
# ---------------------------------------------------------------------------


def test_push_code_clones_target_repo(
    output_dir: pathlib.Path, github_config: dict, clone_root: pathlib.Path
) -> None:
    """_push_code performs a shallow git clone of TARGET_GITHUB_REPO."""
    captured, _ = _run_push_code(output_dir, github_config, clone_root)

    clone_cmds = [c for c in captured if "clone" in c]
    assert clone_cmds, "Expected at least one git clone invocation"
    clone_cmd = clone_cmds[0]
    assert "--depth" in clone_cmd and "1" in clone_cmd, "Expected shallow clone flag"
    assert any("my-org/my-repo" in part for part in clone_cmd), (
        "Clone URL should contain the target repo"
    )


# ---------------------------------------------------------------------------
# 3. test_push_code_creates_branch_with_jira_slug
# ---------------------------------------------------------------------------


def test_push_code_creates_branch_with_jira_slug(
    output_dir: pathlib.Path, github_config: dict, clone_root: pathlib.Path
) -> None:
    """_push_code creates a branch feat/<jira_lower>-<title-slug>."""
    captured, _ = _run_push_code(output_dir, github_config, clone_root)

    checkout_cmds = [c for c in captured if "checkout" in c and "-b" in c]
    assert checkout_cmds, "Expected git checkout -b command"
    branch = checkout_cmds[0][-1]
    assert branch.startswith("feat/build-1707-"), (
        f"Branch must start with feat/build-1707-; got: {branch}"
    )
    assert branch == branch.lower(), "Branch must be fully lower-case"
    # No characters outside [a-z0-9/-]
    import re
    assert not re.search(r"[^a-z0-9/_-]", branch), (
        f"Branch contains unexpected characters: {branch}"
    )


# ---------------------------------------------------------------------------
# 4. test_push_code_copies_code_files
# ---------------------------------------------------------------------------


def test_push_code_copies_code_files(
    output_dir: pathlib.Path, github_config: dict, clone_root: pathlib.Path
) -> None:
    """Files under output_dir/code/ are written to the clone root preserving relative paths."""
    _, clone_root_real = _run_push_code(output_dir, github_config, clone_root)

    expected = clone_root_real / "pkg" / "webhook" / "handler.go"
    assert expected.exists(), f"Expected {expected} to be copied into the clone"
    assert expected.read_text(encoding="utf-8") == "package webhook\n"


# ---------------------------------------------------------------------------
# 5. test_push_code_copies_test_files
# ---------------------------------------------------------------------------


def test_push_code_copies_test_files(
    output_dir: pathlib.Path, github_config: dict, clone_root: pathlib.Path
) -> None:
    """Files under output_dir/tests/ are written to the clone root preserving relative paths."""
    _, clone_root_real = _run_push_code(output_dir, github_config, clone_root)

    expected = clone_root_real / "unit" / "handler_test.go"
    assert expected.exists(), f"Expected {expected} to be copied into the clone"
    assert expected.read_text(encoding="utf-8") == "package webhook_test\n"


# ---------------------------------------------------------------------------
# 6. test_push_code_creates_pr
# ---------------------------------------------------------------------------


def test_push_code_creates_pr(
    output_dir: pathlib.Path, github_config: dict, clone_root: pathlib.Path
) -> None:
    """_push_code calls gh pr create with correct --repo, --base, and --title flags."""
    captured, _ = _run_push_code(output_dir, github_config, clone_root)

    pr_cmds = [c for c in captured if c and c[0] == "gh" and "pr" in c and "create" in c]
    assert pr_cmds, "Expected gh pr create command"
    pr_cmd = pr_cmds[0]
    assert "--repo" in pr_cmd
    assert "my-org/my-repo" in pr_cmd
    assert "--base" in pr_cmd
    assert "main" in pr_cmd
    assert "--title" in pr_cmd
    # PR body should be passed via a file (not inline --body)
    assert "--body-file" in pr_cmd


# ---------------------------------------------------------------------------
# 7. test_push_code_dry_run_skips_git_calls
# ---------------------------------------------------------------------------


def test_push_code_dry_run_skips_git_calls(
    output_dir: pathlib.Path, github_config: dict, capsys
) -> None:
    """In dry-run mode, publish._run is never called."""
    with patch("publish._run") as mock_run:
        publish._push_code(output_dir, github_config, dry_run=True)

    mock_run.assert_not_called()
    captured = capsys.readouterr()
    assert "dry-run" in captured.out.lower()


# ---------------------------------------------------------------------------
# 8. test_push_code_missing_target_repo_exits
# ---------------------------------------------------------------------------


def test_push_code_missing_target_repo_exits(output_dir: pathlib.Path) -> None:
    """_push_code exits 1 when TARGET_GITHUB_REPO is absent."""
    config = {"TARGET_GITHUB_REPO": "", "TARGET_GITHUB_BASE_BRANCH": "main", "GITHUB_TOKEN": "tok"}
    with pytest.raises(SystemExit) as exc_info:
        publish._push_code(output_dir, config, dry_run=False)
    assert exc_info.value.code == 1


def test_push_code_missing_github_token_exits(output_dir: pathlib.Path) -> None:
    """_push_code exits 1 when GITHUB_TOKEN is absent."""
    config = {"TARGET_GITHUB_REPO": "org/repo", "TARGET_GITHUB_BASE_BRANCH": "main", "GITHUB_TOKEN": ""}
    with pytest.raises(SystemExit) as exc_info:
        publish._push_code(output_dir, config, dry_run=False)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# 9. test_push_code_cleanup_on_error
# ---------------------------------------------------------------------------


def test_push_code_cleanup_on_error(output_dir: pathlib.Path, github_config: dict, tmp_path: pathlib.Path) -> None:
    """shutil.rmtree is still called when git clone raises CalledProcessError."""
    fake_tmp = tmp_path / "publish-err"
    fake_tmp.mkdir()
    with patch("publish._run", side_effect=subprocess.CalledProcessError(1, "git")):
        with patch("shutil.rmtree") as mock_rmtree:
            with patch("tempfile.mkdtemp", return_value=str(fake_tmp)):
                with patch("os.makedirs"):
                    with pytest.raises(subprocess.CalledProcessError):
                        publish._push_code(output_dir, github_config, dry_run=False)

    mock_rmtree.assert_called_once()


# ---------------------------------------------------------------------------
# 10. test_slug_generation_special_chars
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Add timeout support", "add-timeout-support"),
        ("Fix: memory leak in webhook!", "fix-memory-leak-in-webhook"),
        # '/' is stripped (not whitespace), so "multi/path" → "multipath"
        ("Feature (NEW) -- multi/path support", "feature-new-multipath-support"),
        ("  leading and trailing spaces  ", "leading-and-trailing-spaces"),
        ("UPPERCASE TITLE", "uppercase-title"),
        ("a" * 50, "a" * 40),  # truncated to max_len=40
        ("hello---world", "hello-world"),  # consecutive hyphens collapsed
        ("", ""),
    ],
)
def test_slug_generation_special_chars(title: str, expected: str) -> None:
    """_slug converts titles to URL-safe slugs, max 40 chars."""
    assert publish._slug(title) == expected


# ---------------------------------------------------------------------------
# Bonus: _collect_files helper
# ---------------------------------------------------------------------------


def test_collect_files_returns_all_files(tmp_path: pathlib.Path) -> None:
    """_collect_files returns relative-path -> content for every file in the tree."""
    (tmp_path / "a.go").write_text("package a\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.go").write_text("package b\n")

    result = publish._collect_files(tmp_path)

    assert "a.go" in result
    assert str(pathlib.Path("sub") / "b.go") in result
    assert result["a.go"] == "package a\n"


def test_collect_files_nonexistent_dir(tmp_path: pathlib.Path) -> None:
    """_collect_files returns {} when the directory does not exist."""
    result = publish._collect_files(tmp_path / "missing")
    assert result == {}


# ---------------------------------------------------------------------------
# 11. test_push_code_token_not_in_clone_url
# ---------------------------------------------------------------------------


def test_push_code_token_not_in_clone_url(
    output_dir: pathlib.Path, github_config: dict, clone_root: pathlib.Path
) -> None:
    """GITHUB_TOKEN must not appear in the git clone URL."""
    token = github_config["GITHUB_TOKEN"]
    captured, _ = _run_push_code(output_dir, github_config, clone_root)

    clone_cmds = [c for c in captured if "clone" in c]
    assert clone_cmds, "Expected at least one git clone invocation"
    for arg in clone_cmds[0]:
        assert token not in arg, (
            f"GITHUB_TOKEN found in clone argument: {arg!r}"
        )


# ---------------------------------------------------------------------------
# 12. test_push_code_push_rejection_prints_clear_error
# ---------------------------------------------------------------------------


def test_push_code_push_rejection_prints_clear_error(
    output_dir: pathlib.Path,
    github_config: dict,
    clone_root: pathlib.Path,
    capsys,
) -> None:
    """When git push fails, a clear error message is printed and the exception propagates."""
    push_error = subprocess.CalledProcessError(
        1, "git push", stderr="remote: branch already exists"
    )

    def _selective_run(cmd, cwd=None, check=True, env=None):
        if "push" in cmd:
            raise push_error
        return _fake_run_result()

    tmp_parent = clone_root.parent
    clone_root.rename(tmp_parent / "repo")

    with patch("publish._run", side_effect=_selective_run):
        with patch("shutil.rmtree"):
            with patch("tempfile.mkdtemp", return_value=str(tmp_parent)):
                with patch("os.makedirs"):
                    with pytest.raises(subprocess.CalledProcessError):
                        publish._push_code(output_dir, github_config, dry_run=False)

    out = capsys.readouterr().out
    assert "already exist" in out, (
        f"Expected 'already exist' in output; got:\n{out}"
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
