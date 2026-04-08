"""GitHub integration — fetch PR metadata from URLs."""
import os
from typing import Any

from utils.file_logger import get_logger

logger = get_logger(__name__)


def fetch_github_prs(pr_urls: list[str]) -> dict[str, Any]:
    """Fetch GitHub PR metadata from a list of PR URLs.

    In DRY_RUN mode, returns empty PR data.
    Returns dict with: pr_data (list of PR metadata dicts)
    """
    if os.getenv("DRY_RUN", "").lower() == "true":
        return {"pr_data": []}

    if not pr_urls:
        return {"pr_data": []}

    from tools.github_client import is_github_configured, get_github_client

    if not is_github_configured():
        logger.warning("GitHub not configured, skipping PR fetch")
        return {"pr_data": []}

    client = get_github_client()
    pr_data = client.fetch_prs_from_urls(pr_urls)
    return {"pr_data": pr_data}
