#!/usr/bin/env bash
# Codifica as credenciais locais em base64 para colar no dashboard do Render.
# Uso: bash scripts/encode-credentials.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SA_FILE="$REPO_ROOT/credentials/conta_servico_google.json"
ADS_FILE="$REPO_ROOT/credentials/google-ads.yaml"

echo "============================================================"
echo "Cole esses valores nas env vars do serviço autoreport-backend no Render"
echo "============================================================"
echo ""

if [[ -f "$SA_FILE" ]]; then
  echo "GOOGLE_SERVICE_ACCOUNT_JSON_B64:"
  base64 -i "$SA_FILE"
  echo ""
else
  echo "AVISO: $SA_FILE não encontrado"
fi

if [[ -f "$ADS_FILE" ]]; then
  echo "GOOGLE_ADS_YAML_B64:"
  base64 -i "$ADS_FILE"
  echo ""
else
  echo "AVISO: $ADS_FILE não encontrado"
fi

echo "============================================================"
echo "Demais variáveis — copie do seu .env:"
echo ""
grep -v "^#\|^$\|SERVICE_ACCOUNT\|GOOGLE_ADS_YAML" "$REPO_ROOT/.env" 2>/dev/null || true
grep -v "^#\|^$\|DATABASE_URL" "$REPO_ROOT/web/backend/.env" 2>/dev/null || true
