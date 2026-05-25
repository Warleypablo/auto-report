#!/usr/bin/env bash
# Startup script para o backend no Render.
# 1. Decodifica credenciais Google de variáveis de ambiente base64
# 2. Roda migrations Alembic
# 3. Inicia o uvicorn

set -uo pipefail  # sem -e para conseguir logar erros antes de abortar
trap 'echo "[start] ERRO na linha $LINENO (exit=$?)" >&2' ERR

echo "[start] === BOOT INICIO === $(date -u +%FT%TZ)"
echo "[start] python: $(python3 --version 2>&1)"
echo "[start] cwd: $(pwd)"
echo "[start] PYTHONPATH=${PYTHONPATH:-<unset>}"

# Sanity check: config/settings.py existe?
if [[ -f "config/settings.py" ]]; then
  echo "[start] OK config/settings.py existe ($(wc -l < config/settings.py) linhas)"
else
  echo "[start] ERRO config/settings.py NÃO existe — backend não vai funcionar"
  ls -la config/ 2>&1 || true
fi

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
if ! alembic upgrade head; then
  echo "[start] ERRO alembic falhou (exit=$?)" >&2
  exit 1
fi
cd -

# ── Sanity check de imports antes de subir uvicorn ───────────────────────────
echo "[start] Verificando que main:app importa..."
if ! python3 -c "import sys; sys.path.insert(0, 'web/backend'); import main; print('[start] main:app OK')" 2>&1; then
  echo "[start] ERRO import de main:app falhou — uvicorn não vai conseguir subir" >&2
  exit 1
fi

# ── Servidor ─────────────────────────────────────────────────────────────────
# PYTHONPATH inclui a raiz do repo E web/backend, então uvicorn encontra main:app
echo "[start] Iniciando uvicorn..."
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1 \
  --log-level info \
  --app-dir web/backend
