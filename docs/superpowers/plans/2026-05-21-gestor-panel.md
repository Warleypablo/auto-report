# Painel de Gestores — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-service `/gestor/*` panel where internal team members log in with email + password, see only their assigned clients, and trigger Google Slides report generation with real-time status polling.

**Architecture:** New FastAPI routers (`/auth`, `/gestor`) + SQLAlchemy models (3 tables) + Alembic migration, all wired into the existing `web/backend/main.py`. Frontend adds Next.js pages under `app/gestor/` (all client components) that call Next.js API routes acting as a proxy; the proxy reads an httpOnly cookie and forwards requests to FastAPI with a Bearer token. Report generation delegates to the existing `core/` scripts and returns the Google Slides URL.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, python-jose[cryptography] (JWT), passlib[bcrypt] (passwords), Next.js 14 App Router (client components + API routes), TypeScript

---

## File Structure

**Backend — new files:**
- `web/backend/models/usuario.py` — `Usuario` SQLAlchemy model
- `web/backend/models/usuario_cliente.py` — `UsuarioCliente` association table
- `web/backend/models/report_job.py` — `ReportJob` model + `JobStatus` enum
- `web/backend/schemas/gestor.py` — Pydantic schemas for auth and gestor endpoints
- `web/backend/api/auth.py` — JWT encode/decode + `/auth/login`, `/auth/logout`, `/auth/me`
- `web/backend/api/gestor.py` — `/gestor/clientes`, `/gestor/reports/*`, `/gestor/admin/*`
- `web/backend/services/report_slides.py` — Wraps core generation, returns slides URL
- `web/backend/scripts/seed_admin.py` — One-time first-admin creation
- `web/backend/alembic/versions/<hash>_add_gestor_tables.py` — Migration

**Backend — modified files:**
- `web/backend/requirements.txt` — Add `python-jose[cryptography]`, `passlib[bcrypt]`
- `web/backend/app_settings.py` — Add `jwt_secret` field
- `web/backend/models/__init__.py` — Export new models
- `web/backend/main.py` — Register new routers, add lifespan stale-job cleanup

**Frontend — new files:**
- `web/frontend/middleware.ts` — Protect `/gestor/*` routes (except `/gestor/login`)
- `web/frontend/app/api/gestor/login/route.ts` — POST: forward to backend, set httpOnly cookie
- `web/frontend/app/api/gestor/logout/route.ts` — POST: clear cookie
- `web/frontend/app/api/gestor/[...path]/route.ts` — Catch-all proxy for all other gestor calls
- `web/frontend/lib/api-gestor.ts` — Client-side fetch helpers (call `/api/gestor/*`)
- `web/frontend/app/gestor/login/page.tsx` — Login form
- `web/frontend/app/gestor/page.tsx` — Dashboard: list assigned clients
- `web/frontend/app/gestor/[slug]/page.tsx` — Trigger report + poll status + history
- `web/frontend/app/gestor/admin/usuarios/page.tsx` — Admin: list + create users
- `web/frontend/app/gestor/admin/usuarios/[id]/page.tsx` — Admin: edit user, assign clients

---

## Task 1: Backend Dependencies + Settings

**Files:**
- Modify: `web/backend/requirements.txt`
- Modify: `web/backend/app_settings.py`
- Test: `web/backend/tests/test_auth.py` (just import test for now)

- [ ] **Step 1: Add packages to requirements.txt**

```text
# append to web/backend/requirements.txt
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
```

- [ ] **Step 2: Install packages**

```bash
cd /Users/mac0267/Documents/auto-report-main
web/backend/.venv/bin/pip install "python-jose[cryptography]>=3.3.0" "passlib[bcrypt]>=1.7.4"
```

Expected: `Successfully installed python-jose-... passlib-...`

- [ ] **Step 3: Add jwt_secret to app_settings.py**

Replace the `Settings` class in `web/backend/app_settings.py`:

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    etl_trigger_token: str = Field(default="dev-token-change-me")
    etl_threads: int = Field(default=10)
    etl_periodo_granularidade: str = Field(default="MENSAL")
    jwt_secret: str = Field(default="dev-jwt-secret-change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiry_hours: int = Field(default=8)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write failing import test**

Create `web/backend/tests/test_auth.py`:

```python
import pytest
from jose import jwt
from passlib.context import CryptContext


def test_jose_jwt_roundtrip():
    secret = "test-secret"
    payload = {"sub": "abc", "is_admin": False}
    token = jwt.encode(payload, secret, algorithm="HS256")
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    assert decoded["sub"] == "abc"
    assert decoded["is_admin"] is False


def test_passlib_bcrypt():
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = ctx.hash("mypassword")
    assert ctx.verify("mypassword", hashed)
    assert not ctx.verify("wrong", hashed)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/mac0267/Documents/auto-report-main
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add web/backend/requirements.txt web/backend/app_settings.py web/backend/tests/test_auth.py
git commit -m "feat(gestor): add JWT/bcrypt deps + jwt_secret setting"
```

---

## Task 2: DB Models

**Files:**
- Create: `web/backend/models/usuario.py`
- Create: `web/backend/models/usuario_cliente.py`
- Create: `web/backend/models/report_job.py`
- Modify: `web/backend/models/__init__.py`

- [ ] **Step 1: Create models/usuario.py**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    senha_hash: Mapped[str] = mapped_column(String, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    clientes: Mapped[list["UsuarioCliente"]] = relationship(
        "UsuarioCliente", back_populates="usuario", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ReportJob"]] = relationship(
        "ReportJob", back_populates="usuario", cascade="all, delete-orphan"
    )
```

- [ ] **Step 2: Create models/usuario_cliente.py**

```python
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class UsuarioCliente(Base):
    __tablename__ = "usuario_clientes"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="clientes")
    cliente: Mapped["Cliente"] = relationship("Cliente")
```

- [ ] **Step 3: Create models/report_job.py**

```python
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class ReportJob(Base):
    __tablename__ = "report_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mes: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), nullable=False, default=JobStatus.PENDING
    )
    slides_url: Mapped[str | None] = mapped_column(String, nullable=True)
    erro: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="jobs")
    cliente: Mapped["Cliente"] = relationship("Cliente")
```

- [ ] **Step 4: Update models/__init__.py**

```python
from .base import Base
from .cliente import Categoria, Cliente
from .report_job import JobStatus, ReportJob
from .snapshot import Frequencia, Snapshot
from .usuario import Usuario
from .usuario_cliente import UsuarioCliente

__all__ = [
    "Base",
    "Categoria",
    "Cliente",
    "Frequencia",
    "JobStatus",
    "ReportJob",
    "Snapshot",
    "Usuario",
    "UsuarioCliente",
]
```

- [ ] **Step 5: Write failing import test**

Add to `web/backend/tests/test_auth.py`:

```python
def test_models_import():
    from models import Usuario, UsuarioCliente, ReportJob, JobStatus
    assert JobStatus.PENDING == "pending"
    assert JobStatus.DONE == "done"
```

- [ ] **Step 6: Run test**

```bash
cd /Users/mac0267/Documents/auto-report-main
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py::test_models_import -v
```

Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
git add web/backend/models/usuario.py web/backend/models/usuario_cliente.py \
        web/backend/models/report_job.py web/backend/models/__init__.py \
        web/backend/tests/test_auth.py
git commit -m "feat(gestor): add Usuario, UsuarioCliente, ReportJob models"
```

---

## Task 3: Alembic Migration

**Files:**
- Create: `web/backend/alembic/versions/<hash>_add_gestor_tables.py`

- [ ] **Step 1: Generate migration**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend
.venv/bin/alembic revision --autogenerate -m "add_gestor_tables"
```

Expected: `Generating .../alembic/versions/<hash>_add_gestor_tables.py ... done`

- [ ] **Step 2: Review the generated migration**

Open the generated file and verify it creates:
- `usuarios` table with all fields including `is_admin`, `ativo`
- `usuario_clientes` table with composite PK
- `report_jobs` table with `job_status` enum

If the autogenerate missed anything, add it manually.

- [ ] **Step 3: Apply migration**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend
.venv/bin/alembic upgrade head
```

Expected: `Running upgrade <previous> -> <new>, add_gestor_tables`

- [ ] **Step 4: Verify tables exist**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend
.venv/bin/python -c "
from db import engine
from sqlalchemy import inspect
insp = inspect(engine)
tables = insp.get_table_names()
assert 'usuarios' in tables, f'Missing usuarios. Got: {tables}'
assert 'usuario_clientes' in tables
assert 'report_jobs' in tables
print('OK:', [t for t in tables if t in {'usuarios','usuario_clientes','report_jobs'}])
"
```

Expected: `OK: ['report_jobs', 'usuario_clientes', 'usuarios']`

- [ ] **Step 5: Commit**

```bash
git add web/backend/alembic/versions/
git commit -m "feat(gestor): migration — usuarios, usuario_clientes, report_jobs tables"
```

---

## Task 4: Gestor Pydantic Schemas

**Files:**
- Create: `web/backend/schemas/gestor.py`
- Modify: `web/backend/schemas/__init__.py`

- [ ] **Step 1: Create schemas/gestor.py**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    email: str
    senha: str


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nome: str
    is_admin: bool


class LoginResponse(BaseModel):
    token: str
    usuario: UsuarioResponse


class ClienteGestorItem(BaseModel):
    slug: str
    nome: str
    categoria: str


class ClientesGestorResponse(BaseModel):
    items: list[ClienteGestorItem]


class TriggerRequest(BaseModel):
    slug: str
    mes: str  # YYYY-MM


class TriggerResponse(BaseModel):
    job_id: uuid.UUID


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mes: str
    status: str
    slides_url: str | None
    erro: str | None
    created_at: datetime
    finished_at: datetime | None
    cliente_slug: str
    cliente_nome: str


class CreateUsuarioRequest(BaseModel):
    email: str
    nome: str
    senha: str
    is_admin: bool = False


class UsuarioListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nome: str
    is_admin: bool
    ativo: bool
    n_clientes: int = 0


class UsuariosListResponse(BaseModel):
    items: list[UsuarioListItem]


class AssignClientesRequest(BaseModel):
    cliente_ids: list[uuid.UUID]
```

- [ ] **Step 2: Update schemas/__init__.py**

```python
from .admin import (
    ClienteListItem,
    ClientesListResponse,
    PeriodoDisponivel,
    PeriodosResponse,
)
from .case import CaseDetail, CaseSummary
from .gestor import (
    AssignClientesRequest,
    ClienteGestorItem,
    ClientesGestorResponse,
    CreateUsuarioRequest,
    JobStatusResponse,
    LoginRequest,
    LoginResponse,
    TriggerRequest,
    TriggerResponse,
    UsuarioListItem,
    UsuarioResponse,
    UsuariosListResponse,
)
from .ranking import RankingItem, RankingsResponse

__all__ = [
    "AssignClientesRequest",
    "CaseDetail",
    "CaseSummary",
    "ClienteGestorItem",
    "ClienteListItem",
    "ClientesGestorResponse",
    "ClientesListResponse",
    "CreateUsuarioRequest",
    "JobStatusResponse",
    "LoginRequest",
    "LoginResponse",
    "PeriodoDisponivel",
    "PeriodosResponse",
    "RankingItem",
    "RankingsResponse",
    "TriggerRequest",
    "TriggerResponse",
    "UsuarioListItem",
    "UsuarioResponse",
    "UsuariosListResponse",
]
```

- [ ] **Step 3: Write failing import test**

Add to `web/backend/tests/test_auth.py`:

```python
def test_schemas_import():
    from schemas.gestor import LoginRequest, LoginResponse, JobStatusResponse
    req = LoginRequest(email="a@b.com", senha="pass")
    assert req.email == "a@b.com"
```

- [ ] **Step 4: Run test**

```bash
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py::test_schemas_import -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add web/backend/schemas/gestor.py web/backend/schemas/__init__.py web/backend/tests/test_auth.py
git commit -m "feat(gestor): add Pydantic schemas for auth and gestor endpoints"
```

---

## Task 5: JWT Auth Utilities + Auth Endpoints

**Files:**
- Create: `web/backend/api/auth.py`
- Modify: `web/backend/tests/test_auth.py`

- [ ] **Step 1: Write failing tests for JWT utils**

Add to `web/backend/tests/test_auth.py`:

```python
import uuid
from datetime import datetime, timezone


def test_create_access_token_contains_sub():
    from api.auth import create_access_token
    uid = uuid.uuid4()
    token = create_access_token(uid, is_admin=False, secret="s", algorithm="HS256", expiry_hours=1)
    from jose import jwt
    payload = jwt.decode(token, "s", algorithms=["HS256"])
    assert payload["sub"] == str(uid)
    assert payload["is_admin"] is False


def test_decode_token_returns_payload():
    from api.auth import create_access_token, decode_token
    uid = uuid.uuid4()
    token = create_access_token(uid, is_admin=True, secret="s", algorithm="HS256", expiry_hours=1)
    payload = decode_token(token, secret="s", algorithm="HS256")
    assert payload["sub"] == str(uid)
    assert payload["is_admin"] is True


def test_decode_expired_token_raises():
    from api.auth import create_access_token, decode_token
    from jose import JWTError
    uid = uuid.uuid4()
    token = create_access_token(uid, is_admin=False, secret="s", algorithm="HS256", expiry_hours=0)
    with pytest.raises(JWTError):
        decode_token(token, secret="s", algorithm="HS256")
```

- [ ] **Step 2: Run tests to see them fail**

```bash
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py -k "create_access_token or decode_token" -v
```

Expected: `3 failed` (ImportError or similar)

- [ ] **Step 3: Create api/auth.py**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_settings import Settings, get_settings
from db import get_session
from models import Usuario
from schemas import LoginRequest, LoginResponse, UsuarioResponse

router = APIRouter()

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Pure utility functions (also tested directly) ──────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(
    user_id: uuid.UUID,
    *,
    is_admin: bool,
    secret: str,
    algorithm: str,
    expiry_hours: int,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    payload = {"sub": str(user_id), "is_admin": is_admin, "exp": expire}
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, *, secret: str, algorithm: str) -> dict:
    """Raises JWTError on invalid or expired token."""
    return jwt.decode(token, secret, algorithms=[algorithm])


# ── FastAPI dependency ─────────────────────────────────────────────────────

def get_current_user(
    authorization: str = Cookie(default="", alias="Authorization"),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> Usuario:
    """Extracts Bearer token from Authorization header, validates, returns user."""
    raise HTTPException(status_code=401, detail="Não autenticado")


def require_auth(
    authorization: str | None = None,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> Usuario:
    """Dependency: validates Bearer token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    uid = uuid.UUID(payload["sub"])
    user = session.get(Usuario, uid)
    if user is None or not user.ativo:
        raise HTTPException(status_code=401, detail="Usuário inativo ou inexistente")
    return user


def require_admin(user: Usuario = Depends(require_auth)) -> Usuario:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> LoginResponse:
    user = session.execute(
        select(Usuario).where(Usuario.email == body.email, Usuario.ativo == True)  # noqa: E712
    ).scalar_one_or_none()
    if user is None or not verify_password(body.senha, user.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")
    token = create_access_token(
        user.id,
        is_admin=user.is_admin,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expiry_hours=settings.jwt_expiry_hours,
    )
    return LoginResponse(
        token=token,
        usuario=UsuarioResponse(id=user.id, email=user.email, nome=user.nome, is_admin=user.is_admin),
    )


@router.post("/auth/logout")
def logout() -> dict:
    return {"ok": True}


@router.get("/auth/me", response_model=UsuarioResponse)
def me(user: Usuario = Depends(require_auth)) -> UsuarioResponse:
    return UsuarioResponse(id=user.id, email=user.email, nome=user.nome, is_admin=user.is_admin)
```

**Note on `require_auth`:** The frontend (Next.js API routes) reads the `gestor_token` cookie and forwards requests to FastAPI with `Authorization: Bearer <token>` header. FastAPI reads the `Authorization` header — not a cookie — so there are no cross-origin cookie issues.

- [ ] **Step 4: Run tests**

```bash
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py -v
```

Expected: all pass (6+ tests)

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/auth.py web/backend/tests/test_auth.py
git commit -m "feat(gestor): JWT auth utilities and /auth/* endpoints"
```

---

## Task 6: Report Slides Service

**Files:**
- Create: `web/backend/services/report_slides.py`
- Modify: `web/backend/tests/test_auth.py` (import smoke test)

> **Context:** `core/report_generator.py::processar_cliente()` runs the full generation pipeline but returns `None`. This service replicates the same steps and returns the Google Slides URL. We use `leitura_central.fetch_clientes(atualizar=False, only=nome)` so any assigned client can be generated regardless of the `GERAR?` column in the Central Sheet.

- [ ] **Step 1: Write failing smoke test**

Add to `web/backend/tests/test_auth.py`:

```python
def test_report_slides_import():
    from services.report_slides import gerar_slides
    import inspect
    sig = inspect.signature(gerar_slides)
    assert "slug" in sig.parameters
    assert "nome_cliente" in sig.parameters
    assert "mes" in sig.parameters
```

- [ ] **Step 2: Create services/__init__.py**

```python
```

(empty file)

- [ ] **Step 3: Create services/report_slides.py**

```python
"""Wraps core report generation and returns the Google Slides URL.

Called in a background thread by the gestor API. Replicates the steps of
report_generator.processar_cliente() but captures and returns presentation_id
instead of discarding it.
"""
from __future__ import annotations

import calendar
import sys
from datetime import date
from pathlib import Path

# Ensure project root (auto-report-main/) is on sys.path for core imports
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def gerar_slides(slug: str, nome_cliente: str, mes: str) -> str:
    """Generate Google Slides report for one client and return the Drive URL.

    Args:
        slug: DB slug (used only for error messages here)
        nome_cliente: Client name as it appears in the Central Sheet
        mes: Reference month in YYYY-MM format

    Returns:
        Full URL to the created Google Slides presentation

    Raises:
        ValueError: if client is not found in the Central Sheet
        Exception: propagated from core (API errors, Drive errors, etc.)
    """
    from config import settings as core_settings  # type: ignore
    from core import (  # type: ignore
        basic_placeholders,
        periodo as periodo_mod,
        slide_filler,
        template_manager,
    )
    from core.categorias import get_handler  # type: ignore
    from core.leitura_central import fetch_clientes  # type: ignore
    from core.status import set_status  # type: ignore

    # Convert "YYYY-MM" to a `today` in the NEXT month so periodo_referencia
    # returns the correct month. Example: mes="2026-04" → today=2026-05-15
    ano, mes_num = int(mes[:4]), int(mes[5:7])
    proximo = mes_num + 1
    ano_alvo = ano + (1 if proximo > 12 else 0)
    proximo = 1 if proximo > 12 else proximo
    today = date(ano_alvo, proximo, 15)

    clientes = fetch_clientes(
        atualizar=False,
        only=nome_cliente,
        sheet_url=core_settings.CENTRAL_SHEET_URL,
        tab_name=core_settings.CENTRAL_TAB_NAME,
    )
    if not clientes:
        raise ValueError(
            f"Cliente '{nome_cliente}' (slug={slug!r}) não encontrado na Planilha Central"
        )

    cliente = clientes[0]
    FREQ = "MENSAL"

    periodo_ref = periodo_mod.periodo_referencia(today=today, frequencia=FREQ)
    periodo_comp = periodo_mod.periodo_referencia(today=periodo_ref.inicio, frequencia=FREQ)

    dados = basic_placeholders.montar_placeholders_basicos(cliente, periodo_ref, FREQ=FREQ)
    dados.update(
        basic_placeholders.montar_placeholders_basicos(cliente, periodo_comp, FREQ=FREQ, sufixo="_comp")
    )

    handler = get_handler(cliente.categoria)
    dados.update(handler.coletar_dados(cliente, periodo_ref, periodo_comp))

    presentation_id = template_manager.criar_copia(
        cliente, periodo_ref, template_id=handler.template_id, FREQ=FREQ
    )
    slide_filler.preencher(presentation_id, dados, handler._SLIDES.meta_ads)
    handler.pos_processar(presentation_id, dados)
    set_status(cliente, "GERADO ✅")

    return f"https://docs.google.com/presentation/d/{presentation_id}/edit"
```

- [ ] **Step 4: Run import test**

```bash
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py::test_report_slides_import -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add web/backend/services/__init__.py web/backend/services/report_slides.py \
        web/backend/tests/test_auth.py
git commit -m "feat(gestor): report_slides service wrapping core generation"
```

---

## Task 7: Gestor API — Clientes + Reports

**Files:**
- Create: `web/backend/api/gestor.py` (first section)
- Modify: `web/backend/tests/test_auth.py`

- [ ] **Step 1: Write failing endpoint tests**

Add to `web/backend/tests/test_auth.py`:

```python
def test_gestor_router_mounts():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.gestor import router as gestor_router
    from api.auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(gestor_router, prefix="/gestor")

    client = TestClient(app)
    # No auth → 401
    r = client.get("/gestor/clientes")
    assert r.status_code == 401

    r = client.post("/gestor/reports/trigger", json={"slug": "x", "mes": "2026-04"})
    assert r.status_code == 401
```

- [ ] **Step 2: Create api/gestor.py (clientes + reports section)**

```python
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session, selectinload

from api.auth import require_admin, require_auth
from db import get_session
from models import Cliente, ReportJob, Usuario, UsuarioCliente
from models.report_job import JobStatus
from schemas import (
    AssignClientesRequest,
    ClienteGestorItem,
    ClientesGestorResponse,
    CreateUsuarioRequest,
    JobStatusResponse,
    TriggerRequest,
    TriggerResponse,
    UsuarioListItem,
    UsuarioResponse,
    UsuariosListResponse,
)

router = APIRouter()

_MES_RE = __import__("re").compile(r"^\d{4}-\d{2}$")

# ── Helpers ────────────────────────────────────────────────────────────────

def _job_to_response(job: ReportJob) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        mes=job.mes,
        status=job.status.value,
        slides_url=job.slides_url,
        erro=job.erro,
        created_at=job.created_at,
        finished_at=job.finished_at,
        cliente_slug=job.cliente.slug,
        cliente_nome=job.cliente.nome,
    )


def _mark_stale_running_jobs(session: Session) -> None:
    """Mark jobs stuck in 'running' for more than 10 minutes as error."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    session.execute(
        update(ReportJob)
        .where(ReportJob.status == JobStatus.RUNNING, ReportJob.created_at < cutoff)
        .values(
            status=JobStatus.ERROR,
            erro="Timeout: job ficou em running por mais de 10 minutos",
            finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.commit()


# ── GET /gestor/clientes ───────────────────────────────────────────────────

@router.get("/clientes", response_model=ClientesGestorResponse)
def list_clientes(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClientesGestorResponse:
    stmt = (
        select(Cliente)
        .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
        .where(UsuarioCliente.usuario_id == user.id)
        .order_by(Cliente.nome.asc())
    )
    clientes = session.execute(stmt).scalars().all()
    return ClientesGestorResponse(
        items=[
            ClienteGestorItem(slug=c.slug, nome=c.nome, categoria=c.categoria.value)
            for c in clientes
        ]
    )


# ── POST /gestor/reports/trigger ───────────────────────────────────────────

@router.post("/reports/trigger", response_model=TriggerResponse)
def trigger_report(
    body: TriggerRequest,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> TriggerResponse:
    if not _MES_RE.match(body.mes):
        raise HTTPException(status_code=400, detail="mes deve ser YYYY-MM")

    # Verify user has access to this client
    cliente = session.execute(
        select(Cliente)
        .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
        .where(
            Cliente.slug == body.slug,
            UsuarioCliente.usuario_id == user.id,
        )
    ).scalar_one_or_none()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado ou sem acesso")

    # Mark any stale running jobs before checking for duplicates
    _mark_stale_running_jobs(session)

    # Prevent duplicate running job for same client
    running = session.execute(
        select(ReportJob).where(
            ReportJob.cliente_id == cliente.id,
            ReportJob.status == JobStatus.RUNNING,
        )
    ).scalar_one_or_none()
    if running is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Já existe um job em andamento para este cliente (job_id={running.id})",
        )

    job = ReportJob(
        usuario_id=user.id,
        cliente_id=cliente.id,
        mes=body.mes,
        status=JobStatus.PENDING,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    job_id = job.id
    cliente_slug = cliente.slug
    cliente_nome = cliente.nome

    def _run():
        from db import SessionLocal
        from services.report_slides import gerar_slides

        with SessionLocal() as bg_session:
            bg_job = bg_session.get(ReportJob, job_id)
            if bg_job is None:
                return
            bg_job.status = JobStatus.RUNNING
            bg_session.commit()

        try:
            url = gerar_slides(slug=cliente_slug, nome_cliente=cliente_nome, mes=body.mes)
            with SessionLocal() as bg_session:
                bg_job = bg_session.get(ReportJob, job_id)
                if bg_job:
                    bg_job.status = JobStatus.DONE
                    bg_job.slides_url = url
                    bg_job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    bg_session.commit()
        except Exception as exc:
            with SessionLocal() as bg_session:
                bg_job = bg_session.get(ReportJob, job_id)
                if bg_job:
                    bg_job.status = JobStatus.ERROR
                    bg_job.erro = str(exc)[:500]
                    bg_job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    bg_session.commit()

    threading.Thread(target=_run, daemon=True).start()
    return TriggerResponse(job_id=job.id)


# ── GET /gestor/reports/{job_id} ───────────────────────────────────────────

@router.get("/reports/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: uuid.UUID,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> JobStatusResponse:
    job = session.execute(
        select(ReportJob)
        .options(selectinload(ReportJob.cliente))
        .where(ReportJob.id == job_id, ReportJob.usuario_id == user.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return _job_to_response(job)


# ── GET /gestor/reports ────────────────────────────────────────────────────

@router.get("/reports", response_model=list[JobStatusResponse])
def list_jobs(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
    slug: str | None = Query(default=None),
) -> list[JobStatusResponse]:
    stmt = (
        select(ReportJob)
        .options(selectinload(ReportJob.cliente))
        .where(ReportJob.usuario_id == user.id)
        .order_by(ReportJob.created_at.desc())
        .limit(50)
    )
    if slug:
        stmt = stmt.join(Cliente, Cliente.id == ReportJob.cliente_id).where(Cliente.slug == slug)
    jobs = session.execute(stmt).scalars().all()
    return [_job_to_response(j) for j in jobs]
```

- [ ] **Step 3: Run endpoint test**

```bash
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py::test_gestor_router_mounts -v
```

Expected: `1 passed`

- [ ] **Step 4: Commit**

```bash
git add web/backend/api/gestor.py web/backend/tests/test_auth.py
git commit -m "feat(gestor): gestor router — clientes + reports endpoints"
```

---

## Task 8: Gestor API — Admin Section

**Files:**
- Modify: `web/backend/api/gestor.py` (append admin section)

- [ ] **Step 1: Write failing admin test**

Add to `web/backend/tests/test_auth.py`:

```python
def test_admin_routes_require_admin():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.gestor import router as gestor_router
    from api.auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(gestor_router, prefix="/gestor")

    client = TestClient(app)
    r = client.get("/gestor/admin/usuarios")
    assert r.status_code == 401  # no auth at all
```

- [ ] **Step 2: Append admin endpoints to api/gestor.py**

Add these functions after the `list_jobs` function:

```python
# ── Admin: GET /gestor/admin/usuarios ─────────────────────────────────────

@router.get("/admin/usuarios", response_model=UsuariosListResponse)
def admin_list_usuarios(
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UsuariosListResponse:
    stmt = (
        select(
            Usuario,
            func.count(UsuarioCliente.cliente_id).label("n_clientes"),
        )
        .outerjoin(UsuarioCliente, UsuarioCliente.usuario_id == Usuario.id)
        .group_by(Usuario.id)
        .order_by(Usuario.nome.asc())
    )
    rows = session.execute(stmt).all()
    return UsuariosListResponse(
        items=[
            UsuarioListItem(
                id=u.id,
                email=u.email,
                nome=u.nome,
                is_admin=u.is_admin,
                ativo=u.ativo,
                n_clientes=n,
            )
            for u, n in rows
        ]
    )


# ── Admin: POST /gestor/admin/usuarios ────────────────────────────────────

@router.post("/admin/usuarios", response_model=UsuarioResponse, status_code=201)
def admin_create_usuario(
    body: CreateUsuarioRequest,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UsuarioResponse:
    from api.auth import hash_password
    from sqlalchemy import select as sa_select

    existing = session.execute(
        sa_select(Usuario).where(Usuario.email == body.email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    user = Usuario(
        email=body.email,
        nome=body.nome,
        senha_hash=hash_password(body.senha),
        is_admin=body.is_admin,
        ativo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UsuarioResponse(id=user.id, email=user.email, nome=user.nome, is_admin=user.is_admin)


# ── Admin: DELETE /gestor/admin/usuarios/{id} (deactivate) ────────────────

@router.delete("/admin/usuarios/{usuario_id}", status_code=204)
def admin_deactivate_usuario(
    usuario_id: uuid.UUID,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    user = session.get(Usuario, usuario_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    user.ativo = False
    session.commit()


# ── Admin: GET /gestor/admin/usuarios/{id}/clientes ───────────────────────

@router.get("/admin/usuarios/{usuario_id}/clientes", response_model=ClientesGestorResponse)
def admin_get_usuario_clientes(
    usuario_id: uuid.UUID,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ClientesGestorResponse:
    stmt = (
        select(Cliente)
        .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
        .where(UsuarioCliente.usuario_id == usuario_id)
        .order_by(Cliente.nome.asc())
    )
    clientes = session.execute(stmt).scalars().all()
    return ClientesGestorResponse(
        items=[ClienteGestorItem(slug=c.slug, nome=c.nome, categoria=c.categoria.value) for c in clientes]
    )


# ── Admin: POST /gestor/admin/usuarios/{id}/clientes ──────────────────────

@router.post("/admin/usuarios/{usuario_id}/clientes", status_code=204)
def admin_assign_clientes(
    usuario_id: uuid.UUID,
    body: AssignClientesRequest,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    user = session.get(Usuario, usuario_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    existing = {
        uc.cliente_id
        for uc in session.execute(
            select(UsuarioCliente).where(UsuarioCliente.usuario_id == usuario_id)
        ).scalars().all()
    }

    for cid in body.cliente_ids:
        if cid not in existing:
            session.add(UsuarioCliente(usuario_id=usuario_id, cliente_id=cid))

    session.commit()


# ── Admin: DELETE /gestor/admin/usuarios/{id}/clientes/{cliente_id} ───────

@router.delete("/admin/usuarios/{usuario_id}/clientes/{cliente_id}", status_code=204)
def admin_remove_cliente(
    usuario_id: uuid.UUID,
    cliente_id: uuid.UUID,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    uc = session.execute(
        select(UsuarioCliente).where(
            UsuarioCliente.usuario_id == usuario_id,
            UsuarioCliente.cliente_id == cliente_id,
        )
    ).scalar_one_or_none()
    if uc:
        session.delete(uc)
        session.commit()
```

- [ ] **Step 3: Run all tests**

```bash
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py -v
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add web/backend/api/gestor.py web/backend/tests/test_auth.py
git commit -m "feat(gestor): admin endpoints — user CRUD + client assignment"
```

---

## Task 9: Wire Routers + Stale Job Cleanup on Startup

**Files:**
- Modify: `web/backend/main.py`

- [ ] **Step 1: Update main.py**

Replace the full contents of `web/backend/main.py`:

```python
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import cases, health, internal, rankings
from api.auth import router as auth_router
from api.gestor import router as gestor_router
from app_settings import get_settings
from logging_config import setup_logging


def _cleanup_stale_jobs() -> None:
    """On startup: mark jobs stuck in 'running' for >10 min as error."""
    try:
        from db import SessionLocal
        from models import ReportJob
        from models.report_job import JobStatus
        from sqlalchemy import update

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        with SessionLocal() as session:
            session.execute(
                update(ReportJob)
                .where(ReportJob.status == JobStatus.RUNNING, ReportJob.created_at < cutoff)
                .values(
                    status=JobStatus.ERROR,
                    erro="Timeout detectado no startup — job estava em running há mais de 10 min",
                    finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            session.commit()
    except Exception:
        pass  # Don't fail startup because of this


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _cleanup_stale_jobs()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vitrine de Cases API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    app.include_router(rankings.router, prefix="/api")
    app.include_router(internal.router, prefix="/internal")
    app.include_router(auth_router)
    app.include_router(gestor_router, prefix="/gestor")
    return app


app = create_app()
```

- [ ] **Step 2: Test server starts**

```bash
cd /Users/mac0267/Documents/auto-report-main
web/backend/.venv/bin/uvicorn --app-dir web/backend main:app --port 8765 --host 127.0.0.1 &
sleep 2
curl -s http://localhost:8765/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('status')=='ok' else d)"
curl -s -X POST http://localhost:8765/auth/login -H "content-type: application/json" -d '{"email":"x","senha":"x"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('Got 401 or user field:', 'detail' in d or 'token' in d)"
kill %1
```

Expected: `OK` then `Got 401 or user field: True`

- [ ] **Step 3: Commit**

```bash
git add web/backend/main.py
git commit -m "feat(gestor): wire auth + gestor routers, stale job cleanup on startup"
```

---

## Task 10: seed_admin.py Script

**Files:**
- Create: `web/backend/scripts/seed_admin.py`

- [ ] **Step 1: Create the script**

```python
"""One-time script: creates the first admin user.

Usage (run from project root):
    python web/backend/scripts/seed_admin.py --email admin@agencia.com --nome "Admin" --senha "changeme"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.auth import hash_password
from db import SessionLocal
from models import Usuario
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria o primeiro admin do painel de gestores")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nome", required=True)
    parser.add_argument("--senha", required=True)
    args = parser.parse_args()

    with SessionLocal() as session:
        existing = session.execute(select(Usuario).where(Usuario.email == args.email)).scalar_one_or_none()
        if existing:
            print(f"Usuário {args.email!r} já existe (id={existing.id})")
            sys.exit(0)

        user = Usuario(
            email=args.email,
            nome=args.nome,
            senha_hash=hash_password(args.senha),
            is_admin=True,
            ativo=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"Admin criado: id={user.id} email={user.email}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the script (dry run)**

```bash
cd /Users/mac0267/Documents/auto-report-main
web/backend/.venv/bin/python web/backend/scripts/seed_admin.py \
    --email "admin@agencia.com" --nome "Admin" --senha "changeme123"
```

Expected: `Admin criado: id=<uuid> email=admin@agencia.com`

Run again to confirm idempotency:
```bash
web/backend/.venv/bin/python web/backend/scripts/seed_admin.py \
    --email "admin@agencia.com" --nome "Admin" --senha "changeme123"
```

Expected: `Usuário 'admin@agencia.com' já existe (id=<uuid>)`

- [ ] **Step 3: Commit**

```bash
git add web/backend/scripts/seed_admin.py
git commit -m "feat(gestor): seed_admin.py script for first admin creation"
```

---

## Task 11: Next.js API Routes (Login, Logout, Catch-All Proxy)

**Files:**
- Create: `web/frontend/app/api/gestor/login/route.ts`
- Create: `web/frontend/app/api/gestor/logout/route.ts`
- Create: `web/frontend/app/api/gestor/[...path]/route.ts`

> **How auth flows:** Login route calls FastAPI `/auth/login`, gets `{token, usuario}`, sets `gestor_token` as httpOnly cookie on the Next.js domain (same origin as pages), then returns user info. All subsequent API calls go through the catch-all proxy, which reads the cookie and forwards as `Authorization: Bearer <token>` to FastAPI.

- [ ] **Step 1: Create app/api/gestor/login/route.ts**

```typescript
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const BACKEND = process.env.INTERNAL_API_URL ?? "http://localhost:8765";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body?.email || !body?.senha) {
    return NextResponse.json({ error: "email e senha obrigatórios" }, { status: 400 });
  }

  const backendRes = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await backendRes.json().catch(() => ({}));

  if (!backendRes.ok) {
    return NextResponse.json(data, { status: backendRes.status });
  }

  const response = NextResponse.json({ usuario: data.usuario });
  response.cookies.set("gestor_token", data.token, {
    httpOnly: true,
    path: "/",
    maxAge: 8 * 60 * 60,
    sameSite: "lax",
  });
  return response;
}
```

- [ ] **Step 2: Create app/api/gestor/logout/route.ts**

```typescript
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set("gestor_token", "", {
    httpOnly: true,
    path: "/",
    maxAge: 0,
  });
  return response;
}
```

- [ ] **Step 3: Create app/api/gestor/[...path]/route.ts**

```typescript
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const BACKEND = process.env.INTERNAL_API_URL ?? "http://localhost:8765";

function backendUrl(segments: string[], search: string): string {
  const path = segments.join("/");
  // /api/gestor/me → /auth/me
  if (path === "me") return `${BACKEND}/auth/me${search}`;
  // /api/gestor/clientes, /api/gestor/reports/*, /api/gestor/admin/* → /gestor/...
  return `${BACKEND}/gestor/${path}${search}`;
}

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const token = req.cookies.get("gestor_token")?.value ?? "";
  const search = req.nextUrl.search ?? "";
  const url = backendUrl(path, search);

  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (token) headers["authorization"] = `Bearer ${token}`;

  let body: string | undefined;
  if (req.method !== "GET" && req.method !== "DELETE") {
    body = await req.text().catch(() => undefined);
  }

  const backendRes = await fetch(url, {
    method: req.method,
    headers,
    body,
  });

  const contentType = backendRes.headers.get("content-type") ?? "";
  if (backendRes.status === 204 || !contentType.includes("application/json")) {
    return new NextResponse(null, { status: backendRes.status });
  }

  const data = await backendRes.json().catch(() => ({}));
  return NextResponse.json(data, { status: backendRes.status });
}

export { handler as GET, handler as POST, handler as DELETE };
```

- [ ] **Step 4: Test login route manually (after restarting backend)**

```bash
# Start backend in background
cd /Users/mac0267/Documents/auto-report-main
web/backend/.venv/bin/uvicorn --app-dir web/backend main:app --port 8765 --host 127.0.0.1 &
sleep 2

# Test login with bad credentials (should get 401)
curl -s -X POST http://localhost:3000/api/gestor/login \
  -H "content-type: application/json" \
  -d '{"email":"bad@test.com","senha":"bad"}' | python3 -m json.tool

kill %1
```

Expected: `{"detail": "Email ou senha inválidos"}` (forwarded from backend)

- [ ] **Step 5: Commit**

```bash
git add web/frontend/app/api/gestor/
git commit -m "feat(gestor): Next.js API routes — login, logout, catch-all proxy"
```

---

## Task 12: Frontend Middleware

**Files:**
- Create: `web/frontend/middleware.ts`

- [ ] **Step 1: Create middleware.ts**

```typescript
import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const token = req.cookies.get("gestor_token")?.value;
  if (!token) {
    const loginUrl = req.nextUrl.clone();
    loginUrl.pathname = "/gestor/login";
    loginUrl.search = "";
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/gestor/:path*"],
  // Exclude /gestor/login from protection
  // Next.js evaluates the matcher: add negative lookahead via regex
};
```

- [ ] **Step 2: Update middleware to exclude /gestor/login**

The `matcher` above matches ALL `/gestor/*` including `/gestor/login`. Fix it by checking the pathname inside the function:

```typescript
import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Allow login page through without auth check
  if (pathname === "/gestor/login") {
    return NextResponse.next();
  }

  const token = req.cookies.get("gestor_token")?.value;
  if (!token) {
    const loginUrl = req.nextUrl.clone();
    loginUrl.pathname = "/gestor/login";
    loginUrl.search = "";
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/gestor/:path*"],
};
```

- [ ] **Step 3: Commit**

```bash
git add web/frontend/middleware.ts
git commit -m "feat(gestor): Next.js middleware to protect /gestor/* routes"
```

---

## Task 13: Client-Side API Helpers

**Files:**
- Create: `web/frontend/lib/api-gestor.ts`

- [ ] **Step 1: Create lib/api-gestor.ts**

```typescript
export type UsuarioInfo = {
  id: string;
  email: string;
  nome: string;
  is_admin: boolean;
};

export type ClienteGestor = {
  slug: string;
  nome: string;
  categoria: string;
};

export type JobStatus = "pending" | "running" | "done" | "error";

export type JobInfo = {
  id: string;
  mes: string;
  status: JobStatus;
  slides_url: string | null;
  erro: string | null;
  created_at: string;
  finished_at: string | null;
  cliente_slug: string;
  cliente_nome: string;
};

export type UsuarioListItem = {
  id: string;
  email: string;
  nome: string;
  is_admin: boolean;
  ativo: boolean;
  n_clientes: number;
};

async function apiCall<T>(
  path: string,
  method: string = "GET",
  body?: object,
): Promise<T> {
  const res = await fetch(`/api/gestor/${path}`, {
    method,
    headers: { "content-type": "application/json" },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (res.status === 204) return undefined as unknown as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail ?? `Erro ${res.status}`);
  }
  return data as T;
}

export const gestorApi = {
  login: (email: string, senha: string) =>
    apiCall<{ usuario: UsuarioInfo }>("login", "POST", { email, senha }),

  logout: () => apiCall<void>("logout", "POST"),

  me: () => apiCall<UsuarioInfo>("me"),

  clientes: () =>
    apiCall<{ items: ClienteGestor[] }>("clientes"),

  triggerReport: (slug: string, mes: string) =>
    apiCall<{ job_id: string }>("reports/trigger", "POST", { slug, mes }),

  getJob: (job_id: string) =>
    apiCall<JobInfo>(`reports/${job_id}`),

  listJobs: (slug?: string) =>
    apiCall<JobInfo[]>(`reports${slug ? `?slug=${slug}` : ""}`),

  // Admin
  listUsuarios: () =>
    apiCall<{ items: UsuarioListItem[] }>("admin/usuarios"),

  createUsuario: (data: { email: string; nome: string; senha: string; is_admin: boolean }) =>
    apiCall<UsuarioInfo>("admin/usuarios", "POST", data),

  deactivateUsuario: (id: string) =>
    apiCall<void>(`admin/usuarios/${id}`, "DELETE"),

  getUsuarioClientes: (id: string) =>
    apiCall<{ items: ClienteGestor[] }>(`admin/usuarios/${id}/clientes`),

  assignClientes: (id: string, cliente_ids: string[]) =>
    apiCall<void>(`admin/usuarios/${id}/clientes`, "POST", { cliente_ids }),

  removeClienteFromUsuario: (usuario_id: string, cliente_id: string) =>
    apiCall<void>(`admin/usuarios/${usuario_id}/clientes/${cliente_id}`, "DELETE"),
};
```

- [ ] **Step 2: Commit**

```bash
git add web/frontend/lib/api-gestor.ts
git commit -m "feat(gestor): client-side API helpers"
```

---

## Task 14: Login Page

**Files:**
- Create: `web/frontend/app/gestor/login/page.tsx`

- [ ] **Step 1: Create app/gestor/login/page.tsx**

```tsx
"use client";

import { useState, FormEvent } from "react";
import { gestorApi } from "@/lib/api-gestor";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setLoading(true);
    try {
      await gestorApi.login(email, senha);
      window.location.href = "/gestor";
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao entrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="font-display text-2xl font-medium tracking-tight text-[var(--ink)]">
            CASES
          </p>
          <p className="eyebrow mt-1 text-xs text-[var(--muted)]">Painel de Gestores</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="email"
            placeholder="email@agencia.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-2.5 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          />
          <input
            type="password"
            placeholder="••••••••"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
            className="w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-2.5 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          />

          {erro && (
            <p className="text-xs text-[var(--crimson)]">{erro}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className={[
              "w-full rounded-md border py-2.5 text-xs uppercase tracking-[0.18em] transition",
              loading
                ? "cursor-wait border-[var(--rule-soft)] text-[var(--muted)]"
                : "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest)] hover:text-[var(--paper)]",
            ].join(" ")}
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/frontend/app/gestor/login/page.tsx
git commit -m "feat(gestor): login page"
```

---

## Task 15: Dashboard Page

**Files:**
- Create: `web/frontend/app/gestor/page.tsx`

- [ ] **Step 1: Create app/gestor/page.tsx**

```tsx
"use client";

import { useEffect, useState } from "react";
import { gestorApi, ClienteGestor, UsuarioInfo } from "@/lib/api-gestor";
import Link from "next/link";

export default function GestorDashboard() {
  const [user, setUser] = useState<UsuarioInfo | null>(null);
  const [clientes, setClientes] = useState<ClienteGestor[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([gestorApi.me(), gestorApi.clientes()])
      .then(([u, c]) => {
        setUser(u);
        setClientes(c.items);
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleLogout() {
    await gestorApi.logout();
    window.location.href = "/gestor/login";
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <header className="mb-10 flex items-center justify-between">
        <div>
          <p className="text-xs text-[var(--muted)]">Olá, {user?.nome ?? "—"}</p>
          {user?.is_admin && (
            <Link
              href="/gestor/admin/usuarios"
              className="mt-1 block text-xs text-[var(--forest)] underline underline-offset-2"
            >
              Administração →
            </Link>
          )}
        </div>
        <button
          onClick={handleLogout}
          className="text-xs text-[var(--muted)] hover:text-[var(--ink)] transition"
        >
          Sair
        </button>
      </header>

      <h1 className="font-display mb-6 text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
        Seus clientes
      </h1>

      {erro && <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>}

      {clientes.length === 0 && !erro && (
        <p className="text-sm text-[var(--muted)]">
          Nenhum cliente atribuído. Peça ao administrador para configurar seu acesso.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {clientes.map((c) => (
          <li key={c.slug}>
            <Link
              href={`/gestor/${c.slug}`}
              className="flex items-center justify-between rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3 transition hover:border-[var(--forest)] hover:bg-[var(--paper-deep)]"
            >
              <div>
                <p className="text-sm font-medium text-[var(--ink)]">{c.nome}</p>
                <p className="text-xs text-[var(--muted)]">{c.categoria}</p>
              </div>
              <span className="text-xs text-[var(--forest)]">Gerar report →</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/frontend/app/gestor/page.tsx
git commit -m "feat(gestor): dashboard page listing assigned clients"
```

---

## Task 16: Client Report Page (with Polling)

**Files:**
- Create: `web/frontend/app/gestor/[slug]/page.tsx`

- [ ] **Step 1: Create app/gestor/[slug]/page.tsx**

```tsx
"use client";

import { useEffect, useState, useRef, use } from "react";
import Link from "next/link";
import { gestorApi, JobInfo, ClienteGestor } from "@/lib/api-gestor";
import { mesUltimoFechado, deslocarMes } from "@/lib/mes-utils";

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}

export default function ClienteReportPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const [cliente, setCliente] = useState<ClienteGestor | null>(null);
  const [mes, setMes] = useState(mesUltimoFechado());
  const [activeJob, setActiveJob] = useState<JobInfo | null>(null);
  const [history, setHistory] = useState<JobInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    Promise.all([gestorApi.clientes(), gestorApi.listJobs(slug)])
      .then(([{ items }, jobs]) => {
        const c = items.find((i) => i.slug === slug) ?? null;
        if (!c) setErro("Cliente não encontrado ou sem acesso");
        setCliente(c);
        setHistory(jobs);
        const running = jobs.find((j) => j.status === "running" || j.status === "pending");
        if (running) startPolling(running.id);
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));

    return () => stopPolling();
  }, [slug]);

  function startPolling(jobId: string) {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const job = await gestorApi.getJob(jobId);
        setActiveJob(job);
        if (job.status === "done" || job.status === "error") {
          stopPolling();
          setHistory((prev) => {
            const idx = prev.findIndex((j) => j.id === jobId);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = job;
              return next;
            }
            return [job, ...prev];
          });
        }
      } catch {
        stopPolling();
      }
    }, 2000);
  }

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function handleTrigger() {
    setErro(null);
    setTriggering(true);
    try {
      const { job_id } = await gestorApi.triggerReport(slug, mes);
      const initialJob: JobInfo = {
        id: job_id,
        mes,
        status: "pending",
        slides_url: null,
        erro: null,
        created_at: new Date().toISOString(),
        finished_at: null,
        cliente_slug: slug,
        cliente_nome: cliente?.nome ?? slug,
      };
      setActiveJob(initialJob);
      setHistory((prev) => [initialJob, ...prev]);
      startPolling(job_id);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao disparar report");
    } finally {
      setTriggering(false);
    }
  }

  const isRunning =
    activeJob?.status === "running" || activeJob?.status === "pending";

  const mesesDisponiveis = Array.from({ length: 12 }, (_, i) =>
    deslocarMes(mesUltimoFechado(), -i),
  );

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-xl px-6 py-16">
      <Link
        href="/gestor"
        className="mb-8 block text-xs text-[var(--muted)] hover:text-[var(--ink)] transition"
      >
        ← Seus clientes
      </Link>

      <h1 className="font-display mb-8 text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
        {cliente?.nome ?? slug}
      </h1>

      {/* Month selector */}
      <div className="mb-4">
        <p className="eyebrow mb-2 text-xs text-[var(--muted)]">Mês de referência</p>
        <select
          value={mes}
          onChange={(e) => setMes(e.target.value)}
          disabled={isRunning}
          className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
        >
          {mesesDisponiveis.map((m) => (
            <option key={m} value={m}>
              {mesLabel(m)}
            </option>
          ))}
        </select>
      </div>

      {/* Trigger button */}
      <button
        onClick={handleTrigger}
        disabled={isRunning || triggering}
        className={[
          "mb-6 w-full rounded-md border py-3 text-xs uppercase tracking-[0.18em] transition",
          isRunning || triggering
            ? "cursor-wait border-[var(--rule-soft)] text-[var(--muted)]"
            : "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest)] hover:text-[var(--paper)]",
        ].join(" ")}
      >
        {triggering ? "Disparando…" : isRunning ? "Gerando slides…" : "▶ Gerar report"}
      </button>

      {/* Active job status */}
      {activeJob && (
        <div className="mb-8 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
          {activeJob.status === "running" || activeJob.status === "pending" ? (
            <div className="flex items-center gap-3">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--rule-soft)] border-t-[var(--forest)]" />
              <div>
                <p className="text-sm text-[var(--ink)]">Gerando slides…</p>
                <p className="text-xs text-[var(--muted)]">Pode levar 1–2 minutos</p>
              </div>
            </div>
          ) : activeJob.status === "done" ? (
            <div>
              <p className="mb-2 text-sm font-medium text-[var(--forest)]">Report gerado!</p>
              <a
                href={activeJob.slides_url ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-[var(--forest)] underline underline-offset-2"
              >
                → Abrir slides
              </a>
            </div>
          ) : (
            <p className="text-sm text-[var(--crimson)]">
              Erro: {activeJob.erro ?? "Falha desconhecida"}
            </p>
          )}
        </div>
      )}

      {erro && <p className="mb-6 text-sm text-[var(--crimson)]">{erro}</p>}

      {/* History */}
      {history.filter((j) => j.status === "done" || j.status === "error").length > 0 && (
        <div>
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Reports anteriores</p>
          <ul className="flex flex-col gap-px border-t border-[var(--rule-soft)]">
            {history
              .filter((j) => j.status === "done" || j.status === "error")
              .map((j) => (
                <li
                  key={j.id}
                  className="flex items-center justify-between border-b border-[var(--rule-soft)] py-3"
                >
                  <span className="text-xs text-[var(--ink-soft)]">{mesLabel(j.mes)}</span>
                  {j.status === "done" && j.slides_url ? (
                    <a
                      href={j.slides_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-[var(--forest)] underline underline-offset-2"
                    >
                      → Abrir slides
                    </a>
                  ) : (
                    <span className="text-xs text-[var(--crimson)]">Erro</span>
                  )}
                </li>
              ))}
          </ul>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/frontend/app/gestor/[slug]/page.tsx
git commit -m "feat(gestor): client report page with 2s polling"
```

---

## Task 17: Admin — User List Page

**Files:**
- Create: `web/frontend/app/gestor/admin/usuarios/page.tsx`

- [ ] **Step 1: Create app/gestor/admin/usuarios/page.tsx**

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { gestorApi, UsuarioListItem } from "@/lib/api-gestor";

export default function AdminUsuariosPage() {
  const [usuarios, setUsuarios] = useState<UsuarioListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ email: "", nome: "", senha: "", is_admin: false });
  const [criando, setCriando] = useState(false);
  const [formErro, setFormErro] = useState<string | null>(null);

  function load() {
    setLoading(true);
    gestorApi
      .listUsuarios()
      .then(({ items }) => setUsuarios(items))
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormErro(null);
    setCriando(true);
    try {
      await gestorApi.createUsuario(form);
      setShowForm(false);
      setForm({ email: "", nome: "", senha: "", is_admin: false });
      load();
    } catch (err) {
      setFormErro(err instanceof Error ? err.message : "Erro ao criar");
    } finally {
      setCriando(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <Link href="/gestor" className="mb-8 block text-xs text-[var(--muted)] hover:text-[var(--ink)] transition">
        ← Dashboard
      </Link>

      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-3xl font-medium tracking-tight text-[var(--ink)]">
          Gestores
        </h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-full border border-[var(--forest)] px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)]"
        >
          {showForm ? "Cancelar" : "+ Novo gestor"}
        </button>
      </div>

      {erro && <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-8 flex flex-col gap-3 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4"
        >
          <p className="eyebrow text-xs text-[var(--muted)]">Novo gestor</p>
          {(["email", "nome", "senha"] as const).map((field) => (
            <input
              key={field}
              type={field === "senha" ? "password" : field === "email" ? "email" : "text"}
              placeholder={field}
              value={form[field]}
              onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.value }))}
              required
              className="w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
            />
          ))}
          <label className="flex items-center gap-2 text-sm text-[var(--ink-soft)]">
            <input
              type="checkbox"
              checked={form.is_admin}
              onChange={(e) => setForm((f) => ({ ...f, is_admin: e.target.checked }))}
            />
            Administrador
          </label>
          {formErro && <p className="text-xs text-[var(--crimson)]">{formErro}</p>}
          <button
            type="submit"
            disabled={criando}
            className="w-full rounded-md border border-[var(--forest)] py-2 text-xs uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:opacity-50"
          >
            {criando ? "Criando…" : "Criar"}
          </button>
        </form>
      )}

      <ul className="flex flex-col gap-2">
        {usuarios.map((u) => (
          <li key={u.id}>
            <Link
              href={`/gestor/admin/usuarios/${u.id}`}
              className="flex items-center justify-between rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3 transition hover:border-[var(--forest)]"
            >
              <div>
                <p className="text-sm font-medium text-[var(--ink)]">
                  {u.nome}
                  {u.is_admin && (
                    <span className="ml-2 text-xs text-[var(--amber)]">admin</span>
                  )}
                  {!u.ativo && (
                    <span className="ml-2 text-xs text-[var(--muted)]">(inativo)</span>
                  )}
                </p>
                <p className="text-xs text-[var(--muted)]">
                  {u.email} · {u.n_clientes} cliente{u.n_clientes !== 1 ? "s" : ""}
                </p>
              </div>
              <span className="text-xs text-[var(--muted)]">Editar →</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/frontend/app/gestor/admin/usuarios/page.tsx
git commit -m "feat(gestor): admin user list page with create form"
```

---

## Task 18: Admin — User Edit Page

**Files:**
- Create: `web/frontend/app/gestor/admin/usuarios/[id]/page.tsx`

**Pre-condition — apply these schema fixes FIRST (before writing the page):**

The admin edit page needs client UUIDs to call the assign endpoint. Fix three files:

1. **`web/backend/schemas/gestor.py`** — add `id: uuid.UUID` to `ClienteGestorItem`:

```python
class ClienteGestorItem(BaseModel):
    id: uuid.UUID
    slug: str
    nome: str
    categoria: str
```

2. **`web/backend/api/gestor.py`** — update every `ClienteGestorItem(...)` call to include `id=c.id`:

```python
# In list_clientes and admin_get_usuario_clientes — both use the same pattern:
ClienteGestorItem(id=c.id, slug=c.slug, nome=c.nome, categoria=c.categoria.value)
```

3. **`web/frontend/lib/api-gestor.ts`** — add `id: string` to `ClienteGestor` type:

```typescript
export type ClienteGestor = {
  id: string;
  slug: string;
  nome: string;
  categoria: string;
};
```

- [ ] **Step 1: Apply schema fixes to schemas/gestor.py, api/gestor.py, and lib/api-gestor.ts**

Verify the change doesn't break existing tests:

```bash
web/backend/.venv/bin/pytest web/backend/tests/test_auth.py -v
```

Expected: all pass

- [ ] **Step 2: Create app/gestor/admin/usuarios/[id]/page.tsx**

```tsx
"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { gestorApi, ClienteGestor } from "@/lib/api-gestor";

export default function EditUsuarioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [todosClientes, setTodosClientes] = useState<ClienteGestor[]>([]);
  const [atribuidos, setAtribuidos] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);
  const [busca, setBusca] = useState("");

  useEffect(() => {
    Promise.all([gestorApi.clientes(), gestorApi.getUsuarioClientes(id)])
      .then(([todos, assigned]) => {
        setTodosClientes(todos.items);
        setAtribuidos(new Set(assigned.items.map((c) => c.slug)));
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleSave() {
    setSalvando(true);
    setErro(null);
    setSucesso(false);
    try {
      // 1. Add newly assigned clients
      const clienteIds = todosClientes
        .filter((c) => atribuidos.has(c.slug))
        .map((c) => c.id);
      if (clienteIds.length > 0) {
        await gestorApi.assignClientes(id, clienteIds);
      }
      // 2. Remove unassigned clients
      const atual = await gestorApi.getUsuarioClientes(id);
      for (const c of atual.items) {
        if (!atribuidos.has(c.slug)) {
          await gestorApi.removeClienteFromUsuario(id, c.id);
        }
      }
      setSucesso(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  const filtered = todosClientes.filter(
    (c) =>
      c.nome.toLowerCase().includes(busca.toLowerCase()) ||
      c.slug.toLowerCase().includes(busca.toLowerCase()),
  );

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <Link
        href="/gestor/admin/usuarios"
        className="mb-8 block text-xs text-[var(--muted)] hover:text-[var(--ink)] transition"
      >
        ← Gestores
      </Link>

      <h1 className="font-display mb-2 text-3xl font-medium tracking-tight text-[var(--ink)]">
        Editar gestor
      </h1>
      <p className="mb-8 text-sm text-[var(--muted)]">ID: {id}</p>

      {erro && <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>}
      {sucesso && (
        <p className="mb-4 text-sm text-[var(--forest)]">Atribuições salvas!</p>
      )}

      <div className="mb-8">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Atribuir clientes</p>
        <input
          type="text"
          placeholder="Buscar cliente…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="mb-3 w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
        />

        <ul className="max-h-80 overflow-y-auto flex flex-col gap-1">
          {filtered.map((c) => {
            const checked = atribuidos.has(c.slug);
            return (
              <li key={c.slug}>
                <label className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 transition hover:bg-[var(--paper-soft)]">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() =>
                      setAtribuidos((prev) => {
                        const next = new Set(prev);
                        if (checked) next.delete(c.slug);
                        else next.add(c.slug);
                        return next;
                      })
                    }
                    className="h-4 w-4 accent-[var(--forest)]"
                  />
                  <div>
                    <p className="text-sm text-[var(--ink)]">{c.nome}</p>
                    <p className="text-xs text-[var(--muted)]">{c.categoria}</p>
                  </div>
                </label>
              </li>
            );
          })}
        </ul>

        <button
          onClick={handleSave}
          disabled={salvando}
          className={[
            "mt-3 w-full rounded-md border py-2.5 text-xs uppercase tracking-[0.18em] transition",
            salvando
              ? "cursor-wait border-[var(--rule-soft)] text-[var(--muted)]"
              : "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest)] hover:text-[var(--paper)]",
          ].join(" ")}
        >
          {salvando ? "Salvando…" : "Salvar atribuições"}
        </button>
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/frontend/app/gestor/admin/usuarios/[id]/page.tsx \
        web/backend/schemas/gestor.py \
        web/backend/api/gestor.py \
        web/frontend/lib/api-gestor.ts
git commit -m "feat(gestor): admin user edit page with client assignment"
```

---

## Testing the Full Flow

After all tasks are complete, test end-to-end:

- [ ] **Start backend**

```bash
cd /Users/mac0267/Documents/auto-report-main
web/backend/.venv/bin/uvicorn --app-dir web/backend main:app --port 8765 --host 127.0.0.1
```

- [ ] **Create first admin** (if not done in Task 10)

```bash
web/backend/.venv/bin/python web/backend/scripts/seed_admin.py \
    --email "admin@agencia.com" --nome "Admin" --senha "changeme123"
```

- [ ] **Start frontend**

```bash
cd web/frontend && npm run dev
```

- [ ] **Verify in browser:**
  1. Navigate to `http://localhost:3000/gestor` → should redirect to `/gestor/login`
  2. Login with admin credentials → should land on dashboard
  3. Go to `/gestor/admin/usuarios` → should show admin interface
  4. Create a new gestor user
  5. Assign a client to the new gestor
  6. Login as the new gestor → dashboard shows only assigned clients
  7. Click a client → trigger report → watch spinner → see result

- [ ] **Run backend tests**

```bash
cd /Users/mac0267/Documents/auto-report-main
web/backend/.venv/bin/pytest web/backend/tests/ -v
```

Expected: all pre-existing tests pass + new auth/gestor tests pass
