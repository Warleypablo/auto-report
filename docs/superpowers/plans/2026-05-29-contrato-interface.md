# CONTRATO DE INTERFACE — Criativos v2

> **Fonte única de verdade** para as 7 fases (F0–F6) do design `docs/superpowers/specs/2026-05-29-criativos-v2-design.md`.
> Todos os nomes (tabelas, colunas, campos JSON, tipos TS, módulos, funções, fixtures) abaixo são **normativos**. Não renomeie nada sem atualizar este documento primeiro.
> Caminhos absolutos partem de `/Users/mac0267/Documents/auto-report-main`. Backend roda a partir de `web/backend/` (esse é o `sys.path` raiz dos imports — `from models...`, `from etl...`, `from schemas...`).

---

## 0. Convenções gerais (ancoradas no código existente)

- **ORM:** SQLAlchemy 2.x estilo `Mapped[...] = mapped_column(...)`, base única `from .base import Base` (`web/backend/models/base.py` → `class Base(DeclarativeBase)`).
- **PK UUID:** `Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)` (import `from sqlalchemy.dialects.postgresql import UUID`).
- **FK p/ clientes:** `ForeignKey("clientes.id", ondelete="CASCADE")`, sempre `index=True` na coluna FK (igual `Snapshot.cliente_id`).
- **Timestamps:** `mapped_column(DateTime(timezone=True), server_default=func.now())`; `atualizado_em` adiciona `onupdate=func.now()` (igual `Cliente`).
- **Enums:** `enum.Enum` subclasse de `str`, mapeada com `mapped_column(Enum(NomeEnum, name="<snake>"))` (igual `Categoria`/`Frequencia`). O `name=` é o nome do tipo Postgres.
- **Numéricos monetários:** `Numeric(20, 2)` (igual `Snapshot.faturamento`/`investimento`).
- **Todo módulo de model começa com** `from __future__ import annotations`.
- **Decimais → API:** convertidos para `float` com guarda `... if x is not None else None` (padrão `services/metricas.py` / `api/gestor.py`).

---

## 1. DDL / Models

### 1.1 `models/criativo.py` → `class Criativo` e `class CriativoThumb`

Arquivo: `web/backend/models/criativo.py`

```python
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Date, DateTime, Enum, ForeignKey, Integer,
    LargeBinary, Numeric, String, Text, UniqueConstraint, func,
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

**Notas normativas:**
- Índice composto adicional em `criativos`: `(cliente_id, rede)` → nome `ix_criativos_cliente_rede` (criado na migration; não declarar via `index=True` por ser composto).
- `LargeBinary` mapeia para `BYTEA` no Postgres (= o "BYTEA" do spec).
- `nome`, `primeiro_dia`, `ultimo_dia` são **nullable** (no 1º upsert de insights o metadado pode ainda não ter sido buscado).

### 1.2 `models/ad_insight.py` → `class AdInsight`

Arquivo: `web/backend/models/ad_insight.py`

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .criativo import RedeAnuncio  # reusa o MESMO Enum (não redefinir)


class AdInsight(Base):
    __tablename__ = "ad_insights"
    __table_args__ = (
        UniqueConstraint("cliente_id", "rede", "ad_id", "dia", name="uq_ad_insight_cliente_rede_ad_dia"),
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

**Decisão fechada (resolve o "a confirmar" do spec sobre frequency):** a coluna **`reach` ENTRA** em `ad_insights` (nullable BigInteger). `frequency` continua **não** sendo armazenada e só é exibida quando `Σreach > 0` (senão `null`).

**Índices de `ad_insights`** (criados na migration):
- `ix_ad_insights_cliente_id` (via `index=True` na coluna FK — já declarado).
- `ix_ad_insights_cliente_dia` → `(cliente_id, dia)`.
- `ix_ad_insights_cliente_rede_dia` → `(cliente_id, rede, dia)`.

**Importante:** O Enum Postgres `rede_anuncio` é **um único tipo** compartilhado por `criativos` e `ad_insights`. Na migration, criar o tipo **uma vez** e referenciá-lo com `create_type=False` na segunda tabela (ver §8).

### 1.3 Nova coluna `clientes.gestor_travado`

Editar `web/backend/models/cliente.py` → `class Cliente`, adicionar (após `gestor`):

```python
    gestor_travado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
```

(`Boolean` já está importado em `cliente.py`.)

### 1.4 Registro em `models/__init__.py`

Adicionar imports e `__all__` (manter ordem alfabética do arquivo):

```python
from .ad_insight import AdInsight
from .criativo import Criativo, CriativoThumb, RedeAnuncio, ThumbStatus
```

E acrescentar a `__all__`: `"AdInsight"`, `"Criativo"`, `"CriativoThumb"`, `"RedeAnuncio"`, `"ThumbStatus"`.

---

## 2. Enums (resumo normativo)

| Enum | Arquivo | `name=` (tipo PG) | Membros (Python) → valor string |
|---|---|---|---|
| `RedeAnuncio` | `models/criativo.py` | `rede_anuncio` | `META`→`"META"`, `GOOGLE`→`"GOOGLE"` |
| `ThumbStatus` | `models/criativo.py` | `thumb_status` | `PENDENTE`→`"pendente"`, `OK`→`"ok"`, `SEM_IMAGEM`→`"sem_imagem"`, `ERRO`→`"erro"` |

- `AdInsight` **importa** `RedeAnuncio` de `models/criativo.py` (não redefine).
- Na API/JSON, `rede` aparece em **minúsculas** (`"meta"` / `"google"`) — ver §3.1 e §4. A conversão Enum→lowercase é feita na camada de query/serialização (`row.rede.value.lower()`), não no Enum.

---

## 3. Query de agregação (abordagem ÚNICA — definida)

**Abordagem:** agregação **em SQL** (`GROUP BY`), com as métricas derivadas calculadas **em Python pós-query** a partir das somas (evita divisão-por-zero no SQL e mantém consistência com o estilo `_calc_roas`/`_calc_cpa` de `campaign_facebook_gather.py`). As somas são feitas no banco; as razões em Python.

Local: `web/backend/services/criativos.py` → função `agregar_criativos(...)` (ver §4.3). SELECT canônico (SQLAlchemy Core, sobre os models):

```sql
SELECT
    i.cliente_id                AS cliente_id,
    i.rede                      AS rede,
    i.ad_id                     AS ad_id,
    SUM(i.investimento)         AS investimento,
    SUM(i.faturamento)          AS faturamento,
    SUM(i.conversoes)           AS conversoes,
    SUM(i.leads)                AS leads,
    SUM(i.impressoes)           AS impressoes,
    SUM(i.clicks)               AS clicks,
    SUM(i.video_3s)             AS video_3s,
    SUM(i.reach)                AS reach
FROM ad_insights i
JOIN clientes c ON c.id = i.cliente_id
WHERE i.dia >= :de AND i.dia <= :ate
  AND c.ativo = true
  -- filtros opcionais: rede, categoria (IN), gestor, cliente.slug
  -- escopo de acesso: admin = sem filtro; gestor = c.id IN (usuario_clientes)
GROUP BY i.cliente_id, i.rede, i.ad_id
HAVING (:fat_min IS NULL OR SUM(i.faturamento) >= :fat_min)
   AND (:fat_max IS NULL OR SUM(i.faturamento) <= :fat_max)
   AND (:inv_min IS NULL OR SUM(i.investimento) >= :inv_min)
   AND (:inv_max IS NULL OR SUM(i.investimento) <= :inv_max)
```

**Filtros por cliente** (`cli_fat_min/max`, `cli_inv_min/max`): aplicados como **subquery/CTE** que agrega `ad_insights` por `cliente_id` no mesmo range e filtra os `cliente_id` que satisfazem as faixas, antes (ou via `JOIN`) da agregação por anúncio. Não usar o `HAVING` por-criativo para isso.

**Join de metadados:** o resultado por `(cliente_id, rede, ad_id)` é juntado com `criativos` (mesma tripla via `uq_criativo_cliente_rede_ad`) para obter `nome`, `tipo`, `preview_link`, `thumb_status`, e com `clientes` para `nome`/`slug`/`categoria`/`gestor`.

**Ordenação:** `order_by` ∈ `{roas, faturamento, investimento}` — aplicada **após** o cálculo das derivadas. Para `roas`, ordenar pela razão calculada (default DESC). `limit`/`offset` aplicados no fim. `total` = contagem de grupos **antes** de `limit/offset` (segunda query `COUNT(*)` sobre o mesmo conjunto filtrado).

**Métricas derivadas (Python, a partir das somas)** — fórmulas normativas:
- `roas = faturamento / investimento` se `investimento > 0` senão `None`
- `ctr = clicks / impressoes` se `impressoes > 0` senão `None` *(fração 0–1; o frontend formata em %)*
- `cpa = investimento / conversoes` se `conversoes > 0` senão `None`
- `cpl = investimento / leads` se `leads` (somado) `> 0` senão `None`
- `hook_rate = video_3s / impressoes` se `video_3s is not None and impressoes > 0` senão `None` (só Meta) *(fração 0–1)*
- `frequency = impressoes / reach` se `reach` (somado) `> 0` senão `None`

---

## 4. API

Endpoints adicionados em `web/backend/api/gestor.py` (mesmo `router = APIRouter()`; o app monta com prefix `/gestor`). Auth: `Depends(require_auth)`; escopo admin vs gestor segue o padrão existente (admin → todos `Cliente.ativo == True`; não-admin → `JOIN UsuarioCliente ON cliente_id WHERE usuario_id == user.id`).

### 4.1 `GET /gestor/criativos`

**Assinatura FastAPI (nomes e tipos de query params — normativos):**

```python
@router.get("/criativos", response_model=CriativosResponse)
def list_criativos(
    de: date = Query(..., description="YYYY-MM-DD inclusive"),
    ate: date = Query(..., description="YYYY-MM-DD inclusive"),
    rede: Literal["meta", "google", "todos"] = Query("todos"),
    categoria: list[Literal["ECOMMERCE", "LEAD_COM_SITE", "LEAD_SEM_SITE"]] | None = Query(None),
    gestor: str | None = Query(None),
    cliente: str | None = Query(None, description="slug do cliente"),
    fat_min: float | None = Query(None),
    fat_max: float | None = Query(None),
    inv_min: float | None = Query(None),
    inv_max: float | None = Query(None),
    cli_fat_min: float | None = Query(None),
    cli_fat_max: float | None = Query(None),
    cli_inv_min: float | None = Query(None),
    cli_inv_max: float | None = Query(None),
    order_by: Literal["roas", "faturamento", "investimento"] = Query("roas"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> CriativosResponse: ...
```

- `de`/`ate`: tipo `datetime.date` (FastAPI parseia `YYYY-MM-DD`).
- `categoria`: multi-valor (`?categoria=ECOMMERCE&categoria=LEAD_COM_SITE`). Valores = **chaves do enum** `Categoria` (não os labels). O atalho "Lead (ambos)" do frontend manda `LEAD_COM_SITE` + `LEAD_SEM_SITE`.
- `rede`: minúsculo. Mapear para `RedeAnuncio.META`/`GOOGLE` no service.

### 4.2 JSON de resposta (campos EXATOS)

```jsonc
{
  "items": [
    {
      "criativo_id": "uuid-string",
      "cliente_slug": "loja-fashion",
      "cliente_nome": "Loja Fashion",
      "categoria": "E-commerce",          // label do enum Categoria (.value)
      "gestor_nome": "Gabriel Taufner",   // pode ser null
      "rede": "meta",                     // "meta" | "google"
      "ad_id": "1203...",
      "nome": "Criativo Black Friday",    // pode ser null
      "tipo": "video",                    // pode ser null
      "preview_link": "https://...",      // pode ser null
      "thumb_url": "/api/gestor/criativos/<criativo_id>/thumb",  // null se thumb_status != "ok"
      "thumb_status": "ok",               // "pendente"|"ok"|"sem_imagem"|"erro"
      "investimento": 1234.56,
      "faturamento": 5678.90,
      "roas": 4.6,                        // null quando investimento==0
      "ctr": 0.0123,                      // fração; null quando impressoes==0
      "cpa": 12.34,                       // null
      "cpl": 8.90,                        // null
      "impressoes": 100000,
      "clicks": 1230,
      "conversoes": 100.0,
      "leads": 50,                        // null quando não aplicável
      "hook_rate": 0.21,                  // null exceto Meta com vídeo
      "frequency": 1.8                    // null quando reach não somável
    }
  ],
  "total": 873
}
```

- `thumb_url`: construída como `/api/gestor/criativos/{criativo_id}/thumb` (prefixo `/api` é o proxy do Next; o backend monta `/gestor/...`). Normativo: o **campo** chama-se `thumb_url` e aponta para a rota de §4.4. Quando `thumb_status != "ok"`, `thumb_url` é `null`.
- `categoria`: serializa o **label** (`Categoria.value`, ex. `"E-commerce"`) — consistente com `coerce_categoria` já usado nos outros schemas.

### 4.3 Schemas Pydantic

Arquivo **novo**: `web/backend/schemas/criativo.py`. Reexportar via `web/backend/schemas/__init__.py` (adicionar ao bloco de imports e ao `__all__`, como os demais).

```python
# web/backend/schemas/criativo.py
from __future__ import annotations

import uuid
from pydantic import BaseModel


class CriativoAgregado(BaseModel):
    criativo_id: uuid.UUID
    cliente_slug: str
    cliente_nome: str
    categoria: str
    gestor_nome: str | None = None
    rede: str            # "meta" | "google"
    ad_id: str
    nome: str | None = None
    tipo: str | None = None
    preview_link: str | None = None
    thumb_url: str | None = None
    thumb_status: str
    investimento: float
    faturamento: float
    roas: float | None = None
    ctr: float | None = None
    cpa: float | None = None
    cpl: float | None = None
    impressoes: int
    clicks: int
    conversoes: float
    leads: int | None = None
    hook_rate: float | None = None
    frequency: float | None = None


class CriativosResponse(BaseModel):
    items: list[CriativoAgregado]
    total: int
```

Lógica de agregação fica em `web/backend/services/criativos.py` → `agregar_criativos(session, *, de, ate, rede, categorias, gestor, cliente_slug, fat_min, fat_max, inv_min, inv_max, cli_fat_min, cli_fat_max, cli_inv_min, cli_inv_max, order_by, limit, offset, user) -> tuple[list[CriativoAgregado], int]`.

### 4.4 `GET /gestor/criativos/{criativo_id}/thumb`

> O spec escreve `/criativos/{id}/thumb`; como o router é montado sob `/gestor`, a rota canônica completa é **`/gestor/criativos/{criativo_id}/thumb`** (no router, path `"/criativos/{criativo_id}/thumb"`). O frontend acessa via `/api/gestor/criativos/{id}/thumb`.

```python
@router.get("/criativos/{criativo_id}/thumb")
def get_criativo_thumb(
    criativo_id: uuid.UUID,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> Response: ...
```

- Resposta: `fastapi.Response(content=<bytes>, media_type=thumb.mime)`.
- Headers: `Cache-Control: public, max-age=31536000, immutable` e `ETag: "<criativo_id>"` (suporta `If-None-Match` → `304`).
- `404` (`HTTPException(404)`) quando o `Criativo` não existe, o usuário não tem acesso ao `cliente_id`, **ou** `thumb_status != "ok"` / sem row em `criativo_thumbs`.
- Escopo de acesso: mesmo padrão (admin tudo; não-admin valida `UsuarioCliente`).

---

## 5. Tipos TypeScript (`web/frontend/lib/api-gestor.ts`)

Nomes de campos **idênticos** ao JSON de §4.2. Adicionar ao arquivo (não alterar os tipos `MetaAd`/`GoogleAd` legados — convivem):

```typescript
export type RedeAnuncio = "meta" | "google";
export type ThumbStatus = "pendente" | "ok" | "sem_imagem" | "erro";

export type CriativoAgregado = {
  criativo_id: string;
  cliente_slug: string;
  cliente_nome: string;
  categoria: string;
  gestor_nome: string | null;
  rede: RedeAnuncio;
  ad_id: string;
  nome: string | null;
  tipo: string | null;
  preview_link: string | null;
  thumb_url: string | null;
  thumb_status: ThumbStatus;
  investimento: number;
  faturamento: number;
  roas: number | null;
  ctr: number | null;
  cpa: number | null;
  cpl: number | null;
  impressoes: number;
  clicks: number;
  conversoes: number;
  leads: number | null;
  hook_rate: number | null;
  frequency: number | null;
};

export type CriativosResponse = {
  items: CriativoAgregado[];
  total: number;
};

export type CriativosParams = {
  de: string;            // YYYY-MM-DD
  ate: string;           // YYYY-MM-DD
  rede?: "meta" | "google" | "todos";
  categoria?: Array<"ECOMMERCE" | "LEAD_COM_SITE" | "LEAD_SEM_SITE">;
  gestor?: string;
  cliente?: string;      // slug
  fat_min?: number;
  fat_max?: number;
  inv_min?: number;
  inv_max?: number;
  cli_fat_min?: number;
  cli_fat_max?: number;
  cli_inv_min?: number;
  cli_inv_max?: number;
  order_by?: "roas" | "faturamento" | "investimento";
  limit?: number;
  offset?: number;
};
```

Função no objeto `gestorApi` (segue o padrão `apiCall<T>("path?...")`; multi-valor `categoria` vira `?categoria=A&categoria=B`):

```typescript
  criativos: (params: CriativosParams) => {
    const qs = new URLSearchParams();
    qs.set("de", params.de);
    qs.set("ate", params.ate);
    if (params.rede) qs.set("rede", params.rede);
    (params.categoria ?? []).forEach((c) => qs.append("categoria", c));
    if (params.gestor) qs.set("gestor", params.gestor);
    if (params.cliente) qs.set("cliente", params.cliente);
    for (const k of ["fat_min","fat_max","inv_min","inv_max","cli_fat_min","cli_fat_max","cli_inv_min","cli_inv_max","limit","offset"] as const) {
      const v = params[k];
      if (v !== undefined && v !== null) qs.set(k, String(v));
    }
    if (params.order_by) qs.set("order_by", params.order_by);
    return apiCall<CriativosResponse>(`criativos?${qs.toString()}`);
  },
```

> O `apiCall` prefixa `/api/gestor/`; portanto `criativos?...` resolve em `GET /api/gestor/criativos?...`. A thumb (`thumb_url`) já vem absoluta (`/api/gestor/criativos/{id}/thumb`) — usar direto em `<img src>`.
> Em `web/frontend/app/gestor/performance/page.tsx`, os tipos derivados existentes `RankedMetaAd`/`RankedGoogleAd` serão **substituídos** (F4) por um único `RankedCriativo = CriativoAgregado & { rank: number; rankDelta: number | null }`. A função `gestorApi.metricasBreakdown` deixa de ser usada nesta página (mantida para outras telas).

---

## 6. Módulos / funções do ETL

### 6.1 `web/backend/etl/collect_criativos.py` (novo — separado de `collect.py`)

Reusa o padrão de `collect.py`: `sys.path` para `core/`, `ThreadPoolExecutor(max_workers=settings.etl_threads)`, uma `SessionLocal()` por thread, `advisory_lock(engine, "etl:criativos:run", blocking=False)`.

Assinaturas normativas:

```python
def run_collect_criativos(backfill_meses: int | None = None, incremental: bool = False) -> dict:
    """Entrypoint. backfill_meses=6 → janela últimos 6 meses;
    incremental=True → dia anterior + janela de retroação de RETROACAO_DIAS (=3).
    Retorna {"ok": int, "fail": int, "total": int}.
    Exatamente um modo deve ser escolhido (backfill_meses XOR incremental)."""

def coletar_criativos_meta(cliente: Cliente, since: date, until: date,
                           session_factory: Callable[[], Session] = SessionLocal) -> bool:
    """Coleta insights ad-level Meta (time_increment=1) + metadados/thumb/link em lote.
    Faz upsert em ad_insights e criativos. Retorna True em sucesso."""

def coletar_criativos_google(cliente: Cliente, since: date, until: date,
                             session_factory: Callable[[], Session] = SessionLocal) -> bool:
    """Coleta ad_group_ad com segments.date via GAQL + thumb (Asset API) + deep-link.
    Search ads → thumb_status = SEM_IMAGEM. Retorna True em sucesso."""
```

- **Constante:** `RETROACAO_DIAS = 3` (módulo-level).
- **Meta:** reusa lógica de `core/categorias/ecommerce/campaign_facebook_gather.py` (mesmos campos de insights `ad_id,ad_name,spend,impressions,clicks,reach,actions,action_values,video_3_sec_watched_actions`, mesma extração `_extract_purchase_metrics` / `_video_3s_views_from_row`), porém com `time_increment=1` (diário, sem teto/`_TOP_N`) e batch de metadados (`?ids=...&fields=name,creative{thumbnail_url,image_url,object_type},preview_shareable_link`, lotes de `_BATCH_SIZE=50`).
- **Upsert idempotente:** `ad_insights` por `uq_ad_insight_cliente_rede_ad_dia`; `criativos` por `uq_criativo_cliente_rede_ad`. Usar `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(constraint=...)` (mesmo padrão de `etl/upsert.py`). Sugestão de helpers no mesmo arquivo: `upsert_ad_insight(session, **campos)` e `upsert_criativo(session, **campos)` (ou em `etl/upsert.py` ao lado de `upsert_snapshot`). `primeiro_dia`/`ultimo_dia` em `criativos` atualizados com `LEAST/GREATEST` no upsert.

### 6.2 `web/backend/etl/thumbnails.py` (novo)

```python
def fetch_e_redimensionar(url: str, *, lado_max: int = 320) -> tuple[bytes, str]:
    """Baixa a imagem da URL, redimensiona para `lado_max` px no maior lado
    (mantém proporção) e retorna (bytes, mime). mime tipicamente 'image/jpeg'.
    Levanta exceção em falha de download/decode (caller marca thumb_status=ERRO)."""
```

- HTTP: usar `httpx` (já em requirements; mesma lib usada no projeto). Imagem: **Pillow** (`from PIL import Image`).
- **Dedup por anúncio:** a chave é `criativos.id`; gravar/atualizar **uma** row em `criativo_thumbs` por criativo.

### 6.3 Entrypoint CLI

`python -m etl.collect_criativos` com flags `--backfill-meses N` e `--incremental` (mutuamente exclusivas) → chama `run_collect_criativos(...)`. (Cron no Render é item operacional do design; não faz parte deste contrato de código.)

### 6.4 Dependência nova — `web/backend/requirements.txt`

Adicionar (na seção de libs, antes de `# Test`):

```
Pillow>=11.0.0
```

(`httpx>=0.28.1` já presente; nada mais a adicionar.)

---

## 7. Convenções de teste

### 7.1 Backend — pytest

- **Framework:** `pytest` (já em `requirements.txt`: `pytest>=8.3.4`, `pytest-asyncio`, `pytest-postgresql`, `respx>=0.21.1`).
- **Pasta:** `web/backend/tests/`. Nome dos arquivos novos: `test_collect_criativos.py`, `test_thumbnails.py`, `test_criativos_api.py`, `test_criativos_service.py`.
- **Sem `pytest.ini`/`pyproject` de config** — rodar a partir de `web/backend/` (o `conftest.py` em `tests/` só ajusta `sys.path` para `web/backend/` e a raiz do repo; **não** define fixtures de DB).
- **Banco de teste (padrão real do projeto):** as fixtures de DB são **locais a cada arquivo de teste** (não há fixture global de DB no `conftest.py`). Padrão a seguir (de `tests/test_cliente_metricas.py` e `tests/test_cliente_auth.py`):
  ```python
  TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"
  # fixture:
  engine = create_engine(TEST_DB_URL)
  Base.metadata.drop_all(engine); Base.metadata.create_all(engine)  # cria as tabelas novas automaticamente
  TS = sessionmaker(bind=engine)
  # FastAPI: app.dependency_overrides[get_session] = ...; [get_settings] = lambda: Settings(database_url=TEST_DB_URL)
  ```
  Para testes de service/ETL que usam `SessionLocal` diretamente (ex. `tests/test_collect.py`), usar `from db import SessionLocal` e fixtures que criam/limpam um `Cliente` (padrão da fixture `cliente_id` em `test_collect.py`).
- **Fixtures reais disponíveis (citadas por nome):**
  - `cliente_id` — em `tests/test_collect.py` (cria `Cliente` ECOMMERCE via `SessionLocal`, cleanup no teardown). Modelo para criar fixtures análogas (`criativo`, `ad_insights`) nos novos arquivos.
  - `app_with_db` — em `tests/test_cliente_metricas.py` e `tests/test_cliente_auth.py` (monta FastAPI + cria schema `staging` + `Base.metadata.create_all`). **Replicar localmente** no novo `test_criativos_api.py` montando o `router` de `api.gestor` com prefix `/gestor` e overrides de `get_session`/`get_settings` + `require_auth`.
  - **Não existe** fixture global compartilhada de sessão/app no `conftest.py` — não assuma `db_session`/`client` globais.
- **Mock HTTP — `respx`:** está em `requirements.txt` mas **ainda não é usado** em nenhum teste atual (verificado: 0 ocorrências em `tests/`). Padrão normativo para os novos testes de coleta (Meta/Google/thumbnails usam `httpx`):
  ```python
  import respx, httpx
  @respx.mock
  def test_coletar_criativos_meta(...):
      respx.get(url__regex=r"https://graph\.facebook\.com/.*").mock(
          return_value=httpx.Response(200, json={"data": [...]})
      )
      ...
  ```
  > Atenção: o módulo **core** `campaign_facebook_gather.py` usa a lib `requests` (não `httpx`). Em `collect_criativos.py` o HTTP **deve usar `httpx`** para ser mockável com `respx`. Onde reusar funções do `core` que chamam `requests`, mockar via `unittest.mock.patch` (padrão de `tests/test_collect.py`: `patch("etl.collect._get_handler", ...)`).
- **Comando para rodar (exato), a partir de `web/backend/`:**
  ```
  cd web/backend && python -m pytest tests/ -v
  ```
  Um arquivo isolado: `cd web/backend && python -m pytest tests/test_criativos_api.py -v`. (Requer Postgres local com DB `vitrine_test` para os testes que tocam o banco; testes puros de `thumbnails`/cálculo de derivadas não precisam de DB.)

### 7.2 Frontend — Playwright

- **Config:** `web/frontend/playwright.config.ts` (`testDir: "./tests/e2e"`, `baseURL` via `E2E_BASE_URL` default `http://localhost:3010`, projeto `chromium`).
- **Pasta de specs:** `web/frontend/tests/e2e/`. Novos: `criativos.spec.ts`.
- **Comando:** a partir de `web/frontend/`: `npm run test:e2e` (= `playwright test`).
- **Não há** unit-test runner (vitest/jest) configurado em `package.json` — somente Playwright e2e.

---

## 8. Migrations (Alembic)

- **HEAD atual (down_revision da migration F0):** **`f79fffd5b218`** (arquivo `web/backend/alembic/versions/f79fffd5b218_add_insights.py`; nada aponta para ele — é a head verificada pela cadeia de revisões).
- **Geração:** `cd web/backend && python -m alembic revision -m "add_criativos_ad_insights_gestor_travado"` (autogenerate disponível, mas **revisar à mão** — ver §1 e abaixo). `env.py` usa `target_metadata = Base.metadata`, então os 3 models novos precisam estar importados em `models/__init__.py` (§1.4) antes de gerar.
- **Convenção de arquivo/revision id:** `<hash>_<slug>.py` (ex. `<hash>_add_criativos_ad_insights_gestor_travado.py`); header e identificadores no estilo de `f79fffd5b218_add_insights.py`:
  ```python
  revision: str = '<novo_hash>'
  down_revision: Union[str, Sequence[str], None] = 'f79fffd5b218'
  branch_labels: Union[str, Sequence[str], None] = None
  depends_on: Union[str, Sequence[str], None] = None
  ```
- **Conteúdo da migration F0 (uma única migration):**
  1. `op.add_column("clientes", sa.Column("gestor_travado", sa.Boolean(), nullable=False, server_default=sa.text("false")))` (estilo de `a654ab44e4cb_add_gestor_to_clientes.py`).
  2. Criar o tipo Enum `rede_anuncio` **uma vez** e reusar; criar tipo `thumb_status`. Padrão recomendado:
     ```python
     rede_enum = postgresql.ENUM("META", "GOOGLE", name="rede_anuncio")
     thumb_enum = postgresql.ENUM("pendente", "ok", "sem_imagem", "erro", name="thumb_status")
     rede_enum.create(op.get_bind(), checkfirst=True)
     thumb_enum.create(op.get_bind(), checkfirst=True)
     # nas create_table, referenciar com create_type=False:
     # sa.Column("rede", postgresql.ENUM(..., name="rede_anuncio", create_type=False), nullable=False)
     ```
  3. `op.create_table("criativos", ...)` com PK `id`, FK `cliente_id`→`clientes.id` `ondelete='CASCADE'`, `UniqueConstraint(... name="uq_criativo_cliente_rede_ad")`; índices `op.create_index(op.f("ix_criativos_cliente_id"), "criativos", ["cliente_id"])` e `op.create_index("ix_criativos_cliente_rede", "criativos", ["cliente_id","rede"])`.
  4. `op.create_table("criativo_thumbs", ...)` PK `criativo_id` (FK→`criativos.id` `ondelete='CASCADE'`), `conteudo` `sa.LargeBinary()`, `mime` `sa.String()`.
  5. `op.create_table("ad_insights", ...)` com `UniqueConstraint(name="uq_ad_insight_cliente_rede_ad_dia")`, `Numeric(20,2)`/`Numeric(12,2)`/`BigInteger`/`Integer` conforme §1.2; índices `ix_ad_insights_cliente_id`, `ix_ad_insights_cliente_dia` (`["cliente_id","dia"]`), `ix_ad_insights_cliente_rede_dia` (`["cliente_id","rede","dia"]`).
  - `downgrade()` na ordem inversa: drop indexes → drop `ad_insights` → `criativo_thumbs` → `criativos` → `op.drop_column("clientes","gestor_travado")` → `thumb_enum.drop(...)` / `rede_enum.drop(...)`.
- **F5 (`gestor_travado`):** a coluna é criada já na F0 (junto às tabelas, conforme acima). A F5 apenas a **consome** (re-sync com sobrescrita só quando `gestor_travado = false`); não cria migration própria.

---

## 9. Mapa fase → artefatos (para os 7 planos)

| Fase | Cria/edita |
|---|---|
| **F0** | `models/criativo.py`, `models/ad_insight.py`, `models/__init__.py`, `models/cliente.py` (+`gestor_travado`), migration `<hash>_add_criativos_ad_insights_gestor_travado.py` (down_revision `f79fffd5b218`), script/endpoint de auditoria de IDs |
| **F1** | `etl/collect_criativos.py` (`run_collect_criativos`, `coletar_criativos_meta`), `etl/thumbnails.py`, `requirements.txt` (+Pillow), `tests/test_collect_criativos.py`, `tests/test_thumbnails.py` |
| **F2** | `etl/collect_criativos.py` (`coletar_criativos_google`), thumb Google via Asset API |
| **F3** | `schemas/criativo.py` (`CriativoAgregado`, `CriativosResponse`), `schemas/__init__.py`, `services/criativos.py` (`agregar_criativos`), `api/gestor.py` (`list_criativos`, `get_criativo_thumb`), `tests/test_criativos_api.py`, `tests/test_criativos_service.py` |
| **F4** | `web/frontend/lib/api-gestor.ts` (tipos §5 + `gestorApi.criativos`), `app/gestor/performance/page.tsx`, `tests/e2e/criativos.spec.ts` |
| **F5** | `etl/sync_planilha.py` / endpoint sync (sobrescreve `cliente.gestor` quando `gestor_travado=false`), botão UI |
| **F6** | operacional (preencher IDs, sync, backfill, criar "Turbo") |

Arquivos-chave (caminhos absolutos): `/Users/mac0267/Documents/auto-report-main/web/backend/models/criativo.py`, `/.../models/ad_insight.py`, `/.../schemas/criativo.py`, `/.../services/criativos.py`, `/.../etl/collect_criativos.py`, `/.../etl/thumbnails.py`, `/.../api/gestor.py`, `/.../web/frontend/lib/api-gestor.ts`, `/.../web/frontend/app/gestor/performance/page.tsx`. HEAD do Alembic confirmada: **`f79fffd5b218`**.