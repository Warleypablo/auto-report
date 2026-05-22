#!/usr/bin/env bash
# Startup script para o backend no Render.
# 1. Decodifica credenciais Google de variáveis de ambiente base64
# 2. Roda migrations Alembic
# 3. Inicia o uvicorn

set -euo pipefail

CRED_DIR="/tmp/autoreport-credentials"
mkdir -p "$CRED_DIR"

# ── Credenciais Google Service Account ──────────────────────────────────────
if [[ -n "${GOOGLE_SERVICE_ACCOUNT_JSON_B64:-}" ]]; then
  echo "$GOOGLE_SERVICE_ACCOUNT_JSON_B64" | base64 -d > "$CRED_DIR/service_account.json"
  export GOOGLE_SERVICE_ACCOUNT_FILE="$CRED_DIR/service_account.json"
  export SERVICE_ACCOUNT_FILE="$CRED_DIR/service_account.json"
  echo "[start] Credencial Google Service Account escrita em $CRED_DIR/service_account.json"
else
  echo "[start] AVISO: GOOGLE_SERVICE_ACCOUNT_JSON_B64 não definida"
fi

# ── Google Ads YAML ──────────────────────────────────────────────────────────
if [[ -n "${GOOGLE_ADS_YAML_B64:-}" ]]; then
  echo "$GOOGLE_ADS_YAML_B64" | base64 -d > "$CRED_DIR/google-ads.yaml"
  export GOOGLE_ADS_YAML_PATH="$CRED_DIR/google-ads.yaml"
  echo "[start] Google Ads YAML escrito em $CRED_DIR/google-ads.yaml"
else
  echo "[start] AVISO: GOOGLE_ADS_YAML_B64 não definida"
fi

# ── Migrations ───────────────────────────────────────────────────────────────
echo "[start] Rodando migrations Alembic..."
cd web/backend
alembic upgrade head
cd -

# ── Servidor ─────────────────────────────────────────────────────────────────
# PYTHONPATH inclui a raiz do repo E web/backend, então uvicorn encontra main:app
echo "[start] Iniciando uvicorn..."
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 2 \
  --log-level info \
  --app-dir web/backend
