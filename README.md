# PrynAI MCP — Self-hosted MCP Server

Python MCP server with Streamable HTTP transport. Local first. Dockerized with Redis for state. Built to scale out later on Azure.

## Stack

- Python 3.12+
- [`mcp` Python SDK]
- Starlette + Uvicorn
- Redis (for Phase 2)
- Docker Compose

## Repo layout

src/prynai_mcp/
server.py # FastMCP server (tools, resources, prompts, sampling, logging, notifications)
app.py # ASGI app (SHTTP + /healthz + /livez), container entry
config.py # settings (REDIS_URL, CORS)
redis_client.py # lazy Redis init
examples/
smoke_http.py
smoke_http_phase1.py
infra/docker/
Dockerfile
docker-compose.yml


## Prereqs

- Python and `uv` (or pip)
- Docker Desktop

---

## Quick start

Local:
```bash
uv venv
uv pip install -e .
uv run python -m prynai_mcp.server   # serves http://127.0.0.1:8000/mcp
uv run python examples/smoke_http.py


Docker + Redis:

docker compose up -d --build
curl http://127.0.0.1:8000/healthz
uv run python examples/smoke_http_phase1.py


VS Code Copilot Agent Mode (MCP):

// .vscode/mcp.json
{
  "servers": {
    "prynai-mcp": { "type": "http", "url": "http://127.0.0.1:8000/mcp" }
  }
}

Phase 0 — Bootstrap (local, no auth)

Outcome

Runnable MCP server at /mcp using Streamable HTTP.

Features: tools, resources, prompts, sampling hook, logging, notifications.

What we built

server.py with tools add, echo, long_task, summarize_via_client_llm.

Resources: prynai://status, hello://{name}.

Prompt: quick_summary.


Run

uv run python -m prynai_mcp.server
uv run python examples/smoke_http.py


Expected result

TOOLS: ['add','echo','long_task','summarize_via_client_llm']
RESOURCES: ['prynai://status']
PROMPTS: ['quick_summary']
STATUS: ok
ADD RESULT: 5
LONG_TASK: done
SAMPLING: sampling unavailable   # expected unless the client provides a sampler


Phase 1 — Feature-complete surface (local)

Outcome

Resource subscriptions and update notifications.

Richer prompt structure.

Sampling-backed “completions” path (mockable).

Structured log notifications via ctx.info/warning.

What we added

Resource prynai://counter plus tool bump_counter that notifies updates.

Prompt returns structured messages.

Sampling path via create_message(...) with graceful fallback.

Run

uv run python -m prynai_mcp.server
uv run python examples/smoke_http_phase1.py


Expected result

RESOURCES: ['prynai://status','prynai://counter']
COUNTER: 0
COUNTER_AFTER: 2
PROMPT TEXT: Write a concise, formal summary. Document title: MCP Phase 1 ...
SAMPLING RESULT: MOCK:...  # if client sampler provided; otherwise "sampling unavailable"


Phase 2 — Containerization + Redis sessions

Outcome

Containerized ASGI app with /mcp, /healthz, /livez.

Redis-backed state for shared counter and persistence across restarts.

Lazy Redis init for reliable startup.

What we added

app.py wraps mcp.streamable_http_app() and wires health routes, CORS, and Redis lifecycle.

redis_client.py with ensure_redis().

docker-compose.yml with mcp and redis.

Dockerfile using Uvicorn (--lifespan on).


Run

docker compose up -d --build
curl http://127.0.0.1:8000/healthz     # {"status":"ok","redis":true}
uv run python examples/smoke_http_phase1.py
docker compose restart mcp
uv run python examples/smoke_http_phase1.py   # counter persists


Expected result

COUNTER: 2
COUNTER_AFTER: 4
...
# after restart:
COUNTER: 4
COUNTER_AFTER: 6


Using with VS Code Copilot Agent Mode

Workspace config: mcp.json

{
  "servers": {
    "prynai-mcp": { "type": "http", "url": "http://127.0.0.1:8000/mcp" }
  }
}


Start the server first (local or Docker).

In Agent Mode, tools from prynai-mcp appear under Tools.








