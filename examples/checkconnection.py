
import httpx, json, os
u="https://prynai-mcp.purplegrass-10f29d71.eastus.azurecontainerapps.io/mcp"
h={"Accept":"text/event-stream","Content-Type":"application/json","Authorization":f"Bearer {os.environ['TOK']}"}
with httpx.Client(trust_env=False, timeout=20) as c:
    r=c.post(u, headers=h, content=json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{}}}))
    print(r.status_code, r.headers.get("content-type"))
