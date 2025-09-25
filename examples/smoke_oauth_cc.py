"""
Client-credentials smoke test.
Requires:
  - Server running with AUTH_REQUIRED=true
  - An Entra "server app" exposing an API (App ID URI)
  - A "client app" with application permission granted to the server app
  - Tenant admin consent done for that permission
"""

import os
from dotenv import load_dotenv
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import msal

load_dotenv(dotenv_path="../.env",verbose=True)
# Point at HTTPS if enabled; else use http://127.0.0.1:8000/mcp
SERVER = os.getenv("PRYNAI_MCP_URL", "https://127.0.0.1:8443/mcp")

TENANT_ID = os.getenv("ENTRA_TENANT_ID")
CLIENT_ID = os.getenv("ENTRA_CLIENT_ID")           # client app id
CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET")   # client app secret
# For client credentials, scope must be '<server-app-id-uri>/.default'
SERVER_APP_ID_URI = os.getenv("SERVER_APP_ID") # e.g., 'api://xxxxxxxx-xxxx-...'
SCOPE = f"{SERVER_APP_ID_URI}/.default"

def get_token() -> str:
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=authority, client_credential=CLIENT_SECRET
    )
    # Acquire token for app
    result = app.acquire_token_for_client(scopes=[SCOPE])
    if "access_token" not in result:
        raise RuntimeError(f"Token error: {result}")
    return result["access_token"]

async def main():
    token = get_token()
    # Pass bearer header to the SHTTP client
    headers = {"Authorization": f"Bearer {token}"}

    async with streamablehttp_client(SERVER, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

            # Call a tool
            out = await session.call_tool("add", {"a": 7, "b": 8})
            print("ADD RESULT:", out.content[0].text)

            # Read a resource secured behind auth
            res = await session.read_resource("prynai://status")
            print("STATUS:", res.contents[0].text)

if __name__ == "__main__":
    asyncio.run(main())