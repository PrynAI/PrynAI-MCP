# examples/use_core_langchain_agent.py
import os, asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from prynai.mcp_core import build_langchain_tools  # returns all MCP tools

async def main():
    tools = await build_langchain_tools()
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)

    agent = create_agent(llm, tools)

    inputs = {
        "messages": [HumanMessage(content="Add 7 and 8 using the available tools. Return only the number.")]
    }
    result = await agent.ainvoke(inputs)

    msgs = result.get("messages", [])
    last_ai = next((m for m in reversed(msgs) if isinstance(m, AIMessage)), None)
    print(last_ai.content if last_ai else result)

if __name__ == "__main__":
    asyncio.run(main())
