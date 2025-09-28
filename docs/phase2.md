# Phase 2 — Containerization + Redis sessions

## Outcome

- Containerized ASGI app with /mcp, /healthz, /livez.

- Redis-backed state for shared counter and persistence across restarts.

- Lazy Redis init for reliable startup.

## What we added

- app.py wraps mcp.streamable_http_app() and wires health routes, CORS, and Redis lifecycle.

- redis_client.py with ensure_redis().

- docker-compose.yml with mcp and redis.

- Dockerfile using Uvicorn (--lifespan on).


## Run
```
docker compose up -d --build
curl http://127.0.0.1:8000/healthz     # {"status":"ok","redis":true}
uv run python examples/smoke_http_phase1.py
docker compose restart mcp
uv run python examples/smoke_http_phase1.py   # counter persists
```

### Expected result
```
COUNTER: 2
COUNTER_AFTER: 4
...
# after restart:
COUNTER: 4
COUNTER_AFTER: 6
```

## Using with VS Code Copilot Agent Mode

### Workspace config: mcp.json

'''
{
  "servers": {
    "prynai-mcp": { "type": "http", "url": "http://127.0.0.1:8000/mcp" }
  }
}
'''

- Start the server first (local or Docker).

- In Agent Mode, tools from prynai-mcp appear under Tools.
