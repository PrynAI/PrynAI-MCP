# examples/phase5_langchain_create_agent_alltools_smoke.py
import os, asyncio, msal
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Tuple
from dotenv import load_dotenv
from pydantic import create_model
from langchain.agents import create_agent
from langchain.tools import tool  # decorator, used programmatically
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    BaseMessage,
    ToolMessage,
)
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv("./.env")

# Remove proxy/CA envs that often break TLS on Windows
for k in (
    "SSL_CERT_FILE","REQUESTS_CA_BUNDLE",
    "HTTP_PROXY","http_proxy","HTTPS_PROXY","https_proxy",
    "ALL_PROXY","all_proxy","NO_PROXY","no_proxy"
):
    os.environ.pop(k, None)

MCP_URL = os.environ["PRYNAI_MCP_URL"]
TENANT_ID = os.environ["ENTRA_TENANT_ID"]
CLIENT_ID = os.environ["ENTRA_CLIENT_ID"]
CLIENT_SECRET = os.environ["ENTRA_CLIENT_SECRET"]
SERVER_APP_ID_URI = os.environ["SERVER_APP_ID_URI"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def bearer() -> str:
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    r = app.acquire_token_for_client(scopes=[f"{SERVER_APP_ID_URI}/.default"])
    if "access_token" not in r:
        raise RuntimeError(f"token error: {r}")
    return r["access_token"]

@asynccontextmanager
async def mcp_session():
    headers = {"Authorization": f"Bearer {bearer()}"}
    async with streamablehttp_client(MCP_URL, headers=headers, timeout=60.0) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            yield s

def _py_type(t: str):
    return {"string": str, "integer": int, "number": float, "boolean": bool}.get(t, str)

def args_model_from_schema(name: str, schema: Dict[str, Any]):
    schema = schema or {}
    props = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    fields: Dict[str, Tuple[type, Any]] = {}
    for k, spec in props.items():
        fields[k] = (_py_type(spec.get("type", "string")), ... if k in required else None)
    if not fields:  # permissive fallback
        fields["payload"] = (str, None)
    return create_model(f"MCP_{name}_Args", **fields)  # type: ignore

async def build_all_mcp_tools() -> List[Any]:
    tools = []
    async with mcp_session() as s:
        catalog = await s.list_tools()
        print("MCP tools discovered:", [t.name for t in catalog.tools])

        for t in catalog.tools:
            tool_name = t.name
            desc = (getattr(t, "description", "") or f"MCP tool {tool_name}").strip()
            schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
            if hasattr(schema, "model_dump"):
                schema = schema.model_dump()
            elif hasattr(schema, "to_dict"):
                schema = schema.to_dict()
            elif not isinstance(schema, dict):
                schema = {}

            ArgsModel = args_model_from_schema(tool_name, schema)

            async def _dyn_tool(_tool_name=tool_name, **kwargs) -> str:
                """{desc}"""
                async with mcp_session() as s2:
                    out = await s2.call_tool(_tool_name, kwargs)
                    parts = []
                    for c in getattr(out, "content", []) or []:
                        txt = getattr(c, "text", None)
                        if txt is None and isinstance(c, dict):
                            txt = c.get("text")
                        if isinstance(txt, str):
                            parts.append(txt)
                    return "\n".join(parts) if parts else ""

            wrapped = tool(args_schema=ArgsModel)(_dyn_tool)
            wrapped.name = tool_name
            wrapped.description = desc
            tools.append(wrapped)

    return tools

# ---------------- Formatter ----------------
def format_conversation(result_dict: Dict[str, Any]) -> str:
    lines = []
    for msg in result_dict.get("messages", []):
        if isinstance(msg, HumanMessage):
            lines.append(f"👤 Human: {msg.content}")
        elif isinstance(msg, AIMessage):
            if msg.content:
                lines.append(f"🤖 AI: {msg.content}")
            tool_calls = msg.additional_kwargs.get("tool_calls", [])
            for call in tool_calls:
                fn = call["function"]["name"]
                args = call["function"]["arguments"]
                lines.append(f"🤖 AI → ToolCall: {fn}({args})")
        elif isinstance(msg, ToolMessage):
            lines.append(f"🛠 Tool[{msg.name}]: {msg.content}")
        else:
            lines.append(f"❓ {msg}")
    return "\n".join(lines)

# ---------------- Main ----------------
async def main():
    tools = await build_all_mcp_tools()
    agent = create_agent(f"openai:{OPENAI_MODEL}", tools=tools)

    prompt = "Add 7 and 8 using the right tool. Then say 'done'."
    result = await agent.ainvoke({"messages": [("user", prompt)]})

    print("=== Conversation Transcript ===")
    print(format_conversation(result))

if __name__ == "__main__":
    asyncio.run(main())
