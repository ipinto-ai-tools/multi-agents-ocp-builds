"""Helper to check if Vertex AI authentication is available for tests."""
import os


def has_anthropic_auth() -> bool:
    """Check if Vertex AI authentication is configured and usable."""
    if os.getenv("ANTHROPIC_VERTEX_PROJECT_ID"):
        try:
            import google.auth
            return True
        except ImportError:
            return False
    return False


HAS_ANTHROPIC_AUTH = has_anthropic_auth()
