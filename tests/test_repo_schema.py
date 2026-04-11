"""Tests for repo.yaml schema validation (config/repo_schema.py + config/repo_config.py)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from pydantic import ValidationError

from config.repo_schema import (
    ApprovalConfig,
    PromptOverrides,
    RepoCommands,
    RepoConfig,
    RepoEntry,
    VALID_STAGES,
)


# ---------------------------------------------------------------------------
# RepoCommands
# ---------------------------------------------------------------------------


class TestRepoCommands:
    """RepoCommands model tests."""

    def test_defaults_are_none(self) -> None:
        cmd = RepoCommands()
        assert cmd.build is None
        assert cmd.lint is None
        assert cmd.test is None
        assert cmd.doc is None

    def test_all_fields(self) -> None:
        cmd = RepoCommands(
            build="go build ./...",
            lint="golangci-lint run",
            test="go test ./...",
            doc="godoc",
        )
        assert cmd.build == "go build ./..."
        assert cmd.lint == "golangci-lint run"
        assert cmd.test == "go test ./..."
        assert cmd.doc == "godoc"

    def test_partial_fields(self) -> None:
        cmd = RepoCommands(test="pytest")
        assert cmd.test == "pytest"
        assert cmd.build is None


# ---------------------------------------------------------------------------
# RepoEntry
# ---------------------------------------------------------------------------


class TestRepoEntry:
    """RepoEntry model tests."""

    def test_minimal_path_only(self) -> None:
        entry = RepoEntry(path="/home/user/repo")
        assert entry.path == "/home/user/repo"
        assert entry.language is None
        assert entry.commands == RepoCommands()

    def test_full_entry(self) -> None:
        entry = RepoEntry(
            path="/home/user/repo",
            language="go",
            commands=RepoCommands(build="go build ./...", test="go test ./..."),
        )
        assert entry.language == "go"
        assert entry.commands.build == "go build ./..."
        assert entry.commands.test == "go test ./..."

    def test_relative_path_raises(self) -> None:
        with pytest.raises(ValidationError, match="must be absolute"):
            RepoEntry(path="relative/path")

    def test_dot_path_raises(self) -> None:
        with pytest.raises(ValidationError, match="must be absolute"):
            RepoEntry(path=".")

    def test_absolute_path_accepted(self) -> None:
        entry = RepoEntry(path="/absolute/path")
        assert entry.path == "/absolute/path"


# ---------------------------------------------------------------------------
# RepoConfig (top-level)
# ---------------------------------------------------------------------------


class TestRepoConfig:
    """RepoConfig model tests."""

    def test_empty_repos_list(self) -> None:
        cfg = RepoConfig(repos=[])
        assert cfg.repos == []

    def test_default_empty(self) -> None:
        cfg = RepoConfig()
        assert cfg.repos == []

    def test_valid_config_multiple_repos(self) -> None:
        cfg = RepoConfig(
            repos=[
                RepoEntry(path="/home/user/repo1"),
                RepoEntry(path="/home/user/repo2", language="python"),
            ]
        )
        assert len(cfg.repos) == 2
        assert cfg.repos[1].language == "python"

    def test_model_validate_from_dict(self) -> None:
        data = {
            "repos": [
                {
                    "path": "/home/user/repo",
                    "language": "go",
                    "commands": {"build": "make", "test": "make test"},
                }
            ]
        }
        cfg = RepoConfig.model_validate(data)
        assert len(cfg.repos) == 1
        assert cfg.repos[0].commands.build == "make"

    def test_model_validate_path_only(self) -> None:
        """Backward-compatible: entries with only a path key."""
        data = {"repos": [{"path": "/home/user/repo"}]}
        cfg = RepoConfig.model_validate(data)
        assert len(cfg.repos) == 1
        assert cfg.repos[0].language is None
        assert cfg.repos[0].commands == RepoCommands()

    def test_model_validate_missing_repos_key(self) -> None:
        """Missing 'repos' key defaults to empty list."""
        cfg = RepoConfig.model_validate({})
        assert cfg.repos == []

    def test_model_validate_invalid_entry(self) -> None:
        """An entry with a relative path should fail validation."""
        data = {"repos": [{"path": "relative/path"}]}
        with pytest.raises(ValidationError, match="must be absolute"):
            RepoConfig.model_validate(data)


# ---------------------------------------------------------------------------
# Integration: load_repo_config via repo_config module
# ---------------------------------------------------------------------------


class TestLoadRepoConfig:
    """Integration tests for config.repo_config.load_repo_config."""

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        cfg = load_repo_config(tmp_path / "nonexistent.yaml")
        assert cfg.repos == []

    def test_valid_yaml(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_content = dedent("""\
            repos:
              - path: /home/user/repo1
                language: go
                commands:
                  build: go build ./...
              - path: /home/user/repo2
        """)
        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(yaml_content)

        cfg = load_repo_config(yaml_file)
        assert len(cfg.repos) == 2
        assert cfg.repos[0].language == "go"
        assert cfg.repos[0].commands.build == "go build ./..."
        assert cfg.repos[1].language is None

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(": [invalid yaml\n")

        cfg = load_repo_config(yaml_file)
        assert cfg.repos == []

    def test_validation_error_returns_empty(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_content = dedent("""\
            repos:
              - path: relative/path
        """)
        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(yaml_content)

        cfg = load_repo_config(yaml_file)
        assert cfg.repos == []

    def test_non_dict_root_returns_empty(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text("- just a list\n")

        cfg = load_repo_config(yaml_file)
        assert cfg.repos == []

    def test_repos_not_a_list_returns_empty(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_content = dedent("""\
            repos: "not a list"
        """)
        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(yaml_content)

        cfg = load_repo_config(yaml_file)
        assert cfg.repos == []

    def test_backward_compat_load_repo_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_repo_paths still works end-to-end with the new schema."""
        from config.repo_config import load_repo_paths

        # Create a repo dir so the existence check passes
        repo_dir = tmp_path / "myrepo"
        repo_dir.mkdir()

        yaml_content = f"repos:\n  - path: {repo_dir}\n"
        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(yaml_content)

        # Clear env vars that could inject extra paths
        monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
        monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
        monkeypatch.setenv("ENABLE_REPO_ANALYSIS", "true")

        paths = load_repo_paths(project_root=str(tmp_path))
        assert len(paths) == 1
        assert paths[0] == str(repo_dir.resolve())


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


class TestStages:
    """Stage ordering configuration tests."""

    def test_default_stages(self) -> None:
        config = RepoConfig()
        assert config.stages == ["design", "develop", "testing", "docs"]

    def test_default_stages_match_constant(self) -> None:
        config = RepoConfig()
        assert config.stages == VALID_STAGES

    def test_custom_stage_order(self) -> None:
        config = RepoConfig(stages=["design", "develop", "docs"])
        assert config.stages == ["design", "develop", "docs"]

    def test_invalid_stage_name(self) -> None:
        with pytest.raises(ValidationError, match="Invalid stage"):
            RepoConfig(stages=["design", "invalid_stage"])

    def test_duplicate_stages(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate stages"):
            RepoConfig(stages=["design", "design", "develop"])

    def test_empty_stages(self) -> None:
        config = RepoConfig(stages=[])
        assert config.stages == []

    def test_single_stage(self) -> None:
        config = RepoConfig(stages=["docs"])
        assert config.stages == ["docs"]

    def test_reversed_order(self) -> None:
        config = RepoConfig(stages=["docs", "testing", "develop", "design"])
        assert config.stages == ["docs", "testing", "develop", "design"]


# ---------------------------------------------------------------------------
# ApprovalConfig
# ---------------------------------------------------------------------------


class TestApprovalConfig:
    """Approval requirements tests."""

    def test_default_approvals(self) -> None:
        config = RepoConfig()
        assert config.approvals.required_stages == []
        assert config.approvals.auto_approve is False

    def test_required_stages(self) -> None:
        config = RepoConfig(approvals={"required_stages": ["develop", "testing"]})
        assert config.approvals.required_stages == ["develop", "testing"]

    def test_auto_approve(self) -> None:
        config = RepoConfig(approvals={"auto_approve": True})
        assert config.approvals.auto_approve is True

    def test_invalid_approval_stage(self) -> None:
        with pytest.raises(ValidationError, match="Invalid stage name"):
            RepoConfig(approvals={"required_stages": ["nonexistent"]})

    def test_approval_config_standalone(self) -> None:
        approval = ApprovalConfig(required_stages=["design"], auto_approve=True)
        assert approval.required_stages == ["design"]
        assert approval.auto_approve is True

    def test_approval_config_empty(self) -> None:
        approval = ApprovalConfig()
        assert approval.required_stages == []
        assert approval.auto_approve is False


# ---------------------------------------------------------------------------
# PromptOverrides
# ---------------------------------------------------------------------------


class TestPromptOverrides:
    """Prompt override tests."""

    def test_default_prompts(self) -> None:
        config = RepoConfig()
        assert config.prompts.design is None
        assert config.prompts.develop is None
        assert config.prompts.test is None
        assert config.prompts.docs is None

    def test_custom_prompts(self) -> None:
        config = RepoConfig(prompts={"design": "Custom design prompt"})
        assert config.prompts.design == "Custom design prompt"
        assert config.prompts.develop is None

    def test_all_prompts(self) -> None:
        config = RepoConfig(
            prompts={
                "design": "Design prompt",
                "develop": "Develop prompt",
                "test": "Test prompt",
                "docs": "Docs prompt",
            }
        )
        assert config.prompts.design == "Design prompt"
        assert config.prompts.develop == "Develop prompt"
        assert config.prompts.test == "Test prompt"
        assert config.prompts.docs == "Docs prompt"

    def test_prompt_overrides_standalone(self) -> None:
        overrides = PromptOverrides(design="Custom", test="Also custom")
        assert overrides.design == "Custom"
        assert overrides.test == "Also custom"
        assert overrides.develop is None
        assert overrides.docs is None


# ---------------------------------------------------------------------------
# Full YAML round-trip via load_repo_config
# ---------------------------------------------------------------------------


class TestFullConfigYaml:
    """End-to-end YAML parsing with new schema fields."""

    def test_full_config_from_yaml(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_content = dedent("""\
            repos:
              - path: /tmp/test-repo
            stages:
              - design
              - develop
            approvals:
              required_stages:
                - develop
              auto_approve: false
            prompts:
              design: "Custom design prompt"
        """)
        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(yaml_content)

        config = load_repo_config(yaml_file)
        assert len(config.repos) == 1
        assert config.stages == ["design", "develop"]
        assert config.approvals.required_stages == ["develop"]
        assert config.approvals.auto_approve is False
        assert config.prompts.design == "Custom design prompt"

    def test_yaml_with_only_repos_keeps_defaults(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_content = dedent("""\
            repos:
              - path: /tmp/test-repo
        """)
        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(yaml_content)

        config = load_repo_config(yaml_file)
        assert config.stages == VALID_STAGES
        assert config.approvals.required_stages == []
        assert config.approvals.auto_approve is False
        assert config.prompts.design is None

    def test_yaml_invalid_stage_returns_empty(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_content = dedent("""\
            repos:
              - path: /tmp/test-repo
            stages:
              - design
              - bogus
        """)
        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(yaml_content)

        config = load_repo_config(yaml_file)
        # Validation failure falls back to empty config
        assert config.repos == []

    def test_yaml_auto_approve_only(self, tmp_path: Path) -> None:
        from config.repo_config import load_repo_config

        yaml_content = dedent("""\
            repos: []
            approvals:
              auto_approve: true
        """)
        yaml_file = tmp_path / "repos.yaml"
        yaml_file.write_text(yaml_content)

        config = load_repo_config(yaml_file)
        assert config.approvals.auto_approve is True
        assert config.approvals.required_stages == []
