"""High-level memory service wrapping the store and extractor modules.

Provides retrieval and storage of cross-session memories for the
orchestrator.  All store/extractor calls are wrapped in try/except
so that memory failures never crash the pipeline.
"""

from __future__ import annotations

import os

from memory.models import MemoryEntry, MemoryQuery, MemoryType
from memory.store import MemoryStore
from memory.extractor import extract_memories
from utils.file_logger import get_logger

logger = get_logger("memory.service")

_MEMORY_TYPE_LABELS: dict[str, str] = {
    MemoryType.best_practice: "Best Practices",
    MemoryType.anti_pattern: "Anti-Patterns",
    MemoryType.heuristic: "Heuristics",
    MemoryType.execution_note: "Execution Notes",
    MemoryType.reusable_context: "Reusable Context",
}

_MAX_PROMPT_CHARS = 2000


class MemoryService:
    """Facade for retrieving and storing pipeline memories."""

    def __init__(
        self,
        enabled: bool | None = None,
        db_path: str | None = None,
    ) -> None:
        if enabled is None:
            enabled = os.getenv("MEMORY_ENABLED", "false").lower() == "true"

        if enabled:
            self._store: MemoryStore | None = MemoryStore(db_path)
            logger.info("MemoryService enabled")
        else:
            self._store = None
            logger.info("MemoryService disabled")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Return whether the memory service is active."""
        return self._store is not None

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve_for_stage(self, stage: str, context: dict) -> str:
        """Retrieve relevant memories and format as prompt context.

        Returns an empty string when the service is disabled or when no
        memories match the query.
        """
        if not self.enabled:
            return ""

        try:
            query_text = (
                context.get("issue_title", "")
                + " "
                + context.get("issue_description", "")
            ).strip()

            query = MemoryQuery(
                query_text=query_text,
                stage=stage,
                issue_type=context.get("issue_type"),
                max_results=5,
            )

            assert self._store is not None  # guarded by self.enabled
            results = self._store.search(query)
            return self.format_memories_for_prompt(results)
        except Exception:
            logger.exception("Failed to retrieve memories for stage=%s", stage)
            return ""

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def store_from_stage(
        self,
        stage: str,
        context: dict,
        stage_output: dict,
    ) -> list[int]:
        """Extract and store memories from a stage's output.

        Returns the list of stored memory row IDs, or an empty list when
        the service is disabled or an error occurs.
        """
        if not self.enabled:
            return []

        try:
            entries = extract_memories(stage, context, stage_output)
            assert self._store is not None  # guarded by self.enabled
            ids: list[int] = []
            for entry in entries:
                row_id = self._store.store(entry)
                ids.append(row_id)
            logger.info(
                "Stored %d memories from stage=%s", len(ids), stage
            )
            return ids
        except Exception:
            logger.exception("Failed to store memories for stage=%s", stage)
            return []

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def format_memories_for_prompt(memories: list[MemoryEntry]) -> str:
        """Format memories as a Markdown section for prompt injection.

        Memories are grouped by ``memory_type`` and the total output is
        capped at 2000 characters.  Returns an empty string when
        *memories* is empty.
        """
        if not memories:
            return ""

        grouped: dict[str, list[MemoryEntry]] = {}
        for mem in memories:
            label = _MEMORY_TYPE_LABELS.get(mem.memory_type, mem.memory_type)
            grouped.setdefault(label, []).append(mem)

        lines: list[str] = ["## Cross-Session Memory Context", ""]

        for section_label, entries in grouped.items():
            lines.append(f"### {section_label}")
            for entry in entries:
                lines.append(f"- **{entry.title}**: {entry.content}")
            lines.append("")

        output = "\n".join(lines).rstrip()

        if len(output) > _MAX_PROMPT_CHARS:
            output = output[: _MAX_PROMPT_CHARS - 3] + "..."

        return output
