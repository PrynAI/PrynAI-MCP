# src/prynai/mcp_core.py
"""
Minimal, reusable MCP client helpers for LangChain/LangGraph agents.

Stable API you can import:
- get_cc_token() -> str
- list_mcp_tools() -> list[(name, description)]
- call_mcp_tool(name, args) -> str
- build_langchain_tools(tool_names: Optional[list[str]]) -> list[BaseTool]

Notes
- Each LangChain tool opens/closes its OWN MCP session per invocation.
- Avoids sharing a session (prevents anyio.ClosedResourceError).
- Ensures each tool has a docstring and passes description=... to the
  decorator, satisfying LangChain's requirement.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
from contextlib import asynccontextmanager

import msal
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict, create_model

from langchain_core.tools import tool, BaseTool

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


# ---------------------------------------------------------------------------
# Env
# ---------------------------------------------------------------------------

# Load a project-level .env if present
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

MCP_URL = os.getenv("PRYNAI_MCP_URL", "").strip()
TENANT_ID = os.getenv("ENTRA_TENANT_ID", "").strip()
CLIENT_ID = os.getenv("ENTRA_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET", "").strip()
SERVER_APP_URI = os.getenv("SERVER_APP_ID_URI", "").strip()

if not MCP_URL:
    raise RuntimeError("PRYNAI_MCP_URL is required")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_cc_token() -> str:
    """Acquire an Entra ID client-credentials access token for the MCP server."""
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    scope = f"{SERVER_APP_URI}/.default"
    res = app.acquire_token_for_client(scopes=[scope])
    if "access_token" not in res:
        raise RuntimeError(f"Token acquisition failed: {res}")
    return res["access_token"]


# ---------------------------------------------------------------------------
# MCP session helper (short-lived per call)
# ---------------------------------------------------------------------------

def _scrub_network_env() -> None:
    """Avoid proxy/CA overrides that can break TLS for ACA endpoints."""
    for k in (
        "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
        "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
        "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
    ):
        os.environ.pop(k, None)

@asynccontextmanager
async def _mcp_session(headers: Optional[Dict[str, str]] = None):
    """Yield an initialized MCP ClientSession (short-lived)."""
    _scrub_network_env()
    if headers is None:
        token = get_cc_token()
        headers = {"Authorization": f"Bearer {token}"}
    async with streamablehttp_client(MCP_URL, headers=headers, timeout=120.0) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            yield s


# ---------------------------------------------------------------------------
# Simple one-shot helpers
# ---------------------------------------------------------------------------

async def list_mcp_tools() -> List[Tuple[str, str]]:
    """Return a list of (name, description) for all server tools."""
    async with _mcp_session() as s:
        resp = await s.list_tools()
        out: List[Tuple[str, str]] = []
        for t in resp.tools:
            out.append((getattr(t, "name", ""), getattr(t, "description", "") or ""))
        return out

async def call_mcp_tool(name: str, args: Dict[str, Any]) -> str:
    """Call a specific MCP tool and return best-effort text output."""
    async with _mcp_session() as s:
        res = await s.call_tool(name, args)
        parts: List[str] = []
        for c in getattr(res, "content", []) or []:
            if getattr(c, "type", "text") == "text":
                parts.append(c.text)
        return "\n".join(parts) if parts else str(res.model_dump())


# ---------------------------------------------------------------------------
# JSON-schema → Pydantic (permissive) for LangChain tools
# ---------------------------------------------------------------------------

class _PermissiveModel(BaseModel):
    model_config = ConfigDict(extra="allow")

_JSON_TO_PY = {
    "integer": int,
    "number": float,
    "boolean": bool,
    "string": str,
    "array": list,
    "object": dict,
}

def _py_type_from_jsonschema(s: Dict[str, Any]) -> Any:
    return _JSON_TO_PY.get(s.get("type"), str)

def _args_model_from_schema(tool_name: str, schema: Optional[Dict[str, Any]]) -> type[BaseModel]:
    """Create a permissive Pydantic model from a JSON schema (best effort)."""
    if not schema or not isinstance(schema, dict):
        return create_model(f"{tool_name}_Args", __base__=_PermissiveModel)

    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    fields: Dict[str, tuple[Any, Any]] = {}

    for pname, pdef in props.items():
        pdef = pdef or {}
        py_t = _py_type_from_jsonschema(pdef if isinstance(pdef, dict) else {})
        default = ... if pname in required else None
        desc = pdef.get("description")
        fields[pname] = (
            py_t,
            Field(default, description=desc) if desc else default,
        )

    if not fields:
        return create_model(f"{tool_name}_Args", __base__=_PermissiveModel)

    return create_model(f"{tool_name}_Args", __base__=_PermissiveModel, **fields)


# ---------------------------------------------------------------------------
# LangChain tool factory
# ---------------------------------------------------------------------------

async def build_langchain_tools(tool_names: Optional[List[str]] = None) -> List[BaseTool]:
    """
    Convert MCP tools into LangChain tools.
    - tool_names=None → all tools
    - Each generated tool has a docstring and passes description=... to @tool.
    """
    # Discover tools and schemas
    async with _mcp_session() as s:
        tlist = await s.list_tools()
        schema_by_name: Dict[str, Dict[str, Any]] = {}
        for t in tlist.tools:
            schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
            schema_by_name[getattr(t, "name", "")] = schema
        selected = [t for t in tlist.tools if not tool_names or getattr(t, "name", "") in tool_names]

    tools: List[BaseTool] = []
    for t in selected:
        name = getattr(t, "name", "")
        if not name:
            continue
        desc = (getattr(t, "description", "") or "").strip() or f"MCP tool '{name}'."
        args_model = _args_model_from_schema(name, schema_by_name.get(name))

        # Bind 'name' into the function to avoid late-binding issues
        async def _impl(bound_name: str, **kwargs) -> str:
            """(Docstring set dynamically per tool below)"""
            async with _mcp_session() as s2:
                res = await s2.call_tool(bound_name, kwargs)
                parts: List[str] = []
                for c in getattr(res, "content", []) or []:
                    if getattr(c, "type", "text") == "text":
                        parts.append(c.text)
                return "\n".join(parts) if parts else str(res.model_dump())

        # Create a per-tool callable with a proper docstring (LangChain requires one)
        async def _wrapped(**kwargs) -> str:
            return await _impl(name, **kwargs)
        _wrapped.__name__ = f"mcp_{name}"
        _wrapped.__doc__ = desc  # <-- IMPORTANT for LangChain

        # Also pass description into the decorator (works across LC versions)
        wrapped_tool = tool(args_schema=args_model, description=desc)(_wrapped)
        wrapped_tool.name = name
        wrapped_tool.description = desc
        tools.append(wrapped_tool)

    return tools
