# Multi-Agent OpenShift Builds

AI-powered development orchestrator for Shipwright Build using Claude AI and LangGraph.

The Multi-Agent OpenShift Builds system automates the design analysis and documentation generation workflow for OpenShift and Shipwright Build projects. By leveraging Claude AI agents and LangGraph orchestration, it transforms feature requests and bug reports into comprehensive design documents with impact analysis, implementation plans, and production-ready documentation.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

---

## Features

### Intelligent Analysis

- **Design Agent**: Analyzes GitHub issues and generates comprehensive design documents using Claude API
- **Documentation Agent**: Produces PR summaries, release notes, and documentation changes
- **Repository Analysis**: Examines Shipwright codebase to identify impacted components
- **Risk Assessment**: Evaluates compatibility concerns and architectural impacts

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
- **Anthropic API Key**: Get yours at [console.anthropic.com](https://console.anthropic.com/settings/keys)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/muilti-agents-ocp-builds.git
   cd muilti-agents-ocp-builds
   ```

2. **Install dependencies**

   ```bash
   # Using uv (recommended)
   uv pip install -r requirements.txt

   # Or using pip
   pip install -r requirements.txt
   ```

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

### Configuration

Create a `.env` file with your settings:

```bash
# Required: Your Anthropic Claude API key
ANTHROPIC_API_KEY=your_api_key_here

# Optional: Path to Shipwright repository for code analysis
SHIPWRIGHT_REPO_PATH=/path/to/shipwright-build

# Optional: Path to OpenShift builds repository
OPENSHIFT_BUILDS_REPO_PATH=/path/to/openshift-builds

# Optional: Logging configuration
LOG_LEVEL=INFO
LOG_FORMAT=text

# Optional: Claude model configuration
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=8000
```

See [`.env.example`](.env.example) for all available configuration options.

### Running Your First Analysis

```bash
# Run design analysis on a GitHub issue
uv run python -m agents.design_agent \
  --title "Add timeout support to BuildRun API" \
  --description "Users need to specify timeouts for build execution"

# Run full orchestration workflow
uv run python -m graph.orchestrator \
  --issue-number 123 \
  --repo shipwright-io/build
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
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│  Design  │  │   Docs   │  │   Test   │
│  Agent   │  │  Agent   │  │  Agent   │
├──────────┤  ├──────────┤  ├──────────┤
│ Claude   │  │ Claude   │  │ Local    │
│ API      │  │ API      │  │ Exec     │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └─────────────┴─────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│         Shipwright Repository Analysis              │
│  • API Types  • Controllers  • CRDs  • Webhooks     │
└─────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent            | Purpose                                                                      | Technology      |
|------------------|------------------------------------------------------------------------------|-----------------|
| **Design Agent** | Analyzes requirements, identifies impacted components, generates design docs | Claude API      |
| **Docs Agent**   | Creates PR summaries, release notes, documentation changes                   | Claude API      |
| **Test Agent**   | Validates implementation, runs test suites                                   | Local execution |
| **Orchestrator** | Coordinates workflow, manages state, handles errors                          | LangGraph       |

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Repository Structure

```text
muilti-agents-ocp-builds/
├── agents/               # AI agent implementations
│   ├── design_agent.py   # Design analysis agent (Claude API)
│   ├── docs_agent.py     # Documentation generation agent (Claude API)
│   └── test_agent.py     # Test execution agent
├── graph/                # LangGraph orchestration
│   ├── orchestrator.py   # Main workflow orchestrator
│   └── state.py          # State management
├── tools/                # Repository analysis tools
│   ├── repo_analyzer.py  # Code structure analysis
│   └── component_map.py  # Shipwright component mapping
├── config/               # Configuration files
│   └── components.yaml   # Shipwright component definitions
├── tests/                # Comprehensive test suite
│   ├── test_design_agent.py
│   ├── test_docs_agent.py
│   └── test_orchestration.py
├── docs/                 # Documentation
│   ├── HOWTO.md          # Detailed usage guide
│   └── ARCHITECTURE.md   # Architecture documentation
├── scripts/              # Utility scripts
├── .env.example          # Environment configuration template
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## Documentation

- **[HOWTO.md](docs/HOWTO.md)** - Comprehensive usage guide with examples
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
- **[Test Suite Guide](tests/README.md)** - Testing documentation and best practices

---

## Example Usage

### Design Analysis

Analyze a feature request and generate a design document:

```bash
uv run python -m agents.design_agent \
  --title "Add BuildRun timeout support" \
  --description "Users need to configure max execution time for builds" \
  --components buildrun_api,buildrun_controller
```

**Output**: Comprehensive design document with:

- Component impact analysis
- Risk assessment
- Implementation recommendations
- Acceptance criteria
- Testing strategy

### Documentation Generation

Generate documentation from a completed design:

```bash
uv run python -m agents.docs_agent \
  --design-doc /path/to/design.md \
  --code-changes /path/to/diff.txt \
  --test-results /path/to/test-output.txt
```

**Output**:

- PR summary with technical overview
- Release notes for end users
- Documentation change recommendations

### Full Orchestration

Run the complete workflow for a GitHub issue:

```bash
uv run python -m graph.orchestrator \
  --issue-number 456 \
  --repo shipwright-io/build \
  --components buildrun_api,webhook_validation
```

**Workflow**:

1. Fetch issue from GitHub
2. Analyze design requirements
3. Identify impacted components
4. Generate implementation plan
5. Create documentation artifacts

---

## Testing

The project includes a comprehensive test suite with support for both mocked and real API testing.

### Run All Tests

```bash
uv run pytest tests/ -v
```

### Run Specific Test Suite

```bash
# Test design agent
uv run pytest tests/test_design_agent.py -v

# Test docs agent
uv run pytest tests/test_docs_agent.py -v

# Test orchestration
uv run pytest tests/test_orchestration.py -v
```

### Run with Real Claude API

```bash
export ANTHROPIC_API_KEY=your_key_here
uv run pytest tests/ -v
```

### Run with Coverage

```bash
uv run pytest tests/ --cov=agents --cov=graph --cov-report=html
```

See [tests/README.md](tests/README.md) for detailed testing documentation.

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
