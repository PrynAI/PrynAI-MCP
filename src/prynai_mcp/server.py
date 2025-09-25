from __future__ import annotations
import asyncio
from typing import Literal
from typing import Optional
from pydantic import AnyUrl
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import SamplingMessage, TextContent
from mcp.server.fastmcp.prompts import base
import logging, json, sys
from .redis_client import ensure_redis
import os, json
from .config import settings

DEPLOY = os.getenv("PRYNAI_ENV", "local")
BUILD  = os.getenv("PRYNAI_BUILD", "dev")

# --------------------------------------------------------------------
# PrynAI MCP — Phase 0 (local, no auth). Streamable HTTP transport.
# Run:  python -m prynai_mcp.server
# URL:  http://127.0.0.1:8000/mcp ,https://127.0.0.1:8003/mcp
# --------------------------------------------------------------------

mcp = FastMCP(name="PrynAI MCP")

# ----------------------- Tools --------------------------------------

# COUNTER: int = 0

async def _get_counter() -> int:
    r = await ensure_redis()
    val = await r.get("prynai:counter")
    return int(val) if val is not None else 0

async def _incr_counter(step: int) -> int:
    r = await ensure_redis()
    return int(await r.incrby("prynai:counter", step))

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@mcp.tool()
async def echo(message: str, ctx: Context[ServerSession, None]) -> str:
    """Echo text and emit an info log notification."""
    await ctx.info(f"echo called: {message}")
    return message


@mcp.tool()
async def long_task(steps: int = 3, ctx: Context[ServerSession, None] = None) -> str:
    """Demonstrate progress notifications."""
    await ctx.info(f"long_task starting: {steps} steps")
    for i in range(steps):
        await asyncio.sleep(0.2)
        # progress is a float 0..1; total optional
        await ctx.report_progress(progress=(i + 1) / steps, total=1.0, message=f"step {i + 1}/{steps}")
    await ctx.warning("long_task done")
    return "done"


@mcp.tool()
async def summarize_via_client_llm(text: str, ctx: Context[ServerSession, None]) -> str:
    """Ask the client LLM to summarize; fall back if unsupported."""
    try:
        res = await ctx.session.create_message(
            messages=[SamplingMessage(role="user", content=TextContent(type="text", text=f"Summarize: {text}"))],
            max_tokens=64,
            temperature=0.0,
        )
        return res.content.text if getattr(res, "content", None) and res.content.type == "text" else str(res)
    except Exception as e:
        await ctx.warning(f"sampling unavailable: {e}")
        return "sampling unavailable"
    

# update bump_counter to use Redis and notify
@mcp.tool()
async def bump_counter(step: int = 1, ctx: Context[ServerSession, None] = None) -> int:
    new_val = await _incr_counter(step)
    if ctx:
        await ctx.session.send_resource_updated("prynai://counter")
        await ctx.info(f"counter updated -> {new_val}")
    return new_val

# ----------------------- Resources ----------------------------------


@mcp.resource("prynai://status")
def status() -> str:
    """Simple status resource."""
    return "ok"


@mcp.resource("hello://{name}")
def hello_res(name: str) -> str:
    """Dynamic resource."""
    return f"Hello, {name}"


# update resource to be async and read from Redis
@mcp.resource("prynai://counter")
async def counter_value() -> str:
    return str(await _get_counter())

@mcp.resource("prynai://server-info")
def server_info() -> str:
    return json.dumps({
        "deployment": os.getenv("PRYNAI_ENV", "local"),
        "build": os.getenv("PRYNAI_BUILD", "dev"),
        "auth_required": settings.AUTH_REQUIRED,
        "issuer": settings.issuer,
        "audiences": (settings.ENTRA_AUDIENCES or "").split(",") if settings.ENTRA_AUDIENCES else [],
    })

# ----------------------- Prompts ------------------------------------


@mcp.prompt(name="quick_summary", title="Quick Summary")
def quick_summary(title: str = "Untitled", tone: str = "formal") -> list[base.Message]:
    """Reusable summary prompt."""
    style = "Write a concise, formal summary." if tone == "formal" else "Summarize informally."
    return [
        base.UserMessage(f"{style} Document title: {title}"),
    ]


# ----------------------- Structured logging ------------------------------------


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"level": record.levelname.lower(), "msg": record.getMessage(), "logger": record.name}
        return json.dumps(payload)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
root = logging.getLogger()
root.handlers = [handler]
root.setLevel(logging.INFO)


# ----------------------- Entrypoint ---------------------------------


def main() -> None:
    # Streamable HTTP server at /mcp on 127.0.0.1:8000
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
