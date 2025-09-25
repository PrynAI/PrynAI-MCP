Phases
Phase 0 — Bootstrap (local, no auth)

Deliverables:

Python FastMCP server exposing: tools, resources, prompts, sampling, completions, logging, notifications. Transport: Streamable HTTP at /mcp. Run via uvicorn. 
GitHub

Basic Starlette ASGI mount using FastMCP.streamable_http_app(). 
GitHub

Tests:

tests/smoke/test_list_capabilities.py: client connects to http://localhost:8000/mcp, initialize(), list_tools(), list_resources(), list_prompts(), call a simple tool, assert 200-level and expected content. Client uses streamablehttp_client. 
GitHub

Phase 1 — Feature-complete protocol surface (local)

Deliverables:

Tools: echo, add, long-running with ctx.report_progress() and ctx.info() to verify notifications. 
GitHub

Resources: static and templated URIs; resource subscriptions.

Prompts: parameterized prompts with titles.

Completions + Sampling: server calls back to client sampling primitives where supported; include a deterministic “mock sampler” for tests. 
GitHub

Structured logging to stdout.

Tests:

tests/feature/test_notifications.py: assert progress events stream back.

tests/feature/test_prompts_and_completions.py: list prompts, request completions, assert schema.

tests/feature/test_resources_subscription.py: subscribe and receive an update.

Phase 2 — Containerization + local Redis sessions

Deliverables:

Dockerized ASGI app (Uvicorn). Health endpoints /healthz and /livez.

Redis-backed session/event store for multi-instance resumability; store Mcp-Session-Id keyed state and event log in Redis. Streamable HTTP remains the sole transport. 
GitHub

Tests:

docker-compose up with Redis. Run smoke tests against http://localhost:8000/mcp. Kill and restart container, reuse Mcp-Session-Id, assert session resumes.

References: Streamable HTTP session semantics and header usage. 
GitHub


# in a second shell
uv run python examples/smoke_http_phase1.py
# bump_counter will update Redis
docker compose restart mcp
uv run python examples/smoke_http_phase1.py  # COUNTER_AFTER reflects persisted value

Phase 3 — OAuth 2.0 (Entra ID) + HTTPS (still local containers)

Deliverables:

Bearer-token middleware validating Microsoft Entra ID JWT via tenant JWKS; support authorization_code + refresh_token for interactive clients and client_credentials for LangGraph services. Validate aud = App ID URI, scopes/roles required. 
Microsoft Learn
+1

Client example using the SDK’s OAuth client hooks; alternate client for service-to-service using MSAL to fetch tokens and inject Authorization: Bearer. 
GitHub

Tests:

tests/auth/test_oauth_required.py: unauthenticated 401; authenticated 200.

tests/auth/test_cc_flow.py: obtain token with client credentials and call a tool.

Phase 4 — Azure Container Apps (ACA) + Azure Cache for Redis

Deliverables:

IaC/CLI scripts to provision: ACA environment, Container App, Azure Cache for Redis, secrets, scaling rules, ingress HTTPS. ACA provides HTTPS by default; add custom domain + cert when ready. 
Microsoft Learn
+2
Microsoft Learn
+2

VNET-enabled option and private Redis endpoint variants.

ACA logging to Log Analytics.

Tests:

scripts/smoke_aca.sh: curl health; Python client hits https://<app>.azurecontainerapps.io/mcp, lists tools.

Redis connectivity check from app startup logs.

References: ACA + Redis integration patterns. 
Microsoft Learn
+1

Phase 5 — LangGraph + LangSmith integration smoke

Deliverables:

Minimal LangGraph agent node that uses the MCP Python client to call PrynAI MCP over Streamable HTTP using client credentials. Emit traces to LangSmith via env vars. (Use MCP client example API for HTTP streams.) 
GitHub

Tests:

examples/langgraph_smoke.py: run the graph, confirm it invokes MCP tool and returns result; verify log lines and LangSmith run created.

Phase 6 — Hardening and scale

Deliverables:

Horizontal scaling (min/max replicas) and KEDA rules based on concurrent connections/CPU.

CORS config exposing Mcp-Session-Id when browser-based clients are used. 
GitHub

WAF or API Management front door optional; keep MCP at /mcp. (API Management + OAuth is compatible if desired.) 
Microsoft Learn

Tests:

Locust/Gunicorn-style load test: N parallel initialize() + tool calls; assert <p95 latency budget and no session loss.