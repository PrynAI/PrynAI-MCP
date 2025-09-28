# Phase 1 — Feature-complete surface (local)

## Outcome

- Resource subscriptions and update notifications.

- Richer prompt structure.

- Sampling-backed “completions” path (mockable).

- Structured log notifications via ctx.info/warning.

## What we added

- Resource prynai://counter plus tool bump_counter that notifies updates.

- Prompt returns structured messages.

- Sampling path via create_message(...) with graceful fallback.

## Run
```
uv run python -m prynai_mcp.server
uv run python examples/smoke_http_phase1.py
```

#### Expected result

```
RESOURCES: ['prynai://status','prynai://counter']
COUNTER: 0
COUNTER_AFTER: 2
PROMPT TEXT: Write a concise, formal summary. Document title: MCP Phase 1 ...
SAMPLING RESULT: MOCK:...  # if client sampler provided; otherwise "sampling unavailable"
```