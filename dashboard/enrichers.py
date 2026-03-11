"""Enricher framework for processing agent heartbeats.

This module implements the enricher pattern for extracting structured
information from raw agent state in heartbeats.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime


class Enricher(ABC):
    """Base class for heartbeat enrichers."""

    @abstractmethod
    def enrich(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a heartbeat with additional structured data.

        Args:
            heartbeat: Raw heartbeat dictionary

        Returns:
            Enriched heartbeat dictionary
        """
        pass


class ModelInfoEnricher(Enricher):
    """Extracts model information from agent state."""

    def enrich(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Extract model information.

        Args:
            heartbeat: Raw heartbeat

        Returns:
            Heartbeat with model field added
        """
        # Default model from environment or hardcoded
        heartbeat["model"] = "claude-sonnet-4-20250514"
        return heartbeat


class TokenCountEnricher(Enricher):
    """Estimates token count and context percentage from state."""

    MAX_TOKENS = 200000  # Claude's context window

    def enrich(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate token usage metrics.

        Args:
            heartbeat: Raw heartbeat

        Returns:
            Heartbeat with token metrics added
        """
        # Rough estimation: 1 char ≈ 0.75 tokens
        raw_state = heartbeat.get("raw_state", {})
        state_str = str(raw_state)
        estimated_tokens = int(len(state_str) * 0.75)

        # Add design analysis content if available (major contributor to tokens)
        design_analysis = raw_state.get("design_analysis", "")
        if design_analysis:
            estimated_tokens += int(len(design_analysis) * 0.75)

        # Add docs output if available
        pr_summary = raw_state.get("pr_summary", "")
        if pr_summary:
            estimated_tokens += int(len(pr_summary) * 0.75)

        context_percent = (estimated_tokens / self.MAX_TOKENS) * 100

        heartbeat["context_tokens"] = estimated_tokens
        heartbeat["context_percent"] = round(context_percent, 1)

        return heartbeat


class PhaseStatusEnricher(Enricher):
    """Converts phase to user-friendly status."""

    PHASE_TO_STATUS = {
        "init": "initializing",
        "design_complete": "design_done",
        "testing_complete": "testing_done",
        "done": "complete",
        "error": "error"
    }

    def enrich(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize phase status.

        Args:
            heartbeat: Raw heartbeat

        Returns:
            Heartbeat with status field added
        """
        phase = heartbeat.get("phase", "unknown")
        status = self.PHASE_TO_STATUS.get(phase, "in_progress")

        heartbeat["status"] = status
        heartbeat["phase_display"] = phase.replace("_", " ").title()

        return heartbeat


class ComponentsEnricher(Enricher):
    """Extracts impacted components from agent state."""

    def enrich(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Extract impacted components.

        Args:
            heartbeat: Raw heartbeat

        Returns:
            Heartbeat with components field added
        """
        raw_state = heartbeat.get("raw_state", {})
        components = raw_state.get("impacted_components", [])

        # Ensure it's a list
        if not isinstance(components, list):
            components = []

        heartbeat["impacted_components"] = components
        heartbeat["component_count"] = len(components)

        return heartbeat


class RisksEnricher(Enricher):
    """Extracts risk information from agent state."""

    def enrich(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Extract risk information.

        Args:
            heartbeat: Raw heartbeat

        Returns:
            Heartbeat with risks field added
        """
        raw_state = heartbeat.get("raw_state", {})
        risks = raw_state.get("risks", [])

        # Ensure it's a list
        if not isinstance(risks, list):
            risks = []

        heartbeat["risks"] = risks
        heartbeat["risk_count"] = len(risks)

        # Add risk level based on count
        if len(risks) == 0:
            risk_level = "none"
        elif len(risks) <= 2:
            risk_level = "low"
        elif len(risks) <= 5:
            risk_level = "medium"
        else:
            risk_level = "high"

        heartbeat["risk_level"] = risk_level

        return heartbeat


class IssueInfoEnricher(Enricher):
    """Extracts issue/task information from agent state."""

    def enrich(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Extract issue information.

        Args:
            heartbeat: Raw heartbeat

        Returns:
            Heartbeat with issue info added
        """
        raw_state = heartbeat.get("raw_state", {})

        heartbeat["issue_title"] = raw_state.get("issue_title", "Unknown Task")
        heartbeat["issue_type"] = raw_state.get("issue_type", "feature")
        heartbeat["issue_description"] = raw_state.get("issue_description", "")

        return heartbeat


class TimestampEnricher(Enricher):
    """Adds formatted timestamp information."""

    def enrich(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Add formatted timestamps.

        Args:
            heartbeat: Raw heartbeat

        Returns:
            Heartbeat with formatted timestamp fields
        """
        timestamp_str = heartbeat.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                heartbeat["timestamp_formatted"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                heartbeat["timestamp_relative"] = self._relative_time(timestamp)
            except (ValueError, AttributeError):
                heartbeat["timestamp_formatted"] = "Unknown"
                heartbeat["timestamp_relative"] = "Unknown"

        return heartbeat

    def _relative_time(self, timestamp: datetime) -> str:
        """Calculate relative time from now.

        Args:
            timestamp: Timestamp to compare

        Returns:
            Human-readable relative time (e.g., "2m ago")
        """
        now = datetime.utcnow()
        diff = now - timestamp

        seconds = diff.total_seconds()
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        else:
            return f"{int(seconds / 86400)}d ago"


class EnricherPipeline:
    """Pipeline of enrichers to process heartbeats."""

    def __init__(self, enrichers: List[Enricher] = None):
        """Initialize enricher pipeline.

        Args:
            enrichers: List of enrichers to apply (default: standard pipeline)
        """
        if enrichers is None:
            enrichers = self._create_default_pipeline()
        self.enrichers = enrichers

    def _create_default_pipeline(self) -> List[Enricher]:
        """Create the default enricher pipeline.

        Returns:
            List of enrichers in application order
        """
        return [
            ModelInfoEnricher(),
            TokenCountEnricher(),
            PhaseStatusEnricher(),
            ComponentsEnricher(),
            RisksEnricher(),
            IssueInfoEnricher(),
            TimestampEnricher()
        ]

    def process(self, heartbeat: Dict[str, Any]) -> Dict[str, Any]:
        """Process a heartbeat through all enrichers.

        Args:
            heartbeat: Raw heartbeat dictionary

        Returns:
            Fully enriched heartbeat
        """
        enriched = heartbeat.copy()

        for enricher in self.enrichers:
            enriched = enricher.enrich(enriched)

        return enriched

    def add_enricher(self, enricher: Enricher):
        """Add an enricher to the pipeline.

        Args:
            enricher: Enricher to add
        """
        self.enrichers.append(enricher)


# Global pipeline instance
_global_pipeline: Optional[EnricherPipeline] = None


def get_global_pipeline() -> EnricherPipeline:
    """Get or create the global enricher pipeline.

    Returns:
        Global EnricherPipeline instance
    """
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = EnricherPipeline()
    return _global_pipeline


def enrich_heartbeat(heartbeat: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to enrich a heartbeat using global pipeline.

    Args:
        heartbeat: Raw heartbeat dictionary

    Returns:
        Enriched heartbeat
    """
    pipeline = get_global_pipeline()
    return pipeline.process(heartbeat)
