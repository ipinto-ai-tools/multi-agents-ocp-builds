"""Tests for dashboard components."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from dashboard.heartbeat import (
    Heartbeat,
    HeartbeatEmitter,
    HeartbeatConfig,
    SessionContext,
    create_emitter
)
from dashboard.enrichers import (
    ModelInfoEnricher,
    TokenCountEnricher,
    PhaseStatusEnricher,
    ComponentsEnricher,
    RisksEnricher,
    IssueInfoEnricher,
    TimestampEnricher,
    EnricherPipeline,
    enrich_heartbeat
)


class TestHeartbeat:
    """Tests for Heartbeat class."""

    def test_heartbeat_creation(self):
        """Test creating a heartbeat."""
        state = {
            "issue_title": "Test Issue",
            "current_phase": "design",
            "impacted_components": ["component1", "component2"]
        }

        heartbeat = Heartbeat(
            session_id="test-session",
            agent="design",
            phase="design",
            raw_state=state
        )

        assert heartbeat.session_id == "test-session"
        assert heartbeat.agent == "design"
        assert heartbeat.phase == "design"
        assert heartbeat.raw_state == state

    def test_heartbeat_to_dict(self):
        """Test converting heartbeat to dictionary."""
        state = {"issue_title": "Test"}
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        heartbeat = Heartbeat(
            session_id="test",
            agent="design",
            phase="init",
            raw_state=state,
            timestamp=timestamp
        )

        result = heartbeat.to_dict()

        assert result["session_id"] == "test"
        assert result["agent"] == "design"
        assert result["phase"] == "init"
        assert result["raw_state"] == state
        assert "2024-01-01" in result["timestamp"]


class TestHeartbeatConfig:
    """Tests for HeartbeatConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = HeartbeatConfig()

        assert config.dashboard_url == "http://localhost:8080"
        assert config.enabled is True
        assert config.interval_seconds == 3
        assert config.timeout_seconds == 2

    def test_custom_config(self):
        """Test custom configuration."""
        config = HeartbeatConfig(
            dashboard_url="http://example.com:9000",
            enabled=False,
            interval_seconds=5,
            timeout_seconds=3
        )

        assert config.dashboard_url == "http://example.com:9000"
        assert config.enabled is False
        assert config.interval_seconds == 5
        assert config.timeout_seconds == 3


class TestHeartbeatEmitter:
    """Tests for HeartbeatEmitter."""

    def test_emitter_creation(self):
        """Test creating an emitter."""
        emitter = HeartbeatEmitter()

        assert emitter.config is not None
        assert emitter.session_id is not None

    @patch('requests.post')
    def test_emit_success(self, mock_post):
        """Test successful heartbeat emission."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        emitter = HeartbeatEmitter()
        heartbeat = Heartbeat(
            session_id="test",
            agent="design",
            phase="init",
            raw_state={}
        )

        result = emitter.emit(heartbeat)

        assert result is True
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_emit_disabled(self, mock_post):
        """Test emission when disabled."""
        config = HeartbeatConfig(enabled=False)
        emitter = HeartbeatEmitter(config=config)

        heartbeat = Heartbeat(
            session_id="test",
            agent="design",
            phase="init",
            raw_state={}
        )

        result = emitter.emit(heartbeat)

        assert result is False
        mock_post.assert_not_called()

    @patch('requests.post')
    def test_emit_network_error(self, mock_post):
        """Test emission with network error."""
        mock_post.side_effect = Exception("Network error")

        emitter = HeartbeatEmitter()
        heartbeat = Heartbeat(
            session_id="test",
            agent="design",
            phase="init",
            raw_state={}
        )

        result = emitter.emit(heartbeat)

        assert result is False

    @patch('requests.post')
    def test_emit_from_state(self, mock_post):
        """Test creating and emitting from state."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        emitter = HeartbeatEmitter()
        state = {
            "current_phase": "design",
            "issue_title": "Test Issue"
        }

        result = emitter.emit_from_state("design", state)

        assert result is True
        mock_post.assert_called_once()


class TestSessionContext:
    """Tests for SessionContext."""

    def test_context_manager(self):
        """Test session context manager."""
        with SessionContext(session_id="test-session") as emitter:
            assert emitter.session_id == "test-session"
            assert isinstance(emitter, HeartbeatEmitter)

    @patch('requests.post')
    def test_context_error_handling(self, mock_post):
        """Test error handling in context manager."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with pytest.raises(ValueError):
            with SessionContext(session_id="test"):
                raise ValueError("Test error")

        # Should have emitted error heartbeat
        assert mock_post.called


class TestEnrichers:
    """Tests for enricher classes."""

    def test_model_info_enricher(self):
        """Test ModelInfoEnricher."""
        enricher = ModelInfoEnricher()
        heartbeat = {"session_id": "test"}

        result = enricher.enrich(heartbeat)

        assert "model" in result
        assert "claude" in result["model"].lower()

    def test_token_count_enricher(self):
        """Test TokenCountEnricher."""
        enricher = TokenCountEnricher()
        heartbeat = {
            "session_id": "test",
            "raw_state": {
                "issue_title": "Test Issue",
                "design_analysis": "A" * 1000
            }
        }

        result = enricher.enrich(heartbeat)

        assert "context_tokens" in result
        assert "context_percent" in result
        assert result["context_tokens"] > 0
        assert 0 <= result["context_percent"] <= 100

    def test_phase_status_enricher(self):
        """Test PhaseStatusEnricher."""
        enricher = PhaseStatusEnricher()

        # Test different phases
        test_cases = [
            ("init", "initializing"),
            ("design_complete", "design_done"),
            ("done", "complete"),
            ("error", "error"),
            ("unknown", "in_progress")
        ]

        for phase, expected_status in test_cases:
            heartbeat = {"phase": phase}
            result = enricher.enrich(heartbeat)

            assert result["status"] == expected_status
            assert "phase_display" in result

    def test_components_enricher(self):
        """Test ComponentsEnricher."""
        enricher = ComponentsEnricher()

        # Test with components
        heartbeat = {
            "raw_state": {
                "impacted_components": ["comp1", "comp2", "comp3"]
            }
        }

        result = enricher.enrich(heartbeat)

        assert result["impacted_components"] == ["comp1", "comp2", "comp3"]
        assert result["component_count"] == 3

        # Test without components
        heartbeat = {"raw_state": {}}
        result = enricher.enrich(heartbeat)

        assert result["impacted_components"] == []
        assert result["component_count"] == 0

    def test_risks_enricher(self):
        """Test RisksEnricher."""
        enricher = RisksEnricher()

        # Test different risk levels
        test_cases = [
            ([], "none"),
            (["risk1"], "low"),
            (["risk1", "risk2"], "low"),
            (["risk1", "risk2", "risk3"], "medium"),
            (["r1", "r2", "r3", "r4", "r5"], "medium"),
            (["r1", "r2", "r3", "r4", "r5", "r6"], "high")
        ]

        for risks, expected_level in test_cases:
            heartbeat = {"raw_state": {"risks": risks}}
            result = enricher.enrich(heartbeat)

            assert result["risks"] == risks
            assert result["risk_count"] == len(risks)
            assert result["risk_level"] == expected_level

    def test_issue_info_enricher(self):
        """Test IssueInfoEnricher."""
        enricher = IssueInfoEnricher()

        heartbeat = {
            "raw_state": {
                "issue_title": "Test Issue",
                "issue_type": "feature",
                "issue_description": "Test description"
            }
        }

        result = enricher.enrich(heartbeat)

        assert result["issue_title"] == "Test Issue"
        assert result["issue_type"] == "feature"
        assert result["issue_description"] == "Test description"

    def test_timestamp_enricher(self):
        """Test TimestampEnricher."""
        enricher = TimestampEnricher()

        # Test with valid timestamp
        heartbeat = {
            "timestamp": datetime.utcnow().isoformat()
        }

        result = enricher.enrich(heartbeat)

        assert "timestamp_formatted" in result
        assert "timestamp_relative" in result
        assert "ago" in result["timestamp_relative"]


class TestEnricherPipeline:
    """Tests for EnricherPipeline."""

    def test_default_pipeline(self):
        """Test creating default pipeline."""
        pipeline = EnricherPipeline()

        assert len(pipeline.enrichers) > 0

    def test_custom_pipeline(self):
        """Test creating custom pipeline."""
        enrichers = [ModelInfoEnricher(), TokenCountEnricher()]
        pipeline = EnricherPipeline(enrichers=enrichers)

        assert len(pipeline.enrichers) == 2

    def test_pipeline_processing(self):
        """Test processing heartbeat through pipeline."""
        pipeline = EnricherPipeline()

        heartbeat = {
            "session_id": "test",
            "agent": "design",
            "phase": "init",
            "timestamp": datetime.utcnow().isoformat(),
            "raw_state": {
                "issue_title": "Test Issue",
                "issue_type": "feature",
                "impacted_components": ["comp1"],
                "risks": ["risk1", "risk2"]
            }
        }

        result = pipeline.process(heartbeat)

        # Check all enrichments were applied
        assert "model" in result
        assert "context_tokens" in result
        assert "status" in result
        assert "impacted_components" in result
        assert "risk_level" in result
        assert "issue_title" in result
        assert "timestamp_formatted" in result

    def test_add_enricher(self):
        """Test adding enricher to pipeline."""
        pipeline = EnricherPipeline(enrichers=[])
        assert len(pipeline.enrichers) == 0

        pipeline.add_enricher(ModelInfoEnricher())
        assert len(pipeline.enrichers) == 1

    def test_enrich_heartbeat_convenience(self):
        """Test convenience function."""
        heartbeat = {
            "session_id": "test",
            "agent": "design",
            "phase": "init",
            "timestamp": datetime.utcnow().isoformat(),
            "raw_state": {}
        }

        result = enrich_heartbeat(heartbeat)

        assert "model" in result
        assert "status" in result


class TestCreateEmitter:
    """Tests for create_emitter convenience function."""

    def test_create_emitter_default(self):
        """Test creating emitter with auto-generated session ID."""
        emitter = create_emitter()

        assert emitter.session_id is not None
        assert isinstance(emitter, HeartbeatEmitter)

    def test_create_emitter_with_session_id(self):
        """Test creating emitter with specific session ID."""
        emitter = create_emitter(session_id="custom-session")

        assert emitter.session_id == "custom-session"
