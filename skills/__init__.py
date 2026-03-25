from skills.base import Skill
from skills.registry import SkillRegistry
from skills.jira import FetchJiraTicketSkill, UpdateJiraSkill
from skills.github import FetchGitHubPRsSkill

# Default registry pre-populated with all skills.
# Constructed here (not in registry.py) to avoid mid-module imports.
default_registry = SkillRegistry()
default_registry.register(FetchJiraTicketSkill())
default_registry.register(UpdateJiraSkill())
default_registry.register(FetchGitHubPRsSkill())

__all__ = ["Skill", "SkillRegistry", "default_registry"]
