# examples/smoke_http.py
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SERVER = "http://127.0.0.1:8000/mcp"

async def main():
    async with streamablehttp_client(SERVER) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

            resources = await session.list_resources()
            print("RESOURCES:", [str(r.uri) for r in resources.resources])

            prompts = await session.list_prompts()
            print("PROMPTS:", [p.name for p in prompts.prompts])

            res = await session.read_resource(uri="prynai://status")
            print("STATUS:", res.contents[0].text)

            prompt = await session.get_prompt(
                name="quick_summary",
                arguments={"topic": "MCP Phase 0", "tone": "formal"},
            )
            msg0 = prompt.messages[0]
            print("PROMPT TEXT:", msg0.content.text[:60], "...")

            out = await session.call_tool(name="add", arguments={"a": 2, "b": 3})
            print("ADD RESULT:", out.content[0].text)

            out2 = await session.call_tool(name="long_task", arguments={"steps": 3})
            print("LONG_TASK:", out2.content[0].text)

            out3 = await session.call_tool(
                name="summarize_via_client_llm",
                arguments={"text": "PrynAI MCP is a local server."},
            )
            print("SAMPLING:", out3.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())
