# Área do Cliente — Login por CNPJ + Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar uma terceira persona "cliente" à app que se autentica via CNPJ (cruzando `staging.cup_clientes` → `clientes`) e vê um dashboard próprio de performance, isolado do gestor.

**Architecture:** Novo router FastAPI `api/cliente.py` reusando services de métricas extraídos de `api/gestor.py` para `services/metricas.py`. Frontend novo em `app/cliente/{login,dashboard}` com proxy Next.js para cookie httpOnly. Middleware path-aware lidando com ambas as personas.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Alembic, Next.js 14 App Router, Tailwind, Recharts, Playwright, pytest.

**Spec:** `docs/superpowers/specs/2026-05-26-cliente-view-cnpj-design.md`

---

## File Structure

### Novos — backend
| Arquivo | Responsabilidade |
|---|---|
| `web/backend/alembic/versions/<rev>_add_cnpj_to_cup_clientes.py` | Migration idempotente `ADD COLUMN IF NOT EXISTS cnpj` |
| `web/backend/services/metricas.py` | Funções `build_timeline`, `build_breakdown`, `meses_disponiveis_for_cliente` extraídas do gestor |
| `web/backend/api/cliente.py` | Router `/cliente/*`: login, logout, me, métricas; dep `require_cliente`; helper `normalize_cnpj` |
| `web/backend/tests/test_cliente_auth.py` | Login flow + casos de erro |
| `web/backend/tests/test_cliente_require_dep.py` | Dep auth — isolamento gestor/cliente |
| `web/backend/tests/test_cliente_metricas.py` | Isolamento entre clientes + ausência de campos internos |
| `web/backend/tests/test_services_metricas.py` | Funções extraídas |

### Modificados — backend
| Arquivo | Mudança |
|---|---|
| `web/backend/main.py` | Registrar `cliente.router` com prefix `/cliente` |
| `web/backend/api/gestor.py` | Chamar `services/metricas.py` em vez de helpers inline |
| `web/backend/schemas/__init__.py` | Re-export schemas novos |
| `web/backend/schemas/cliente.py` | **(novo)** `ClienteLoginRequest`, `ClientePublic`, `ClienteLoginResponse` |
| `web/backend/scripts/seed_dev.py` | Popular `cnpj` em `cup_clientes` ao criar mocks |

### Novos — frontend
| Arquivo | Responsabilidade |
|---|---|
| `web/frontend/app/cliente/layout.tsx` | Layout próprio (sem nav do gestor) |
| `web/frontend/app/cliente/login/page.tsx` | Form CNPJ |
| `web/frontend/app/cliente/dashboard/page.tsx` | Dashboard (KPIs + evolução + breakdown) |
| `web/frontend/app/api/cliente/login/route.ts` | Proxy login → seta cookie httpOnly |
| `web/frontend/app/api/cliente/logout/route.ts` | Limpa cookie |
| `web/frontend/app/api/cliente/me/route.ts` | Proxy GET /cliente/me |
| `web/frontend/app/api/cliente/metricas/timeline/route.ts` | Proxy timeline |
| `web/frontend/app/api/cliente/metricas/breakdown/route.ts` | Proxy breakdown |
| `web/frontend/app/api/cliente/metricas/meses-disponiveis/route.ts` | Proxy meses |
| `web/frontend/lib/api-cliente.ts` | Cliente HTTP tipado |
| `web/frontend/tests/cliente-login.spec.ts` | Playwright e2e login |
| `web/frontend/tests/cliente-dashboard.spec.ts` | Playwright e2e dashboard |

### Modificados — frontend
| Arquivo | Mudança |
|---|---|
| `web/frontend/middleware.ts` | Path-aware: distingue `/gestor/*` (cookie `gestor_token`) e `/cliente/dashboard/*` (cookie `cliente_token`); deixa `/cliente/login` passar |

---

## Backend

### Task 1: Migration — adicionar `cnpj` em `staging.cup_clientes`

**Files:**
- Create: `web/backend/alembic/versions/<rev>_add_cnpj_to_cup_clientes.py`

- [ ] **Step 1: Gerar revisão alembic**

```bash
cd web/backend && source .venv/bin/activate
alembic revision -m "add_cnpj_to_cup_clientes"
```

Anote o `<rev>` gerado.

- [ ] **Step 2: Escrever a migration**

Substitua o conteúdo do arquivo criado por:

```python
"""add_cnpj_to_cup_clientes

Revision ID: <rev>
Revises: f3a1b2c4d5e6
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "<rev>"
down_revision: Union[str, None] = "f3a1b2c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotente: em produção a coluna já existe (populada por pipeline externo);
    # em dev/local cria. Sem índice — tabela tem ~1k linhas.
    op.execute("ALTER TABLE staging.cup_clientes ADD COLUMN IF NOT EXISTS cnpj text")


def downgrade() -> None:
    op.execute("ALTER TABLE staging.cup_clientes DROP COLUMN IF EXISTS cnpj")
```

Mantenha `<rev>` como o ID que o alembic gerou. Substitua `down_revision` se a head atual não for `f3a1b2c4d5e6` (rode `alembic heads` para conferir).

- [ ] **Step 3: Aplicar migration**

```bash
alembic upgrade head
```

Expected: sem erro; mostra `Running upgrade f3a1b2c4d5e6 -> <rev>`.

- [ ] **Step 4: Verificar no banco**

```bash
PGPASSWORD=vitrine psql -h localhost -U vitrine -d vitrine -c "\d staging.cup_clientes" | grep cnpj
```

Expected: linha contendo `cnpj | text`.

- [ ] **Step 5: Commit**

```bash
git add web/backend/alembic/versions/<rev>_add_cnpj_to_cup_clientes.py
git commit -m "feat(db): adicionar coluna cnpj em staging.cup_clientes (idempotente)"
```

---

### Task 2: Extrair `build_timeline` para `services/metricas.py`

**Files:**
- Create: `web/backend/services/metricas.py`
- Modify: `web/backend/api/gestor.py` (`get_metricas_timeline` em torno da linha 1324)
- Create: `web/backend/tests/test_services_metricas.py`

- [ ] **Step 1: Escrever teste falhante**

Crie `web/backend/tests/test_services_metricas.py`:

```python
def test_build_timeline_imports():
    """Sanity: função existe e é importável.
    A cobertura comportamental real vem dos testes de endpoint
    (test_cliente_metricas), que rodam contra Postgres com snapshots semeados.
    """
    from services.metricas import build_timeline
    assert callable(build_timeline)
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web/backend && source .venv/bin/activate
pytest tests/test_services_metricas.py::test_build_timeline_imports -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'services.metricas'`.

- [ ] **Step 3: Criar `services/metricas.py` com `build_timeline`**

Crie `web/backend/services/metricas.py`:

```python
from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session


def build_timeline(cliente_id: uuid.UUID, meses: int, session: Session) -> list[dict]:
    """Snapshots MENSAL dos últimos N meses, ordem cronológica (antigo → recente).

    Retorna a estrutura interna que os controllers usam para montar o response
    final (gestor inclui campos extras, cliente filtra os internos).
    """
    from models.snapshot import Snapshot

    snapshots = session.execute(
        select(Snapshot)
        .where(Snapshot.cliente_id == cliente_id, Snapshot.frequencia == "MENSAL")
        .order_by(Snapshot.periodo_fim.desc())
        .limit(meses)
    ).scalars().all()

    snapshots = list(reversed(snapshots))

    return [
        {
            "mes": s.periodo_fim.strftime("%Y-%m"),
            "periodo_inicio": str(s.periodo_inicio),
            "periodo_fim": str(s.periodo_fim),
            "faturamento": float(s.faturamento) if s.faturamento is not None else None,
            "investimento": float(s.investimento) if s.investimento is not None else None,
            "roas": float(s.roas) if s.roas is not None else None,
            "cpa": float(s.cpa) if s.cpa is not None else None,
            "leads": s.leads,
            "vendas": s.vendas,
            "faturamento_var_pct": float(s.faturamento_var_pct) if s.faturamento_var_pct is not None else None,
            "roas_var_pct": float(s.roas_var_pct) if s.roas_var_pct is not None else None,
        }
        for s in snapshots
    ]
```

- [ ] **Step 4: Atualizar `api/gestor.py` para usar a função**

Em `web/backend/api/gestor.py`, localize `get_metricas_timeline`. O handler tem 3 partes:
1. Resolve `cliente` por `slug` + checa `ativo` (manter intacto)
2. Checa acesso `UsuarioCliente` se não for admin (manter intacto)
3. Faz `select(Snapshot)...` + monta lista de items + retorna (**substituir**)

Substitua **apenas a parte 3** — o bloco que começa em:
```python
    snapshots = session.execute(
        select(Snapshot)
```
e vai até o `return {...}` final do handler — pelo seguinte:

```python
    from services.metricas import build_timeline
    items = build_timeline(cliente.id, meses, session)

    return {
        "cliente": {
            "slug": cliente.slug,
            "nome": cliente.nome,
            "categoria": cliente.categoria.value,
            "gestor": cliente.gestor,
        },
        "items": items,
    }
```

O import `from models.snapshot import Snapshot` no início do handler pode ficar — não atrapalha, mesmo não sendo mais usado nessa função (outras no arquivo usam).

- [ ] **Step 5: Rodar teste de imports**

```bash
pytest tests/test_services_metricas.py::test_build_timeline_imports -v
```

Expected: PASS.

- [ ] **Step 6: Rodar suite completa de testes do gestor para non-regression**

```bash
pytest tests/test_auth.py -v
```

Expected: PASS (nada deve ter quebrado — esse arquivo cobre rotas do gestor incluindo timeline indiretamente).

- [ ] **Step 7: Commit**

```bash
git add web/backend/services/metricas.py web/backend/api/gestor.py web/backend/tests/test_services_metricas.py
git commit -m "refactor(metricas): extrair build_timeline para services/metricas.py"
```

---

### Task 3: Extrair `build_breakdown` para `services/metricas.py`

**Files:**
- Modify: `web/backend/services/metricas.py`
- Modify: `web/backend/api/gestor.py` (`get_metricas_breakdown` ~linha 1385)
- Modify: `web/backend/tests/test_services_metricas.py`

- [ ] **Step 1: Adicionar teste**

Em `web/backend/tests/test_services_metricas.py`, adicione:

```python
def test_build_breakdown_imports():
    from services.metricas import build_breakdown
    assert callable(build_breakdown)
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/test_services_metricas.py::test_build_breakdown_imports -v
```

Expected: FAIL — `ImportError: cannot import name 'build_breakdown'`.

- [ ] **Step 3: Adicionar `build_breakdown` em `services/metricas.py`**

No final de `web/backend/services/metricas.py`, adicione:

```python
def _parse_br(v: str | None) -> float | None:
    if not v or v.strip() in ("-", ""):
        return None
    try:
        cleaned = v.replace("R$", "").replace("\xa0", "").strip()
        cleaned = cleaned.replace(".", "").replace(",", ".")
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _parse_int_br(v: str | None) -> int | None:
    if not v or v.strip() in ("-", ""):
        return None
    try:
        return int(v.replace(".", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def build_breakdown(cliente_id: uuid.UUID, mes: str | None, session: Session) -> dict:
    """Top anúncios Meta + Google do snapshot mensal mais recente do cliente
    (ou do mês específico se passado).
    """
    from datetime import date, timedelta
    from models.snapshot import Snapshot

    snap_filter = [Snapshot.cliente_id == cliente_id, Snapshot.frequencia == "MENSAL"]
    if mes:
        ano, mes_num = int(mes[:4]), int(mes[5:7])
        primeiro = date(ano, mes_num, 1)
        if mes_num == 12:
            ultimo = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            ultimo = date(ano, mes_num + 1, 1) - timedelta(days=1)
        snap_filter.append(Snapshot.periodo_fim >= primeiro)
        snap_filter.append(Snapshot.periodo_fim <= ultimo)

    snap = session.execute(
        select(Snapshot).where(*snap_filter).order_by(Snapshot.periodo_fim.desc())
    ).scalars().first()

    if not snap or not snap.raw_dados:
        return {"meta_ads": [], "google_ads": []}

    rd = snap.raw_dados

    meta_ads = []
    for i in range(1, 21):
        nome = rd.get(f"{{{{nome_adf{i}}}}}", "")
        if not nome or nome == "-":
            continue
        img = rd.get(f"{{{{img_adf{i}}}}}", "") or ""
        meta_ads.append({
            "nome": nome,
            "investimento": _parse_br(rd.get(f"{{{{inv_adf{i}}}}}")),
            "leads": _parse_int_br(rd.get(f"{{{{lead_adf{i}}}}}")),
            "cpl": _parse_br(rd.get(f"{{{{cpl_adf{i}}}}}")),
            "conversoes": _parse_int_br(rd.get(f"{{{{conv_adf{i}}}}}")),
            "faturamento": _parse_br(rd.get(f"{{{{fat_adf{i}}}}}")),
            "roas": _parse_br(rd.get(f"{{{{roas_adf{i}}}}}")),
            "cpa": _parse_br(rd.get(f"{{{{cpa_adf{i}}}}}")),
            "impressoes": _parse_int_br(rd.get(f"{{{{imp_adf{i}}}}}")),
            "imagem_url": img if img not in ("__NO_IMAGE__", "-", "") else None,
        })

    google_ads = []
    for i in range(1, 21):
        nome = rd.get(f"{{{{nome_adg{i}}}}}", "")
        if not nome or nome == "-":
            continue
        google_ads.append({
            "nome": nome,
            "investimento": _parse_br(rd.get(f"{{{{inv_adg{i}}}}}")),
            "faturamento": _parse_br(rd.get(f"{{{{fat_adg{i}}}}}")),
            "conversoes": _parse_br(rd.get(f"{{{{conv_adg{i}}}}}")),
            "cpa": _parse_br(rd.get(f"{{{{cpa_adg{i}}}}}")),
            "roas": _parse_br(rd.get(f"{{{{roas_adg{i}}}}}")),
            "impressoes": _parse_int_br(rd.get(f"{{{{imp_adg{i}}}}}")),
        })

    return {"meta_ads": meta_ads, "google_ads": google_ads}
```

- [ ] **Step 4: Atualizar `api/gestor.py` `get_metricas_breakdown`**

Em `web/backend/api/gestor.py`, substitua o corpo de `get_metricas_breakdown` após a checagem de acesso por:

```python
    from services.metricas import build_breakdown
    return build_breakdown(cliente.id, mes, session)
```

Remova as funções `_parse_br` e `_parse_int_br` no topo do arquivo (~linha 1298) — agora vivem em `services/metricas.py`.

- [ ] **Step 5: Rodar suite**

```bash
pytest tests/test_services_metricas.py tests/test_auth.py -v
```

Expected: PASS em tudo.

- [ ] **Step 6: Commit**

```bash
git add web/backend/services/metricas.py web/backend/api/gestor.py web/backend/tests/test_services_metricas.py
git commit -m "refactor(metricas): extrair build_breakdown e parsers PT-BR"
```

---

### Task 4: Extrair `meses_disponiveis_for_cliente` para `services/metricas.py`

**Files:**
- Modify: `web/backend/services/metricas.py`
- Modify: `web/backend/tests/test_services_metricas.py`

- [ ] **Step 1: Adicionar teste**

Em `web/backend/tests/test_services_metricas.py`:

```python
def test_meses_disponiveis_imports():
    from services.metricas import meses_disponiveis_for_cliente
    assert callable(meses_disponiveis_for_cliente)
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/test_services_metricas.py::test_meses_disponiveis_imports -v
```

Expected: FAIL.

- [ ] **Step 3: Adicionar função em `services/metricas.py`**

No final do arquivo:

```python
from sqlalchemy import text


def meses_disponiveis_for_cliente(cliente_id: uuid.UUID, session: Session) -> list[str]:
    """Meses (YYYY-MM, DESC) que têm snapshot MENSAL para o cliente."""
    rows = session.execute(
        text("""
            SELECT DISTINCT TO_CHAR(periodo_fim, 'YYYY-MM') AS mes
            FROM snapshots
            WHERE frequencia = 'MENSAL' AND cliente_id = :cid
            ORDER BY mes DESC
        """),
        {"cid": cliente_id},
    ).all()
    return [r[0] for r in rows]
```

Não modifique o endpoint do gestor `metricas_meses_disponiveis` agora — ele lida com múltiplos clientes (lista do user), o que é diferente do caso do cliente final (1 cliente só). Apenas adicione a função nova.

- [ ] **Step 4: Rodar**

```bash
pytest tests/test_services_metricas.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/services/metricas.py web/backend/tests/test_services_metricas.py
git commit -m "feat(metricas): meses_disponiveis_for_cliente em services/metricas"
```

---

### Task 5: Schemas Pydantic — `schemas/cliente.py`

**Files:**
- Create: `web/backend/schemas/cliente.py`
- Modify: `web/backend/schemas/__init__.py`

- [ ] **Step 1: Criar `schemas/cliente.py`**

```python
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from models.cliente import Categoria


class ClienteLoginRequest(BaseModel):
    cnpj: str = Field(..., min_length=11, max_length=20, description="CNPJ formatado ou só dígitos")


class ClientePublic(BaseModel):
    id: uuid.UUID
    slug: str
    nome: str
    categoria: Categoria
    logo_url: str | None = None
    setor: str | None = None


class ClienteLoginResponse(BaseModel):
    token: str
    cliente: ClientePublic
```

- [ ] **Step 2: Re-exportar em `schemas/__init__.py`**

Abra `web/backend/schemas/__init__.py` e adicione (mantendo o que já existe):

```python
from schemas.cliente import ClienteLoginRequest, ClientePublic, ClienteLoginResponse
```

- [ ] **Step 3: Smoke test de import**

```bash
python -c "from schemas import ClienteLoginRequest, ClientePublic, ClienteLoginResponse; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add web/backend/schemas/cliente.py web/backend/schemas/__init__.py
git commit -m "feat(schemas): adicionar ClienteLoginRequest/Public/Response"
```

---

### Task 6: Helpers `normalize_cnpj` + dep `require_cliente` em `api/cliente.py`

**Files:**
- Create: `web/backend/api/cliente.py`
- Create: `web/backend/tests/test_cliente_require_dep.py`

- [ ] **Step 1: Escrever teste falhante**

Crie `web/backend/tests/test_cliente_require_dep.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt


def test_normalize_cnpj_removes_punctuation():
    from api.cliente import normalize_cnpj
    assert normalize_cnpj("12.345.678/0001-90") == "12345678000190"
    assert normalize_cnpj("  12345678000190  ") == "12345678000190"
    assert normalize_cnpj("abc12def345") == "12345"


def test_require_cliente_rejects_gestor_token():
    """Token com kind='gestor' não pode autenticar em rota de cliente."""
    from fastapi import FastAPI, Depends
    from fastapi.testclient import TestClient
    from api.cliente import router as cliente_router, require_cliente
    from app_settings import get_settings

    settings = get_settings()
    app = FastAPI()
    app.include_router(cliente_router, prefix="/cliente")

    client = TestClient(app)
    # token assinado com o secret real, mas com kind=gestor
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "kind": "gestor",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get("/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_require_cliente_rejects_missing_header():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.cliente import router as cliente_router

    app = FastAPI()
    app.include_router(cliente_router, prefix="/cliente")

    client = TestClient(app)
    r = client.get("/cliente/me")
    assert r.status_code == 401
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web/backend && source .venv/bin/activate
pytest tests/test_cliente_require_dep.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'api.cliente'`.

- [ ] **Step 3: Criar `api/cliente.py` com helpers + dep + endpoint vazio**

```python
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_settings import Settings, get_settings
from db import get_session
from models import Cliente
from schemas import ClientePublic

router = APIRouter()
_log = logging.getLogger(__name__)


# ── Pure utility functions ─────────────────────────────────────────────────

def normalize_cnpj(raw: str) -> str:
    """Remove tudo que não for dígito."""
    return re.sub(r"\D", "", raw or "")


def mask_cnpj(cnpj_digits: str) -> str:
    """Mascara CNPJ para logging: '12345678000190' → '12.***.678/****-**'."""
    d = normalize_cnpj(cnpj_digits)
    if len(d) != 14:
        return "***"
    return f"{d[0:2]}.***.{d[5:8]}/****-**"


def create_cliente_token(
    cliente_id: uuid.UUID,
    *,
    secret: str,
    algorithm: str,
    expiry_hours: int,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    payload = {"sub": str(cliente_id), "kind": "cliente", "exp": expire}
    return jwt.encode(payload, secret, algorithm=algorithm)


# ── FastAPI dependency ─────────────────────────────────────────────────────

def require_cliente(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> Cliente:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("kind") != "cliente":
            raise HTTPException(status_code=401, detail="Token inválido para esta área")
        cid = uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    cliente = session.get(Cliente, cid)
    if cliente is None or not cliente.ativo:
        raise HTTPException(status_code=401, detail="Conta inativa ou inexistente")
    return cliente


# ── Endpoints (placeholder para validar dep) ──────────────────────────────

@router.get("/me", response_model=ClientePublic)
def me(cliente: Cliente = Depends(require_cliente)) -> ClientePublic:
    return ClientePublic(
        id=cliente.id,
        slug=cliente.slug,
        nome=cliente.nome,
        categoria=cliente.categoria,
        logo_url=cliente.logo_url,
        setor=cliente.setor,
    )
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/test_cliente_require_dep.py -v
```

Expected: PASS nos 3 testes.

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/cliente.py web/backend/tests/test_cliente_require_dep.py
git commit -m "feat(cliente): require_cliente dep + normalize_cnpj + endpoint /me"
```

---

### Task 7: Endpoint `POST /cliente/auth/login`

**Files:**
- Modify: `web/backend/api/cliente.py`
- Create: `web/backend/tests/test_cliente_auth.py`

- [ ] **Step 1: Escrever testes falhantes**

Crie `web/backend/tests/test_cliente_auth.py`:

```python
import uuid
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app_settings import Settings, get_settings
from db import get_session
from models import Cliente
from models.base import Base
from models.cliente import Categoria


@pytest.fixture
def app_with_db(tmp_path):
    """FastAPI app montado contra Postgres limpo (NÃO SQLite — usamos staging.cup_clientes
    que é Postgres-only). O teste assume que existe um Postgres rodando localmente em
    postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test."""
    url = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"
    engine = create_engine(url)

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS staging.cup_clientes (
                task_id text PRIMARY KEY,
                nome text,
                cnpj text
            )
        """))
        conn.execute(text("DELETE FROM staging.cup_clientes"))

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    TestSession = sessionmaker(bind=engine)

    from api.cliente import router as cliente_router
    app = FastAPI()
    app.include_router(cliente_router, prefix="/cliente")

    def override_session():
        with TestSession() as s:
            yield s

    def override_settings():
        # Reaproveita defaults reais e só overrida o database_url.
        return Settings(database_url=url)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings

    return app, TestSession


def _seed_cliente(TestSession, *, nome, cnpj, task_id="task-1", ativo=True):
    with TestSession() as s:
        c = Cliente(
            slug=nome.lower().replace(" ", "-"),
            nome=nome,
            categoria=Categoria.LEAD_COM_SITE,
            cup_task_id=task_id,
            ativo=ativo,
        )
        s.add(c); s.commit()
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome, cnpj) VALUES (:t, :n, :c)"),
            {"t": task_id, "n": nome, "c": cnpj},
        )
        s.commit()
        return c.id


def test_login_with_formatted_cnpj_returns_token(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente(TS, nome="Cliente A", cnpj="12345678000190")

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "12.345.678/0001-90"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data
    assert data["cliente"]["id"] == str(cid)
    assert data["cliente"]["nome"] == "Cliente A"
    # campos internos não vazam
    assert "gestor" not in data["cliente"]
    assert "cup_task_id" not in data["cliente"]


def test_login_with_digits_only(app_with_db):
    app, TS = app_with_db
    _seed_cliente(TS, nome="Cliente A", cnpj="12345678000190")

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "12345678000190"})
    assert r.status_code == 200


def test_login_cnpj_not_found(app_with_db):
    app, TS = app_with_db
    _seed_cliente(TS, nome="Cliente A", cnpj="12345678000190")

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "99999999999999"})
    assert r.status_code == 401
    assert "não encontrado" in r.json()["detail"].lower()


def test_login_inactive_cliente(app_with_db):
    app, TS = app_with_db
    _seed_cliente(TS, nome="Inativa", cnpj="11111111000111", ativo=False)

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "11111111000111"})
    assert r.status_code == 401
    assert "inativa" in r.json()["detail"].lower()


def test_login_multiple_cnpjs(app_with_db):
    app, TS = app_with_db
    _seed_cliente(TS, nome="A", cnpj="22222222000122", task_id="t1")
    _seed_cliente(TS, nome="B", cnpj="22222222000122", task_id="t2")

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "22222222000122"})
    assert r.status_code == 401
    assert "múltiplas" in r.json()["detail"].lower() or "multiplas" in r.json()["detail"].lower()


def test_login_broken_link(app_with_db):
    """CNPJ existe em cup_clientes mas não há cliente correspondente."""
    app, TS = app_with_db
    with TS() as s:
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome, cnpj) VALUES ('orfao', 'X', '33333333000133')")
        ); s.commit()

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "33333333000133"})
    assert r.status_code == 401
```

> **Nota:** este teste exige um Postgres local em `localhost:5432` com banco `vitrine_test`. Antes de rodar:
> ```bash
> psql -d postgres -c "CREATE DATABASE vitrine_test OWNER vitrine;" 2>/dev/null || true
> ```

- [ ] **Step 2: Rodar e ver falhar**

```bash
psql -d postgres -c "CREATE DATABASE vitrine_test OWNER vitrine;" 2>/dev/null || true
cd web/backend && source .venv/bin/activate
pytest tests/test_cliente_auth.py -v
```

Expected: FAIL nos 6 testes — endpoint `/cliente/auth/login` não existe (404).

- [ ] **Step 3: Implementar endpoint em `api/cliente.py`**

Adicione no topo de `api/cliente.py` (após os imports):

```python
from sqlalchemy import text
from schemas import ClienteLoginRequest, ClienteLoginResponse, ClientePublic
```

E ao final do arquivo (antes ou depois de `me`):

```python
@router.post("/auth/login", response_model=ClienteLoginResponse)
def login(
    body: ClienteLoginRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> ClienteLoginResponse:
    cnpj_digits = normalize_cnpj(body.cnpj)
    if len(cnpj_digits) < 11:
        _log.info("cliente_login cnpj_mask=*** result=invalid_format")
        raise HTTPException(status_code=401, detail="CNPJ inválido")

    # Busca task_ids em staging.cup_clientes
    rows = session.execute(
        text("""
            SELECT cc.task_id
            FROM staging.cup_clientes cc
            WHERE regexp_replace(COALESCE(cc.cnpj, ''), '[^0-9]', '', 'g') = :cnpj
        """),
        {"cnpj": cnpj_digits},
    ).all()

    masked = mask_cnpj(cnpj_digits)

    if not rows:
        _log.info(f"cliente_login cnpj_mask={masked} result=not_found")
        raise HTTPException(
            status_code=401,
            detail="CNPJ não encontrado. Verifique o número ou entre em contato com seu gestor.",
        )
    if len(rows) > 1:
        _log.info(f"cliente_login cnpj_mask={masked} result=multiple")
        raise HTTPException(
            status_code=401,
            detail="Múltiplas contas encontradas para este CNPJ. Fale com seu gestor.",
        )

    task_id = rows[0][0]
    cliente = session.execute(
        select(Cliente).where(Cliente.cup_task_id == task_id)
    ).scalar_one_or_none()

    if cliente is None:
        _log.info(f"cliente_login cnpj_mask={masked} result=broken_link")
        raise HTTPException(
            status_code=401,
            detail="Conta não disponível no momento. Fale com seu gestor.",
        )

    if not cliente.ativo:
        _log.info(f"cliente_login cnpj_mask={masked} result=inactive")
        raise HTTPException(status_code=401, detail="Conta inativa. Fale com seu gestor.")

    token = create_cliente_token(
        cliente.id,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expiry_hours=settings.jwt_expiry_hours,
    )

    _log.info(f"cliente_login cnpj_mask={masked} result=ok cliente_id={cliente.id}")

    return ClienteLoginResponse(
        token=token,
        cliente=ClientePublic(
            id=cliente.id,
            slug=cliente.slug,
            nome=cliente.nome,
            categoria=cliente.categoria,
            logo_url=cliente.logo_url,
            setor=cliente.setor,
        ),
    )
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/test_cliente_auth.py -v
```

Expected: PASS nos 6.

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/cliente.py web/backend/tests/test_cliente_auth.py
git commit -m "feat(cliente): endpoint POST /cliente/auth/login por CNPJ"
```

---

### Task 8: Endpoint `POST /cliente/auth/logout`

**Files:**
- Modify: `web/backend/api/cliente.py`
- Modify: `web/backend/tests/test_cliente_auth.py`

- [ ] **Step 1: Adicionar teste**

No final de `tests/test_cliente_auth.py`:

```python
def test_logout_returns_204(app_with_db):
    """Logout é stateless: backend só sinaliza ok; frontend limpa cookie."""
    app, TS = app_with_db
    cid = _seed_cliente(TS, nome="Cliente Y", cnpj="44444444000144")

    client = TestClient(app)
    login = client.post("/cliente/auth/login", json={"cnpj": "44444444000144"})
    token = login.json()["token"]

    r = client.post("/cliente/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/test_cliente_auth.py::test_logout_returns_204 -v
```

Expected: FAIL (rota não existe).

- [ ] **Step 3: Adicionar endpoint em `api/cliente.py`**

```python
@router.post("/auth/logout", status_code=204)
def logout(_cliente: Cliente = Depends(require_cliente)) -> None:
    return None
```

- [ ] **Step 4: Rodar e ver passar**

```bash
pytest tests/test_cliente_auth.py::test_logout_returns_204 -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/cliente.py web/backend/tests/test_cliente_auth.py
git commit -m "feat(cliente): endpoint POST /cliente/auth/logout"
```

---

### Task 9: Endpoint `GET /cliente/metricas/timeline`

**Files:**
- Modify: `web/backend/api/cliente.py`
- Create: `web/backend/tests/test_cliente_metricas.py`

- [ ] **Step 1: Escrever teste**

Crie `web/backend/tests/test_cliente_metricas.py`:

```python
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app_settings import Settings, get_settings
from db import get_session
from models import Cliente
from models.base import Base
from models.cliente import Categoria
from models.snapshot import Snapshot, Frequencia


@pytest.fixture
def app_with_db():
    url = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"
    engine = create_engine(url)

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS staging.cup_clientes (
                task_id text PRIMARY KEY, nome text, cnpj text
            )
        """))
        conn.execute(text("DELETE FROM staging.cup_clientes"))
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine)

    from api.cliente import router
    app = FastAPI(); app.include_router(router, prefix="/cliente")

    def s_dep():
        with TS() as s: yield s

    def cfg_dep():
        return Settings(database_url=url)

    app.dependency_overrides[get_session] = s_dep
    app.dependency_overrides[get_settings] = cfg_dep
    return app, TS


def _seed_cliente_with_snaps(TS, *, nome, cnpj, task_id, snaps=None):
    snaps = snaps or [("2026-04", 1000, 100), ("2026-03", 800, 80)]
    with TS() as s:
        c = Cliente(slug=nome.lower(), nome=nome, categoria=Categoria.LEAD_COM_SITE,
                    cup_task_id=task_id, ativo=True)
        s.add(c); s.commit(); s.refresh(c)
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome, cnpj) VALUES (:t, :n, :c)"),
            {"t": task_id, "n": nome, "c": cnpj},
        )
        for mes, fat, inv in snaps:
            ano, m = int(mes[:4]), int(mes[5:7])
            s.add(Snapshot(
                cliente_id=c.id,
                periodo_inicio=date(ano, m, 1),
                periodo_fim=date(ano, m, 28),
                frequencia=Frequencia.MENSAL,
                faturamento=Decimal(fat), investimento=Decimal(inv),
                roas=Decimal("3.5"), cpa=Decimal(50),
                leads=20, vendas=5,
            ))
        s.commit()
        return c.id


def _login(client, cnpj):
    return client.post("/cliente/auth/login", json={"cnpj": cnpj}).json()["token"]


def test_timeline_returns_own_snapshots(app_with_db):
    app, TS = app_with_db
    _seed_cliente_with_snaps(TS, nome="A", cnpj="55555555000155", task_id="tA")
    client = TestClient(app)
    tok = _login(client, "55555555000155")

    r = client.get("/cliente/metricas/timeline?meses=12",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    # ordem cronológica (antigo → recente)
    assert data["items"][0]["mes"] == "2026-03"
    assert data["items"][1]["mes"] == "2026-04"
    # campos internos não vazam
    assert "gestor" not in data
    assert "slides_url" not in str(data)


def test_timeline_isolation(app_with_db):
    """Cliente A logado não vê snapshots de B."""
    app, TS = app_with_db
    _seed_cliente_with_snaps(TS, nome="A", cnpj="66666666000166", task_id="tA",
                             snaps=[("2026-04", 1000, 100)])
    _seed_cliente_with_snaps(TS, nome="B", cnpj="77777777000177", task_id="tB",
                             snaps=[("2026-04", 9999, 999)])
    client = TestClient(app)
    tok_a = _login(client, "66666666000166")

    r = client.get("/cliente/metricas/timeline?meses=12",
                   headers={"Authorization": f"Bearer {tok_a}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["faturamento"] == 1000.0  # do A, não do B


def test_timeline_empty(app_with_db):
    app, TS = app_with_db
    _seed_cliente_with_snaps(TS, nome="C", cnpj="88888888000188", task_id="tC", snaps=[])
    client = TestClient(app)
    tok = _login(client, "88888888000188")

    r = client.get("/cliente/metricas/timeline?meses=12",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json() == {"items": []}
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/test_cliente_metricas.py::test_timeline_returns_own_snapshots -v
```

Expected: FAIL (rota não existe).

- [ ] **Step 3: Adicionar endpoint em `api/cliente.py`**

No topo dos imports, garanta:

```python
from fastapi import Query
from services.metricas import build_timeline
```

E adicione o endpoint:

```python
@router.get("/metricas/timeline")
def metricas_timeline(
    meses: int = Query(12, ge=1, le=36),
    cliente: Cliente = Depends(require_cliente),
    session: Session = Depends(get_session),
) -> dict:
    return {"items": build_timeline(cliente.id, meses, session)}
```

- [ ] **Step 4: Rodar**

```bash
pytest tests/test_cliente_metricas.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/cliente.py web/backend/tests/test_cliente_metricas.py
git commit -m "feat(cliente): GET /cliente/metricas/timeline reusando services"
```

---

### Task 10: Endpoint `GET /cliente/metricas/breakdown`

**Files:**
- Modify: `web/backend/api/cliente.py`
- Modify: `web/backend/tests/test_cliente_metricas.py`

- [ ] **Step 1: Adicionar teste**

Adicione em `tests/test_cliente_metricas.py`:

```python
def test_breakdown_isolation(app_with_db):
    app, TS = app_with_db
    # seed A com raw_dados (1 ad meta)
    with TS() as s:
        c_a = Cliente(slug="a", nome="A", categoria=Categoria.LEAD_COM_SITE,
                      cup_task_id="tA", ativo=True)
        s.add(c_a); s.commit(); s.refresh(c_a)
        s.execute(text("INSERT INTO staging.cup_clientes (task_id, nome, cnpj) VALUES ('tA','A','99999999000199')")); s.commit()
        s.add(Snapshot(
            cliente_id=c_a.id,
            periodo_inicio=date(2026, 4, 1), periodo_fim=date(2026, 4, 30),
            frequencia=Frequencia.MENSAL,
            raw_dados={
                "{{nome_adf1}}": "Ad do A",
                "{{inv_adf1}}": "R$ 100,00",
            },
        )); s.commit()

    client = TestClient(app)
    tok = _login(client, "99999999000199")
    r = client.get("/cliente/metricas/breakdown?mes=2026-04",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["meta_ads"]) == 1
    assert data["meta_ads"][0]["nome"] == "Ad do A"
    assert data["meta_ads"][0]["investimento"] == 100.0
    assert data["google_ads"] == []
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/test_cliente_metricas.py::test_breakdown_isolation -v
```

Expected: FAIL.

- [ ] **Step 3: Adicionar endpoint**

Em `api/cliente.py`, garanta o import:

```python
from services.metricas import build_breakdown
```

E adicione:

```python
_MES_RE = re.compile(r"^\d{4}-\d{2}$")


@router.get("/metricas/breakdown")
def metricas_breakdown(
    mes: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    cliente: Cliente = Depends(require_cliente),
    session: Session = Depends(get_session),
) -> dict:
    return build_breakdown(cliente.id, mes, session)
```

- [ ] **Step 4: Rodar**

```bash
pytest tests/test_cliente_metricas.py -v
```

Expected: PASS em todos.

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/cliente.py web/backend/tests/test_cliente_metricas.py
git commit -m "feat(cliente): GET /cliente/metricas/breakdown"
```

---

### Task 11: Endpoint `GET /cliente/metricas/meses-disponiveis`

**Files:**
- Modify: `web/backend/api/cliente.py`
- Modify: `web/backend/tests/test_cliente_metricas.py`

- [ ] **Step 1: Adicionar teste**

```python
def test_meses_disponiveis(app_with_db):
    app, TS = app_with_db
    _seed_cliente_with_snaps(TS, nome="M", cnpj="10101010000110", task_id="tM",
                             snaps=[("2026-04", 1000, 100), ("2026-03", 900, 90)])
    client = TestClient(app)
    tok = _login(client, "10101010000110")

    r = client.get("/cliente/metricas/meses-disponiveis",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json() == {"meses": ["2026-04", "2026-03"]}
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/test_cliente_metricas.py::test_meses_disponiveis -v
```

Expected: FAIL.

- [ ] **Step 3: Implementar**

Em `api/cliente.py`:

```python
from services.metricas import meses_disponiveis_for_cliente
```

E o endpoint:

```python
@router.get("/metricas/meses-disponiveis")
def metricas_meses_disponiveis(
    cliente: Cliente = Depends(require_cliente),
    session: Session = Depends(get_session),
) -> dict:
    return {"meses": meses_disponiveis_for_cliente(cliente.id, session)}
```

- [ ] **Step 4: Rodar**

```bash
pytest tests/test_cliente_metricas.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/cliente.py web/backend/tests/test_cliente_metricas.py
git commit -m "feat(cliente): GET /cliente/metricas/meses-disponiveis"
```

---

### Task 12: Registrar router em `main.py` + atualizar `seed_dev.py`

**Files:**
- Modify: `web/backend/main.py`
- Modify: `web/backend/scripts/seed_dev.py`

- [ ] **Step 1: Registrar router**

Em `web/backend/main.py`, no topo:

```python
from api.cliente import router as cliente_router
```

E em `create_app()`, após `app.include_router(gestor_router, prefix="/gestor")`:

```python
    app.include_router(cliente_router, prefix="/cliente")
```

- [ ] **Step 2: Atualizar seed_dev.py**

Abra `web/backend/scripts/seed_dev.py`. Adicione `from sqlalchemy import text` aos imports do topo (se ainda não tiver).

Em `main()`, logo antes do `session.commit()` final (que hoje está na linha ~197), adicione um bloco que cria/upsert linhas em `staging.cup_clientes` apontando para os clientes recém-criados via `cup_task_id`. Cada cliente do seed recebe um `task_id = f"task-mock-{slug}"` e um CNPJ fictício previsível baseado no índice:

```python
        # Vincula cada cliente a uma row em staging.cup_clientes com CNPJ
        # determinístico — usado pela área do cliente (/cliente/login).
        for idx, data in enumerate(CLIENTES_DATA, start=1):
            slug = data[0]
            nome = data[1]
            task_id = f"task-mock-{slug}"
            cnpj = f"{idx:014d}"  # 00000000000001, 00000000000002, ...
            # Garante schema (em DBs novos)
            session.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS staging.cup_clientes (
                    task_id text PRIMARY KEY,
                    nome text,
                    cnpj text
                )
            """))
            session.execute(text("""
                INSERT INTO staging.cup_clientes (task_id, nome, cnpj)
                VALUES (:t, :n, :c)
                ON CONFLICT (task_id) DO UPDATE
                SET nome = EXCLUDED.nome, cnpj = EXCLUDED.cnpj
            """), {"t": task_id, "n": nome, "c": cnpj})
            session.execute(
                text("UPDATE clientes SET cup_task_id = :t WHERE slug = :s"),
                {"t": task_id, "s": slug},
            )
```

E ajuste o print final para também reportar quantos CNPJs foram semeados:

```python
        print(f"Seeded {len(CLIENTES_DATA)} clientes com {len(CLIENTES_DATA) * MESES} snapshots + cup_clientes/CNPJ")
```

**CNPJ semeado para o cliente `loja-fashion` (primeiro): `00000000000001`.** Usar esse no teste manual do Step 4.

- [ ] **Step 3: Subir o backend e testar /docs**

```bash
cd web/backend && source .venv/bin/activate
uvicorn main:app --port 8765 &
sleep 2
curl -s http://localhost:8765/openapi.json | python3 -c "
import sys, json
paths = sorted(p for p in json.load(sys.stdin)['paths'] if p.startswith('/cliente'))
for p in paths: print(p)
"
pkill -f "uvicorn main:app"
```

Expected: lista contendo `/cliente/auth/login`, `/cliente/auth/logout`, `/cliente/me`, `/cliente/metricas/timeline`, `/cliente/metricas/breakdown`, `/cliente/metricas/meses-disponiveis`.

- [ ] **Step 4: Rodar seed e validar login local**

```bash
python scripts/seed_dev.py
uvicorn main:app --port 8765 &
sleep 2
curl -X POST http://localhost:8765/cliente/auth/login \
  -H "Content-Type: application/json" \
  -d '{"cnpj": "00000000000001"}'
pkill -f "uvicorn main:app"
```

Expected: response 200 com `token` e `cliente` (slug `loja-fashion`).

- [ ] **Step 5: Commit**

```bash
git add web/backend/main.py web/backend/scripts/seed_dev.py
git commit -m "feat(cliente): registrar router /cliente + seed com CNPJ"
```

---

## Frontend

### Task 13: `lib/api-cliente.ts` — cliente HTTP tipado

**Files:**
- Create: `web/frontend/lib/api-cliente.ts`

- [ ] **Step 1: Criar o arquivo**

```typescript
// web/frontend/lib/api-cliente.ts
export type ClientePublic = {
  id: string;
  slug: string;
  nome: string;
  categoria: string;
  logo_url: string | null;
  setor: string | null;
};

export type TimelineItem = {
  mes: string;
  periodo_inicio: string;
  periodo_fim: string;
  faturamento: number | null;
  investimento: number | null;
  roas: number | null;
  cpa: number | null;
  leads: number | null;
  vendas: number | null;
  faturamento_var_pct: number | null;
  roas_var_pct: number | null;
};

export type MetaAd = {
  nome: string;
  imagem_url: string | null;
  investimento: number | null;
  leads: number | null;
  cpl: number | null;
  conversoes: number | null;
  faturamento: number | null;
  roas: number | null;
  cpa: number | null;
  impressoes: number | null;
};

export type GoogleAd = {
  nome: string;
  investimento: number | null;
  faturamento: number | null;
  conversoes: number | null;
  cpa: number | null;
  roas: number | null;
  impressoes: number | null;
};

export type Breakdown = { meta_ads: MetaAd[]; google_ads: GoogleAd[] };

class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api/cliente${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { detail = (await r.json()).detail ?? detail; } catch {}
    throw new ApiError(r.status, detail);
  }
  if (r.status === 204) return undefined as T;
  return r.json();
}

export const clienteApi = {
  login: (cnpj: string) => call<{ ok: true; cliente: ClientePublic }>("/login", {
    method: "POST",
    body: JSON.stringify({ cnpj }),
  }),
  logout: () => call<void>("/logout", { method: "POST" }),
  me: () => call<ClientePublic>("/me"),
  timeline: (meses = 12) => call<{ items: TimelineItem[] }>(`/metricas/timeline?meses=${meses}`),
  breakdown: (mes: string) => call<Breakdown>(`/metricas/breakdown?mes=${mes}`),
  mesesDisponiveis: () => call<{ meses: string[] }>("/metricas/meses-disponiveis"),
};

export { ApiError };
```

- [ ] **Step 2: Smoke test**

```bash
cd web/frontend && npx tsc --noEmit lib/api-cliente.ts
```

Expected: sem erros de tipo.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/lib/api-cliente.ts
git commit -m "feat(cliente-fe): lib/api-cliente.ts tipado"
```

---

### Task 14: Next API proxy routes (login + logout)

**Files:**
- Create: `web/frontend/app/api/cliente/login/route.ts`
- Create: `web/frontend/app/api/cliente/logout/route.ts`

- [ ] **Step 1: Criar `login/route.ts`**

```typescript
// web/frontend/app/api/cliente/login/route.ts
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8765";
const COOKIE_NAME = "cliente_token";
const EXPIRY_HOURS = 8;

export async function POST(req: NextRequest) {
  const { cnpj } = await req.json();
  const r = await fetch(`${API_URL}/cliente/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cnpj }),
  });

  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: "Erro inesperado" }));
    return NextResponse.json({ detail: data.detail ?? "Erro inesperado" }, { status: r.status });
  }

  const data = await r.json();
  const resp = NextResponse.json({ ok: true, cliente: data.cliente });
  resp.cookies.set({
    name: COOKIE_NAME,
    value: data.token,
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: EXPIRY_HOURS * 3600,
  });
  return resp;
}
```

- [ ] **Step 2: Criar `logout/route.ts`**

```typescript
// web/frontend/app/api/cliente/logout/route.ts
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8765";

export async function POST(req: NextRequest) {
  const token = req.cookies.get("cliente_token")?.value;
  if (token) {
    // Best-effort no backend; ignora erro
    await fetch(`${API_URL}/cliente/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  const resp = NextResponse.json({ ok: true });
  resp.cookies.delete("cliente_token");
  return resp;
}
```

- [ ] **Step 3: Type-check**

```bash
cd web/frontend && npx tsc --noEmit
```

Expected: sem erros.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/api/cliente/login/route.ts web/frontend/app/api/cliente/logout/route.ts
git commit -m "feat(cliente-fe): proxy routes login + logout com cookie httpOnly"
```

---

### Task 15: Next API proxy routes (me + métricas)

**Files:**
- Create: `web/frontend/app/api/cliente/me/route.ts`
- Create: `web/frontend/app/api/cliente/metricas/timeline/route.ts`
- Create: `web/frontend/app/api/cliente/metricas/breakdown/route.ts`
- Create: `web/frontend/app/api/cliente/metricas/meses-disponiveis/route.ts`

- [ ] **Step 1: Criar helper compartilhado**

Crie `web/frontend/app/api/cliente/_proxy.ts`:

```typescript
// web/frontend/app/api/cliente/_proxy.ts
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8765";

export async function proxyGet(req: NextRequest, backendPath: string, query?: URLSearchParams) {
  const token = req.cookies.get("cliente_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Token ausente" }, { status: 401 });
  }
  const url = `${API_URL}${backendPath}${query ? `?${query.toString()}` : ""}`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  const body = await r.text();
  return new NextResponse(body, {
    status: r.status,
    headers: { "Content-Type": r.headers.get("Content-Type") ?? "application/json" },
  });
}
```

- [ ] **Step 2: Criar `me/route.ts`**

```typescript
// web/frontend/app/api/cliente/me/route.ts
import { NextRequest } from "next/server";
import { proxyGet } from "../_proxy";

export async function GET(req: NextRequest) {
  return proxyGet(req, "/cliente/me");
}
```

- [ ] **Step 3: Criar `metricas/timeline/route.ts`**

```typescript
// web/frontend/app/api/cliente/metricas/timeline/route.ts
import { NextRequest } from "next/server";
import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  const meses = req.nextUrl.searchParams.get("meses") ?? "12";
  return proxyGet(req, "/cliente/metricas/timeline", new URLSearchParams({ meses }));
}
```

- [ ] **Step 4: Criar `metricas/breakdown/route.ts`**

```typescript
// web/frontend/app/api/cliente/metricas/breakdown/route.ts
import { NextRequest, NextResponse } from "next/server";
import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  const mes = req.nextUrl.searchParams.get("mes");
  if (!mes) return NextResponse.json({ detail: "mes obrigatório" }, { status: 400 });
  return proxyGet(req, "/cliente/metricas/breakdown", new URLSearchParams({ mes }));
}
```

- [ ] **Step 5: Criar `metricas/meses-disponiveis/route.ts`**

```typescript
// web/frontend/app/api/cliente/metricas/meses-disponiveis/route.ts
import { NextRequest } from "next/server";
import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  return proxyGet(req, "/cliente/metricas/meses-disponiveis");
}
```

- [ ] **Step 6: Type-check**

```bash
cd web/frontend && npx tsc --noEmit
```

Expected: sem erros.

- [ ] **Step 7: Commit**

```bash
git add web/frontend/app/api/cliente/
git commit -m "feat(cliente-fe): proxy routes me + métricas (timeline/breakdown/meses)"
```

---

### Task 16: Middleware — path-aware para `/cliente/*`

**Files:**
- Modify: `web/frontend/middleware.ts`

- [ ] **Step 1: Substituir o conteúdo do middleware**

```typescript
// web/frontend/middleware.ts
import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Área do cliente
  if (pathname.startsWith("/cliente/")) {
    if (pathname === "/cliente/login") {
      return NextResponse.next();
    }
    const token = req.cookies.get("cliente_token")?.value;
    if (!token) {
      const loginUrl = req.nextUrl.clone();
      loginUrl.pathname = "/cliente/login";
      loginUrl.search = "";
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.next();
  }

  // Área do gestor (comportamento existente)
  if (pathname === "/gestor/login") {
    return NextResponse.next();
  }
  if (pathname.startsWith("/gestor/")) {
    const token = req.cookies.get("gestor_token")?.value;
    if (!token) {
      const loginUrl = req.nextUrl.clone();
      loginUrl.pathname = "/gestor/login";
      loginUrl.search = "";
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|api/).*)",
  ],
};
```

- [ ] **Step 2: Type-check**

```bash
cd web/frontend && npx tsc --noEmit
```

Expected: sem erros.

- [ ] **Step 3: Subir frontend e validar redirect**

```bash
cd web/frontend && npm run dev &
sleep 5
# Sem cookie → /cliente/dashboard redireciona pra /cliente/login
curl -si http://localhost:3000/cliente/dashboard | grep -E "^(HTTP|location)"
pkill -f "next dev"
```

Expected: `HTTP/1.1 307` e `location: /cliente/login`.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/middleware.ts
git commit -m "feat(cliente-fe): middleware path-aware para /cliente/* e /gestor/*"
```

---

### Task 17: `app/cliente/layout.tsx`

**Files:**
- Create: `web/frontend/app/cliente/layout.tsx`

- [ ] **Step 1: Criar layout**

```tsx
// web/frontend/app/cliente/layout.tsx
export default function ClienteLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-[var(--paper)]">{children}</div>;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/frontend/app/cliente/layout.tsx
git commit -m "feat(cliente-fe): layout da área do cliente"
```

---

### Task 18: Página de login `/cliente/login`

**Files:**
- Create: `web/frontend/app/cliente/login/page.tsx`

- [ ] **Step 1: Criar página**

```tsx
// web/frontend/app/cliente/login/page.tsx
"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { clienteApi, ApiError } from "@/lib/api-cliente";

function maskCNPJ(v: string): string {
  const d = v.replace(/\D/g, "").slice(0, 14);
  if (d.length <= 2) return d;
  if (d.length <= 5) return `${d.slice(0, 2)}.${d.slice(2)}`;
  if (d.length <= 8) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5)}`;
  if (d.length <= 12) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8)}`;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

export default function LoginPage() {
  const router = useRouter();
  const search = useSearchParams();
  const [cnpj, setCnpj] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(
    search.get("expired") ? "Sua sessão expirou. Entre novamente." : null
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      await clienteApi.login(cnpj);
      router.push("/cliente/dashboard");
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : "Erro ao entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="font-display mb-1 text-2xl font-medium tracking-tight text-[var(--ink)]">
        Área do Cliente
      </h1>
      <p className="mb-8 text-xs text-[var(--muted)]">
        Entre com o CNPJ para ver seus dados de performance.
      </p>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label htmlFor="cnpj" className="flex flex-col gap-1">
          <span className="text-xs text-[var(--muted)]">CNPJ</span>
          <input
            id="cnpj"
            inputMode="numeric"
            autoComplete="off"
            value={cnpj}
            onChange={(e) => setCnpj(maskCNPJ(e.target.value))}
            placeholder="00.000.000/0000-00"
            className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          />
        </label>

        {err && (
          <p role="alert" className="text-xs text-[var(--crimson)]">
            {err}
          </p>
        )}

        <button
          type="submit"
          disabled={loading || cnpj.replace(/\D/g, "").length < 11}
          className="rounded-full border border-[var(--forest)] px-5 py-2 text-xs uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 2: Type-check + smoke**

```bash
cd web/frontend && npx tsc --noEmit
npm run dev &
sleep 5
curl -si http://localhost:3000/cliente/login | head -1
pkill -f "next dev"
```

Expected: `HTTP/1.1 200`.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/app/cliente/login/page.tsx
git commit -m "feat(cliente-fe): página /cliente/login"
```

---

### Task 19: Playwright e2e para login

**Files:**
- Create: `web/frontend/tests/cliente-login.spec.ts`

- [ ] **Step 1: Escrever testes**

```typescript
// web/frontend/tests/cliente-login.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Cliente login", () => {
  test("renderiza form de CNPJ", async ({ page }) => {
    await page.goto("/cliente/login");
    await expect(page.getByLabel("CNPJ")).toBeVisible();
    await expect(page.getByRole("button", { name: /entrar/i })).toBeVisible();
  });

  test("CNPJ inválido mostra mensagem de erro", async ({ page }) => {
    await page.goto("/cliente/login");
    await page.getByLabel("CNPJ").fill("99999999000199");
    await page.getByRole("button", { name: /entrar/i }).click();
    await expect(page.getByRole("alert")).toContainText(/não encontrado|não disponível|inativa|múltiplas/i);
  });

  test("CNPJ válido redireciona para /cliente/dashboard", async ({ page }) => {
    await page.goto("/cliente/login");
    // CNPJ semeado por scripts/seed_dev.py — ajuste se necessário
    await page.getByLabel("CNPJ").fill("00000000000001");
    await page.getByRole("button", { name: /entrar/i }).click();
    await page.waitForURL("**/cliente/dashboard", { timeout: 5000 });
  });

  test("acessar /cliente/dashboard sem cookie redireciona para login", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/cliente/dashboard");
    await page.waitForURL("**/cliente/login", { timeout: 5000 });
  });
});
```

- [ ] **Step 2: Rodar (precisa backend + frontend ativos)**

```bash
# Em outro terminal:
cd web/backend && source .venv/bin/activate && uvicorn main:app --port 8765 &
cd web/frontend && PORT=3010 npm run dev &
sleep 5
cd web/frontend && npx playwright test tests/cliente-login.spec.ts
```

Expected: 4 PASS.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/tests/cliente-login.spec.ts
git commit -m "test(cliente-fe): Playwright e2e login"
```

---

### Task 20: `app/cliente/dashboard/page.tsx` — esqueleto

**Files:**
- Create: `web/frontend/app/cliente/dashboard/page.tsx`

- [ ] **Step 1: Criar estrutura base (header + seletor + área de loading)**

```tsx
// web/frontend/app/cliente/dashboard/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clienteApi,
  ApiError,
  ClientePublic,
  TimelineItem,
  Breakdown,
} from "@/lib/api-cliente";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const NOMES_MES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
function mesLabel(mes: string): string {
  const [a, m] = mes.split("-");
  return `${NOMES_MES[parseInt(m) - 1]} ${a}`;
}
function fmtBRL(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}
function fmtNum(v: number | null | undefined, d = 2) {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { maximumFractionDigits: d });
}
function fmtPct(v: number | null | undefined) {
  if (v == null) return "—";
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(1)}%`;
}

export default function ClienteDashboardPage() {
  const router = useRouter();
  const [cliente, setCliente] = useState<ClientePublic | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [mesesDisponiveis, setMesesDisponiveis] = useState<string[]>([]);
  const [mes, setMes] = useState<string>("");
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingBreakdown, setLoadingBreakdown] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [verTodosMeta, setVerTodosMeta] = useState(false);
  const [verTodosGoogle, setVerTodosGoogle] = useState(false);

  useEffect(() => {
    Promise.all([
      clienteApi.me(),
      clienteApi.timeline(12),
      clienteApi.mesesDisponiveis(),
    ])
      .then(([me, tl, md]) => {
        setCliente(me);
        setTimeline(tl.items);
        setMesesDisponiveis(md.meses);
        if (md.meses.length > 0) setMes(md.meses[0]);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) {
          router.push("/cliente/login?expired=1");
          return;
        }
        setErr(e instanceof Error ? e.message : "Erro ao carregar dados.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    if (!mes) return;
    setLoadingBreakdown(true);
    clienteApi.breakdown(mes)
      .then(setBreakdown)
      .catch(() => setBreakdown(null))
      .finally(() => setLoadingBreakdown(false));
  }, [mes]);

  const snapMes = useMemo(
    () => timeline.find((i) => i.mes === mes) ?? null,
    [timeline, mes]
  );

  const chartData = useMemo(
    () => timeline.map((i) => ({
      mes: mesLabel(i.mes),
      Faturamento: i.faturamento ?? 0,
      Investimento: i.investimento ?? 0,
      ROAS: i.roas ?? 0,
    })),
    [timeline]
  );

  async function handleLogout() {
    await clienteApi.logout().catch(() => {});
    router.push("/cliente/login");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  if (err) {
    return (
      <main className="mx-auto max-w-md px-6 py-12">
        <p className="text-sm text-[var(--crimson)]">{err}</p>
      </main>
    );
  }

  const metaAds = breakdown?.meta_ads ?? [];
  const googleAds = breakdown?.google_ads ?? [];

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          {cliente?.logo_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={cliente.logo_url} alt={cliente.nome} className="h-10 w-10 rounded object-contain" />
          )}
          <div>
            <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
              {cliente?.nome ?? "Cliente"}
            </h1>
            <p className="mt-1 text-xs text-[var(--muted)]">{cliente?.setor ?? cliente?.categoria}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {mesesDisponiveis.length > 0 && (
            <>
              <label htmlFor="mes" className="text-xs text-[var(--muted)]">Mês:</label>
              <select
                id="mes"
                value={mes}
                onChange={(e) => setMes(e.target.value)}
                className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
              >
                {mesesDisponiveis.map((m) => (
                  <option key={m} value={m}>{mesLabel(m)}</option>
                ))}
              </select>
            </>
          )}
          <button
            onClick={handleLogout}
            className="rounded-full border border-[var(--rule-soft)] px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
          >
            Sair
          </button>
        </div>
      </header>

      {/* KPIs */}
      <section className="mb-8">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">
          KPIs {mes && `· ${mesLabel(mes)}`}
        </p>
        {!snapMes ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
            Seus dados ainda estão sendo processados. Volte em breve.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              { label: "Faturamento", value: fmtBRL(snapMes.faturamento), var: snapMes.faturamento_var_pct },
              { label: "Investimento", value: fmtBRL(snapMes.investimento), var: null },
              { label: "ROAS", value: snapMes.roas != null ? `${fmtNum(snapMes.roas)}×` : "—", var: snapMes.roas_var_pct },
              { label: "CPA", value: fmtBRL(snapMes.cpa), var: null },
              { label: "Leads", value: snapMes.leads != null ? snapMes.leads.toLocaleString("pt-BR") : "—", var: null },
              { label: "Vendas", value: snapMes.vendas != null ? snapMes.vendas.toLocaleString("pt-BR") : "—", var: null },
            ].map((kpi) => (
              <div key={kpi.label} className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-3">
                <p className="eyebrow mb-1 text-[10px] text-[var(--muted)]">{kpi.label}</p>
                <p className="font-mono-num text-lg font-medium text-[var(--ink)]">{kpi.value}</p>
                {kpi.var != null && (
                  <p className={`font-mono-num text-[10px] ${kpi.var >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                    {fmtPct(kpi.var)} vs mês anterior
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Evolução */}
      {chartData.length > 1 && (
        <section className="mb-8">
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Evolução · últimos {chartData.length} meses</p>
          <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="var(--rule-soft)" strokeDasharray="3 3" />
                <XAxis dataKey="mes" tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <YAxis yAxisId="left" tick={{ fill: "var(--muted)", fontSize: 11 }} tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "var(--paper)", border: "1px solid var(--rule-soft)", fontSize: 12 }}
                  formatter={(value, name) => {
                    const v = typeof value === "number" ? value : 0;
                    if (name === "ROAS") return [`${v.toFixed(2)}×`, name as string];
                    return [fmtBRL(v), name as string];
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line yAxisId="left" type="monotone" dataKey="Faturamento" stroke="var(--forest)" strokeWidth={2} dot={{ r: 3 }} />
                <Line yAxisId="left" type="monotone" dataKey="Investimento" stroke="var(--amber)" strokeWidth={2} dot={{ r: 3 }} />
                <Line yAxisId="right" type="monotone" dataKey="ROAS" stroke="var(--crimson)" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Campanhas */}
      <section className="mb-8">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">
          Campanhas {mes && `· ${mesLabel(mes)}`}
        </p>
        {loadingBreakdown ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
            Carregando…
          </p>
        ) : !breakdown || (metaAds.length === 0 && googleAds.length === 0) ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
            Sem detalhamento de campanhas neste mês.
          </p>
        ) : (
          <div className="flex flex-col gap-5">
            {metaAds.length > 0 && (
              <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
                <p className="eyebrow mb-2 text-[10px] font-medium text-[var(--muted)]">Meta Ads — top anúncios</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-[var(--rule-soft)]">
                        <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">Criativo</th>
                        <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">Anúncio</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Leads</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Conv.</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Fat.</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">CPL/CPA</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
                        <th className="pb-1 text-right font-medium text-[var(--muted)]">Impressões</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(verTodosMeta ? metaAds : metaAds.slice(0, 5)).map((ad, i) => (
                        <tr key={i} className="border-b border-[var(--rule-soft)]/40">
                          <td className="py-2 pr-3">
                            {ad.imagem_url ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={ad.imagem_url} alt={ad.nome} className="h-10 w-10 rounded object-cover" />
                            ) : (
                              <div className="h-10 w-10 rounded bg-[var(--paper)]" />
                            )}
                          </td>
                          <td className="py-2 pr-3 font-medium text-[var(--ink)]">{ad.nome}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.investimento)}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.leads ?? "—"}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.conversoes ?? "—"}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.faturamento)}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.cpl ?? ad.cpa)}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.roas != null ? `${fmtNum(ad.roas)}×` : "—"}</td>
                          <td className="py-2 text-right font-mono-num text-[var(--ink)]">{ad.impressoes != null ? ad.impressoes.toLocaleString("pt-BR") : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {metaAds.length > 5 && (
                  <button onClick={() => setVerTodosMeta((v) => !v)} className="mt-2 text-[10px] text-[var(--forest)] hover:underline">
                    {verTodosMeta ? "Mostrar só top 5" : `Ver todos os ${metaAds.length}`}
                  </button>
                )}
              </div>
            )}

            {googleAds.length > 0 && (
              <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
                <p className="eyebrow mb-2 text-[10px] font-medium text-[var(--muted)]">Google Ads — top campanhas</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-[var(--rule-soft)]">
                        <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">Campanha</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Conv.</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Fat.</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">CPA</th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
                        <th className="pb-1 text-right font-medium text-[var(--muted)]">Impressões</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(verTodosGoogle ? googleAds : googleAds.slice(0, 5)).map((ad, i) => (
                        <tr key={i} className="border-b border-[var(--rule-soft)]/40">
                          <td className="py-2 pr-3 font-medium text-[var(--ink)]">{ad.nome}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.investimento)}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.conversoes ?? "—"}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.faturamento)}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.cpa)}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.roas != null ? `${fmtNum(ad.roas)}×` : "—"}</td>
                          <td className="py-2 text-right font-mono-num text-[var(--ink)]">{ad.impressoes != null ? ad.impressoes.toLocaleString("pt-BR") : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {googleAds.length > 5 && (
                  <button onClick={() => setVerTodosGoogle((v) => !v)} className="mt-2 text-[10px] text-[var(--forest)] hover:underline">
                    {verTodosGoogle ? "Mostrar só top 5" : `Ver todas as ${googleAds.length}`}
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd web/frontend && npx tsc --noEmit
```

Expected: sem erros.

- [ ] **Step 3: Verificar render manual**

```bash
cd web/backend && source .venv/bin/activate && uvicorn main:app --port 8765 &
cd web/frontend && npm run dev &
sleep 5
# Abrir manualmente http://localhost:3000/cliente/login e:
# 1. Logar com CNPJ semeado
# 2. Verificar que dashboard renderiza com KPIs e gráfico
```

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/cliente/dashboard/page.tsx
git commit -m "feat(cliente-fe): página /cliente/dashboard com KPIs, evolução e campanhas"
```

---

### Task 21: Playwright e2e dashboard

**Files:**
- Create: `web/frontend/tests/cliente-dashboard.spec.ts`

- [ ] **Step 1: Escrever testes**

```typescript
// web/frontend/tests/cliente-dashboard.spec.ts
import { test, expect } from "@playwright/test";

const CNPJ_SEED = "00000000000001"; // do seed_dev.py — corresponde ao cliente loja-fashion

async function login(page) {
  await page.goto("/cliente/login");
  await page.getByLabel("CNPJ").fill(CNPJ_SEED);
  await page.getByRole("button", { name: /entrar/i }).click();
  await page.waitForURL("**/cliente/dashboard");
}

test.describe("Cliente dashboard", () => {
  test("mostra nome e seção de KPIs após login", async ({ page }) => {
    await login(page);
    await expect(page.locator("h1")).toBeVisible();
    await expect(page.getByText(/KPIs/i)).toBeVisible();
  });

  test("seletor de mês muda o breakdown", async ({ page }) => {
    await login(page);
    const select = page.locator("select#mes");
    if (await select.isVisible()) {
      const options = await select.locator("option").allTextContents();
      if (options.length > 1) {
        await select.selectOption({ index: 1 });
        await expect(page.getByText(/campanhas/i)).toBeVisible();
      }
    }
  });

  test("botão Sair redireciona para login e limpa cookie", async ({ page, context }) => {
    await login(page);
    await page.getByRole("button", { name: /sair/i }).click();
    await page.waitForURL("**/cliente/login");
    const cookies = await context.cookies();
    expect(cookies.find((c) => c.name === "cliente_token")).toBeUndefined();
  });
});
```

- [ ] **Step 2: Rodar**

```bash
cd web/backend && source .venv/bin/activate && uvicorn main:app --port 8765 &
cd web/frontend && PORT=3010 npm run dev &
sleep 5
cd web/frontend && npx playwright test tests/cliente-dashboard.spec.ts
```

Expected: 3 PASS.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/tests/cliente-dashboard.spec.ts
git commit -m "test(cliente-fe): Playwright e2e dashboard"
```

---

## Pós-implementação

### Task 22: Verificação manual end-to-end

- [ ] **Step 1: Subir tudo e validar fluxo completo**

```bash
# Terminal 1
cd web/backend && source .venv/bin/activate && uvicorn main:app --port 8765

# Terminal 2
cd web/frontend && NEXT_PUBLIC_API_URL=http://localhost:8765 npm run dev
```

- [ ] **Step 2: Manual checklist**
  - Acessa `http://localhost:3000/cliente/login` — form aparece
  - Digita CNPJ inválido → vê mensagem de erro
  - Digita CNPJ válido (do seed) → redireciona para `/cliente/dashboard`
  - Dashboard mostra nome, KPIs do mês mais recente, gráfico, campanhas
  - Troca mês → breakdown atualiza
  - "Sair" → volta para `/cliente/login`, cookie limpo
  - Acessa `/cliente/dashboard` sem login → redireciona para `/cliente/login`

- [ ] **Step 3: Suite completa**

```bash
cd web/backend && source .venv/bin/activate && pytest -v
cd web/frontend && npx playwright test
```

Expected: tudo PASS.

---

## Notas

- **Postgres de teste:** Tasks 7–11 e 21 dependem de Postgres em `localhost:5432` com banco `vitrine_test`. Se não existir, criar antes:
  ```bash
  psql -d postgres -c "CREATE DATABASE vitrine_test OWNER vitrine;"
  ```
- **Seed `scripts/seed_dev.py`:** A Task 12 atualiza o seed para incluir CNPJ. Após cada execução do seed, o CNPJ `12345678000190` é o que os testes Playwright (Tasks 19 e 21) usam.
- **Em produção:** A migration da Task 1 é no-op (coluna `cnpj` já existe). O pipeline externo BigQuery → Postgres continua sendo responsável por popular a coluna.
- **Out of scope:** OTP, rate limit, multi-conta, geração de slides pelo cliente. Listados como não-objetivos na spec.
