"""Authentication configuration for Claude API via Google Vertex AI.

This module provides unified authentication handling for Google Vertex AI.
All agents should use get_anthropic_client() to obtain a properly configured
AnthropicVertex client.

Supports:
- Google Vertex AI authentication (ANTHROPIC_VERTEX_PROJECT_ID, CLOUD_ML_REGION)

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

from dotenv import load_dotenv, find_dotenv

# Load .env file - find_dotenv() walks up directories to locate it
load_dotenv(find_dotenv())

try:
    from anthropic import AnthropicVertex
except ImportError:
    raise ImportError(
        "anthropic library is required. Install with: uv pip install anthropic"
    )

logger = logging.getLogger(__name__)


def get_anthropic_client() -> AnthropicVertex:
    """Get configured AnthropicVertex client for Google Vertex AI authentication.

    Environment Variables:
        CLAUDE_CODE_USE_VERTEX: Set to "1" to enable Vertex AI mode
        ANTHROPIC_VERTEX_PROJECT_ID: GCP project ID (required)
        CLOUD_ML_REGION: GCP region (default: "us-east5")

    Returns:
        Configured AnthropicVertex client ready to use

    Raises:
        ValueError: If authentication is not configured or if initialization fails

    """
    use_vertex = os.getenv("CLAUDE_CODE_USE_VERTEX") == "1"
    project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
    region = os.getenv("CLOUD_ML_REGION", "us-east5")
 
    if not project_id and not use_vertex:
        raise ValueError(
            "No Claude authentication configured. Please set:\n"
            "  export ANTHROPIC_VERTEX_PROJECT_ID='your-gcp-project-id'\n"
            "  export CLOUD_ML_REGION='us-east5'  # Optional, defaults to us-east5\n"
            "\n"
            "Note: Vertex AI uses gcloud credentials automatically.\n"
            "Make sure you've run: gcloud auth application-default login\n"
            "\n"
            "See .env.example for configuration details."
        )
           
    try:
        client = AnthropicVertex(region=region, project_id=project_id)
        logger.info(
            f"Using Google Vertex AI authentication (project: {project_id}, region: {region})"
        )
        return client
    except Exception as e:
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
                f"  gcloud projects describe {project_id}\n"
            ) from e
        else:
            raise ValueError(
                f"Failed to initialize Vertex AI client: {e}\n"
                "\n"
                "Please verify your Vertex AI configuration:\n"
                f"  - ANTHROPIC_VERTEX_PROJECT_ID: {project_id}\n"
                f"  - CLOUD_ML_REGION: {region}\n"
                "  - gcloud auth configured: gcloud auth application-default login\n"
            ) from e


def validate_authentication() -> dict:
    """Validate authentication configuration without creating a client.

    This is useful for testing configuration or displaying authentication status.

    Returns:
        Dictionary with authentication details:
            - auth_type: "vertex_ai" or "none"
            - has_vertex_project_id: bool
            - has_vertex_region: bool

    Example:
        >>> auth_info = validate_authentication()
        >>> print(f"Authentication type: {auth_info['auth_type']}")
    """
    use_vertex = os.getenv("CLAUDE_CODE_USE_VERTEX") == "1"
    vertex_project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
    vertex_region = os.getenv("CLOUD_ML_REGION")

    if use_vertex or vertex_project_id:
        auth_type = "vertex_ai"
    else:
        auth_type = "none"

    return {
        "auth_type": auth_type,
        "has_vertex_project_id": bool(vertex_project_id),
        "has_vertex_region": bool(vertex_region),
    }
