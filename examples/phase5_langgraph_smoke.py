# examples/phase5_langgraph_smoke.py
"""
Phase 5: LangGraph + LangSmith smoke hitting the remote PrynAI MCP.

Flow:
1) Acquire Entra ID client-credentials token.
2) Open an MCP HTTP session (Streamable HTTP) with Bearer auth.
3) List tools, call 'add', read 'status' and 'counter'.
4) Fetch MCP prompt 'quick_summary' (args: title, tone), then
   append the body text as a user message and summarize via OpenAI.

Notes:
- Keeps MCP sessions fully contained per call with a real async
  context manager to avoid anyio cancel-scope errors.
- Normalizes prompt parts so it works whether parts are SDK objects,
  dicts, strings, or tuples like ('text', '...').
- Removes proxy/CA envs that often break TLS on Windows shells.
"""

import os
import asyncio
import msal
from typing import List, TypedDict, Dict, Any
from contextlib import asynccontextmanager
from collections.abc import Mapping
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    BaseMessage,
)

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


# ---------- ENV / CONFIG ----------

# Load repo-level .env if present
load_dotenv(dotenv_path="./.env", verbose=False)

# Strip local proxy/CA overrides that can cause TLS failures
for k in (
    "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
    "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
):
    os.environ.pop(k, None)

# Remote MCP endpoint published in Phase 4 (ACA)
MCP_URL = os.getenv(
    "PRYNAI_MCP_URL",
    "https://prynai-mcp.purplegrass-10f29d71.eastus.azurecontainerapps.io/mcp",
)

# Entra ID (client credentials)
TENANT_ID = os.environ["ENTRA_TENANT_ID"]
CLIENT_ID = os.environ["ENTRA_CLIENT_ID"]
CLIENT_SECRET = os.environ["ENTRA_CLIENT_SECRET"]
SERVER_APP_URI = os.environ["SERVER_APP_ID_URI"]  # e.g., "api://<server-app-guid>"

# OpenAI model to use via LangChain
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ---------- AUTH (client credentials) ----------

def get_cc_token() -> str:
    """Acquire a Bearer token for the server resource using client credentials."""
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    scopes = [f"{SERVER_APP_URI}/.default"]
    res = app.acquire_token_for_client(scopes=scopes)
    if "access_token" not in res:
        raise RuntimeError(f"Token error: {res}")
    return res["access_token"]


# ---------- MCP SESSION (real async CM to avoid anyio scope errors) ----------

@asynccontextmanager
async def mcp_session(headers: Dict[str, str]):
    """
    Provides an initialized MCP ClientSession as an async context manager.

    Each use creates/tears down its own task group inside the MCP client,
    which avoids “Attempted to exit cancel scope in a different task” errors
    when LangGraph runs nodes concurrently.
    """
    async with streamablehttp_client(MCP_URL, headers=headers, timeout=60.0) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


# ---------- PROMPT PART NORMALIZATION ----------

def _part_text(part) -> str | None:
    """
    Extract text from varied part representations:
    - SDK objects with .text
    - plain str
    - dict-like {"type": "text", "text": "..."} or {"text": "..."}
    - tuple/list forms ("text", "...") or ("text", {"text": "..."})
    """
    if hasattr(part, "text"):
        return getattr(part, "text")
    if isinstance(part, str):
        return part
    if isinstance(part, Mapping):
        if part.get("type") == "text" and "text" in part:
            return part["text"]
        if "text" in part:
            return part["text"]
    if isinstance(part, (tuple, list)) and len(part) >= 2 and part[0] in ("text", b"text"):
        v = part[1]
        if isinstance(v, str):
            return v
        if isinstance(v, Mapping) and "text" in v:
            return v["text"]
    return None


# ---------- MCP HELPERS ----------

async def mcp_list_tools(headers) -> List[str]:
    async with mcp_session(headers) as s:
        tools = await s.list_tools()
        return [t.name for t in tools.tools]

async def mcp_call_tool(headers, name: str, args: Dict[str, Any]) -> str:
    async with mcp_session(headers) as s:
        out = await s.call_tool(name, args)
        return out.content[0].text  # server returns a single text part

async def mcp_read_resource(headers, uri: str) -> str:
    async with mcp_session(headers) as s:
        r = await s.read_resource(uri)
        return r.contents[0].text

async def mcp_render_prompt(headers, prompt_name: str, args: Dict[str, Any]) -> List[BaseMessage]:
    """
    Fetch an MCP prompt and convert to LangChain messages.
    Your `quick_summary` accepts only {title, tone}.
    """
    role_map = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    async with mcp_session(headers) as s:
        p = await s.get_prompt(prompt_name, args)
        msgs: List[BaseMessage] = []
        for m in p.messages:
            role = getattr(m, "role", "user")
            texts: List[str] = []
            for part in getattr(m, "content", []) or []:
                t = _part_text(part)
                if t:
                    texts.append(t)
            if not texts:
                continue
            cls = role_map.get(role, HumanMessage)
            msgs.append(cls(content="\n".join(texts)))
        return msgs


# ---------- LANGGRAPH STATE / NODES ----------

class GraphState(TypedDict, total=False):
    token: str
    headers: Dict[str, str]
    tools: List[str]
    add_result: str
    status: str
    counter: str
    summary: str

async def node_auth(state: GraphState) -> GraphState:
    """Create Authorization header once."""
    tok = get_cc_token()
    return {"token": tok, "headers": {"Authorization": f"Bearer {tok}"}}

async def node_list_tools(state: GraphState) -> GraphState:
    return {"tools": await mcp_list_tools(state["headers"])}

async def node_call_add(state: GraphState) -> GraphState:
    return {"add_result": await mcp_call_tool(state["headers"], "add", {"a": 7, "b": 8})}

async def node_read_resources(state: GraphState) -> GraphState:
    status = await mcp_read_resource(state["headers"], "prynai://status")
    counter = await mcp_read_resource(state["headers"], "prynai://counter")
    return {"status": status, "counter": counter}

async def node_prompt_and_llm(state: GraphState) -> GraphState:
    """
    Render MCP prompt 'quick_summary' with accepted args {title, tone}.
    Then append the body text as an extra user message and summarize with OpenAI.
    """
    msgs = await mcp_render_prompt(
        state["headers"],
        "quick_summary",
        {"title": "MCP Phase 5", "tone": "formal"},
    )
    msgs.append(HumanMessage(content="Show that the agent can use MCP prompts and tools."))

    if not os.getenv("OPENAI_API_KEY"):
        return {"summary": "sampling unavailable"}

    llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)
    ai = await llm.ainvoke(msgs)
    return {"summary": ai.content}


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("auth", node_auth)
    g.add_node("list_tools", node_list_tools)
    g.add_node("call_add", node_call_add)
    g.add_node("read_resources", node_read_resources)
    g.add_node("prompt_llm", node_prompt_and_llm)

    g.set_entry_point("auth")
    g.add_edge("auth", "list_tools")
    g.add_edge("list_tools", "call_add")
    g.add_edge("call_add", "read_resources")
    g.add_edge("read_resources", "prompt_llm")
    g.add_edge("prompt_llm", END)
    return g.compile()


# ---------- MAIN ----------

async def main():
    graph = build_graph()
    result = await graph.ainvoke({})
    print("TOOLS:", result.get("tools"))
    print("ADD RESULT:", result.get("add_result"))
    print("STATUS TEXT:", result.get("status"))
    print("COUNTER TEXT:", result.get("counter"))
    print("SUMMARY:", (result.get("summary") or "")[:160], "...")

if __name__ == "__main__":
    asyncio.run(main())
