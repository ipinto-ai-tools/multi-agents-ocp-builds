import logging
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from config.repo_schema import RepoConfig

logger = logging.getLogger(__name__)

_DEFAULT_YAML_NAME = "repos.yaml"


def _resolve_project_root(project_root: str | None) -> Path:
    if project_root is not None:
        return Path(project_root)
    # config/ package lives one level below the project root
    return Path(__file__).resolve().parent.parent


def _load_raw_yaml(yaml_path: Path) -> dict | None:
    """Load and return raw YAML data, or ``None`` on failure."""
    if not yaml_path.is_file():
        logger.debug("repos.yaml not found at %s, skipping", yaml_path)
        return None

    try:
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse %s: %s", yaml_path, exc)
        return None

    if not isinstance(data, dict):
        logger.warning("repos.yaml root must be a mapping, got %s", type(data).__name__)
        return None

    return data


def load_repo_config(yaml_path: Path) -> RepoConfig:
    """Parse *yaml_path* into a validated :class:`RepoConfig`.

    Returns an empty ``RepoConfig()`` when the file is missing, unparseable,
    or fails schema validation -- the caller never has to handle ``None``.
    """
    raw = _load_raw_yaml(yaml_path)
    if raw is None:
        return RepoConfig()

    try:
        return RepoConfig.model_validate(raw)
    except ValidationError as exc:
        logger.warning("repos.yaml schema validation failed: %s", exc)
        return RepoConfig()


def _load_yaml_paths(yaml_path: Path) -> list[str]:
    config = load_repo_config(yaml_path)
    return [entry.path for entry in config.repos]


def _env_var_paths() -> list[str]:
    paths: list[str] = []
    for var in ("SHIPWRIGHT_REPO_PATH", "OPENSHIFT_BUILDS_REPO_PATH"):
        value = os.getenv(var)
        if value:
            paths.append(value)
    return paths


def _deduplicated(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for p in paths:
        resolved = str(Path(p).resolve())
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def load_repo_paths(
    cli_repo_path: str | None = None,
    project_root: str | None = None,
) -> list[str]:
    if os.getenv("ENABLE_REPO_ANALYSIS", "true").lower() == "false":
        logger.info("Repository analysis disabled (ENABLE_REPO_ANALYSIS=false)")
        return []

    root = _resolve_project_root(project_root)
    yaml_path = root / _DEFAULT_YAML_NAME

    candidates: list[str] = []

    # Highest priority: CLI argument
    if cli_repo_path:
        candidates.append(cli_repo_path)

    # repos.yaml paths
    yaml_paths = _load_yaml_paths(yaml_path)
    candidates.extend(yaml_paths)

    # Env var fallback (appended; duplicates removed by deduplication)
    candidates.extend(_env_var_paths())

    # Deduplicate (resolves symlinks / relative differences)
    unique = _deduplicated(candidates)

    # Validate existence
    validated: list[str] = []
    for p in unique:
        if Path(p).is_dir():
            validated.append(p)
        else:
            logger.warning("Repo path does not exist, skipping: %s", p)

    logger.info("Loaded %d repo path(s) for analysis", len(validated))
    return validated
