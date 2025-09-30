<#
Deploy PrynAI MCP to Azure Container Apps with Azure Cache for Redis.

Fixes:
- Registers providers.
- Always passes -g.
- Logs into ACR with explicit creds BEFORE docker push.
- No reliance on az CLI defaults.
#>

param(
    [string]$Prefix = "prynai",
    [string]$Location = "eastus",
    [string]$ResourceGroup = "$Prefix-mcp-rg",
    [string]$AcrName = ("{0}acr{1}" -f $Prefix, (Get-Random -Maximum 99999)),
    [string]$EnvName = "$Prefix-aca-env",
    [string]$AppName = "$Prefix-mcp",
    [string]$RedisName = "$Prefix-redis",
    [string]$ImageTag = "phase4",
    [int]$ContainerPort = 8000,
    [int]$MinReplicas = 1,
    [int]$MaxReplicas = 5
)

$ErrorActionPreference = "Stop"

function Ensure-ContainerAppExtension {
    $ext = az extension list --query "[?name=='containerapp'].name" -o tsv 2>$null
    if (-not $ext) { az extension add -n containerapp | Out-Null }
}

function Register-Providers {
    foreach ($ns in @(
            "Microsoft.ContainerRegistry",
            "Microsoft.Cache",
            "Microsoft.App",
            "Microsoft.OperationalInsights",
            "Microsoft.Network"
        )) {
        az provider register --namespace $ns | Out-Null
        $state = ""
        for ($i = 0; $i -lt 20; $i++) {
            $state = az provider show --namespace $ns --query registrationState -o tsv
            if ($state -eq "Registered") { break }
            Start-Sleep -Seconds 5
        }
        if ($state -ne "Registered") { throw "Provider $ns not registered. Current: $state" }
    }
}

function Load-DotEnv {
    param([string]$Path = ".\.env")
    if (Test-Path $Path) {
        foreach ($line in Get-Content $Path) {
            if ($line -match '^\s*#' -or $line -match '^\s*$') { continue }
            $kv = $line -split '=', 2
            if ($kv.Count -ne 2) { continue }
            Set-Item -Path ("Env:{0}" -f $kv[0].Trim()) -Value ($kv[1].Trim().Trim('"'))
        }
    }
}

Ensure-ContainerAppExtension
Load-DotEnv
Register-Providers

$ENTRA_TENANT_ID = $env:ENTRA_TENANT_ID
$SERVER_APP_ID = $env:SERVER_APP_ID
if (-not $ENTRA_TENANT_ID -or -not $SERVER_APP_ID) {
    throw "Missing ENTRA_TENANT_ID or SERVER_APP_ID. Set them in env or .env"
}

Write-Host "Subscription:" (az account show --query name -o tsv)
Write-Host "Resource Group:" $ResourceGroup
Write-Host "ACR:" $AcrName
Write-Host "ACA Env:" $EnvName
Write-Host "App:" $AppName
Write-Host "Redis:" $RedisName
Write-Host "Location:" $Location

# RG
az group create -n $ResourceGroup -l $Location | Out-Null

# ACR
az acr create -g $ResourceGroup -n $AcrName --sku Basic --admin-enabled true | Out-Null
$acrLoginServer = az acr show -n $AcrName -g $ResourceGroup --query loginServer -o tsv
if (-not $acrLoginServer) { throw "loginServer empty for ACR $AcrName" }
# Fetch creds and login BEFORE push
$acrUser = az acr credential show -n $AcrName -g $ResourceGroup --query username -o tsv
$acrPass = az acr credential show -n $AcrName -g $ResourceGroup --query "passwords[0].value" -o tsv
docker login $acrLoginServer -u $acrUser -p $acrPass | Out-Null

# Build + push
$img = "$acrLoginServer/prynai-mcp:$ImageTag"
docker build -f infra/docker/Dockerfile -t $img .
docker push $img

# Redis (TLS)
az redis create -n $RedisName -g $ResourceGroup --location $Location --sku Basic --vm-size c0 | Out-Null
$redisHost = az redis show -n $RedisName -g $ResourceGroup --query hostName -o tsv
$redisKey = az redis list-keys -n $RedisName -g $ResourceGroup --query primaryKey -o tsv
if (-not $redisHost -or -not $redisKey) { throw "Redis not provisioned" }
$REDIS_URL = "rediss://:${redisKey}@${redisHost}:6380/0"

# ACA env
az containerapp env create -g $ResourceGroup -n $EnvName -l $Location | Out-Null

# Audiences accept both forms
$audiences = "$SERVER_APP_ID,api://$SERVER_APP_ID"

# App
az containerapp create `
    -g $ResourceGroup `
    -n $AppName `
    --environment $EnvName `
    --image $img `
    --target-port $ContainerPort `
    --ingress external `
    --registry-server $acrLoginServer `
    --registry-username $acrUser `
    --registry-password $acrPass `
    --secrets redis-url="$REDIS_URL" entra-tenant="$ENTRA_TENANT_ID" entra-audiences="$audiences" `
    --env-vars REDIS_URL=secretref:redis-url AUTH_REQUIRED=true ENTRA_TENANT_ID=secretref:entra-tenant ENTRA_AUDIENCES=secretref:entra-audiences CORS_ALLOW_ORIGINS="*" `
    --cpu 0.5 --memory 1.0Gi `
    --min-replicas $MinReplicas --max-replicas $MaxReplicas | Out-Null

$fqdn = az containerapp show -g $ResourceGroup -n $AppName --query properties.configuration.ingress.fqdn -o tsv
if (-not $fqdn) { throw "Container App FQDN not returned" }

Write-Host ""
Write-Host "ACA FQDN: $fqdn"
Write-Host "MCP URL: https://$fqdn/mcp"
Write-Host ""
Write-Host "Health:"
Write-Host "  curl https://$fqdn/healthz"
Write-Host ""
Write-Host "Client-credentials smoke:"
Write-Host "  set PRYNAI_MCP_URL=https://$fqdn/mcp"