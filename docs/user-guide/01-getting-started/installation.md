# Installation

Set up the Multi-Agent OCP Builds system on your local machine.

---

## Prerequisites

### System Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11 or higher | Required for type hints and performance |
| Git | 2.0 or higher | For repository operations |
| uv | Latest | Recommended Python package installer |
| Google Cloud CLI | Latest | Required for Vertex AI authentication |

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify the installation:

```bash
uv --version
```

### Verify Python Version

```bash
python --version
# Expected: Python 3.11.x or higher
```

---

## Installation Steps

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/muilti-agents-ocp-builds.git
cd muilti-agents-ocp-builds
```

### Step 2: Install Dependencies

**Option A - Virtual environment (recommended for repeated use):**

```bash
uv venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Option B - uv sync (if pyproject.toml is configured):**

```bash
uv sync
```

Activate the virtual environment before running scripts:

```bash
source .venv/bin/activate
```

### Step 3: Configure Environment Variables

```bash
cp .env.example .env
# Open .env in your editor and set your GCP project ID
```

See [Configuration](configuration.md) for all available settings.

### Step 4: Set Up Authentication

The system uses Google Vertex AI. Run these commands once:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project your-gcp-project-id
```

> **Note:** No API keys are required. The system uses your existing Google Cloud credentials via Application Default Credentials (ADC).

> **Note:** If you only need to try the system without credentials, see [Dry Run Mode](../06-advanced/dry-run-mode.md). No authentication is needed in dry run mode.

### Step 5: Verify the Installation

Run these checks with your virtual environment activated:

```bash
python -c "from agents.design_agent import run_design; print('OK design agent')"
python -c "from agents.go_k8s_developer import run_development; print('OK development agent')"
python -c "from agents.testing_agent import run_testing; print('OK testing agent')"
python -c "from agents.docs_agent import run_docs; print('OK docs agent')"
```

Expected output:

```
OK design agent
OK development agent
OK testing agent
OK docs agent
```

---

## Optional: Shipwright Repository

Providing the Shipwright Build source repository enables deeper analysis. Agents can identify specific files to modify, match existing conventions, and produce more accurate component impact analysis.

```bash
git clone https://github.com/shipwright-io/build.git /path/to/shipwright-build
```

Then set `SHIPWRIGHT_REPO_PATH` in your `.env` file:

```bash
SHIPWRIGHT_REPO_PATH=/path/to/shipwright-build
```

---

## Next Steps

- [Quick Start](quick-start.md) - Run your first workflow
- [Configuration](configuration.md) - Full environment variable reference
- [Vertex AI Setup](../05-authentication/vertex-ai.md) - Detailed authentication guide

---

[← User Guide](../README.md) | [Next: Quick Start →](quick-start.md)
