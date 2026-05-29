# F0 — Schema (3 tabelas + gestor_travado) e Script de Auditoria de IDs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Criar a fundação de dados do Criativos v2: os models SQLAlchemy `Criativo`, `CriativoThumb` e `AdInsight`, a nova coluna `clientes.gestor_travado` (Boolean default `false`), uma única migration Alembic que materializa as 3 tabelas + a coluna (down_revision `f79fffd5b218`), e um script `scripts/audit_ids.py` que lista clientes ativos sem `id_meta_ads` e/ou `id_google_ads` (saída em tabela no stdout e CSV). Não tocar em `Snapshot`. Tudo coberto por testes TDD que rodam contra o Postgres de teste.

**Architecture:** Backend roda a partir de `web/backend/` (raiz do `sys.path` — imports tipo `from models import ...`, `from db import ...`). Models seguem o estilo SQLAlchemy 2.x `Mapped[...] = mapped_column(...)` com base única `from .base import Base`. O Enum Postgres `rede_anuncio` é **um único tipo** compartilhado por `criativos` e `ad_insights` (criado uma vez na migration, referenciado com `create_type=False` na segunda tabela). Os tipos novos são registrados em `models/__init__.py` para que `target_metadata = Base.metadata` (em `alembic/env.py`) os enxergue e para que os testes de DB (`Base.metadata.create_all`) materializem as tabelas automaticamente. O script de auditoria usa `SessionLocal` e consulta `Cliente` filtrando `ativo == True` e `id_meta_ads IS NULL` / `id_google_ads IS NULL`.

**Tech Stack:** Python 3, SQLAlchemy 2.x (`DeclarativeBase`, `Mapped`/`mapped_column`), Alembic (head atual `f79fffd5b218`, confirmada via `alembic heads`), Postgres (dialeto `postgresql+psycopg`), pytest 8.x. Banco de teste: `postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test`. Stdlib `csv` para o CSV; nenhuma dependência nova nesta fase (Pillow entra apenas na F1).

> **Interpretador Python (IMPORTANTE):** neste ambiente **não há `python` no PATH** — o interpretador do projeto é `web/backend/.venv/bin/python`. Todos os comandos abaixo o invocam explicitamente como `.venv/bin/python` a partir de `web/backend/`. (`alembic` e `pytest` são executados como módulos: `.venv/bin/python -m alembic`, `.venv/bin/python -m pytest`.)
>
> **Pré-requisito de DB:** os testes que tocam o banco e a validação da migration exigem um Postgres local com o database `vitrine_test` (usuário/senha `vitrine`). O binário `psql` está disponível em `/opt/homebrew/opt/postgresql@18/bin/psql` (já no PATH interativo).

---

## File Structure

**Criados:**
- `web/backend/models/criativo.py` — `RedeAnuncio` (Enum), `ThumbStatus` (Enum), `Criativo` (tabela `criativos`), `CriativoThumb` (tabela `criativo_thumbs`).
- `web/backend/models/ad_insight.py` — `AdInsight` (tabela `ad_insights`); reusa `RedeAnuncio` de `criativo.py`.
- `web/backend/alembic/versions/b1c2d3e4f5a6_add_criativos_ad_insights_gestor_travado.py` — migration única: coluna `gestor_travado`, enums `rede_anuncio`/`thumb_status`, tabelas `criativos`, `criativo_thumbs`, `ad_insights` + índices.
- `web/backend/scripts/audit_ids.py` — `auditar_ids(session) -> list[dict]`, impressão em tabela no stdout e geração de CSV; CLI `main()`.
- `web/backend/tests/test_models_criativos.py` — testes de criação/constraints dos models novos (usa fixture de DB local ao arquivo).
- `web/backend/tests/test_audit_ids.py` — testes do script de auditoria com dados semeados.

**Modificados:**
- `web/backend/models/cliente.py` — adiciona coluna `gestor_travado` à classe `Cliente`.
- `web/backend/models/__init__.py` — importa e exporta `AdInsight`, `Criativo`, `CriativoThumb`, `RedeAnuncio`, `ThumbStatus`.

---

## Task 1: Coluna `clientes.gestor_travado` no model `Cliente`

**Files:**
- Modify: `web/backend/models/cliente.py`
- Test: `web/backend/tests/test_models_criativos.py`

- [ ] Criar o arquivo de teste com fixture de DB local e o primeiro teste (`gestor_travado` default `false`). Escrever `web/backend/tests/test_models_criativos.py`:

```python
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models import (
    AdInsight,
    Categoria,
    Cliente,
    Criativo,
    CriativoThumb,
    RedeAnuncio,
    ThumbStatus,
)
from models.base import Base

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _cliente(s, slug="c-criativos"):
    c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


def test_cliente_gestor_travado_default_false(TS):
    with TS() as s:
        c = _cliente(s)
        assert c.gestor_travado is False
```

- [ ] Rodar o teste e ver falhar por `ImportError` (os models novos ainda não existem). Comando (a partir de `web/backend/`):

```
cd web/backend && .venv/bin/python -m pytest tests/test_models_criativos.py -v
```

Saída esperada: erro de coleta `ImportError: cannot import name 'AdInsight' from 'models'` (ou `Criativo`/`CriativoThumb`/`RedeAnuncio`/`ThumbStatus`) — o teste nem chega a rodar (`collected 0 items / 1 error`).

- [ ] Adicionar a coluna `gestor_travado` em `web/backend/models/cliente.py`, logo após a linha de `gestor` (linha 28). `Boolean` já está importado no arquivo (linha 7). Inserir entre a linha `gestor:` e `id_google_ads:`:

```python
    gestor_travado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
```

(O `ImportError` só some após a Task 2/3 criarem os models novos. Esta sub-task isola a mudança em `cliente.py`; o teste verde vem ao final da Task 3.)

- [ ] Commit:

```
git add web/backend/models/cliente.py web/backend/tests/test_models_criativos.py
git commit -m "$(cat <<'EOF'
feat(models): adiciona coluna gestor_travado a Cliente + teste base de criativos

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Models `Criativo` e `CriativoThumb` (`models/criativo.py`)

**Files:**
- Create: `web/backend/models/criativo.py`
- Modify: `web/backend/models/__init__.py`
- Test: `web/backend/tests/test_models_criativos.py`

- [ ] Adicionar testes de `Criativo`/`CriativoThumb` ao arquivo de teste. Acrescentar ao final de `web/backend/tests/test_models_criativos.py`:

```python
def test_criativo_cria_e_le(TS):
    with TS() as s:
        c = _cliente(s, slug="c-criativo-cria")
        cr = Criativo(
            cliente_id=c.id,
            rede=RedeAnuncio.META,
            ad_id="1203",
            nome="Criativo BF",
            tipo="video",
        )
        s.add(cr)
        s.commit()
        s.refresh(cr)
        assert isinstance(cr.id, uuid.UUID)
        assert cr.thumb_status is ThumbStatus.PENDENTE
        assert cr.nome == "Criativo BF"
        assert cr.primeiro_dia is None and cr.ultimo_dia is None


def test_criativo_unique_cliente_rede_ad(TS):
    with TS() as s:
        c = _cliente(s, slug="c-criativo-uniq")
        s.add(Criativo(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="999"))
        s.commit()
        s.add(Criativo(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="999"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_criativo_thumb_relationship_e_cascade(TS):
    with TS() as s:
        c = _cliente(s, slug="c-thumb")
        cr = Criativo(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="thumb-1")
        cr.thumb = CriativoThumb(conteudo=b"\x89PNG", mime="image/png")
        s.add(cr)
        s.commit()
        cr_id = cr.id
        assert cr.thumb is not None and cr.thumb.mime == "image/png"
        s.delete(cr)
        s.commit()
        assert s.get(CriativoThumb, cr_id) is None
```

- [ ] Rodar e ver falhar por `ImportError` (ainda não há `Criativo`). Comando:

```
cd web/backend && .venv/bin/python -m pytest tests/test_models_criativos.py -v
```

Saída esperada: `ImportError: cannot import name 'Criativo' from 'models'` (ou `AdInsight`) na coleta (`collected 0 items / 1 error`).

- [ ] Criar `web/backend/models/criativo.py` com o conteúdo completo (estilo idêntico a `snapshot.py`):

```python
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class RedeAnuncio(str, enum.Enum):
    META = "META"
    GOOGLE = "GOOGLE"


class ThumbStatus(str, enum.Enum):
    PENDENTE = "pendente"
    OK = "ok"
    SEM_IMAGEM = "sem_imagem"
    ERRO = "erro"


class Criativo(Base):
    __tablename__ = "criativos"
    __table_args__ = (
        UniqueConstraint("cliente_id", "rede", "ad_id", name="uq_criativo_cliente_rede_ad"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rede: Mapped[RedeAnuncio] = mapped_column(Enum(RedeAnuncio, name="rede_anuncio"), nullable=False)
    ad_id: Mapped[str] = mapped_column(String, nullable=False)
    nome: Mapped[str | None] = mapped_column(String, nullable=True)
    tipo: Mapped[str | None] = mapped_column(String, nullable=True)
    preview_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumb_status: Mapped[ThumbStatus] = mapped_column(
        Enum(ThumbStatus, name="thumb_status"), nullable=False, default=ThumbStatus.PENDENTE
    )
    primeiro_dia: Mapped[date | None] = mapped_column(Date, nullable=True)
    ultimo_dia: Mapped[date | None] = mapped_column(Date, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    thumb: Mapped["CriativoThumb | None"] = relationship(
        "CriativoThumb", back_populates="criativo", cascade="all, delete-orphan", uselist=False
    )


class CriativoThumb(Base):
    __tablename__ = "criativo_thumbs"

    criativo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("criativos.id", ondelete="CASCADE"), primary_key=True
    )
    conteudo: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime: Mapped[str] = mapped_column(String, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    criativo: Mapped["Criativo"] = relationship("Criativo", back_populates="thumb")
```

- [ ] Registrar os novos símbolos em `web/backend/models/__init__.py`. Adicionar a linha de import de `criativo` logo após `from .cliente import Categoria, Cliente`, e acrescentar os 4 nomes ao `__all__`. Editar o arquivo para ficar exatamente assim (ainda **sem** `AdInsight`, que entra na Task 3):

```python
from .base import Base
from .cliente import Categoria, Cliente
from .criativo import Criativo, CriativoThumb, RedeAnuncio, ThumbStatus
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
    "Criativo",
    "CriativoThumb",
    "Frequencia",
    "GestorCadastrado",
    "Insight",
    "JobStatus",
    "RedeAnuncio",
    "ReportJob",
    "Snapshot",
    "ThumbStatus",
    "Usuario",
    "UsuarioCliente",
]
```

(O `ImportError` ainda persiste por causa de `AdInsight`, resolvido na Task 3.)

- [ ] Rodar e confirmar que o erro de coleta agora é apenas `cannot import name 'AdInsight'` (os símbolos de `criativo.py` já importam). Comando:

```
cd web/backend && .venv/bin/python -m pytest tests/test_models_criativos.py -v
```

Saída esperada: `ImportError: cannot import name 'AdInsight' from 'models'` (`collected 0 items / 1 error`).

- [ ] Commit:

```
git add web/backend/models/criativo.py web/backend/models/__init__.py web/backend/tests/test_models_criativos.py
git commit -m "$(cat <<'EOF'
feat(models): models Criativo e CriativoThumb + enums RedeAnuncio/ThumbStatus

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Model `AdInsight` (`models/ad_insight.py`) + suíte de models verde

**Files:**
- Create: `web/backend/models/ad_insight.py`
- Modify: `web/backend/models/__init__.py`
- Test: `web/backend/tests/test_models_criativos.py`

- [ ] Adicionar testes de `AdInsight` ao arquivo de teste. Acrescentar ao final de `web/backend/tests/test_models_criativos.py`:

```python
def test_ad_insight_cria_com_defaults(TS):
    import datetime as dt
    from decimal import Decimal

    with TS() as s:
        c = _cliente(s, slug="c-insight")
        ins = AdInsight(
            cliente_id=c.id,
            rede=RedeAnuncio.META,
            ad_id="ad-1",
            dia=dt.date(2026, 5, 1),
        )
        s.add(ins)
        s.commit()
        s.refresh(ins)
        assert isinstance(ins.id, uuid.UUID)
        assert ins.investimento == Decimal("0")
        assert ins.faturamento == Decimal("0")
        assert ins.conversoes == Decimal("0")
        assert ins.impressoes == 0
        assert ins.clicks == 0
        assert ins.leads is None
        assert ins.video_3s is None
        assert ins.reach is None


def test_ad_insight_unique_cliente_rede_ad_dia(TS):
    import datetime as dt

    with TS() as s:
        c = _cliente(s, slug="c-insight-uniq")
        kwargs = dict(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="x", dia=dt.date(2026, 5, 1))
        s.add(AdInsight(**kwargs))
        s.commit()
        s.add(AdInsight(**kwargs))
        with pytest.raises(IntegrityError):
            s.commit()


def test_ad_insight_reusa_enum_rede_anuncio(TS):
    # rede em criativos e ad_insights compartilham o MESMO tipo Postgres
    assert AdInsight.__table__.c.rede.type.name == "rede_anuncio"
    assert Criativo.__table__.c.rede.type.name == "rede_anuncio"
```

- [ ] Rodar e ver falhar por `ImportError` em `AdInsight`. Comando:

```
cd web/backend && .venv/bin/python -m pytest tests/test_models_criativos.py -v
```

Saída esperada: `ImportError: cannot import name 'AdInsight' from 'models'` (`collected 0 items / 1 error`).

- [ ] Criar `web/backend/models/ad_insight.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .criativo import RedeAnuncio  # reusa o MESMO Enum (não redefinir)


class AdInsight(Base):
    __tablename__ = "ad_insights"
    __table_args__ = (
        UniqueConstraint(
            "cliente_id", "rede", "ad_id", "dia", name="uq_ad_insight_cliente_rede_ad_dia"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rede: Mapped[RedeAnuncio] = mapped_column(Enum(RedeAnuncio, name="rede_anuncio"), nullable=False)
    ad_id: Mapped[str] = mapped_column(String, nullable=False)
    dia: Mapped[date] = mapped_column(Date, nullable=False)

    investimento: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    faturamento: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    conversoes: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    leads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressoes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    video_3s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

- [ ] Registrar `AdInsight` em `web/backend/models/__init__.py`. Como `ad_insight.py` importa `RedeAnuncio` de `criativo.py`, a linha de import de `criativo` deve vir **antes** da de `ad_insight` (evita import circular). Editar o arquivo para ficar exatamente assim:

```python
from .base import Base
from .cliente import Categoria, Cliente
from .criativo import Criativo, CriativoThumb, RedeAnuncio, ThumbStatus
from .ad_insight import AdInsight
from .gestor import GestorCadastrado
from .insight import Insight
from .report_job import JobStatus, ReportJob
from .snapshot import Frequencia, Snapshot
from .usuario import Usuario
from .usuario_cliente import UsuarioCliente

__all__ = [
    "AdInsight",
    "Base",
    "Categoria",
    "Cliente",
    "Criativo",
    "CriativoThumb",
    "Frequencia",
    "GestorCadastrado",
    "Insight",
    "JobStatus",
    "RedeAnuncio",
    "ReportJob",
    "Snapshot",
    "ThumbStatus",
    "Usuario",
    "UsuarioCliente",
]
```

- [ ] Rodar a suíte de models completa e ver tudo passar (inclui o teste de `gestor_travado` da Task 1). Comando:

```
cd web/backend && .venv/bin/python -m pytest tests/test_models_criativos.py -v
```

Saída esperada: `7 passed` — `test_cliente_gestor_travado_default_false`, `test_criativo_cria_e_le`, `test_criativo_unique_cliente_rede_ad`, `test_criativo_thumb_relationship_e_cascade`, `test_ad_insight_cria_com_defaults`, `test_ad_insight_unique_cliente_rede_ad_dia`, `test_ad_insight_reusa_enum_rede_anuncio`.

- [ ] Commit:

```
git add web/backend/models/ad_insight.py web/backend/models/__init__.py web/backend/tests/test_models_criativos.py
git commit -m "$(cat <<'EOF'
feat(models): model AdInsight (ad_insights) reusando enum rede_anuncio

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Migration Alembic única (3 tabelas + `gestor_travado`)

**Files:**
- Create: `web/backend/alembic/versions/b1c2d3e4f5a6_add_criativos_ad_insights_gestor_travado.py`

> Não há teste pytest dedicado para a migration; a verificação é executá-la contra um Postgres descartável (`alembic upgrade head` → `downgrade -1` → `upgrade head`) e conferir o estado. O `down_revision` é a head confirmada `f79fffd5b218`. O `alembic/env.py` lê a URL de `settings.database_url` (pydantic-settings), que pode ser sobrescrita via env var `DATABASE_URL` numa invocação nova de processo.

- [ ] Confirmar a head atual antes de gerar (deve imprimir `f79fffd5b218 (head)`). Comando:

```
cd web/backend && .venv/bin/python -m alembic heads
```

Saída esperada: `f79fffd5b218 (head)`.

- [ ] Criar o arquivo de migration `web/backend/alembic/versions/b1c2d3e4f5a6_add_criativos_ad_insights_gestor_travado.py` (escrito à mão; o revision id `b1c2d3e4f5a6` é consistente com o filename):

```python
"""add_criativos_ad_insights_gestor_travado

Revision ID: b1c2d3e4f5a6
Revises: f79fffd5b218
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'f79fffd5b218'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Nova coluna em clientes
    op.add_column(
        "clientes",
        sa.Column("gestor_travado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 2) Tipos Enum Postgres (rede_anuncio compartilhado entre criativos e ad_insights)
    rede_enum = postgresql.ENUM("META", "GOOGLE", name="rede_anuncio")
    thumb_enum = postgresql.ENUM("pendente", "ok", "sem_imagem", "erro", name="thumb_status")
    rede_enum.create(op.get_bind(), checkfirst=True)
    thumb_enum.create(op.get_bind(), checkfirst=True)

    # 3) criativos
    op.create_table(
        "criativos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cliente_id", sa.UUID(), nullable=False),
        sa.Column(
            "rede",
            postgresql.ENUM("META", "GOOGLE", name="rede_anuncio", create_type=False),
            nullable=False,
        ),
        sa.Column("ad_id", sa.String(), nullable=False),
        sa.Column("nome", sa.String(), nullable=True),
        sa.Column("tipo", sa.String(), nullable=True),
        sa.Column("preview_link", sa.Text(), nullable=True),
        sa.Column(
            "thumb_status",
            postgresql.ENUM(
                "pendente", "ok", "sem_imagem", "erro", name="thumb_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("primeiro_dia", sa.Date(), nullable=True),
        sa.Column("ultimo_dia", sa.Date(), nullable=True),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cliente_id", "rede", "ad_id", name="uq_criativo_cliente_rede_ad"),
    )
    op.create_index(op.f("ix_criativos_cliente_id"), "criativos", ["cliente_id"], unique=False)
    op.create_index("ix_criativos_cliente_rede", "criativos", ["cliente_id", "rede"], unique=False)

    # 4) criativo_thumbs
    op.create_table(
        "criativo_thumbs",
        sa.Column("criativo_id", sa.UUID(), nullable=False),
        sa.Column("conteudo", sa.LargeBinary(), nullable=False),
        sa.Column("mime", sa.String(), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["criativo_id"], ["criativos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("criativo_id"),
    )

    # 5) ad_insights
    op.create_table(
        "ad_insights",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cliente_id", sa.UUID(), nullable=False),
        sa.Column(
            "rede",
            postgresql.ENUM("META", "GOOGLE", name="rede_anuncio", create_type=False),
            nullable=False,
        ),
        sa.Column("ad_id", sa.String(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("investimento", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("faturamento", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("conversoes", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("leads", sa.Integer(), nullable=True),
        sa.Column("impressoes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("video_3s", sa.Integer(), nullable=True),
        sa.Column("reach", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cliente_id", "rede", "ad_id", "dia", name="uq_ad_insight_cliente_rede_ad_dia"
        ),
    )
    op.create_index(op.f("ix_ad_insights_cliente_id"), "ad_insights", ["cliente_id"], unique=False)
    op.create_index(
        "ix_ad_insights_cliente_dia", "ad_insights", ["cliente_id", "dia"], unique=False
    )
    op.create_index(
        "ix_ad_insights_cliente_rede_dia",
        "ad_insights",
        ["cliente_id", "rede", "dia"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ad_insights_cliente_rede_dia", table_name="ad_insights")
    op.drop_index("ix_ad_insights_cliente_dia", table_name="ad_insights")
    op.drop_index(op.f("ix_ad_insights_cliente_id"), table_name="ad_insights")
    op.drop_table("ad_insights")

    op.drop_table("criativo_thumbs")

    op.drop_index("ix_criativos_cliente_rede", table_name="criativos")
    op.drop_index(op.f("ix_criativos_cliente_id"), table_name="criativos")
    op.drop_table("criativos")

    op.drop_column("clientes", "gestor_travado")

    thumb_enum = postgresql.ENUM("pendente", "ok", "sem_imagem", "erro", name="thumb_status")
    rede_enum = postgresql.ENUM("META", "GOOGLE", name="rede_anuncio")
    thumb_enum.drop(op.get_bind(), checkfirst=True)
    rede_enum.drop(op.get_bind(), checkfirst=True)
```

- [ ] Validar a migration num banco descartável (cria DB temporário, sobe tudo até a nova head, faz downgrade de 1 e re-upgrade). Comando (a partir de `web/backend/`):

```
cd web/backend && psql "postgresql://vitrine:vitrine@localhost:5432/postgres" -c "DROP DATABASE IF EXISTS vitrine_mig_test" \
  && psql "postgresql://vitrine:vitrine@localhost:5432/postgres" -c "CREATE DATABASE vitrine_mig_test" \
  && DATABASE_URL="postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_mig_test" .venv/bin/python -m alembic upgrade head \
  && DATABASE_URL="postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_mig_test" .venv/bin/python -m alembic current \
  && DATABASE_URL="postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_mig_test" .venv/bin/python -m alembic downgrade -1 \
  && DATABASE_URL="postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_mig_test" .venv/bin/python -m alembic upgrade head
```

Saída esperada: o `upgrade head` aplica até `b1c2d3e4f5a6`; `alembic current` mostra `b1c2d3e4f5a6 (head)`; o `downgrade -1` volta para `f79fffd5b218` e o `upgrade head` final reaplica `b1c2d3e4f5a6` — tudo sem stacktrace/erro.

> **Fallback se não puder criar DB novo:** rodar o ciclo contra o `vitrine_test` já existente (sem `DATABASE_URL`, pois é o default de `app_settings`): `cd web/backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic current && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head`. (Atenção: isso muta o `vitrine_test`; os testes pytest recriam o schema via `Base.metadata.create_all` e não dependem do `alembic_version`, então não há conflito.)

- [ ] Confirmar que `alembic heads` aponta para a nova revisão e que não há múltiplas heads. Comando:

```
cd web/backend && .venv/bin/python -m alembic heads
```

Saída esperada: `b1c2d3e4f5a6 (head)` (única head, uma linha só).

- [ ] Commit:

```
git add web/backend/alembic/versions/b1c2d3e4f5a6_add_criativos_ad_insights_gestor_travado.py
git commit -m "$(cat <<'EOF'
feat(db): migration criativos, criativo_thumbs, ad_insights + clientes.gestor_travado

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Script de auditoria de IDs (`scripts/audit_ids.py`)

**Files:**
- Create: `web/backend/scripts/audit_ids.py`
- Test: `web/backend/tests/test_audit_ids.py`

> A função pura `auditar_ids(session)` recebe uma `Session` (testável com a fixture de DB do arquivo) e retorna uma lista de dicts. A formatação em tabela (`formatar_tabela`) e o CSV (`escrever_csv`) também são testáveis sem DB. O `main()` (CLI) usa `SessionLocal`.

- [ ] Criar `web/backend/tests/test_audit_ids.py` com a fixture de DB e os testes. Conteúdo completo:

```python
import csv
import io

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Categoria, Cliente
from models.base import Base
from scripts.audit_ids import auditar_ids, escrever_csv, formatar_tabela

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _cli(s, slug, *, meta=None, google=None, ativo=True):
    c = Cliente(
        slug=slug,
        nome=slug,
        categoria=Categoria.ECOMMERCE,
        id_meta_ads=meta,
        id_google_ads=google,
        ativo=ativo,
    )
    s.add(c)
    s.commit()
    return c


def test_auditar_ids_lista_apenas_ativos_com_id_faltante(TS):
    with TS() as s:
        _cli(s, "completo", meta="m1", google="g1")          # nao aparece
        _cli(s, "sem-meta", meta=None, google="g2")          # falta meta
        _cli(s, "sem-google", meta="m3", google=None)        # falta google
        _cli(s, "sem-ambos", meta=None, google=None)         # falta os dois
        _cli(s, "inativo", meta=None, google=None, ativo=False)  # ignorado (inativo)

        rows = auditar_ids(s)

    by_slug = {r["slug"]: r for r in rows}
    assert set(by_slug) == {"sem-meta", "sem-google", "sem-ambos"}
    assert by_slug["sem-meta"]["falta_meta"] is True
    assert by_slug["sem-meta"]["falta_google"] is False
    assert by_slug["sem-google"]["falta_meta"] is False
    assert by_slug["sem-google"]["falta_google"] is True
    assert by_slug["sem-ambos"]["falta_meta"] is True
    assert by_slug["sem-ambos"]["falta_google"] is True


def test_auditar_ids_ordena_por_slug(TS):
    with TS() as s:
        _cli(s, "zeta", meta=None)
        _cli(s, "alfa", meta=None)
        rows = auditar_ids(s)
    assert [r["slug"] for r in rows] == ["alfa", "zeta"]


def test_formatar_tabela_inclui_header_e_slugs():
    rows = [
        {"slug": "sem-meta", "nome": "Sem Meta", "falta_meta": True, "falta_google": False},
    ]
    out = formatar_tabela(rows)
    assert "slug" in out
    assert "sem-meta" in out
    assert "Sem Meta" in out


def test_escrever_csv_gera_cabecalho_e_linhas():
    rows = [
        {"slug": "sem-ambos", "nome": "Sem Ambos", "falta_meta": True, "falta_google": True},
    ]
    buf = io.StringIO()
    escrever_csv(rows, buf)
    buf.seek(0)
    parsed = list(csv.reader(buf))
    assert parsed[0] == ["slug", "nome", "falta_meta", "falta_google"]
    assert parsed[1] == ["sem-ambos", "Sem Ambos", "True", "True"]
```

- [ ] Rodar e ver falhar por `ModuleNotFoundError` (script ainda não existe). Comando:

```
cd web/backend && .venv/bin/python -m pytest tests/test_audit_ids.py -v
```

Saída esperada: erro de coleta `ModuleNotFoundError: No module named 'scripts.audit_ids'` (`collected 0 items / 1 error`).

- [ ] Criar `web/backend/scripts/audit_ids.py` (estilo de `reprocessar_snapshots.py`: ajuste de `sys.path` para `web/backend/`, `SessionLocal`, `main()`). `Path(__file__).resolve().parents[1]` aponta para `web/backend/` (o script vive em `web/backend/scripts/`):

```python
"""Auditoria de IDs de conta de anúncio.

Lista clientes ATIVOS que estão sem `id_meta_ads` e/ou `id_google_ads`.
Saída: tabela no stdout + arquivo CSV (default: audit_ids.csv).

Uso (a partir de web/backend/):
    .venv/bin/python -m scripts.audit_ids [--csv CAMINHO]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import TextIO

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db import SessionLocal  # noqa: E402
from models import Cliente  # noqa: E402

_COLS = ["slug", "nome", "falta_meta", "falta_google"]


def auditar_ids(session: Session) -> list[dict]:
    """Retorna clientes ativos sem id_meta_ads e/ou id_google_ads, ordenados por slug."""
    stmt = (
        select(Cliente)
        .where(Cliente.ativo.is_(True))
        .where((Cliente.id_meta_ads.is_(None)) | (Cliente.id_google_ads.is_(None)))
        .order_by(Cliente.slug)
    )
    rows: list[dict] = []
    for c in session.scalars(stmt):
        rows.append(
            {
                "slug": c.slug,
                "nome": c.nome,
                "falta_meta": c.id_meta_ads is None,
                "falta_google": c.id_google_ads is None,
            }
        )
    return rows


def formatar_tabela(rows: list[dict]) -> str:
    """Formata os resultados como tabela alinhada para o stdout."""
    largs = {col: len(col) for col in _COLS}
    for r in rows:
        for col in _COLS:
            largs[col] = max(largs[col], len(str(r[col])))
    linhas = ["  ".join(col.ljust(largs[col]) for col in _COLS)]
    linhas.append("  ".join("-" * largs[col] for col in _COLS))
    for r in rows:
        linhas.append("  ".join(str(r[col]).ljust(largs[col]) for col in _COLS))
    linhas.append("")
    linhas.append(f"Total: {len(rows)} cliente(s) ativo(s) com ID faltante.")
    return "\n".join(linhas)


def escrever_csv(rows: list[dict], fp: TextIO) -> None:
    """Escreve os resultados como CSV (cabeçalho _COLS) no file-like `fp`."""
    writer = csv.writer(fp)
    writer.writerow(_COLS)
    for r in rows:
        writer.writerow([str(r[col]) for col in _COLS])


def main() -> list[dict]:
    parser = argparse.ArgumentParser(description="Auditoria de IDs de conta de anúncio.")
    parser.add_argument("--csv", default="audit_ids.csv", help="Caminho do CSV de saída.")
    args = parser.parse_args()

    with SessionLocal() as session:
        rows = auditar_ids(session)

    print(formatar_tabela(rows))
    with open(args.csv, "w", newline="", encoding="utf-8") as fp:
        escrever_csv(rows, fp)
    print(f"CSV gravado em: {args.csv}")
    return rows


if __name__ == "__main__":
    main()
```

- [ ] Rodar e ver tudo passar. Comando:

```
cd web/backend && .venv/bin/python -m pytest tests/test_audit_ids.py -v
```

Saída esperada: `4 passed` — `test_auditar_ids_lista_apenas_ativos_com_id_faltante`, `test_auditar_ids_ordena_por_slug`, `test_formatar_tabela_inclui_header_e_slugs`, `test_escrever_csv_gera_cabecalho_e_linhas`.

- [ ] Commit:

```
git add web/backend/scripts/audit_ids.py web/backend/tests/test_audit_ids.py
git commit -m "$(cat <<'EOF'
feat(scripts): audit_ids lista clientes ativos sem id_meta_ads/id_google_ads (stdout + CSV)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Verificação final da fase

**Files:** nenhum (apenas verificação).

- [ ] Rodar a suíte completa do backend e confirmar que nada quebrou (models novos + script + suítes existentes). Comando:

```
cd web/backend && .venv/bin/python -m pytest tests/ -v
```

Saída esperada: todos os testes `passed` (incluindo `tests/test_models_criativos.py` com 7 e `tests/test_audit_ids.py` com 4); zero `failed`/`error`. (Requer Postgres local com `vitrine_test`.)

- [ ] Confirmar que `Snapshot` não foi alterado (a fase não deve tocá-lo). Comando:

```
cd /Users/mac0267/Documents/auto-report-main && git diff --stat HEAD~5 HEAD -- web/backend/models/snapshot.py
```

Saída esperada: vazia (nenhuma mudança em `snapshot.py`).

- [ ] Conferir o conjunto de arquivos da fase (5 criados, 2 modificados). Comando:

```
cd /Users/mac0267/Documents/auto-report-main && git diff --name-only HEAD~5 HEAD
```

Saída esperada (exatamente estes 8 paths):

```
web/backend/alembic/versions/b1c2d3e4f5a6_add_criativos_ad_insights_gestor_travado.py
web/backend/models/__init__.py
web/backend/models/ad_insight.py
web/backend/models/cliente.py
web/backend/models/criativo.py
web/backend/scripts/audit_ids.py
web/backend/tests/test_audit_ids.py
web/backend/tests/test_models_criativos.py
```

---

**Notas de fechamento (DRY / YAGNI):**
- O Enum `rede_anuncio` é definido **uma única vez** em `models/criativo.py` e reusado por `AdInsight` (import), e criado **uma vez** na migration com `create_type=False` na segunda/terceira referência — sem duplicação de tipo Postgres.
- O script `audit_ids.py` separa lógica pura (`auditar_ids`/`formatar_tabela`/`escrever_csv`) do I/O (`main` com `SessionLocal` e `open`), permitindo testes sem mockar filesystem nem CLI.
- Nada de endpoint de auditoria nesta fase (YAGNI — o spec pede "script/endpoint"; F0 entrega o script, suficiente para o fluxo operacional #9 parte 1; o endpoint só seria adicionado se a UI exigir, fora do escopo F0).
- Nenhuma dependência nova é adicionada nesta fase (Pillow entra apenas na F1).
- **Interpretador:** todos os comandos usam `web/backend/.venv/bin/python` (não existe `python` no PATH deste ambiente); `alembic`/`pytest` rodam como módulos (`-m alembic` / `-m pytest`).
