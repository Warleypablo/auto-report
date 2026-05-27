# TurboMax — Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Criar o TurboMax, assistente de chat com IA especializado em Meta Ads e Google Ads, alimentado com dados reais dos clientes Turbo Partners, acessível como página dedicada no painel gestor.

**Architecture:** Tool-use agent (Claude Sonnet) com endpoint `POST /api/gestor/chat`. Claude decide quais ferramentas chamar (banco de dados local + APIs ao vivo Meta/Google Ads) para compor respostas técnicas e contextuais. Frontend: página `/gestor/turbomax` com chat React ephemeral (sem persistência em banco).

**Tech Stack:** FastAPI, SQLAlchemy, Anthropic SDK (tool_use), Meta Ads Graph API, Google Ads API, Next.js App Router, TypeScript.

---

## Contexto

O painel já possui:
- `Snapshot` — métricas mensais por cliente (ROAS, faturamento, investimento, leads, CPA)
- `Insight` — sinais detectados + narrativa gerada por Claude Haiku
- Handlers de ETL (`campaign_facebook_gather.py`, `campaign_google_gather.py`) que acessam Meta e Google Ads usando credenciais da Planilha Central
- `fetch_clientes_tolerante()` — carrega objetos de cliente com `id_meta_ads`, `id_google_ads`, token Meta

O TurboMax reutiliza toda essa infraestrutura — não duplica lógica de API.

---

## Escopo desta spec (Peça 1)

Inclui:
- Endpoint de chat com tool-use
- 7 ferramentas (4 DB + 3 APIs externas)
- System prompt especialista
- UI de chat no painel gestor

Fora de escopo (Peças futuras):
- **Peça 2 — RAG de documentação:** coleta e indexação de docs Meta/Google para consulta semântica
- **Peça 3 — Alertas proativos:** TurboMax monitora e notifica gestores automaticamente

---

## Backend

### 1. Arquivo `web/backend/api/turbomax.py`

Router FastAPI com prefixo `/gestor/turbomax`.

#### Endpoint `POST /gestor/turbomax/chat`

**Auth:** `Depends(require_auth)` — qualquer gestor logado.

**Request body:**
```json
{
  "messages": [
    {"role": "user", "content": "Qual cliente tem melhor ROAS esse mês?"}
  ],
  "cliente_slug": "loja-fashion"
}
```
- `messages`: histórico completo da conversa (role `user` | `assistant`)
- `cliente_slug`: opcional — quando presente, o contexto do chat foca nesse cliente

**Response 200:**
```json
{
  "reply": "Com base nos dados de maio/2026, o cliente..."
}
```

**Comportamento:**
1. Valida que `messages` não está vazio e que o último é role `user`
2. Se `cliente_slug` fornecido, valida que pertence ao gestor autenticado (admin vê todos)
3. Monta contexto do usuário (nome, clientes atribuídos ou todos se admin)
4. Chama `_run_agent(messages, user_context, cliente_slug)` — loop de tool_use
5. Retorna `{"reply": <texto final>}`

**Loop de tool_use (`_run_agent`):**
```
1. Chama Claude Sonnet com system prompt + messages + tool definitions
2. Se resposta tem tool_use blocks:
   a. Executa cada tool chamada
   b. Adiciona tool_result ao histórico
   c. Chama Claude novamente (máx. 8 iterações)
3. Quando resposta é text, retorna
```

Máximo de 8 iterações de tool_use por resposta. Se exceder, retorna mensagem de erro ao usuário.

---

### 2. System Prompt

```
Você é TurboMax, especialista máximo em performance digital da Turbo Partners.
Domina Meta Ads e Google Ads no nível mais técnico. Responde sempre em português,
com dados reais quando disponíveis.

EXPERTISE META ADS:
- Estrutura de campanhas: CBO vs ABO, Campaign Budget Optimization
- Audiências: Lookalike (1–10%), Retargeting (visitantes, compradores), Broad, Interest
- Attribution windows: 1d_click, 7d_click, 1d_view — impacto direto no ROAS reportado
- Criativos: UGC, Carrossel, Reels, Image Ads — hooks, CTR benchmark > 2%
- Diagnóstico: fadiga de audiência (CTR caindo + CPM subindo), frequency > 3.5
- Meta Advantage+ Shopping Campaigns (ASC) vs campanhas manuais
- Pixel events: Purchase, AddToCart, InitiateCheckout — qualidade do sinal de conversão

EXPERTISE GOOGLE ADS:
- Estratégias de lance: Target ROAS (tROAS), Maximize Conversions, tCPA — quando usar cada
- Quality Score: componentes (CTR esperado, relevância, landing page) — impacto no CPC
- Performance Max: como funciona, quando usar, como interpretar asset groups
- Search Impression Share (SIS): perdido por orçamento vs rank
- Brand vs Non-brand: diferença de custo, ROAS inflado por brand
- Smart Bidding: período de aprendizado (2 semanas, 50 conversões)

CONTEXTO TURBO PARTNERS:
- Categorias de clientes: E-commerce (ROAS ≥ 3.0 é referência), Lead Com Site, Lead Sem Site (CPL como métrica principal)
- Métricas disponíveis: faturamento, investimento, ROAS, CPA, leads, vendas (mensais)
- Sinais automáticos: roas_queda (>20%), faturamento_queda (>25%), roas_brand_inflado, oportunidade_escala, cpl_vs_media

REGRAS:
- Sempre use ferramentas para buscar dados antes de responder sobre clientes específicos
- Quando comparar clientes ou campanhas, use tabelas markdown
- Nunca invente números — se não tiver dado, diga que não tem e sugira como obter
- Se o usuário perguntar sobre "bom" ou "ruim", compare com benchmarks da carteira
- Gestores veem apenas seus clientes atribuídos
```

---

### 3. Definições das 7 ferramentas

#### `listar_clientes`
Lista os clientes acessíveis ao gestor com métricas do mês mais recente.

**Input:** nenhum

**Output:**
```json
[
  {
    "slug": "loja-fashion",
    "nome": "Loja Fashion",
    "categoria": "E-commerce",
    "ativo": true,
    "ultimo_snapshot": {
      "mes": "2026-05",
      "roas": 3.8,
      "faturamento": 85000,
      "investimento": 22368,
      "leads": null,
      "vendas": 210
    }
  }
]
```

**Implementação:** query em `Snapshot` + `Cliente` para o mês mais recente de cada cliente, filtrado pelos clientes do gestor.

---

#### `get_metricas_cliente`
Métricas detalhadas de um cliente num mês específico.

**Input:**
```json
{"slug": "loja-fashion", "mes": "2026-05"}
```
`mes` opcional — usa o mês mais recente se omitido.

**Output:**
```json
{
  "cliente": "Loja Fashion",
  "categoria": "E-commerce",
  "mes": "2026-05",
  "roas": 3.8,
  "roas_var_pct": 12.5,
  "faturamento": 85000,
  "faturamento_var_pct": -3.2,
  "investimento": 22368,
  "cpa": null,
  "leads": null,
  "vendas": 210,
  "meta_ads": {"investimento": 15000, "roas": 4.1, "faturamento": 61500},
  "google_ads": {"investimento": 7368, "roas": 3.2, "faturamento": 23578}
}
```

**Implementação:** query em `Snapshot` com `metricas_detalhadas` JSONB para o breakdown canal.

---

#### `get_historico_cliente`
Últimos N meses de snapshots de um cliente.

**Input:**
```json
{"slug": "loja-fashion", "n_meses": 6}
```
`n_meses` padrão: 6, máximo: 24.

**Output:** lista ordenada de snapshots mensais (mesmo schema de `get_metricas_cliente`, sem breakdown por canal).

---

#### `get_sinais_cliente`
Sinais de inteligência e narrativa gerada para um cliente.

**Input:**
```json
{"slug": "loja-fashion", "mes": "2026-05"}
```

**Output:**
```json
{
  "cliente": "Loja Fashion",
  "mes": "2026-05",
  "sinais": [
    {
      "tipo": "roas_queda",
      "severidade": "alta",
      "titulo": "Queda de ROAS acima de 20%",
      "metrica_principal": "ROAS: 3.8× (era 4.3×)",
      "contexto": "Queda de 11.6% mês a mês"
    }
  ],
  "narrativa": "O cliente Loja Fashion apresentou queda..."
}
```

**Implementação:** query em `Insight` filtrado por cliente e mês.

---

#### `comparar_clientes`
Compara múltiplos clientes numa métrica para um período.

**Input:**
```json
{"slugs": ["loja-a", "loja-b", "loja-c"], "metrica": "roas", "mes": "2026-05"}
```
`slugs` opcional — compara todos os clientes do gestor se omitido.
`metrica`: `roas` | `faturamento` | `investimento` | `cpa` | `leads` | `vendas`

**Output:**
```json
{
  "mes": "2026-05",
  "metrica": "roas",
  "ranking": [
    {"slug": "loja-b", "nome": "Loja B", "valor": 5.1, "var_pct": 8.3},
    {"slug": "loja-a", "nome": "Loja A", "valor": 3.8, "var_pct": -2.1},
    {"slug": "loja-c", "nome": "Loja C", "valor": 2.9, "var_pct": 15.0}
  ],
  "media_carteira": 3.93
}
```

---

#### `buscar_campanhas_meta`
Campanhas ativas no Meta Ads para um cliente e período.

**Input:**
```json
{"slug": "loja-fashion", "date_start": "2026-05-01", "date_end": "2026-05-31"}
```

**Output:**
```json
{
  "cliente": "Loja Fashion",
  "periodo": {"inicio": "2026-05-01", "fim": "2026-05-31"},
  "campanhas": [
    {
      "id": "120208...",
      "nome": "Prospeccao_Lookalike_1pct",
      "status": "ACTIVE",
      "spend": 8500.00,
      "impressions": 320000,
      "clicks": 6400,
      "ctr": 2.0,
      "purchases": 95,
      "purchase_roas": 4.2,
      "cpm": 26.56
    }
  ]
}
```

**Implementação:** chama `coletar_metricas_anuncios_meta()` de `core/categorias/ecommerce/campaign_facebook_gather.py`, passando o objeto cliente obtido via `fetch_clientes_tolerante()`. Retorna erro amigável se `id_meta_ads` ausente.

---

#### `buscar_campanhas_google`
Campanhas no Google Ads para um cliente e período.

**Input:**
```json
{"slug": "loja-fashion", "date_start": "2026-05-01", "date_end": "2026-05-31"}
```

**Output:**
```json
{
  "cliente": "Loja Fashion",
  "periodo": {"inicio": "2026-05-01", "fim": "2026-05-31"},
  "campanhas": [
    {
      "id": "12345678",
      "nome": "Search_Brand",
      "status": "ENABLED",
      "spend": 2100.00,
      "impressions": 45000,
      "clicks": 3200,
      "conversions": 87,
      "conv_value": 12800.00,
      "roas": 6.1,
      "cpc": 0.66
    }
  ]
}
```

**Implementação:** chama o gather de campanhas de `core/categorias/ecommerce/campaign_google_gather.py`. Retorna erro amigável se `id_google_ads` ausente.

---

### 4. Autorização das ferramentas

Cada tool implementa a mesma guarda:

```python
def _check_acesso_cliente(slug: str, user: Usuario, session: Session) -> Cliente:
    """Retorna o cliente se o gestor tem acesso, levanta ValueError se não."""
    cliente = session.scalar(select(Cliente).where(Cliente.slug == slug))
    if cliente is None:
        raise ValueError(f"Cliente '{slug}' não encontrado")
    if not user.is_admin:
        atribuido = session.scalar(
            select(UsuarioCliente).where(
                UsuarioCliente.usuario_id == user.id,
                UsuarioCliente.cliente_id == cliente.id,
            )
        )
        if not atribuido:
            raise ValueError(f"Você não tem acesso ao cliente '{slug}'")
    return cliente
```

Erros de autorização são capturados e retornados como `tool_result` com `is_error=True`, para que Claude explique ao usuário sem quebrar o loop.

---

### 5. Registro do router

**Arquivo:** `web/backend/main.py`

```python
from api.turbomax import router as turbomax_router
app.include_router(turbomax_router, prefix="/api")
```

---

## Frontend

### 6. Página `/gestor/turbomax`

**Arquivo:** `web/frontend/app/gestor/turbomax/page.tsx`

Cliente React com `useState`:

```typescript
type Message = {
  role: "user" | "assistant";
  content: string;
};

const [messages, setMessages] = useState<Message[]>([WELCOME_MSG]);
const [input, setInput] = useState("");
const [loading, setLoading] = useState(false);
const [clienteSlug, setClienteSlug] = useState<string>("");
```

**Fluxo de envio:**
1. Usuário digita e pressiona Enviar ou Ctrl+Enter
2. Adiciona mensagem do usuário ao estado
3. `setLoading(true)` — exibe "TurboMax está consultando..."
4. `POST /api/gestor/turbomax/chat` com `{ messages, cliente_slug }`
5. Adiciona resposta ao estado
6. `setLoading(false)`

**Mensagem de boas-vindas (`WELCOME_MSG`):**
```
Olá! Sou o TurboMax, seu especialista em performance digital.
Posso te ajudar com:
• Análise de ROAS, CPL e métricas de qualquer cliente
• Diagnóstico de campanhas Meta Ads e Google Ads ao vivo
• Comparativos entre clientes da carteira
• Dicas técnicas de otimização

Por onde quer começar?
```

**Seletor de cliente:** `<select>` populado via `gestorApi.clientes()`. Opção padrão "Todos os clientes" (`clienteSlug = ""`).

**Renderização das mensagens:** markdown simples — detecta tabelas (linhas com `|`) e renderiza como `<table>`, negrito com `**`, listas com `-`. Sem dependência externa.

**Scroll automático:** `useEffect` com `ref` no final da lista de mensagens — scroll sempre que `messages` muda.

---

### 7. Sidebar (`_shell.tsx`)

Adiciona entrada ao array `NAV`:

```typescript
{ href: "/gestor/turbomax", label: "TurboMax", icon: "⚡" }
```

Posicionado após "Performance" e antes das entradas admin.

---

### 8. API client (`lib/api-gestor.ts`)

**Novos tipos:**
```typescript
export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatResponse = {
  reply: string;
};
```

**Novo método:**
```typescript
chat: (messages: ChatMessage[], clienteSlug?: string) =>
  apiCall<ChatResponse>("turbomax/chat", "POST", {
    messages,
    cliente_slug: clienteSlug ?? "",
  }),
```

---

## Tratamento de Erros

| Situação | Comportamento |
|---|---|
| `anthropic_api_key` não configurada | HTTP 503 com mensagem clara |
| Tool chamada para cliente sem acesso | `tool_result` com `is_error=True` — Claude explica ao usuário |
| Meta/Google sem credenciais para o cliente | Tool retorna `{"erro": "Cliente não tem id_meta_ads configurado"}` |
| Loop de tool_use excede 8 iterações | Retorna resposta parcial com aviso |
| Timeout de API externa (30s) | Tool retorna erro, Claude avisa e continua com dados do banco |

---

## Fora de Escopo

- **Streaming/SSE** — pode ser adicionado na Peça 2
- **Persistência de conversas** — cada sessão começa do zero
- **RAG de documentação** — Peça 2 (coleta e indexação de docs Meta/Google)
- **Alertas proativos** — Peça 3
- **TurboMax como Claude Code skill** — skill separado para uso interno da equipe
