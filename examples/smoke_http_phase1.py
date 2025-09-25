# examples/smoke_http_phase1.py
import asyncio
import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SERVER = "http://127.0.0.1:8000/mcp"
COUNTER_URI = "prynai://counter"

# deterministic client-side sampler
async def sampling_handler(messages, params, context):
    # messages are SamplingMessage; each has .content.text
    try:
        first = next((m.content.text for m in messages if hasattr(m.content, "text")), "")
    except StopIteration:
        first = ""
    return "MOCK:" + first[:40]

async def main():
    async with streamablehttp_client(SERVER) as (read, write, _):
        # pass sampler if supported; fall back if not
        try:
            session_cm = ClientSession(read, write, sampling_handler=sampling_handler)
        except TypeError:
            session_cm = ClientSession(read, write)

        async with session_cm as session:
            await session.initialize()

            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

            res = await session.list_resources()
            print("RESOURCES:", [str(r.uri) for r in res.resources])

            prompts = await session.list_prompts()
            print("PROMPTS:", [p.name for p in prompts.prompts])

            # subscribe to counter updates (best-effort)
            try:
                await session.subscribe_resource(COUNTER_URI)
                subscribed = True
            except Exception:
                # older clients: raw call
                try:
                    await session._client.call("resources/subscribe", {"uri": COUNTER_URI})
                    subscribed = True
                except Exception:
                    subscribed = False

            # capture notifications if dispatcher exists
            updated = {"seen": False}
            async def handler(msg):
                try:
                    if msg.method == "notifications/resources/updated":
                        if COUNTER_URI in msg.params.get("uri", []):
                            updated["seen"] = True
                except Exception:
                    pass

            use_dispatch = hasattr(session, "_message_dispatch")
            async with anyio.create_task_group() as tg:
                if use_dispatch:
                    tg.start_soon(session._message_dispatch.add_handler, handler)

                # read initial value
                r = await session.read_resource(COUNTER_URI)
                print("COUNTER:", r.contents[0].text)

                # bump and wait for notification (or just verify value changed)
                await session.call_tool("bump_counter", {"step": 2})

                if subscribed and use_dispatch:
                    with anyio.move_on_after(3):
                        while not updated["seen"]:
                            await anyio.sleep(0.05)
                # read again for verification
                r2 = await session.read_resource(COUNTER_URI)
                print("COUNTER_AFTER:", r2.contents[0].text)

                # prompt render
                prompt = await session.get_prompt("quick_summary", {"title": "MCP Phase 1", "tone": "formal"})
                msg0 = prompt.messages[0]
                text0 = getattr(getattr(msg0, "content", None), "text", "")
                print("PROMPT TEXT:", text0[:60], "...")

                # sampling-backed tool (MOCK:... if sampler wired, else server fallback)
                out = await session.call_tool("summarize_via_client_llm", {"text": "hello world"})
                print("SAMPLING RESULT:", out.content[0].text)

                # long task
                await session.call_tool("long_task", {"steps": 3})
                tg.cancel_scope.cancel()

if __name__ == "__main__":
    asyncio.run(main())
