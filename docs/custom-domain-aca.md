# Goal
- Serve the MCP endpoint at https://mcp.prynai.com/mcp using Azure Container Apps (ACA) with Azure managed certificate.

## Prereqs

- ACA app is public with Ingress enabled.
- You control DNS for prynai.com at GoDaddy.
- App’s generated FQDN (example): prynai-mcp.<hash>.<region>.azurecontainerapps.io.

## 1) Get values from Azure
```
# app FQDN for CNAME
az containerapp show -g <rg> -n prynai-mcp -o tsv --query "properties.configuration.ingress.fqdn"

# domain verification code (asuid)
az containerapp show -g <rg> -n prynai-mcp -o tsv --query "properties.customDomainVerificationId"
```

- Azure uses a TXT record named asuid.<subdomain> for domain ownership checks.

## 2) Create DNS records at GoDaddy

### Create two records in the prynai.com zone:

### CNAME

- Host: mcp

- Points to: the ACA FQDN from step 1

- TTL: any standard value


### TXT

- Host: asuid.mcp
- Value: the verification code from step 1


### Note: Managed certs require the subdomain CNAME to point directly to the ACA-generated domain. Do not insert Cloudflare, Traffic Manager, or other intermediate CNAME targets. Issuance and renewals will fail if you do.

## 3) Bind domain and issue free managed cert

- Portal path: Container Apps → prynai-mcp → Networkiing → Custom domains → Add custom domain → Managed certificate → mcp.prynai.com → Validate → Add.

### CLI alternative:

```
# add hostname
az containerapp hostname add -g <rg> -n prynai-mcp --hostname mcp.prynai.com

# bind with managed certificate (validation via CNAME)
az containerapp hostname bind \
  -g <rg> -n prynai-mcp --environment <env-name> \
  --hostname mcp.prynai.com --validation-method CNAME

```

- The app must be publicly reachable for free certs

## 4) Verify

```
curl -I https://mcp.prynai.com/mcp

Output:

HTTP/1.1 405 Method Not Allowed
date: Thu, 02 Oct 2025 10:39:48 GMT
server: uvicorn
content-type: application/json
allow: GET, POST, DELETE
mcp-session-id: 5370f4ba76f644e3b4dcdb0b8a55833a
content-length: 92
```
## 5) Use in clients

- Set the MCP base URL to the custom domain:

### .env or environment
```
PRYNAI_MCP_URL=https://mcp.prynai.com/mcp
```
- Run existing smoke tests and agents under examples/ (LangGraph and LangChain) to list tools and call them.

## Notes

- Managed certs auto-renew while DNS keeps pointing directly to the ACA FQDN and ingress stays public. 
- For apex domains you would use an A record and TXT asuid at the root; for subdomains you use CNAME and TXT asuid.<subdomain>. This guide uses a subdomain