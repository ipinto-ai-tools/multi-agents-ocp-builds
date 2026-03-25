from typing import Any

from skills.base import Skill


class FetchGitHubPRsSkill(Skill):
    name = "fetch_github_prs"
    description = "Fetch GitHub PRs by URL and return structured PR data."
    input_schema = {"pr_urls": {"type": "array", "items": {"type": "string"}}}
    output_schema = {"pr_data": {"type": "array"}}

    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        from tools.github_client import get_github_client, is_github_configured

        pr_urls = input.get("pr_urls") or []
        if not is_github_configured() or not pr_urls:
            return {"pr_data": []}

        client = get_github_client()
        pr_data = client.fetch_prs_from_urls(pr_urls)
        return {"pr_data": pr_data}

    def _mock_response(self, input: dict[str, Any]) -> dict[str, Any]:
        return {"pr_data": []}
