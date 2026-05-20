# Design — Vitrine pública de cases (ROI, ROAS, melhores resultados)

**Data:** 2026-05-20
**Status:** Aprovado para implementação
**Projeto pai:** `auto-report-main`

---

## Contexto e objetivo

O projeto `auto-report-main` já automatiza a geração de relatórios em Google Slides para clientes da agência, com gathers conectados a Meta Ads, Google Ads, GA4 e a um painel interno. Os dados são organizados por categoria (E-commerce, Lead Com Site, Lead Sem Site) através de handlers em `core/categorias/`.

A proposta é **reaproveitar essa inteligência de coleta** para alimentar um novo sistema web: uma **vitrine pública de cases**, onde a agência mostra publicamente os melhores resultados (ROI, ROAS, faturamento gerado, crescimento) para atrair prospects e fortalecer a marca comercial.

## Decisões-chave (do brainstorming)

| Tema | Decisão |
|------|---------|
| Propósito | Vitrine pública (site comercial), não dashboard interno nem portal do cliente |
| Fonte de dados | Tempo real via APIs, reutilizando os gathers do auto-report |
| Privacidade | Identificado: nome + logo + números absolutos. Requer opt-in explícito por cliente |
| UX | Grid de cards na home + página detalhada por case |
| Stack | FastAPI (Python) + Next.js (React/TypeScript) |
| Arquitetura de dados | Snapshot diário em Postgres (visitante nunca toca APIs externas) |

## Arquitetura de alto nível

```
┌─────────────────────────────────────────────────────────────────┐
│                       Vitrine pública                            │
│                                                                  │
│   Visitante → Next.js (SSR/ISR) → FastAPI → Postgres             │
│                                       ↑                          │
└───────────────────────────────────────│──────────────────────────┘
                                        │ apenas leitura
                                        │
┌───────────────────────────────────────│──────────────────────────┐
│                       Ingestão (1×/dia)                          │
│                                       │                          │
│   Cron diário → Worker Python → grava no Postgres                │
│         │                                                        │
│         └─→ chama gathers existentes do auto-report:             │
│             facebook_metrics_gather, google_metrics_gather,      │
│             ga4_scraper, painel_scraper                          │
│         └─→ filtra clientes com flag PUBLICAR_VITRINE = TRUE     │
│             (nova coluna na Planilha Central)                    │
└──────────────────────────────────────────────────────────────────┘
```

**Princípios:**
- **Reuso total** dos handlers atuais via `core.categorias.get_handler(categoria).coletar_dados(...)`.
- **Postgres é a fonte de verdade da vitrine**: APIs externas (Meta/Google/GA4) nunca são chamadas em request de visitante.
- **Opt-in via Planilha Central** (mesma planilha do auto-report) com novas colunas.
- **Repositório**: novo diretório `web/` dentro do `auto-report-main`. O `core/` atual permanece inalterado.

## Estrutura de diretórios

```
auto-report-main/
├── core/                       # existente, inalterado
├── config/, credentials/, utils/, report_generator.py  # existentes
└── web/                        # NOVO
    ├── backend/
    │   ├── api/                # FastAPI routes
    │   │   ├── cases.py        # GET /cases, GET /cases/{slug}
    │   │   └── health.py
    │   ├── models/             # SQLAlchemy ORM
    │   ├── services/           # lógica de negócio
    │   │   ├── rankings.py     # top ROAS, top crescimento
    │   │   └── case_builder.py # DTO público a partir do snapshot
    │   ├── etl/
    │   │   ├── collect.py      # orquestra: planilha → handler → grava DB
    │   │   ├── transform.py    # parse de strings PT-BR → numéricos
    │   │   └── schedule.py     # entrypoint do cron
    │   ├── alembic/            # migrations
    │   └── main.py             # FastAPI app + CORS + lifespan
    ├── frontend/               # Next.js (App Router)
    │   ├── app/
    │   │   ├── page.tsx        # home: grid de cards
    │   │   ├── cases/[slug]/page.tsx  # detalhe por case
    │   │   └── layout.tsx
    │   ├── components/
    │   │   ├── CaseCard.tsx
    │   │   ├── CaseDetail.tsx
    │   │   ├── MetricGrid.tsx
    │   │   └── EvolutionChart.tsx
    │   ├── lib/api.ts          # fetch wrapper tipado
    │   └── public/logos/       # logos dos clientes
    ├── docker/
    │   ├── backend.Dockerfile
    │   └── frontend.Dockerfile
    ├── docker-compose.yml      # dev: backend + frontend + postgres
    └── README.md
```

## Modelo de dados

### Tabela `clientes`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID PK | |
| `slug` | TEXT UNIQUE | URL-friendly (`loja-fashion`) |
| `nome` | TEXT | Nome público do cliente |
| `logo_url` | TEXT | Caminho para `/public/logos/` ou CDN |
| `categoria` | ENUM | `E-commerce` \| `Lead Com Site` \| `Lead Sem Site` |
| `setor` | TEXT | Ex.: "Moda", "Saúde" |
| `porte` | TEXT | Ex.: "Médio", "Grande" |
| `descricao_publica` | TEXT | "Case story" curto |
| `publicar_vitrine` | BOOL | Opt-in. Espelha flag da Planilha Central |
| `destaque` | BOOL | Força aparecer no topo |
| `criado_em`, `atualizado_em` | TIMESTAMP | |

### Tabela `snapshots`

Uma linha por cliente × período coletado (histórico preservado).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID PK | |
| `cliente_id` | UUID FK | |
| `periodo_inicio`, `periodo_fim` | DATE | |
| `frequencia` | ENUM | `SEMANAL` \| `MENSAL` |
| `data_coleta` | TIMESTAMP | Quando o ETL rodou |
| `faturamento`, `investimento`, `roas`, `cpa`, `leads`, `vendas` | NUMERIC nullable | Métricas de destaque, denormalizadas para filtros/ordenação |
| `faturamento_var_pct`, `roas_var_pct`, ... | NUMERIC | Variações vs período anterior |
| `metricas_detalhadas` | JSONB | `{"meta": {...}, "google": {...}, "ga4": {...}, "painel": {...}}` |
| `raw_dados` | JSONB | Dump completo do `coletar_dados()` (audit/debug) |

**Unique constraint:** `(cliente_id, periodo_inicio, periodo_fim)` — garante idempotência do ETL.
**Índices:** `(cliente_id, periodo_fim DESC)`, `(periodo_fim DESC, roas DESC)`.

### View `cases_view`

JOIN entre `clientes` (onde `publicar_vitrine = TRUE`) e o snapshot mais recente de cada cliente. Usada pela listagem da home.

**Por que esta modelagem:**
- Colunas tipadas para métricas que aparecem em filtros/ordenação — indexáveis.
- JSONB para métricas específicas de categoria sem mudar schema toda vez.
- Histórico de snapshots permite gráfico de evolução na página detalhada.
- `raw_dados` JSONB é rede de segurança: se faltar algo nos campos tipados, o original está lá.

**Migrations:** Alembic.

## Backend — FastAPI

### Endpoints públicos

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/cases` | Lista paginada. Filtros: `categoria`, `setor`. Ordenação: `roas`, `faturamento`, `crescimento`. Retorna do `cases_view`. |
| `GET` | `/api/cases/{slug}` | Detalhe completo: snapshot atual + série histórica + métricas por fonte. |
| `GET` | `/api/rankings/{tipo}` | Top N por ROAS, faturamento, crescimento. |
| `GET` | `/api/health` | Health check. |

**Sem endpoints de escrita público.** Toda escrita acontece via ETL.

### Endpoint interno (autenticado por token)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/internal/etl/trigger` | Dispara o ETL manualmente (usado pelo cron e para debug). |

## ETL — fluxo de ingestão

### Frequência e disparo

- **Disparo do cron:** 1×/dia às 04:00 (`ETL_CRON_SCHEDULE`).
- **Granularidade do período coletado:** MENSAL (`ETL_PERIODO_GRANULARIDADE`). O ETL roda diariamente mas coleta o período mensal atual; conforme o mês avança, o snapshot do mês corrente é atualizado.

### Pseudo-código

```python
# web/backend/etl/collect.py

def run_etl(today: date, frequencia: str = "MENSAL"):
    with lock("etl:run"):                           # evita execução paralela
        clientes = core.leitura_central.listar(
            filter={"PUBLICAR_VITRINE": True}
        )

        periodo_ref  = core.periodo.periodo_referencia(today, frequencia)
        periodo_comp = core.periodo.periodo_referencia(periodo_ref.inicio, frequencia)

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            futures = {pool.submit(processar_cliente, c, periodo_ref, periodo_comp): c
                       for c in clientes}
            for f in as_completed(futures):
                f.result()  # log de sucesso/erro

def processar_cliente(cliente, periodo_ref, periodo_comp):
    try:
        handler = core.categorias.get_handler(cliente.categoria)
        dados_pt_br = handler.coletar_dados(cliente, periodo_ref, periodo_comp)
        # ↑ mesmo dict {"{{fat_face}}": "R$ 12.345,67", ...} do auto-report

        numerico = transform.parse_pt_br(dados_pt_br)
        # vira dict de Decimals/ints prontos pro DB

        upsert_snapshot(
            cliente_id=cliente.id,
            periodo=periodo_ref,
            metricas=numerico,
            raw=dados_pt_br,
        )
        log.info("snapshot_gravado", cliente=cliente.nome)
    except Exception as exc:
        log.exception("etl_falhou", cliente=cliente.nome, erro=str(exc))
        # batch continua, outros clientes não são afetados
```

### Notas técnicas

- **Idempotência:** `upsert_snapshot` usa o unique constraint para upsertar. Re-rodar o ETL no mesmo dia atualiza ao invés de duplicar.
- **Reuso:** ETL não conhece Meta/Google/GA4. Só conhece o contrato `handler.coletar_dados(...)`. Toda complexidade vive em `core/categorias/`.
- **Parser PT-BR:** os gathers atuais devolvem strings formatadas em PT-BR (`"R$ 12.345,67"`, `"8,5x"`, `"+12,3%"`). O `etl/transform.py` reverte para `Decimal`/`int`. Casos de borda: `""`, `"-"`, `None`, valores negativos. Esta lógica é o módulo mais importante de ter cobertura de teste.
- **Histórico:** snapshots não são apagados. Página detalhada usa últimos 6-12 meses para gráfico de evolução.
- **Logs:** padrão do auto-report (`utils.logger.StepLogger`) — sumário por cliente + agregado final.
- **Lock distribuído:** advisory lock do Postgres (`pg_try_advisory_lock`). Garante que se o cron disparar duplicado, só uma execução roda.
- **Custo computacional estimado:** 50 clientes × ~1 min × 10 threads ≈ 5 min/dia.

### Variáveis de ambiente novas

```
DATABASE_URL=postgresql+psycopg://...
ETL_THREADS=10
ETL_PERIODO_GRANULARIDADE=MENSAL   # granularidade do período coletado (SEMANAL|MENSAL)
ETL_CRON_SCHEDULE="0 4 * * *"      # quando o cron dispara o ETL
ETL_LOCK_BACKEND=postgres
ETL_TRIGGER_TOKEN=<token-para-endpoint-interno>
```

> Distinção importante: `ETL_PERIODO_GRANULARIDADE` define **qual período de dados o ETL coleta** (ex.: o mês inteiro). `ETL_CRON_SCHEDULE` define **com que frequência o ETL roda** (1×/dia, mesmo coletando dados mensais — o mês atual cresce e o snapshot atualiza diariamente).

## Frontend — Next.js

### Páginas

- **`/`** (home) — Hero da agência + grid de cards de cases. Cada card: logo, nome, categoria, métrica destaque (ex.: "ROAS 8,5x"), CTA "Ver case completo". Filtros: categoria, setor.
- **`/cases/[slug]`** (detalhe) — Header com logo/nome/contexto. Grid de métricas principais (faturamento, investimento, ROAS, CPA, vendas, leads). Gráfico de evolução (Recharts) com 6-12 meses. Detalhe por fonte (Meta/Google/GA4). Narrativa (`descricao_publica`).

### Tecnologias

- **App Router** + Server Components → SSR para SEO (crítico em vitrine pública).
- **ISR** (`revalidate: 3600`) → cada página em cache CDN por 1h, regenera em background.
- **TailwindCSS + shadcn/ui** para componentes base.
- **Recharts** para gráficos.
- **TypeScript** com tipos gerados do OpenAPI do FastAPI (geração automática via `openapi-typescript`).

## Privacidade e opt-in

### Como um cliente entra na vitrine

1. Time comercial obtém autorização escrita do cliente.
2. Atualiza Planilha Central:
   - `PUBLICAR_VITRINE = TRUE`
   - `DESCRICAO_PUBLICA = "..."`
   - `LOGO_URL = "..."`
   - `SETOR_PUBLICO`, `PORTE_PUBLICO` (opcionais)
3. Próximo ETL (no máximo 24h) detecta a flag e começa a popular snapshots.
4. Cliente aparece na vitrine no próximo build/ISR do frontend (até 1h depois).

### Revogação

- Cliente pede para sair → atualiza `PUBLICAR_VITRINE = FALSE` na planilha.
- Próximo ETL não atualiza mais o cliente.
- Backend filtra `WHERE publicar_vitrine = TRUE` em todos endpoints públicos. Próximo ISR do frontend remove o card.
- **Latência máxima de remoção:** ~1h (TTL do ISR). Para remoção imediata, possível endpoint `/internal/cache/purge`.

## Error handling

| Falha | Onde | Comportamento |
|-------|------|---------------|
| API externa (Meta/Google/GA4) | gathers do `core/` | retry/backoff em `utils/retry.py` já existente |
| Cliente individual falha no ETL | `processar_cliente` | log + skip; batch continua |
| ETL batch inteiro falha | `run_etl` | snapshot anterior continua sendo servido — vitrine não cai |
| Parse PT-BR → numérico falha | `transform.py` | métrica afetada vira NULL; restante grava |
| Métrica ausente | DB → API → frontend | seção daquela métrica não renderiza |
| Cliente revoga opt-in | flag na planilha | próximo ETL respeita, ISR remove em até 1h |
| API pública 500 | frontend Next.js | error boundary + fallback ("vitrine temporariamente indisponível") |

## Testes

- **Backend:** `pytest` + `httpx.AsyncClient` para endpoints. Fixtures com Postgres efêmero (`pytest-postgresql`).
- **ETL:** unit tests de `transform.parse_pt_br` cobrindo formatos `R$ X,XX`, `X,Xx`, `+X,X%`, `-`, `""`, `None`. Testes de `collect.py` com gathers mockados.
- **Frontend:** Vitest + React Testing Library para componentes (`CaseCard`, `MetricGrid`).
- **E2E:** Playwright apenas no caminho golden (home → click em case → detalhe).
- **CI:** GitHub Actions com 3 jobs paralelos (backend, frontend, e2e).

## Deploy e infraestrutura

### Dev local

`docker-compose up` levanta Postgres + backend + frontend.

### Produção (recomendação minimalista)

| Componente | Sugestão | Alternativas |
|------------|----------|--------------|
| Backend FastAPI | Cloud Run / Fly.io | VPS com Docker |
| Frontend Next.js | Vercel (CDN + ISR nativo) | Container próprio |
| Postgres | Managed (Cloud SQL / Supabase / Neon) | Não auto-hospedar em prod |
| Cron ETL | Cloud Scheduler → `/internal/etl/trigger` | k8s CronJob, crontab no VPS |

### Secrets

Via env vars. Mesmo padrão atual do auto-report (`core.cred_manager` para Google APIs).

## Observabilidade

- **Logs estruturados:** reuso do `utils.logger.StepLogger`. Em prod, agregar com Datadog / Sentry / Loki.
- **Alertas:** webhook Slack/email quando ETL falha em >N clientes ou falha total.
- **Métricas básicas:** quantos cases públicos, snapshots/dia, latência da API. Sem dashboard formal no MVP; adicionar quando virar dor.

## Segurança

- API: apenas endpoints de leitura públicos. Endpoint de escrita é interno + token.
- Flag `publicar_vitrine` é fonte única de verdade para exposição pública.
- Postgres acessível apenas pela VPC do backend.
- CORS restrito ao domínio da vitrine.
- Logos hospedados em `web/frontend/public/logos/`, versionados no repositório. Migração para CDN/S3 é next step (ver "Fora do MVP"). Não aceita upload público em nenhuma fase.

## Escopo e limites do MVP

**Dentro do MVP:**
- Grid de cards na home + página detalhada por case.
- ETL diário reutilizando gathers do auto-report.
- Opt-in via Planilha Central.
- Métricas de destaque (faturamento, investimento, ROAS, CPA, vendas, leads).
- Gráfico de evolução.

**Fora do MVP (próximas iterações):**
- Admin UI interna para revisar cases antes de publicar.
- Webhook de revogação imediata (sem esperar ISR).
- Filtros avançados (faixa de faturamento, período).
- Página de "rankings" dedicada.
- Audit log de quem mudou flags.
- Comparativos lado a lado entre cases.
- Migração de logos para CDN/S3.

## Próximos passos

1. **Plano de implementação** (próxima skill: `writing-plans`) — detalha tarefas, sequenciamento, marcos.
2. Validação técnica do parser PT-BR com amostras reais dos gathers.
3. Definição de identidade visual da vitrine (cores, tipografia, hero).
4. Provisionamento de Postgres em ambiente de dev e prod.
