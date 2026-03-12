#!/usr/bin/env python3
"""Example of using the authentication configuration module.

This example demonstrates how to use Google Vertex AI, Claude Enterprise,
and individual API key authentication with the multi-agent system.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.auth_config import get_anthropic_client, validate_authentication


def main():
    """Demonstrate authentication configuration."""

    print("=" * 80)
    print("Authentication Configuration Example")
    print("=" * 80)

    # Check current authentication configuration
    print("\n1. Validating authentication configuration...")
    auth_info = validate_authentication()

    print(f"   Authentication Type: {auth_info['auth_type']}")
    print(f"   Has Vertex AI Project ID: {auth_info['has_vertex_project_id']}")
    print(f"   Has Vertex AI Region: {auth_info['has_vertex_region']}")
    print(f"   Has API Key: {auth_info['has_api_key']}")
    print(f"   Has Base URL: {auth_info['has_base_url']}")
    print(f"   Has Auth Token: {auth_info['has_auth_token']}")
    print(f"   Has Org ID: {auth_info['has_org_id']}")

    # Try to get a client
    print("\n2. Attempting to get Anthropic client...")
    try:
        client = get_anthropic_client()
        print("   ✓ Successfully initialized Anthropic client")
        print(f"   Client type: {type(client).__name__}")

        # Optional: Test the client with a simple API call
        # Uncomment to test (will use API credits):
        # print("\n3. Testing client with a simple API call...")
        # response = client.messages.create(
        #     model="claude-sonnet-4-20250514",
        #     max_tokens=100,
        #     messages=[{"role": "user", "content": "Say hello!"}]
        # )
        # print(f"   Response: {response.content[0].text}")

    except ValueError as e:
        print(f"   ✗ Authentication error: {e}")
        print("\n   To fix this, set one of:")
        print("   - ANTHROPIC_VERTEX_PROJECT_ID for Google Vertex AI")
        print("   - ANTHROPIC_API_KEY for individual API key authentication")
        print("   - ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN for enterprise")
        return 1
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        return 1

    print("\n" + "=" * 80)
    print("Configuration Examples:")
    print("=" * 80)

    print("\n# Google Vertex AI (Highest Priority):")
    print("export ANTHROPIC_VERTEX_PROJECT_ID='my-gcp-project-id'")
    print("export CLOUD_ML_REGION='us-east5'  # Optional, defaults to us-east5")
    print("# Note: Uses gcloud auth automatically - run: gcloud auth application-default login")

    print("\n# Claude Enterprise:")
    print("export ANTHROPIC_BASE_URL='https://api.claude.yourcompany.com'")
    print("export ANTHROPIC_AUTH_TOKEN='enterprise-token-...'")
    print("export ANTHROPIC_ORG_ID='org-123'  # Optional")

    print("\n# Individual API Key (Standard):")
    print("export ANTHROPIC_API_KEY='sk-ant-...'")

    print("\n# Or use .env file:")
    print("cp .env.example .env")
    print("# Edit .env and set your credentials")

    print("\n" + "=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
