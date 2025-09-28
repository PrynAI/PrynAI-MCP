# Phase 0 — Bootstrap (local, no auth)

## Outcome

- Runnable MCP server at /mcp using Streamable HTTP.

## Features: tools, resources, prompts, sampling hook, logging, notifications.

## What we built

- server.py with tools add, echo, long_task, summarize_via_client_llm.

- Resources: prynai://status, hello://{name}.

- Prompt: quick_summary.


## Run
```
uv run python -m prynai_mcp.server
uv run python examples/smoke_http.py
```

###Expected result

```
TOOLS: ['add','echo','long_task','summarize_via_client_llm']
RESOURCES: ['prynai://status']
PROMPTS: ['quick_summary']
STATUS: ok
ADD RESULT: 5
LONG_TASK: done
SAMPLING: sampling unavailable   # expected unless the client provides a sampler
```