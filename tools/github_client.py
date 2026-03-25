"""GitHub REST API client for fetching pull request data.

Uses GitHub REST API v3 with Bearer token authentication (personal access token
or fine-grained PAT with read:repo scope).

Auth: GITHUB_TOKEN env var — a personal access token with at minimum read-only
access to repository contents and pull requests. A classic PAT with the `repo`
scope or a fine-grained PAT with `Pull requests: Read` permission is sufficient.
"""

import os
import re
import logging
from typing import Any

import requests

from tools.pii_redactor import redact_pii

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REQUEST_TIMEOUT = int(os.getenv("GITHUB_REQUEST_TIMEOUT", "10"))

_GITHUB_PR_URL_RE = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")


def parse_github_pr_url(url: str) -> tuple[str, str, int] | None:
    """Parse a GitHub PR URL into (owner, repo, pr_number).

    Returns None if the URL does not match the expected GitHub PR URL format.

    Examples:
        >>> parse_github_pr_url("https://github.com/openshift/builds/pull/42")
        ('openshift', 'builds', 42)
        >>> parse_github_pr_url("https://example.com/not-a-pr") is None
        True
    """
    match = _GITHUB_PR_URL_RE.search(url)
    if not match:
        return None
    owner, repo, pr_number = match.groups()
    return owner, repo, int(pr_number)


class GitHubClient:
    """Fetch GitHub pull request data via REST API v3."""

    _BASE_URL = "https://api.github.com"

    def __init__(self, token: str) -> None:
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def fetch_pr(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        """Fetch pull request details from GitHub.

        Calls GET /repos/{owner}/{repo}/pulls/{pr_number} and returns a
        structured dict with the most useful PR fields normalised for
        downstream use.

        Raises:
            requests.HTTPError: on non-2xx API responses.
            ValueError: if the response Content-Type is not JSON.
        """
        url = f"{self._BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"

        logger.info("Fetching GitHub PR: %s/%s#%d", owner, repo, pr_number)
        response = requests.get(url, headers=self.headers, timeout=GITHUB_REQUEST_TIMEOUT)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            raise ValueError(
                f"Unexpected Content-Type from GitHub API: '{content_type}'. "
                "Expected 'application/json'. Check that the URL is correct and "
                "the token has the required scopes."
            )

        data = response.json()

        merged = data.get("merged", False)
        state = "merged" if merged else data.get("state", "")

        pr_dict = {
            "pr_number": data.get("number"),
            "pr_url": data.get("html_url", ""),
            "title": data.get("title", ""),
            "body": data.get("body") or "",
            "state": state,
            "merged": merged,
            "merged_at": data.get("merged_at"),
            "author": (data.get("user") or {}).get("login", ""),
            "reviewers": [r.get("login", "") for r in data.get("requested_reviewers", [])],
            "labels": [lbl.get("name", "") for lbl in data.get("labels", [])],
            "base_branch": (data.get("base") or {}).get("ref", ""),
            "head_branch": (data.get("head") or {}).get("ref", ""),
            "repo_full_name": ((data.get("base") or {}).get("repo") or {}).get("full_name", ""),
            "files_changed": data.get("changed_files", 0),
            "additions": data.get("additions", 0),
            "deletions": data.get("deletions", 0),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }
        return redact_pii(pr_dict, source=f"github:{owner}/{repo}#{pr_number}")

    def fetch_prs_from_urls(self, pr_urls: list[str]) -> list[dict[str, Any]]:
        """Fetch multiple PRs from a list of GitHub PR URLs.

        Each URL is parsed into (owner, repo, pr_number) and then fetched
        individually. URLs that do not match the expected format, or that
        result in an API error, are skipped with a warning logged.

        Returns a list of PR dicts in the same order as the successfully
        fetched URLs (failed URLs are omitted).
        """
        results: list[dict[str, Any]] = []

        for url in pr_urls:
            parsed = parse_github_pr_url(url)
            if parsed is None:
                logger.warning("Skipping unrecognised GitHub PR URL: %s", url)
                continue

            owner, repo, pr_number = parsed
            try:
                pr_data = self.fetch_pr(owner, repo, pr_number)
                results.append(pr_data)
            except Exception as exc:
                logger.warning(
                    "Could not fetch PR %s/%s#%d (%s: %s)",
                    owner,
                    repo,
                    pr_number,
                    type(exc).__name__,
                    exc,
                )

        return results


def get_github_client() -> GitHubClient:
    """Factory: create a GitHubClient from environment variables.

    Raises:
        ValueError: if GITHUB_TOKEN is not set, with a helpful message
            explaining which token scopes are required.
    """
    if not GITHUB_TOKEN:
        raise ValueError(
            "GITHUB_TOKEN is required for GitHub PR fetching. "
            "Set it in .env (read-only token with repo scope is sufficient)."
        )
    return GitHubClient(GITHUB_TOKEN)


def is_github_configured() -> bool:
    """Return True if GITHUB_TOKEN is set in the environment."""
    return bool(GITHUB_TOKEN)
