"""Tests for config.repo_config module.

Covers repo path loading from repos.yaml, environment variables, and CLI
arguments, including precedence, deduplication, validation, and the
ENABLE_REPO_ANALYSIS kill-switch.
"""

import logging

import pytest
import yaml

from config.repo_config import load_repo_paths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_repos_yaml(directory, repos_content):
    """Write a repos.yaml file into *directory* with the given content dict."""
    yaml_path = directory / "repos.yaml"
    yaml_path.write_text(yaml.dump(repos_content))
    return yaml_path


def _make_repo_dirs(tmp_path, names):
    """Create subdirectories under *tmp_path* and return their resolved paths."""
    paths = []
    for name in names:
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        paths.append(str(d.resolve()))
    return paths


# ---------------------------------------------------------------------------
# 1. No repos.yaml, no env vars, no CLI arg -> empty list
# ---------------------------------------------------------------------------

def test_no_config_returns_empty(tmp_path, monkeypatch):
    """With no repos.yaml, no env vars, and no CLI arg the result is empty."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    result = load_repo_paths(project_root=str(tmp_path))

    assert result == []


# ---------------------------------------------------------------------------
# 2. repos.yaml with valid paths -> returns those paths
# ---------------------------------------------------------------------------

def test_yaml_with_valid_paths(tmp_path, monkeypatch):
    """repos.yaml listing existing directories returns those paths."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    dirs = _make_repo_dirs(tmp_path, ["repo-a", "repo-b"])
    _write_repos_yaml(tmp_path, {"repos": [{"path": d} for d in dirs]})

    result = load_repo_paths(project_root=str(tmp_path))

    assert result == dirs


# ---------------------------------------------------------------------------
# 3. repos.yaml with non-existent paths -> skips with warning
# ---------------------------------------------------------------------------

def test_yaml_with_nonexistent_paths_warns(tmp_path, monkeypatch, caplog):
    """Non-existent paths in repos.yaml are skipped and a warning is logged."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    fake = str(tmp_path / "does-not-exist")
    _write_repos_yaml(tmp_path, {"repos": [{"path": fake}]})

    with caplog.at_level(logging.WARNING, logger="config.repo_config"):
        result = load_repo_paths(project_root=str(tmp_path))

    assert result == []
    assert any("does not exist" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# 4. repos.yaml with mixed valid/invalid paths -> only valid ones returned
# ---------------------------------------------------------------------------

def test_yaml_mixed_valid_invalid(tmp_path, monkeypatch):
    """Only existing directories from repos.yaml are returned."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    valid_dirs = _make_repo_dirs(tmp_path, ["good-repo"])
    bad_path = str(tmp_path / "missing-repo")
    entries = [{"path": valid_dirs[0]}, {"path": bad_path}]
    _write_repos_yaml(tmp_path, {"repos": entries})

    result = load_repo_paths(project_root=str(tmp_path))

    assert result == valid_dirs


# ---------------------------------------------------------------------------
# 5. No repos.yaml, env vars set -> falls back to env var paths
# ---------------------------------------------------------------------------

def test_env_var_fallback(tmp_path, monkeypatch):
    """When repos.yaml is absent, SHIPWRIGHT_REPO_PATH and
    OPENSHIFT_BUILDS_REPO_PATH are used as fallback."""
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    dirs = _make_repo_dirs(tmp_path, ["ship", "ocp"])
    monkeypatch.setenv("SHIPWRIGHT_REPO_PATH", dirs[0])
    monkeypatch.setenv("OPENSHIFT_BUILDS_REPO_PATH", dirs[1])

    # Point project_root at a directory without repos.yaml
    empty_root = tmp_path / "empty-root"
    empty_root.mkdir()

    result = load_repo_paths(project_root=str(empty_root))

    assert dirs[0] in result
    assert dirs[1] in result


# ---------------------------------------------------------------------------
# 6. repos.yaml AND env vars -> yaml first, env appended, no duplicates
# ---------------------------------------------------------------------------

def test_yaml_and_env_vars_combined(tmp_path, monkeypatch):
    """repos.yaml paths appear first; env-var paths are appended without
    duplicating any path already present."""
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    dirs = _make_repo_dirs(tmp_path, ["yaml-repo", "env-repo"])
    _write_repos_yaml(tmp_path, {"repos": [{"path": dirs[0]}]})

    monkeypatch.setenv("SHIPWRIGHT_REPO_PATH", dirs[1])
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)

    result = load_repo_paths(project_root=str(tmp_path))

    assert result == dirs  # yaml-repo first, env-repo second


def test_yaml_and_env_vars_no_duplicate(tmp_path, monkeypatch):
    """If a path appears in both repos.yaml and an env var it is not
    duplicated."""
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    dirs = _make_repo_dirs(tmp_path, ["shared-repo"])
    _write_repos_yaml(tmp_path, {"repos": [{"path": dirs[0]}]})
    monkeypatch.setenv("SHIPWRIGHT_REPO_PATH", dirs[0])
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)

    result = load_repo_paths(project_root=str(tmp_path))

    assert result == dirs
    assert len(result) == 1


# ---------------------------------------------------------------------------
# 7. CLI arg takes highest precedence -> prepended before yaml & env
# ---------------------------------------------------------------------------

def test_cli_arg_highest_precedence(tmp_path, monkeypatch):
    """The cli_repo_path argument is prepended before repos.yaml and env-var
    paths."""
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    dirs = _make_repo_dirs(tmp_path, ["cli-repo", "yaml-repo", "env-repo"])
    _write_repos_yaml(tmp_path, {"repos": [{"path": dirs[1]}]})
    monkeypatch.setenv("SHIPWRIGHT_REPO_PATH", dirs[2])
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)

    result = load_repo_paths(cli_repo_path=dirs[0], project_root=str(tmp_path))

    assert result[0] == dirs[0], "CLI path must come first"
    assert dirs[1] in result
    assert dirs[2] in result


# ---------------------------------------------------------------------------
# 8. Deduplication -> same path via CLI + yaml + env appears only once
# ---------------------------------------------------------------------------

def test_deduplication_across_sources(tmp_path, monkeypatch):
    """A path supplied via CLI, repos.yaml, and env var appears only once."""
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    dirs = _make_repo_dirs(tmp_path, ["the-repo"])
    _write_repos_yaml(tmp_path, {"repos": [{"path": dirs[0]}]})
    monkeypatch.setenv("SHIPWRIGHT_REPO_PATH", dirs[0])
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)

    result = load_repo_paths(cli_repo_path=dirs[0], project_root=str(tmp_path))

    assert result == dirs
    assert len(result) == 1


# ---------------------------------------------------------------------------
# 9. ENABLE_REPO_ANALYSIS=false -> empty list regardless of other config
# ---------------------------------------------------------------------------

def test_enable_repo_analysis_false(tmp_path, monkeypatch):
    """Setting ENABLE_REPO_ANALYSIS=false returns an empty list even when
    repos.yaml and env vars provide valid paths."""
    dirs = _make_repo_dirs(tmp_path, ["a-repo"])
    _write_repos_yaml(tmp_path, {"repos": [{"path": dirs[0]}]})
    monkeypatch.setenv("SHIPWRIGHT_REPO_PATH", dirs[0])
    monkeypatch.setenv("ENABLE_REPO_ANALYSIS", "false")

    result = load_repo_paths(cli_repo_path=dirs[0], project_root=str(tmp_path))

    assert result == []


def test_enable_repo_analysis_false_case_insensitive(tmp_path, monkeypatch):
    """The kill-switch is case-insensitive (e.g. 'False', 'FALSE')."""
    dirs = _make_repo_dirs(tmp_path, ["a-repo"])
    _write_repos_yaml(tmp_path, {"repos": [{"path": dirs[0]}]})
    monkeypatch.setenv("ENABLE_REPO_ANALYSIS", "False")
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)

    result = load_repo_paths(project_root=str(tmp_path))

    assert result == []


# ---------------------------------------------------------------------------
# 10. Malformed YAML -> returns empty list (logs warning)
# ---------------------------------------------------------------------------

def test_malformed_yaml_returns_empty(tmp_path, monkeypatch, caplog):
    """A repos.yaml with invalid YAML syntax yields an empty list and a
    warning."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    yaml_path = tmp_path / "repos.yaml"
    yaml_path.write_text("repos:\n  - path: [unterminated")

    with caplog.at_level(logging.WARNING, logger="config.repo_config"):
        result = load_repo_paths(project_root=str(tmp_path))

    assert result == []
    assert any("Failed to parse" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# 11. repos.yaml missing 'repos' key -> returns empty list
# ---------------------------------------------------------------------------

def test_yaml_missing_repos_key(tmp_path, monkeypatch, caplog):
    """A repos.yaml without the top-level 'repos' key yields an empty list
    and a warning."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    _write_repos_yaml(tmp_path, {"paths": ["/some/path"]})

    with caplog.at_level(logging.WARNING, logger="config.repo_config"):
        result = load_repo_paths(project_root=str(tmp_path))

    assert result == []
    assert any("missing" in msg.lower() for msg in caplog.messages)


def test_yaml_repos_key_with_empty_list(tmp_path, monkeypatch):
    """A repos.yaml with an empty 'repos' list returns nothing."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    _write_repos_yaml(tmp_path, {"repos": []})

    result = load_repo_paths(project_root=str(tmp_path))

    assert result == []


# ---------------------------------------------------------------------------
# 12. repos.yaml with 'repos:' but no entries (None value) -> empty list
# ---------------------------------------------------------------------------

def test_yaml_repos_key_with_none_value(tmp_path, monkeypatch):
    """When repos.yaml contains just ``repos:`` (no entries),
    ``yaml.safe_load`` returns ``{"repos": None}``.  The function should
    return an empty list without crashing."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    yaml_path = tmp_path / "repos.yaml"
    yaml_path.write_text("repos:\n")

    result = load_repo_paths(project_root=str(tmp_path))
    assert result == []


# ---------------------------------------------------------------------------
# 13. repos.yaml entry without 'path' key -> skipped with warning
# ---------------------------------------------------------------------------

def test_yaml_entry_without_path_key(tmp_path, monkeypatch, caplog):
    """When an entry in the repos list doesn't have a ``path`` key, it
    should be skipped with a warning."""
    monkeypatch.delenv("SHIPWRIGHT_REPO_PATH", raising=False)
    monkeypatch.delenv("OPENSHIFT_BUILDS_REPO_PATH", raising=False)
    monkeypatch.delenv("ENABLE_REPO_ANALYSIS", raising=False)

    _write_repos_yaml(tmp_path, {"repos": [{"name": "oops"}]})

    with caplog.at_level(logging.WARNING, logger="config.repo_config"):
        result = load_repo_paths(project_root=str(tmp_path))

    assert result == []
    assert any("malformed" in msg.lower() for msg in caplog.messages)
