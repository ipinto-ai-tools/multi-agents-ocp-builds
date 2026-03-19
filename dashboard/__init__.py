"""Dashboard module for multi-agent monitoring.

This module provides real-time monitoring capabilities for the Design and Docs agents
through a web-based dashboard interface.
"""

from dashboard.heartbeat import (
    Heartbeat,
    HeartbeatEmitter,
    HeartbeatConfig,
    SessionContext,
    create_emitter,
    emit_heartbeat,
    get_global_emitter
)

from dashboard.enrichers import (
    Enricher,
    EnricherPipeline,
    enrich_heartbeat,
    get_global_pipeline
)

__all__ = [
    # Heartbeat
    "Heartbeat",
    "HeartbeatEmitter",
    "HeartbeatConfig",
    "SessionContext",
    "create_emitter",
    "emit_heartbeat",
    "get_global_emitter",
    # Enrichers
    "Enricher",
    "EnricherPipeline",
    "enrich_heartbeat",
    "get_global_pipeline",
]
