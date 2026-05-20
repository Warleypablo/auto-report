# Vitrine pública de cases

Sistema web que reaproveita os gathers do `auto-report-main` (Meta Ads, Google Ads, GA4, Painel) para mostrar publicamente cases de sucesso dos clientes — ROI, ROAS, faturamento e evolução temporal.

## Estrutura

```
web/
├── backend/      # FastAPI + SQLAlchemy + Alembic + ETL
└── frontend/     # Next.js 14 (App Router) + TypeScript + Tailwind + Recharts
```

Spec: `docs/superpowers/specs/2026-05-20-vitrine-cases-design.md`
Plano: `docs/superpowers/plans/2026-05-20-vitrine-cases.md`

## Rodando em dev

### Pré-requisitos

- Python 3.12+ (testado com 3.14)
- Node 20+ (testado com 25)
- Postgres 15+ rodando localmente

### Bootstrap inicial

```bash
# 1. Criar role e banco
psql -d postgres -c "CREATE USER vitrine WITH PASSWORD 'vitrine';"
psql -d postgres -c "CREATE DATABASE vitrine OWNER vitrine;"

# 2. Backend
cd web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_dev.py     # popula 2 clientes de exemplo

# 3. Frontend
cd ../frontend
npm install
```

### Rodar

```bash
# Terminal 1
cd web/backend && source .venv/bin/activate
uvicorn main:app --port 8765

# Terminal 2
cd web/frontend
NEXT_PUBLIC_API_URL=http://localhost:8765 npm run dev
# abrir http://localhost:3000
```

## Testes

```bash
# Backend
cd web/backend && source .venv/bin/activate && pytest

# Frontend (unit / lint / build)
cd web/frontend && npm run lint && npm run build

# E2E (Playwright) — requer backend e frontend (port 3010) rodando
cd web/frontend && npm run test:e2e
```

## ETL

O ETL diário lê a Planilha Central (filtrando clientes com `PUBLICAR_VITRINE = TRUE`), chama os gathers de `core/categorias/`, parseia a saída PT-BR e grava snapshots no Postgres.

### Manual

```bash
cd web/backend && source .venv/bin/activate
python -m etl.schedule
```

### Via HTTP (requer token)

```bash
curl -X POST http://localhost:8765/internal/etl/trigger \
  -H "x-etl-token: $ETL_TRIGGER_TOKEN"
```

### Configuração necessária para a primeira rodada real

1. **Credenciais Google** — `credentials/` e `config/settings.py` (mesmo padrão do auto-report).
2. **Planilha Central** — adicionar colunas:
   - `PUBLICAR_VITRINE` (TRUE/FALSE, controla opt-in)
   - `DESCRICAO_PUBLICA`
   - `LOGO_URL` (caminho relativo `/logos/<nome>.svg` ou URL externa)
   - `SETOR_PUBLICO`, `PORTE_PUBLICO`
3. **Logos** em `web/frontend/public/logos/<slug>.svg`.

## Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `DATABASE_URL` | `postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine` | Conexão Postgres |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Origens permitidas (JSON array) |
| `ETL_TRIGGER_TOKEN` | `dev-token-change-me` | Token p/ `/internal/etl/trigger` |
| `ETL_THREADS` | `10` | Pool de workers do ETL |
| `ETL_PERIODO_GRANULARIDADE` | `MENSAL` | `SEMANAL` ou `MENSAL` |
| `ETL_ALERT_WEBHOOK_URL` | — | Webhook Slack/etc para alertas (opcional) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL da API no frontend |

## Deploy em produção

### Backend (Cloud Run)

```bash
# Build e push da imagem (a partir da raiz do auto-report-main)
PROJECT=<seu-gcp-project>
REGION=us-central1

docker build -f web/backend/Dockerfile -t vitrine-backend:latest .
docker tag vitrine-backend:latest $REGION-docker.pkg.dev/$PROJECT/vitrine/backend:latest
docker push $REGION-docker.pkg.dev/$PROJECT/vitrine/backend:latest

# Migrations contra Postgres de prod (Cloud SQL, Supabase, Neon, etc.)
DATABASE_URL=<prod-url> alembic upgrade head

# Deploy
gcloud run deploy vitrine-backend \
  --image=$REGION-docker.pkg.dev/$PROJECT/vitrine/backend:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=<...>,CORS_ORIGINS=[\"https://cases.exemplo.com\"],ETL_TRIGGER_TOKEN=<token-seguro>"
```

### Frontend (Vercel)

1. Vercel → New Project → import deste repositório.
2. **Root directory**: `web/frontend`.
3. **Env var**: `NEXT_PUBLIC_API_URL=https://<url-do-backend>`.
4. Deploy automático a cada push em `main`.

### Cron diário (Cloud Scheduler)

```bash
gcloud scheduler jobs create http vitrine-etl-diario \
  --location=$REGION \
  --schedule="0 4 * * *" \
  --time-zone="America/Sao_Paulo" \
  --uri="https://<url-cloud-run>/internal/etl/trigger" \
  --http-method=POST \
  --headers="x-etl-token=<token>" \
  --attempt-deadline=30m
```

Disparar manualmente para validar:

```bash
gcloud scheduler jobs run vitrine-etl-diario --location=$REGION
```

## Operação

- **Ver status do ETL**: olhar logs do Cloud Run (`gcloud run logs read vitrine-backend`).
- **Re-rodar ETL manualmente**: chamar `/internal/etl/trigger` com header `x-etl-token`.
- **Remover cliente da vitrine**: setar `PUBLICAR_VITRINE = FALSE` na Planilha Central. Próximo ETL respeita; ISR do Vercel remove em até 1h.
- **Adicionar novo case**: setar `PUBLICAR_VITRINE = TRUE` + preencher `DESCRICAO_PUBLICA`/`LOGO_URL`. Próximo ETL popula.
