# Phase 5 — LangGraph + LangChain Agent + LangSmith (Smoke Tests)

This phase adds two small agents that exercise your remote MCP server:

LangGraph smoke: pulls MCP prompts/resources/tools and calls OpenAI for a short summary.
examples/phase5_langgraph_smoke.py

LangChain core “create_agent” smoke: dynamically builds LangChain tools from MCP (all tools), then lets the LLM pick “add” via natural language.
examples/phase5_langchain_create_agent_alltools_smoke.py

Core helper used by both: builds MCP session (Entra ID auth), lists tools, and converts MCP tools to LangChain tools.
src/prynai/mcp_core.py

Tiny demos:

examples/use_core_list_tools.py — list tools via the core helper

examples/use_core_langchain_agent.py — minimal “create_agent” run against MCP tools

Your production MCP server (ACA):

https://prynai-mcp.purplegrass-10f29d71.eastus.azurecontainerapps.io/mcp

## Prerequisites

Python 3.11+ (project already uses uv)

An OpenAI API key (for the LLM portions)

Azure Entra client credentials for the MCP server’s protected API

Deployed ACA app + Redis (already done in prior phases)


## Environment

```
# MCP (stable URL)
PRYNAI_MCP_URL=https://prynai-mcp.purplegrass-10f29d71.eastus.azurecontainerapps.io/mcp

# Entra ID (client credentials)
ENTRA_TENANT_ID=<your_tenant_id>
ENTRA_CLIENT_ID=<your_app_client_id>
ENTRA_CLIENT_SECRET=<your_app_client_secret>
SERVER_APP_ID_URI=api://<server-app-guid-or-app-id-uri>

# OpenAI
OPENAI_API_KEY=<your_openai_key>
OPENAI_MODEL=gpt-4o-mini

```

### Install / Update deps

```
uv sync
# For the LangChain v1 core agent helper (already added in prior steps):
uv add --prerelease=allow langchain

```
## What’s in this phase

examples/phase5_langgraph_smoke.py
A simple LangGraph that:

Gets Entra token

Lists tools

Calls add

Reads prynai://status and prynai://counter

Renders MCP prompt quick_summary and calls OpenAI

examples/phase5_langchain_create_agent_alltools_smoke.py
Uses LangChain’s create_agent and all MCP tools converted to LangChain tools. A natural language prompt (“add 7 and 8…”) makes the agent choose the right MCP tool.

src/prynai/mcp_core.py
Shared helper for:

Entra ID token acquisition

Creating an MCP session with auth headers

Converting all remote MCP tools into LangChain StructuredTools (with auto-generated pydantic arg schemas)

A small list_tools() convenience

## Run the smoke tests

### 1) LangGraph smoke

```
uv run python examples/phase5_langgraph_smoke.py
```

### Expected (abbrev):
```
TOOLS: ['add', 'echo', 'long_task', 'summarize_via_client_llm', 'bump_counter']
ADD RESULT: 15
STATUS TEXT: ok
COUNTER TEXT: 0
SUMMARY: <short summary text...>
```

### 2) LangChain “create_agent” (all tools)
```
uv run python examples/phase5_langchain_create_agent_alltools_smoke.py
```

### Expected (abbrev):
```
MCP tools discovered: ['add', 'echo', 'long_task', 'summarize_via_client_llm', 'bump_counter']
AGENT FINAL:
15
```

### 3) Core helper demos
```
uv run python examples/use_core_list_tools.py
uv run python examples/use_core_langchain_agent.py
```

### LangSmith tracing
```
export LANGCHAIN_TRACING_V2=true
export LANGSMITH_API_KEY=<your_key>
export LANGSMITH_PROJECT=prynai-mcp-phase5
```

# Deploying new server tools (ACA revisions)

When you add functions to server.py:

Commit changes locally.

Create a new ACA revision via remote ACR build using our script:

```
# From repo root
.\infra\azure\deploy_update.ps1
```

The script:

Builds a new image in ACR (tag = git short SHA or timestamp)

Creates a new revision on prynai-mcp

Prints the preview FQDN for smoke testing

Shows the command to promote 100% traffic when ready

### Promote traffic when smoke tests pass:
```
az containerapp ingress traffic set -g prynai-mcp-rg -n prynai-mcp --revision-weight <new-revision-name>=100
```

This keeps the stable URL (https://prynai-mcp....azurecontainerapps.io/mcp) unchanged while you roll forward safely.

### Troubleshooting

Auth 401: Check Entra values in .env and that your app has permission to the server’s App ID URI.

TLS/Cert issues: Ensure you’re not setting REQUESTS_CA_BUNDLE or proxy vars that override certs.

LangChain tool schema errors: The helper auto-generates pydantic schemas. If your MCP tool has complex/optional args, make sure server tool metadata describes them clearly (name, description, example input).

