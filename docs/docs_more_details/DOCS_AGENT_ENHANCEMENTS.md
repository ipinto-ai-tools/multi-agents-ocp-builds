# Documentation Agent Enhancements

## Overview

The Documentation Agent has been enhanced with three major capabilities:

1. **Agentic RAG (Retrieval-Augmented Generation)** - Automatically fetches relevant documentation, code examples, and API usage patterns
2. **SHIP Format Output** - Structured documentation for stakeholder communication
3. **Input File Support** - Process specific files as context for documentation generation
4. **High-Level Design Generation** - Comprehensive design documents for implementation guidance

## New Features

### 1. Agentic RAG

The RAG system automatically searches the codebase for relevant context:

- **Documentation Search**: Finds related markdown documentation based on issue title and modified files
- **Code Example Extraction**: Extracts test functions, example code, and YAML manifests
- **API Pattern Discovery**: Finds how APIs are used throughout the codebase
- **Similar Implementation Search**: Identifies similar code implementations for reference

#### Usage

```python
from agents.docs_agent import run_docs

result = run_docs(
    context=agent_context,
    enable_rag=True  # Enable RAG (default: True)
)
```

The RAG system requires `repo_path` in the context:

```python
context = {
    "design_analysis": "...",
    "code_changes": {...},
    "test_results": {...},
    "repo_path": "/path/to/repository"  # Required for RAG
}
```

#### RAG Components

**RAG Search Tool** (`tools/rag_search.py`):
- `search_shipwright_docs()` - Search documentation by query
- `search_similar_code()` - Find similar implementations
- `search_api_patterns()` - Discover API usage patterns
- `extract_code_examples()` - Extract code examples from files
- `get_related_documentation()` - Find docs related to changed files

#### Example RAG Output

```python
{
    "related_docs": [
        {
            "file": "docs/buildrun-api.md",
            "section": "Timeout Configuration",
            "content": "You can configure timeout..."
        }
    ],
    "code_examples": [
        {
            "file": "test/buildrun_test.go",
            "language": "go",
            "context": "TestBuildRunTimeout",
            "code": "func TestBuildRunTimeout() { ... }"
        }
    ],
    "api_patterns": [
        {
            "api": "BuildRun",
            "file": "controller.go",
            "type": "initialization",
            "code": "br := &BuildRun{...}"
        }
    ]
}
```

### 2. SHIP Format Output

SHIP (Solution, Highlight, Impact, Plan) format provides structured documentation for stakeholders:

- **Solution**: What is being built and why
- **Highlight**: Key features, benefits, and differentiators
- **Impact**: Who is affected and how (users, operators, developers)
- **Plan**: Implementation roadmap with phases and milestones

#### Usage

```python
result = run_docs(
    context=context,
    output_format="ship"  # Options: "standard", "ship", "jtbd", "all"
)

print(result["ship_document"])
```

#### Example SHIP Document

```markdown
## SHIP Document

### Solution
Implement configurable timeout for BuildRun resources to prevent indefinite execution
and resource exhaustion in the cluster.

### Highlight
- User-configurable timeout values with intuitive duration syntax
- Automatic build termination when timeout is exceeded
- Backward compatible implementation - no breaking changes
- Minimal performance overhead (~10s granularity)
- Clear error messages when timeout triggers

### Impact

**Users**: Can prevent runaway builds from consuming cluster resources indefinitely.
No longer need external monitoring to kill hung builds.

**Operators**: Better resource management and capacity planning. Can enforce
cluster-wide timeout policies through admission webhooks.

**Developers**: Simple API addition with clear testing strategy. Follows existing
patterns in the codebase.

### Plan

**Phase 1**: Core API and CRD changes (Week 1)
- Add timeout field to BuildRun CRD
- Update API validation
- Update webhooks

**Phase 2**: Controller timeout enforcement (Week 1-2)
- Implement timeout monitoring in reconciliation loop
- Add timeout termination logic
- Handle edge cases (controller restart, etc.)

**Phase 3**: Webhook validation (Week 2)
- Validate timeout format and ranges
- Add sensible defaults
- Prevent extremely short timeouts

**Phase 4**: Documentation and examples (Week 2-3)
- User guide updates
- API reference documentation
- Working examples in examples/
- Release notes
```

### 3. Input File Support

Provide specific files as context for more targeted documentation:

```python
result = run_docs(
    context=context,
    input_files=[
        "pkg/apis/build/v1beta1/buildrun_types.go",
        "pkg/controller/buildrun/controller.go",
        "examples/buildrun-timeout.yaml"
    ]
)

# Check which files were analyzed
print(result["input_files_analyzed"])
```

#### Use Cases

- **API Documentation**: Provide type definition files for accurate field documentation
- **Configuration Examples**: Include sample YAML files to generate usage examples
- **Implementation Reference**: Show specific controller/handler implementations

### 4. High-Level Design Document

Comprehensive design documentation for implementation guidance:

```python
result = run_docs(context=context, output_format="all")

print(result["high_level_design"])
```

#### HLD Sections

1. **Overview** - What is being built, why, and success criteria
2. **Architecture** - Components, interactions, data flow, integration points
3. **Implementation Approach** - Algorithms, data structures, error handling
4. **API/Interface Design** - API specs, field types, validation rules
5. **Testing Strategy** - Unit/integration/E2E test coverage
6. **Rollout Plan** - Feature flags, compatibility, migration path
7. **Future Considerations** - Planned enhancements, limitations, extensibility

## Complete API Reference

### Function: `run_docs()`

```python
def run_docs(
    context: Dict[str, Any],
    input_files: Optional[List[str]] = None,
    output_format: str = "standard",
    enable_rag: bool = True
) -> Dict[str, Any]:
    """Generate comprehensive documentation."""
```

#### Parameters

- **context** (Dict[str, Any]): Agent context from previous phases
  - Required keys: `design_analysis`, `code_changes`, `test_results`
  - Optional: `repo_path` (required for RAG), `issue_title`, `files_modified`, etc.

- **input_files** (Optional[List[str]]): List of file paths to include as context
  - Files are read and included in the prompt
  - Large files (>5000 chars) are automatically truncated

- **output_format** (str): Documentation format
  - `"standard"`: Standard documentation (default)
  - `"ship"`: Adds SHIP document
  - `"jtbd"`: Adds Jobs-to-be-Done documentation
  - `"all"`: All formats

- **enable_rag** (bool): Enable RAG context fetching (default: True)
  - Requires `repo_path` in context
  - Gracefully falls back if RAG fails

#### Returns

Dictionary with documentation outputs:

```python
{
    # Core documentation
    "pr_summary": str,              # PR description
    "release_notes": str,           # Changelog entry
    "docs_changes": dict,           # File path -> changes
    "upgrade_notes": str,           # Version upgrade guidance
    "known_limitations": str,       # Edge cases and limitations

    # Enhanced outputs
    "high_level_design": str,       # HLD document
    "jtbd_documentation": str,      # Jobs-to-be-Done (if requested)
    "ship_document": str,           # SHIP format (if requested)

    # Metadata
    "input_files_analyzed": list,   # Files processed
    "rag_enabled": bool,            # Whether RAG was enabled
    "output_format": str            # Format requested
}
```

## Integration with Existing Workflow

The enhancements are backward compatible. Existing code continues to work:

```python
# Existing usage (still works)
result = run_docs(context)

# Enhanced usage
result = run_docs(
    context=context,
    input_files=["types.go", "controller.go"],
    output_format="ship",
    enable_rag=True
)
```

## Configuration

### Agent Prompts

Enhanced prompts in `config/agent_prompts.py` include:

- SHIP format guidelines
- High-level design structure
- RAG context integration instructions
- Input file processing guidelines

### State Management

Updated `graph/state.py` with new output fields:

```python
class AgentState(TypedDict):
    # ... existing fields ...

    # New documentation outputs
    upgrade_notes: str
    known_limitations: str
    jtbd_documentation: str
    ship_document: str
    high_level_design: str
```

## Testing

Comprehensive test coverage:

### RAG Tests (`tests/test_rag_search.py`)
- Documentation search
- Code example extraction
- API pattern discovery
- Similar code finding
- Edge cases and error handling

### Enhanced Docs Agent Tests (`tests/test_docs_agent_enhanced.py`)
- SHIP format output
- JTBD format output
- Input file processing
- RAG integration
- Metadata validation

### Run Tests

```bash
# All documentation and RAG tests
uv run pytest tests/ -k "docs_agent or rag" -v

# Specific test files
uv run pytest tests/test_rag_search.py -v
uv run pytest tests/test_docs_agent_enhanced.py -v

# Original tests (backward compatibility)
uv run pytest tests/test_docs_agent.py -v
```

## Examples

### Example 1: Standard Documentation with RAG

```python
from agents.docs_agent import run_docs

context = {
    "design_analysis": "Add timeout to BuildRun API...",
    "code_changes": {
        "pkg/apis/buildrun.go": "Added timeout field"
    },
    "test_results": {"unit": {"passed": 45}},
    "repo_path": "/path/to/repo",
    "issue_title": "Add BuildRun timeout support"
}

result = run_docs(context, enable_rag=True)

print(result["pr_summary"])
print(result["high_level_design"])
```

### Example 2: SHIP Format for Stakeholders

```python
result = run_docs(
    context=context,
    output_format="ship"
)

# Share with product/engineering leadership
with open("ship_doc.md", "w") as f:
    f.write(result["ship_document"])
```

### Example 3: Input Files for API Documentation

```python
result = run_docs(
    context=context,
    input_files=[
        "pkg/apis/build/v1beta1/buildrun_types.go",
        "examples/buildrun-timeout.yaml"
    ],
    output_format="all"
)

# Comprehensive documentation with examples from actual files
print(result["docs_changes"])
print(result["jtbd_documentation"])
```

### Example 4: Disable RAG for Speed

```python
# When working on documentation-only changes or without repo access
result = run_docs(
    context=context,
    enable_rag=False  # Skip RAG for faster execution
)
```

## Performance Considerations

- **RAG Search**: Adds ~1-3 seconds for typical repositories
- **Input Files**: Large files are automatically truncated to 5000 characters
- **Token Usage**: Increased from 4096 to 8192 max tokens for comprehensive output
- **Graceful Degradation**: RAG failures don't block documentation generation

## Error Handling

The enhanced agent includes robust error handling:

1. **Missing repo_path**: RAG gracefully skips if repo_path not provided
2. **Invalid file paths**: Input files that don't exist are skipped
3. **RAG failures**: Warning logged, documentation generation continues
4. **Large files**: Automatically truncated with "(truncated)" marker

## Future Enhancements

Potential future improvements:

- **Semantic search**: Use embeddings for more accurate documentation matching
- **Cross-repository search**: Search related projects for patterns
- **Automatic diagram generation**: Convert text descriptions to diagrams
- **Version comparison**: Show diff between versions for upgrade notes
- **Multi-language support**: Expand beyond Go to Java, Python, etc.

## Contributing

When extending the Documentation Agent:

1. Add tests for new features in `tests/test_docs_agent_enhanced.py`
2. Update prompts in `config/agent_prompts.py` for new output formats
3. Ensure backward compatibility with existing usage
4. Add documentation examples to this guide

## References

- **Agent Implementation**: `/home/israelpinto/git/muilti-agents-ocp-builds/agents/docs_agent.py`
- **RAG Tool**: `/home/israelpinto/git/muilti-agents-ocp-builds/tools/rag_search.py`
- **Agent Prompts**: `/home/israelpinto/git/muilti-agents-ocp-builds/config/agent_prompts.py`
- **Tests**: `/home/israelpinto/git/muilti-agents-ocp-builds/tests/test_docs_agent_enhanced.py`
