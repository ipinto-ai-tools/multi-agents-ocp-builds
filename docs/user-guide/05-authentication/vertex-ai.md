# Vertex AI Setup

Google Vertex AI is the default (and currently only) authentication method. It uses Application Default Credentials (ADC) managed by the Google Cloud CLI. No API key is stored anywhere.

---

## When to Use Vertex AI

- Production environments with GCP access
- Teams that want GCP IAM to control Claude API access
- Organizations that already use Google Cloud services
- When you prefer credential rotation through GCP rather than managing an API key

---

## Setup Steps

### Step 1: Install the Google Cloud CLI

Follow the official guide: https://cloud.google.com/sdk/docs/install

Verify installation:

```bash
gcloud --version
```

### Step 2: Authenticate Your Account

```bash
gcloud auth application-default login
```

This opens a browser window for Google account sign-in. Your credentials are cached locally at `~/.config/gcloud/application_default_credentials.json`.

### Step 3: Set the Billing Project

```bash
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
```

Find your project ID if you do not have it:

```bash
gcloud projects list
```

### Step 4: Enable the Vertex AI API

```bash
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

### Step 5: Grant IAM Permissions

Your account needs the `roles/aiplatform.user` role:

```bash
gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/aiplatform.user"
```

> **Note:** If using a service account instead of a user account, replace `user:` with `serviceAccount:` in the command above.

### Step 6: Set the Environment Variable

In your `.env` file:

```bash
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=us-east5   # Optional, defaults to us-east5
```

---

## Available Regions

| Region | Notes |
|--------|-------|
| `us-east5` | Default, recommended |
| `us-central1` | US central |
| `europe-west1` | EU west |
| `asia-southeast1` | Asia Pacific |

Set the region in `.env` if the default `us-east5` is not available in your GCP project:

```bash
CLOUD_ML_REGION=us-central1
```

---

## How ADC Works in the System

1. The system reads `ANTHROPIC_VERTEX_PROJECT_ID` from environment variables
2. `config/auth_config.get_anthropic_client()` creates an `AnthropicVertex` client
3. The client uses the ADC token cached by `gcloud auth application-default login`
4. All Claude API requests route through the Vertex AI endpoint in the configured region
5. GCP manages token refresh automatically - no manual rotation needed

---

## Verify Your Setup

Check that credentials are active:

```bash
gcloud auth application-default print-access-token
gcloud auth application-default describe
```

Run the bundled auth example:

```bash
uv run python examples/auth_example.py
```

---

## Credential Rotation

ADC tokens expire automatically and are refreshed by the Google Cloud CLI. For long-running environments, re-run the login command periodically:

```bash
gcloud auth application-default login
```

For service accounts in CI/CD environments, use Workload Identity Federation or a service account key file rather than interactive ADC.

---

## Troubleshooting

### Token expired

```bash
gcloud auth application-default login
```

### Wrong project

```bash
gcloud auth application-default set-quota-project CORRECT_PROJECT_ID
```

### API quota exceeded

Check your quota in the GCP console under Vertex AI > Quotas. You may need to request a quota increase for Claude model requests.

---

[← Previous: Auth Overview](overview.md) | [Next: API Key →](api-key.md)
