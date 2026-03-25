from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skills.base import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, "Skill"] = {}

    def register(self, skill: "Skill") -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> "Skill":
        if name not in self._skills:
            raise KeyError(
                f"Skill '{name}' not found. Available: {list(self._skills)}"
            )
        return self._skills[name]

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())
