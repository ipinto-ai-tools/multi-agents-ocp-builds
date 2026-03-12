# Multi-Agent OpenShift Builds

AI-powered development orchestrator for Shipwright Build using Claude AI and LangGraph.

The Multi-Agent OpenShift Builds system automates the design analysis and documentation generation workflow for OpenShift and Shipwright Build projects. By leveraging Claude AI agents and LangGraph orchestration, it transforms feature requests and bug reports into comprehensive design documents with impact analysis, implementation plans, and production-ready documentation.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

---

## Features

### Intelligent Analysis

- **Design Agent**: Analyzes GitHub issues and generates comprehensive design documents using Claude API
- **Development Agent**: Writes production-quality Go code for Kubernetes/OpenShift following strict security standards
- **Testing Agent**: Generates Ginkgo v2 tests with Data-Driven Testing patterns for unit, integration, and E2E scenarios
- **Documentation Agent**: Produces PR summaries, release notes, and documentation changes
- **Repository Analysis**: Examines Shipwright codebase to identify impacted components
- **Risk Assessment**: Evaluates compatibility concerns and architectural impacts

### Real-Time Monitoring

- **Dashboard**: Web-based dashboard for monitoring agent workflows in real-time
- **Heartbeat Protocol**: Agents emit state updates for live progress tracking
- **Context Tracking**: Monitor token usage and context consumption
- **Session Management**: View active and completed agent sessions

### Orchestrated Workflow

- **LangGraph Coordination**: Manages multi-agent workflows with state management
- **Phase-Based Execution**: Sequential processing through design, development, testing, and documentation
- **Context Propagation**: Shares analysis results between agents for informed decision-making

### Shipwright Domain Expertise

- **Component Mapping**: Understands BuildRun, Build, BuildStrategy, and webhook components
- **CRD Analysis**: Analyzes Custom Resource Definitions and API types
- **Controller Context**: Evaluates controller logic and reconciliation patterns
- **OpenShift Integration**: Considers OpenShift Build API compatibility

---

## Quick Start

### Prerequisites

- **Python**: 3.11 or higher
- **uv**: Python package installer (recommended)

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **Git**: 2.0 or higher
- **Google Cloud CLI**: For Vertex AI authentication
  ```bash
  # Install gcloud CLI - see: https://cloud.google.com/sdk/docs/install

  # Authenticate
  gcloud auth application-default login
  gcloud auth application-default set-quota-project your-gcp-project-id
  ```
- **Claude Authentication**: Configured via one of:
  - **Google Vertex AI** (recommended): Uses gcloud authentication
  - **Individual API Key**: Personal API key from console.anthropic.com

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/muilti-agents-ocp-builds.git
   cd muilti-agents-ocp-builds
   ```

2. **Install dependencies**

   ```bash
   # Option 1: Create virtual environment with uv
   uv venv
   source .venv/bin/activate
   pip install -r requirements.txt

   # Option 2: Use uv sync if pyproject.toml is configured
   uv sync
   ```

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env and configure your Claude authentication
   ```

### Configuration

Create a `.env` file in the project root:

**Option 1: Google Vertex AI (Recommended)**

```bash
# Google Vertex AI Authentication
# Uses gcloud authentication (no API keys needed!)
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=  # Optional, defaults to us-east5

# Authenticate with gcloud:
# gcloud auth application-default login
# gcloud auth application-default set-quota-project your-gcp-project-id

# Optional: Repository paths for code analysis
SHIPWRIGHT_REPO_PATH=/path/to/shipwright-build
OPENSHIFT_BUILDS_REPO_PATH=/path/to/openshift-builds

# Optional: Model configuration
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=8000
```

**Option 2: Individual API Key**

```bash
# Individual API Key (alternative to Vertex AI)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# Optional: Repository paths for code analysis
SHIPWRIGHT_REPO_PATH=/path/to/shipwright-build
OPENSHIFT_BUILDS_REPO_PATH=/path/to/openshift-builds

# Optional: Model configuration
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=8000
```

**Option 3: Custom Enterprise Endpoint**

```bash
# Custom enterprise endpoint (alternative)
ANTHROPIC_BASE_URL=https://your-endpoint.com
ANTHROPIC_AUTH_TOKEN=your-auth-token

# Optional: Repository paths for code analysis
SHIPWRIGHT_REPO_PATH=/path/to/shipwright-build
OPENSHIFT_BUILDS_REPO_PATH=/path/to/openshift-builds

# Optional: Model configuration
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=8000
```

**For Vertex AI setup:**
1. Install Google Cloud CLI
2. Run authentication commands (see Prerequisites)
3. Set your GCP project ID in `.env`
4. No API keys needed!

**For Individual API Key:**
- Get your API key at [console.anthropic.com](https://console.anthropic.com/settings/keys)

**Quick setup**: Copy `.env.example` to `.env` and configure your authentication method. Everything else has sensible defaults.

See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) for detailed setup.

### Running Your First Analysis

**Option 1: Quick design analysis** (no GitHub required)

```bash
# Option 1: With virtual environment (recommended for repeated use)
uv venv
source .venv/bin/activate
pip install -r requirements.txt
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun API" \
  --description "Users need to specify timeouts for build execution"

# Option 2: Direct execution with dependencies (one-time use)
uv run --with anthropic --with langgraph --with langchain-core \
       --with python-dotenv --with GitPython --with pyyaml \
python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun API" \
  --description "Users need to specify timeouts for build execution"
```

This generates a design document with component analysis and recommendations.

**Option 2: Full workflow with dashboard** (recommended for monitoring)

```bash
# Terminal 1: Start the dashboard
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py
# Open http://localhost:8080 in your browser

# Terminal 2: Run the workflow
# Option 1: With virtual environment (recommended for repeated use)
uv venv
source .venv/bin/activate
pip install -r requirements.txt
uv run python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun API" \
  --description "Users need to specify timeouts for build execution"

# Option 2: Direct execution with dependencies (one-time use)
uv run --with anthropic --with langgraph --with langchain-core \
       --with python-dotenv --with GitPython --with pyyaml \
python scripts/orchestrate.py \
  --title "Add timeout support to BuildRun API" \
  --description "Users need to specify timeouts for build execution"
```

The dashboard shows real-time progress, context usage, and component impacts.

### Common Commands

**Three essential commands you'll use:**

```bash
# 1. Run a workflow (most common)
# Option 1: With virtual environment (recommended for repeated use)
uv venv
source .venv/bin/activate
pip install -r requirements.txt
uv run python scripts/orchestrate.py \
  --title "Your feature title" \
  --description "Detailed description"

# Option 2: Direct execution with dependencies (one-time use)
uv run --with anthropic --with langgraph --with langchain-core \
       --with python-dotenv --with GitPython --with pyyaml \
python scripts/orchestrate.py \
  --title "Your feature title" \
  --description "Detailed description"

# 2. Start the dashboard (for monitoring)
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py
# Note: The dashboard requires 'requests' for heartbeat communication with agents

# 3. Run tests
uv run pytest tests/ -v
```

---

## Architecture Overview

The system uses a multi-agent architecture orchestrated by LangGraph:

```text
┌─────────────────────────────────────────────────────┐
│                    User Request                     │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              LangGraph Orchestrator                 │
│  • State Management                                 │
│  • Phase Coordination                               │
│  • Error Handling                                   │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┼─────────────┬───────────┐
        │            │             │           │
        ▼            ▼             ▼           ▼
┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│    Design    │  │  Develop │  │ Testing  │  │   Docs   │
│    Agent     │─>│  Agent   │─>│  Agent   │─>│  Agent   │
├──────────────┤  ├──────────┤  ├──────────┤  ├──────────┤
│  Claude API  │  │Claude API│  │Claude API│  │Claude API│
└──────┬───────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
       │               │             │             │
       └───────────────┼─────────────┼─────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│         Shipwright Repository Analysis              │
│  • API Types  • Controllers  • CRDs  • Webhooks     │
└─────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent                  | Input                    | Output                                    | Purpose                                      |
|------------------------|--------------------------|-------------------------------------------|----------------------------------------------|
| **Design Agent**       | Issue description, repo  | Implementation plan, analysis             | Strategic planning and architectural review  |
| **Development Agent**  | Implementation plan      | Production Go code                        | Write secure, maintainable K8s/OpenShift code |
| **Testing Agent**      | Implementation plan      | Ginkgo v2 test suite                      | Comprehensive test coverage                  |
| **Docs Agent**         | Changes, context         | PR description, release notes             | Professional documentation                   |
| **Orchestrator**       | User request             | Coordinated agent workflow                | Multi-agent coordination via LangGraph       |

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Repository Structure

```text
muilti-agents-ocp-builds/
├── agents/               # AI agent implementations
│   ├── design_agent.py   # Design analysis agent with SHIP format support
│   ├── docs_agent.py     # Documentation generation with Agentic RAG
│   ├── go_k8s_developer.py  # Production Go/K8s code generation
│   ├── testing_agent.py  # Ginkgo v2 test generation with enhanced patterns
│   └── graph.py          # LangGraph workflow orchestrator
├── config/               # Configuration files
│   ├── agent_prompts.py  # Agent system prompts and templates
│   ├── auth_config.py    # Authentication configuration and utilities
│   ├── mock_responses.py # Mock API responses for dry-run mode
│   ├── testing_config.py # Testing patterns and Ginkgo templates
│   └── shipwright_components.py  # Shipwright component definitions
├── dashboard/            # Real-time monitoring dashboard
│   ├── backend.py        # FastAPI dashboard server
│   ├── enrichers.py      # State enrichment pipeline
│   ├── heartbeat.py      # Heartbeat protocol implementation
│   ├── frontend/         # Web UI
│   │   └── index.html    # Dashboard interface
│   └── __init__.py       # Dashboard module initialization
├── docs/                 # Documentation
│   ├── ARCHITECTURE.md   # System architecture overview
│   ├── AUTHENTICATION.md # Authentication and dry-run mode guide
│   ├── DASHBOARD_ARCHITECTURE.md  # Dashboard design and implementation
│   ├── DOCS_AGENT_ENHANCEMENTS.md # Docs agent features and usage
│   ├── GO_K8S_DEVELOPER_AGENT.md  # Go/K8s developer agent guide
│   ├── HOWTO.md          # Comprehensive user guide with examples
│   ├── IMPLEMENTATION_SUMMARY.md  # Implementation details and history
│   ├── TESTING_AGENT.md  # Testing agent capabilities and patterns
│   └── TESTING_INFRASTRUCTURE.md  # Testing infrastructure guide
├── examples/             # Example usage scripts
│   ├── auth_example.py   # Authentication configuration example
│   └── test_agents_demo.sh  # Demo script for agent testing
├── graph/                # LangGraph state management
│   ├── state.py          # Agent state schema and types
│   └── __init__.py       # Graph module initialization
├── mcp/                  # MCP server integration stubs
│   ├── github_stub.py    # GitHub MCP server stub
│   ├── jira_stub.py      # Jira MCP server stub
│   └── __init__.py       # MCP module initialization
├── scripts/              # Utility scripts
│   ├── orchestrate.py    # Manual orchestration runner
│   ├── run_dashboard.py  # Dashboard server launcher
│   └── test_agents.py    # CLI tool for manual agent testing
├── tests/                # Comprehensive test suite
│   ├── conftest.py       # Pytest configuration and fixtures
│   ├── test_agents_validator_dashboard.py  # Dashboard integration tests
│   ├── test_agents_validator_design.py     # Design agent validation
│   ├── test_agents_validator_develop.py    # Go/K8s developer agent tests
│   ├── test_agents_validator_docs.py       # Docs agent validation
│   ├── test_agents_validator_docs_enhanced.py  # Enhanced docs tests
│   ├── test_agents_validator_orchestration.py  # Orchestration tests
│   ├── test_agents_validator_rag.py        # RAG functionality tests
│   ├── test_agents_validator_testing.py    # Testing agent validation
│   ├── test_auth_config.py                 # Authentication config tests
│   ├── README.md         # Test suite documentation
│   └── SUMMARY.md        # Test coverage summary
├── tools/                # Repository analysis tools
│   ├── git_ops.py        # Git operations and utilities
│   ├── rag_search.py     # Documentation search with RAG
│   ├── repo_search.py    # Code search and analysis
│   └── __init__.py       # Tools module initialization
├── utils/                # Utility modules
│   ├── logging_config.py # Logging configuration and debug support
│   └── __init__.py       # Utils module initialization
├── .env.example          # Environment configuration template
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## Documentation

- **[HOWTO.md](docs/HOWTO.md)** - Comprehensive usage guide with examples
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
- **[DASHBOARD_ARCHITECTURE.md](docs/DASHBOARD_ARCHITECTURE.md)** - Dashboard design and implementation
- **[Test Suite Guide](tests/README.md)** - Testing documentation and best practices

---

## Example Usage

### 1. Design Analysis

Generate a design document for a feature request:

```bash
# Option 1: With virtual environment (recommended for repeated use)
uv venv
source .venv/bin/activate
pip install -r requirements.txt
uv run python scripts/orchestrate.py \
  --title "Add BuildRun timeout support" \
  --description "Users need to configure max execution time for builds"

# Option 2: Direct execution with dependencies (one-time use)
uv run --with anthropic --with langgraph --with langchain-core \
       --with python-dotenv --with GitPython --with pyyaml \
python scripts/orchestrate.py \
  --title "Add BuildRun timeout support" \
  --description "Users need to configure max execution time for builds"
```

**What you get**: A comprehensive design document including component impacts, risks, implementation plan, acceptance criteria, and testing strategy.

### 2. Full Workflow with Dashboard

Monitor the workflow in real-time:

```bash
# Terminal 1: Start dashboard
uv run --with fastapi --with "uvicorn[standard]" --with requests python scripts/run_dashboard.py

# Terminal 2: Run workflow
# Option 1: With virtual environment (recommended for repeated use)
uv venv
source .venv/bin/activate
pip install -r requirements.txt
uv run python scripts/orchestrate.py \
  --title "Add BuildRun timeout support" \
  --description "Users need to configure max execution time for builds"

# Option 2: Direct execution with dependencies (one-time use)
uv run --with anthropic --with langgraph --with langchain-core \
       --with python-dotenv --with GitPython --with pyyaml \
python scripts/orchestrate.py \
  --title "Add BuildRun timeout support" \
  --description "Users need to configure max execution time for builds"
```

**What happens**: Analyzes requirements → identifies impacted components → generates design → creates Ginkgo tests → generates documentation → dashboard shows real-time progress.

### 3. Testing Agent Output

The Testing Agent generates comprehensive Ginkgo v2 tests:

**What you get**:

- **Test Plan**: Human-readable test strategy and coverage mapping
- **Test Specifications**: YAML test specs with scenario IDs
- **Unit Tests**: Mock-based, isolated function tests
- **Integration Tests**: Real K8s cluster controller/webhook tests
- **E2E Tests**: Full workflow tests with actual build execution
- **Coverage Analysis**: Mapping of tests to acceptance criteria

**Example test output**:

- Ginkgo v2 syntax with proper imports
- Data-Driven Testing (DescribeTable) for parameterized tests
- Shipwright-specific helpers (libfactory, libk8s)
- Pattern detection (kaniko, buildkit, git sources, etc.)

---

## Testing

The project includes a comprehensive test suite with support for both mocked and real API testing.

### Run All Tests

```bash
uv run pytest tests/ -v
```

### Run Specific Test Suite

```bash
# Test individual agents
uv run pytest tests/test_agents_validator_design.py -v
uv run pytest tests/test_agents_validator_develop.py -v
uv run pytest tests/test_agents_validator_testing.py -v
uv run pytest tests/test_agents_validator_docs.py -v

# Test orchestration
uv run pytest tests/test_orchestration.py -v
```

### Run with Real Claude API

```bash
# For Enterprise
export ANTHROPIC_BASE_URL=https://your-enterprise-endpoint.anthropic.com
export ANTHROPIC_AUTH_TOKEN=your_enterprise_auth_token

# Or for Individual API Key
export ANTHROPIC_API_KEY=your_key_here

uv run pytest tests/ -v
```

### Run with Coverage

```bash
uv run pytest tests/ --cov=agents --cov=graph --cov-report=html
```

See [tests/README.md](tests/README.md) for detailed testing documentation.

### Manual Agent Testing

Test agents individually or as a complete workflow using the test CLI:

```bash
# Test with dry-run (no API calls, uses mock responses)
uv run python scripts/test_agents.py --e2e --dry-run --debug

# Test specific agent
uv run python scripts/test_agents.py --agent design --dry-run

# Test dashboard
uv run python scripts/test_agents.py --dashboard
```

**Features:**
- Dry-run mode with mock responses (no API calls, no authentication needed)
- Debug mode with verbose logging
- Local artifact storage
- Individual agent or E2E testing
- Dashboard functionality validation

See [docs/TESTING_INFRASTRUCTURE.md](docs/TESTING_INFRASTRUCTURE.md) for complete testing documentation.

---

## Contributing

We welcome contributions to improve the multi-agent system.

### Development Setup

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run pytest tests/ -v`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Guidelines

- Follow existing code style and patterns
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass before submitting PR
- Use descriptive commit messages

---

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

---

## Links

- **GitHub Repository**: [muilti-agents-ocp-builds](https://github.com/yourusername/muilti-agents-ocp-builds)
- **Issue Tracker**: [Issues](https://github.com/yourusername/muilti-agents-ocp-builds/issues)
- **Shipwright Build**: [shipwright-io/build](https://github.com/shipwright-io/build)
- **OpenShift Builds**: [openshift/builds](https://github.com/openshift/builds)
- **Claude API Documentation**: [docs.anthropic.com](https://docs.anthropic.com/)

---

## Acknowledgments

- **Anthropic Claude**: Powers the intelligent design and documentation agents
- **LangGraph**: Provides the orchestration framework
- **Shipwright Community**: Open-source Kubernetes build framework
- **OpenShift**: Enterprise Kubernetes platform

---

## Support

For questions, issues, or feature requests:

- Open an [issue](https://github.com/yourusername/muilti-agents-ocp-builds/issues)
- Review the [HOWTO guide](docs/HOWTO.md)
- Check the [FAQ section](docs/HOWTO.md#faq) in the documentation

---

## Built With

This project is built with Claude AI and LangGraph.
