# PrynAI MCP — Self-hosted MCP Server

Production-ready **Model Context Protocol (MCP)** server plus client examples that show how to:
- Run locally and in Docker
- Deploy to **Azure Container Apps (ACA)** behind **Entra ID (OAuth2 client credentials)**
- Use **Azure Cache for Redis** for state
- Call MCP tools/resources/prompts from **LangGraph** and **LangChain** agents
- Roll out new server revisions safely (blue/green via ACA revisions)

> 📚 Step-by-step guides live in [`/docs`](./docs): [Phase 1](./docs/phase1.md) · [Phase 2](./docs/phase2.md) · [Phase 3](./docs/phase3.md) · [Phase 4](./docs/phase4.md) · [Phase 5](./docs/phase5.md)

---

## Repo layout

.
├─ server.py # MCP server (tools/resources/prompts)
├─ src/prynai/mcp_core.py # Client helpers: auth, MCP sessions, LangChain tools
├─ examples/ # Smoke tests for each phase
│ ├─ smoke_oauth_ccACADeployment.py
│ ├─ phase5_langgraph_smoke.py
│ ├─ phase5_langchain_create_agent_alltools_smoke.py
│ ├─ use_core_list_tools.py
│ └─ use_core_langchain_agent.py
├─ infra/
│ ├─ docker/Dockerfile
│ ├─ docker-compose.yml
│ └─ azure/
│ ├─ deploy_aca.ps1 # First-time deploy (env + app)
│ └─ deploy_update.ps1 # Remote build in ACR + new ACA revision + traffic
├─ docs/ # Phase guides
└─ .env.example # Sample environment


---

## Features

- ✅ MCP Server (HTTP streamable) with example tools: `add`, `echo`, `long_task`, `bump_counter`, `summarize_via_client_llm`
- ✅ MCP resources (e.g., `prynai://status`, `prynai://counter`)
- ✅ MCP prompts (e.g., `quick_summary`)
- ✅ OAuth2 (Entra ID client credentials) on `/mcp`
- ✅ Redis-backed state (counter)
- ✅ ACA deployment with **remote image builds** in ACR and **multi-revision** rollouts
- ✅ LangGraph + LangChain agents that auto-discover MCP tools

---

## Quick start

### 1) Clone & create env
```bash
git clone https://github.com/PrynAI/PrynAI-MCP.git
cd PrynAI-MCP
cp .env.example .env
# Fill in: PRYNAI_MCP_URL, ENTRA_* , SERVER_APP_ID_URI, OPENAI_API_KEY/OPENAI_MODEL, REDIS_*
```

### 2) Run locally (Python)

```
uv sync
uv run python examples/use_core_list_tools.py
uv run python examples/use_core_langchain_agent.py
```

## Deploy to Azure Container Apps

### First-time (creates env, app, wiring): see docs/phase4.md

### Updates (safe remote build + new revision):

# From repo root
.\infra\azure\deploy_update.ps1
# Script prints preview FQDN; smoke test it, then promote 100% traffic (also printed).

## Versioning & releases

- Tags: MAJOR.MINOR.PATCH-qualifier (e.g., 0.5.0-phase5)

- Create annotated tags and optional GitHub Releases.

- Deployment scripts accept -Tag to pin the image.

## Contributing

- Fork & create a feature branch.

- Add/modify tools in server.py (sync or async are supported).

- Add tests/smoke in examples/.

- Run ruff/black (if configured) and uv run smoke tests.

-Open a PR with a clear description.

⚠️ Never commit secrets. .env is local only.

## Support

- Issues: GitHub Issues

- Security: security@ (responsible disclosure)


---

### `docs/phase1.md`

```markdown
# Phase 1 — Local MCP server & first tool

## Goal
Run the MCP server locally, expose a health check, and implement basic tools/resources/prompts.

## What you get
- `server.py` with tools: `add`, `echo`
- Resource: `prynai://status`
- Prompt: `quick_summary` (simple template)
- Local smoke tests under `examples/`

## Prereqs
- Python 3.11+ and `uv`
- (Optional) Docker if you prefer containers

## Setup
```bash
cp .env.example .env
# For Phase 1 local runs you can temporarily leave OAuth off or point to dev values.
uv sync
```

### Run

```
uv run python examples/smoke_http_phase1.py
# Lists tools via HTTP stream to /mcp (no OAuth in this phase)

MCP tools discovered: ['add', 'echo', ...]
```

## Move to Phase 2 to add Redis and stateful behavior.


---

### `docs/phase2.md`

```markdown
# Phase 2 — Redis state (counter)

## Goal
Add Redis to persist state and expose a counter as an MCP resource/tool.

## What you get
- Redis connection (via `REDIS_URL` or host/port/password)
- `bump_counter` tool
- `prynai://counter` resource

## Prereqs
- A Redis instance (local or cloud)
- Update `.env` with Redis settings

## Run locally
bash
# Option A: docker compose (includes Redis)
docker compose up --build

# Option B: your own Redis, run server with uv
uv run python examples/use_core_list_tools.py
uv run python examples/use_core_langchain_agent.py
```

### Smoke


# List tools and call counter
uv run python examples/use_core_list_tools.py
# Expect 'bump_counter' and resource 'prynai://counter'

## Troubleshooting

- If counter doesn’t change, verify Redis connectivity and credentials.

- Make sure the server process can reach Redis from its network.


---

### `docs/phase3.md`

```markdown
# Phase 3 — OAuth (Entra ID client credentials)

## Goal
Protect `/mcp` with Entra ID (Azure AD) OAuth2 (client credentials flow).

## What you get
- Server validates `Authorization: Bearer <token>`
- Example client code to fetch tokens via `msal`

## Configure Entra
- **App registrations**: one for the server (expose API), one for the client
- Record:
  - `ENTRA_TENANT_ID`
  - `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` (client app)
  - `SERVER_APP_ID_URI` (e.g., `api://<server-app-id>`)

Update `.env`:
```

### ENTRA_TENANT_ID=...
### ENTRA_CLIENT_ID=...
### ENTRA_CLIENT_SECRET=...
### SERVER_APP_ID_URI=api://...


## Smoke
```bash
uv run python examples/smoke_oauth_ccACADeployment.py
# Shows 401 if missing token, 200 with token; lists tools & reads resources.
```

## Troubleshooting

- 401/missing_or_malformed: check Authorization header and scopes (<SERVER_APP_ID_URI>/.default).

- SSL issues: ensure you haven’t set custom CA/proxy envs locally unless intended.


---

### `docs/phase4.md`

```markdown
# Phase 4 — Azure Container Apps deployment

## Goal
Deploy the MCP server to **Azure Container Apps (ACA)**, use **Azure Container Registry (ACR)** for images, and wire **Redis** & OAuth secrets.

## Azure resources (example names)
- RG: `prynai-mcp-rg`
- ACA Env: `prynai-aca-env`
- Container App: `prynai-mcp` → `https://<fqdn>/mcp`
- ACR: `prynaiacr44058.azurecr.io`
- Azure Cache for Redis: e.g., `prynai-redis.redis.cache.windows.net`

## First-time deploy
Use `infra/azure/deploy_aca.ps1` (provisions env/app + initial image). Fill environment in the script or pass parameters as needed.

## Updating (safe rollout)
Use **remote build** + **revision traffic** via:
```powershell
.\infra\azure\deploy_update.ps1 -Tag 0.5.0-phase5
# Script prints a new revision FQDN for smoke tests and the promote command.

### What the update script does:

- Builds a new image in ACR (no local Docker needed).

- Creates a new ACA revision with that image.

- Keeps multiple revisions enabled for safe testing.

- You manually promote traffic to 100% when satisfied.


## Promote to 100%

### The script prints the exact az containerapp ingress traffic set ... command with the new revision name.

## Troubleshooting

- If a revision gets a new sub-FQDN, that’s expected in “multiple revisions” mode. Your stable app URL stays the same once you promote.


---

### `docs/phase5.md`

```markdown
# Phase 5 — Agents (LangGraph & LangChain) + LangSmith

## Goal
Demonstrate agents that **discover and call MCP tools** and prompts. Show both **LangGraph** and **LangChain** flows. Optional **LangSmith** tracing.

## What you get
- `examples/phase5_langgraph_smoke.py`: 5-step graph
  1) Acquire Entra token
  2) List tools
  3) Call `add`
  4) Read `prynai://status` & `prynai://counter`
  5) Render `quick_summary` and ask OpenAI to summarize
- `examples/phase5_langchain_create_agent_alltools_smoke.py`: build **all** MCP tools into LangChain tools and let the agent pick
- `examples/use_core_langchain_agent.py`: minimal `create_agent` usage
- `src/prynai/mcp_core.py`: **reusable** building block to:
  - fetch token
  - create MCP sessions
  - convert MCP tool catalog → LangChain tools (with Pydantic arg models)
  - (Optionally) return a single “add-only” tool if you want a scoped agent

## Env
```

PRYNAI_MCP_URL=https://<your-aca-fqdn>/mcp
ENTRA_TENANT_ID=...
ENTRA_CLIENT_ID=...
ENTRA_CLIENT_SECRET=...
SERVER_APP_ID_URI=api://...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

## Optional LangSmith

LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=PrynAI-MCP


## Run
```bash
uv run python examples/phase5_langgraph_smoke.py
uv run python examples/phase5_langchain_create_agent_alltools_smoke.py
uv run python examples/use_core_langchain_agent.py
```

## Adding new tools

- Implement sync or async functions in server.py. Both work.

- Register them like existing tools; include helpful docstrings (agents read these).

- If args are structured, ensure they’re validated server-side (Pydantic or your schema).

- Re-deploy with infra/azure/deploy_update.ps1 -Tag <new-tag> and smoke test the new revision before promoting.







