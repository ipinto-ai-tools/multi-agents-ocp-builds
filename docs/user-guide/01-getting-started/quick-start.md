# Quick Start

Everything you need to go from zero to running your first pipeline. The FlowPilot dashboard is the recommended interface — it provides a web UI for creating runs, monitoring progress, streaming logs, and downloading artifacts. A [CLI](../10-reference/cli.md) is also available for scripting and automation.

---

## 1. Install

```bash
git clone https://github.com/your-org/muilti-agents-ocp-builds.git
cd muilti-agents-ocp-builds
uv venv && uv pip install -r requirements.txt
cp .env.example .env
```

Open `.env` in your editor and fill in the credentials from the sections below.

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`).

---

## 2. Configure Claude API (Vertex AI)

The system uses Google Vertex AI to access Claude. Authentication is handled through Application Default Credentials (ADC) — no API key is stored anywhere.

```bash
# One-time setup
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
gcloud services enable aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

Add to `.env`:

```bash
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=us-east5  # Optional, defaults to us-east5
```

Verify:

```bash
gcloud auth application-default print-access-token
```

See [Authentication](../05-authentication/authentication.md) for full Vertex AI setup including IAM permissions and troubleshooting.

---

## 3. Configure Jira (Recommended)

Jira integration lets you pass a ticket ID directly to the pipeline. The system fetches title, description, acceptance criteria, priority, labels, and linked issues automatically.

Add to `.env`:

```bash
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

Generate a token at [https://id.atlassian.com/manage-profile/security](https://id.atlassian.com/manage-profile/security).

> **VPN required:** The Jira REST API is not reachable outside the corporate network. Use dry-run mode when off-VPN.

See [Jira & Rovo Integration](../09-integrations/jira-rovo.md) for full details.

---

## 4. Configure GitHub (Optional)

Enriches the docs agent with upstream PR context from Jira-linked pull requests. Also required by `publish.py` for pushing generated code as a PR.

Add to `.env`:

```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
TARGET_GITHUB_REPO=openshift-builds/builds
TARGET_GITHUB_BASE_BRANCH=main
```

Without a `GITHUB_TOKEN`, the pipeline runs normally — PR enrichment is silently skipped.

---

## 5. Configure Repository Paths (Optional)

Repository paths let agents analyze actual Go types, CRDs, and controllers from source for more accurate analysis and code generation. Configure multiple repositories using `repos.yaml`:

```bash
cp repos.yaml.example repos.yaml
```

Edit `repos.yaml` to list your local clones:

```yaml
repos:
  - path: /home/user/git/shipwright-io/build
  - path: /home/user/git/shipwright-io/operator
  - path: /home/user/git/redhat-openshift-builds/operator
```

See `repos.yaml.example` for a full template with all Shipwright and OpenShift Builds repositories.

**Alternative:** Set `SHIPWRIGHT_REPO_PATH` and `OPENSHIFT_BUILDS_REPO_PATH` in `.env` for single-repo setups. See [Configuration](configuration.md) for details.

Without repo paths, agents fall back to component metadata only. Analysis is still valid, but less precise.

---

## 6. Run

Start the dashboard and open the web UI:

```bash
uv run python scripts/run_dashboard.py
```

Open [http://localhost:8080](http://localhost:8080) in your browser. Click **New Run** and fill in:

1. **Feature description** — describe the feature or bug to work on
2. **Jira Ticket** (recommended) — enter a ticket ID like `BUILD-123` to auto-fetch context
3. Click **Run Feature**

The pipeline runs all five phases automatically: Design → Development → Code Review → Testing → Documentation. Progress is visible in real time on the Dashboard page.

### Try It Without Credentials

Use dry-run mode to test the system without API credentials or VPN:

1. Open `http://localhost:8080`
2. Click **New Run**
3. Toggle **Dry Run** to `On` in Advanced Options
4. Enter any description and click **Run Feature**

### Alternative: CLI

For scripting and automation, see the [CLI Reference](../10-reference/cli.md):

```bash
uv run python scripts/orchestrate.py --jira-ticket BUILD-1707 --output-dir ./output
```

---

## Next Steps

| I want to... | Go to |
| --- | --- |
| Understand the dashboard pages | [Dashboard Overview](../04-dashboard/overview.md) |
| Learn what each agent does | [Agents Overview](../02-concepts/agents-overview.md) |
| See all environment variables | [Configuration](configuration.md) |
| Run from the command line | [CLI Reference](../10-reference/cli.md) |
| Use the REST API directly | [API Reference](../10-reference/api.md) |
| Test without API calls | [Dry Run Mode](../06-advanced/dry-run-mode.md) |
| Set up Vertex AI authentication | [Authentication](../05-authentication/authentication.md) |
| Publish artifacts to GitHub/Jira | [Publishing](../09-integrations/publish.md) |

---

[← Installation](installation.md) | [Configuration →](configuration.md)
