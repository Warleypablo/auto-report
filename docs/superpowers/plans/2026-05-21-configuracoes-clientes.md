# Configurações de Clientes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar à aba Configurações do painel gestor uma tabela editável de clientes, com modal para editar campos operacionais (IDs de plataforma, links, gestor) e soft delete.

**Architecture:** Seis novas colunas no modelo `Cliente` (id_google_ads, id_meta_ads, id_ga4, painel_url, pasta_url, ativo). A sincronização com a planilha popula os campos na inserção mas não os sobrescreve em updates. O backend expõe PATCH e DELETE em `/gestor/clientes/{id}`. O frontend substitui o placeholder `AbaConfiguracoes` por tabela + modal.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL (backend), Next.js 14 App Router + TypeScript + Tailwind CSS (frontend)

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `web/backend/alembic/versions/<hash>_add_ids_ativo_to_clientes.py` | Criar | Migration: 6 novas colunas |
| `web/backend/models/cliente.py` | Modificar | Adicionar 6 campos ao modelo |
| `web/backend/etl/sync_planilha.py` | Modificar | Ler colunas novas, não sobrescrever no update |
| `web/backend/schemas/gestor.py` | Modificar | Adicionar ClienteEditRequest + ClienteDetalheItem |
| `web/backend/schemas/__init__.py` | Modificar | Exportar novos schemas |
| `web/backend/api/gestor.py` | Modificar | PATCH + DELETE, filtrar ativo=True no GET |
| `web/backend/tests/test_configuracoes_clientes.py` | Criar | Testes dos novos schemas |
| `web/frontend/lib/api-gestor.ts` | Modificar | Tipo ClienteGestor ampliado + 2 novos métodos |
| `web/frontend/app/gestor/page.tsx` | Modificar | AbaConfiguracoes com tabela/modal + callbacks no pai |

---

## Contexto do projeto

O projeto está em `web/backend/` (FastAPI) e `web/frontend/` (Next.js 14).
O banco de dados é PostgreSQL com Alembic para migrations. A migration mais recente é `a654ab44e4cb` (down_revision=`d97ddcec2df1`).
Para rodar o backend: `cd web/backend && source .venv/bin/activate && uvicorn main:app --port 8765 --reload`.
Todos os comandos alembic são executados em `web/backend/` com a venv ativada.

---

## Task 1: DB migration + campos no modelo

**Files:**
- Create: `web/backend/alembic/versions/<hash>_add_ids_ativo_to_clientes.py`
- Modify: `web/backend/models/cliente.py`

- [ ] **Step 1: Gerar o arquivo de migration**

```bash
cd web/backend
source .venv/bin/activate
alembic revision -m "add_ids_ativo_to_clientes"
```

Esperado: `Generating .../alembic/versions/<hash>_add_ids_ativo_to_clientes.py`

- [ ] **Step 2: Preencher upgrade/downgrade na migration gerada**

Abra o arquivo gerado em `web/backend/alembic/versions/<hash>_add_ids_ativo_to_clientes.py` e substitua as funções `upgrade` e `downgrade` pelo seguinte:

```python
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column("clientes", sa.Column("id_google_ads", sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("id_meta_ads",   sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("id_ga4",        sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("painel_url",    sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("pasta_url",     sa.String(), nullable=True))
    op.add_column(
        "clientes",
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("clientes", "ativo")
    op.drop_column("clientes", "pasta_url")
    op.drop_column("clientes", "painel_url")
    op.drop_column("clientes", "id_ga4")
    op.drop_column("clientes", "id_meta_ads")
    op.drop_column("clientes", "id_google_ads")
```

Mantenha o cabeçalho gerado (revision, down_revision, branch_labels, depends_on) intacto.

- [ ] **Step 3: Aplicar a migration**

```bash
cd web/backend
source .venv/bin/activate
alembic upgrade head
```

Esperado: `Running upgrade a654ab44e4cb -> <novo-hash>, add_ids_ativo_to_clientes`

- [ ] **Step 4: Verificar colunas no banco**

```bash
cd web/backend
source .venv/bin/activate
python -c "
from app_settings import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
engine = create_engine(get_settings().database_url)
with Session(engine) as s:
    cols = s.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='clientes' ORDER BY ordinal_position\")).scalars().all()
    print(cols)
"
```

Esperado: lista incluindo `'id_google_ads'`, `'id_meta_ads'`, `'id_ga4'`, `'painel_url'`, `'pasta_url'`, `'ativo'`.

- [ ] **Step 5: Adicionar campos ao modelo SQLAlchemy**

Em `web/backend/models/cliente.py`, adicione os 6 campos logo após `gestor`:

```python
# Antes (linha ~27):
gestor: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
setor: Mapped[str | None] = mapped_column(String, nullable=True)

# Depois:
gestor: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
id_google_ads: Mapped[str | None] = mapped_column(String, nullable=True)
id_meta_ads: Mapped[str | None] = mapped_column(String, nullable=True)
id_ga4: Mapped[str | None] = mapped_column(String, nullable=True)
painel_url: Mapped[str | None] = mapped_column(String, nullable=True)
pasta_url: Mapped[str | None] = mapped_column(String, nullable=True)
ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
setor: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 6: Verificar que o modelo importa sem erro**

```bash
cd web/backend
source .venv/bin/activate
python -c "from models.cliente import Cliente; print(Cliente.__table__.columns.keys())"
```

Esperado: lista com `id_google_ads`, `id_meta_ads`, `id_ga4`, `painel_url`, `pasta_url`, `ativo`.

- [ ] **Step 7: Commit**

```bash
git add web/backend/alembic/versions/
git add web/backend/models/cliente.py
git commit -m "feat(db): add ids, painel_url, pasta_url, ativo to clientes"
```

---

## Task 2: Sync — popular novos campos na planilha

**Files:**
- Modify: `web/backend/etl/sync_planilha.py`

Contexto: `sync_planilha.py` lê a planilha central e faz upsert no DB. Na regra "DB é fonte de verdade", o update de clientes existentes NÃO deve sobrescrever os campos operacionais editáveis se já tiverem valor. O insert de novos clientes deve popular tudo.

- [ ] **Step 1: Adicionar constantes de coluna no topo de sync_planilha.py**

Encontre o bloco de constantes existente (próximo à linha 35) e adicione após as já existentes:

```python
COL_PAINEL    = "LINK PAINEL DE CONTROLE"
COL_PASTA     = "LINK PASTA"
COL_IDGOOGLE  = "ID GOOGLE ADS"
COL_IDMETA    = "ID META ADS"
COL_IDGA4     = "ID GA4"
```

- [ ] **Step 2: Incluir novos campos no payload de parse**

No loop de construção de `desejados` (próximo à linha 115, dentro de `sync_clientes`), adicione os novos campos ao dict `payload`:

```python
payload = dict(
    slug=slug,
    nome=nome,
    categoria=categoria_enum,
    gestor=_cell(row, header.get(COL_GESTOR)) or None,
    id_google_ads=_cell(row, header.get(COL_IDGOOGLE)) or None,
    id_meta_ads=_cell(row, header.get(COL_IDMETA)) or None,
    id_ga4=_cell(row, header.get(COL_IDGA4)) or None,
    painel_url=_cell(row, header.get(COL_PAINEL)) or None,
    pasta_url=_cell(row, header.get(COL_PASTA)) or None,
    publicar_vitrine=_is_true(_cell(row, header.get(COL_PUBLICAR))),
    descricao_publica=_cell(row, header.get(COL_DESCRICAO)) or None,
    logo_url=_cell(row, header.get(COL_LOGO)) or None,
    setor=_cell(row, header.get(COL_SETOR_PUB)) or None,
    porte=_cell(row, header.get(COL_PORTE_PUB)) or None,
    row_idx=row_idx,
)
```

- [ ] **Step 3: Atualizar a lógica de update (não sobrescrever campos operacionais)**

No bloco de upsert (próximo à linha 145), substitua o bloco do `if existing:` pelo seguinte:

```python
if existing:
    # Campos estruturais: sempre sincroniza da planilha
    existing.nome = p["nome"]
    existing.categoria = p["categoria"]
    existing.publicar_vitrine = p["publicar_vitrine"]
    # Campos opcionais estruturais: só atualiza se vieram preenchidos
    if p["logo_url"]:
        existing.logo_url = p["logo_url"]
    if p["descricao_publica"]:
        existing.descricao_publica = p["descricao_publica"]
    if p["setor"]:
        existing.setor = p["setor"]
    if p["porte"]:
        existing.porte = p["porte"]
    # Campos operacionais editáveis: só preenche se ainda NULL no DB
    # (primeira carga), preservando edições manuais posteriores
    if existing.gestor is None and p["gestor"]:
        existing.gestor = p["gestor"]
    if existing.id_google_ads is None and p["id_google_ads"]:
        existing.id_google_ads = p["id_google_ads"]
    if existing.id_meta_ads is None and p["id_meta_ads"]:
        existing.id_meta_ads = p["id_meta_ads"]
    if existing.id_ga4 is None and p["id_ga4"]:
        existing.id_ga4 = p["id_ga4"]
    if existing.painel_url is None and p["painel_url"]:
        existing.painel_url = p["painel_url"]
    if existing.pasta_url is None and p["pasta_url"]:
        existing.pasta_url = p["pasta_url"]
    updated += 1
```

- [ ] **Step 4: Atualizar o INSERT para incluir novos campos**

Ainda no bloco de upsert, no `else:` (INSERT), adicione os novos campos:

```python
else:
    session.add(Cliente(
        slug=slug,
        nome=p["nome"],
        categoria=p["categoria"],
        gestor=p["gestor"],
        id_google_ads=p["id_google_ads"],
        id_meta_ads=p["id_meta_ads"],
        id_ga4=p["id_ga4"],
        painel_url=p["painel_url"],
        pasta_url=p["pasta_url"],
        logo_url=p["logo_url"],
        descricao_publica=p["descricao_publica"],
        setor=p["setor"],
        porte=p["porte"],
        publicar_vitrine=p["publicar_vitrine"],
        destaque=False,
        ativo=True,
    ))
    inserted += 1
```

- [ ] **Step 5: Verificar que o sync importa sem erro**

```bash
cd web/backend
source .venv/bin/activate
python -c "from etl.sync_planilha import sync_clientes; print('OK')"
```

Esperado: `OK`

- [ ] **Step 6: Disparar sync e verificar que os novos campos foram populados**

```bash
curl -s -X POST http://localhost:8765/internal/sync-clientes \
  -H "x-etl-token: dev-token-change-me" | python3 -m json.tool
```

Esperado: `{"inserted": 0, "updated": N, ...}` sem erros.

```bash
cd web/backend
source .venv/bin/activate
python -c "
from app_settings import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
engine = create_engine(get_settings().database_url)
with Session(engine) as s:
    row = s.execute(text(\"SELECT id_google_ads, id_meta_ads, id_ga4, painel_url, pasta_url FROM clientes WHERE id_google_ads IS NOT NULL LIMIT 1\")).first()
    print(row)
"
```

Esperado: uma tupla com pelo menos um campo preenchido (se a planilha tiver esses dados).

- [ ] **Step 7: Commit**

```bash
git add web/backend/etl/sync_planilha.py
git commit -m "feat(sync): populate ids/links from sheet, preserve DB edits on update"
```

---

## Task 3: Schemas + testes

**Files:**
- Modify: `web/backend/schemas/gestor.py`
- Modify: `web/backend/schemas/__init__.py`
- Create: `web/backend/tests/test_configuracoes_clientes.py`

- [ ] **Step 1: Escrever o teste antes de criar os schemas**

Crie `web/backend/tests/test_configuracoes_clientes.py`:

```python
"""Testes para os schemas de edição e detalhe de clientes."""
import uuid
import pytest


def test_cliente_edit_request_partial():
    """Só os campos enviados devem ficar em model_fields_set."""
    from schemas.gestor import ClienteEditRequest
    req = ClienteEditRequest(nome="Novo Nome", gestor="Ana")
    data = req.model_dump(exclude_unset=True)
    assert data == {"nome": "Novo Nome", "gestor": "Ana"}
    assert "id_google_ads" not in data


def test_cliente_edit_request_null_clears_field():
    """Campo explicitamente null deve ser incluído (para limpar o valor)."""
    from schemas.gestor import ClienteEditRequest
    req = ClienteEditRequest(gestor=None)
    data = req.model_dump(exclude_unset=True)
    assert "gestor" in data
    assert data["gestor"] is None


def test_cliente_edit_request_categoria_valida():
    from schemas.gestor import ClienteEditRequest
    req = ClienteEditRequest(categoria="E-commerce")
    assert req.categoria == "E-commerce"


def test_cliente_edit_request_categoria_invalida():
    from schemas.gestor import ClienteEditRequest
    with pytest.raises(Exception):
        ClienteEditRequest(categoria="Invalida")


def test_cliente_detalhe_item_fields():
    """ClienteDetalheItem deve ter todos os campos esperados."""
    from schemas.gestor import ClienteDetalheItem
    item = ClienteDetalheItem(
        id=uuid.uuid4(),
        slug="meu-cliente",
        nome="Meu Cliente",
        categoria="E-commerce",
        gestor="Ana",
        id_google_ads="123",
        id_meta_ads="456",
        id_ga4="G-789",
        painel_url="https://example.com/painel",
        pasta_url="https://example.com/pasta",
        ativo=True,
    )
    assert item.slug == "meu-cliente"
    assert item.ativo is True


def test_cliente_detalhe_item_nullable_fields():
    """Campos opcionais devem aceitar None."""
    from schemas.gestor import ClienteDetalheItem
    item = ClienteDetalheItem(
        id=uuid.uuid4(),
        slug="slug",
        nome="Nome",
        categoria="Lead Com Site",
        ativo=True,
    )
    assert item.gestor is None
    assert item.id_google_ads is None
```

- [ ] **Step 2: Rodar os testes para confirmar que falham (schemas não existem ainda)**

```bash
cd web/backend
source .venv/bin/activate
pytest tests/test_configuracoes_clientes.py -v 2>&1 | head -30
```

Esperado: `ImportError` ou `ModuleNotFoundError` — os schemas ainda não existem.

- [ ] **Step 3: Adicionar os novos schemas em schemas/gestor.py**

Abra `web/backend/schemas/gestor.py` e adicione no final do arquivo (antes do fechamento):

```python
from typing import Literal

CATEGORIAS_VALIDAS = ("E-commerce", "Lead Com Site", "Lead Sem Site")


class ClienteEditRequest(BaseModel):
    nome: str | None = None
    categoria: Literal["E-commerce", "Lead Com Site", "Lead Sem Site"] | None = None
    gestor: str | None = None
    id_google_ads: str | None = None
    id_meta_ads: str | None = None
    id_ga4: str | None = None
    painel_url: str | None = None
    pasta_url: str | None = None


class ClienteDetalheItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    nome: str
    categoria: str
    gestor: str | None = None
    id_google_ads: str | None = None
    id_meta_ads: str | None = None
    id_ga4: str | None = None
    painel_url: str | None = None
    pasta_url: str | None = None
    ativo: bool

    @field_validator("categoria", mode="before")
    @classmethod
    def coerce_categoria(cls, v: object) -> str:
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)
```

Adicione também `field_validator` ao import de pydantic no topo do arquivo:

```python
from pydantic import BaseModel, ConfigDict, field_validator
```

- [ ] **Step 4: Exportar os novos schemas em schemas/__init__.py**

No arquivo `web/backend/schemas/__init__.py`, adicione `ClienteEditRequest` e `ClienteDetalheItem` nas importações e no `__all__`:

```python
from .gestor import (
    AssignClientesRequest,
    ClienteDetalheItem,     # <-- novo
    ClienteEditRequest,     # <-- novo
    ClienteGestorItem,
    ClienteMetricasItem,
    ClientesGestorResponse,
    CreateUsuarioRequest,
    GestoresResponse,
    JobStatusResponse,
    LoginRequest,
    LoginResponse,
    MetricasDashboardResponse,
    TriggerRequest,
    TriggerResponse,
    UsuarioListItem,
    UsuarioResponse,
    UsuariosListResponse,
)
```

E em `__all__`, adicione `"ClienteDetalheItem"` e `"ClienteEditRequest"` na lista ordenada.

- [ ] **Step 5: Rodar os testes para confirmar que passam**

```bash
cd web/backend
source .venv/bin/activate
pytest tests/test_configuracoes_clientes.py -v
```

Esperado: todos os 6 testes passando (`6 passed`).

- [ ] **Step 6: Rodar a suite completa para confirmar sem regressões**

```bash
cd web/backend
source .venv/bin/activate
pytest tests/ -v --ignore=tests/__pycache__ 2>&1 | tail -20
```

Esperado: todos os testes passando, nenhuma falha.

- [ ] **Step 7: Commit**

```bash
git add web/backend/schemas/gestor.py web/backend/schemas/__init__.py
git add web/backend/tests/test_configuracoes_clientes.py
git commit -m "feat(schemas): ClienteEditRequest + ClienteDetalheItem"
```

---

## Task 4: Endpoints PATCH + DELETE e filtro ativo nos endpoints existentes

**Files:**
- Modify: `web/backend/api/gestor.py`

- [ ] **Step 1: Adicionar imports necessários no topo de api/gestor.py**

No bloco de imports de `schemas`, adicione `ClienteDetalheItem` e `ClienteEditRequest`:

```python
from schemas import (
    AssignClientesRequest,
    ClienteDetalheItem,      # <-- novo
    ClienteEditRequest,      # <-- novo
    ClienteGestorItem,
    ClienteMetricasItem,
    ClientesGestorResponse,
    CreateUsuarioRequest,
    GestoresResponse,
    JobStatusResponse,
    MetricasDashboardResponse,
    TriggerRequest,
    TriggerResponse,
    UsuarioListItem,
    UsuarioResponse,
    UsuariosListResponse,
)
```

- [ ] **Step 2: Filtrar ativo=True no GET /gestor/clientes**

Na função `list_clientes`, adicione `.where(Cliente.ativo == True)` nas duas branches (admin e gestor comum):

```python
@router.get("/clientes", response_model=ClientesGestorResponse)
def list_clientes(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClientesGestorResponse:
    if user.is_admin:
        stmt = select(Cliente).where(Cliente.ativo == True).order_by(Cliente.nome.asc())
    else:
        stmt = (
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(UsuarioCliente.usuario_id == user.id, Cliente.ativo == True)
            .order_by(Cliente.nome.asc())
        )
    clientes = session.execute(stmt).scalars().all()
    return ClientesGestorResponse(
        items=[
            ClienteGestorItem(
                id=c.id, slug=c.slug, nome=c.nome,
                categoria=c.categoria.value, gestor=c.gestor,
            )
            for c in clientes
        ]
    )
```

- [ ] **Step 3: Filtrar ativo=True no GET /gestor/gestores**

Na função `list_gestores`, adicione `Cliente.ativo == True` nos dois `where`:

```python
@router.get("/gestores", response_model=GestoresResponse)
def list_gestores(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> GestoresResponse:
    from sqlalchemy import distinct
    if user.is_admin:
        stmt = (
            select(distinct(Cliente.gestor))
            .where(Cliente.gestor.isnot(None), Cliente.ativo == True)
            .order_by(Cliente.gestor)
        )
    else:
        stmt = (
            select(distinct(Cliente.gestor))
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(
                UsuarioCliente.usuario_id == user.id,
                Cliente.gestor.isnot(None),
                Cliente.ativo == True,
            )
            .order_by(Cliente.gestor)
        )
    gestores = [row[0] for row in session.execute(stmt).all()]
    return GestoresResponse(items=gestores)
```

- [ ] **Step 4: Filtrar ativo=True no GET /gestor/metricas**

Na função `get_metricas_dashboard`, adicione `.where(Cliente.ativo == True)` nas duas branches:

```python
# Branch admin:
clientes = session.execute(
    select(Cliente).where(Cliente.ativo == True).order_by(Cliente.nome)
).scalars().all()

# Branch gestor:
clientes = session.execute(
    select(Cliente)
    .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
    .where(UsuarioCliente.usuario_id == user.id, Cliente.ativo == True)
    .order_by(Cliente.nome)
).scalars().all()
```

- [ ] **Step 5: Adicionar PATCH /gestor/clientes/{cliente_id}**

Adicione a função abaixo da função `list_gestores`:

```python
# ── PATCH /gestor/clientes/{cliente_id} ───────────────────────────────────

@router.patch("/clientes/{cliente_id}", response_model=ClienteDetalheItem)
def update_cliente(
    cliente_id: uuid.UUID,
    body: ClienteEditRequest,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClienteDetalheItem:
    if user.is_admin:
        cliente = session.get(Cliente, cliente_id)
    else:
        cliente = session.execute(
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(Cliente.id == cliente_id, UsuarioCliente.usuario_id == user.id)
        ).scalar_one_or_none()

    if cliente is None or not cliente.ativo:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "categoria" and value is not None:
            from models.cliente import Categoria as CatEnum
            value = CatEnum(value)
        setattr(cliente, field, value)

    session.commit()
    session.refresh(cliente)
    return ClienteDetalheItem.model_validate(cliente)
```

- [ ] **Step 6: Adicionar DELETE /gestor/clientes/{cliente_id}**

Adicione logo após o PATCH:

```python
# ── DELETE /gestor/clientes/{cliente_id} (soft delete) ────────────────────

@router.delete("/clientes/{cliente_id}", status_code=204)
def deactivate_cliente(
    cliente_id: uuid.UUID,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> None:
    if user.is_admin:
        cliente = session.get(Cliente, cliente_id)
    else:
        cliente = session.execute(
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(Cliente.id == cliente_id, UsuarioCliente.usuario_id == user.id)
        ).scalar_one_or_none()

    if cliente is None or not cliente.ativo:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    cliente.ativo = False
    session.commit()
```

- [ ] **Step 7: Verificar novos endpoints com curl**

Obtenha um token de admin:
```bash
TOKEN=$(curl -s -X POST http://localhost:8765/auth/login \
  -H "content-type: application/json" \
  -d '{"email":"admin@agencia.com","senha":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```

Liste os clientes e pegue um ID:
```bash
curl -s http://localhost:8765/gestor/clientes \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json; items=json.load(sys.stdin)['items']; print(items[0]['id'], items[0]['nome'])
"
```

Teste o PATCH:
```bash
CLIENTE_ID="<id-do-cliente-acima>"
curl -s -X PATCH "http://localhost:8765/gestor/clientes/$CLIENTE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "content-type: application/json" \
  -d '{"gestor": "Gestor Teste"}' | python3 -m json.tool
```

Esperado: JSON com `"gestor": "Gestor Teste"` e todos os campos do `ClienteDetalheItem`.

Verifique que os outros endpoints continuam funcionando (GET /clientes, GET /gestores, GET /metricas devem retornar 200).

- [ ] **Step 8: Commit**

```bash
git add web/backend/api/gestor.py
git commit -m "feat(api): PATCH+DELETE clientes, filtrar ativo=True nos listings"
```

---

## Task 5: Frontend — tipos TypeScript e cliente de API

**Files:**
- Modify: `web/frontend/lib/api-gestor.ts`

- [ ] **Step 1: Atualizar o tipo ClienteGestor com os novos campos**

Em `web/frontend/lib/api-gestor.ts`, substitua a definição de `ClienteGestor`:

```typescript
export type ClienteGestor = {
  id: string;
  slug: string;
  nome: string;
  categoria: string;
  gestor: string | null;
  id_google_ads: string | null;
  id_meta_ads: string | null;
  id_ga4: string | null;
  painel_url: string | null;
  pasta_url: string | null;
  ativo: boolean;
};
```

- [ ] **Step 2: Adicionar o tipo ClienteEditData**

Logo após `ClienteGestor`, adicione:

```typescript
export type ClienteEditData = {
  nome?: string | null;
  categoria?: string | null;
  gestor?: string | null;
  id_google_ads?: string | null;
  id_meta_ads?: string | null;
  id_ga4?: string | null;
  painel_url?: string | null;
  pasta_url?: string | null;
};
```

- [ ] **Step 3: Adicionar métodos updateCliente e deleteCliente em gestorApi**

No objeto `gestorApi`, adicione logo após o método `gestores`:

```typescript
  updateCliente: (id: string, data: ClienteEditData) =>
    apiCall<ClienteGestor>(`clientes/${id}`, "PATCH", data),

  deleteCliente: (id: string) =>
    apiCall<void>(`clientes/${id}`, "DELETE"),
```

- [ ] **Step 4: Adicionar PATCH ao proxy Next.js**

O proxy em `web/frontend/app/api/gestor/[...path]/route.ts` precisa exportar `PATCH` (atualmente só exporta GET, POST, DELETE). Na última linha do arquivo, substitua:

```typescript
export { handler as GET, handler as POST, handler as DELETE };
```

por:

```typescript
export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
```

- [ ] **Step 5: Verificar que o TypeScript compila sem erros**

```bash
cd web/frontend
npx tsc --noEmit 2>&1 | head -30
```

Esperado: sem erros (ou apenas erros pré-existentes não relacionados a este arquivo).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/lib/api-gestor.ts
git add web/frontend/app/api/gestor/
git commit -m "feat(frontend/api): ClienteGestor com IDs, updateCliente, deleteCliente, PATCH proxy"
```

---

## Task 6: Frontend — AbaConfiguracoes com tabela, modal e soft delete

**Files:**
- Modify: `web/frontend/app/gestor/page.tsx`

Contexto: `AbaConfiguracoes` é chamada na linha `{tab === "configuracoes" && <AbaConfiguracoes />}` do componente pai `GestorDashboard`. Precisamos passar os clientes filtrados e dois callbacks para atualizar o estado do pai.

- [ ] **Step 1: Adicionar tipo EditForm e substituir AbaConfiguracoes**

Em `web/frontend/app/gestor/page.tsx`, localize a função `AbaConfiguracoes` (que atualmente retorna apenas um placeholder) e substitua-a completamente pelo seguinte:

```tsx
// ── Tipos locais ─────────────────────────────────────────────────────────
type EditForm = {
  nome: string;
  categoria: string;
  gestor: string;
  id_google_ads: string;
  id_meta_ads: string;
  id_ga4: string;
  painel_url: string;
  pasta_url: string;
};

const CATEGORIAS = ["E-commerce", "Lead Com Site", "Lead Sem Site"] as const;

function emptyForm(c: ClienteGestor): EditForm {
  return {
    nome: c.nome,
    categoria: c.categoria,
    gestor: c.gestor ?? "",
    id_google_ads: c.id_google_ads ?? "",
    id_meta_ads: c.id_meta_ads ?? "",
    id_ga4: c.id_ga4 ?? "",
    painel_url: c.painel_url ?? "",
    pasta_url: c.pasta_url ?? "",
  };
}

// ── Aba Configurações ─────────────────────────────────────────────────────
function AbaConfiguracoes({
  clientes,
  onClienteUpdated,
  onClienteDeleted,
}: {
  clientes: ClienteGestor[];
  onClienteUpdated: (c: ClienteGestor) => void;
  onClienteDeleted: (id: string) => void;
}) {
  const [busca, setBusca] = useState("");
  const [editando, setEditando] = useState<ClienteGestor | null>(null);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [deletando, setDeletando] = useState<ClienteGestor | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);

  const filtrados = clientes.filter((c) =>
    c.nome.toLowerCase().includes(busca.toLowerCase()) ||
    c.categoria.toLowerCase().includes(busca.toLowerCase()),
  );

  function openEdit(c: ClienteGestor) {
    setEditando(c);
    setEditForm(emptyForm(c));
    setSaveErr(null);
  }

  function openDelete(c: ClienteGestor) {
    setDeletando(c);
    setDeleteErr(null);
  }

  async function handleSalvar(e: React.FormEvent) {
    e.preventDefault();
    if (!editando || !editForm) return;
    setSaving(true);
    setSaveErr(null);
    try {
      const updated = await gestorApi.updateCliente(editando.id, {
        nome: editForm.nome || null,
        categoria: editForm.categoria || null,
        gestor: editForm.gestor || null,
        id_google_ads: editForm.id_google_ads || null,
        id_meta_ads: editForm.id_meta_ads || null,
        id_ga4: editForm.id_ga4 || null,
        painel_url: editForm.painel_url || null,
        pasta_url: editForm.pasta_url || null,
      });
      onClienteUpdated(updated);
      setEditando(null);
      setEditForm(null);
    } catch (err: unknown) {
      setSaveErr(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  async function handleDesativar() {
    if (!deletando) return;
    setDeleting(true);
    setDeleteErr(null);
    try {
      await gestorApi.deleteCliente(deletando.id);
      onClienteDeleted(deletando.id);
      setDeletando(null);
    } catch (err: unknown) {
      setDeleteErr(err instanceof Error ? err.message : "Erro ao desativar");
    } finally {
      setDeleting(false);
    }
  }

  function field(
    label: string,
    key: keyof EditForm,
    type: "text" | "select" = "text",
  ) {
    if (!editForm) return null;
    const inputCls =
      "rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]";
    return (
      <label className="flex flex-col gap-1">
        <span className="eyebrow text-xs text-[var(--muted)]">{label}</span>
        {type === "select" ? (
          <select
            value={editForm[key]}
            onChange={(e) => setEditForm((f) => f && { ...f, [key]: e.target.value })}
            className={inputCls}
          >
            {CATEGORIAS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={editForm[key]}
            onChange={(e) => setEditForm((f) => f && { ...f, [key]: e.target.value })}
            className={inputCls}
          />
        )}
      </label>
    );
  }

  return (
    <div className="pb-24">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-2xl font-medium text-[var(--ink)]">Configurações</h1>
        <span className="eyebrow text-xs text-[var(--muted)]">{clientes.length} cliente{clientes.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Busca */}
      <div className="mb-4">
        <input
          type="search"
          placeholder="Buscar cliente ou categoria…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="w-full max-w-xs rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
        />
      </div>

      {/* Tabela */}
      <div className="overflow-x-auto rounded-lg border border-[var(--rule-soft)]">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
              {["Nome", "Categoria", "Gestor", "ID Google", "ID Meta", "ID GA4", ""].map((h) => (
                <th key={h} className="px-3 py-2 text-left font-medium text-[var(--muted)]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtrados.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-10 text-center text-sm text-[var(--muted)]">
                  Nenhum cliente encontrado.
                </td>
              </tr>
            ) : (
              filtrados.map((c, idx) => (
                <tr
                  key={c.id}
                  className={idx % 2 === 0 ? "bg-[var(--paper-soft)]" : "bg-[var(--paper)]"}
                >
                  <td className="px-3 py-2 font-medium text-[var(--ink)]">{c.nome}</td>
                  <td className="px-3 py-2 text-[var(--muted)]">{c.categoria}</td>
                  <td className="px-3 py-2 text-[var(--muted)]">{c.gestor ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-[var(--muted)]">{c.id_google_ads ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-[var(--muted)]">{c.id_meta_ads ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-[var(--muted)]">{c.id_ga4 ?? "—"}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openEdit(c)}
                        className="rounded border border-[var(--rule-soft)] px-2 py-1 text-xs text-[var(--muted)] transition hover:border-[var(--forest)] hover:text-[var(--forest)]"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => openDelete(c)}
                        className="rounded border border-[var(--rule-soft)] px-2 py-1 text-xs text-[var(--muted)] transition hover:border-[var(--crimson)] hover:text-[var(--crimson)]"
                      >
                        Desativar
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal de edição */}
      {editando && editForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] p-6 shadow-xl">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-display text-lg font-medium text-[var(--ink)]">
                Editar — {editando.nome}
              </h2>
              <button
                type="button"
                onClick={() => setEditando(null)}
                className="text-sm text-[var(--muted)] transition hover:text-[var(--ink)]"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSalvar} className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                {field("Nome", "nome")}
                {field("Categoria", "categoria", "select")}
                {field("Gestor", "gestor")}
                {field("ID Google Ads", "id_google_ads")}
                {field("ID Meta Ads", "id_meta_ads")}
                {field("ID GA4", "id_ga4")}
              </div>
              {field("Link Painel de Controle", "painel_url")}
              {field("Link Pasta", "pasta_url")}
              {saveErr && (
                <p className="text-xs text-[var(--crimson)]">{saveErr}</p>
              )}
              <div className="mt-1 flex gap-3">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 rounded-md bg-[var(--forest)] py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
                >
                  {saving ? "Salvando…" : "Salvar"}
                </button>
                <button
                  type="button"
                  onClick={() => setEditando(null)}
                  className="flex-1 rounded-md border border-[var(--rule-soft)] py-2 text-sm text-[var(--muted)] transition hover:border-[var(--ink)] hover:text-[var(--ink)]"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmação de desativação */}
      {deletando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] p-6 shadow-xl">
            <h2 className="font-display text-lg font-medium text-[var(--ink)]">Desativar cliente</h2>
            <p className="mt-2 text-sm text-[var(--ink-soft)]">
              Deseja desativar <strong>{deletando.nome}</strong>? O cliente não aparecerá mais nas
              listas, mas os dados históricos serão preservados.
            </p>
            {deleteErr && (
              <p className="mt-2 text-xs text-[var(--crimson)]">{deleteErr}</p>
            )}
            <div className="mt-4 flex gap-3">
              <button
                onClick={handleDesativar}
                disabled={deleting}
                className="flex-1 rounded-md bg-[var(--crimson,#c0392b)] py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
              >
                {deleting ? "Desativando…" : "Desativar"}
              </button>
              <button
                onClick={() => setDeletando(null)}
                className="flex-1 rounded-md border border-[var(--rule-soft)] py-2 text-sm text-[var(--muted)] transition hover:border-[var(--ink)] hover:text-[var(--ink)]"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Atualizar o componente pai GestorDashboard para passar clientes e callbacks**

No corpo de `GestorDashboard`, localize a linha que renderiza `<AbaConfiguracoes />` e substitua por:

```tsx
{tab === "configuracoes" && (
  <AbaConfiguracoes
    clientes={clientesFiltrados}
    onClienteUpdated={(updated) =>
      setClientes((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
    }
    onClienteDeleted={(id) =>
      setClientes((prev) => prev.filter((c) => c.id !== id))
    }
  />
)}
```

- [ ] **Step 3: Verificar que o TypeScript compila sem erros**

```bash
cd web/frontend
npx tsc --noEmit 2>&1 | head -30
```

Esperado: sem novos erros.

- [ ] **Step 4: Testar no browser**

1. Abra `http://localhost:3000/gestor` e faça login.
2. Clique na aba **Configurações** — deve aparecer a tabela de clientes.
3. Clique em **Editar** num cliente — modal deve abrir com os campos preenchidos.
4. Altere o gestor, clique **Salvar** — modal fecha, tabela atualiza sem reload.
5. Clique em **Desativar** — dialog de confirmação abre, clique **Desativar** — cliente some da tabela e da aba Clientes.
6. Verifique que o filtro de gestor da barra superior filtra a tabela de Configurações também.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/app/gestor/page.tsx
git commit -m "feat(frontend): aba Configurações com tabela, modal de edição e soft delete"
```
