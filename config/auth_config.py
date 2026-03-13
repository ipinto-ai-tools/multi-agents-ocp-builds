"""Authentication configuration for Claude API.

This module provides unified authentication handling for individual API keys,
Claude Enterprise authentication, and Google Vertex AI. All agents should use
get_anthropic_client() to obtain a properly configured Anthropic client.

Supports:
- Google Vertex AI authentication (ANTHROPIC_VERTEX_PROJECT_ID, CLOUD_ML_REGION)
- Claude Enterprise authentication (ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN)
- Individual API key authentication (ANTHROPIC_API_KEY)
- Optional organization ID for enterprise setups (ANTHROPIC_ORG_ID)

Example usage:
    from config.auth_config import get_anthropic_client

    try:
        client = get_anthropic_client()
        response = client.messages.create(...)
    except ValueError as e:
        print(f"Authentication error: {e}")
"""

import os
import logging
from typing import Optional, Union

try:
    from anthropic import Anthropic, AnthropicVertex
except ImportError:
    raise ImportError(
        "anthropic library is required. Install with: uv pip install anthropic"
    )

logger = logging.getLogger(__name__)


def get_anthropic_client() -> Union[Anthropic, AnthropicVertex]:
    """Get configured Anthropic client with Vertex AI, enterprise, or API key authentication.

    Authentication priority:
    1. Google Vertex AI (if CLAUDE_CODE_USE_VERTEX or ANTHROPIC_VERTEX_PROJECT_ID is set)
    2. Claude Enterprise (if ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN is set)
    3. Individual API key (if ANTHROPIC_API_KEY is set)

    Environment Variables:
        # Google Vertex AI (highest priority)
        CLAUDE_CODE_USE_VERTEX: Set to "1" to enable Vertex AI mode
        ANTHROPIC_VERTEX_PROJECT_ID: GCP project ID (required for Vertex AI)
        CLOUD_ML_REGION: GCP region (default: "us-east5")

        # Claude Enterprise
        ANTHROPIC_BASE_URL: Custom base URL for Claude Enterprise
        ANTHROPIC_AUTH_TOKEN: Enterprise authentication token (alternative to API key)
        ANTHROPIC_ORG_ID: Optional organization ID for enterprise

        # Individual API key (fallback)
        ANTHROPIC_API_KEY: Individual API key

    Returns:
        Configured Anthropic or AnthropicVertex client ready to use

    Raises:
        ValueError: If no authentication method is configured or if configuration
                   is incomplete

    Example:
        >>> client = get_anthropic_client()
        >>> response = client.messages.create(
        ...     model="claude-sonnet-4-20250514",
        ...     max_tokens=1024,
        ...     messages=[{"role": "user", "content": "Hello"}]
        ... )
    """
    # Check for Google Vertex AI authentication first
    use_vertex = os.getenv("CLAUDE_CODE_USE_VERTEX") == "1"
    vertex_project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")

    if use_vertex or vertex_project_id:
        return _get_vertex_client(vertex_project_id)

    # Check for enterprise authentication second
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    org_id = os.getenv("ANTHROPIC_ORG_ID")

    if base_url or auth_token:
        return _get_enterprise_client(base_url, auth_token, org_id)

    # Fall back to individual API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        logger.info("Using Claude API key authentication")
        return Anthropic(api_key=api_key)

    # No authentication configured
    raise ValueError(
        "No Claude authentication configured. Please set one of:\n"
        "  - ANTHROPIC_VERTEX_PROJECT_ID for Google Vertex AI authentication\n"
        "  - ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN for enterprise authentication\n"
        "  - ANTHROPIC_API_KEY for individual API key authentication\n"
        "\n"
        "See .env.example for configuration details."
    )


def _get_vertex_client(project_id: Optional[str]) -> AnthropicVertex:
    """Configure AnthropicVertex client for Google Vertex AI.

    Args:
        project_id: GCP project ID (required)

    Returns:
        Configured AnthropicVertex client

    Raises:
        ValueError: If project_id is not provided or client initialization fails
    """
    # Validate project ID is provided
    if not project_id:
        raise ValueError(
            "ANTHROPIC_VERTEX_PROJECT_ID is required for Vertex AI authentication.\n"
            "\n"
            "Please set:\n"
            "  export ANTHROPIC_VERTEX_PROJECT_ID='your-gcp-project-id'\n"
            "  export CLOUD_ML_REGION='us-east5'  # Optional, defaults to us-east5\n"
            "\n"
            "Note: Vertex AI uses gcloud credentials automatically.\n"
            "Make sure you've run: gcloud auth application-default login"
        )

    # Get region (default to us-east5)
    region = os.getenv("CLOUD_ML_REGION", "us-east5")

    # Try to create Vertex AI client
    try:
        client = AnthropicVertex(region=region, project_id=project_id)
        logger.info(
            f"Using Google Vertex AI authentication (project: {project_id}, region: {region})"
        )
        return client
    except Exception as e:
        # Provide helpful error message if gcloud auth not configured
        error_msg = str(e).lower()
        if "credential" in error_msg or "auth" in error_msg or "permission" in error_msg:
            raise ValueError(
                f"Failed to initialize Vertex AI client: {e}\n"
                "\n"
                "This usually means gcloud authentication is not configured.\n"
                "Please run:\n"
                "  gcloud auth application-default login\n"
                "\n"
                "Then verify your project access:\n"
                "  gcloud projects describe {project_id}\n"
            ) from e
        else:
            raise ValueError(
                f"Failed to initialize Vertex AI client: {e}\n"
                "\n"
                "Please verify your Vertex AI configuration:\n"
                "  - ANTHROPIC_VERTEX_PROJECT_ID: {project_id}\n"
                "  - CLOUD_ML_REGION: {region}\n"
                "  - gcloud auth configured: gcloud auth application-default login\n"
            ) from e


def _get_enterprise_client(
    base_url: Optional[str],
    auth_token: Optional[str],
    org_id: Optional[str]
) -> Anthropic:
    """Configure Anthropic client for Claude Enterprise.

    Args:
        base_url: Custom base URL for enterprise endpoint
        auth_token: Enterprise authentication token
        org_id: Optional organization ID

    Returns:
        Configured Anthropic client for enterprise

    Raises:
        ValueError: If enterprise configuration is incomplete
    """
    # Validate enterprise configuration
    if not base_url and not auth_token:
        raise ValueError(
            "Incomplete enterprise configuration. Please set:\n"
            "  - ANTHROPIC_BASE_URL and/or ANTHROPIC_AUTH_TOKEN\n"
            "\n"
            "For enterprise authentication, both values are typically required.\n"
            "See .env.example for configuration details."
        )

    # Build client configuration
    client_kwargs = {}

    if base_url:
        client_kwargs["base_url"] = base_url
        logger.info(f"Using Claude Enterprise authentication (base_url: {base_url})")

    if auth_token:
        # Enterprise uses auth_token as the API key
        client_kwargs["api_key"] = auth_token
        if not base_url:
            logger.info("Using Claude Enterprise authentication (auth_token provided)")
    else:
        # If base_url is set but no auth_token, check for API key
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Enterprise base URL is set but no authentication token provided.\n"
                "Please set either:\n"
                "  - ANTHROPIC_AUTH_TOKEN for enterprise authentication\n"
                "  - ANTHROPIC_API_KEY for standard API key\n"
                "\n"
                "See .env.example for configuration details."
            )
        client_kwargs["api_key"] = api_key

    # Add optional organization ID
    if org_id:
        # Note: The Anthropic SDK may use headers or other mechanisms for org_id
        # This is a placeholder - adjust based on actual SDK requirements
        logger.info(f"Using organization ID: {org_id}")
        # If the SDK supports it, add it here:
        # client_kwargs["organization_id"] = org_id
        # For now, we'll pass it as a default header
        client_kwargs["default_headers"] = {"anthropic-organization": org_id}

    try:
        return Anthropic(**client_kwargs)
    except Exception as e:
        raise ValueError(
            f"Failed to initialize Claude Enterprise client: {e}\n"
            "\n"
            "Please verify your enterprise configuration:\n"
            "  - ANTHROPIC_BASE_URL should be a valid URL\n"
            "  - ANTHROPIC_AUTH_TOKEN should be a valid enterprise token\n"
            "  - ANTHROPIC_ORG_ID (optional) should be your organization ID\n"
        ) from e


def validate_authentication() -> dict:
    """Validate authentication configuration without creating a client.

    This is useful for testing configuration or displaying authentication status.

    Returns:
        Dictionary with authentication details:
            - auth_type: "vertex_ai", "enterprise", "api_key", or "none"
            - has_vertex_project_id: bool
            - has_vertex_region: bool
            - has_base_url: bool
            - has_auth_token: bool
            - has_api_key: bool
            - has_org_id: bool

    Example:
        >>> auth_info = validate_authentication()
        >>> print(f"Authentication type: {auth_info['auth_type']}")
    """
    # Check all environment variables
    use_vertex = os.getenv("CLAUDE_CODE_USE_VERTEX") == "1"
    vertex_project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
    vertex_region = os.getenv("CLOUD_ML_REGION")
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    org_id = os.getenv("ANTHROPIC_ORG_ID")

    # Determine authentication type based on priority
    if use_vertex or vertex_project_id:
        auth_type = "vertex_ai"
    elif base_url or auth_token:
        auth_type = "enterprise"
    elif api_key:
        auth_type = "api_key"
    else:
        auth_type = "none"

    return {
        "auth_type": auth_type,
        "has_vertex_project_id": bool(vertex_project_id),
        "has_vertex_region": bool(vertex_region),
        "has_base_url": bool(base_url),
        "has_auth_token": bool(auth_token),
        "has_api_key": bool(api_key),
        "has_org_id": bool(org_id),
    }
