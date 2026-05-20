# Vitrine pública de cases — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir uma vitrine pública de cases (web app) que reaproveita os gathers do `auto-report-main` (Meta Ads, Google Ads, GA4, Painel) para mostrar ROI, ROAS e melhores resultados de clientes, com snapshot diário em Postgres.

**Architecture:** ETL Python diário consome `core.categorias.get_handler(...).coletar_dados(...)`, parseia strings PT-BR para numéricos, grava snapshots em Postgres. FastAPI expõe API pública de leitura. Next.js (App Router + ISR) renderiza o site público.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, psycopg, Postgres 15, Node 20, Next.js 14 (App Router), TypeScript, TailwindCSS, shadcn/ui, Recharts, pytest, Vitest, Playwright, Docker.

---

## Spec de referência

`docs/superpowers/specs/2026-05-20-vitrine-cases-design.md`

Leia o spec antes de começar. Este plano detalha a implementação; o spec contém o "porquê" das decisões.

---

## Mapa de arquivos

### Backend (`web/backend/`)

| Arquivo | Responsabilidade |
|---------|------------------|
| `main.py` | FastAPI app: monta rotas, CORS, lifespan, OpenAPI |
| `config.py` | Carrega env vars (DATABASE_URL, ETL_*, CORS_ORIGINS), valida via Pydantic |
| `db.py` | SQLAlchemy engine, sessionmaker, dependency `get_session()` |
| `models/__init__.py` | Exporta todos os modelos |
| `models/base.py` | `DeclarativeBase` comum |
| `models/cliente.py` | Modelo `Cliente` |
| `models/snapshot.py` | Modelo `Snapshot` |
| `schemas/__init__.py` | Pydantic schemas (DTOs) |
| `schemas/case.py` | `CaseListItem`, `CaseDetail`, `MetricasPorFonte`, `PontoEvolucao` |
| `schemas/ranking.py` | `RankingItem` |
| `api/__init__.py` | Agrega routers |
| `api/health.py` | `/api/health` |
| `api/cases.py` | `/api/cases`, `/api/cases/{slug}` |
| `api/rankings.py` | `/api/rankings/{tipo}` |
| `api/internal.py` | `/internal/etl/trigger` (auth por token) |
| `services/case_builder.py` | Monta DTO público a partir do snapshot |
| `services/rankings.py` | Calcula rankings (top ROAS, etc.) |
| `etl/__init__.py` | |
| `etl/transform.py` | `parse_pt_br`: strings PT-BR → numéricos |
| `etl/collect.py` | `run_etl`, `processar_cliente`, `upsert_snapshot` |
| `etl/lock.py` | Lock distribuído via `pg_try_advisory_lock` |
| `etl/schedule.py` | Entrypoint CLI do cron (`python -m etl.schedule`) |
| `alembic.ini`, `alembic/env.py`, `alembic/versions/*.py` | Migrations |
| `tests/conftest.py` | Fixtures (Postgres efêmero, async client) |
| `tests/test_transform.py` | Testes do `parse_pt_br` |
| `tests/test_collect.py` | Testes do ETL (gathers mockados) |
| `tests/test_api_cases.py` | Testes da API |
| `tests/test_lock.py` | Testes do lock |
| `Dockerfile` | Imagem do backend |
| `requirements.txt` | Dependências Python |
| `pyproject.toml` | Config pytest, black, ruff |

### Frontend (`web/frontend/`)

| Arquivo | Responsabilidade |
|---------|------------------|
| `app/page.tsx` | Home: grid de cards |
| `app/cases/[slug]/page.tsx` | Detalhe do case |
| `app/layout.tsx` | Layout global (header, footer, tema) |
| `app/api/openapi/route.ts` | Proxy do OpenAPI (opcional) |
| `components/CaseCard.tsx` | Card de case (logo, nome, métrica destaque) |
| `components/CaseDetailHeader.tsx` | Header com logo, nome, descrição |
| `components/MetricGrid.tsx` | Grid de métricas principais |
| `components/EvolutionChart.tsx` | Gráfico de evolução (Recharts) |
| `components/FontDetail.tsx` | Detalhe por fonte (Meta/Google/GA4) |
| `components/Filters.tsx` | Filtros (categoria, setor) |
| `lib/api.ts` | Fetch wrapper tipado |
| `lib/types.ts` | Tipos TS gerados do OpenAPI |
| `lib/format.ts` | Formatadores PT-BR (R$, %, x) |
| `public/logos/*` | Logos dos clientes |
| `tailwind.config.ts` | Config Tailwind |
| `Dockerfile` | Imagem do frontend |
| `package.json`, `tsconfig.json`, `next.config.mjs` | Configs |
| `tests/CaseCard.test.tsx`, etc. | Testes Vitest |
| `tests/e2e/golden.spec.ts` | E2E Playwright |

### Infra

| Arquivo | Responsabilidade |
|---------|------------------|
| `web/docker-compose.yml` | Dev: postgres + backend + frontend |
| `web/.env.example` | Template das env vars |
| `.github/workflows/ci.yml` | CI (lint, test, build) |

### Alterações no `core/` existente

| Arquivo | Mudança |
|---------|---------|
| `core/leitura_central.py` | Adicionar suporte às novas colunas `PUBLICAR_VITRINE`, `DESCRICAO_PUBLICA`, `LOGO_URL`, `SETOR_PUBLICO`, `PORTE_PUBLICO` |

Nenhum outro arquivo de `core/` é alterado.

---

## Fases

- **Fase 0** — Setup do projeto (estrutura, Docker, skeletons)
- **Fase 1** — Camada de dados (SQLAlchemy, Alembic, modelos)
- **Fase 2** — Parser PT-BR (TDD intensivo)
- **Fase 3** — Backend API (endpoints públicos)
- **Fase 4** — ETL (reuso do core/, lock, trigger)
- **Fase 5** — Frontend Next.js (componentes, páginas, ISR)
- **Fase 6** — Testes E2E e observabilidade
- **Fase 7** — Deploy (Dockerfiles, CI, cron de prod)

---

## Fase 0 — Setup do projeto

### Task 0.1: Criar estrutura de pastas

**Files:**
- Create: `web/`, `web/backend/`, `web/frontend/`, `web/backend/api/`, `web/backend/models/`, `web/backend/schemas/`, `web/backend/services/`, `web/backend/etl/`, `web/backend/alembic/`, `web/backend/alembic/versions/`, `web/backend/tests/`

- [ ] **Step 1: Criar diretórios**

```bash
cd /Users/mac0267/Documents/auto-report-main
mkdir -p web/backend/{api,models,schemas,services,etl,alembic/versions,tests}
mkdir -p web/frontend
touch web/backend/{api,models,schemas,services,etl,tests}/__init__.py
touch web/backend/__init__.py
```

- [ ] **Step 2: Commit**

```bash
git add web/
git commit -m "chore(web): create initial directory structure"
```

---

### Task 0.2: requirements.txt do backend

**Files:**
- Create: `web/backend/requirements.txt`

- [ ] **Step 1: Escrever requirements.txt**

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
sqlalchemy==2.0.36
alembic==1.14.0
psycopg[binary]==3.2.3
pydantic==2.10.3
pydantic-settings==2.7.0
python-multipart==0.0.18
httpx==0.28.1
structlog==24.4.0

# Test
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-postgresql==6.1.1
respx==0.21.1
```

- [ ] **Step 2: Verificar instalação local**

```bash
cd web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: instalação sem erros.

- [ ] **Step 3: Commit**

```bash
git add web/backend/requirements.txt
git commit -m "chore(backend): pin Python dependencies"
```

---

### Task 0.3: Skeleton FastAPI + health check

**Files:**
- Create: `web/backend/config.py`
- Create: `web/backend/main.py`
- Create: `web/backend/api/health.py`

- [ ] **Step 1: Criar `config.py`**

```python
# web/backend/config.py
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Criar `api/health.py`**

```python
# web/backend/api/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 3: Criar `main.py`**

```python
# web/backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import health
from .config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vitrine de Cases API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    return app


app = create_app()
```

- [ ] **Step 4: Subir e testar**

```bash
cd web/backend
uvicorn main:app --reload
# em outro terminal:
curl http://localhost:8000/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add web/backend/{config,main}.py web/backend/api/health.py
git commit -m "feat(backend): scaffold FastAPI app with health check"
```

---

### Task 0.4: docker-compose.yml para dev

**Files:**
- Create: `web/docker-compose.yml`
- Create: `web/.env.example`
- Create: `web/backend/Dockerfile`

- [ ] **Step 1: Criar `web/.env.example`**

```
DATABASE_URL=postgresql+psycopg://vitrine:vitrine@postgres:5432/vitrine
CORS_ORIGINS=["http://localhost:3000"]
ETL_TRIGGER_TOKEN=dev-token-change-me
ETL_THREADS=10
ETL_PERIODO_GRANULARIDADE=MENSAL
```

- [ ] **Step 2: Criar `web/backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# instala deps do projeto
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copia código do backend + core/ do auto-report (importado pelo ETL)
COPY . /app/web/backend
COPY ../../core /app/core
COPY ../../utils /app/utils
COPY ../../config /app/config

ENV PYTHONPATH=/app

WORKDIR /app/web/backend
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> NOTA: O `COPY ../../core` não funciona no Docker tradicional. O `docker-compose.yml` precisa setar `build.context: ../` para enxergar a raiz do projeto. Veja próximo step.

- [ ] **Step 3: Criar `web/docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: vitrine
      POSTGRES_PASSWORD: vitrine
      POSTGRES_DB: vitrine
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vitrine"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ..                              # raiz do auto-report-main
      dockerfile: web/backend/Dockerfile
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg://vitrine:vitrine@postgres:5432/vitrine
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ..:/app:cached                          # hot reload em dev

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    env_file: .env
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next

volumes:
  pg_data:
```

- [ ] **Step 4: Atualizar `Dockerfile` para usar context da raiz**

```dockerfile
# web/backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# context é a raiz do auto-report-main
COPY web/backend/requirements.txt /app/web/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/web/backend/requirements.txt

# código do backend
COPY web/backend /app/web/backend

# código do auto-report reutilizado pelo ETL
COPY core /app/core
COPY utils /app/utils
COPY config /app/config

ENV PYTHONPATH=/app

WORKDIR /app/web/backend
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 5: Subir docker-compose e testar**

```bash
cd web
cp .env.example .env
docker compose up -d postgres backend
sleep 5
curl http://localhost:8000/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit**

```bash
git add web/docker-compose.yml web/.env.example web/backend/Dockerfile
git commit -m "chore(web): add docker-compose for local dev"
```

---

### Task 0.5: Atualizar .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Adicionar entradas ao .gitignore**

```
# web
web/.env
web/backend/.venv/
web/backend/__pycache__/
web/backend/**/__pycache__/
web/backend/.pytest_cache/
web/frontend/node_modules/
web/frontend/.next/
web/frontend/out/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore web/ artifacts"
```

---

## Fase 1 — Camada de dados (SQLAlchemy + Alembic)

### Task 1.1: Configurar SQLAlchemy (engine, session)

**Files:**
- Create: `web/backend/db.py`
- Create: `web/backend/models/base.py`

- [ ] **Step 1: Criar `models/base.py`**

```python
# web/backend/models/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Criar `db.py`**

```python
# web/backend/db.py
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 3: Commit**

```bash
git add web/backend/db.py web/backend/models/base.py
git commit -m "feat(backend): add SQLAlchemy engine and session"
```

---

### Task 1.2: Modelo `Cliente`

**Files:**
- Create: `web/backend/models/cliente.py`
- Modify: `web/backend/models/__init__.py`

- [ ] **Step 1: Criar `models/cliente.py`**

```python
# web/backend/models/cliente.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Categoria(str, enum.Enum):
    ECOMMERCE = "E-commerce"
    LEAD_COM_SITE = "Lead Com Site"
    LEAD_SEM_SITE = "Lead Sem Site"


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    categoria: Mapped[Categoria] = mapped_column(Enum(Categoria, name="categoria"), nullable=False)
    setor: Mapped[str | None] = mapped_column(String, nullable=True)
    porte: Mapped[str | None] = mapped_column(String, nullable=True)
    descricao_publica: Mapped[str | None] = mapped_column(String, nullable=True)
    publicar_vitrine: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    destaque: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list["Snapshot"]] = relationship(
        "Snapshot", back_populates="cliente", cascade="all, delete-orphan"
    )
```

- [ ] **Step 2: Atualizar `models/__init__.py`**

```python
# web/backend/models/__init__.py
from .base import Base
from .cliente import Categoria, Cliente
from .snapshot import Snapshot

__all__ = ["Base", "Categoria", "Cliente", "Snapshot"]
```

> NOTA: `Snapshot` ainda não existe — será criado na Task 1.3. O import vai falhar até lá. Isso é OK porque vamos commitar `cliente.py` separadamente do `__init__.py`.

- [ ] **Step 3: Commit (sem `__init__.py` ainda)**

```bash
git add web/backend/models/cliente.py
git commit -m "feat(backend): add Cliente model"
```

---

### Task 1.3: Modelo `Snapshot`

**Files:**
- Create: `web/backend/models/snapshot.py`
- Modify: `web/backend/models/__init__.py`

- [ ] **Step 1: Criar `models/snapshot.py`**

```python
# web/backend/models/snapshot.py
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Frequencia(str, enum.Enum):
    SEMANAL = "SEMANAL"
    MENSAL = "MENSAL"


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        UniqueConstraint("cliente_id", "periodo_inicio", "periodo_fim", name="uq_snapshot_periodo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    frequencia: Mapped[Frequencia] = mapped_column(Enum(Frequencia, name="frequencia"), nullable=False)
    data_coleta: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Métricas de destaque (denormalizadas)
    faturamento: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    investimento: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    roas: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    cpa: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    leads: Mapped[int | None] = mapped_column(nullable=True)
    vendas: Mapped[int | None] = mapped_column(nullable=True)

    # Variações vs período anterior
    faturamento_var_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    roas_var_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Detalhes por fonte
    metricas_detalhadas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_dados: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="snapshots")
```

- [ ] **Step 2: Confirmar que `__init__.py` (da Task 1.2 step 2) agora resolve**

```bash
cd web/backend
python -c "from models import Cliente, Snapshot; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add web/backend/models/snapshot.py web/backend/models/__init__.py
git commit -m "feat(backend): add Snapshot model"
```

---

### Task 1.4: Configurar Alembic

**Files:**
- Create: `web/backend/alembic.ini`
- Create: `web/backend/alembic/env.py`
- Create: `web/backend/alembic/script.py.mako`

- [ ] **Step 1: Inicializar Alembic**

```bash
cd web/backend
alembic init -t async alembic
```

(Edita `alembic.ini` para apontar `script_location = alembic` e remover `sqlalchemy.url` (vai vir do env).)

- [ ] **Step 2: Sobrescrever `alembic/env.py`**

```python
# web/backend/alembic/env.py
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import get_settings
from models import Base

config = context.config
fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Gerar primeira migration**

```bash
cd web/backend
alembic revision --autogenerate -m "init: clientes e snapshots"
```

Expected: arquivo em `alembic/versions/<rev>_init_clientes_e_snapshots.py` com `create_table('clientes')` e `create_table('snapshots')`.

- [ ] **Step 4: Aplicar migration**

```bash
alembic upgrade head
```

Expected: sem erros. `psql vitrine -c "\dt"` mostra `clientes`, `snapshots`, `alembic_version`.

- [ ] **Step 5: Commit**

```bash
git add web/backend/alembic.ini web/backend/alembic/
git commit -m "feat(backend): setup Alembic with initial migration"
```

---

### Task 1.5: Criar view `cases_view`

**Files:**
- Create: `web/backend/alembic/versions/<rev>_cases_view.py`

- [ ] **Step 1: Gerar migration vazia**

```bash
cd web/backend
alembic revision -m "view: cases_view"
```

- [ ] **Step 2: Editar migration gerada**

```python
"""view: cases_view

Revision ID: <gerado>
Revises: <init>
Create Date: ...
"""
from alembic import op


revision = "<gerado>"
down_revision = "<init>"
branch_labels = None
depends_on = None


CREATE_VIEW = """
CREATE OR REPLACE VIEW cases_view AS
WITH ultimo_snapshot AS (
    SELECT DISTINCT ON (cliente_id)
        cliente_id,
        id AS snapshot_id,
        periodo_inicio,
        periodo_fim,
        frequencia,
        data_coleta,
        faturamento,
        investimento,
        roas,
        cpa,
        leads,
        vendas,
        faturamento_var_pct,
        roas_var_pct,
        metricas_detalhadas
    FROM snapshots
    ORDER BY cliente_id, periodo_fim DESC, data_coleta DESC
)
SELECT
    c.id            AS cliente_id,
    c.slug,
    c.nome,
    c.logo_url,
    c.categoria,
    c.setor,
    c.porte,
    c.descricao_publica,
    c.destaque,
    s.snapshot_id,
    s.periodo_inicio,
    s.periodo_fim,
    s.frequencia,
    s.data_coleta,
    s.faturamento,
    s.investimento,
    s.roas,
    s.cpa,
    s.leads,
    s.vendas,
    s.faturamento_var_pct,
    s.roas_var_pct,
    s.metricas_detalhadas
FROM clientes c
JOIN ultimo_snapshot s ON s.cliente_id = c.id
WHERE c.publicar_vitrine = TRUE;
"""

DROP_VIEW = "DROP VIEW IF EXISTS cases_view;"


def upgrade() -> None:
    op.execute(CREATE_VIEW)


def downgrade() -> None:
    op.execute(DROP_VIEW)
```

- [ ] **Step 3: Aplicar e validar**

```bash
alembic upgrade head
psql vitrine -c "SELECT * FROM cases_view LIMIT 1;"
```

Expected: query executa sem erros (retorna 0 linhas).

- [ ] **Step 4: Commit**

```bash
git add web/backend/alembic/versions/
git commit -m "feat(backend): add cases_view"
```

---

### Task 1.6: Seeds para dev

**Files:**
- Create: `web/backend/scripts/seed_dev.py`

- [ ] **Step 1: Criar script de seed**

```python
# web/backend/scripts/seed_dev.py
"""Popula DB com clientes e snapshots fictícios para dev local."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import SessionLocal
from models import Categoria, Cliente, Snapshot
from models.snapshot import Frequencia


CLIENTES = [
    dict(
        slug="loja-fashion",
        nome="Loja Fashion BR",
        logo_url="/logos/loja-fashion.svg",
        categoria=Categoria.ECOMMERCE,
        setor="Moda",
        porte="Médio",
        descricao_publica="E-commerce de moda feminina que cresceu 230% em 12 meses.",
        publicar_vitrine=True,
        destaque=True,
    ),
    dict(
        slug="dental-care",
        nome="Dental Care+",
        logo_url="/logos/dental-care.svg",
        categoria=Categoria.LEAD_COM_SITE,
        setor="Saúde",
        porte="Pequeno",
        descricao_publica="Clínica odontológica que reduziu CPL em 60%.",
        publicar_vitrine=True,
        destaque=False,
    ),
]


def main() -> None:
    with SessionLocal() as session:
        for data in CLIENTES:
            cliente = Cliente(**data)
            session.add(cliente)
            session.flush()

            hoje = date.today()
            for i in range(6):
                periodo_fim = (hoje.replace(day=1) - timedelta(days=1 * 30 * i))
                periodo_inicio = periodo_fim.replace(day=1)
                snap = Snapshot(
                    cliente_id=cliente.id,
                    periodo_inicio=periodo_inicio,
                    periodo_fim=periodo_fim,
                    frequencia=Frequencia.MENSAL,
                    faturamento=Decimal("100000") * (i + 1),
                    investimento=Decimal("15000"),
                    roas=Decimal("6.5") + Decimal(i) * Decimal("0.3"),
                    cpa=Decimal("85.50"),
                    leads=200 + 20 * i,
                    vendas=50 + 5 * i,
                    faturamento_var_pct=Decimal("12.5"),
                    roas_var_pct=Decimal("4.8"),
                    metricas_detalhadas={"meta": {"roas": 7.0}, "google": {"roas": 8.2}},
                    raw_dados={},
                )
                session.add(snap)
        session.commit()
        print(f"Seeded {len(CLIENTES)} clientes")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar seed**

```bash
cd web/backend
python scripts/seed_dev.py
psql vitrine -c "SELECT slug, nome FROM clientes;"
```

Expected: 2 linhas (`loja-fashion`, `dental-care`).

- [ ] **Step 3: Commit**

```bash
mkdir -p web/backend/scripts
git add web/backend/scripts/seed_dev.py
git commit -m "feat(backend): add dev seed script"
```

---

## Fase 2 — Parser PT-BR (TDD)

Esta fase é crítica: os gathers do `core/categorias/` retornam dict com **strings já formatadas em PT-BR**. O ETL precisa reverter esses formatos para `Decimal`/`int` antes de gravar no DB. Erros aqui silenciosamente corrompem todos os snapshots.

### Formatos a suportar

| Formato | Exemplo | Tipo destino |
|---------|---------|--------------|
| Moeda BRL | `"R$ 12.345,67"`, `"R$ 1.234.567,89"` | `Decimal` |
| Percentual | `"+12,5%"`, `"-3,7%"`, `"12,5%"` | `Decimal` (sem `%`, sinal preservado) |
| Multiplicador | `"8,5x"`, `"12x"` | `Decimal` |
| Inteiro PT-BR | `"1.234"`, `"567"` | `int` |
| Decimal puro | `"12,34"`, `"0,5"` | `Decimal` |
| Vazio/nulo | `""`, `"-"`, `"N/A"`, `None` | `None` |
| Já numérico | `12.5`, `1000`, `Decimal(...)` | preservado |

### Task 2.1: Testes do parser (RED)

**Files:**
- Create: `web/backend/tests/test_transform.py`

- [ ] **Step 1: Criar `conftest.py` mínimo**

```python
# web/backend/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 2: Escrever testes (TODOS devem falhar)**

```python
# web/backend/tests/test_transform.py
from decimal import Decimal

import pytest

from etl.transform import parse_pt_br, parse_metric


class TestParsePtBr:
    def test_brl_simples(self):
        assert parse_pt_br("R$ 12,34") == Decimal("12.34")

    def test_brl_com_milhar(self):
        assert parse_pt_br("R$ 12.345,67") == Decimal("12345.67")

    def test_brl_milhoes(self):
        assert parse_pt_br("R$ 1.234.567,89") == Decimal("1234567.89")

    def test_percentual_positivo(self):
        assert parse_pt_br("+12,5%") == Decimal("12.5")

    def test_percentual_negativo(self):
        assert parse_pt_br("-3,7%") == Decimal("-3.7")

    def test_percentual_sem_sinal(self):
        assert parse_pt_br("12,5%") == Decimal("12.5")

    def test_multiplicador(self):
        assert parse_pt_br("8,5x") == Decimal("8.5")

    def test_multiplicador_inteiro(self):
        assert parse_pt_br("12x") == Decimal("12")

    def test_inteiro_com_milhar(self):
        assert parse_pt_br("1.234") == Decimal("1234")

    def test_inteiro_simples(self):
        assert parse_pt_br("567") == Decimal("567")

    def test_decimal_simples(self):
        assert parse_pt_br("12,34") == Decimal("12.34")

    def test_decimal_zero_a_um(self):
        assert parse_pt_br("0,5") == Decimal("0.5")

    @pytest.mark.parametrize("entrada", ["", "-", "N/A", "n/a", None])
    def test_vazio_vira_none(self, entrada):
        assert parse_pt_br(entrada) is None

    def test_ja_decimal_preserva(self):
        assert parse_pt_br(Decimal("12.5")) == Decimal("12.5")

    def test_ja_int_preserva(self):
        assert parse_pt_br(10) == Decimal("10")

    def test_ja_float_preserva(self):
        assert parse_pt_br(12.5) == Decimal("12.5")

    def test_string_invalida_levanta(self):
        with pytest.raises(ValueError):
            parse_pt_br("não-é-número")

    def test_whitespace_extremos(self):
        assert parse_pt_br("  R$ 12,34  ") == Decimal("12.34")


class TestParseMetric:
    """parse_metric tolera erros e devolve None, log de warning."""

    def test_parse_metric_normal(self):
        assert parse_metric("fat_face", "R$ 100,00") == Decimal("100")

    def test_parse_metric_invalido_retorna_none(self, caplog):
        result = parse_metric("fat_face", "xyz")
        assert result is None
        assert "xyz" in caplog.text
```

- [ ] **Step 3: Rodar e verificar que TODOS falham (módulo nem existe ainda)**

```bash
cd web/backend
pytest tests/test_transform.py -v
```

Expected: `ImportError: cannot import name 'parse_pt_br' from 'etl.transform'`. Esse é o estado RED esperado.

- [ ] **Step 4: Commit dos testes**

```bash
git add web/backend/tests/
git commit -m "test(etl): add parse_pt_br test suite (RED)"
```

---

### Task 2.2: Implementar parser (GREEN)

**Files:**
- Create: `web/backend/etl/transform.py`

- [ ] **Step 1: Implementar `parse_pt_br` e `parse_metric`**

```python
# web/backend/etl/transform.py
from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

_EMPTY_VALUES = {"", "-", "n/a", "N/A", "—"}

# remove prefixos/sufixos comuns
_STRIPPABLE = ("R$", "%", "x")


def parse_pt_br(valor: Any) -> Decimal | None:
    """Converte strings PT-BR (R$, %, x, etc.) para Decimal.

    Retorna None para valores vazios/ausentes. Levanta ValueError para strings
    sintaticamente inválidas.
    """
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    if not isinstance(valor, str):
        raise ValueError(f"Tipo não suportado: {type(valor).__name__}")

    s = valor.strip()
    if s in _EMPTY_VALUES or s.lower() in {v.lower() for v in _EMPTY_VALUES}:
        return None

    sinal = ""
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("-"):
        sinal = "-"
        s = s[1:]

    for suffix_or_prefix in _STRIPPABLE:
        s = s.replace(suffix_or_prefix, "")

    s = s.strip()
    if not s:
        return None

    # PT-BR: "1.234,56" → "1234.56"
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    # senão é inteiro estilo "1.234" → "1234"
    else:
        s = s.replace(".", "")

    try:
        return Decimal(sinal + s)
    except InvalidOperation as exc:
        raise ValueError(f"Não foi possível converter {valor!r} para Decimal") from exc


def parse_metric(nome: str, valor: Any) -> Decimal | None:
    """Versão tolerante: loga warning e devolve None em erro."""
    try:
        return parse_pt_br(valor)
    except ValueError as exc:
        logger.warning("falha_parse_metric", extra={"metric": nome, "valor": valor, "erro": str(exc)})
        return None
```

- [ ] **Step 2: Rodar testes — esperado GREEN**

```bash
pytest tests/test_transform.py -v
```

Expected: todos passam.

- [ ] **Step 3: Commit**

```bash
git add web/backend/etl/transform.py
git commit -m "feat(etl): implement parse_pt_br for BR-formatted strings"
```

---

### Task 2.3: Mapper handler dict → snapshot dict

**Files:**
- Modify: `web/backend/etl/transform.py`
- Modify: `web/backend/tests/test_transform.py`

O handler do auto-report retorna dict com chaves como `{{fat_face}}`, `{{roas_goog}}`, etc. Precisamos mapear isso para os campos do `Snapshot`.

- [ ] **Step 1: Adicionar testes (RED)**

Anexe ao `test_transform.py`:

```python
from etl.transform import map_handler_dados


class TestMapHandlerDados:
    def test_mapeia_metricas_destaque(self):
        entrada = {
            "{{fat_sem}}": "R$ 100.000,00",
            "{{inv_sem}}": "R$ 15.000,00",
            "{{roas}}": "6,7x",
            "{{cpa}}": "R$ 85,50",
            "{{vendas}}": "50",
            "{{fat_face}}": "R$ 40.000,00",
            "{{roas_face}}": "5,5x",
        }
        resultado = map_handler_dados(entrada)
        assert resultado["faturamento"] == Decimal("100000")
        assert resultado["investimento"] == Decimal("15000")
        assert resultado["roas"] == Decimal("6.7")
        assert resultado["cpa"] == Decimal("85.50")
        assert resultado["vendas"] == 50
        assert resultado["metricas_detalhadas"]["meta"]["faturamento"] == Decimal("40000")
        assert resultado["metricas_detalhadas"]["meta"]["roas"] == Decimal("5.5")

    def test_ignora_chave_desconhecida(self):
        entrada = {"{{chave_inexistente}}": "valor qualquer"}
        resultado = map_handler_dados(entrada)
        assert resultado.get("faturamento") is None
        assert resultado["raw_dados"] == entrada

    def test_preserva_raw(self):
        entrada = {"{{fat_sem}}": "R$ 1,00"}
        resultado = map_handler_dados(entrada)
        assert resultado["raw_dados"] == entrada
```

Rodar:

```bash
pytest tests/test_transform.py::TestMapHandlerDados -v
```

Expected: FAIL — `map_handler_dados` não existe.

- [ ] **Step 2: Implementar mapper**

Append ao `etl/transform.py`:

```python
# mapping de chave-placeholder → (campo_destino, fonte_opcional)
# fonte=None significa campo de destaque na tabela snapshots
# fonte="meta"/"google"/"ga4"/"painel" vai para metricas_detalhadas[fonte]
_MAPA_HANDLER = {
    # Destaque (colunas tipadas)
    "{{fat_sem}}": ("faturamento", None),
    "{{inv_sem}}": ("investimento", None),
    "{{roas}}":    ("roas", None),
    "{{cpa}}":     ("cpa", None),
    "{{vendas}}":  ("vendas", None),
    "{{leads}}":   ("leads", None),
    # Variações
    "{{fat_sem_var}}": ("faturamento_var_pct", None),
    "{{roas_var}}":    ("roas_var_pct", None),
    # Meta
    "{{fat_face}}":   ("faturamento", "meta"),
    "{{inv_face}}":   ("investimento", "meta"),
    "{{roas_face}}":  ("roas", "meta"),
    "{{cpa_face}}":   ("cpa", "meta"),
    "{{vendas_face}}":("vendas", "meta"),
    # Google
    "{{fat_goog}}":   ("faturamento", "google"),
    "{{inv_goog}}":   ("investimento", "google"),
    "{{roas_goog}}":  ("roas", "google"),
    "{{cpa_goog}}":   ("cpa", "google"),
    "{{vendas_goog}}":("vendas", "google"),
    # GA4
    "{{ses_ga}}":      ("sessoes", "ga4"),
    "{{ses_eng_ga}}":  ("sessoes_engajadas", "ga4"),
    "{{taxa_eng_ga}}": ("taxa_engajamento", "ga4"),
}

_INTEGER_CAMPOS = {"vendas", "leads", "sessoes", "sessoes_engajadas"}


def map_handler_dados(dados: dict[str, str]) -> dict:
    """Converte dict do handler (placeholders PT-BR) em dict tipado para Snapshot."""
    resultado: dict = {"metricas_detalhadas": {}, "raw_dados": dict(dados)}

    for chave, valor in dados.items():
        mapping = _MAPA_HANDLER.get(chave)
        if mapping is None:
            continue
        campo, fonte = mapping
        parsed = parse_metric(chave, valor)
        if parsed is None:
            continue
        if campo in _INTEGER_CAMPOS:
            parsed = int(parsed)
        if fonte is None:
            resultado[campo] = parsed
        else:
            resultado["metricas_detalhadas"].setdefault(fonte, {})[campo] = parsed

    return resultado
```

- [ ] **Step 3: Rodar testes**

```bash
pytest tests/test_transform.py -v
```

Expected: todos passam.

- [ ] **Step 4: Commit**

```bash
git add web/backend/etl/transform.py web/backend/tests/test_transform.py
git commit -m "feat(etl): map handler placeholders to snapshot fields"
```

---

### Task 2.4: Validar com amostra real de handler

**Files:**
- Create: `web/backend/scripts/validate_parser.py`

Este passo NÃO é automatizado — é uma verificação manual para garantir que o `_MAPA_HANDLER` da Task 2.3 cobre as chaves reais que os handlers do `core/categorias/` produzem.

- [ ] **Step 1: Criar script de validação**

```python
# web/backend/scripts/validate_parser.py
"""Roda um handler real do auto-report e mostra as chaves não mapeadas."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]   # auto-report-main
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

import core.categorias as cats
from config.settings import CENTRAL_SHEET_URL, CENTRAL_TAB_NAME
from core.periodo import periodo_referencia
from core.leitura_central import fetch_clientes
from etl.transform import _MAPA_HANDLER


def main(cliente_nome: str) -> None:
    clientes = fetch_clientes(atualizar=False, sheet_url=CENTRAL_SHEET_URL, tab_name=CENTRAL_TAB_NAME)
    cliente = next(c for c in clientes if cliente_nome.lower() in c.nome.lower())

    periodo_ref = periodo_referencia(date.today(), "MENSAL")
    periodo_comp = periodo_referencia(periodo_ref.inicio, "MENSAL")

    handler = cats.get_handler(cliente.categoria)
    dados = handler.coletar_dados(cliente, periodo_ref, periodo_comp)

    print(f"\n--- Chaves do handler ({len(dados)}):")
    for k, v in dados.items():
        prefix = "✓" if k in _MAPA_HANDLER else "✗"
        print(f"  {prefix} {k} = {v!r}")

    nao_mapeadas = [k for k in dados if k not in _MAPA_HANDLER]
    if nao_mapeadas:
        print(f"\n⚠️  {len(nao_mapeadas)} chaves não mapeadas — atualize _MAPA_HANDLER em etl/transform.py")
    else:
        print("\n✓ Todas as chaves estão mapeadas.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/validate_parser.py <nome-parcial-cliente>")
        sys.exit(1)
    main(sys.argv[1])
```

- [ ] **Step 2: Rodar com um cliente real**

```bash
cd web/backend
python scripts/validate_parser.py "loja"
```

Expected: lista de chaves com ✓/✗. Se houver chaves ✗ relevantes (faturamento, ROAS, etc.), adicionar entradas em `_MAPA_HANDLER` e repetir.

- [ ] **Step 3: Atualizar `_MAPA_HANDLER` conforme necessário**

Se aparecerem chaves novas (ex.: `{{tck_med}}`, `{{taxa_conv}}`), adicione ao `_MAPA_HANDLER` em `transform.py` e crie um teste novo em `test_transform.py` para a chave.

- [ ] **Step 4: Commit**

```bash
git add web/backend/scripts/validate_parser.py web/backend/etl/transform.py web/backend/tests/test_transform.py
git commit -m "feat(etl): validate parser coverage against real handler"
```

---

## Fase 3 — Backend API

### Task 3.1: Pydantic schemas (DTOs)

**Files:**
- Create: `web/backend/schemas/case.py`
- Create: `web/backend/schemas/ranking.py`
- Create: `web/backend/schemas/__init__.py`

- [ ] **Step 1: Criar `schemas/case.py`**

```python
# web/backend/schemas/case.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class CaseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    nome: str
    logo_url: str | None
    categoria: str
    setor: str | None
    porte: str | None
    descricao_publica: str | None
    destaque: bool
    periodo_inicio: date
    periodo_fim: date
    faturamento: Decimal | None
    investimento: Decimal | None
    roas: Decimal | None
    cpa: Decimal | None
    leads: int | None
    vendas: int | None
    faturamento_var_pct: Decimal | None
    roas_var_pct: Decimal | None


class PontoEvolucao(BaseModel):
    periodo_inicio: date
    periodo_fim: date
    faturamento: Decimal | None
    investimento: Decimal | None
    roas: Decimal | None


class CaseDetail(CaseListItem):
    metricas_detalhadas: dict[str, dict[str, Any]]
    evolucao: list[PontoEvolucao]
    data_coleta: datetime
```

- [ ] **Step 2: Criar `schemas/ranking.py`**

```python
# web/backend/schemas/ranking.py
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RankingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    nome: str
    logo_url: str | None
    valor: Decimal
```

- [ ] **Step 3: Criar `schemas/__init__.py`**

```python
# web/backend/schemas/__init__.py
from .case import CaseDetail, CaseListItem, PontoEvolucao
from .ranking import RankingItem

__all__ = ["CaseDetail", "CaseListItem", "PontoEvolucao", "RankingItem"]
```

- [ ] **Step 4: Commit**

```bash
git add web/backend/schemas/
git commit -m "feat(backend): add Pydantic DTOs for cases and rankings"
```

---

### Task 3.2: Service `case_builder`

**Files:**
- Create: `web/backend/services/case_builder.py`
- Create: `web/backend/tests/test_case_builder.py`

- [ ] **Step 1: Escrever testes (RED)**

```python
# web/backend/tests/test_case_builder.py
from datetime import date
from decimal import Decimal
from uuid import uuid4

from models import Categoria, Cliente, Snapshot
from models.snapshot import Frequencia
from services.case_builder import build_case_detail, build_case_list_item


def _cliente(**kwargs) -> Cliente:
    base = dict(
        id=uuid4(), slug="x", nome="X", categoria=Categoria.ECOMMERCE,
        publicar_vitrine=True, destaque=False,
    )
    base.update(kwargs)
    return Cliente(**base)


def _snapshot(cliente_id, **kwargs) -> Snapshot:
    base = dict(
        cliente_id=cliente_id,
        periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 1, 31),
        frequencia=Frequencia.MENSAL,
        faturamento=Decimal("100000"), roas=Decimal("6.5"),
        metricas_detalhadas={"meta": {"roas": 7.0}}, raw_dados={},
    )
    base.update(kwargs)
    return Snapshot(**base)


def test_build_list_item():
    c = _cliente()
    s = _snapshot(c.id)
    dto = build_case_list_item(c, s)
    assert dto.slug == "x"
    assert dto.faturamento == Decimal("100000")
    assert dto.roas == Decimal("6.5")


def test_build_detail_inclui_evolucao():
    c = _cliente()
    snaps = [_snapshot(c.id, periodo_fim=date(2026, m, 28)) for m in (1, 2, 3)]
    dto = build_case_detail(c, snapshot_atual=snaps[-1], historico=snaps)
    assert len(dto.evolucao) == 3
    assert dto.evolucao[0].periodo_fim == date(2026, 1, 28)
    assert dto.metricas_detalhadas == {"meta": {"roas": 7.0}}
```

Rodar:

```bash
cd web/backend
pytest tests/test_case_builder.py -v
```

Expected: FAIL — módulo não existe.

- [ ] **Step 2: Implementar `case_builder`**

```python
# web/backend/services/case_builder.py
from __future__ import annotations

from models import Cliente, Snapshot
from schemas import CaseDetail, CaseListItem, PontoEvolucao


def build_case_list_item(cliente: Cliente, snapshot: Snapshot) -> CaseListItem:
    return CaseListItem(
        slug=cliente.slug,
        nome=cliente.nome,
        logo_url=cliente.logo_url,
        categoria=cliente.categoria.value,
        setor=cliente.setor,
        porte=cliente.porte,
        descricao_publica=cliente.descricao_publica,
        destaque=cliente.destaque,
        periodo_inicio=snapshot.periodo_inicio,
        periodo_fim=snapshot.periodo_fim,
        faturamento=snapshot.faturamento,
        investimento=snapshot.investimento,
        roas=snapshot.roas,
        cpa=snapshot.cpa,
        leads=snapshot.leads,
        vendas=snapshot.vendas,
        faturamento_var_pct=snapshot.faturamento_var_pct,
        roas_var_pct=snapshot.roas_var_pct,
    )


def build_case_detail(
    cliente: Cliente,
    snapshot_atual: Snapshot,
    historico: list[Snapshot],
) -> CaseDetail:
    base = build_case_list_item(cliente, snapshot_atual).model_dump()
    return CaseDetail(
        **base,
        metricas_detalhadas=snapshot_atual.metricas_detalhadas or {},
        evolucao=[
            PontoEvolucao(
                periodo_inicio=s.periodo_inicio,
                periodo_fim=s.periodo_fim,
                faturamento=s.faturamento,
                investimento=s.investimento,
                roas=s.roas,
            )
            for s in sorted(historico, key=lambda x: x.periodo_fim)
        ],
        data_coleta=snapshot_atual.data_coleta,
    )
```

- [ ] **Step 3: Rodar testes — GREEN**

```bash
pytest tests/test_case_builder.py -v
```

Expected: passam.

- [ ] **Step 4: Commit**

```bash
git add web/backend/services/case_builder.py web/backend/tests/test_case_builder.py
git commit -m "feat(backend): build case DTOs from ORM models"
```

---

### Task 3.3: Endpoint `GET /api/cases`

**Files:**
- Create: `web/backend/api/cases.py`
- Modify: `web/backend/main.py`
- Create: `web/backend/tests/test_api_cases.py`

- [ ] **Step 1: Criar fixture de DB para testes**

Edite `web/backend/tests/conftest.py`:

```python
# web/backend/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pytest_postgresql import factories

from models import Base


postgresql_proc = factories.postgresql_proc(load=[])
postgresql = factories.postgresql("postgresql_proc")


@pytest.fixture
def db_engine(postgresql):
    url = f"postgresql+psycopg://{postgresql.info.user}:@{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, future=True)
    with Session() as s:
        yield s


@pytest.fixture
def client(db_engine, monkeypatch):
    from fastapi.testclient import TestClient
    from main import create_app
    from db import SessionLocal

    monkeypatch.setattr("db.engine", db_engine)
    monkeypatch.setattr("db.SessionLocal", sessionmaker(bind=db_engine, future=True))

    app = create_app()
    return TestClient(app)
```

- [ ] **Step 2: Escrever teste do endpoint (RED)**

```python
# web/backend/tests/test_api_cases.py
from datetime import date
from decimal import Decimal

from models import Categoria, Cliente, Snapshot
from models.snapshot import Frequencia


def _seed_cliente(db_session, *, slug="x", publicar=True, roas=Decimal("6")):
    c = Cliente(slug=slug, nome=slug.upper(), categoria=Categoria.ECOMMERCE, publicar_vitrine=publicar)
    db_session.add(c); db_session.flush()
    db_session.add(Snapshot(
        cliente_id=c.id, periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 1, 31),
        frequencia=Frequencia.MENSAL, faturamento=Decimal("100000"), roas=roas,
        metricas_detalhadas={}, raw_dados={},
    ))
    db_session.commit()
    return c


def test_list_retorna_apenas_publicos(client, db_session):
    _seed_cliente(db_session, slug="publico", publicar=True)
    _seed_cliente(db_session, slug="privado", publicar=False)

    r = client.get("/api/cases")
    assert r.status_code == 200
    slugs = [item["slug"] for item in r.json()["items"]]
    assert "publico" in slugs
    assert "privado" not in slugs


def test_list_ordena_por_roas_desc(client, db_session):
    _seed_cliente(db_session, slug="baixo", roas=Decimal("3"))
    _seed_cliente(db_session, slug="alto", roas=Decimal("9"))

    r = client.get("/api/cases?order_by=roas")
    slugs = [item["slug"] for item in r.json()["items"]]
    assert slugs[0] == "alto"


def test_list_filtra_categoria(client, db_session):
    c1 = _seed_cliente(db_session, slug="a")
    c1.categoria = Categoria.LEAD_COM_SITE; db_session.commit()
    _seed_cliente(db_session, slug="b")  # E-commerce

    r = client.get("/api/cases?categoria=E-commerce")
    slugs = [item["slug"] for item in r.json()["items"]]
    assert slugs == ["b"]
```

Rodar:

```bash
pytest tests/test_api_cases.py::test_list_retorna_apenas_publicos -v
```

Expected: FAIL — 404 (rota não existe).

- [ ] **Step 3: Implementar `api/cases.py`**

```python
# web/backend/api/cases.py
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..db import get_session
from ..models import Cliente, Snapshot
from ..schemas import CaseDetail, CaseListItem
from ..services.case_builder import build_case_detail, build_case_list_item

router = APIRouter()


class CaseListResponse(BaseModel):
    items: list[CaseListItem]
    total: int


@router.get("/cases", response_model=CaseListResponse)
def list_cases(
    categoria: str | None = Query(default=None),
    setor: str | None = Query(default=None),
    order_by: Literal["roas", "faturamento", "crescimento"] = Query(default="faturamento"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> CaseListResponse:
    # subquery: snapshot mais recente por cliente
    sub = (
        select(Snapshot.cliente_id, Snapshot.id.label("snap_id"))
        .distinct(Snapshot.cliente_id)
        .order_by(Snapshot.cliente_id, Snapshot.periodo_fim.desc(), Snapshot.data_coleta.desc())
    ).subquery()

    stmt = (
        select(Cliente, Snapshot)
        .join(sub, sub.c.cliente_id == Cliente.id)
        .join(Snapshot, Snapshot.id == sub.c.snap_id)
        .where(Cliente.publicar_vitrine.is_(True))
    )
    if categoria:
        stmt = stmt.where(Cliente.categoria == categoria)
    if setor:
        stmt = stmt.where(Cliente.setor == setor)

    if order_by == "roas":
        stmt = stmt.order_by(Snapshot.roas.desc().nullslast())
    elif order_by == "crescimento":
        stmt = stmt.order_by(Snapshot.faturamento_var_pct.desc().nullslast())
    else:
        stmt = stmt.order_by(Snapshot.faturamento.desc().nullslast())

    total = session.scalar(select(stmt.with_only_columns().count())) or 0
    rows = session.execute(stmt.limit(limit).offset(offset)).all()

    items = [build_case_list_item(c, s) for (c, s) in rows]
    return CaseListResponse(items=items, total=total)


@router.get("/cases/{slug}", response_model=CaseDetail)
def get_case(slug: str, session: Session = Depends(get_session)) -> CaseDetail:
    cliente = session.scalar(
        select(Cliente)
        .where(Cliente.slug == slug, Cliente.publicar_vitrine.is_(True))
        .options(joinedload(Cliente.snapshots))
    )
    if cliente is None or not cliente.snapshots:
        raise HTTPException(404, "Case não encontrado")

    snapshots = sorted(cliente.snapshots, key=lambda s: s.periodo_fim)
    atual = snapshots[-1]
    historico = snapshots[-12:]
    return build_case_detail(cliente, atual, historico)
```

- [ ] **Step 4: Registrar router em `main.py`**

```python
# web/backend/main.py — ADIÇÃO
from .api import cases, health

# dentro de create_app(), antes do return:
    app.include_router(cases.router, prefix="/api")
```

- [ ] **Step 5: Rodar testes**

```bash
pytest tests/test_api_cases.py -v
```

Expected: passam.

- [ ] **Step 6: Commit**

```bash
git add web/backend/api/cases.py web/backend/main.py web/backend/tests/
git commit -m "feat(backend): add GET /api/cases and /api/cases/{slug}"
```

---

### Task 3.4: Endpoint `GET /api/rankings/{tipo}`

**Files:**
- Create: `web/backend/services/rankings.py`
- Create: `web/backend/api/rankings.py`
- Modify: `web/backend/main.py`
- Create: `web/backend/tests/test_api_rankings.py`

- [ ] **Step 1: Escrever testes (RED)**

```python
# web/backend/tests/test_api_rankings.py
from datetime import date
from decimal import Decimal

from models import Categoria, Cliente, Snapshot
from models.snapshot import Frequencia


def _seed(db_session, slug, roas):
    c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE, publicar_vitrine=True)
    db_session.add(c); db_session.flush()
    db_session.add(Snapshot(
        cliente_id=c.id, periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 1, 31),
        frequencia=Frequencia.MENSAL, roas=roas, metricas_detalhadas={}, raw_dados={},
    ))
    db_session.commit()


def test_ranking_roas(client, db_session):
    _seed(db_session, "alto", Decimal("9"))
    _seed(db_session, "medio", Decimal("5"))
    _seed(db_session, "baixo", Decimal("1"))

    r = client.get("/api/rankings/roas?limit=2")
    assert r.status_code == 200
    items = r.json()
    assert [i["slug"] for i in items] == ["alto", "medio"]
    assert items[0]["valor"] == "9"   # Decimal -> str via Pydantic


def test_ranking_tipo_invalido(client):
    r = client.get("/api/rankings/cor-favorita")
    assert r.status_code == 422 or r.status_code == 400
```

Rodar:

```bash
pytest tests/test_api_rankings.py -v
```

Expected: FAIL (404).

- [ ] **Step 2: Implementar `services/rankings.py`**

```python
# web/backend/services/rankings.py
from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Cliente, Snapshot

RankingTipo = Literal["roas", "faturamento", "crescimento"]

_COLUNA = {
    "roas": Snapshot.roas,
    "faturamento": Snapshot.faturamento,
    "crescimento": Snapshot.faturamento_var_pct,
}


def top_n(session: Session, tipo: RankingTipo, limit: int) -> list[tuple[Cliente, Snapshot]]:
    sub = (
        select(Snapshot.cliente_id, Snapshot.id.label("snap_id"))
        .distinct(Snapshot.cliente_id)
        .order_by(Snapshot.cliente_id, Snapshot.periodo_fim.desc(), Snapshot.data_coleta.desc())
    ).subquery()

    coluna = _COLUNA[tipo]
    stmt = (
        select(Cliente, Snapshot)
        .join(sub, sub.c.cliente_id == Cliente.id)
        .join(Snapshot, Snapshot.id == sub.c.snap_id)
        .where(Cliente.publicar_vitrine.is_(True), coluna.is_not(None))
        .order_by(coluna.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).all())
```

- [ ] **Step 3: Implementar `api/rankings.py`**

```python
# web/backend/api/rankings.py
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import RankingItem
from ..services import rankings as rankings_svc

router = APIRouter()


@router.get("/rankings/{tipo}", response_model=list[RankingItem])
def get_ranking(
    tipo: Literal["roas", "faturamento", "crescimento"],
    limit: int = Query(default=10, le=50),
    session: Session = Depends(get_session),
) -> list[RankingItem]:
    rows = rankings_svc.top_n(session, tipo, limit)
    coluna = rankings_svc._COLUNA[tipo]
    return [
        RankingItem(slug=c.slug, nome=c.nome, logo_url=c.logo_url, valor=getattr(s, coluna.key))
        for (c, s) in rows
    ]
```

- [ ] **Step 4: Adicionar import e `services/__init__.py`**

```python
# web/backend/services/__init__.py
from . import case_builder, rankings

__all__ = ["case_builder", "rankings"]
```

Registrar router em `main.py`:

```python
from .api import cases, health, rankings
# ...
    app.include_router(rankings.router, prefix="/api")
```

- [ ] **Step 5: Rodar testes**

```bash
pytest tests/test_api_rankings.py -v
```

Expected: passam.

- [ ] **Step 6: Commit**

```bash
git add web/backend/services/ web/backend/api/rankings.py web/backend/main.py web/backend/tests/test_api_rankings.py
git commit -m "feat(backend): add GET /api/rankings/{tipo}"
```

---

## Fase 4 — ETL (reuso do `core/`)

### Task 4.1: Estender `core.leitura_central` com novas colunas

**Files:**
- Modify: `core/leitura_central.py`

A Planilha Central já tem colunas para o auto-report (`CATEGORIA`, status, etc.). Vamos adicionar suporte às novas colunas necessárias para a vitrine.

- [ ] **Step 1: Inspecionar leitura atual**

```bash
cd /Users/mac0267/Documents/auto-report-main
grep -n "COL\|columns\|header" core/leitura_central.py | head -30
```

Identifique como as colunas atuais são mapeadas (ex.: constantes `COL_CATEGORIA = "CATEGORIA"`).

- [ ] **Step 2: Adicionar constantes e atributos**

`core/leitura_central.py` já tem o dataclass `Cliente` (linha ~74) e o parser `_parse_rows` (linha ~170). A função pública é `fetch_clientes` (linha ~304).

Adicione constantes próximo às outras `COL_*`:

```python
COL_PUBLICAR_VITRINE = "PUBLICAR_VITRINE"
COL_DESCRICAO_PUBLICA = "DESCRICAO_PUBLICA"
COL_LOGO_URL = "LOGO_URL"
COL_SETOR_PUBLICO = "SETOR_PUBLICO"
COL_PORTE_PUBLICO = "PORTE_PUBLICO"
```

Adicione campos ao `@dataclass class Cliente` (logo após `email: str | None = None`):

```python
publicar_vitrine: bool = False
descricao_publica: str | None = None
logo_url: str | None = None
setor_publico: str | None = None
porte_publico: str | None = None
```

No `_parse_rows`, adicione leitura tolerante a colunas ausentes. Importante: o parser atual usa `row[header_map[COL_X]]` que falha se a coluna não estiver no header. Use um helper:

```python
def _parse_bool_pt(val: str | None) -> bool:
    return (val or "").strip().upper() in {"TRUE", "VERDADEIRO", "SIM", "X", "1"}


def _get_optional(row: list[str], header_map: dict[str, int], col: str) -> str | None:
    idx = header_map.get(col)
    if idx is None or idx >= len(row):
        return None
    val = (row[idx] or "").strip()
    return val or None
```

E ao construir cada `Cliente(...)` em `_parse_rows`, passe os novos campos:

```python
cliente = Cliente(
    nome=nome,
    categoria=...,
    # ... outros campos existentes
    publicar_vitrine=_parse_bool_pt(_get_optional(row, header_map, COL_PUBLICAR_VITRINE)),
    descricao_publica=_get_optional(row, header_map, COL_DESCRICAO_PUBLICA),
    logo_url=_get_optional(row, header_map, COL_LOGO_URL),
    setor_publico=_get_optional(row, header_map, COL_SETOR_PUBLICO),
    porte_publico=_get_optional(row, header_map, COL_PORTE_PUBLICO),
)
```

> NOTA: Há duas construções de `Cliente(...)` no arquivo (em `_parse_rows` linha ~239 e em `fetch_clientes` linha ~337). Atualize ambas.

- [ ] **Step 3: Garantir tolerância a colunas ausentes**

`_get_optional` já trata coluna ausente (`header_map.get(col)` retorna `None`). Validar que `fetch_clientes()` não falha em planilhas que ainda não têm as novas colunas.

- [ ] **Step 4: Teste manual**

```bash
cd /Users/mac0267/Documents/auto-report-main
python -c "from core.leitura_central import fetch_clientes; cs = fetch_clientes(); print([(c.nome, c.publicar_vitrine) for c in cs[:3]])"
```

Expected: lista de tuplas. `publicar_vitrine` deve ser `False` para clientes sem a flag e `True` para os que tiverem `TRUE` na nova coluna.

- [ ] **Step 5: Commit**

```bash
git add core/leitura_central.py
git commit -m "feat(core): read PUBLICAR_VITRINE and related public columns from central sheet"
```

---

### Task 4.2: Lock distribuído via Postgres advisory lock

**Files:**
- Create: `web/backend/etl/lock.py`
- Create: `web/backend/tests/test_lock.py`

- [ ] **Step 1: Escrever testes (RED)**

```python
# web/backend/tests/test_lock.py
import pytest

from etl.lock import advisory_lock, LockTaken


def test_advisory_lock_basico(db_engine):
    with advisory_lock(db_engine, "etl:run"):
        pass  # libera ao sair


def test_advisory_lock_concorrente(db_engine):
    with advisory_lock(db_engine, "etl:run"):
        with pytest.raises(LockTaken):
            with advisory_lock(db_engine, "etl:run", blocking=False):
                pytest.fail("não devia ter conseguido")
```

Rodar:

```bash
cd web/backend
pytest tests/test_lock.py -v
```

Expected: FAIL — módulo não existe.

- [ ] **Step 2: Implementar `etl/lock.py`**

```python
# web/backend/etl/lock.py
from __future__ import annotations

import contextlib
import hashlib

from sqlalchemy import text
from sqlalchemy.engine import Engine


class LockTaken(Exception):
    pass


def _key_to_bigint(key: str) -> int:
    """Converte string em bigint estável (positivo, cabe em int64)."""
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=True)


@contextlib.contextmanager
def advisory_lock(engine: Engine, key: str, *, blocking: bool = True):
    """Lock distribuído via pg_advisory_lock. Liberado no commit OU ao fechar a conexão."""
    bigint = _key_to_bigint(key)
    conn = engine.connect()
    try:
        if blocking:
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": bigint})
        else:
            got = conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": bigint})
            if not got:
                raise LockTaken(f"Lock {key!r} ocupado")
        yield
    finally:
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": bigint})
        conn.close()
```

- [ ] **Step 3: Rodar testes**

```bash
pytest tests/test_lock.py -v
```

Expected: passam.

- [ ] **Step 4: Commit**

```bash
git add web/backend/etl/lock.py web/backend/tests/test_lock.py
git commit -m "feat(etl): postgres advisory lock for distributed mutex"
```

---

### Task 4.3: Upsert idempotente de snapshot

**Files:**
- Create: `web/backend/etl/upsert.py`
- Create: `web/backend/tests/test_upsert.py`

- [ ] **Step 1: Testes (RED)**

```python
# web/backend/tests/test_upsert.py
from datetime import date
from decimal import Decimal
from uuid import uuid4

from models import Categoria, Cliente
from models.snapshot import Frequencia
from etl.upsert import upsert_snapshot
from sqlalchemy import select
from models import Snapshot


def test_insere_novo(db_session):
    c = Cliente(slug="x", nome="X", categoria=Categoria.ECOMMERCE, publicar_vitrine=True)
    db_session.add(c); db_session.commit()

    upsert_snapshot(
        db_session,
        cliente_id=c.id,
        periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 1, 31),
        frequencia=Frequencia.MENSAL,
        dados={"faturamento": Decimal("100"), "metricas_detalhadas": {}, "raw_dados": {}},
    )
    db_session.commit()
    n = db_session.scalar(select(Snapshot).where(Snapshot.cliente_id == c.id))
    assert n.faturamento == Decimal("100")


def test_atualiza_mesmo_periodo(db_session):
    c = Cliente(slug="x", nome="X", categoria=Categoria.ECOMMERCE, publicar_vitrine=True)
    db_session.add(c); db_session.commit()

    base = dict(
        cliente_id=c.id,
        periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 1, 31),
        frequencia=Frequencia.MENSAL,
    )
    upsert_snapshot(db_session, **base, dados={"faturamento": Decimal("100"), "metricas_detalhadas": {}, "raw_dados": {}})
    db_session.commit()
    upsert_snapshot(db_session, **base, dados={"faturamento": Decimal("200"), "metricas_detalhadas": {}, "raw_dados": {}})
    db_session.commit()

    snaps = db_session.scalars(select(Snapshot).where(Snapshot.cliente_id == c.id)).all()
    assert len(snaps) == 1
    assert snaps[0].faturamento == Decimal("200")
```

Rodar:

```bash
pytest tests/test_upsert.py -v
```

Expected: FAIL — módulo não existe.

- [ ] **Step 2: Implementar `etl/upsert.py`**

```python
# web/backend/etl/upsert.py
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import Snapshot
from ..models.snapshot import Frequencia


def upsert_snapshot(
    session: Session,
    *,
    cliente_id: uuid.UUID,
    periodo_inicio: date,
    periodo_fim: date,
    frequencia: Frequencia,
    dados: dict,
) -> Snapshot:
    """Insere ou atualiza snapshot baseado em (cliente_id, periodo_inicio, periodo_fim)."""
    payload = {
        "cliente_id": cliente_id,
        "periodo_inicio": periodo_inicio,
        "periodo_fim": periodo_fim,
        "frequencia": frequencia,
        **dados,
    }
    stmt = insert(Snapshot).values(**payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_snapshot_periodo",
        set_={k: v for k, v in payload.items() if k not in {"cliente_id", "periodo_inicio", "periodo_fim", "frequencia"}},
    )
    session.execute(stmt)
    return session.scalar(
        select(Snapshot).where(
            Snapshot.cliente_id == cliente_id,
            Snapshot.periodo_inicio == periodo_inicio,
            Snapshot.periodo_fim == periodo_fim,
        )
    )
```

- [ ] **Step 3: Rodar testes**

```bash
pytest tests/test_upsert.py -v
```

Expected: passam.

- [ ] **Step 4: Commit**

```bash
git add web/backend/etl/upsert.py web/backend/tests/test_upsert.py
git commit -m "feat(etl): idempotent snapshot upsert"
```

---

### Task 4.4: Orquestrador `collect.py`

**Files:**
- Create: `web/backend/etl/collect.py`
- Create: `web/backend/tests/test_collect.py`

- [ ] **Step 1: Testes (RED) — mockando handler**

```python
# web/backend/tests/test_collect.py
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from etl.collect import processar_cliente, _to_snapshot_payload
from models.snapshot import Frequencia


class FakeCliente:
    def __init__(self, **kw):
        self.id = kw.get("id")
        self.nome = kw["nome"]
        self.slug = kw["slug"]
        self.categoria = kw["categoria"]
        self.publicar_vitrine = True


def test_to_snapshot_payload_mapeia_corretamente():
    handler_dados = {
        "{{fat_sem}}": "R$ 100,00",
        "{{roas}}": "6,5x",
        "{{vendas}}": "10",
    }
    payload = _to_snapshot_payload(handler_dados)
    assert payload["faturamento"] == Decimal("100")
    assert payload["roas"] == Decimal("6.5")
    assert payload["vendas"] == 10
    assert payload["raw_dados"] == handler_dados


def test_processar_cliente_grava_snapshot(db_session, db_engine):
    from models import Categoria, Cliente

    cliente_db = Cliente(slug="acme", nome="Acme", categoria=Categoria.ECOMMERCE, publicar_vitrine=True)
    db_session.add(cliente_db); db_session.commit()

    fake_handler = MagicMock()
    fake_handler.coletar_dados.return_value = {"{{fat_sem}}": "R$ 1.000,00", "{{roas}}": "4,2x"}

    with patch("etl.collect._get_handler", return_value=fake_handler):
        processar_cliente(
            cliente_planilha=FakeCliente(nome="Acme", slug="acme", categoria="E-commerce"),
            cliente_db_id=cliente_db.id,
            periodo_ref=MagicMock(inicio=date(2026, 1, 1), fim=date(2026, 1, 31)),
            periodo_comp=MagicMock(),
            frequencia=Frequencia.MENSAL,
            session_factory=lambda: db_session,
        )

    from models import Snapshot
    snap = db_session.scalar(__import__("sqlalchemy").select(Snapshot))
    assert snap.faturamento == Decimal("1000")
    assert snap.roas == Decimal("4.2")
```

Rodar:

```bash
pytest tests/test_collect.py -v
```

Expected: FAIL — módulo não existe.

- [ ] **Step 2: Implementar `collect.py`**

```python
# web/backend/etl/collect.py
from __future__ import annotations

import logging
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Callable

# Garante que core/ (raiz do auto-report) está no PYTHONPATH
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import Categoria, Cliente
from ..models.snapshot import Frequencia
from .lock import LockTaken, advisory_lock
from .transform import map_handler_dados
from .upsert import upsert_snapshot

log = logging.getLogger(__name__)


def _get_handler(categoria: str):
    """Wrapper para permitir mock em testes."""
    import core.categorias as cats
    return cats.get_handler(categoria)


def _to_snapshot_payload(handler_dados: dict[str, str]) -> dict:
    return map_handler_dados(handler_dados)


def _sync_cliente_db(session: Session, cliente_planilha) -> Cliente:
    """Upsert do cliente no DB com dados da planilha. Requer `cliente_planilha.slug` setado."""
    slug = cliente_planilha.slug
    cliente = session.scalar(select(Cliente).where(Cliente.slug == slug))
    if cliente is None:
        cliente = Cliente(slug=slug, nome=cliente_planilha.nome, categoria=Categoria(cliente_planilha.categoria))
        session.add(cliente)
    else:
        cliente.nome = cliente_planilha.nome
        cliente.categoria = Categoria(cliente_planilha.categoria)
    cliente.logo_url = getattr(cliente_planilha, "logo_url", None)
    cliente.descricao_publica = getattr(cliente_planilha, "descricao_publica", None)
    cliente.setor = getattr(cliente_planilha, "setor_publico", None)
    cliente.porte = getattr(cliente_planilha, "porte_publico", None)
    cliente.publicar_vitrine = bool(getattr(cliente_planilha, "publicar_vitrine", False))
    session.flush()
    return cliente


def _slugify(nome: str) -> str:
    """Converte nome do cliente em slug URL-friendly."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "cliente"


def processar_cliente(
    *,
    cliente_planilha,
    cliente_db_id: uuid.UUID,
    periodo_ref,
    periodo_comp,
    frequencia: Frequencia,
    session_factory: Callable[[], Session] = SessionLocal,
) -> bool:
    try:
        handler = _get_handler(cliente_planilha.categoria)
        dados = handler.coletar_dados(cliente_planilha, periodo_ref, periodo_comp)

        payload = _to_snapshot_payload(dados)

        session = session_factory()
        try:
            upsert_snapshot(
                session,
                cliente_id=cliente_db_id,
                periodo_inicio=periodo_ref.inicio,
                periodo_fim=periodo_ref.fim,
                frequencia=frequencia,
                dados=payload,
            )
            session.commit()
        finally:
            if session_factory is SessionLocal:
                session.close()

        log.info("etl_snapshot_gravado", extra={"cliente": cliente_planilha.nome})
        return True
    except Exception:
        log.exception("etl_falhou", extra={"cliente": cliente_planilha.nome})
        return False


def run_etl(today: date | None = None, frequencia_str: str | None = None) -> dict:
    settings = get_settings()
    today = today or date.today()
    frequencia_str = frequencia_str or settings.etl_periodo_granularidade
    frequencia = Frequencia(frequencia_str)

    from config.settings import CENTRAL_SHEET_URL, CENTRAL_TAB_NAME
    from core.leitura_central import fetch_clientes
    from core.periodo import periodo_referencia
    from db import engine

    try:
        with advisory_lock(engine, "etl:vitrine:run", blocking=False):
            todos = fetch_clientes(
                atualizar=False,                 # ETL só lê, não muda status do auto-report
                sheet_url=CENTRAL_SHEET_URL,
                tab_name=CENTRAL_TAB_NAME,
            )
            clientes = [c for c in todos if getattr(c, "publicar_vitrine", False)]
            log.info("etl_iniciado", extra={"n_clientes": len(clientes), "frequencia": frequencia_str})

            periodo_ref = periodo_referencia(today, frequencia_str)
            periodo_comp = periodo_referencia(periodo_ref.inicio, frequencia_str)

            # Atribui slugs derivados do nome (estável)
            for c in clientes:
                c.slug = _slugify(c.nome)  # type: ignore[attr-defined]

            # Sincroniza clientes no DB
            ids: dict[str, uuid.UUID] = {}
            with SessionLocal() as session:
                for c in clientes:
                    cdb = _sync_cliente_db(session, c)
                    ids[c.slug] = cdb.id
                session.commit()

            ok = 0
            fail = 0
            with ThreadPoolExecutor(max_workers=settings.etl_threads) as pool:
                futures = {
                    pool.submit(
                        processar_cliente,
                        cliente_planilha=c,
                        cliente_db_id=ids[c.slug],
                        periodo_ref=periodo_ref,
                        periodo_comp=periodo_comp,
                        frequencia=frequencia,
                    ): c
                    for c in clientes
                }
                for f in as_completed(futures):
                    if f.result():
                        ok += 1
                    else:
                        fail += 1

            resumo = {"ok": ok, "fail": fail, "total": len(clientes)}
            log.info("etl_finalizado", extra=resumo)
            return resumo
    except LockTaken:
        log.warning("etl_skip_lock_ocupado")
        return {"skipped": True}
```

- [ ] **Step 3: Rodar testes**

```bash
pytest tests/test_collect.py -v
```

Expected: passam.

- [ ] **Step 4: Commit**

```bash
git add web/backend/etl/collect.py web/backend/tests/test_collect.py
git commit -m "feat(etl): orchestrate snapshot collection from auto-report gathers"
```

---

### Task 4.5: Endpoint `/internal/etl/trigger` e CLI `schedule.py`

**Files:**
- Create: `web/backend/api/internal.py`
- Create: `web/backend/etl/schedule.py`
- Modify: `web/backend/main.py`

- [ ] **Step 1: Implementar endpoint interno**

```python
# web/backend/api/internal.py
from fastapi import APIRouter, Depends, Header, HTTPException

from ..config import Settings, get_settings
from ..etl.collect import run_etl

router = APIRouter()


def _require_token(
    x_etl_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.etl_trigger_token or x_etl_token != settings.etl_trigger_token:
        raise HTTPException(status_code=401, detail="Token inválido")


@router.post("/etl/trigger", dependencies=[Depends(_require_token)])
def trigger_etl() -> dict:
    return run_etl()
```

- [ ] **Step 2: Registrar em `main.py`**

```python
# main.py — ADIÇÃO
from .api import cases, health, internal, rankings
# ...
    app.include_router(internal.router, prefix="/internal")
```

- [ ] **Step 3: CLI `schedule.py`**

```python
# web/backend/etl/schedule.py
"""Entry point para o cron de produção: `python -m etl.schedule`."""
import logging
import sys

from .collect import run_etl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> int:
    resumo = run_etl()
    print(f"ETL finalizado: {resumo}")
    if resumo.get("fail", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Teste manual do endpoint**

```bash
cd web/backend
uvicorn main:app --reload &
sleep 2
curl -X POST http://localhost:8000/internal/etl/trigger -H "x-etl-token: dev-token-change-me"
```

Expected: JSON com `ok`/`fail`/`total` (mesmo se 0 clientes têm flag).

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/internal.py web/backend/etl/schedule.py web/backend/main.py
git commit -m "feat(etl): /internal/etl/trigger endpoint + schedule CLI"
```

---

## Fase 5 — Frontend Next.js

### Task 5.1: Bootstrap do projeto Next.js

**Files:**
- Create: `web/frontend/*` (estrutura inicial via `create-next-app`)

- [ ] **Step 1: Criar projeto Next.js**

```bash
cd /Users/mac0267/Documents/auto-report-main/web
npx create-next-app@14 frontend \
  --typescript \
  --tailwind \
  --app \
  --src-dir=false \
  --import-alias="@/*" \
  --eslint \
  --no-turbo
cd frontend
```

- [ ] **Step 2: Instalar dependências adicionais**

```bash
npm install recharts class-variance-authority clsx tailwind-merge lucide-react
npm install -D @types/node openapi-typescript vitest @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react playwright @playwright/test
```

- [ ] **Step 3: Configurar shadcn/ui**

```bash
npx shadcn@latest init -d
npx shadcn@latest add button card badge select
```

- [ ] **Step 4: Adicionar Dockerfile**

```dockerfile
# web/frontend/Dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:20-alpine AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 5: Atualizar `next.config.mjs` para standalone**

```js
// web/frontend/next.config.mjs
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
};
export default nextConfig;
```

- [ ] **Step 6: Verificar dev server**

```bash
cd web/frontend
npm run dev
# abrir http://localhost:3000 — deve mostrar página default do Next.js
```

- [ ] **Step 7: Commit**

```bash
git add web/frontend/
git commit -m "chore(frontend): bootstrap Next.js + Tailwind + shadcn"
```

---

### Task 5.2: Gerar tipos TypeScript do OpenAPI

**Files:**
- Create: `web/frontend/lib/types.ts` (gerado)
- Modify: `web/frontend/package.json` (script)

- [ ] **Step 1: Adicionar script ao `package.json`**

```json
{
  "scripts": {
    "types:openapi": "openapi-typescript http://localhost:8000/openapi.json -o lib/types.ts"
  }
}
```

- [ ] **Step 2: Rodar geração (backend precisa estar rodando)**

```bash
cd web
docker compose up -d backend
sleep 5
cd frontend
npm run types:openapi
```

Expected: `lib/types.ts` criado com interfaces `paths`, `components`, etc.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/lib/types.ts web/frontend/package.json
git commit -m "feat(frontend): generate TypeScript types from OpenAPI"
```

---

### Task 5.3: API client tipado (`lib/api.ts`)

**Files:**
- Create: `web/frontend/lib/api.ts`

- [ ] **Step 1: Implementar wrapper**

```typescript
// web/frontend/lib/api.ts
import type { paths } from "./types";

type CaseListResponse = paths["/api/cases"]["get"]["responses"]["200"]["content"]["application/json"];
type CaseDetail = paths["/api/cases/{slug}"]["get"]["responses"]["200"]["content"]["application/json"];
type RankingItem = paths["/api/rankings/{tipo}"]["get"]["responses"]["200"]["content"]["application/json"];

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error(`API ${path} retornou ${res.status}`);
  return res.json() as Promise<T>;
}

export type ListCasesParams = {
  categoria?: string;
  setor?: string;
  orderBy?: "roas" | "faturamento" | "crescimento";
  limit?: number;
  offset?: number;
};

export function listCases(params: ListCasesParams = {}): Promise<CaseListResponse> {
  const qs = new URLSearchParams();
  if (params.categoria) qs.set("categoria", params.categoria);
  if (params.setor) qs.set("setor", params.setor);
  if (params.orderBy) qs.set("order_by", params.orderBy);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.offset) qs.set("offset", String(params.offset));
  const suffix = qs.toString() ? `?${qs}` : "";
  return fetchJson<CaseListResponse>(`/api/cases${suffix}`);
}

export function getCase(slug: string): Promise<CaseDetail> {
  return fetchJson<CaseDetail>(`/api/cases/${slug}`);
}

export function getRanking(
  tipo: "roas" | "faturamento" | "crescimento",
  limit = 10,
): Promise<RankingItem> {
  return fetchJson<RankingItem>(`/api/rankings/${tipo}?limit=${limit}`);
}
```

- [ ] **Step 2: Commit**

```bash
git add web/frontend/lib/api.ts
git commit -m "feat(frontend): typed API client"
```

---

### Task 5.4: Formatadores PT-BR (`lib/format.ts`)

**Files:**
- Create: `web/frontend/lib/format.ts`
- Create: `web/frontend/tests/format.test.ts`

- [ ] **Step 1: Testes (RED)**

```typescript
// web/frontend/tests/format.test.ts
import { describe, expect, it } from "vitest";
import { formatBRL, formatRoas, formatPct, formatInt } from "../lib/format";

describe("formatBRL", () => {
  it("formata milhares", () => {
    expect(formatBRL("12345.67")).toBe("R$ 12.345,67");
  });
  it("formata zero", () => {
    expect(formatBRL("0")).toBe("R$ 0,00");
  });
  it("formata null/undefined", () => {
    expect(formatBRL(null)).toBe("—");
    expect(formatBRL(undefined)).toBe("—");
  });
});

describe("formatRoas", () => {
  it("acrescenta x", () => {
    expect(formatRoas("6.5")).toBe("6,5x");
  });
});

describe("formatPct", () => {
  it("formata positivo", () => {
    expect(formatPct("12.5")).toBe("+12,5%");
  });
  it("formata negativo", () => {
    expect(formatPct("-3.7")).toBe("-3,7%");
  });
});

describe("formatInt", () => {
  it("formata milhares", () => {
    expect(formatInt(1234)).toBe("1.234");
  });
});
```

Configurar Vitest:

```typescript
// web/frontend/vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true },
});
```

Adicionar ao `package.json`:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

Rodar:

```bash
npm test
```

Expected: FAIL — módulo não existe.

- [ ] **Step 2: Implementar `lib/format.ts`**

```typescript
// web/frontend/lib/format.ts
type MaybeNum = number | string | null | undefined;

function toNumber(v: MaybeNum): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

const brlFmt = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
});

const intFmt = new Intl.NumberFormat("pt-BR");

export function formatBRL(v: MaybeNum): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return brlFmt.format(n);
}

export function formatInt(v: MaybeNum): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return intFmt.format(n);
}

export function formatRoas(v: MaybeNum): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return `${n.toFixed(1).replace(".", ",")}x`;
}

export function formatPct(v: MaybeNum): string {
  const n = toNumber(v);
  if (n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1).replace(".", ",")}%`;
}
```

Rodar:

```bash
npm test
```

Expected: passam.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/lib/format.ts web/frontend/tests/format.test.ts web/frontend/vitest.config.ts web/frontend/package.json
git commit -m "feat(frontend): PT-BR formatters"
```

---

### Task 5.5: Componente `CaseCard`

**Files:**
- Create: `web/frontend/components/CaseCard.tsx`
- Create: `web/frontend/tests/CaseCard.test.tsx`

- [ ] **Step 1: Testes (RED)**

```tsx
// web/frontend/tests/CaseCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CaseCard } from "../components/CaseCard";

const item = {
  slug: "loja-fashion",
  nome: "Loja Fashion",
  logo_url: "/logos/loja.svg",
  categoria: "E-commerce",
  setor: "Moda",
  porte: "Médio",
  descricao_publica: "Cresceu 230% em 12 meses.",
  destaque: false,
  periodo_inicio: "2026-01-01",
  periodo_fim: "2026-01-31",
  faturamento: "1234567.89",
  investimento: "150000",
  roas: "6.5",
  cpa: null,
  leads: null,
  vendas: 80,
  faturamento_var_pct: "23.5",
  roas_var_pct: "4.8",
};

describe("CaseCard", () => {
  it("renderiza nome e métrica principal", () => {
    render(<CaseCard item={item as any} />);
    expect(screen.getByText("Loja Fashion")).toBeDefined();
    expect(screen.getByText("6,5x")).toBeDefined();
  });

  it("mostra crescimento de faturamento", () => {
    render(<CaseCard item={item as any} />);
    expect(screen.getByText(/\+23,5%/)).toBeDefined();
  });
});
```

Rodar:

```bash
npm test
```

Expected: FAIL — componente não existe.

- [ ] **Step 2: Implementar `CaseCard`**

```tsx
// web/frontend/components/CaseCard.tsx
import Link from "next/link";
import { formatBRL, formatPct, formatRoas } from "@/lib/format";

type CaseListItem = {
  slug: string;
  nome: string;
  logo_url: string | null;
  categoria: string;
  setor: string | null;
  descricao_publica: string | null;
  destaque: boolean;
  faturamento: string | null;
  roas: string | null;
  faturamento_var_pct: string | null;
};

export function CaseCard({ item }: { item: CaseListItem }) {
  return (
    <Link
      href={`/cases/${item.slug}`}
      className="group rounded-xl border bg-white p-6 shadow-sm transition hover:shadow-lg"
    >
      <div className="flex items-center gap-4">
        {item.logo_url && (
          <img src={item.logo_url} alt={item.nome} className="h-12 w-12 rounded object-contain" />
        )}
        <div>
          <h3 className="font-semibold">{item.nome}</h3>
          <p className="text-xs text-neutral-500">
            {item.categoria}{item.setor ? ` · ${item.setor}` : ""}
          </p>
        </div>
        {item.destaque && (
          <span className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
            Destaque
          </span>
        )}
      </div>

      <p className="mt-4 text-sm text-neutral-600 line-clamp-2">{item.descricao_publica}</p>

      <div className="mt-4 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs uppercase text-neutral-500">ROAS</p>
          <p className="text-2xl font-bold">{formatRoas(item.roas)}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-neutral-500">Faturamento</p>
          <p className="text-base font-medium">{formatBRL(item.faturamento)}</p>
          <p className="text-xs text-emerald-600">{formatPct(item.faturamento_var_pct)}</p>
        </div>
      </div>
    </Link>
  );
}
```

Rodar:

```bash
npm test
```

Expected: passam.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/CaseCard.tsx web/frontend/tests/CaseCard.test.tsx
git commit -m "feat(frontend): CaseCard component"
```

---

### Task 5.6: Página home (grid)

**Files:**
- Modify: `web/frontend/app/page.tsx`
- Create: `web/frontend/components/Filters.tsx`

- [ ] **Step 1: Implementar `Filters.tsx`**

```tsx
// web/frontend/components/Filters.tsx
"use client";
import { useRouter, useSearchParams } from "next/navigation";

const CATEGORIAS = ["", "E-commerce", "Lead Com Site", "Lead Sem Site"];
const ORDENS = [
  { value: "faturamento", label: "Maior faturamento" },
  { value: "roas", label: "Maior ROAS" },
  { value: "crescimento", label: "Maior crescimento" },
];

export function Filters() {
  const router = useRouter();
  const sp = useSearchParams();

  function update(key: string, value: string) {
    const next = new URLSearchParams(sp.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.push(`?${next.toString()}`);
  }

  return (
    <div className="mb-8 flex flex-wrap gap-4">
      <select
        defaultValue={sp.get("categoria") ?? ""}
        onChange={(e) => update("categoria", e.target.value)}
        className="rounded border px-3 py-2 text-sm"
      >
        {CATEGORIAS.map((c) => (
          <option key={c} value={c}>{c || "Todas as categorias"}</option>
        ))}
      </select>

      <select
        defaultValue={sp.get("order_by") ?? "faturamento"}
        onChange={(e) => update("order_by", e.target.value)}
        className="rounded border px-3 py-2 text-sm"
      >
        {ORDENS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}
```

- [ ] **Step 2: Implementar `app/page.tsx`**

```tsx
// web/frontend/app/page.tsx
import { CaseCard } from "@/components/CaseCard";
import { Filters } from "@/components/Filters";
import { listCases } from "@/lib/api";

export const revalidate = 3600;

type SearchParams = {
  categoria?: string;
  order_by?: "roas" | "faturamento" | "crescimento";
};

export default async function HomePage({ searchParams }: { searchParams: SearchParams }) {
  const data = await listCases({
    categoria: searchParams.categoria,
    orderBy: searchParams.order_by ?? "faturamento",
    limit: 50,
  });

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      <header className="mb-12">
        <h1 className="text-4xl font-bold tracking-tight">Cases de sucesso</h1>
        <p className="mt-3 max-w-2xl text-neutral-600">
          Resultados reais dos nossos clientes em mídia paga e analytics.
        </p>
      </header>

      <Filters />

      {data.items.length === 0 ? (
        <p className="text-neutral-500">Nenhum case encontrado.</p>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((item) => (
            <CaseCard key={item.slug} item={item as any} />
          ))}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Validar com dev server**

```bash
# (backend rodando + seed populado)
cd web/frontend
npm run dev
# abrir http://localhost:3000
```

Expected: grid com clientes do seed (Loja Fashion + Dental Care).

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/page.tsx web/frontend/components/Filters.tsx
git commit -m "feat(frontend): home page with grid and filters"
```

---

### Task 5.7: Componente `MetricGrid` + `EvolutionChart`

**Files:**
- Create: `web/frontend/components/MetricGrid.tsx`
- Create: `web/frontend/components/EvolutionChart.tsx`
- Create: `web/frontend/tests/MetricGrid.test.tsx`

- [ ] **Step 1: Teste do `MetricGrid` (RED)**

```tsx
// web/frontend/tests/MetricGrid.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetricGrid } from "../components/MetricGrid";

describe("MetricGrid", () => {
  it("renderiza todas as métricas com valor", () => {
    render(
      <MetricGrid
        snapshot={{
          faturamento: "1000000",
          investimento: "100000",
          roas: "10",
          cpa: "85",
          leads: 200,
          vendas: 80,
          faturamento_var_pct: "23",
          roas_var_pct: "5",
        } as any}
      />,
    );
    expect(screen.getByText(/R\$ 1\.000\.000,00/)).toBeDefined();
    expect(screen.getByText(/10,0x/)).toBeDefined();
    expect(screen.getByText(/80/)).toBeDefined();
  });

  it("oculta métricas null", () => {
    render(<MetricGrid snapshot={{ faturamento: "100", roas: null, cpa: null } as any} />);
    expect(screen.queryByText("ROAS")).toBeNull();
  });
});
```

- [ ] **Step 2: Implementar `MetricGrid`**

```tsx
// web/frontend/components/MetricGrid.tsx
import { formatBRL, formatInt, formatPct, formatRoas } from "@/lib/format";

type Snapshot = {
  faturamento?: string | null;
  investimento?: string | null;
  roas?: string | null;
  cpa?: string | null;
  leads?: number | null;
  vendas?: number | null;
  faturamento_var_pct?: string | null;
  roas_var_pct?: string | null;
};

type MetricDef = {
  key: keyof Snapshot;
  label: string;
  format: (v: any) => string;
  variation?: keyof Snapshot;
};

const METRICS: MetricDef[] = [
  { key: "faturamento", label: "Faturamento", format: formatBRL, variation: "faturamento_var_pct" },
  { key: "investimento", label: "Investimento", format: formatBRL },
  { key: "roas", label: "ROAS", format: formatRoas, variation: "roas_var_pct" },
  { key: "cpa", label: "CPA", format: formatBRL },
  { key: "vendas", label: "Vendas", format: formatInt },
  { key: "leads", label: "Leads", format: formatInt },
];

export function MetricGrid({ snapshot }: { snapshot: Snapshot }) {
  return (
    <div className="grid gap-6 sm:grid-cols-3">
      {METRICS.filter((m) => snapshot[m.key] != null).map((m) => (
        <div key={m.key as string} className="rounded-lg border bg-white p-5">
          <p className="text-xs uppercase tracking-wider text-neutral-500">{m.label}</p>
          <p className="mt-1 text-2xl font-bold">{m.format(snapshot[m.key])}</p>
          {m.variation && snapshot[m.variation] != null && (
            <p className="mt-1 text-sm text-emerald-600">{formatPct(snapshot[m.variation] as string)}</p>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Implementar `EvolutionChart`**

```tsx
// web/frontend/components/EvolutionChart.tsx
"use client";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Ponto = {
  periodo_fim: string;
  faturamento?: string | null;
  roas?: string | null;
};

export function EvolutionChart({ pontos }: { pontos: Ponto[] }) {
  const data = pontos.map((p) => ({
    mes: new Date(p.periodo_fim).toLocaleDateString("pt-BR", { month: "short", year: "2-digit" }),
    faturamento: p.faturamento ? Number(p.faturamento) : null,
    roas: p.roas ? Number(p.roas) : null,
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data}>
          <XAxis dataKey="mes" />
          <YAxis />
          <Tooltip
            formatter={(v: any) => (typeof v === "number" ? v.toLocaleString("pt-BR") : v)}
          />
          <Line type="monotone" dataKey="faturamento" stroke="#2563eb" strokeWidth={2} dot />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: Rodar testes**

```bash
npm test
```

Expected: passam.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/components/MetricGrid.tsx web/frontend/components/EvolutionChart.tsx web/frontend/tests/MetricGrid.test.tsx
git commit -m "feat(frontend): MetricGrid + EvolutionChart"
```

---

### Task 5.8: Página detalhada `/cases/[slug]`

**Files:**
- Create: `web/frontend/app/cases/[slug]/page.tsx`
- Create: `web/frontend/components/FontDetail.tsx`

- [ ] **Step 1: Implementar `FontDetail`**

```tsx
// web/frontend/components/FontDetail.tsx
import { formatBRL, formatInt, formatRoas } from "@/lib/format";

const FONTES = [
  { key: "meta", label: "Meta Ads" },
  { key: "google", label: "Google Ads" },
  { key: "ga4", label: "GA4" },
  { key: "painel", label: "Painel" },
];

type Detalhes = Record<string, Record<string, any>>;

export function FontDetail({ detalhes }: { detalhes: Detalhes }) {
  return (
    <section className="mt-12">
      <h2 className="text-xl font-bold">Detalhamento por fonte</h2>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {FONTES.filter((f) => detalhes[f.key]).map((f) => (
          <div key={f.key} className="rounded-lg border bg-white p-5">
            <h3 className="font-semibold">{f.label}</h3>
            <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
              {Object.entries(detalhes[f.key]).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-neutral-500">{k}</dt>
                  <dd className="font-medium">
                    {k === "roas" ? formatRoas(v) :
                     ["faturamento", "investimento", "cpa"].includes(k) ? formatBRL(v) :
                     formatInt(v)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Implementar página**

```tsx
// web/frontend/app/cases/[slug]/page.tsx
import { notFound } from "next/navigation";

import { EvolutionChart } from "@/components/EvolutionChart";
import { FontDetail } from "@/components/FontDetail";
import { MetricGrid } from "@/components/MetricGrid";
import { getCase } from "@/lib/api";

export const revalidate = 3600;

export default async function CaseDetailPage({ params }: { params: { slug: string } }) {
  let detail;
  try {
    detail = await getCase(params.slug);
  } catch {
    notFound();
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-12 flex items-center gap-6">
        {detail.logo_url && (
          <img src={detail.logo_url} alt={detail.nome} className="h-20 w-20 rounded object-contain" />
        )}
        <div>
          <h1 className="text-3xl font-bold">{detail.nome}</h1>
          <p className="mt-1 text-sm text-neutral-500">
            {detail.categoria}
            {detail.setor ? ` · ${detail.setor}` : ""}
            {detail.porte ? ` · ${detail.porte}` : ""}
          </p>
          {detail.descricao_publica && (
            <p className="mt-3 max-w-2xl text-neutral-700">{detail.descricao_publica}</p>
          )}
        </div>
      </header>

      <section>
        <h2 className="mb-6 text-xl font-bold">Métricas do último mês</h2>
        <MetricGrid snapshot={detail as any} />
      </section>

      <section className="mt-12">
        <h2 className="mb-6 text-xl font-bold">Evolução</h2>
        <EvolutionChart pontos={detail.evolucao as any} />
      </section>

      <FontDetail detalhes={(detail.metricas_detalhadas ?? {}) as any} />
    </main>
  );
}
```

- [ ] **Step 3: Verificar manualmente**

```bash
cd web/frontend
npm run dev
# abrir http://localhost:3000/cases/loja-fashion
```

Expected: header com logo/nome, métricas, gráfico, detalhes por fonte.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/cases/ web/frontend/components/FontDetail.tsx
git commit -m "feat(frontend): case detail page"
```

---

### Task 5.9: Layout global e estilo

**Files:**
- Modify: `web/frontend/app/layout.tsx`
- Modify: `web/frontend/app/globals.css`

- [ ] **Step 1: Layout com header/footer**

```tsx
// web/frontend/app/layout.tsx
import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Cases de sucesso",
  description: "Resultados reais dos nossos clientes em marketing digital.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <header className="border-b bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-lg font-bold">Cases</Link>
            <nav className="text-sm text-neutral-600">
              <Link href="/" className="hover:text-neutral-900">Vitrine</Link>
            </nav>
          </div>
        </header>
        {children}
        <footer className="mt-24 border-t bg-white">
          <div className="mx-auto max-w-7xl px-6 py-8 text-sm text-neutral-500">
            © {new Date().getFullYear()} — Cases publicados com autorização dos clientes.
          </div>
        </footer>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Verificar visual**

Abrir `localhost:3000` e `localhost:3000/cases/loja-fashion`. Layout consistente, header e footer presentes.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/app/layout.tsx web/frontend/app/globals.css
git commit -m "feat(frontend): site layout with header/footer"
```

---

## Fase 6 — Testes E2E e observabilidade

### Task 6.1: E2E Playwright (golden path)

**Files:**
- Create: `web/frontend/tests/e2e/golden.spec.ts`
- Create: `web/frontend/playwright.config.ts`

- [ ] **Step 1: Config Playwright**

```typescript
// web/frontend/playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
  },
});
```

- [ ] **Step 2: Teste do golden path**

```typescript
// web/frontend/tests/e2e/golden.spec.ts
import { expect, test } from "@playwright/test";

test("visitante navega da home para detalhe de case", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Cases de sucesso")).toBeVisible();

  // Clica no primeiro card
  const primeiro = page.locator("a[href^='/cases/']").first();
  await expect(primeiro).toBeVisible();
  await primeiro.click();

  // Página detalhada tem métricas e gráfico
  await expect(page.getByText("Métricas do último mês")).toBeVisible();
  await expect(page.getByText("Evolução")).toBeVisible();
});

test("filtro por categoria refina lista", async ({ page }) => {
  await page.goto("/?categoria=E-commerce");
  // Deve haver pelo menos 1 case (seed contém um e-commerce)
  await expect(page.locator("a[href^='/cases/']").first()).toBeVisible();
});
```

- [ ] **Step 3: Adicionar script ao `package.json`**

```json
{
  "scripts": {
    "test:e2e": "playwright test"
  }
}
```

- [ ] **Step 4: Instalar browsers do Playwright**

```bash
cd web/frontend
npx playwright install chromium
```

- [ ] **Step 5: Rodar (backend + frontend rodando, com seed)**

```bash
# em outro terminal: docker compose up backend postgres
npm run test:e2e
```

Expected: 2 testes passam.

- [ ] **Step 6: Commit**

```bash
git add web/frontend/tests/e2e/ web/frontend/playwright.config.ts web/frontend/package.json
git commit -m "test(frontend): E2E golden path with Playwright"
```

---

### Task 6.2: Logs estruturados no backend

**Files:**
- Modify: `web/backend/main.py`
- Create: `web/backend/logging_config.py`

- [ ] **Step 1: Implementar configuração**

```python
# web/backend/logging_config.py
import logging
import sys

import structlog


def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    # Redireciona stdlib logging para structlog
    logging.basicConfig(format="%(message)s", level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
```

- [ ] **Step 2: Chamar no startup do FastAPI**

```python
# web/backend/main.py — adição
from contextlib import asynccontextmanager
from .logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vitrine de Cases API", version="0.1.0", lifespan=lifespan)
    # ...
```

- [ ] **Step 3: Smoke test**

```bash
cd web/backend
uvicorn main:app
# em outro terminal
curl http://localhost:8000/api/health
```

Expected: log em JSON no stdout do servidor.

- [ ] **Step 4: Commit**

```bash
git add web/backend/logging_config.py web/backend/main.py
git commit -m "feat(backend): structured JSON logging"
```

---

### Task 6.3: Alerta de falha no ETL

**Files:**
- Create: `web/backend/etl/alerting.py`
- Modify: `web/backend/etl/collect.py`

- [ ] **Step 1: Implementar webhook**

```python
# web/backend/etl/alerting.py
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)


def alert(resumo: dict) -> None:
    """Envia webhook se houver falhas no ETL. Sem webhook configurado, é noop."""
    url = os.getenv("ETL_ALERT_WEBHOOK_URL")
    if not url:
        return

    fail = resumo.get("fail", 0)
    total = resumo.get("total", 0)
    if total == 0 or fail == 0:
        return

    pct = fail / total
    if pct < 0.1:
        return  # ruído OK; só alerta se >10% falhou

    msg = f"⚠️ ETL vitrine: {fail}/{total} clientes falharam ({pct:.0%})"
    try:
        httpx.post(url, json={"text": msg}, timeout=10)
    except Exception:
        log.exception("falha_envio_alerta")
```

- [ ] **Step 2: Chamar no fim do `run_etl`**

```python
# web/backend/etl/collect.py — modificar run_etl
from .alerting import alert

# logo antes do return:
            log.info("etl_finalizado", extra=resumo)
            alert(resumo)
            return resumo
```

- [ ] **Step 3: Commit**

```bash
git add web/backend/etl/alerting.py web/backend/etl/collect.py
git commit -m "feat(etl): webhook alert on >10% failure rate"
```

---

## Fase 7 — Deploy

### Task 7.1: CI GitHub Actions

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Implementar workflow**

```yaml
# .github/workflows/ci.yml
name: ci

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: vitrine
          POSTGRES_PASSWORD: vitrine
          POSTGRES_DB: vitrine
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r web/backend/requirements.txt
      - run: cd web/backend && alembic upgrade head
        env:
          DATABASE_URL: postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine
      - run: cd web/backend && pytest -v
        env:
          DATABASE_URL: postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: web/frontend/package-lock.json
      - run: cd web/frontend && npm ci
      - run: cd web/frontend && npm test
      - run: cd web/frontend && npm run build
```

- [ ] **Step 2: Push e validar**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflow"
git push
# checar Actions tab no GitHub
```

Expected: jobs `backend` e `frontend` verdes.

---

### Task 7.2: Deploy do backend (Cloud Run / Fly.io)

**Files:**
- Create: `web/backend/.gcloudignore` ou `fly.toml` (depende do escolhido)

Esta task assume Cloud Run. Adapte para Fly.io se preferir.

- [ ] **Step 1: Build da imagem**

```bash
cd /Users/mac0267/Documents/auto-report-main
docker build -f web/backend/Dockerfile -t vitrine-backend:latest .
```

- [ ] **Step 2: Push para Artifact Registry**

```bash
PROJECT=<seu-gcp-project>
REGION=us-central1
docker tag vitrine-backend:latest $REGION-docker.pkg.dev/$PROJECT/vitrine/backend:latest
docker push $REGION-docker.pkg.dev/$PROJECT/vitrine/backend:latest
```

- [ ] **Step 3: Provisionar Postgres (Cloud SQL)**

Console GCP → Cloud SQL → criar instância Postgres 15. Anotar connection string.

- [ ] **Step 4: Rodar migrations contra prod**

```bash
DATABASE_URL=<connection-string-prod> alembic upgrade head
```

- [ ] **Step 5: Deploy no Cloud Run**

```bash
gcloud run deploy vitrine-backend \
  --image=$REGION-docker.pkg.dev/$PROJECT/vitrine/backend:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=<...>,CORS_ORIGINS=[\"https://cases.exemplo.com\"],ETL_TRIGGER_TOKEN=<gerar-token-seguro>"
```

- [ ] **Step 6: Smoke test**

```bash
curl https://<url-cloud-run>/api/health
```

Expected: `{"status":"ok"}`.

- [ ] **Step 7: Documentar URLs no README**

Adicione a `web/README.md`:

```markdown
## URLs de produção
- Backend: https://<url>
- Frontend: https://<dominio>

## Comandos comuns
- `docker compose up -d` — dev local
- `alembic upgrade head` — aplicar migrations
- `python -m etl.schedule` — rodar ETL manualmente
```

Commit:

```bash
git add web/README.md
git commit -m "docs(web): add prod URLs and common commands"
```

---

### Task 7.3: Deploy do frontend (Vercel)

- [ ] **Step 1: Conectar repo na Vercel**

Console Vercel → Add New Project → import do GitHub. Root directory: `web/frontend`. Framework: Next.js (autodetect).

- [ ] **Step 2: Configurar env var**

`NEXT_PUBLIC_API_URL=https://<url-do-backend-cloud-run>`

- [ ] **Step 3: Trigger deploy**

Push para `main` ou clicar "Deploy" no painel.

- [ ] **Step 4: Validar**

Acessar URL gerada (`<projeto>.vercel.app` ou domínio próprio). Conferir que a home carrega e cases aparecem.

- [ ] **Step 5: Configurar domínio (opcional)**

Vercel → Settings → Domains → adicionar `cases.exemplo.com`. Configurar DNS.

---

### Task 7.4: Cron de produção

Esta task assume Cloud Scheduler. Alternativas: GitHub Actions cron, k8s CronJob, crontab no VPS.

- [ ] **Step 1: Criar job no Cloud Scheduler**

```bash
gcloud scheduler jobs create http vitrine-etl-diario \
  --location=$REGION \
  --schedule="0 4 * * *" \
  --time-zone="America/Sao_Paulo" \
  --uri="https://<url-cloud-run>/internal/etl/trigger" \
  --http-method=POST \
  --headers="x-etl-token=<token>" \
  --attempt-deadline=30m
```

- [ ] **Step 2: Disparar manualmente para validar**

```bash
gcloud scheduler jobs run vitrine-etl-diario --location=$REGION
# acompanhar logs do Cloud Run
```

Expected: log `etl_finalizado` com `ok > 0`.

- [ ] **Step 3: Documentar no README**

Adicione seção "Operação" ao `web/README.md` explicando como pausar/disparar o cron manualmente.

---

## Apêndice — Notas de integração com o `core/` existente

APIs do auto-report que este plano consome (verificadas em 2026-05-20):

| API | Localização | Assinatura |
|-----|-------------|------------|
| `fetch_clientes(*, atualizar, only, sheet_url, tab_name) -> list[Cliente]` | `core/leitura_central.py` | Keyword-only |
| `Cliente` dataclass | `core/leitura_central.py` linha ~74 | Campos: `nome`, `categoria`, `painel_url`, `pasta_url`, `id_google_ads`, `id_meta_ads`, `id_ga4`, `email`, `extras`. **Não tem `slug` nativo** — o ETL deriva via `_slugify(c.nome)`. |
| `get_handler(nome: str) -> module` | `core/categorias/__init__.py` linha 27 | Retorna módulo handler para a categoria |
| `handler.coletar_dados(cliente, periodo_ref, periodo_comp) -> dict` | Cada handler em `core/categorias/*.py` | Retorna dict `{ "{{placeholder}}": "valor_pt_br" }` |
| `Frequencia` enum | `core/periodo.py` linha 49 | `SEMANAL` \| `MENSAL` |
| `Periodo` dataclass | `core/periodo.py` linha ~70 | Campos: `inicio`, `fim`, `fim_plus_1`, `extra`. **Não tem `nome`/`frequencia`** — a frequência precisa ser passada explicitamente em paralelo ao `Periodo`. |
| `periodo_referencia(today, frequencia) -> Periodo` | `core/periodo.py` | `frequencia` é string (`"MENSAL"`/`"SEMANAL"`) |
| `CENTRAL_SHEET_URL`, `CENTRAL_TAB_NAME` | `config/settings.py` linhas 36-37 | Constantes do auto-report |

**Implicações:**
- O `Cliente` do core não persiste — é um value object da planilha. O modelo `Cliente` do backend é a entidade durável.
- Existe risco de duplicação se o cliente for renomeado: o slug derivado mudaria. Mitigação: registrar `slug_anterior` se for um problema real (fora do MVP).
- A planilha controla autoritariamente o opt-in. Se o cliente sair, o ETL apenas para de atualizar seu snapshot — o último permanece no DB até a Task de cleanup ser adicionada (fora do MVP). Para remoção imediata, atualizar `clientes.publicar_vitrine = false` direto no DB ou usar o endpoint `/internal/cache/purge` (também fora do MVP).
