# Phase 4 — Azure Container Apps (ACA) + Azure Cache for Redis

## Outcome

- PrynAI MCP runs on ACA with public HTTPS /mcp.
- Redis-backed sessions on Azure Cache for Redis.
- OAuth2 enforced by Entra ID. Health probes exposed.

### What we deployed

- ACA environment + app: public ingress on 443, app listens on 8000.

- Azure Cache for Redis: TLS on 6380. App reads REDIS_URL at startup.

- Health endpoints: /healthz returns {"status":"ok","redis":<bool>}; /livez always ok.
```
MCP surface: tools add, echo, long_task, summarize_via_client_llm, bump_counter; resources prynai://status, prynai://counter; prompt quick_summary.
```
### Prerequisites

- Azure CLI logged in and subscription selected.

- Docker Desktop running.

### Entra apps created:

- Server app exposing API (use its GUID and api://<GUID>).

- Client app with application permission to server API and admin consent granted.

### .env contains:

- ENTRA_TENANT_ID,
- ENTRA_CLIENT_ID,
- ENTRA_CLIENT_SECRET,
- SERVER_APP_ID_URI,
- SERVER_APP_ID.


### Deploy
Set required env and run the script:
```

.\infra\azure\deploy_aca.ps1

```

- The script builds and pushes the image to a new ACR, creates Redis, creates ACA Env and App, wires secrets and env, and prints the FQDN.

- Note the outputs:


```
ACA FQDN: <name>.<hash>.eastus.azurecontainerapps.io
MCP URL:  https://<fqdn>/mcp
```

### Health check
```
curl https://<fqdn>/healthz
# -> {"status":"ok","redis":true}

If redis:false, validate the secret format rediss://:<key>@<host>:6380/0 and restart the app.
```

### Smoke test (client-credentials, cloud)

Use the ACA smoke client. It fetches a token with MSAL and calls the remote MCP.

```
uv run python examples/smoke_oauth_ccACADeployment.py
# Expected:
# TOOLS: [...]
# ADD RESULT: 15
# STATUS: ok

```

### Token generator (optional) to inspect aud, iss, roles
```
uv run python examples/Generatetoken.py
```

### VS Code Agent Mode
Use a header token, not dynamic registration.

```
{
    "inputs": [
        {
            "id": "token",
            "type": "promptString",
            "title": "Paste an access token",
            "description": "Get a token via MSAL client credentials",
            "password": true
        }
    ],
    "servers": {
        "PrynAI MCP": {
            "type": "http",
            "url": "https://prynai-mcp.purplegrass-10f29d71.eastus.azurecontainerapps.io/mcp",
            "headers": {
                "Authorization": "Bearer ${input:token}"
            }
        }
    }
}

Generate a token with the helper, paste when prompted.
```

### Operate

Logs and scale:
```
az containerapp logs show -g <rg> -n prynai-mcp --follow
az containerapp update    -g <rg> -n prynai-mcp --min-replicas 2 --max-replicas 10
```

Roll a new image:
```
$acr = (az acr list -g <rg> --query "[0].loginServer" -o tsv)
docker build -f infra/docker/Dockerfile -t $acr/prynai-mcp:phase4 .
az acr login -n ($acr.Split('.')[0])
docker push $acr/prynai-mcp:phase4
az containerapp update -g <rg> -n prynai-mcp --image $acr/prynai-mcp:phase4

```

### Troubleshooting

- 401: Token audience mismatch. ACA expects ENTRA_AUDIENCES to include <server-app-guid> and api://<server-app-guid>. Token aud must match. Auth middleware returns structured 401 with WWW-Authenticate.

- Not Acceptable: Client must accept text/event-stream: You hit /mcp with curl. Use the MCP client or the smoke script. Health checks use /healthz.

- Redis stays false: Wrong REDIS_URL or missing hostname. Fix secret and restart.

- TLS errors from client: Remove local overrides like SSL_CERT_FILE or REQUESTS_CA_BUNDLE. The ACA cert is a public Microsoft chain.

- Proxy interference: The ACA smoke clears proxy envs before connecting. Use it as-is


### Source map (phase 4 relevant)

- Server surface and tools: src/prynai_mcp/server.py.

- App factory, health, CORS, auth wiring: src/prynai_mcp/app.py.

- Redis client: src/prynai_mcp/redis_client.py.

- OAuth config and middleware: src/prynai_mcp/config.py, src/prynai_mcp/auth/azure_oauth.py, src/prynai_mcp/auth/middleware.py.

- Cloud smoke: examples/smoke_oauth_ccACADeployment.py.

- This phase delivers a production entry on Azure with Redis-backed state, OAuth, and health visibility

