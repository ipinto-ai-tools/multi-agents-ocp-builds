# Multi-Agent OCP Builds - User Guide

AI-powered development orchestrator for Shipwright Build using Claude AI and LangGraph.

This system automates the design, development, testing, and documentation workflow for OpenShift and Shipwright Build projects. You provide a feature request or bug report; the agent pipeline returns a design document, production Go code, Ginkgo v2 tests, and full documentation.

---

## Navigation

### Section 1 - Getting Started

| Page | Description |
|------|-------------|
| [Installation](01-getting-started/installation.md) | System requirements and install steps |
| [Quick Start](01-getting-started/quick-start.md) | Run your first workflow in minutes |
| [Configuration](01-getting-started/configuration.md) | Environment variables and `.env` setup |

### Section 2 - Core Concepts

| Page | Description |
|------|-------------|
| [Architecture](02-concepts/architecture.md) | System overview and LangGraph pipeline |
| [Agents Overview](02-concepts/agents-overview.md) | The four agents and how they connect |
| [State Management](02-concepts/state-management.md) | AgentState, phase transitions, data flow |

### Section 3 - Agents

| Page | Description |
|------|-------------|
| [Design Agent](03-agents/design-agent.md) | Inputs, outputs, and direct usage |
| [Development Agent](03-agents/development-agent.md) | Go/Kubernetes code generation |
| [Testing Agent](03-agents/testing-agent.md) | Ginkgo v2 patterns and test types |
| [Docs Agent](03-agents/docs-agent.md) | RAG, SHIP format, and JTBD documentation |

### Section 4 - Dashboard

| Page | Description |
|------|-------------|
| [Overview](04-dashboard/overview.md) | Dashboard intro and architecture |
| [Session Management](04-dashboard/session-management.md) | Sessions, heartbeats, and cleanup |

### Section 5 - Authentication

| Page | Description |
|------|-------------|
| [Overview](05-authentication/overview.md) | How authentication works |
| [Vertex AI](05-authentication/vertex-ai.md) | Google Vertex AI setup guide |
| [API Key](05-authentication/api-key.md) | Direct API key setup |

### Section 6 - Advanced

| Page | Description |
|------|-------------|
| [Dry Run Mode](06-advanced/dry-run-mode.md) | Test without API calls |
| [Logging](06-advanced/logging.md) | Log files, levels, and session logs |
| [Troubleshooting](06-advanced/troubleshooting.md) | Common issues and fixes |

---

## Quick Navigation by Use Case

| I want to... | Go to |
|---|---|
| Install the system for the first time | [Installation](01-getting-started/installation.md) |
| Run my first workflow | [Quick Start](01-getting-started/quick-start.md) |
| Configure environment variables | [Configuration](01-getting-started/configuration.md) |
| Understand what each agent does | [Agents Overview](02-concepts/agents-overview.md) |
| Call an agent directly from Python | [Design Agent](03-agents/design-agent.md) / [Testing Agent](03-agents/testing-agent.md) |
| Monitor a running workflow | [Dashboard Overview](04-dashboard/overview.md) |
| Set up Google Vertex AI authentication | [Vertex AI](05-authentication/vertex-ai.md) |
| Test without making API calls | [Dry Run Mode](06-advanced/dry-run-mode.md) |
| Debug a failing workflow | [Troubleshooting](06-advanced/troubleshooting.md) |
| Understand how state flows between agents | [State Management](02-concepts/state-management.md) |

---

## Status

| Item | Value |
|------|-------|
| Default model | `claude-sonnet-4-20250514` |
| Python requirement | 3.11 or higher |
| Auth method | Google Vertex AI (Application Default Credentials) |
| Dashboard port | 8080 (local only) |
| Dry run support | Yes - no credentials needed |
