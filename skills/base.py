import os
from abc import ABC, abstractmethod
from typing import Any


class Skill(ABC):
    name: str
    description: str
    input_schema: dict
    output_schema: dict

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for attr in ("name", "description", "input_schema", "output_schema"):
            if not hasattr(cls, attr):
                raise TypeError(f"{cls.__name__} must define class attribute '{attr}'")

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        if self._is_dry_run():
            return self._mock_response(input)
        return self._execute(input)

    @abstractmethod
    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        ...

    def _mock_response(self, input: dict[str, Any]) -> dict[str, Any]:
        return {}

    def _is_dry_run(self) -> bool:
        return os.getenv("DRY_RUN", "").lower() == "true"
