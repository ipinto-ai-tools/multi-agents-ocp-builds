"""Tests for authentication configuration module.

This module tests the auth_config module to ensure it correctly handles
Google Vertex AI, Claude Enterprise, and individual API key authentication.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from config.auth_config import (
    get_anthropic_client,
    validate_authentication,
    _get_enterprise_client,
    _get_vertex_client,
)


class TestGetAnthropicClient:
    """Test cases for get_anthropic_client function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_no_auth_configured_raises_error(self):
        """Test that ValueError is raised when no authentication is configured."""
        with pytest.raises(ValueError) as exc_info:
            get_anthropic_client()

        assert "No Claude authentication configured" in str(exc_info.value)
        assert "ANTHROPIC_VERTEX_PROJECT_ID" in str(exc_info.value)
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)
        assert "ANTHROPIC_BASE_URL" in str(exc_info.value)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-api-key"}, clear=True)
    @patch("config.auth_config.Anthropic")
    def test_api_key_authentication(self, mock_anthropic):
        """Test authentication with individual API key."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = get_anthropic_client()

        mock_anthropic.assert_called_once_with(api_key="test-api-key")
        assert client == mock_client

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_BASE_URL": "https://api.enterprise.com",
            "ANTHROPIC_AUTH_TOKEN": "enterprise-token",
        },
        clear=True,
    )
    @patch("config.auth_config.Anthropic")
    def test_enterprise_authentication_with_both(self, mock_anthropic):
        """Test enterprise authentication with both base_url and auth_token."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = get_anthropic_client()

        mock_anthropic.assert_called_once_with(
            base_url="https://api.enterprise.com",
            api_key="enterprise-token",
        )
        assert client == mock_client

    @patch.dict(
        os.environ,
        {"ANTHROPIC_BASE_URL": "https://api.enterprise.com"},
        clear=True,
    )
    def test_enterprise_with_base_url_only_raises_error(self):
        """Test that base_url without auth raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_anthropic_client()

        assert "no authentication token provided" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_BASE_URL": "https://api.enterprise.com",
            "ANTHROPIC_API_KEY": "fallback-key",
        },
        clear=True,
    )
    @patch("config.auth_config.Anthropic")
    def test_enterprise_base_url_with_api_key_fallback(self, mock_anthropic):
        """Test that API key is used as fallback when base_url set but no auth_token."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = get_anthropic_client()

        mock_anthropic.assert_called_once_with(
            base_url="https://api.enterprise.com",
            api_key="fallback-key",
        )
        assert client == mock_client

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_BASE_URL": "https://api.enterprise.com",
            "ANTHROPIC_AUTH_TOKEN": "enterprise-token",
            "ANTHROPIC_ORG_ID": "org-123",
        },
        clear=True,
    )
    @patch("config.auth_config.Anthropic")
    def test_enterprise_with_org_id(self, mock_anthropic):
        """Test enterprise authentication with organization ID."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = get_anthropic_client()

        mock_anthropic.assert_called_once_with(
            base_url="https://api.enterprise.com",
            api_key="enterprise-token",
            default_headers={"anthropic-organization": "org-123"},
        )
        assert client == mock_client

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project",
            "CLOUD_ML_REGION": "us-east5",
        },
        clear=True,
    )
    @patch("config.auth_config.AnthropicVertex")
    def test_vertex_ai_authentication(self, mock_vertex):
        """Test Google Vertex AI authentication."""
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
        {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project",
        },
        clear=True,
    )
    @patch("config.auth_config.AnthropicVertex")
    def test_vertex_ai_with_flag(self, mock_vertex):
        """Test Vertex AI authentication with CLAUDE_CODE_USE_VERTEX flag."""
        mock_client = MagicMock()
        mock_vertex.return_value = mock_client

        client = get_anthropic_client()

        # Should use default region
        mock_vertex.assert_called_once_with(
            region="us-east5",
            project_id="my-gcp-project",
        )
        assert client == mock_client

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project",
            "ANTHROPIC_API_KEY": "api-key",
            "ANTHROPIC_BASE_URL": "https://enterprise.com",
        },
        clear=True,
    )
    @patch("config.auth_config.AnthropicVertex")
    def test_vertex_ai_takes_precedence(self, mock_vertex):
        """Test that Vertex AI takes precedence over other auth methods."""
        mock_client = MagicMock()
        mock_vertex.return_value = mock_client

        client = get_anthropic_client()

        # Should use Vertex AI, not enterprise or API key
        mock_vertex.assert_called_once_with(
            region="us-east5",
            project_id="my-gcp-project",
        )
        assert client == mock_client

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_API_KEY": "api-key",
            "ANTHROPIC_BASE_URL": "https://api.enterprise.com",
        },
        clear=True,
    )
    @patch("config.auth_config.Anthropic")
    def test_enterprise_takes_precedence_over_api_key(self, mock_anthropic):
        """Test that enterprise settings take precedence over API key."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = get_anthropic_client()

        # Should use base_url with api_key (enterprise mode)
        mock_anthropic.assert_called_once_with(
            base_url="https://api.enterprise.com",
            api_key="api-key",
        )
        assert client == mock_client


class TestGetVertexClient:
    """Test cases for _get_vertex_client function."""

    def test_no_project_id_raises_error(self):
        """Test that missing project_id raises error."""
        with pytest.raises(ValueError) as exc_info:
            _get_vertex_client(project_id=None)

        assert "ANTHROPIC_VERTEX_PROJECT_ID is required" in str(exc_info.value)
        assert "gcloud auth application-default login" in str(exc_info.value)

    @patch.dict(os.environ, {"CLOUD_ML_REGION": "us-central1"}, clear=True)
    @patch("config.auth_config.AnthropicVertex")
    def test_vertex_with_custom_region(self, mock_vertex):
        """Test Vertex AI client with custom region."""
        mock_client = MagicMock()
        mock_vertex.return_value = mock_client

        client = _get_vertex_client(project_id="test-project")

        mock_vertex.assert_called_once_with(
            region="us-central1",
            project_id="test-project",
        )
        assert client == mock_client

    @patch.dict(os.environ, {}, clear=True)
    @patch("config.auth_config.AnthropicVertex")
    def test_vertex_default_region(self, mock_vertex):
        """Test Vertex AI client uses default region when not specified."""
        mock_client = MagicMock()
        mock_vertex.return_value = mock_client

        client = _get_vertex_client(project_id="test-project")

        mock_vertex.assert_called_once_with(
            region="us-east5",
            project_id="test-project",
        )
        assert client == mock_client

    @patch("config.auth_config.AnthropicVertex", side_effect=Exception("Unauthorized"))
    def test_vertex_auth_error_helpful_message(self, mock_vertex):
        """Test that auth errors provide helpful message."""
        with pytest.raises(ValueError) as exc_info:
            _get_vertex_client(project_id="test-project")

        error_msg = str(exc_info.value)
        assert "gcloud auth application-default login" in error_msg
        assert "Unauthorized" in error_msg

    @patch("config.auth_config.AnthropicVertex", side_effect=Exception("Invalid region"))
    def test_vertex_other_error_helpful_message(self, mock_vertex):
        """Test that non-auth errors provide helpful message."""
        with pytest.raises(ValueError) as exc_info:
            _get_vertex_client(project_id="test-project")

        error_msg = str(exc_info.value)
        assert "Invalid region" in error_msg
        assert "verify your Vertex AI configuration" in error_msg


class TestValidateAuthentication:
    """Test cases for validate_authentication function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_no_auth_configured(self):
        """Test validation with no authentication configured."""
        result = validate_authentication()

        assert result["auth_type"] == "none"
        assert result["has_vertex_project_id"] is False
        assert result["has_vertex_region"] is False
        assert result["has_base_url"] is False
        assert result["has_auth_token"] is False
        assert result["has_api_key"] is False
        assert result["has_org_id"] is False

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True)
    def test_api_key_validation(self):
        """Test validation with API key configured."""
        result = validate_authentication()

        assert result["auth_type"] == "api_key"
        assert result["has_vertex_project_id"] is False
        assert result["has_vertex_region"] is False
        assert result["has_base_url"] is False
        assert result["has_auth_token"] is False
        assert result["has_api_key"] is True
        assert result["has_org_id"] is False

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_BASE_URL": "https://api.enterprise.com",
            "ANTHROPIC_AUTH_TOKEN": "token",
        },
        clear=True,
    )
    def test_enterprise_validation(self):
        """Test validation with enterprise configured."""
        result = validate_authentication()

        assert result["auth_type"] == "enterprise"
        assert result["has_vertex_project_id"] is False
        assert result["has_vertex_region"] is False
        assert result["has_base_url"] is True
        assert result["has_auth_token"] is True
        assert result["has_api_key"] is False
        assert result["has_org_id"] is False

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_VERTEX_PROJECT_ID": "gcp-project",
            "CLOUD_ML_REGION": "us-east5",
        },
        clear=True,
    )
    def test_vertex_ai_validation(self):
        """Test validation with Vertex AI configured."""
        result = validate_authentication()

        assert result["auth_type"] == "vertex_ai"
        assert result["has_vertex_project_id"] is True
        assert result["has_vertex_region"] is True
        assert result["has_base_url"] is False
        assert result["has_auth_token"] is False
        assert result["has_api_key"] is False
        assert result["has_org_id"] is False

    @patch.dict(
        os.environ,
        {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "gcp-project",
        },
        clear=True,
    )
    def test_vertex_ai_validation_with_flag(self):
        """Test validation with Vertex AI flag enabled."""
        result = validate_authentication()

        assert result["auth_type"] == "vertex_ai"
        assert result["has_vertex_project_id"] is True
        assert result["has_vertex_region"] is False  # Not set explicitly

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_VERTEX_PROJECT_ID": "gcp-project",
            "CLOUD_ML_REGION": "us-east5",
            "ANTHROPIC_BASE_URL": "https://api.enterprise.com",
            "ANTHROPIC_AUTH_TOKEN": "token",
            "ANTHROPIC_ORG_ID": "org-123",
            "ANTHROPIC_API_KEY": "key",
        },
        clear=True,
    )
    def test_all_fields_validation_vertex_priority(self):
        """Test validation with all fields - Vertex AI should take priority."""
        result = validate_authentication()

        assert result["auth_type"] == "vertex_ai"
        assert result["has_vertex_project_id"] is True
        assert result["has_vertex_region"] is True
        assert result["has_base_url"] is True
        assert result["has_auth_token"] is True
        assert result["has_api_key"] is True
        assert result["has_org_id"] is True


class TestGetEnterpriseClient:
    """Test cases for _get_enterprise_client function."""

    @patch("config.auth_config.Anthropic")
    def test_valid_enterprise_config(self, mock_anthropic):
        """Test enterprise client with valid configuration."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = _get_enterprise_client(
            base_url="https://api.enterprise.com",
            auth_token="token",
            org_id=None,
        )

        mock_anthropic.assert_called_once_with(
            base_url="https://api.enterprise.com",
            api_key="token",
        )
        assert client == mock_client

    def test_no_base_url_or_token_raises_error(self):
        """Test that missing both base_url and auth_token raises error."""
        with pytest.raises(ValueError) as exc_info:
            _get_enterprise_client(
                base_url=None,
                auth_token=None,
                org_id=None,
            )

        assert "Incomplete enterprise configuration" in str(exc_info.value)

    @patch("config.auth_config.Anthropic")
    def test_enterprise_with_org_id(self, mock_anthropic):
        """Test enterprise client with organization ID."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = _get_enterprise_client(
            base_url="https://api.enterprise.com",
            auth_token="token",
            org_id="org-123",
        )

        mock_anthropic.assert_called_once_with(
            base_url="https://api.enterprise.com",
            api_key="token",
            default_headers={"anthropic-organization": "org-123"},
        )
        assert client == mock_client

    @patch("config.auth_config.Anthropic", side_effect=Exception("SDK Error"))
    def test_client_creation_failure(self, mock_anthropic):
        """Test that client creation failure is properly handled."""
        with pytest.raises(ValueError) as exc_info:
            _get_enterprise_client(
                base_url="https://api.enterprise.com",
                auth_token="token",
                org_id=None,
            )

        assert "Failed to initialize Claude Enterprise client" in str(exc_info.value)
        assert "SDK Error" in str(exc_info.value)
