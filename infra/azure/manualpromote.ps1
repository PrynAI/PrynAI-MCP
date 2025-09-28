$rg = "prynai-mcp-rg"
$app = "prynai-mcp"

# See revisions
az containerapp revision list -g $rg -n $app -o table

# Promote the new revision (replace <newrev> with the name you just saw)
az containerapp ingress traffic set -g $rg -n $app --revision-weight <newrev>=100

# (Optional) Deactivate the old one
az containerapp revision deactivate -g $rg -n $app --revision <oldrev>