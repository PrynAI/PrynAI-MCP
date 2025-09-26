# examples/smoke_oauth_ccACADeployment.py
import os, asyncio, msal
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def clear_proxy_env() -> None:
    for k in ("HTTP_PROXY","http_proxy","HTTPS_PROXY","https_proxy",
              "ALL_PROXY","all_proxy","NO_PROXY","no_proxy"):
        os.environ.pop(k, None)

# load .env once
load_dotenv(dotenv_path="../.env", verbose=True)
clear_proxy_env()  # bypass corporate proxy for this process

SERVER = os.getenv("PRYNAI_MCP_URL", "https://prynai-mcp.purplegrass-10f29d71.eastus.azurecontainerapps.io/mcp")
TENANT_ID = os.environ["ENTRA_TENANT_ID"]
CLIENT_ID = os.environ["ENTRA_CLIENT_ID"]
CLIENT_SECRET = os.environ["ENTRA_CLIENT_SECRET"]
SERVER_APP_URI = os.environ["SERVER_APP_ID_URI"]  # e.g., api://<server-app-guid>

def get_token() -> str:
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    res = app.acquire_token_for_client(scopes=[f"{SERVER_APP_URI}/.default"])
    if "access_token" not in res:
        raise RuntimeError(f"token error: {res}")
    return res["access_token"]

async def main():
    headers = {"Authorization": f"Bearer {get_token()}"}

    async with streamablehttp_client(SERVER, headers=headers, timeout=60.0) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            out = await session.call_tool("add", {"a": 7, "b": 8})
            print("ADD RESULT:", out.content[0].text)
            res = await session.read_resource("prynai://status")
            print("STATUS:", res.contents[0].text)

if __name__ == "__main__":
    asyncio.run(main())
