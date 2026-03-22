# Docs Agent

The Documentation Agent generates all documentation artifacts from the combined outputs of the previous three agents. It supports multiple output formats and can use RAG (Retrieval-Augmented Generation) to incorporate relevant existing documentation and code examples from the repository.

**File:** `agents/docs_agent.py`
**Entry point:** `run_docs(context, input_files, output_format, enable_rag)`

---

## System Prompt

The Documentation Agent is driven by `DOCS_AGENT_PROMPT` defined in [`config/agent_prompts.py`](../../../config/agent_prompts.py).

The prompt instructs the agent to:

- Only document what has been implemented and tested — never speculate
- Produce a PR Summary (what changed, why, testing, rollout)
- Generate release notes with category, title, description, and migration notes
- Write Jobs-to-be-Done (JTBD) documentation organized around user outcomes
- Produce SHIP format documents (Solution, Highlight, Impact, Plan) for stakeholder communication
- Generate a High-Level Design document as implementation guidance

To customize Documentation Agent behavior, edit `DOCS_AGENT_PROMPT` in `config/agent_prompts.py`.

---

## Inputs

### Context Dictionary

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `design_analysis` | str | Yes | Design document from Design Agent |
| `code_changes` | dict | Yes | File paths to change descriptions |
| `test_results` | dict | Yes | Test execution results |
| `implementation_plan` | str | No | Implementation approach |
| `files_modified` | list[str] | No | Modified file list |
| `test_summary` | str | No | Test summary |
| `issue_title` | str | No | Original issue title |
| `issue_description` | str | No | Original issue description |
| `issue_type` | str | No | `bug`, `feature`, `refactor`, or `docs` |
| `repo_path` | str | No | Required for RAG - path to repository |
| `github_pr_urls` | list[str] | No | GitHub PR URLs extracted from Jira remote links |
| `github_pr_data` | list[dict] | No | Full PR metadata fetched from GitHub API (title, author, reviewers, state, files changed, etc.) |

### Function Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_files` | list[str] | None | Specific repository files to include as context |
| `output_format` | str | `"standard"` | See Output Formats below |
| `enable_rag` | bool | True | Enable RAG context fetching |

---

## Output Formats

| Format | Description |
|--------|-------------|
| `"standard"` | PR summary, release notes, upgrade notes, known limitations |
| `"ship"` | Adds a SHIP (Solution, Highlight, Impact, Plan) document |
| `"jtbd"` | Adds Jobs-to-be-Done user documentation |
| `"all"` | All formats plus a high-level design document |

---

## Outputs

```python
{
    # Core documentation (all formats)
    "pr_summary": str,               # Pull request description
    "release_notes": str,            # User-facing changelog entry
    "docs_changes": dict[str, str],  # doc file path → change description
    "upgrade_notes": str,            # Migration guidance for existing users
    "known_limitations": str,        # Edge cases and current restrictions
    "high_level_design": str,        # High-level design summary

    # Format-specific outputs
    "jtbd_documentation": str,       # Jobs-to-be-Done (if requested)
    "ship_document": str,            # SHIP format (if requested)

    # Metadata
    "input_files_analyzed": list,    # Files that were read and included
    "rag_enabled": bool,             # Whether RAG was active
    "output_format": str             # Format that was used
}
```

---

## Claude API Settings

| Setting | Value |
|---------|-------|
| Model | `claude-sonnet-4-20250514` |
| Max tokens | 8,192 |
| Temperature | 0.3 (lower for consistent documentation style) |

---

## SHIP Format

SHIP stands for Solution, Highlight, Impact, Plan. It provides structured documentation for stakeholder communication.

```markdown
## SHIP Document

### Solution
Implement configurable timeout for BuildRun resources to prevent indefinite
execution and resource exhaustion in the cluster.

### Highlight
- User-configurable timeout values with intuitive duration syntax (10m, 1h)
- Automatic build termination when timeout is exceeded
- Backward compatible - no breaking changes for existing BuildRuns
- Clear error messages when timeout triggers

### Impact
**Users**: Can prevent runaway builds from consuming cluster resources indefinitely.

**Operators**: Better resource management. Can enforce cluster-wide timeout policies
through admission webhooks.

**Developers**: Simple API addition with clear testing strategy.

### Plan
**Phase 1**: Core API and CRD changes (Week 1)
**Phase 2**: Controller timeout enforcement (Week 1-2)
**Phase 3**: Webhook validation and defaults (Week 2)
**Phase 4**: Documentation and examples (Week 2-3)
```

---

## JTBD Documentation Format

Jobs-to-be-Done documentation describes user goals in terms of outcomes. Each job follows this structure:

```markdown
## Job: [What the user wants to accomplish]

**Context:** When [situation], I want to [motivation], so I can [outcome].

**Steps to Complete:**
1. [Concrete action with example]
2. [Concrete action with example]

**Troubleshooting:**
- [Common error and fix]

**Related Jobs:**
- [Related task]
```

---

## RAG (Retrieval-Augmented Generation)

When `enable_rag=True` and `repo_path` is set in the context, the agent searches the repository before generating documentation. This allows Claude to reference real code examples and existing documentation rather than generating generic content.

**What RAG searches for:**

- Related markdown documentation (`search_shipwright_docs()`)
- Code examples and test functions (`extract_code_examples()`)
- API usage patterns (`search_api_patterns()`)
- Similar implementations in the codebase (`search_similar_code()`)

**Performance impact:** RAG adds approximately 1-3 seconds for typical repositories.

**Graceful fallback:** If RAG fails (missing repo_path, search error, etc.), documentation generation continues normally with a warning logged.

---

## Input Files

You can provide specific repository files as additional context. This is useful when you want the agent to document based on the actual final implementation rather than the design document.

```python
result = run_docs(
    context=context,
    input_files=[
        "pkg/apis/build/v1beta1/buildrun_types.go",
        "pkg/controller/buildrun/controller.go",
        "examples/buildrun-timeout.yaml"
    ]
)

print("Files analyzed:", result["input_files_analyzed"])
```

> **Note:** Files larger than 5,000 characters are automatically truncated with a `(truncated)` marker. Files that do not exist are skipped silently.

---

## Direct Invocation

```python
from agents.docs_agent import run_docs

context = {
    "design_analysis": "# Design: Add timeout...",
    "code_changes": {
        "pkg/apis/build/v1beta1/buildrun_types.go": "Added Timeout field to BuildRunSpec"
    },
    "test_results": {"unit": "passed", "e2e": "passed"},
    "issue_title": "Add timeout support",
    "issue_description": "Users need build timeout configuration",
    "issue_type": "feature",
    "repo_path": "/path/to/shipwright-build"  # required for RAG
}

# Standard documentation
result = run_docs(context)
print(result["pr_summary"])
print(result["release_notes"])

# All formats
result = run_docs(context=context, output_format="all")
print(result["ship_document"])
print(result["jtbd_documentation"])
print(result["high_level_design"])

# Disable RAG for faster execution
result = run_docs(context=context, enable_rag=False)
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Missing `repo_path` with RAG enabled | RAG skips gracefully, documentation continues |
| Input file does not exist | File is skipped, generation continues |
| RAG search failure | Warning logged, generation continues |
| Missing required context keys | Raises `RuntimeError: Missing required context keys` |

**Required context keys:** `design_analysis`, `code_changes`, `test_results`

---

## Upstream GitHub PR Integration

When a Jira ticket has GitHub PRs linked via remote links, the docs agent automatically includes them in an "Upstream GitHub Pull Requests" context section that is injected into the prompt before generation.

### What triggers it

The orchestration pipeline fetches Jira remote links and resolves any linked GitHub PRs before calling the docs agent. The resolved data arrives in the context as `github_pr_urls` (a list of URLs) and `github_pr_data` (a list of dicts with full PR metadata). The docs agent detects whichever is present and builds the context section accordingly.

### PR fields included in the prompt

When `github_pr_data` is available (requires `GITHUB_TOKEN` to be set at fetch time), each PR entry includes:

| Field | Description |
|-------|-------------|
| PR number and URL | Link back to the upstream pull request |
| Title | PR title as written by the author |
| State | `MERGED`, `OPEN`, or `CLOSED` |
| Author | GitHub username of the PR author |
| Base branch | Target branch the PR merges into |
| Files changed | Count of changed files with `+additions / -deletions` |
| Reviewers | Usernames of requested and completed reviewers |
| Labels | All labels attached to the PR |
| Merged at | ISO timestamp of when the PR was merged (if applicable) |
| Body | PR description, capped at 2,000 characters to control prompt size |

### Graceful fallback behavior

| Situation | Behavior |
|-----------|----------|
| `github_pr_data` present | Full metadata injected into prompt |
| `github_pr_urls` present but no `github_pr_data` | List of PR URLs injected without metadata (no `GITHUB_TOKEN` was available at fetch time) |
| Neither key present | "Upstream GitHub Pull Requests" section is omitted from the prompt entirely |

### Example output

When GitHub PR data is available, the docs agent uses it to ground the generated documentation in real upstream activity. For example, a PR summary might include:

```markdown
## PR Summary

This change adds `RuntimeClass` support to Shipwright BuildStrategies, enabling
pod-level runtime isolation for builds that require specific node capabilities.

**Upstream reference:** Implemented in [shipwright-io/community #42](https://github.com/shipwright-io/community/pull/42)
— _"Add RuntimeClass support to BuildStrategy pod template"_ (MERGED, authored by @adambkaplan,
reviewed by @qu1queee and @SaschaSchwarze0).

The upstream PR modified 6 files (+312 / -18 lines) targeting the `main` branch and was
merged on 2024-11-14. Labels: `enhancement`, `api-change`.

**What changed:**
- Added `runtimeClassName` field to `BuildStrategySpec.BuildSteps`
- CRD schema updated to include the new optional field
- Controller updated to propagate `runtimeClassName` to generated pods

**Testing:** Unit tests cover field propagation. E2E tests verify builds complete
successfully when a valid `RuntimeClass` is referenced.
```

---

[← Previous: Testing Agent](testing-agent.md) | [Next: Dashboard Overview →](../04-dashboard/overview.md)
