# Design: Painel de Gestores — Geração de Reports

**Data:** 2026-05-21
**Branch:** vitrine-cases
**Status:** Aprovado

---

## Problema

A geração de reports Google Slides depende de scripts rodados manualmente pelo administrador. Gestores não têm como disparar um report por conta própria, criando gargalo operacional.

---

## Solução

Estender a app existente (Next.js + FastAPI + Postgres) com um painel de gestores acessível em `/gestor/*`. Cada gestor faz login com email + senha, vê apenas os clientes atribuídos a ele, e dispara a geração de um report Google Slides com acompanhamento de status em tempo real.

---

## Arquitetura

Sem infra nova. O painel é adicionado à app existente:

- **Frontend:** novas páginas Next.js em `web/frontend/app/gestor/`
- **Backend:** novo router FastAPI em `web/backend/api/gestor.py` + `web/backend/api/auth.py`
- **Banco:** 3 novas tabelas no Postgres existente (sem alterar as existentes)
- **Core:** o router chama `core/categorias/<handler>` em thread de background — mesmo código do script manual

---

## Modelo de Dados

### `usuarios`
| campo | tipo | detalhe |
|---|---|---|
| id | UUID | PK |
| email | text UNIQUE | login |
| senha_hash | text | bcrypt |
| nome | text | exibição |
| is_admin | bool | pode criar usuários e atribuir clientes |
| ativo | bool | desativa sem deletar |
| created_at | timestamp | |

### `usuario_clientes`
| campo | tipo |
|---|---|
| usuario_id | FK → usuarios |
| cliente_id | FK → clientes |
| PK | (usuario_id, cliente_id) |

### `report_jobs`
| campo | tipo | detalhe |
|---|---|---|
| id | UUID | PK |
| usuario_id | FK → usuarios | quem disparou |
| cliente_id | FK → clientes | para qual cliente |
| mes | text | YYYY-MM |
| status | enum | `pending / running / done / error` |
| slides_url | text? | link do Google Slides quando pronto |
| erro | text? | mensagem se falhou |
| created_at | timestamp | |
| finished_at | timestamp? | |

---

## Auth

- **Mecanismo:** JWT assinado com secret no `.env`, expiração de 8h
- **Transporte:** cookie `httpOnly` (sem localStorage)
- **Níveis:** `gestor` (acesso aos próprios clientes) e `admin` (is_admin=true, gestão de usuários)
- **Primeiro admin:** criado via `web/backend/scripts/seed_admin.py` (roda uma vez no terminal)
- **Reset de senha:** admin redefine pelo painel — sem fluxo de email por ora

---

## Rotas do Backend (FastAPI)

Novo router montado sob prefixo `/gestor` e `/auth`, com middleware JWT próprio separado do `x-etl-token` atual.

### Auth
```
POST /auth/login          → { token, usuario }
POST /auth/logout         → invalida cookie
GET  /auth/me             → perfil do usuário logado
```

### Gestor
```
GET  /gestor/clientes              → clientes atribuídos ao gestor logado
POST /gestor/reports/trigger       → { slug, mes } → { job_id }
GET  /gestor/reports/{job_id}      → { status, slides_url, erro, created_at }
GET  /gestor/reports               → histórico de jobs do gestor logado
```

### Admin (requer is_admin=true)
```
GET    /gestor/admin/usuarios
POST   /gestor/admin/usuarios
DELETE /gestor/admin/usuarios/{id}            → desativa (ativo=false)
GET    /gestor/admin/usuarios/{id}/clientes
POST   /gestor/admin/usuarios/{id}/clientes   → body: [cliente_id, ...]
DELETE /gestor/admin/usuarios/{id}/clientes/{cliente_id}
```

---

## Páginas Frontend (Next.js)

| Rota | Acesso | Descrição |
|---|---|---|
| `/gestor/login` | público | Formulário email + senha |
| `/gestor` | gestor | Dashboard: lista de clientes atribuídos |
| `/gestor/[slug]` | gestor | Página do cliente: seletor de mês, botão gerar, status, histórico |
| `/gestor/admin/usuarios` | admin | Lista gestores, cria novos |
| `/gestor/admin/usuarios/[id]` | admin | Edita gestor, atribui/remove clientes |

Middleware Next.js em `web/frontend/middleware.ts` protege todas as rotas `/gestor/*` (exceto `/gestor/login`): verifica cookie JWT, redireciona para login se ausente ou expirado.

---

## Geração de Report — Fluxo

```
POST /gestor/reports/trigger
  1. Valida: gestor tem acesso ao cliente?
  2. Valida: não há job running para este cliente (evita duplicata)
  3. Cria ReportJob (status=pending)
  4. Retorna { job_id } imediatamente
  5. Thread de background:
       a. status = running
       b. Chama a função de geração de slides do core (ponto de entrada a mapear
          na implementação — equivalente ao que o script manual executa)
       c. Sucesso → status=done, slides_url=<url do Drive>
       d. Erro    → status=error, erro=<mensagem>
       e. finished_at = now()
```

**Polling do frontend:**
```
a cada 2s → GET /gestor/reports/{job_id}
  running → spinner "Gerando slides…"
  done    → link "→ Abrir slides"
  error   → mensagem de erro em vermelho
```

**Comportamentos de borda:**
- Gestor fecha a aba → job continua no servidor; ao voltar, histórico mostra o resultado
- Job em `running` há mais de 10 min → marcado como `error` no startup do servidor (verificação ao iniciar o uvicorn) e também antes de cada novo trigger do mesmo cliente
- O core continua atualizando `"GERADO ✅"` na Planilha Central (comportamento preservado)

---

## Arquivos Afetados

| Arquivo | Mudança |
|---|---|
| `web/backend/models/usuario.py` | Novo model `Usuario` |
| `web/backend/models/usuario_cliente.py` | Novo model `UsuarioCliente` |
| `web/backend/models/report_job.py` | Novo model `ReportJob` |
| `web/backend/models/__init__.py` | Exporta novos models |
| `web/backend/api/auth.py` | Endpoints de login/logout/me + JWT utils |
| `web/backend/api/gestor.py` | Endpoints de clientes, reports e admin |
| `web/backend/main.py` | Registra novos routers |
| `web/backend/alembic/versions/` | Nova migration |
| `web/backend/scripts/seed_admin.py` | Script de criação do primeiro admin |
| `web/frontend/app/gestor/login/page.tsx` | Página de login |
| `web/frontend/app/gestor/page.tsx` | Dashboard do gestor |
| `web/frontend/app/gestor/[slug]/page.tsx` | Página de geração de report |
| `web/frontend/app/gestor/admin/usuarios/page.tsx` | Admin: lista gestores |
| `web/frontend/app/gestor/admin/usuarios/[id]/page.tsx` | Admin: edita gestor |
| `web/frontend/middleware.ts` | Proteção JWT das rotas `/gestor/*` |
| `web/frontend/lib/api-gestor.ts` | Funções fetch para os endpoints de gestor |

---

## Fora do Escopo

- Reset de senha por email
- Notificações push ou email quando report ficar pronto
- Permissões granulares por período (gestor pode gerar qualquer mês)
- Multi-tenant (cada gestor em sub-domínio separado)
- Visualização do report dentro do próprio browser (sem Slides)
