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


## Phase 3 — OAuth 2.0 (Entra ID) + HTTPS

### Outcome
- `/mcp` protected by Microsoft Entra ID (OAuth 2.0, JWT).
- Optional HTTPS with local certs.
- Health endpoints stay open.

### What changed
- `auth/azure_oauth.py`: JWT validate via tenant JWKS. Enforce issuer, audience, optional scopes/roles.
- `auth/middleware.py`: Bearer auth on `/mcp`. Health paths bypassed.
- `app.py`: plugs middleware. Keeps Redis, CORS, health.
- `examples/smoke_oauth_cc.py`: client-credentials smoke using MSAL.

### Entra prerequisites
1. **Server app** (exposes API). Note its **Application (client) ID**.
2. **Client app** with **application permission** to the server app.
3. **Admin consent** granted for that permission.
4. Tenant ID available.

### Config (docker-compose)
```version: "3.9"
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"

  mcp:
    build:
      context: .
      dockerfile: infra/docker/Dockerfile
    environment:
      - REDIS_URL=${REDIS_URL}
      - PRYNAI_ENV=container
      - PRYNAI_BUILD=${GIT_COMMIT:-local}
      - AUTH_REQUIRED=true               # enforce OAuth
      - ENTRA_TENANT_ID=${ENTRA_TENANT_ID}
      - ENTRA_AUDIENCES=${SERVER_APP_ID} # or the server app's client-id
      # Optional scope/role checks:
      # - ENTRA_REQUIRED_SCOPES=Mcp.Invoke
      # - ENTRA_REQUIRED_APP_ROLES=Mcp.Invoke
      # HTTPS (optional)
      # Comment these lines to serve HTTP on 8000 instead
      - SSL_CERTFILE=/certs/127.0.0.1+1.pem
      - SSL_KEYFILE=/certs/127.0.0.1+1-key.pem
    volumes:
      - ./certs:/certs:ro
    ports:
      - "8443:8443"    # HTTPS
      - "8000:8000"
    depends_on:
      - redis

volumes:
  redisdata:
```
HTTPS options

HTTP local: simplest. Omit SSL_* vars. Use http://127.0.0.1:8000/mcp.

HTTPS local: generate certs with mkcert. Mount under /certs. Expose 8443.
To make Python trust mkcert:
setx SSL_CERT_FILE "C:\Users\riahl\AppData\Local\mkcert\rootCA.pem"
Then use https://127.0.0.1:8443/mcp.

Run
```
docker compose up -d --build
# health
curl -k https://127.0.0.1:8443/healthz   # if HTTPS
# or
curl http://127.0.0.1:8000/healthz
```

Smoke test (client-credentials)

Set env: Suggestion to create .env file and add configuration to the file 

or for that session set as below 
```
$env:ENTRA_TENANT_ID="<tenant-guid>"
$env:ENTRA_CLIENT_ID="<client-app-guid>"
$env:ENTRA_CLIENT_SECRET="<client-secret>"
$env:SERVER_APP_ID_URI="api://<server-app-guid>"
# pick URL matching your transport
$env:PRYNAI_MCP_URL="http://127.0.0.1:8000/mcp"
# or: $env:PRYNAI_MCP_URL="https://127.0.0.1:8443/mcp"

uv run python examples/smoke_oauth_cc.py ## check the right .env path for load_dotenv(dotenv_path="../.env",verbose=True) 
```
Expected
```
TOOLS: [...]
ADD RESULT: 15
STATUS: ok
```

VSCode agent testing:
```
{
    "inputs": [
        {
            "id": "token",
            "type": "promptString",
            "title": "Paste an access token",
            "description": "Get a token via MSAL client credentials",
            "password": true
        }
    ],
    "servers": {
        "PrynAI MCP": {
            "type": "http",
            "url": "https://127.0.0.1:8443/mcp",
            "headers": {
                "Authorization": "Bearer ${input:token}"
            }
        }
    }
}
```

Common 401 causes : 

aud mismatch: set ENTRA_AUDIENCES to the server app GUID

copes enforced for CC: client-credentials tokens lack scp. Do not set ENTRA_REQUIRED_SCOPES here.

roles enforced but not granted: either grant the app role and admin consent, or clear ENTRA_REQUIRED_APP_ROLES.


## Phase 4 — Azure Container Apps (ACA) + Azure Cache for Redis

### Outcome

PrynAI MCP runs on ACA with public HTTPS /mcp.
Redis-backed sessions on Azure Cache for Redis.
OAuth2 enforced by Entra ID. Health probes exposed.

### What we deployed

ACA environment + app: public ingress on 443, app listens on 8000.

Azure Cache for Redis: TLS on 6380. App reads REDIS_URL at startup.

Health endpoints: /healthz returns {"status":"ok","redis":<bool>}; /livez always ok.

MCP surface: tools add, echo, long_task, summarize_via_client_llm, bump_counter; resources prynai://status, prynai://counter; prompt quick_summary.

### Prerequisites

Azure CLI logged in and subscription selected.

Docker Desktop running.

Entra apps created:

Server app exposing API (use its GUID and api://<GUID>).

Client app with application permission to server API and admin consent granted.

.env contains:

ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, SERVER_APP_ID_URI, SERVER_APP_ID.


### Deploy
Set required env and run the script:
```

.\infra\azure\deploy_aca.ps1

```

The script builds and pushes the image to a new ACR, creates Redis, creates ACA Env and App, wires secrets and env, and prints the FQDN.

Note the outputs:


```
ACA FQDN: <name>.<hash>.eastus.azurecontainerapps.io
MCP URL:  https://<fqdn>/mcp
```

### Health check
```
curl https://<fqdn>/healthz
# -> {"status":"ok","redis":true}

If redis:false, validate the secret format rediss://:<key>@<host>:6380/0 and restart the app.
```

### Smoke test (client-credentials, cloud)

Use the ACA smoke client. It fetches a token with MSAL and calls the remote MCP.

```
uv run python examples/smoke_oauth_ccACADeployment.py
# Expected:
# TOOLS: [...]
# ADD RESULT: 15
# STATUS: ok

```

### Token generator (optional) to inspect aud, iss, roles
```
uv run python examples/Generatetoken.py
```

### VS Code Agent Mode
Use a header token, not dynamic registration.

```
{
    "inputs": [
        {
            "id": "token",
            "type": "promptString",
            "title": "Paste an access token",
            "description": "Get a token via MSAL client credentials",
            "password": true
        }
    ],
    "servers": {
        "PrynAI MCP": {
            "type": "http",
            "url": "https://prynai-mcp.purplegrass-10f29d71.eastus.azurecontainerapps.io/mcp",
            "headers": {
                "Authorization": "Bearer ${input:token}"
            }
        }
    }
}

Generate a token with the helper, paste when prompted.
```

### Operate

Logs and scale:
```
az containerapp logs show -g <rg> -n prynai-mcp --follow
az containerapp update    -g <rg> -n prynai-mcp --min-replicas 2 --max-replicas 10
```

Roll a new image:
```
$acr = (az acr list -g <rg> --query "[0].loginServer" -o tsv)
docker build -f infra/docker/Dockerfile -t $acr/prynai-mcp:phase4 .
az acr login -n ($acr.Split('.')[0])
docker push $acr/prynai-mcp:phase4
az containerapp update -g <rg> -n prynai-mcp --image $acr/prynai-mcp:phase4

```

### Troubleshooting

401: Token audience mismatch. ACA expects ENTRA_AUDIENCES to include <server-app-guid> and api://<server-app-guid>. Token aud must match. Auth middleware returns structured 401 with WWW-Authenticate.

Not Acceptable: Client must accept text/event-stream: You hit /mcp with curl. Use the MCP client or the smoke script. Health checks use /healthz.

Redis stays false: Wrong REDIS_URL or missing hostname. Fix secret and restart.

TLS errors from client: Remove local overrides like SSL_CERT_FILE or REQUESTS_CA_BUNDLE. The ACA cert is a public Microsoft chain.

Proxy interference: The ACA smoke clears proxy envs before connecting. Use it as-is


### Source map (phase 4 relevant)

Server surface and tools: src/prynai_mcp/server.py.

App factory, health, CORS, auth wiring: src/prynai_mcp/app.py.

Redis client: src/prynai_mcp/redis_client.py.

OAuth config and middleware: src/prynai_mcp/config.py, src/prynai_mcp/auth/azure_oauth.py, src/prynai_mcp/auth/middleware.py.

Cloud smoke: examples/smoke_oauth_ccACADeployment.py.

This phase delivers a production entry on Azure with Redis-backed state, OAuth, and health visibility















