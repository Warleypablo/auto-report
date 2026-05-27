# Central de Inteligência — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Painel `/gestor/inteligencia` que mostra portfólio KPIs + feed de alertas com sinais objetivos (regras) e narrativa explicativa gerada por IA (Claude Haiku), computados em batch mensalmente via endpoint admin.

**Architecture:** Signal Registry em `services/inteligencia.py` detecta padrões nos snapshots existentes usando funções puras (sem acesso a DB). Endpoint admin `POST /gestor/inteligencia/generate` carrega dados em bulk, roda os detectores, chama a Claude API e persiste na tabela `insights`. Endpoint `GET /gestor/inteligencia` serve os alertas com filtro por gestor. Frontend segue o padrão de `performance/page.tsx`.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + Anthropic Python SDK (backend), Next.js 14 App Router `"use client"` (frontend), PostgreSQL JSONB (sinais), `claude-haiku-4-5-20251001` (geração de narrativa).

---

## Mapa de arquivos

| Ação | Arquivo |
|---|---|
| Criar | `web/backend/models/insight.py` |
| Modificar | `web/backend/models/__init__.py` |
| Criar | `web/backend/alembic/versions/<rev>_add_insights.py` |
| Modificar | `web/backend/app_settings.py` |
| Modificar | `web/backend/requirements.txt` |
| Criar | `web/backend/services/inteligencia.py` |
| Criar | `web/backend/tests/test_inteligencia.py` |
| Modificar | `web/backend/schemas/gestor.py` |
| Modificar | `web/backend/api/gestor.py` |
| Modificar | `web/frontend/lib/api-gestor.ts` |
| Criar | `web/frontend/app/gestor/inteligencia/page.tsx` |
| Modificar | `web/frontend/app/gestor/page.tsx` |

---

## Task 1: Model Insight + Migration + Dependências

**Files:**
- Create: `web/backend/models/insight.py`
- Modify: `web/backend/models/__init__.py`
- Create: `web/backend/alembic/versions/<rev>_add_insights.py`
- Modify: `web/backend/app_settings.py`
- Modify: `web/backend/requirements.txt`

### Contexto necessário

O projeto usa SQLAlchemy 2.x com `Mapped`/`mapped_column`, PostgreSQL JSONB, e Alembic para migrations. Veja `web/backend/models/gestor.py` para o padrão exato. O `.env` e `app_settings.py` usam `pydantic-settings`; adicionar campo lá faz ele ser lido automaticamente do ambiente.

- [ ] **Step 1: Escrever o teste de importação do modelo**

Crie `web/backend/tests/test_inteligencia.py`:

```python
def test_insight_model_importavel():
    from models.insight import Insight
    assert Insight.__tablename__ == "insights"
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```bash
cd web/backend && python -m pytest tests/test_inteligencia.py -v
```

Expected: `FAILED` com `ModuleNotFoundError: No module named 'models.insight'`

- [ ] **Step 3: Criar `web/backend/models/insight.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        UniqueConstraint("cliente_id", "mes", name="uq_insight_cliente_mes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mes: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    sinais: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    narrativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    gerado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cliente: Mapped["Cliente"] = relationship("Cliente")
```

- [ ] **Step 4: Adicionar `Insight` ao `web/backend/models/__init__.py`**

```python
from .base import Base
from .cliente import Categoria, Cliente
from .gestor import GestorCadastrado
from .insight import Insight
from .report_job import JobStatus, ReportJob
from .snapshot import Frequencia, Snapshot
from .usuario import Usuario
from .usuario_cliente import UsuarioCliente

__all__ = [
    "Base",
    "Categoria",
    "Cliente",
    "Frequencia",
    "GestorCadastrado",
    "Insight",
    "JobStatus",
    "ReportJob",
    "Snapshot",
    "Usuario",
    "UsuarioCliente",
]
```

- [ ] **Step 5: Rodar o teste para confirmar que passa**

```bash
cd web/backend && python -m pytest tests/test_inteligencia.py::test_insight_model_importavel -v
```

Expected: `PASSED`

- [ ] **Step 6: Gerar a migration**

```bash
cd web/backend && alembic revision --autogenerate -m "add_insights"
```

Alembic vai gerar um arquivo em `alembic/versions/<hash>_add_insights.py`. O conteúdo do `upgrade()` gerado deve conter:

```python
op.create_table('insights',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('cliente_id', sa.UUID(), nullable=False),
    sa.Column('mes', sa.String(length=7), nullable=False),
    sa.Column('sinais', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('narrativa', sa.Text(), nullable=True),
    sa.Column('gerado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cliente_id', 'mes', name='uq_insight_cliente_mes')
)
op.create_index(op.f('ix_insights_cliente_id'), 'insights', ['cliente_id'], unique=False)
op.create_index(op.f('ix_insights_mes'), 'insights', ['mes'], unique=False)
```

Se o autogenerate não incluir os índices, adicione-os manualmente ao arquivo gerado.

- [ ] **Step 7: Aplicar a migration**

```bash
cd web/backend && alembic upgrade head
```

Expected: `Running upgrade ... -> <rev>, add_insights`

- [ ] **Step 8: Adicionar `anthropic` ao `requirements.txt`**

Adicione no final do arquivo `web/backend/requirements.txt`:

```
anthropic>=0.40.0
```

- [ ] **Step 9: Instalar a dependência**

```bash
cd web/backend && pip install anthropic>=0.40.0
```

Expected: `Successfully installed anthropic-...`

- [ ] **Step 10: Adicionar `anthropic_api_key` ao `app_settings.py`**

```python
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
    cliente_password: str = Field(default="Warley20192020")
    anthropic_api_key: str = Field(default="")
```

- [ ] **Step 11: Adicionar `ANTHROPIC_API_KEY` ao `.env`**

Adicione ao `web/backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...  # sua chave real aqui
```

- [ ] **Step 12: Commit**

```bash
git add web/backend/models/insight.py \
        web/backend/models/__init__.py \
        web/backend/alembic/versions/*_add_insights.py \
        web/backend/app_settings.py \
        web/backend/requirements.txt \
        web/backend/tests/test_inteligencia.py
git commit -m "feat(inteligencia): modelo Insight + migration + dependência anthropic"
```

---

## Task 2: Signal Registry

**Files:**
- Create: `web/backend/services/inteligencia.py`
- Modify: `web/backend/tests/test_inteligencia.py`

### Contexto necessário

Os detectores recebem dados pré-carregados (sem acesso ao DB). O `breakdown` é o resultado de `build_breakdown()` — dict com `meta_ads` e `google_ads`, cada ad com campos `nome`, `roas`, `investimento`, `faturamento`, etc. O `snap_atual` e `snap_anterior` são objetos `Snapshot` (ou `None`). Campos numéricos em `Snapshot` são `Decimal` ou `None`.

- [ ] **Step 1: Escrever os testes dos detectores**

Adicione ao `web/backend/tests/test_inteligencia.py`:

```python
import pytest


# ── Fixtures de breakdown ──────────────────────────────────────────────────

def _bd_brand():
    """Breakdown com campanha brand (ROAS 577×) e campanha shopping (ROAS 32×)."""
    return {
        "google_ads": [
            {"nome": "[TP] - [Inst] - [09/10]", "roas": 577.57, "investimento": 74.75,
             "faturamento": 43175.90, "conversoes": 37.49, "cpa": 1.99, "impressoes": 4323},
            {"nome": "[TP] - [Shop] - [26/08]", "roas": 32.80, "investimento": 7919.96,
             "faturamento": 259813.29, "conversoes": 199.88, "cpa": 39.62, "impressoes": 828660},
        ],
        "meta_ads": [],
    }


def _bd_vazio():
    return {"google_ads": [], "meta_ads": []}


# ── Testes detectar_roas_brand_inflado ─────────────────────────────────────

def test_roas_brand_inflado_dispara():
    from services.inteligencia import detectar_roas_brand_inflado
    sinal = detectar_roas_brand_inflado(_bd_brand())
    assert sinal is not None
    assert sinal["tipo"] == "roas_brand_inflado"
    assert sinal["severidade"] == "atencao"
    assert sinal["contexto"]["roas_sem_brand"] == pytest.approx(32.80, rel=0.02)


def test_roas_brand_inflado_nao_dispara_sem_brand():
    from services.inteligencia import detectar_roas_brand_inflado
    bd = {
        "google_ads": [
            {"nome": "[TP] - [Shop] - [26/08]", "roas": 32.80, "investimento": 7919.96,
             "faturamento": 259813.29, "conversoes": 199.88, "cpa": 39.62, "impressoes": 828660},
        ],
        "meta_ads": [],
    }
    assert detectar_roas_brand_inflado(bd) is None


def test_roas_brand_inflado_nao_dispara_roas_baixo():
    from services.inteligencia import detectar_roas_brand_inflado
    bd = {
        "google_ads": [
            {"nome": "[TP] - [Brand] - [01/01]", "roas": 8.0, "investimento": 500.0,
             "faturamento": 4000.0, "conversoes": 10, "cpa": 50.0, "impressoes": 1000},
        ],
        "meta_ads": [],
    }
    assert detectar_roas_brand_inflado(bd) is None


# ── Testes detectar_roas_queda ─────────────────────────────────────────────

def test_roas_queda_dispara():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_queda

    class FakeSnap:
        roas = None

    atual = FakeSnap(); atual.roas = Decimal("5.7")
    anterior = FakeSnap(); anterior.roas = Decimal("8.4")
    sinal = detectar_roas_queda(atual, anterior)
    assert sinal is not None
    assert sinal["tipo"] == "roas_queda"
    assert sinal["severidade"] == "critico"


def test_roas_queda_nao_dispara_queda_pequena():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_queda

    class FakeSnap:
        roas = None

    atual = FakeSnap(); atual.roas = Decimal("8.0")
    anterior = FakeSnap(); anterior.roas = Decimal("8.5")
    assert detectar_roas_queda(atual, anterior) is None


def test_roas_queda_nao_dispara_sem_anterior():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_queda

    class FakeSnap:
        roas = None

    atual = FakeSnap(); atual.roas = Decimal("5.0")
    assert detectar_roas_queda(atual, None) is None


# ── Testes detectar_roas_abaixo_limiar ─────────────────────────────────────

def test_roas_abaixo_limiar_dispara():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_abaixo_limiar

    class FakeSnap:
        roas = None

    snap = FakeSnap(); snap.roas = Decimal("1.2")
    assert detectar_roas_abaixo_limiar(snap) is not None


def test_roas_abaixo_limiar_nao_dispara_acima():
    from decimal import Decimal
    from services.inteligencia import detectar_roas_abaixo_limiar

    class FakeSnap:
        roas = None

    snap = FakeSnap(); snap.roas = Decimal("2.5")
    assert detectar_roas_abaixo_limiar(snap) is None


# ── Testes detectar_investimento_parado ───────────────────────────────────

def test_investimento_parado_dispara():
    from services.inteligencia import detectar_investimento_parado
    assert detectar_investimento_parado(None) is not None


def test_investimento_parado_nao_dispara_com_snap():
    from decimal import Decimal
    from services.inteligencia import detectar_investimento_parado

    class FakeSnap:
        investimento = Decimal("1000.0")

    assert detectar_investimento_parado(FakeSnap()) is None


# ── Testes rodar_detectores (pipeline completo) ────────────────────────────

def test_rodar_detectores_retorna_lista():
    from decimal import Decimal
    from services.inteligencia import rodar_detectores

    class FakeSnap:
        roas = Decimal("5.7")
        investimento = Decimal("7000.0")
        faturamento = Decimal("40000.0")

    sinais = rodar_detectores(
        snap_atual=FakeSnap(),
        snap_anterior=None,
        breakdown=_bd_brand(),
        media_investimento_carteira=5000.0,
    )
    assert isinstance(sinais, list)
    assert any(s["tipo"] == "roas_brand_inflado" for s in sinais)
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
cd web/backend && python -m pytest tests/test_inteligencia.py -v --ignore=tests/test_inteligencia.py -k "not importavel"
```

Expected: múltiplos `FAILED` com `ImportError`

- [ ] **Step 3: Implementar `web/backend/services/inteligencia.py`**

```python
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

_BRAND_RE = re.compile(r'\[inst\]|\[brand\]|\[marc\]', re.IGNORECASE)


# ── Detectores individuais (funções puras, sem acesso ao DB) ──────────────

def detectar_roas_brand_inflado(breakdown: dict) -> dict | None:
    """Campanha com padrão brand ([Inst]/[Brand]/[Marc]) e ROAS > 50×."""
    google_ads = breakdown.get("google_ads") or []
    brand = [ad for ad in google_ads if _BRAND_RE.search(ad.get("nome") or "")]
    if not brand:
        return None
    pior = max(brand, key=lambda ad: ad.get("roas") or 0)
    if not pior.get("roas") or pior["roas"] <= 50:
        return None
    outras = [ad for ad in google_ads if ad not in brand]
    fat = sum(ad.get("faturamento") or 0 for ad in outras)
    inv = sum(ad.get("investimento") or 0 for ad in outras)
    roas_sem_brand = round(fat / inv, 2) if inv > 0 else None
    return {
        "tipo": "roas_brand_inflado",
        "severidade": "atencao",
        "titulo": "ROAS inflado por campanha brand",
        "metrica_principal": f"{pior['roas']:.2f}×",
        "contexto": {
            "campanha": pior["nome"],
            "investimento": pior.get("investimento"),
            "faturamento": pior.get("faturamento"),
            "roas_sem_brand": roas_sem_brand,
        },
    }


def detectar_roas_queda(snap_atual, snap_anterior) -> dict | None:
    """ROAS caiu mais de 20% em relação ao mês anterior."""
    if snap_anterior is None or snap_anterior.roas is None:
        return None
    if snap_atual is None or snap_atual.roas is None:
        return None
    roas_ant = float(snap_anterior.roas)
    roas_atu = float(snap_atual.roas)
    if roas_ant == 0:
        return None
    queda = (roas_ant - roas_atu) / roas_ant
    if queda < 0.20:
        return None
    return {
        "tipo": "roas_queda",
        "severidade": "critico",
        "titulo": f"ROAS caiu {queda * 100:.0f}% vs. mês anterior",
        "metrica_principal": f"{roas_atu:.2f}×",
        "contexto": {
            "roas_atual": round(roas_atu, 2),
            "roas_anterior": round(roas_ant, 2),
            "queda_pct": round(queda * 100, 1),
        },
    }


def detectar_faturamento_queda(snap_atual, snap_anterior) -> dict | None:
    """Faturamento caiu mais de 25% em relação ao mês anterior."""
    if snap_anterior is None or snap_anterior.faturamento is None:
        return None
    if snap_atual is None or snap_atual.faturamento is None:
        return None
    fat_ant = float(snap_anterior.faturamento)
    fat_atu = float(snap_atual.faturamento)
    if fat_ant == 0:
        return None
    queda = (fat_ant - fat_atu) / fat_ant
    if queda < 0.25:
        return None
    return {
        "tipo": "faturamento_queda",
        "severidade": "critico",
        "titulo": f"Faturamento caiu {queda * 100:.0f}% vs. mês anterior",
        "metrica_principal": f"R${fat_atu:,.0f}",
        "contexto": {
            "faturamento_atual": round(fat_atu, 2),
            "faturamento_anterior": round(fat_ant, 2),
            "queda_pct": round(queda * 100, 1),
        },
    }


def detectar_roas_abaixo_limiar(snap_atual) -> dict | None:
    """ROAS geral abaixo de 1,5× — queimando dinheiro."""
    if snap_atual is None or snap_atual.roas is None:
        return None
    roas = float(snap_atual.roas)
    if roas >= 1.5:
        return None
    return {
        "tipo": "roas_abaixo_limiar",
        "severidade": "critico",
        "titulo": "ROAS abaixo do mínimo (< 1,5×)",
        "metrica_principal": f"{roas:.2f}×",
        "contexto": {"roas": round(roas, 2)},
    }


def detectar_oportunidade_escala(snap_atual, media_investimento_carteira: float | None) -> dict | None:
    """ROAS > 5× com investimento abaixo de 50% da média da carteira."""
    if snap_atual is None or snap_atual.roas is None or snap_atual.investimento is None:
        return None
    if media_investimento_carteira is None or media_investimento_carteira == 0:
        return None
    roas = float(snap_atual.roas)
    inv = float(snap_atual.investimento)
    if roas <= 5.0:
        return None
    if inv >= media_investimento_carteira * 0.5:
        return None
    return {
        "tipo": "oportunidade_escala",
        "severidade": "oportunidade",
        "titulo": "Alta eficiência com baixo investimento",
        "metrica_principal": f"{roas:.2f}×",
        "contexto": {
            "roas": round(roas, 2),
            "investimento": round(inv, 2),
            "media_carteira": round(media_investimento_carteira, 2),
        },
    }


def detectar_investimento_parado(snap_atual) -> dict | None:
    """Sem investimento registrado no mês."""
    if snap_atual is not None and snap_atual.investimento is not None and float(snap_atual.investimento) > 0:
        return None
    return {
        "tipo": "investimento_parado",
        "severidade": "atencao",
        "titulo": "Sem investimento registrado",
        "metrica_principal": "R$0",
        "contexto": {},
    }


# ── Pipeline ──────────────────────────────────────────────────────────────

def rodar_detectores(
    snap_atual,
    snap_anterior,
    breakdown: dict,
    media_investimento_carteira: float | None,
) -> list[dict]:
    """Roda todos os detectores e retorna lista de sinais (sem None)."""
    candidatos = [
        detectar_roas_brand_inflado(breakdown),
        detectar_roas_queda(snap_atual, snap_anterior),
        detectar_faturamento_queda(snap_atual, snap_anterior),
        detectar_roas_abaixo_limiar(snap_atual),
        detectar_oportunidade_escala(snap_atual, media_investimento_carteira),
        detectar_investimento_parado(snap_atual),
    ]
    return [s for s in candidatos if s is not None]
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
cd web/backend && python -m pytest tests/test_inteligencia.py -v
```

Expected: todos os testes `PASSED`

- [ ] **Step 5: Commit**

```bash
git add web/backend/services/inteligencia.py web/backend/tests/test_inteligencia.py
git commit -m "feat(inteligencia): signal registry com 6 detectores + testes"
```

---

## Task 3: Schemas + Endpoints Backend

**Files:**
- Modify: `web/backend/schemas/gestor.py`
- Modify: `web/backend/api/gestor.py`

### Contexto necessário

Os schemas Pydantic ficam em `web/backend/schemas/gestor.py`. Todos os endpoints novos ficam em `web/backend/api/gestor.py` no `router = APIRouter()` existente. Para o `generate`: carrega todos os snapshots do mês atual e anterior em 2 queries; para o `GET`: filtra por `UsuarioCliente` join (não-admin) ou por `?gestor=` (admin).

A chamada à API Anthropic usa o `settings` injetado via `Depends(get_settings)`. Para evitar criar o cliente Anthropic globalmente (que quebraria o import em ambiente sem chave), ele é criado dentro da função.

- [ ] **Step 1: Adicionar schemas ao `web/backend/schemas/gestor.py`**

Adicione ao final do arquivo (antes do final):

```python
# ── Inteligência ──────────────────────────────────────────────────────────

class InteligenciaAlerta(BaseModel):
    cliente_slug: str
    cliente_nome: str
    cliente_categoria: str
    severidade: str
    sinais: list[dict]
    narrativa: str | None = None


class InteligenciaResponse(BaseModel):
    mes: str
    alertas: list[InteligenciaAlerta]


class InteligenciaGenerateResponse(BaseModel):
    mes: str
    gerados: int
    sem_sinais: int
    sem_dados: int
    erros: int
```

- [ ] **Step 2: Adicionar imports necessários ao `web/backend/api/gestor.py`**

No bloco de imports do arquivo, adicione `Insight` ao import de models:

```python
from models import Cliente, GestorCadastrado, Insight, ReportJob, Usuario, UsuarioCliente
```

E adicione os novos schemas ao import de schemas:

```python
from schemas import (
    AssignClientesRequest,
    ClienteCreateRequest,
    CupClienteInfo,
    ClienteDetalheItem,
    ClienteEditRequest,
    ClienteGestorItem,
    ClienteMetricasItem,
    ClientesGestorResponse,
    CreateUsuarioRequest,
    GestorCadastradoCreate,
    GestorCadastradoItem,
    GestorCadastradosResponse,
    GestorRenameRequest,
    GestorRenameResponse,
    GestoresResponse,
    InteligenciaAlerta,
    InteligenciaGenerateResponse,
    InteligenciaResponse,
    JobStatusResponse,
    MetricasDashboardResponse,
    TriggerRequest,
    TriggerResponse,
    UsuarioListItem,
    UsuarioResponse,
    UsuariosListResponse,
)
```

- [ ] **Step 3: Adicionar `InteligenciaAlerta`, `InteligenciaGenerateResponse`, `InteligenciaResponse` ao `web/backend/schemas/__init__.py`**

Abra `web/backend/schemas/__init__.py` e adicione os três novos nomes ao `__all__` e ao import de `gestor`. (Se o arquivo re-exporta tudo de `gestor.py`, apenas adicione ao `gestor.py` é suficiente — mas verifique o `__init__.py` para manter consistência.)

- [ ] **Step 4: Implementar `POST /gestor/inteligencia/generate`**

Adicione ao final de `web/backend/api/gestor.py`:

```python
# ── POST /gestor/inteligencia/generate ────────────────────────────────────

@router.post("/inteligencia/generate", status_code=200)
def generate_inteligencia(
    mes: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
    settings=Depends(get_settings),
) -> InteligenciaGenerateResponse:
    from datetime import date, timedelta

    from models.snapshot import Snapshot
    from services.inteligencia import build_breakdown, rodar_detectores
    from services.metricas import build_breakdown as _bd

    # Calcula os limites de data para o mês atual e anterior
    ano, mes_num = int(mes[:4]), int(mes[5:7])
    primeiro_atual = date(ano, mes_num, 1)
    ultimo_atual = (date(ano, mes_num + 1, 1) if mes_num < 12 else date(ano + 1, 1, 1)) - timedelta(days=1)

    if mes_num == 1:
        primeiro_ant = date(ano - 1, 12, 1)
        ultimo_ant = date(ano, 1, 1) - timedelta(days=1)
    else:
        primeiro_ant = date(ano, mes_num - 1, 1)
        ultimo_ant = date(ano, mes_num, 1) - timedelta(days=1)

    clientes = session.execute(
        select(Cliente).where(Cliente.ativo == True)
    ).scalars().all()

    # Carrega todos os snapshots do mês atual de uma vez
    snaps_atual = {
        s.cliente_id: s
        for s in session.execute(
            select(Snapshot).where(
                Snapshot.frequencia == "MENSAL",
                Snapshot.periodo_fim >= primeiro_atual,
                Snapshot.periodo_fim <= ultimo_atual,
            )
        ).scalars().all()
    }

    # Carrega todos os snapshots do mês anterior de uma vez
    snaps_ant = {
        s.cliente_id: s
        for s in session.execute(
            select(Snapshot).where(
                Snapshot.frequencia == "MENSAL",
                Snapshot.periodo_fim >= primeiro_ant,
                Snapshot.periodo_fim <= ultimo_ant,
            )
        ).scalars().all()
    }

    # Média de investimento dos clientes com dados no mês atual
    investimentos = [
        float(s.investimento)
        for s in snaps_atual.values()
        if s.investimento is not None
    ]
    media_inv = sum(investimentos) / len(investimentos) if investimentos else None

    gerados = sem_sinais = sem_dados = erros = 0

    import anthropic as _anthropic

    for cliente in clientes:
        try:
            snap_atual = snaps_atual.get(cliente.id)
            snap_ant = snaps_ant.get(cliente.id)

            if snap_atual is None:
                sem_dados += 1
                continue

            breakdown = _bd(cliente.id, mes, session)
            sinais = rodar_detectores(snap_atual, snap_ant, breakdown, media_inv)

            if not sinais:
                sem_sinais += 1
                continue

            narrativa = None
            if settings.anthropic_api_key:
                try:
                    ant_client = _anthropic.Anthropic(api_key=settings.anthropic_api_key)
                    roas_str = f"{float(snap_atual.roas):.2f}×" if snap_atual.roas else "—"
                    fat_str = f"R${float(snap_atual.faturamento):,.0f}" if snap_atual.faturamento else "—"
                    inv_str = f"R${float(snap_atual.investimento):,.0f}" if snap_atual.investimento else "—"
                    sinais_txt = "\n".join(
                        f"- {s['titulo']}: {s['metrica_principal']}" for s in sinais
                    )
                    prompt = (
                        f"Você é um analista de performance de mídia paga. "
                        f"Analise os sinais abaixo para o cliente {cliente.nome} ({cliente.categoria.value}) "
                        f"no mês de {mes} e escreva um parágrafo objetivo de 3 a 4 frases explicando "
                        f"o que está acontecendo e o que o gestor deve observar. Seja direto, sem jargão excessivo.\n\n"
                        f"Sinais detectados:\n{sinais_txt}\n\n"
                        f"Métricas do mês:\n"
                        f"- Faturamento: {fat_str}\n"
                        f"- Investimento: {inv_str}\n"
                        f"- ROAS geral: {roas_str}"
                    )
                    msg = ant_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=300,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    narrativa = msg.content[0].text
                except Exception as e:
                    _log.warning("Claude API falhou para %s: %s", cliente.nome, e)

            # Upsert
            existing = session.execute(
                select(Insight).where(
                    Insight.cliente_id == cliente.id,
                    Insight.mes == mes,
                )
            ).scalar_one_or_none()

            if existing:
                existing.sinais = sinais
                existing.narrativa = narrativa
                from datetime import datetime, timezone
                existing.gerado_em = datetime.now(timezone.utc)
            else:
                session.add(Insight(
                    cliente_id=cliente.id,
                    mes=mes,
                    sinais=sinais,
                    narrativa=narrativa,
                ))

            session.commit()
            gerados += 1

        except Exception as e:
            _log.error("Erro ao gerar insight para cliente %s: %s", cliente.id, e)
            session.rollback()
            erros += 1

    return InteligenciaGenerateResponse(
        mes=mes,
        gerados=gerados,
        sem_sinais=sem_sinais,
        sem_dados=sem_dados,
        erros=erros,
    )
```

- [ ] **Step 5: Implementar `GET /gestor/inteligencia`**

Adicione imediatamente após o endpoint de generate:

```python
# ── GET /gestor/inteligencia ───────────────────────────────────────────────

_SEV_ORDER = {"critico": 0, "atencao": 1, "oportunidade": 2}


@router.get("/inteligencia", status_code=200)
def get_inteligencia(
    mes: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    gestor: str | None = Query(None),
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> InteligenciaResponse:
    # Monta filtro de clientes
    cliente_query = select(Cliente).where(Cliente.ativo == True)

    if user.is_admin:
        if gestor:
            cliente_query = cliente_query.where(Cliente.gestor == gestor)
    else:
        cliente_query = cliente_query.join(
            UsuarioCliente,
            (UsuarioCliente.cliente_id == Cliente.id)
            & (UsuarioCliente.usuario_id == user.id),
        )

    clientes = session.execute(cliente_query).scalars().all()
    cliente_ids = [c.id for c in clientes]
    cliente_map = {c.id: c for c in clientes}

    if not cliente_ids:
        return InteligenciaResponse(mes=mes, alertas=[])

    insights = session.execute(
        select(Insight).where(
            Insight.cliente_id.in_(cliente_ids),
            Insight.mes == mes,
        )
    ).scalars().all()

    alertas = [
        InteligenciaAlerta(
            cliente_slug=cliente_map[i.cliente_id].slug,
            cliente_nome=cliente_map[i.cliente_id].nome,
            cliente_categoria=cliente_map[i.cliente_id].categoria.value,
            severidade=i.sinais[0]["severidade"] if i.sinais else "atencao",
            sinais=i.sinais,
            narrativa=i.narrativa,
        )
        for i in insights
        if i.cliente_id in cliente_map
    ]

    alertas.sort(key=lambda a: _SEV_ORDER.get(a.severidade, 99))

    return InteligenciaResponse(mes=mes, alertas=alertas)
```

- [ ] **Step 6: Verificar que o servidor sobe sem erros**

```bash
cd web/backend && uvicorn main:app --port 8765 --reload
```

Expected: `Application startup complete.` sem erros de import.

Teste rápido do endpoint de generate (requer token admin):

```bash
curl -s -X POST "http://localhost:8765/gestor/inteligencia/generate?mes=2026-04" \
  -H "Authorization: Bearer <token_admin>" | python3 -m json.tool
```

Expected: JSON com `gerados`, `sem_sinais`, `sem_dados`, `erros`.

- [ ] **Step 7: Commit**

```bash
git add web/backend/schemas/gestor.py web/backend/api/gestor.py
git commit -m "feat(inteligencia): endpoints generate (admin) e GET por gestor"
```

---

## Task 4: Frontend — Tipos e API Client

**Files:**
- Modify: `web/frontend/lib/api-gestor.ts`

### Contexto necessário

`gestorApi` é um objeto literal em `web/frontend/lib/api-gestor.ts`. Todos os tipos são exportados do mesmo arquivo. O padrão é declarar o tipo e depois adicionar o método ao objeto `gestorApi`. O proxy Next.js em `app/api/gestor/[...path]/route.ts` repassa automaticamente qualquer path `/api/gestor/...` para o backend.

- [ ] **Step 1: Adicionar tipos e métodos ao `web/frontend/lib/api-gestor.ts`**

Adicione os tipos após a declaração de `MetricasBreakdown` (linha ~128):

```typescript
export type InteligenciaSinal = {
  tipo: string;
  severidade: "critico" | "atencao" | "oportunidade";
  titulo: string;
  metrica_principal: string;
  contexto: Record<string, unknown>;
};

export type InteligenciaAlerta = {
  cliente_slug: string;
  cliente_nome: string;
  cliente_categoria: string;
  severidade: "critico" | "atencao" | "oportunidade";
  sinais: InteligenciaSinal[];
  narrativa: string | null;
};

export type InteligenciaResponse = {
  mes: string;
  alertas: InteligenciaAlerta[];
};

export type InteligenciaGenerateResponse = {
  mes: string;
  gerados: number;
  sem_sinais: number;
  sem_dados: number;
  erros: number;
};
```

Adicione os métodos ao objeto `gestorApi` (antes do fechamento `}`):

```typescript
  inteligencia: (mes: string, gestor?: string) =>
    apiCall<InteligenciaResponse>(
      `inteligencia?mes=${encodeURIComponent(mes)}${gestor ? `&gestor=${encodeURIComponent(gestor)}` : ""}`,
    ),

  generateInteligencia: (mes: string) =>
    apiCall<InteligenciaGenerateResponse>(
      `inteligencia/generate?mes=${encodeURIComponent(mes)}`,
      "POST",
    ),
```

- [ ] **Step 2: Verificar que o TypeScript compila sem erros**

```bash
cd web/frontend && npx tsc --noEmit
```

Expected: sem erros relacionados a `api-gestor.ts`

- [ ] **Step 3: Commit**

```bash
git add web/frontend/lib/api-gestor.ts
git commit -m "feat(inteligencia): tipos e métodos no API client frontend"
```

---

## Task 5: Frontend — Página e Sidebar

**Files:**
- Create: `web/frontend/app/gestor/inteligencia/page.tsx`
- Modify: `web/frontend/app/gestor/page.tsx`

### Contexto necessário

O padrão de página no gestor é `"use client"` com `useEffect([mes])`. Variáveis CSS do projeto: `--paper`, `--paper-soft`, `--paper-deep`, `--ink`, `--ink-soft`, `--muted`, `--rule-soft`, `--forest`, `--crimson`, `--amber`. O header de volta usa `← Seus clientes` linkando para `/gestor`. O seletor de mês usa `mesUltimoFechado()` e `deslocarMes()` de `@/lib/mes-utils`. A formatação de moeda usa `fmtBRL` de `@/lib/roas-tier`.

A sidebar em `page.tsx` já tem dois `<Link>` externos (Performance e Administração). Adicionar o link de Inteligência imediatamente antes do link de Performance.

- [ ] **Step 1: Criar `web/frontend/app/gestor/inteligencia/page.tsx`**

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { gestorApi } from "@/lib/api-gestor";
import type { InteligenciaAlerta, InteligenciaResponse } from "@/lib/api-gestor";
import { deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";
import { fmtBRL } from "@/lib/roas-tier";

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}

const SEV_CONFIG = {
  critico:     { label: "Crítico",     dot: "bg-[var(--crimson)]",  text: "text-[var(--crimson)]",  badge: "bg-red-50 text-[var(--crimson)]" },
  atencao:     { label: "Atenção",     dot: "bg-[#f59e0b]",         text: "text-[#f59e0b]",         badge: "bg-amber-50 text-[#b45309]" },
  oportunidade:{ label: "Oportunidade",dot: "bg-[var(--forest)]",   text: "text-[var(--forest)]",   badge: "bg-green-50 text-[var(--forest)]" },
} as const;

function SeveridadeBadge({ sev }: { sev: InteligenciaAlerta["severidade"] }) {
  const cfg = SEV_CONFIG[sev];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-medium ${cfg.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

function AlertaCard({ alerta }: { alerta: InteligenciaAlerta }) {
  const router = useRouter();
  const sinal_principal = alerta.sinais[0];

  return (
    <div
      onClick={() => router.push(`/gestor/${alerta.cliente_slug}`)}
      className="cursor-pointer rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4 transition hover:bg-[var(--paper-deep)]"
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--ink)]">{alerta.cliente_nome}</p>
          <p className="text-xs text-[var(--muted)]">{alerta.cliente_categoria}</p>
        </div>
        <SeveridadeBadge sev={alerta.severidade} />
      </div>

      {sinal_principal && (
        <p className="mb-1.5 text-xs font-medium text-[var(--ink-soft)]">
          {sinal_principal.titulo}
          <span className="ml-2 font-mono text-[var(--ink)]">{sinal_principal.metrica_principal}</span>
        </p>
      )}

      {alerta.sinais.length > 1 && (
        <p className="mb-1.5 text-[10px] text-[var(--muted)]">
          +{alerta.sinais.length - 1} sinal{alerta.sinais.length > 2 ? "is" : ""} adicional{alerta.sinais.length > 2 ? "is" : ""}
        </p>
      )}

      {alerta.narrativa && (
        <p className="line-clamp-3 text-xs leading-relaxed text-[var(--muted)]">
          {alerta.narrativa}
        </p>
      )}
    </div>
  );
}

export default function InteligenciaPage() {
  const [mes, setMes] = useState(mesUltimoFechado());
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<InteligenciaResponse | null>(null);

  const mesOpcoes = useMemo(
    () => Array.from({ length: 12 }, (_, i) => deslocarMes(mesUltimoFechado(), -i)),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    gestorApi
      .inteligencia(mes)
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mes]);

  const alertas = data?.alertas ?? [];
  const n_critico = alertas.filter((a) => a.severidade === "critico").length;
  const n_atencao = alertas.filter((a) => a.severidade === "atencao").length;
  const n_oportunidade = alertas.filter((a) => a.severidade === "oportunidade").length;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Link
        href="/gestor"
        className="mb-6 block text-xs text-[var(--muted)] transition hover:text-[var(--ink)]"
      >
        ← Seus clientes
      </Link>

      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
          Inteligência
        </h1>
        <div className="flex items-center gap-2">
          <label htmlFor="mes-ref" className="text-xs text-[var(--muted)]">Mês:</label>
          <select
            id="mes-ref"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          >
            {mesOpcoes.map((m) => (
              <option key={m} value={m}>{mesLabel(m)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary strip */}
      {!loading && data && alertas.length > 0 && (
        <div className="mb-6 flex gap-3">
          {n_critico > 0 && (
            <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-[var(--crimson)]">
              {n_critico} crítico{n_critico > 1 ? "s" : ""}
            </span>
          )}
          {n_atencao > 0 && (
            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-[#b45309]">
              {n_atencao} atenção
            </span>
          )}
          {n_oportunidade > 0 && (
            <span className="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-[var(--forest)]">
              {n_oportunidade} oportunidade{n_oportunidade > 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}

      {loading ? (
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
          Carregando…
        </p>
      ) : alertas.length === 0 ? (
        <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-8 text-center">
          <p className="text-sm text-[var(--ink)]">Nenhum insight gerado para este período.</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Acesse o painel de administração para gerar os insights deste mês.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alertas.map((alerta, i) => (
            <AlertaCard key={`${alerta.cliente_slug}-${i}`} alerta={alerta} />
          ))}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Adicionar o link "Inteligência" na sidebar de `web/frontend/app/gestor/page.tsx`**

Localize o bloco (em torno da linha 145):

```tsx
      <Link
        href="/gestor/performance"
        className="mx-3 mb-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]"
      >
        <span className="text-[10px] opacity-60">◈</span>
        Performance
      </Link>
```

Adicione imediatamente **antes** desse bloco:

```tsx
      <Link
        href="/gestor/inteligencia"
        className="mx-3 mb-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]"
      >
        <span className="text-[10px] opacity-60">◆</span>
        Inteligência
      </Link>
```

- [ ] **Step 3: Verificar que o TypeScript compila**

```bash
cd web/frontend && npx tsc --noEmit
```

Expected: sem erros

- [ ] **Step 4: Testar no browser**

1. Suba o frontend: `cd web/frontend && npm run dev`
2. Abra `http://localhost:3000/gestor`
3. Clique em "Inteligência" na sidebar
4. Confirme que a página carrega sem erro
5. Se não houver insights gerados, confirme que o banner "Nenhum insight gerado" aparece
6. Troque o mês no seletor — confirme que o loading reexecuta

- [ ] **Step 5: Commit**

```bash
git add web/frontend/app/gestor/inteligencia/page.tsx web/frontend/app/gestor/page.tsx
git commit -m "feat(inteligencia): página /gestor/inteligencia com feed de alertas + link sidebar"
```

---

## Task 6: Botão "Gerar Insights" na área Admin

**Files:**
- Modify: `web/frontend/app/gestor/page.tsx`

### Contexto necessário

A página `page.tsx` tem uma seção de admin que é renderizada quando `user?.is_admin`. Atualmente há tabs de configurações. O botão de gerar insights deve aparecer em alguma aba admin existente ou em nova sub-seção. O padrão de botão de ação admin no projeto é um `<button>` com `onClick` que chama `gestorApi.<método>`, mostra loading inline e exibe o resultado.

- [ ] **Step 1: Localizar a seção admin em `page.tsx`**

Procure por `is_admin` ou `"configuracoes"` em `page.tsx`. A aba de configurações renderiza sub-tabs. Vamos adicionar um botão de geração na sub-tab `config-clientes` ou em um novo painel admin separado.

- [ ] **Step 2: Adicionar estado e handler para geração**

Adicione junto aos outros estados do componente principal:

```tsx
const [gerandoInsights, setGerandoInsights] = useState(false);
const [resultadoInsights, setResultadoInsights] = useState<string | null>(null);
```

Adicione o handler:

```tsx
async function handleGerarInsights() {
  setGerandoInsights(true);
  setResultadoInsights(null);
  try {
    const res = await gestorApi.generateInteligencia(mes);
    setResultadoInsights(
      `✓ ${res.gerados} gerados · ${res.sem_sinais} sem sinais · ${res.sem_dados} sem dados · ${res.erros} erros`
    );
  } catch (e: unknown) {
    setResultadoInsights(`Erro: ${e instanceof Error ? e.message : "desconhecido"}`);
  } finally {
    setGerandoInsights(false);
  }
}
```

- [ ] **Step 3: Adicionar o botão na UI admin**

Dentro da seção de configurações (onde `user?.is_admin` é verdadeiro), adicione:

```tsx
{user?.is_admin && (
  <div className="mt-6 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
    <p className="mb-3 text-sm font-medium text-[var(--ink)]">Geração de Insights</p>
    <div className="flex items-center gap-3">
      <button
        onClick={handleGerarInsights}
        disabled={gerandoInsights}
        className="rounded-md bg-[var(--forest)] px-4 py-2 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
      >
        {gerandoInsights ? "Gerando…" : `Gerar insights · ${mesLabel(mes)}`}
      </button>
      {resultadoInsights && (
        <span className="text-xs text-[var(--muted)]">{resultadoInsights}</span>
      )}
    </div>
  </div>
)}
```

**Nota:** O `mes` aqui deve ser o mesmo seletor de mês que já existe na tela — verifique qual variável de estado controla o mês selecionado na página e use-a.

- [ ] **Step 4: Testar a geração**

1. Acesse `http://localhost:3000/gestor` com usuário admin
2. Navegue até a aba onde o botão foi adicionado
3. Clique "Gerar insights"
4. Confirme o resultado aparece com contagens
5. Navegue para `/gestor/inteligencia` — confirme que os alertas aparecem

- [ ] **Step 5: Commit**

```bash
git add web/frontend/app/gestor/page.tsx
git commit -m "feat(inteligencia): botão de geração de insights na área admin"
```

---

## Self-Review

Spec coverage:
- ✅ Tabela `insights` com `sinais JSONB` + `narrativa TEXT` + `UNIQUE(cliente_id, mes)`
- ✅ Signal Registry com 6 detectores: `roas_brand_inflado`, `roas_queda`, `faturamento_queda`, `roas_abaixo_limiar`, `oportunidade_escala`, `investimento_parado`
- ✅ Batch endpoint `POST /gestor/inteligencia/generate` (admin only)
- ✅ Read endpoint `GET /gestor/inteligencia?mes=` com filtro gestor/admin
- ✅ Claude Haiku para narrativa (com fallback gracioso se sem API key)
- ✅ Frontend com portfolio summary strip (contagens por severidade)
- ✅ Feed de alertas ordenado: crítico → atenção → oportunidade
- ✅ Sidebar link "Inteligência"
- ✅ Botão admin de geração
- ✅ Banner para meses sem insights gerados

Tipos consistentes: `InteligenciaAlerta` no backend schema bate com o tipo TypeScript `InteligenciaAlerta` no frontend. `severidade` usa os mesmos valores em ambos os lados.
