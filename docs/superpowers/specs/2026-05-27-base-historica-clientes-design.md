# Base Histórica de Clientes — Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Garantir que todos os clientes (ativos e inativos) tenham snapshots de métricas coletados para os meses disponíveis nas APIs, criando uma base histórica completa para geração de inteligência futura.

**Architecture:** Extensão do ETL existente com um endpoint de backfill que itera sobre um intervalo de meses e processa todos os clientes (incluindo inativos). Uma view admin no painel exibe a cobertura atual (matriz cliente × mês) e permite disparar o backfill via UI.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Next.js (admin UI), APIs Meta Ads e Google Ads (lookback até 36–37 meses).

---

## Contexto

O banco já possui:
- Tabela `clientes` com campo `ativo` (soft delete) — clientes inativos permanecem no banco com seus dados.
- Tabela `snapshots` com métricas por período, ligada a `clientes` via FK com cascade.
- ETL (`run_etl`) que coleta dados mês a mês, com upsert seguro (pode reprocessar).

O problema: o ETL histórico só rodou para clientes com `publicar_vitrine=True` no mês corrente. Clientes inativos e meses passados têm lacunas nos snapshots.

---

## Backend

### 1. Modificação em `run_etl`

**Arquivo:** `web/backend/etl/collect.py`

Adicionar parâmetro `incluir_inativos: bool = False`. Quando `True`, a query de clientes remove o filtro `ativo=True`:

```python
def run_etl(mes, slugs=None, incluir_privados=False, incluir_inativos=False, frequencia="MENSAL"):
    query = session.query(Cliente)
    if not incluir_inativos:
        query = query.filter(Cliente.ativo == True)
    if not incluir_privados:
        query = query.filter(Cliente.publicar_vitrine == True)
    if slugs:
        query = query.filter(Cliente.slug.in_(slugs))
    ...
```

### 2. Endpoint `POST /api/gestor/admin/etl/backfill`

**Arquivo:** `web/backend/api/gestor.py`

**Autenticação:** sessão de gestor com `is_admin=True` (mesmo padrão dos demais endpoints admin).

**Request body:**
```json
{
  "mes_inicio": "2023-01",
  "mes_fim":    "2025-12",
  "slug":       "cliente-x"
}
```
- `mes_inicio` e `mes_fim`: obrigatórios, formato `YYYY-MM`.
- `slug`: opcional. Se omitido, processa todos os clientes (ativos + inativos).

**Response 202:**
```json
{
  "job_id":   "uuid",
  "meses":    36,
  "clientes": 47
}
```

**Comportamento:**
1. Valida o intervalo (máximo 36 meses, `mes_fim >= mes_inicio`).
2. Gera um `job_id` (UUID) e registra estado inicial em um dict em memória (`_backfill_jobs`): `{ status, meses_total, meses_concluidos, erros }`.
3. Dispara `BackgroundTask` que itera `mes_inicio → mes_fim` mês a mês, chamando `run_etl(mes, slugs, incluir_privados=True, incluir_inativos=True)` para cada mês.
4. Ao final, atualiza estado para `done` (ou `error` se houve falhas).

O dict `_backfill_jobs` é mantido por processo. Suficiente para o caso de uso (backfills esporádicos, admin único). Não persiste entre reinicializações do servidor — aceitável.

### 3. Endpoint `GET /api/gestor/admin/etl/backfill/{job_id}`

Retorna o estado atual do job:
```json
{
  "job_id":           "uuid",
  "status":           "running",
  "meses_total":      36,
  "meses_concluidos": 12,
  "erros":            2,
  "pct":              33
}
```

### 4. Endpoint `GET /api/gestor/admin/cobertura`

Retorna a matriz de cobertura para a view admin:
```json
{
  "meses": ["2023-01", "2023-02", ...],
  "clientes": [
    {
      "id":     "uuid",
      "nome":   "Cliente X",
      "ativo":  false,
      "meses_com_snapshot": ["2024-01", "2024-02"]
    }
  ]
}
```
- Retorna os últimos 36 meses e todos os clientes (ativos + inativos).
- Requer `is_admin=True`.

---

## Frontend — Admin: `/gestor/admin/historico`

Nova aba acessível apenas para usuários `is_admin`. Adicionada ao link de administração existente na sidebar.

### Matriz de Cobertura

Tabela horizontal com:
- **Linhas:** clientes (nome + badge "inativo" se `ativo=False`)
- **Colunas:** últimos 24 meses (mais recente à esquerda)
- **Célula:** `●` verde se snapshot existe, `○` cinza se vazio

Filtros acima da tabela:
- Toggle "Mostrar inativos" (padrão: ligado)
- Filtro por categoria

### Ações de Backfill

- **Botão "Backfill completo":** dispara backfill para todos os clientes × todos os meses exibidos (últimos 36 meses). Confirma antes de executar.
- **Botão por linha:** ícone de refresh ao lado do nome do cliente, dispara backfill apenas para aquele cliente.
- **Barra de progresso global:** aparece após disparar o backfill, faz polling a cada 3s no `GET /api/gestor/admin/etl/backfill/{job_id}`, mostra `X de Y meses concluídos (Z%)`.

### API client (`lib/api-gestor.ts`)

Novos métodos:
```ts
backfillEtl: (params: { mes_inicio: string; mes_fim: string; slug?: string }) =>
  apiCall<{ job_id: string; meses: number; clientes: number }>("admin/etl/backfill", "POST", params),

getBackfillJob: (job_id: string) =>
  apiCall<{ status: string; meses_total: number; meses_concluidos: number; erros: number; pct: number }>(
    `admin/etl/backfill/${job_id}`
  ),

cobertura() =>
  apiCall<{ meses: string[]; clientes: CoberturaCliente[] }>("admin/cobertura")
```

---

## Fora de Escopo

- **Importação via CSV/planilha** — não necessário, o ETL busca direto das APIs.
- **Peça 2: Inteligência sobre a base histórica** — benchmarks, análise de churn, padrões de performance ao longo do tempo de contrato. Será spec separada após os dados estarem populados.
- **Alterações no modelo `Cliente`** — campos como `data_saida` não são necessários para este escopo.

---

## Limites das APIs

| API        | Lookback máximo |
|------------|-----------------|
| Meta Ads   | ~37 meses       |
| Google Ads | ~36 meses       |
| GA4        | Sem limite prático (dados históricos disponíveis) |

O backfill deve respeitar esses limites — meses além do lookback retornarão dados vazios e não gerarão snapshots.
