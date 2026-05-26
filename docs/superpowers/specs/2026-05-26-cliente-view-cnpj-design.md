# Área do Cliente — Login por CNPJ + Dashboard de Performance

**Data:** 2026-05-26
**Status:** Aprovado para implementação
**Escopo:** Nova persona "cliente" com autenticação por CNPJ e dashboard próprio de performance, isolada da persona "gestor" existente.

---

## Problema

Hoje os relatórios de performance são consumidos via Google Slides gerados pelo gestor (a pedido) ou pela vitrine pública `/cases/[slug]` (opt-in, curado para prospects). Não há uma área onde o **cliente final** acesse seus próprios dados de performance de forma direta, contínua e auto-servida.

## Objetivo

Permitir que o cliente entre na aplicação com o próprio CNPJ e veja um dashboard com seus KPIs, evolução histórica e detalhamento de campanhas, herdando os mesmos dados que o gestor já enxerga — exceto informações operacionais internas.

---

## Decisões de design

- **Autenticação por CNPJ apenas.** Sem OTP, senha ou magic link. Aceita CNPJ formatado (`12.345.678/0001-90`) ou só dígitos (`12345678000190`); backend normaliza.
- **Vínculo CNPJ → cliente via ClickUp.** `staging.cup_clientes.cnpj` localiza o `task_id`; `clientes.cup_task_id` localiza o `Cliente`. Sem fuzzy de nome.
- **1 CNPJ = 1 cliente.** Se a query retornar mais de uma linha, login falha com mensagem para falar com o gestor. Não há tela de seleção de conta.
- **Persona isolada do gestor.** Rotas, dependências, cookie e payload JWT separados (`kind="cliente"`). Um token de gestor não autentica em `/cliente/*` e vice-versa.
- **Reaproveita services de métricas.** As funções que montam timeline e breakdown são extraídas de `api/gestor.py` para `services/metricas.py` e consumidas por ambas as personas. O controller do cliente omite campos internos (gestor, slides_url, dados ClickUp) no response.
- **Mesmo design system.** Sem identidade visual nova — paleta/tipografia/componentes já existentes.
- **Sem rate limiting na primeira versão.** CNPJ é informação pública; a postura é consistente com auth-only-CNPJ. Adicionar limit por IP na camada de infra se virar problema.

---

## Arquitetura

```
Frontend (Next.js)                   Backend (FastAPI)                  DB (Postgres)
─────────────────                    ──────────────────                  ─────────────
/cliente/login                ──┐                                       staging.cup_clientes
  form com 1 campo (CNPJ)       │                                         (cnpj já em prod)
                                │   POST  /cliente/auth/login           ──┐
                                ├──►   ↳ normaliza CNPJ                   │
                                │      ↳ SELECT cup_clientes              │
/cliente/dashboard              │         WHERE regexp_replace(cnpj,...)  │
  KPIs · evolução · top ads     │      ↳ JOIN clientes ON cup_task_id     │
                                │      ↳ valida ativo=true                │
                                │      ↳ emite cliente_token (JWT) ───────┘
                                │
                                │   GET   /cliente/me
                                │   GET   /cliente/metricas/timeline
                                │   GET   /cliente/metricas/breakdown    chama services
                                │   GET   /cliente/metricas/meses-disponiveis
                                └──    ↳ require_cliente (JWT kind=cliente)
```

Sem infra nova. A app existente ganha uma terceira persona.

---

## Modelo de dados

### Banco

- `staging.cup_clientes` — em produção já tem coluna `cnpj` (confirmado). Em dev/local não tem. Migration alembic idempotente:
  ```sql
  ALTER TABLE staging.cup_clientes ADD COLUMN IF NOT EXISTS cnpj text;
  ```
  No-op em prod, cria em local. Sem índice — tabela com ~1000 linhas.

- `clientes` — sem mudanças. O vínculo `cup_task_id → cup_clientes.task_id` já existe.

- `snapshots` — sem mudanças. O cliente lê os mesmos snapshots que o gestor, filtrados por `cliente_id`.

- Sem modelo SQLAlchemy novo — `Cliente` já existe; JWT carrega `cliente_id` direto, sem tabela de sessão.

### Sessão

- JWT payload: `{"sub": str(cliente_id), "kind": "cliente", "exp": now + JWT_EXPIRY_HOURS}`
- Cookie `cliente_token` (httpOnly, sameSite:lax). Duração do cookie alinhada com `JWT_EXPIRY_HOURS` (default 8h).
- Reaproveita `JWT_SECRET`, `JWT_ALGORITHM` e `JWT_EXPIRY_HOURS` do gestor — sem env vars novas.

### Normalização de CNPJ

Tanto o backend quanto o SQL normalizam removendo não-dígitos:
```sql
WHERE regexp_replace(cc.cnpj, '[^0-9]', '', 'g') = :cnpj_digits
```
```python
def normalize_cnpj(raw: str) -> str:
    return re.sub(r"\D", "", raw)
```

---

## Endpoints backend

Novo router `web/backend/api/cliente.py`, prefixo `/cliente/*`.

| Método | Rota | Auth | Body / Query | Retorno |
|---|---|---|---|---|
| `POST` | `/cliente/auth/login` | nenhuma | `{cnpj: str}` | `{token, cliente: ClientePublic}` ou 401 |
| `POST` | `/cliente/auth/logout` | `cliente_token` | — | `204` (frontend limpa cookie) |
| `GET`  | `/cliente/me` | `cliente_token` | — | `ClientePublic` |
| `GET`  | `/cliente/metricas/timeline` | `cliente_token` | `meses=12` | `{items: [TimelineItem, ...]}` |
| `GET`  | `/cliente/metricas/breakdown` | `cliente_token` | `mes=YYYY-MM` | `{meta_ads: [...], google_ads: [...]}` |
| `GET`  | `/cliente/metricas/meses-disponiveis` | `cliente_token` | — | `{meses: ["2026-04", ...]}` |

### Dependência `require_cliente`

Análoga a `require_auth` do gestor, mas com chave `kind == "cliente"` no payload. Garante que um `gestor_token` não passa em rotas `/cliente/*` (e vice-versa). Busca `Cliente` por `sub`, valida `ativo=true`, retorna a entidade.

### Schemas Pydantic (novos em `schemas/__init__.py`)

```python
class ClienteLoginRequest(BaseModel):
    cnpj: constr(min_length=11, max_length=20)

class ClientePublic(BaseModel):
    id: UUID
    slug: str
    nome: str
    categoria: Categoria
    logo_url: str | None
    setor: str | None

class ClienteLoginResponse(BaseModel):
    token: str
    cliente: ClientePublic
```

Campos **omitidos** propositalmente: `gestor`, `cup_task_id`, `painel_url`, `pasta_url`, `id_google_ads`, `id_meta_ads`, `id_ga4`.

### Reaproveitamento de código (refator pequeno)

Hoje as funções que montam timeline e breakdown vivem como helpers privados em `api/gestor.py`. Extrair para `services/metricas.py`:

```python
def build_timeline(cliente_id: UUID, meses: int, session: Session) -> list[TimelineItem]: ...
def build_breakdown(cliente_id: UUID, mes: str, session: Session) -> Breakdown: ...
def meses_disponiveis(cliente_id: UUID, session: Session) -> list[str]: ...
```

`api/gestor.py` e `api/cliente.py` passam a chamar daí. É uma melhoria "no caminho", não inflate de escopo.

---

## Frontend

### Estrutura de arquivos novos

```
web/frontend/
├─ app/cliente/
│  ├─ layout.tsx           # layout próprio (sem nav do gestor)
│  ├─ login/page.tsx       # form CNPJ
│  └─ dashboard/page.tsx   # dashboard completo
├─ app/api/cliente/
│  ├─ login/route.ts       # proxy: chama backend, seta cookie httpOnly
│  ├─ logout/route.ts      # limpa cookie cliente_token
│  ├─ me/route.ts          # proxy GET /cliente/me
│  ├─ metricas/timeline/route.ts
│  ├─ metricas/breakdown/route.ts
│  └─ metricas/meses-disponiveis/route.ts
├─ lib/api-cliente.ts      # client HTTP tipado (análogo a api-gestor.ts)
└─ middleware.ts           # adicionar matcher /cliente/dashboard/:path*
```

### Por que rotas Next API como proxy?

Mesmo padrão do gestor: o cookie httpOnly precisa ser setado pelo servidor Next. O browser não tem acesso ao token; chamadas via `lib/api-cliente.ts` passam pelas rotas Next, que leem o cookie e fazem `Authorization: Bearer ...` para o backend.

### `/cliente/login` — UI

- 1 input com label "CNPJ", máscara opcional `99.999.999/9999-99`
- Botão "Entrar"
- Mensagem de erro inline conforme tabela de erros abaixo
- Sem nav, layout minimalista com logo do produto no topo

### `/cliente/dashboard` — UI

**Header:**
- Esquerda: logo do cliente (se `logo_url`), nome, setor
- Direita: seletor de mês (apenas meses com snapshot), botão "Sair"

**Seções:**
1. **KPIs** do mês selecionado — grid 2/3/6 cols: Faturamento, Investimento, ROAS, CPA, Leads, Vendas. Variação % vs mês anterior.
2. **Evolução** — LineChart Recharts dos últimos 12 meses (Faturamento, Investimento, ROAS).
3. **Campanhas** — tabela top 5 Meta Ads + tabela top 5 Google Ads. Botão "Ver todos" expande.

**Não tem:** botão "Gerar report", card ClickUp, histórico de slides, links para outros clientes.

### Estado vazio

- Sem snapshot: card grande "Seus dados ainda estão sendo processados. Volte em breve."
- Sem dados de campanha no mês: mensagem inline "Sem detalhamento de campanhas neste mês."

### Design system

Reaproveita classes/CSS vars já em uso: `--paper`, `--ink`, `--forest`, `--rule-soft`, `font-display`, `eyebrow`, `font-mono-num`.

### Middleware

Adicionar matcher `/cliente/dashboard/:path*` — se cookie `cliente_token` ausente, redirect 302 para `/cliente/login`. Sem mexer no matcher existente do gestor.

---

## Fluxos

### Login (happy path)

```
1. Browser POST /api/cliente/login {cnpj: "12.345.678/0001-90"}
2. Next route: normaliza → "12345678000190", chama backend
3. Backend POST /cliente/auth/login:
     SELECT cc.task_id FROM staging.cup_clientes cc
     WHERE regexp_replace(cc.cnpj, '[^0-9]', '', 'g') = :cnpj
   → 1 task_id
     SELECT c FROM clientes c
     WHERE c.cup_task_id = :task_id AND c.ativo = true
   → 1 cliente
     emite JWT {sub: cliente.id, kind: "cliente", exp: now + JWT_EXPIRY_HOURS}
     retorna {token, cliente: ClientePublic}
4. Next route: seta cookie httpOnly cliente_token, retorna {ok: true}
5. Frontend: redirect → /cliente/dashboard
```

### Dashboard (happy path)

```
1. Browser GET /cliente/dashboard
2. middleware: cookie presente → 200
3. Página dispara em paralelo:
     GET /api/cliente/me
     GET /api/cliente/metricas/meses-disponiveis
     GET /api/cliente/metricas/timeline?meses=12
4. Cada Next route lê cookie, repassa Authorization Bearer ao backend
5. Backend valida JWT (kind==cliente), filtra snapshots por sub
6. Frontend renderiza KPIs + gráfico
7. Trocar mês → GET /api/cliente/metricas/breakdown?mes=YYYY-MM
```

### Casos de erro

| Caso | HTTP | Mensagem UI |
|---|---|---|
| CNPJ não encontrado em `cup_clientes` | 401 | "CNPJ não encontrado. Verifique o número ou entre em contato com seu gestor." |
| Múltiplos rows com mesmo CNPJ | 401 | "Múltiplas contas encontradas para este CNPJ. Fale com seu gestor." |
| CNPJ encontrado mas vínculo quebrado em `clientes` | 401 | "Conta não disponível no momento. Fale com seu gestor." |
| Cliente existe mas `ativo=false` | 401 | "Conta inativa. Fale com seu gestor." |
| Cliente sem snapshots | 200 (timeline vazia) | Empty state: "Seus dados ainda estão sendo processados." |
| Token expirado/inválido em rota protegida | 401 | middleware redireciona → `/cliente/login?expired=1` |
| Backend fora do ar | 500/network | "Erro de conexão. Tente novamente em alguns segundos." |

### Observabilidade

- Tentativas de login (sucesso + falha): log `INFO cliente_login cnpj_mask=12.***.678/****-** result=ok|not_found|inactive|multiple|broken_link` — **CNPJ mascarado** para não vazar em log estruturado.
- Acessos a métricas: já cobertos pelo log padrão do uvicorn/FastAPI.

---

## Testes

### Backend (`web/backend/tests/`)

**`test_cliente_auth.py`:**
- Login com CNPJ formatado → 200 + token
- Login com CNPJ só dígitos → 200 + token (normalização)
- CNPJ inexistente → 401 "CNPJ não encontrado"
- Cliente `ativo=false` → 401 "Conta inativa"
- Vínculo `cup_task_id` quebrado → 401
- 2 rows `cup_clientes` com mesmo CNPJ → 401 "Múltiplas contas"
- Response **não** contém `gestor`, `cup_task_id`, `painel_url`

**`test_cliente_require_dep.py`:**
- Token do gestor (`kind="gestor"`) em rota `/cliente/*` → 401
- Token expirado → 401
- Sem `Authorization` header → 401
- Cliente desativado pós-emissão → 401 (revalida no DB)

**`test_cliente_metricas.py`:**
- Cliente A logado → timeline retorna só snapshots de A
- Cliente A logado → breakdown só de A
- Cliente sem snapshots → `{items: []}`
- Response **não** contém `slides_url` nem `gestor`

**`test_services_metricas.py`** (após extração):
- `build_timeline`, `build_breakdown`, `meses_disponiveis` cobertos
- Testes existentes do gestor continuam passando depois da refatoração

### Frontend (Playwright, `web/frontend/tests/`)

**`cliente-login.spec.ts`:**
- `/cliente/login` renderiza
- CNPJ válido → redirect `/cliente/dashboard`
- CNPJ inválido → erro inline
- Acessar `/cliente/dashboard` sem cookie → redirect `/cliente/login`
- Cookie expirado → redirect com `?expired=1`

**`cliente-dashboard.spec.ts`:**
- Renderiza nome, logo (se houver) e KPIs
- Seletor de mês muda breakdown carregado
- Botão "Sair" limpa cookie e redireciona para `/cliente/login`
- Cliente sem snapshots → empty state visível

### Estratégia TDD

Para cada endpoint backend novo: teste primeiro (red), implementação (green), refatoração. Mesmo padrão para o middleware e os fluxos Playwright. A refatoração de extração para `services/metricas.py` parte dos testes existentes do gestor continuando verdes.

### Dados de teste

- Fixture `cliente_factory` cria `Cliente` + linha `staging.cup_clientes` com CNPJ + opcionalmente `Snapshot`s.
- Estender `scripts/seed_dev.py` para popular `cnpj` em `cup_clientes` ao criar mocks.

---

## Variáveis de ambiente

Nenhuma nova. Reaproveita `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRY_HOURS` já existentes.

---

## Não-objetivos (out of scope desta spec)

- **OTP / segundo fator** — pode ser adicionado depois sem refazer a arquitetura
- **Rate limiting de login** — fica na camada de infra se necessário
- **Múltiplas contas por CNPJ** — força operação a normalizar dados primeiro
- **Geração de slides pelo cliente** — função do gestor
- **Modo "compartilhar visualização" / link público** — fora desta entrega; `/cases/[slug]` já cobre o caso público

---

## Arquivos novos / modificados (resumo)

### Novos — backend
- `web/backend/api/cliente.py`
- `web/backend/services/metricas.py`
- `web/backend/alembic/versions/<rev>_add_cnpj_to_cup_clientes.py`
- `web/backend/tests/test_cliente_auth.py`
- `web/backend/tests/test_cliente_require_dep.py`
- `web/backend/tests/test_cliente_metricas.py`
- `web/backend/tests/test_services_metricas.py`

### Modificados — backend
- `web/backend/main.py` — registrar `cliente.router`
- `web/backend/api/gestor.py` — chamar funções de `services/metricas.py`
- `web/backend/schemas/__init__.py` — schemas `ClienteLoginRequest`, `ClienteLoginResponse`, `ClientePublic`
- `web/backend/scripts/seed_dev.py` — popular `cnpj` no seed

### Novos — frontend
- `web/frontend/app/cliente/layout.tsx`
- `web/frontend/app/cliente/login/page.tsx`
- `web/frontend/app/cliente/dashboard/page.tsx`
- `web/frontend/app/api/cliente/login/route.ts`
- `web/frontend/app/api/cliente/logout/route.ts`
- `web/frontend/app/api/cliente/me/route.ts`
- `web/frontend/app/api/cliente/metricas/timeline/route.ts`
- `web/frontend/app/api/cliente/metricas/breakdown/route.ts`
- `web/frontend/app/api/cliente/metricas/meses-disponiveis/route.ts`
- `web/frontend/lib/api-cliente.ts`
- `web/frontend/tests/cliente-login.spec.ts`
- `web/frontend/tests/cliente-dashboard.spec.ts`

### Modificados — frontend
- `web/frontend/middleware.ts` — matcher `/cliente/dashboard/:path*`
