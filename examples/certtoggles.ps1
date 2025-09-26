# use local dev with mkcert
function Use-LocalMCP {
    $env:SSL_CERT_FILE = "$env:C:\Users\riahl\AppData\Local\mkcert\rootCA.pem"
    $env:PRYNAI_MCP_URL = "https://127.0.0.1:8443/mcp"
}

# use ACA
function Use-ACAMCP {
    Remove-Item Env:SSL_CERT_FILE, Env:REQUESTS_CA_BUNDLE -ErrorAction SilentlyContinue
    $env:PRYNAI_MCP_URL = "https://prynai-mcp.purplegrass-10f29d71.eastus.azurecontainerapps.io/mcp"
}
