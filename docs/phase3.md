## Phase 3 — OAuth 2.0 (Entra ID) + HTTPS

### Outcome
- `/mcp` protected by Microsoft Entra ID (OAuth 2.0, JWT).
- Optional HTTPS with local certs.
- Health endpoints stay open.

### What changed
- `auth/azure_oauth.py`: JWT validate via tenant JWKS. Enforce issuer, audience, optional scopes/roles.
- `auth/middleware.py`: Bearer auth on `/mcp`. Health paths bypassed.
- `app.py`: plugs middleware. Keeps Redis, CORS, health.
- `examples/smoke_oauth_cc.py`: client-credentials smoke using MSAL.

### Entra prerequisites
1. **Server app** (exposes API). Note its **Application (client) ID**.
2. **Client app** with **application permission** to the server app.
3. **Admin consent** granted for that permission.
4. Tenant ID available.

### Config (docker-compose)
```version: "3.9"
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"

  mcp:
    build:
      context: .
      dockerfile: infra/docker/Dockerfile
    environment:
      - REDIS_URL=${REDIS_URL}
      - PRYNAI_ENV=container
      - PRYNAI_BUILD=${GIT_COMMIT:-local}
      - AUTH_REQUIRED=true               # enforce OAuth
      - ENTRA_TENANT_ID=${ENTRA_TENANT_ID}
      - ENTRA_AUDIENCES=${SERVER_APP_ID} # or the server app's client-id
      # Optional scope/role checks:
      # - ENTRA_REQUIRED_SCOPES=Mcp.Invoke
      # - ENTRA_REQUIRED_APP_ROLES=Mcp.Invoke
      # HTTPS (optional)
      # Comment these lines to serve HTTP on 8000 instead
      - SSL_CERTFILE=/certs/127.0.0.1+1.pem
      - SSL_KEYFILE=/certs/127.0.0.1+1-key.pem
    volumes:
      - ./certs:/certs:ro
    ports:
      - "8443:8443"    # HTTPS
      - "8000:8000"
    depends_on:
      - redis

volumes:
  redisdata:
```
HTTPS options

HTTP local: simplest. Omit SSL_* vars. Use http://127.0.0.1:8000/mcp.

HTTPS local: generate certs with mkcert. Mount under /certs. Expose 8443.
To make Python trust mkcert:
setx SSL_CERT_FILE "C:\Users\riahl\AppData\Local\mkcert\rootCA.pem"
Then use https://127.0.0.1:8443/mcp.

Run
```
docker compose up -d --build
# health
curl -k https://127.0.0.1:8443/healthz   # if HTTPS
# or
curl http://127.0.0.1:8000/healthz
```

### Smoke test (client-credentials)

- Set env: Suggestion to create .env file and add configuration to the file or for that session set as below 
```
$env:ENTRA_TENANT_ID="<tenant-guid>"
$env:ENTRA_CLIENT_ID="<client-app-guid>"
$env:ENTRA_CLIENT_SECRET="<client-secret>"
$env:SERVER_APP_ID_URI="api://<server-app-guid>"
# pick URL matching your transport
$env:PRYNAI_MCP_URL="http://127.0.0.1:8000/mcp"
# or: $env:PRYNAI_MCP_URL="https://127.0.0.1:8443/mcp"

uv run python examples/smoke_oauth_cc.py ## check the right .env path for load_dotenv(dotenv_path="../.env",verbose=True) 
```
Expected
```
TOOLS: [...]
ADD RESULT: 15
STATUS: ok
```

VSCode agent testing:
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
            "url": "https://127.0.0.1:8443/mcp",
            "headers": {
                "Authorization": "Bearer ${input:token}"
            }
        }
    }
}
```

### Common 401 causes : 

- aud mismatch: set ENTRA_AUDIENCES to the server app GUID

- copes enforced for CC: client-credentials tokens lack scp. Do not set ENTRA_REQUIRED_SCOPES here.

- roles enforced but not granted: either grant the app role and admin consent, or clear ENTRA_REQUIRED_APP_ROLES.