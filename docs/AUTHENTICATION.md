# Authentication Configuration

This document describes how to configure authentication for the Multi-Agent OpenShift Builds system.

## Overview

The system supports three authentication methods:

1. **Google Vertex AI** (recommended) - Uses GCP authentication, no API keys needed
2. **Individual API Key** - Standard Anthropic API key for individual developers
3. **Custom Enterprise Endpoint** - Custom enterprise authentication with organization-specific endpoints

## Quick Start

### Google Vertex AI (Recommended)

**No API keys needed!** Vertex AI uses gcloud authentication.

**Step 1: Install Google Cloud CLI**

Follow the installation guide: https://cloud.google.com/sdk/docs/install

**Step 2: Authenticate with gcloud**

```bash
# Authenticate your Google account
gcloud auth application-default login

# Set quota project (replace with your GCP project ID)
gcloud auth application-default set-quota-project your-gcp-project-id
```

**Step 3: Configure environment**

Add to `.env` file:
```bash
cp .env.example .env
# Edit .env and set:
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=  # Optional, defaults to us-east5
```

Or set environment variables:
```bash
export ANTHROPIC_VERTEX_PROJECT_ID='your-gcp-project-id'
export CLOUD_ML_REGION='us-east5'  # Optional
```

**Finding your GCP project ID:**

```bash
# List all projects
gcloud projects list

# Show current project
gcloud config get-value project
```

### Individual API Key (Alternative)

1. Get your API key from [Anthropic Console](https://console.anthropic.com/settings/keys)

2. Set the environment variable:
   ```bash
   export ANTHROPIC_API_KEY='sk-ant-...'
   ```

3. Or add to `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env and set:
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

### Custom Enterprise Endpoint (Alternative)

Contact your enterprise administrator for these values:

```bash
export ANTHROPIC_BASE_URL='https://api.claude.yourcompany.com'
export ANTHROPIC_AUTH_TOKEN='enterprise-token-...'
export ANTHROPIC_ORG_ID='org-123'  # Optional
```

Or add to `.env` file:
```bash
cp .env.example .env
# Edit .env and set:
ANTHROPIC_BASE_URL=https://api.claude.yourcompany.com
ANTHROPIC_AUTH_TOKEN=enterprise-token-...
ANTHROPIC_ORG_ID=org-123
```

## Configuration Details

### Environment Variables

| Variable | Required For | Description |
|----------|-------------|-------------|
| `ANTHROPIC_VERTEX_PROJECT_ID` | Vertex AI | Your GCP project ID |
| `CLOUD_ML_REGION` | Vertex AI (optional) | GCP region (defaults to us-east5) |
| `ANTHROPIC_API_KEY` | Individual API key | Your Anthropic API key |
| `ANTHROPIC_BASE_URL` | Enterprise endpoint | Custom API endpoint URL |
| `ANTHROPIC_AUTH_TOKEN` | Enterprise endpoint | Enterprise authentication token |
| `ANTHROPIC_ORG_ID` | Enterprise (optional) | Organization identifier for routing |

### Authentication Priority

The system checks for authentication in this order:

1. **Vertex AI** (if `ANTHROPIC_VERTEX_PROJECT_ID` is set)
2. **Enterprise** (if `ANTHROPIC_BASE_URL` or `ANTHROPIC_AUTH_TOKEN` is set)
3. **API Key** (if `ANTHROPIC_API_KEY` is set)
4. **Error** (if nothing is configured)

### Google Vertex AI Setup Details

#### Prerequisites

- Google Cloud CLI installed
- Active GCP account with billing enabled
- Project with Vertex AI API enabled
- Appropriate IAM permissions (Vertex AI User role)

#### Enable Vertex AI API

```bash
# Enable Vertex AI API for your project
gcloud services enable aiplatform.googleapis.com --project=your-gcp-project-id
```

#### Configure IAM Permissions

Ensure your account has the necessary permissions:

```bash
# Grant yourself Vertex AI User role (if needed)
gcloud projects add-iam-policy-binding your-gcp-project-id \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

#### Available Regions

Common GCP regions for Vertex AI:
- `us-east5` (default, recommended)
- `us-central1`
- `europe-west1`
- `asia-southeast1`

To check available regions:
```bash
gcloud ai-platform regions list
```

#### Authentication Flow

When using Vertex AI:
1. System reads `ANTHROPIC_VERTEX_PROJECT_ID` from environment
2. Uses Application Default Credentials (ADC) from gcloud
3. Makes requests to Vertex AI endpoint in specified region
4. No API keys transmitted or stored

#### Verify Authentication

```bash
# Check ADC status
gcloud auth application-default print-access-token

# Verify quota project
gcloud auth application-default describe
```

### Configuration Files

#### Using .env file

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your credentials
nano .env
```

#### Example .env configurations

**Google Vertex AI:**
```env
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
CLOUD_ML_REGION=
```

**Individual API Key:**
```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

**Enterprise:**
```env
ANTHROPIC_BASE_URL=https://api.claude.yourcompany.com
ANTHROPIC_AUTH_TOKEN=enterprise-token-here
ANTHROPIC_ORG_ID=org-123
```

## Usage in Code

### Using the auth module directly

```python
from config.auth_config import get_anthropic_client

# Get configured client (handles all auth types automatically)
try:
    client = get_anthropic_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello!"}]
    )
except ValueError as e:
    print(f"Authentication error: {e}")
```

### Validating configuration

```python
from config.auth_config import validate_authentication

# Check authentication status without creating a client
auth_info = validate_authentication()
print(f"Auth type: {auth_info['auth_type']}")  # 'vertex', 'enterprise', 'api_key', or 'none'
print(f"Has Vertex project: {auth_info.get('has_vertex_project')}")
print(f"Has API key: {auth_info['has_api_key']}")
print(f"Has base URL: {auth_info['has_base_url']}")
```

### Using with agents

All agents automatically use the auth configuration module:

```python
from agents.design_agent import run_design

# No need to configure authentication manually
# The agent will use get_anthropic_client() internally
result = run_design(
    title="Add timeout support",
    description="Feature description..."
)
```

## Testing

### Running tests

Tests automatically mock the authentication:

```bash
# Run all tests
uv run pytest tests/

# Run auth-specific tests
uv run pytest tests/test_auth_config.py -v
```

### Testing with real API

**With Vertex AI:**
```bash
export ANTHROPIC_VERTEX_PROJECT_ID='your-gcp-project-id'
uv run pytest tests/ -v
```

**With API Key:**
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
uv run pytest tests/ -v
```

Tests marked with `@pytest.mark.real_api` will only run when authentication is configured.

## Troubleshooting

### Error: "No Claude authentication configured"

**Cause:** No authentication method is set.

**Solution:** Set one of:
- `ANTHROPIC_VERTEX_PROJECT_ID` for Vertex AI (recommended)
- `ANTHROPIC_API_KEY` for individual API key
- `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` for enterprise

### Error: "gcloud not authenticated" or ADC errors

**Cause:** Google Cloud CLI authentication not configured.

**Solution:**
```bash
# Re-authenticate
gcloud auth application-default login

# Set quota project
gcloud auth application-default set-quota-project your-gcp-project-id

# Verify authentication
gcloud auth application-default print-access-token
```

### Error: "Vertex AI API not enabled"

**Cause:** Vertex AI API not enabled for your GCP project.

**Solution:**
```bash
gcloud services enable aiplatform.googleapis.com --project=your-gcp-project-id
```

### Error: "Permission denied" on Vertex AI

**Cause:** Your account lacks necessary IAM permissions.

**Solution:**
```bash
# Grant Vertex AI User role
gcloud projects add-iam-policy-binding your-gcp-project-id \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

### Error: "Incomplete enterprise configuration"

**Cause:** Only `ANTHROPIC_BASE_URL` is set without authentication.

**Solution:** Set one of:
- `ANTHROPIC_AUTH_TOKEN` (enterprise token)
- `ANTHROPIC_API_KEY` (use API key with custom base URL)

### Error: "Failed to initialize Claude Enterprise client"

**Cause:** Invalid enterprise configuration values.

**Solution:** Verify with your enterprise administrator:
- Base URL is correct and accessible
- Auth token is valid
- Organization ID is correct (if required)

### Authentication type unclear

Use the validation function to check current configuration:

```bash
python examples/auth_example.py
```

This will show which authentication method is active.

## Security Best Practices

1. **Never commit credentials** to version control
   - Use `.env` file (already in `.gitignore`)
   - Use environment variables
   - Use secret management tools in production

2. **Rotate credentials regularly**
   - Vertex AI: Managed by GCP (automatic rotation)
   - Individual API keys: Rotate every 90 days
   - Enterprise tokens: Follow your organization's policy

3. **Use least privilege**
   - Vertex AI: Grant only necessary IAM roles
   - Individual API keys: Limit scope to necessary permissions
   - Enterprise: Use organization-specific tokens

4. **Monitor usage**
   - Vertex AI: Check GCP billing and quotas
   - API Key: Check usage in [Anthropic Console](https://console.anthropic.com/settings/usage)
   - Set up billing alerts

5. **Separate environments**
   - Development: Use individual API keys or Vertex AI dev projects
   - Production: Use Vertex AI production projects or enterprise authentication
   - Never share credentials between environments

## Examples

See `examples/auth_example.py` for a complete working example:

```bash
# Run the example
uv run python examples/auth_example.py
```

## API Reference

### `get_anthropic_client()`

Get configured Anthropic client with Vertex AI, enterprise, or API key authentication.

**Returns:**
- `Anthropic` - Configured client ready to use

**Raises:**
- `ValueError` - If no authentication is configured or configuration is invalid

**Example:**
```python
client = get_anthropic_client()
```

### `validate_authentication()`

Validate authentication configuration without creating a client.

**Returns:**
```python
{
    "auth_type": str,           # "vertex", "enterprise", "api_key", or "none"
    "has_vertex_project": bool, # True if ANTHROPIC_VERTEX_PROJECT_ID is set
    "has_base_url": bool,       # True if ANTHROPIC_BASE_URL is set
    "has_auth_token": bool,     # True if ANTHROPIC_AUTH_TOKEN is set
    "has_api_key": bool,        # True if ANTHROPIC_API_KEY is set
    "has_org_id": bool          # True if ANTHROPIC_ORG_ID is set
}
```

**Example:**
```python
auth_info = validate_authentication()
if auth_info['auth_type'] == 'none':
    print("No authentication configured!")
elif auth_info['auth_type'] == 'vertex':
    print("Using Google Vertex AI authentication")
```

## Support

For issues or questions:

1. Check `.env.example` for configuration reference
2. Run `python examples/auth_example.py` to validate setup
3. Review test files in `tests/test_auth_config.py` for examples
4. For Vertex AI issues: Check GCP documentation and IAM permissions
5. For enterprise issues: Contact your enterprise administrator
