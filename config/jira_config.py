"""Jira configuration: field mappings and project settings."""

from typing import Final

# Custom field ID for Acceptance Criteria in Jira.
# This varies by Jira project. Common values:
#   "customfield_10016" - Story Points (NOT this one)
#   "customfield_10014" - Epic Link
#   "customfield_10500" - Acceptance Criteria (common)
# Set JIRA_AC_FIELD_ID env var to override.
import os

ACCEPTANCE_CRITERIA_FIELD_ID: Final[str] = os.getenv(
    "JIRA_AC_FIELD_ID", "customfield_10500"
)

# Map Jira issue types to internal issue_type values used by agents
ISSUE_TYPE_MAP: Final[dict[str, str]] = {
    "bug": "bug",
    "defect": "bug",
    "incident": "bug",
    "story": "feature",
    "feature": "feature",
    "new feature": "feature",
    "improvement": "feature",
    "enhancement": "feature",
    "epic": "feature",
    "task": "feature",
    "sub-task": "feature",
    "refactor": "refactor",
    "refactoring": "refactor",
    "technical debt": "refactor",
    "chore": "refactor",
    "documentation": "docs",
    "docs": "docs",
}

# Priority display labels for dashboard badges
PRIORITY_BADGES: Final[dict[str, str]] = {
    "blocker": "Blocker",
    "critical": "Critical",
    "major": "Major",
    "minor": "Minor",
    "trivial": "Trivial",
    "highest": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "lowest": "Lowest",
}

# Default Jira project key (can be overridden per-request)
DEFAULT_PROJECT_KEY: Final[str] = os.getenv("JIRA_DEFAULT_PROJECT", "SHIP")
