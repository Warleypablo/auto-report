# Central de Inteligência — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Painel proativo para gestores de performance analisarem sua carteira de clientes com sinais objetivos (regras) + narrativas explicativas geradas por IA (Claude API), computados em batch mensalmente.

**Architecture:** Signal Registry no backend detecta padrões nos snapshots existentes e gera uma lista de sinais estruturados por cliente. Um batch endpoint chama a Claude API com esses sinais e salva narrativa + sinais na tabela `insights`. O frontend `/gestor/inteligencia` exibe visão de portfólio agregada seguida de feed de alertas priorizados por severidade.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), Next.js 14 App Router `"use client"` (frontend), Anthropic Python SDK (geração de narrativa), PostgreSQL JSONB (sinais).

---

## Modelo de dados

### Tabela `insights`

```sql
CREATE TABLE insights (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cliente_id  UUID NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
  mes         VARCHAR(7) NOT NULL,   -- "2026-05"
  sinais      JSONB NOT NULL DEFAULT '[]',
  narrativa   TEXT,
  gerado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(cliente_id, mes)
);
CREATE INDEX ix_insights_mes ON insights(mes);
CREATE INDEX ix_insights_cliente ON insights(cliente_id);
```

### Estrutura de um sinal (JSONB)

```json
{
  "tipo": "roas_brand_inflado",
  "severidade": "atencao",
  "titulo": "ROAS inflado por campanha brand",
  "metrica_principal": "577,57×",
  "contexto": {
    "campanha": "[TP] - [Inst] - [09/10]",
    "investimento": 74.75,
    "faturamento": 43175.90,
    "roas_sem_brand": 32.80   // ROAS calculado excluindo campanhas com padrão brand no nome
  }
}
```

Severidades possíveis: `critico`, `atencao`, `oportunidade`.

---

## Backend

### Signal Registry — `services/inteligencia.py`

Cada sinal é uma função `detectar_<tipo>(cliente_id, mes, session) → dict | None`.
O registry é uma lista simples de funções. Para adicionar um sinal novo: escrever a função e adicioná-la à lista.

**Sinais implementados (v1):**

| Tipo | Severidade | Condição de disparo |
|---|---|---|
| `roas_brand_inflado` | `atencao` | Campanha com `[Inst]`, `[Brand]` ou `[Marc]` no nome com ROAS > 50× |
| `roas_queda` | `critico` | ROAS geral caiu >20% comparado ao mês anterior |
| `faturamento_queda` | `critico` | Faturamento caiu >25% comparado ao mês anterior |
| `oportunidade_escala` | `oportunidade` | ROAS > 5× com investimento < 50% da média de investimento dos outros clientes do mesmo gestor no mesmo mês |
| `roas_abaixo_limiar` | `critico` | ROAS geral < 1,5× (queimando dinheiro) |
| `investimento_parado` | `atencao` | Investimento zerado ou nulo no mês atual |
| `sem_dados` | `atencao` | Nenhum snapshot com dados para o mês |

### Batch endpoint

`POST /gestor/inteligencia/generate?mes=2026-05` (requer `is_admin=True`)

Fluxo por cliente:
1. Roda todos os detectores registrados → lista de sinais
2. Se zero sinais: skip (sem narrativa)
3. Monta prompt com sinais + métricas do mês
4. Chama `anthropic.messages.create(model="claude-haiku-4-5-20251001", ...)` → narrativa de 3–4 frases
5. Upsert em `insights(cliente_id, mes, sinais, narrativa)`

Resposta: `{ "mes": "2026-05", "gerados": 68, "sem_sinais": 3, "sem_dados": 4, "erros": 0 }`

### Read endpoint

`GET /gestor/inteligencia?mes=2026-05`

- Gestor autenticado: filtra `clientes.gestor == usuario.nome`, retorna insights + métricas de portfólio agregadas
- Admin: aceita `?gestor=<nome>` para filtrar; sem filtro retorna toda a carteira

Resposta:
```json
{
  "mes": "2026-05",
  "portfolio": {
    "faturamento": 2100000,
    "investimento": 187000,
    "roas_medio": 11.2,
    "n_critico": 3,
    "n_atencao": 5,
    "n_oportunidade": 2
  },
  "alertas": [
    {
      "cliente_slug": "oticas-paris",
      "cliente_nome": "Óticas Paris",
      "severidade": "critico",
      "sinais": [...],
      "narrativa": "..."
    }
  ]
}
```

Ordenação de `alertas`: `critico` → `atencao` → `oportunidade`.

---

## Frontend — `/gestor/inteligencia`

### Componentes

**`PortfolioStrip`** — faixa de KPIs no topo: faturamento total, investimento total, ROAS médio ponderado, badges de contagem por severidade (🔴 N crítico, 🟡 N atenção, 🟢 N oportunidade).

**`AlertaCard`** — card por cliente com:
- Badge de severidade colorido
- Nome do cliente
- Título do sinal principal
- Trecho da narrativa de IA (2–3 linhas, truncado)
- Métricas-chave do sinal (ROAS, investimento)
- Link "Ver cliente" → `/gestor/[slug]`

**Seletor de mês** — mesmo padrão de `performance/page.tsx`, lista últimos 12 meses.

**Banner "sem insights"** — exibido quando não há registro em `insights` para o mês selecionado: "Insights não gerados para este período. Acesse o admin para gerar."

### Acesso

- Gestor comum: vê apenas clientes onde `cliente.gestor == usuário.nome`
- Admin: vê toda a carteira + dropdown "Filtrar por gestor" (lista de gestores distintos)

### Geração (admin)

Botão "Gerar insights · [mês]" na página `/gestor/admin` existente — chama `POST /gestor/inteligencia/generate?mes=...` com feedback inline de progresso.

---

## Prompt para Claude (narrativa)

```
Você é um analista de performance de mídia paga. Analise os sinais abaixo para o cliente {nome} ({categoria}) no mês de {mes} e escreva um parágrafo objetivo de 3 a 4 frases explicando o que está acontecendo e o que o gestor deve observar. Seja direto, sem jargão excessivo.

Sinais detectados:
{sinais_json}

Métricas do mês:
- Faturamento: {faturamento}
- Investimento: {investimento}
- ROAS geral: {roas}
```

---

## Controle de acesso

- `generate` endpoint: `require_admin` (decorator já existente no projeto)
- `GET inteligencia`: gestor vê próprios clientes; admin + filtro via query param
- Nenhuma narrativa de IA é exposta em rotas públicas (vitrine)

---

## O que está fora do escopo (v1)

- Notificações push / e-mail quando um insight crítico é gerado
- Histórico de insights anteriores (navegação por meses já está contemplada)
- Recomendações automáticas de ajuste de orçamento
- Integração direta com Meta Ads / Google Ads API para dados em tempo real
