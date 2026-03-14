"""Tests for authentication configuration module.

This module tests the auth_config module to ensure it correctly handles
Google Vertex AI authentication.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from config.auth_config import (
    get_anthropic_client,
    validate_authentication,
)


class TestGetAnthropicClient:
    """Test cases for get_anthropic_client function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_no_auth_configured(self):
        """Test that ValueError is raised when no authentication is configured."""
        with pytest.raises(ValueError) as exc_info:
            get_anthropic_client()

        assert "No Claude authentication configured" in str(exc_info.value)
        assert "ANTHROPIC_VERTEX_PROJECT_ID" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project",
            "CLOUD_ML_REGION": "us-east5",
        },
        clear=True,
    )
    @patch("config.auth_config.AnthropicVertex")
    def test_get_vertex_client_success(self, mock_vertex):
        """Test successful Vertex AI client creation."""
        mock_client = MagicMock()
        mock_vertex.return_value = mock_client

        client = get_anthropic_client()

        mock_vertex.assert_called_once_with(
            region="us-east5",
            project_id="my-gcp-project",
        )
        assert client == mock_client

    @patch.dict(os.environ, {}, clear=True)
    def test_get_vertex_client_no_project_id(self):
        """Test that missing project_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_anthropic_client()

        assert "ANTHROPIC_VERTEX_PROJECT_ID" in str(exc_info.value)
        assert "gcloud auth application-default login" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project",
            "CLOUD_ML_REGION": "europe-west1",
        },
        clear=True,
    )
    @patch("config.auth_config.AnthropicVertex")
    def test_get_vertex_client_custom_region(self, mock_vertex):
        """Test Vertex AI client with custom CLOUD_ML_REGION."""
        mock_client = MagicMock()
        mock_vertex.return_value = mock_client

        client = get_anthropic_client()

        mock_vertex.assert_called_once_with(
            region="europe-west1",
            project_id="my-gcp-project",
        )
        assert client == mock_client

    @patch.dict(
        os.environ,
        {"ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project"},
        clear=True,
    )
    @patch("config.auth_config.AnthropicVertex")
    def test_get_vertex_client_default_region(self, mock_vertex):
        """Test Vertex AI client defaults to us-east5 when CLOUD_ML_REGION not set."""
        mock_client = MagicMock()
        mock_vertex.return_value = mock_client

        client = get_anthropic_client()

        mock_vertex.assert_called_once_with(
            region="us-east5",
            project_id="my-gcp-project",
        )
        assert client == mock_client

    @patch.dict(
        os.environ,
        {"ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project"},
        clear=True,
    )
    @patch(
        "config.auth_config.AnthropicVertex",
        side_effect=Exception("credential error: unauthorized"),
    )
    def test_get_vertex_client_auth_error(self, mock_vertex):
        """Test helpful error message when gcloud auth is not configured."""
        with pytest.raises(ValueError) as exc_info:
            get_anthropic_client()

        error_msg = str(exc_info.value)
        assert "gcloud auth application-default login" in error_msg
        assert "credential error: unauthorized" in error_msg

    @patch.dict(
        os.environ,
        {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project",
        },
        clear=True,
    )
    @patch("config.auth_config.AnthropicVertex")
    def test_get_vertex_client_with_claude_code_use_vertex(self, mock_vertex):
        """Test Vertex AI client creation with CLAUDE_CODE_USE_VERTEX=1 flag."""
        mock_client = MagicMock()
        mock_vertex.return_value = mock_client

        client = get_anthropic_client()

        mock_vertex.assert_called_once_with(
            region="us-east5",
            project_id="my-gcp-project",
        )
        assert client == mock_client

    @patch.dict(
        os.environ,
        {"CLAUDE_CODE_USE_VERTEX": "1"},
        clear=True,
    )
    def test_get_vertex_client_use_vertex_flag_without_project_id(self):
        """Test that CLAUDE_CODE_USE_VERTEX=1 without project_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_anthropic_client()

        assert "ANTHROPIC_VERTEX_PROJECT_ID is required" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {"ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project"},
        clear=True,
    )
    @patch(
        "config.auth_config.AnthropicVertex",
        side_effect=Exception("Invalid region specified"),
    )
    def test_get_vertex_client_non_auth_error(self, mock_vertex):
        """Test helpful error for non-auth failures (e.g., invalid region)."""
        with pytest.raises(ValueError) as exc_info:
            get_anthropic_client()

        error_msg = str(exc_info.value)
        assert "Invalid region specified" in error_msg
        assert "verify your Vertex AI configuration" in error_msg


class TestValidateAuthentication:
    """Test cases for validate_authentication function."""

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_VERTEX_PROJECT_ID": "gcp-project",
            "CLOUD_ML_REGION": "us-east5",
        },
        clear=True,
    )
    def test_validate_authentication_vertex(self):
        """Test validation returns correct dict for Vertex AI."""
        result = validate_authentication()

        assert result["auth_type"] == "vertex_ai"
        assert result["has_vertex_project_id"] is True
        assert result["has_vertex_region"] is True

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_authentication_none(self):
        """Test validation returns auth_type 'none' when nothing configured."""
        result = validate_authentication()

        assert result["auth_type"] == "none"
        assert result["has_vertex_project_id"] is False
        assert result["has_vertex_region"] is False

    @patch.dict(
        os.environ,
        {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "gcp-project",
        },
        clear=True,
    )
    def test_validate_authentication_vertex_with_flag(self):
        """Test validation with CLAUDE_CODE_USE_VERTEX flag enabled."""
        result = validate_authentication()

        assert result["auth_type"] == "vertex_ai"
        assert result["has_vertex_project_id"] is True
        assert result["has_vertex_region"] is False  # Not set explicitly

    @patch.dict(
        os.environ,
        {"ANTHROPIC_VERTEX_PROJECT_ID": "gcp-project"},
        clear=True,
    )
    def test_validate_authentication_vertex_no_region(self):
        """Test validation when project ID set but region not explicitly set."""
        result = validate_authentication()

        assert result["auth_type"] == "vertex_ai"
        assert result["has_vertex_project_id"] is True
        assert result["has_vertex_region"] is False
