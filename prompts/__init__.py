"""System prompts for each pipeline stage."""

from prompts.code_review import CODE_REVIEW_AGENT_PROMPT
from prompts.design import DESIGN_AGENT_PROMPT
from prompts.develop import DEVELOPMENT_AGENT_PROMPT
from prompts.docs import DOCS_AGENT_PROMPT
from prompts.test import TESTING_AGENT_PROMPT

__all__ = [
    "CODE_REVIEW_AGENT_PROMPT",
    "DESIGN_AGENT_PROMPT",
    "DEVELOPMENT_AGENT_PROMPT",
    "DOCS_AGENT_PROMPT",
    "TESTING_AGENT_PROMPT",
]
