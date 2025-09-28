# examples/use_core_list_tools.py
import asyncio
from prynai.mcp_core import list_mcp_tools

async def main():
    print(await list_mcp_tools())

if __name__ == "__main__":
    asyncio.run(main())