"""Heartbeat protocol for agent state reporting.

This module implements the heartbeat protocol that agents use to report their
state to the dashboard for real-time monitoring.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import requests


class HeartbeatConfig:
    """Configuration for heartbeat emission."""

    def __init__(
        self,
        dashboard_url: str = None,
        enabled: bool = True,
        interval_seconds: int = 3,
        timeout_seconds: int = 2
    ):
        """Initialize heartbeat configuration.

        Args:
            dashboard_url: URL of dashboard API (default: http://localhost:8080)
            enabled: Whether heartbeat emission is enabled
            interval_seconds: How often to emit heartbeats
            timeout_seconds: HTTP request timeout
        """
        self.dashboard_url = dashboard_url or os.getenv(
            "DASHBOARD_URL",
            "http://localhost:8080"
        )
        self.enabled = enabled and os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds


class Heartbeat:
    """Represents an agent heartbeat."""

    def __init__(
        self,
        session_id: str,
        agent: str,
        phase: str,
        raw_state: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ):
        """Create a heartbeat.

        Args:
            session_id: Unique session identifier
            agent: Agent name (design, docs, etc.)
            phase: Current workflow phase
            raw_state: Complete agent state dictionary
            timestamp: Heartbeat timestamp (default: now)
        """
        self.session_id = session_id
        self.agent = agent
        self.phase = phase
        self.raw_state = raw_state
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert heartbeat to dictionary for API transmission.

        Returns:
            Dictionary representation of heartbeat
        """
        return {
            "session_id": self.session_id,
            "agent": self.agent,
            "phase": self.phase,
            "timestamp": self.timestamp.isoformat(),
            "raw_state": self.raw_state
        }


class HeartbeatEmitter:
    """Emits heartbeats to the dashboard API."""

    def __init__(self, config: Optional[HeartbeatConfig] = None):
        """Initialize heartbeat emitter.

        Args:
            config: Heartbeat configuration (default: HeartbeatConfig())
        """
        self.config = config or HeartbeatConfig()
        self.session_id = str(uuid.uuid4())

    def emit(self, heartbeat: Heartbeat) -> bool:
        """Emit a heartbeat to the dashboard.

        Args:
            heartbeat: Heartbeat to emit

        Returns:
            True if emission succeeded, False otherwise
        """
        if not self.config.enabled:
            return False

        try:
            response = requests.post(
                f"{self.config.dashboard_url}/api/heartbeat",
                json=heartbeat.to_dict(),
                timeout=self.config.timeout_seconds
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            # Dashboard not available - fail silently
            return False

    def emit_from_state(
        self,
        agent: str,
        state: Dict[str, Any]
    ) -> bool:
        """Create and emit a heartbeat from agent state.

        Args:
            agent: Agent name
            state: Agent state dictionary

        Returns:
            True if emission succeeded, False otherwise
        """
        heartbeat = Heartbeat(
            session_id=self.session_id,
            agent=agent,
            phase=state.get("current_phase", "unknown"),
            raw_state=state
        )
        return self.emit(heartbeat)


class SessionContext:
    """Context manager for session-scoped heartbeat emission."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        config: Optional[HeartbeatConfig] = None
    ):
        """Initialize session context.

        Args:
            session_id: Session ID (default: auto-generate)
            config: Heartbeat configuration
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.config = config or HeartbeatConfig()
        self.emitter = HeartbeatEmitter(config=self.config)
        self.emitter.session_id = self.session_id

    def __enter__(self):
        """Enter session context."""
        return self.emitter

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit session context - emit final heartbeat if needed."""
        if exc_type is not None:
            # Emit error heartbeat
            error_heartbeat = Heartbeat(
                session_id=self.session_id,
                agent="orchestrator",
                phase="error",
                raw_state={
                    "error": str(exc_val),
                    "error_type": exc_type.__name__
                }
            )
            self.emitter.emit(error_heartbeat)
        return False  # Don't suppress exceptions


def create_emitter(session_id: Optional[str] = None) -> HeartbeatEmitter:
    """Create a heartbeat emitter with optional session ID.

    Args:
        session_id: Session ID (default: auto-generate)

    Returns:
        Configured HeartbeatEmitter
    """
    emitter = HeartbeatEmitter()
    if session_id:
        emitter.session_id = session_id
    return emitter


# Global emitter for convenience (can be overridden per-session)
_global_emitter: Optional[HeartbeatEmitter] = None


def get_global_emitter() -> HeartbeatEmitter:
    """Get or create the global heartbeat emitter.

    Returns:
        Global HeartbeatEmitter instance
    """
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = HeartbeatEmitter()
    return _global_emitter


def emit_heartbeat(agent: str, state: Dict[str, Any]) -> bool:
    """Convenience function to emit a heartbeat using global emitter.

    Args:
        agent: Agent name
        state: Agent state dictionary

    Returns:
        True if emission succeeded, False otherwise
    """
    emitter = get_global_emitter()
    return emitter.emit_from_state(agent, state)
