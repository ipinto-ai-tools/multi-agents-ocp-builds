# Agent SDK Spike — Findings (Task #104)

## SDK Selection

We evaluated three options for replacing the custom `AnthropicVertex` client:

| Option | Package | Verdict |
| --- | --- | --- |
| Anthropic Python SDK | `anthropic` | Already in use — minimal change but no agent loop or structured output |
| Claude Code Agent SDK | `claude_agent_sdk` | **Selected** — agent loop, native tool use, structured output via Pydantic |
| Claude Code CLI | `claude` CLI | Subprocess wrapper — fragile, no structured output |

**Selected: `claude_agent_sdk`** with the `query()` async iterator for programmatic backend use.

## Key Capabilities

### Vertex AI Authentication
- Set `CLAUDE_CODE_USE_VERTEX=1` environment variable
- Uses Application Default Credentials (same as current `AnthropicVertex`)
- No code changes needed for auth — just env var

### Structured Outputs
- Pass a Pydantic model as `output_format` parameter to `query()`
- The SDK enforces the schema and returns validated data
- Maps directly to our `DesignOutput` Pydantic model from Task #106

### Custom Tools
- Define tools using the `@tool` decorator from `claude_agent_sdk`
- Tools are passed to `query()` via the `tools` parameter
- Can wrap existing functions (repo search, component lookup) as SDK tools

### Programmatic API (`query()`)
- `query()` is an async iterator that yields conversation events
- Events include: `assistant` messages, `tool_use` requests, `result` with final output
- Suitable for backend integration (not interactive CLI)

## Migration Pattern

### Before (current — `client.messages.create()`)
```python
from config.auth_config import get_anthropic_client

client = get_anthropic_client()
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8000,
    system=DESIGN_AGENT_PROMPT,
    messages=[{"role": "user", "content": user_prompt}],
)
design_text = response.content[0].text
parsed = _parse_design_output(design_text)
```

### After (target — `claude_agent_sdk.query()`)
```python
import asyncio
from claude_agent_sdk import query
from models.stage_outputs import DesignOutput

async def run_design_sdk(prompt: str) -> DesignOutput:
    result = None
    async for event in query(
        prompt=prompt,
        system=DESIGN_AGENT_PROMPT,
        output_format=DesignOutput,
        max_turns=1,
    ):
        if hasattr(event, 'result'):
            result = event.result
    return result
```

## Backward Compatibility

The migrated Design stage must work with the existing LangGraph orchestrator:
- `run_design()` keeps the same signature and return type (`Dict[str, Any]`)
- Internally uses SDK but returns the same dict structure
- Other stages (Develop, Test, Docs) remain unchanged
- The orchestrator (`agents/graph.py`) calls `run_design()` as before

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| `claude_agent_sdk` not available on PyPI | Verify installation; fallback to `anthropic` SDK if needed |
| Vertex AI auth incompatibility | Tested: `CLAUDE_CODE_USE_VERTEX=1` works with ADC |
| Structured output schema mismatch | Use same `DesignOutput` model from Task #106 |
| Performance regression | Benchmark in PoC; SDK adds agent loop overhead for single-turn |
| Async requirement | `run_design()` wrapper uses `asyncio.run()` for sync callers |

## Recommendations

1. **Use `query()` with `output_format`** — eliminates manual parsing (`_parse_design_output`)
2. **Migrate one stage at a time** — Design first, then Develop/Test/Docs in Task #106
3. **Keep sync wrapper** — `asyncio.run()` in `run_design()` for backward compat
4. **Add `claude_agent_sdk` to requirements.txt** — only when actual migration happens (not in spike)

## Next Steps

- Task #106 already defines `DesignOutput` Pydantic model
- When ready to migrate: replace `client.messages.create()` with `query()` in `agents/design_agent.py`
- Update tests to mock `claude_agent_sdk.query` instead of `client.messages.create`
