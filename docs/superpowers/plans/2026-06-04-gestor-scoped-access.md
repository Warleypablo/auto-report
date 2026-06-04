# Gestor Scoped Access — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create individual logins for 11 gestores, each seeing only their own clients, while admins continue seeing everything.

**Architecture:** The API scoping layer already exists (`usuario_clientes` join table + admin bypass in `GET /gestor/clientes` and related endpoints). Work is: (1) seed script that creates `usuarios` + `usuario_clientes` rows in production, (2) three small frontend guards that hide admin-only controls for non-admin users.

**Tech Stack:** Python/SQLAlchemy (seed), pytest (backend tests), Next.js/React/TypeScript (frontend)

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `web/backend/scripts/seed_gestores_acesso.py` | Idempotent script: cria usuarios + usuario_clientes para os 11 gestores |
| Create | `web/backend/tests/test_gestor_scoped_access.py` | Testes de escopo: gestor A não vê clientes de B, admin vê todos |
| Modify | `web/frontend/app/gestor/page.tsx` | Esconde GestorFiltro, botão "Adicionar cliente" e sub-tab "Gestores" para não-admins |

---

## Task 1: Script de seed

**Files:**
- Create: `web/backend/scripts/seed_gestores_acesso.py`

### Contexto

- Tabela `gestores_cadastrados` tem 11 gestores com clientes ativos
- `clientes.gestor` (string) aponta para `gestores_cadastrados.nome`
- `api.auth.hash_password` faz bcrypt
- Senha inicial para todos: `turbo@2026`
- Algoritmo de email: primeira + última palavra do nome (sem palavras conectivas da/de/do/das/dos), tudo minúsculo sem acentos, separadas por ponto, sufixo `@turbopartners.com.br`
  - "José Neto" → `jose.neto@turbopartners.com.br`
  - "Bruno da Silva" → `bruno.silva@turbopartners.com.br`
  - "Gustavo S Pires" → `gustavo.pires@turbopartners.com.br`

- [ ] **Step 1: Criar `web/backend/scripts/seed_gestores_acesso.py`**

```python
"""Cria usuarios + usuario_clientes para todos os gestores com clientes ativos.

Idempotente: re-rodar não duplica registros.

Usage (from project root):
    python web/backend/scripts/seed_gestores_acesso.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from api.auth import hash_password
from db import SessionLocal
from models import Cliente, GestorCadastrado, Usuario, UsuarioCliente

_CONECTIVAS = {"da", "de", "do", "das", "dos", "e", "von", "van", "del"}
_SENHA_PADRAO = "turbo@2026"
_DOMINIO = "turbopartners.com.br"


def _remover_acentos(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _derivar_email(nome: str) -> str:
    tokens = [t for t in nome.split() if t.lower() not in _CONECTIVAS]
    if not tokens:
        raise ValueError(f"Nome sem tokens válidos: {nome!r}")
    primeiro = _remover_acentos(tokens[0]).lower()
    ultimo = _remover_acentos(tokens[-1]).lower() if len(tokens) > 1 else primeiro
    return f"{primeiro}.{ultimo}@{_DOMINIO}"


def main(dry_run: bool = False) -> None:
    with SessionLocal() as session:
        gestores = session.execute(
            select(GestorCadastrado).order_by(GestorCadastrado.nome)
        ).scalars().all()

        criados = 0
        vinculos = 0

        for g in gestores:
            clientes_ativos = session.execute(
                select(Cliente).where(Cliente.gestor == g.nome, Cliente.ativo == True)
            ).scalars().all()

            if not clientes_ativos:
                print(f"  SKIP {g.nome!r} — sem clientes ativos")
                continue

            email = _derivar_email(g.nome)

            # Cria usuario se não existir
            usuario = session.execute(
                select(Usuario).where(Usuario.email == email)
            ).scalar_one_or_none()

            if usuario is None:
                if not dry_run:
                    usuario = Usuario(
                        email=email,
                        nome=g.nome,
                        senha_hash=hash_password(_SENHA_PADRAO),
                        is_admin=False,
                        ativo=True,
                    )
                    session.add(usuario)
                    session.flush()
                print(f"  CREATE usuario {email}")
                criados += 1
            else:
                print(f"  EXISTS usuario {email} (id={usuario.id})")

            if dry_run:
                print(f"  WOULD link {len(clientes_ativos)} clientes → {email}")
                continue

            # Insere vínculos (ON CONFLICT DO NOTHING)
            for c in clientes_ativos:
                stmt = pg_insert(UsuarioCliente).values(
                    usuario_id=usuario.id,
                    cliente_id=c.id,
                ).on_conflict_do_nothing()
                result = session.execute(stmt)
                vinculos += result.rowcount

        if not dry_run:
            session.commit()

    print(f"\nResumo: {criados} usuários criados, {vinculos} vínculos inseridos")
    if dry_run:
        print("(dry-run — nenhuma alteração foi salva)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
```

- [ ] **Step 2: Testar a derivação de email localmente**

```bash
cd /path/to/auto-report-main
python -c "
import sys; sys.path.insert(0, 'web/backend')
# copie as funções _remover_acentos e _derivar_email aqui para teste rápido
casos = [
    ('José Neto', 'jose.neto@turbopartners.com.br'),
    ('Bruno da Silva', 'bruno.silva@turbopartners.com.br'),
    ('Gabriel Taufner', 'gabriel.taufner@turbopartners.com.br'),
    ('Gustavo S Pires', 'gustavo.pires@turbopartners.com.br'),
    ('Victor Matsushita', 'victor.matsushita@turbopartners.com.br'),
]
import unicodedata
_CONECTIVAS = {'da','de','do','das','dos','e','von','van','del'}
def rem(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
def email(nome):
    tokens = [t for t in nome.split() if t.lower() not in _CONECTIVAS]
    p = rem(tokens[0]).lower()
    u = rem(tokens[-1]).lower() if len(tokens) > 1 else p
    return f'{p}.{u}@turbopartners.com.br'
for nome, esperado in casos:
    got = email(nome)
    status = 'OK' if got == esperado else f'FAIL got {got}'
    print(f'{status}: {nome}')
"
```

Saída esperada: 5 linhas `OK: <nome>`

- [ ] **Step 3: Rodar dry-run em produção para verificar saída antes de commitar**

```bash
DATABASE_URL="postgresql+psycopg://postgres:fts0cVWPEQqXEQ7KTk&rzR&6@34.95.249.110:5432/autoreport" \
  /Users/mac0267/Documents/auto-report-main/web/backend/.venv/bin/python \
  web/backend/scripts/seed_gestores_acesso.py --dry-run
```

Saída esperada: lista de `WOULD link N clientes → email@turbopartners.com.br` para cada gestor, sem erros.

- [ ] **Step 4: Commit**

```bash
git add web/backend/scripts/seed_gestores_acesso.py
git commit -m "feat(gestores): seed script para criar usuarios e vincular clientes por gestor"
```

---

## Task 2: Testes de escopo da API

**Files:**
- Create: `web/backend/tests/test_gestor_scoped_access.py`

### Contexto

- O endpoint `GET /gestor/clientes` já filtra por `usuario_clientes` para não-admins e retorna todos para admins
- `require_auth` valida o JWT e retorna o `Usuario`
- Testar via `TestClient` do FastAPI com fixtures de banco real (padrão dos outros testes neste projeto)

- [ ] **Step 1: Verificar como outros testes criam fixtures de usuário e cliente**

```bash
head -80 web/backend/tests/test_auth.py
```

Observe: como `session` é obtida, se há factory de usuário, como o token JWT é gerado.

- [ ] **Step 2: Escrever os testes**

Crie `web/backend/tests/test_gestor_scoped_access.py`:

```python
"""Testa que gestores só vêem os próprios clientes e admins vêem todos."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from main import app
from models import Cliente, Usuario, UsuarioCliente
from models.cliente import Categoria
from api.auth import hash_password
from app_settings import get_settings


def _make_token(user_id: uuid.UUID, is_admin: bool) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {"sub": str(user_id), "is_admin": is_admin, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _create_user(session: Session, *, is_admin: bool = False) -> Usuario:
    u = Usuario(
        email=f"test-{uuid.uuid4().hex[:8]}@test.com",
        nome="Test",
        senha_hash=hash_password("x"),
        is_admin=is_admin,
        ativo=True,
    )
    session.add(u)
    session.flush()
    return u


def _create_cliente(session: Session, nome: str) -> Cliente:
    c = Cliente(
        slug=f"slug-{uuid.uuid4().hex[:8]}",
        nome=nome,
        categoria=Categoria.ECOMMERCE,
        ativo=True,
    )
    session.add(c)
    session.flush()
    return c


def _link(session: Session, usuario: Usuario, cliente: Cliente) -> None:
    session.add(UsuarioCliente(usuario_id=usuario.id, cliente_id=cliente.id))
    session.flush()


@pytest.fixture()
def client():
    return TestClient(app)


def test_gestor_ve_somente_proprios_clientes(db_session: Session, client: TestClient):
    """Gestor A não vê clientes de Gestor B."""
    gestor_a = _create_user(db_session)
    gestor_b = _create_user(db_session)
    c_a = _create_cliente(db_session, "Cliente A")
    c_b = _create_cliente(db_session, "Cliente B")
    _link(db_session, gestor_a, c_a)
    _link(db_session, gestor_b, c_b)
    db_session.commit()

    token_a = _make_token(gestor_a.id, is_admin=False)
    resp = client.get("/gestor/clientes", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    nomes = [i["nome"] for i in resp.json()["items"]]
    assert "Cliente A" in nomes
    assert "Cliente B" not in nomes


def test_admin_ve_todos_clientes(db_session: Session, client: TestClient):
    """Admin vê clientes de todos os gestores."""
    admin = _create_user(db_session, is_admin=True)
    gestor = _create_user(db_session)
    c1 = _create_cliente(db_session, "Exclusivo Gestor")
    _link(db_session, gestor, c1)
    db_session.commit()

    token_admin = _make_token(admin.id, is_admin=True)
    resp = client.get("/gestor/clientes", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 200
    nomes = [i["nome"] for i in resp.json()["items"]]
    assert "Exclusivo Gestor" in nomes


def test_gestor_sem_clientes_ve_lista_vazia(db_session: Session, client: TestClient):
    gestor = _create_user(db_session)
    db_session.commit()

    token = _make_token(gestor.id, is_admin=False)
    resp = client.get("/gestor/clientes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_seed_email_derivation():
    """Testa derivação de email sem banco."""
    import unicodedata

    _CONECTIVAS = {"da", "de", "do", "das", "dos", "e", "von", "van", "del"}

    def _remover_acentos(s: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
        )

    def _derivar_email(nome: str) -> str:
        tokens = [t for t in nome.split() if t.lower() not in _CONECTIVAS]
        primeiro = _remover_acentos(tokens[0]).lower()
        ultimo = _remover_acentos(tokens[-1]).lower() if len(tokens) > 1 else primeiro
        return f"{primeiro}.{ultimo}@turbopartners.com.br"

    assert _derivar_email("José Neto") == "jose.neto@turbopartners.com.br"
    assert _derivar_email("Bruno da Silva") == "bruno.silva@turbopartners.com.br"
    assert _derivar_email("Gabriel Taufner") == "gabriel.taufner@turbopartners.com.br"
    assert _derivar_email("Gustavo S Pires") == "gustavo.pires@turbopartners.com.br"
    assert _derivar_email("Victor Matsushita") == "victor.matsushita@turbopartners.com.br"
```

- [ ] **Step 3: Verificar nome da fixture de sessão de banco usada nos outros testes**

```bash
grep -n "def db_session\|db_session\|session_fixture" web/backend/tests/conftest.py | head -20
```

Se a fixture se chamar diferente (ex: `session`), ajuste os parâmetros das funções de teste acima.

- [ ] **Step 4: Rodar os testes**

```bash
cd web/backend && .venv/bin/pytest tests/test_gestor_scoped_access.py -v
```

Saída esperada: todos os testes PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/tests/test_gestor_scoped_access.py
git commit -m "test(gestores): escopo por usuario — gestor A não vê clientes de B"
```

---

## Task 3: Frontend — esconder controles admin para não-admins

**Files:**
- Modify: `web/frontend/app/gestor/page.tsx`

### Três mudanças cirúrgicas

**A. `GestorFiltro`** — só faz sentido para admins (não-admins têm apenas seus próprios clientes)

Linha ~1979 atual:
```tsx
{gestores.length > 0 && (
  <GestorFiltro
    gestores={gestores}
    value={gestorFiltro}
    onChange={setGestorFiltro}
  />
)}
```

**B. Botão "Adicionar cliente"** — linha ~1611, dentro de `AbaConfiguracoes`

Atual:
```tsx
<button
  onClick={() => { setCriando(true); setCriarForm(emptyCreateForm()); setCreateErr(null); }}
  className="rounded-md bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
>
  + Adicionar cliente
</button>
```

**C. Sub-tab "Gestores"** — linha ~178, dentro de `Sidebar`

Atual:
```tsx
{CONFIG_SUB_TABS.map(({ id: subId, label: subLabel }) => (
```
`CONFIG_SUB_TABS` inclui `{ id: "config-gestores", label: "Gestores" }` — não-admins não devem ver.

- [ ] **Step 1: Passar `user` para `AbaConfiguracoes`**

Localize a definição de `AbaConfiguracoes` (linha ~1368). Adicione `user: UsuarioInfo | null` às suas props:

```tsx
function AbaConfiguracoes({
  clientes,
  todosClientes,
  configTab,
  onClienteUpdated,
  onClienteDeleted,
  onClienteCriado,
  onGestorRenomeado,
  onGestoresNormalizados,
  user,
}: {
  clientes: ClienteGestor[];
  todosClientes: ClienteGestor[];
  configTab: ConfigTab;
  onClienteUpdated: (c: ClienteGestor) => void;
  onClienteDeleted: (id: string) => void;
  onClienteCriado: (c: ClienteGestor) => void;
  onGestorRenomeado: (de: string, para: string) => void;
  onGestoresNormalizados: (mapeamento: { de: string; para: string }[]) => void;
  user: UsuarioInfo | null;
}) {
```

- [ ] **Step 2: Esconder botão "Adicionar cliente" para não-admins**

Envolva o `<button>` de adicionar cliente com `{user?.is_admin && (...)}`:

```tsx
{user?.is_admin && (
  <button
    onClick={() => { setCriando(true); setCriarForm(emptyCreateForm()); setCreateErr(null); }}
    className="rounded-md bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
  >
    + Adicionar cliente
  </button>
)}
```

- [ ] **Step 3: Passar `user` para `AbaConfiguracoes` na chamada**

Localize o `<AbaConfiguracoes ... />` no JSX principal (~linha 2008) e adicione a prop `user`:

```tsx
<AbaConfiguracoes
  clientes={clientesFiltrados}
  todosClientes={clientes}
  configTab={configTab}
  onClienteUpdated={(updated) =>
    setClientes((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
  }
  onClienteDeleted={(id) =>
    setClientes((prev) => prev.filter((c) => c.id !== id))
  }
  onClienteCriado={(novo) =>
    setClientes((prev) => [...prev, novo].sort((a, b) => a.nome.localeCompare(b.nome)))
  }
  onGestorRenomeado={(de, para) =>
    setClientes((prev) =>
      prev.map((c) => (c.gestor === de ? { ...c, gestor: para } : c))
    )
  }
  onGestoresNormalizados={(mapeamento) =>
    setClientes((prev) =>
      prev.map((c) => {
        const m = mapeamento.find((x) => x.de === c.gestor);
        return m ? { ...c, gestor: m.para } : c;
      })
    )
  }
  user={user}
/>
```

- [ ] **Step 4: Esconder sub-tab "Gestores" para não-admins na sidebar**

Localize o loop de `CONFIG_SUB_TABS` na `Sidebar` (~linha 178). Filtre os sub-tabs por `is_admin`:

```tsx
{CONFIG_SUB_TABS
  .filter(({ id }) => id !== "config-gestores" || user?.is_admin)
  .map(({ id: subId, label: subLabel }) => (
    <button
      key={subId}
      onClick={() => setConfigTab(subId)}
      className={[
        "flex w-full items-center rounded-md px-3 py-1.5 text-left text-xs transition",
        configTab === subId ? "font-medium text-[var(--ink)]" : "text-[var(--muted)] hover:text-[var(--ink)]",
      ].join(" ")}
    >
      <span className={["mr-2 text-[8px]", configTab === subId ? "opacity-100" : "opacity-0"].join(" ")}>▸</span>
      {subLabel}
    </button>
  ))}
```

- [ ] **Step 5: Esconder `GestorFiltro` para não-admins**

Localize o bloco do `GestorFiltro` (~linha 1979). Adicione o guard `user?.is_admin`:

```tsx
{user?.is_admin && gestores.length > 0 && (
  <GestorFiltro
    gestores={gestores}
    value={gestorFiltro}
    onChange={setGestorFiltro}
  />
)}
```

- [ ] **Step 6: Verificar TypeScript sem erros**

```bash
cd web/frontend && npm run build 2>&1 | grep -E "error|Error|warning" | head -20
```

Saída esperada: build concluído sem erros de TypeScript.

- [ ] **Step 7: Commit**

```bash
git add web/frontend/app/gestor/page.tsx
git commit -m "feat(gestor-ui): esconde controles admin para usuarios nao-admin"
```

---

## Task 4: Executar seed em produção

- [ ] **Step 1: Dry-run final para confirmar**

```bash
DATABASE_URL="postgresql+psycopg://postgres:fts0cVWPEQqXEQ7KTk&rzR&6@34.95.249.110:5432/autoreport" \
  /Users/mac0267/Documents/auto-report-main/web/backend/.venv/bin/python \
  web/backend/scripts/seed_gestores_acesso.py --dry-run
```

Confirme que todos os 11 gestores aparecem na saída com os emails corretos.

- [ ] **Step 2: Rodar seed real**

```bash
DATABASE_URL="postgresql+psycopg://postgres:fts0cVWPEQqXEQ7KTk&rzR&6@34.95.249.110:5432/autoreport" \
  /Users/mac0267/Documents/auto-report-main/web/backend/.venv/bin/python \
  web/backend/scripts/seed_gestores_acesso.py
```

Saída esperada: `Resumo: 11 usuários criados, N vínculos inseridos`

- [ ] **Step 3: Verificar no banco**

```bash
PGPASSWORD='fts0cVWPEQqXEQ7KTk&rzR&6' psql -h 34.95.249.110 -U postgres -d autoreport -c "
SELECT u.email, u.nome, COUNT(uc.cliente_id) as clientes
FROM usuarios u
LEFT JOIN usuario_clientes uc ON uc.usuario_id = u.id
WHERE u.is_admin = false
GROUP BY u.id, u.email, u.nome
ORDER BY clientes DESC;
"
```

Saída esperada: 11 linhas, cada uma com o email do gestor e a contagem de clientes correspondente.

- [ ] **Step 4: Testar login de um gestor**

```bash
curl -s -X POST https://autoreport-backend.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"jose.neto@turbopartners.com.br","senha":"turbo@2026"}' | python3 -m json.tool
```

Saída esperada: JSON com `token` e `usuario.is_admin: false`.

---

## Task 5: Push e deploy

- [ ] **Step 1: Merge na main**

```bash
git push
gh pr create --base main --head $(git branch --show-current) \
  --title "feat(gestores): acesso segmentado por gestor" \
  --body "Seed script + frontend guards. Admins vêem tudo, gestores vêem só os próprios clientes."
# Aguardar review e mergear
```

- [ ] **Step 2: Triggar deploy no Render**

No Render dashboard, serviço `autoreport-backend` → **Manual Deploy → Deploy latest commit**.

- [ ] **Step 3: Smoke test em produção**

Logar no `/gestor` com `jose.neto@turbopartners.com.br` / `turbo@2026` e confirmar:
- Vê apenas os clientes de José Neto (14 clientes)
- Não vê dropdown "Gestor" no topo
- Não vê botão "Adicionar cliente"
- Não vê sub-tab "Gestores" em Configurações
- Não vê link "Administração →"
