# Design: Acesso Segmentado por Gestor

**Data:** 2026-06-04
**Status:** Aprovado

## Contexto

O painel `/gestor` hoje exige `is_admin = true` para a maioria das operações. Os gestores (responsáveis pelos clientes) não têm login próprio. A tabela `usuario_clientes` já existe e já é usada em `GET /gestor/clientes` para filtrar clientes por usuário — a infraestrutura está pronta, falta apenas popular os dados e ajustar o bypass para admins.

## Objetivo

Criar acessos individuais para os 11 gestores com clientes ativos, onde cada um só vê e opera sobre os próprios clientes. Admins continuam vendo tudo.

## Gestores (produção, 2026-06-04)

| Nome | Clientes ativos | Email gerado |
|---|---|---|
| José Neto | 14 | jose.neto@turbopartners.com.br |
| Gabriel Taufner | 13 | gabriel.taufner@turbopartners.com.br |
| Bruno da Silva | 13 | bruno.dasilva@turbopartners.com.br |
| Renan Fortunato | 13 | renan.fortunato@turbopartners.com.br |
| Thiago Martins | 12 | thiago.martins@turbopartners.com.br |
| Allan Gestor | 9 | allan.gestor@turbopartners.com.br |
| Victor Matsushita | 9 | victor.matsushita@turbopartners.com.br |
| Thiago Andrey | 9 | thiago.andrey@turbopartners.com.br |
| Rayan Coutinho | 2 | rayan.coutinho@turbopartners.com.br |
| Bruno Parreira | 2 | bruno.parreira@turbopartners.com.br |
| Gustavo S Pires | 1 | gustavo.spires@turbopartners.com.br |

**Senha inicial para todos:** `turbo@2026`

## Arquitetura

### Camada de dados (sem migration)

A tabela `usuario_clientes` já existe com a estrutura correta:

```
usuario_clientes
  usuario_id UUID FK → usuarios.id
  cliente_id UUID FK → clientes.id
```

O vínculo é criado cruzando `clientes.gestor` (string) com o nome do gestor em `gestores_cadastrados`. Clientes ativos (`ativo = true`) são vinculados; inativos são ignorados.

### Script de seed (`scripts/seed_gestores_acesso.py`)

Executa em produção (idempotente — não duplica registros):

1. Para cada gestor em `gestores_cadastrados`:
   - Deriva email: `primeiro.ultimo@turbopartners.com.br` (tokens intermediários ignorados; palavras conectivas como "da/de/do" removidas)
   - Cria `usuarios` com `is_admin = false, ativo = true, senha_hash = bcrypt(turbo@2026)` se não existir
   - Busca clientes ativos onde `clientes.gestor = gestor.nome`
   - Insere em `usuario_clientes` (ON CONFLICT DO NOTHING)

2. Imprime resumo: usuários criados, vínculos inseridos, gestores sem clientes ativos (pulados).

### Camada de API (admin bypass)

Nos endpoints que usam `require_auth` e filtram por `usuario_clientes`, adicionar:

```python
# Admins vêem todos os clientes; gestores vêem só os deles
if not user.is_admin:
    stmt = stmt.join(UsuarioCliente).where(UsuarioCliente.usuario_id == user.id)
```

Endpoints afetados (os que já têm `require_auth` + join `UsuarioCliente`):
- `GET /gestor/clientes` — listagem principal
- `GET /gestor/clientes/{slug}` — detalhe
- `GET /gestor/dashboard` — métricas
- `GET /gestor/reports` — histórico de jobs
- `POST /gestor/trigger` — disparar report
- `GET /gestor/criativos` — criativos
- `GET /gestor/turbomax` — turbomax

Endpoints com `require_admin` (configuração, sync, backfill) — **inalterados**, gestores não têm acesso.

### Frontend

Para usuários com `is_admin = false`:

- **Esconder:** dropdown "Gestor" no topo direito (não faz sentido filtrar por gestor se você é o gestor)
- **Esconder:** botão "Novo cliente"
- **Esconder:** aba "Administração" no menu lateral
- **Esconder:** seção de configurações de integrações (Google Ads ID, Meta ID, etc.)
- **Manter:** tudo mais — disparar report, ver criativos, TurboMax, dashboard, histórico

A API já retorna apenas os clientes do gestor; o frontend só precisa esconder os controles de admin.

## Fluxo de autenticação (sem mudança)

O token JWT já carrega `is_admin` no payload. O `require_auth` dependency já valida e retorna o `Usuario` completo. Nenhuma mudança no sistema de auth.

## Segurança

- Gestores não conseguem acessar clientes de outros gestores via API — o filtro é no SQL, não no frontend
- Endpoints destrutivos (delete, edit, sync) que hoje exigem `require_admin` continuam protegidos
- Novo cliente criado pelo admin **não** é automaticamente visível para gestores — precisa ser vinculado via `usuario_clientes` (por enquanto manualmente pelo admin; automação futura via webhook de sync)

## Testes

- `test_gestor_scoped_access.py`: gestor A não vê clientes de gestor B; admin vê todos; gestor sem clientes vê lista vazia
- Script de seed: idempotência (rodar 2x não duplica)
- Frontend: elementos de admin ausentes para não-admin (snapshot ou Playwright)
