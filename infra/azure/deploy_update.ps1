# This script builds a new image and creates a new revision,
# but it only prints the promote command—it doesn’t shift traffic automatically. 
# Because we set revision mode to multiple, the stable URL keeps pointing to the old revision until we change the traffic.

param(
    [string]$Tag
)

# Resolve repo root
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path

# Safe tag (git short SHA or timestamp)
if (-not $Tag) {
    try { $Tag = (git -C $RepoRoot rev-parse --short HEAD 2>$null).Trim() } catch {}
    if (-not $Tag) { $Tag = Get-Date -Format "yyyyMMddHHmmss" }
}

# Azure resources (your existing names)
$rg = "prynai-mcp-rg"
$app = "prynai-mcp"
$acrName = "prynaiacr44058"
$acrLogin = "$acrName.azurecr.io"

# Derive repo path from the current image (keep repo/name the same)
$currentImage = az containerapp show -g $rg -n $app --query "properties.template.containers[0].image" -o tsv
$repoPath = if ($currentImage) {
    (($currentImage -replace "^$acrLogin/", "").Split(":")[0])
}
else { "prynai-mcp" }

# Build image refs (use ${} before ':')
$imageName = "${repoPath}:$Tag"
$fullImage = "${acrLogin}/${imageName}"

Write-Host "ACR remote build: $acrName  Image: $imageName"
az acr build `
    --registry $acrName `
    --image $imageName `
    --file "$RepoRoot/infra/docker/Dockerfile" `
    "$RepoRoot"

# Multiple revisions for safe rollout
az containerapp revision set-mode -g $rg -n $app --mode multiple | Out-Null

# Create new revision with the new image
az containerapp update -g $rg -n $app `
    --image $fullImage `
    --set-env-vars PRYNAI_BUILD=$Tag | Out-Null

# Show newest revision & FQDN
$newRev = az containerapp revision list -g $rg -n $app -o json | ConvertFrom-Json |
Sort-Object { $_.properties.createdTime } -Descending | Select-Object -First 1
$fqdn = az containerapp revision show -g $rg -n $app --revision $newRev.name --query "properties.fqdn" -o tsv

Write-Host "New revision:" $newRev.name
Write-Host "Preview FQDN: https://$fqdn"
Write-Host "`nSmoke-test the revision:"
Write-Host '$env:PRYNAI_MCP_URL = "https://' + $fqdn + '/mcp"; uv run python .\examples\smoke_oauth_ccACADeployment.py'
Write-Host "`nPromote when ready:"
Write-Host 'az containerapp ingress traffic set -g prynai-mcp-rg -n prynai-mcp --revision-weight ' + $newRev.name + '=100'


# Once this script is successfull test with new mcp url with new revision
#If it is successfull then point traffic to 100 to new revision

# az containerapp ingress traffic set -g prynai-mcp-rg -n prynai-mcp --revision-weight <newrev>=100