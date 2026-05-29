# F1 — Coleta Meta ad-level diária + thumb rehospedada + preview link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Construir o ETL Meta ad-level diário do projeto Criativos v2: um novo módulo `web/backend/etl/collect_criativos.py` que, para cada `Cliente` ativo com `id_meta_ads`, chama a Meta Graph Insights API (`level=ad`, `time_increment=1`) para obter linhas diárias por anúncio, busca metadados/thumbnail/preview-link em lote, rehospeda a thumbnail (download + resize ~320px via Pillow → bytes no Postgres) e faz **upsert idempotente** em `ad_insights` (fato por dia), `criativos` (dimensão) e `criativo_thumbs` (bytes). Dois modos: **backfill** (últimos ~6 meses) e **incremental** (ontem + `RETROACAO_DIAS=3` de retroação, reescrevendo). Paralelização com `ThreadPoolExecutor`.

**Architecture:** Aditivo, separado do snapshot mensal (`etl/collect.py` permanece intacto). `collect_criativos.py` reusa o padrão de `collect.py` (`_ROOT = Path(__file__).resolve().parents[3]` na `sys.path` para a raiz do repo, `SessionLocal`/`engine` de `db`, `advisory_lock(engine, "etl:criativos:run", blocking=False)`, `ThreadPoolExecutor(max_workers=settings.etl_threads)`). A lógica de parsing de insights da Meta (`_extract_purchase_metrics`, `_video_3s_views_from_row`) é **reusada por import** de `core.categorias.ecommerce.campaign_facebook_gather` (funções puras de parsing — não fazem HTTP). O HTTP novo é feito com **`httpx`** (não `requests`) dentro de `collect_criativos.py`/`thumbnails.py` para ser mockável com `respx`. Upserts via `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(constraint=...)`, mesmo padrão de `etl/upsert.py`. Thumbnails em util isolado `etl/thumbnails.py` (Pillow).

**Tech Stack:** Python 3.14 (interpretador do projeto: `web/backend/.venv/bin/python`) / SQLAlchemy 2.x (`Mapped`/`mapped_column`) / FastAPI (não tocado nesta fase) / `httpx>=0.28.1` (HTTP) / Pillow (resize) / `pytest` + `respx>=0.23` (mock HTTP) + Postgres `vitrine_test` via `psycopg` v3 (fixtures de DB com `Base.metadata.create_all`). **Comando de teste canônico (a partir de `web/backend/`):** `.venv/bin/python -m pytest tests/ -v`.

> **NOTA NORMATIVA DE AMBIENTE (verificada):** Não existe o executável `python` neste ambiente, e o `/usr/bin/python3` global **não** tem `respx` instalado (e usa `psycopg2`, não `psycopg`). O interpretador correto, com `respx`, `psycopg` v3, `pytest-postgresql` e demais deps do projeto, é **`web/backend/.venv/bin/python`**. **Todos** os comandos `python`/`pip`/`pytest`/`python -m ...` deste plano usam esse interpretador. O DB `vitrine_test` está acessível em `postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test` (confirmado: `select 1` retorna `1`). O `web/backend/.venv` **não** tem Pillow instalado ainda (Task 1 instala).

**Pré-requisito (F0):** Esta fase assume que **F0 já está mergeada**: os models `models/criativo.py` (`Criativo`, `CriativoThumb`, `RedeAnuncio`, `ThumbStatus`), `models/ad_insight.py` (`AdInsight`), a coluna `clientes.gestor_travado`, o registro em `models/__init__.py` e a migration `<hash>_add_criativos_ad_insights_gestor_travado.py` (down_revision `f79fffd5b218`) existem. As fixtures de teste usam `Base.metadata.create_all(engine)`, então as tabelas novas são criadas automaticamente no `vitrine_test`. Antes da Task 1, confirme:
```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -c "from models import Criativo, CriativoThumb, AdInsight, RedeAnuncio, ThumbStatus; print('F0 ok')"
```
Saída esperada: `F0 ok`. Se falhar com `ImportError`, F0 não está pronta — **pare e finalize F0 primeiro**.

---

## File Structure

**Create:**
- `/Users/mac0267/Documents/auto-report-main/web/backend/etl/thumbnails.py` — util `fetch_e_redimensionar(url, *, lado_max=320) -> tuple[bytes, str]`: baixa imagem via `httpx`, redimensiona para `lado_max` px no maior lado (Pillow, mantém proporção, sem upscale), retorna `(bytes JPEG, "image/jpeg")`. Levanta exceção em falha de download/decode.
- `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py` — ETL Meta ad-level. `RETROACAO_DIAS = 3`; helpers de upsert `upsert_ad_insight` / `upsert_criativo` / `_gravar_thumb`; `_meta_insights_diarios(...)`, `_meta_metadados_lote(...)`; `coletar_criativos_meta(cliente, since, until, session_factory=SessionLocal) -> bool`; `run_collect_criativos(backfill_meses=None, incremental=False) -> dict`; CLI `python -m etl.collect_criativos`.
- `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_thumbnails.py` — testa resize (mock HTTP via respx + Pillow gera imagem in-memory) e propagação de erro.
- `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py` — testa upsert idempotente em `ad_insights`/`criativos`/`criativo_thumbs`, parsing de insights diários, metadados em lote, e `coletar_criativos_meta` end-to-end com respx mockando a Graph API.

**Modify:**
- `/Users/mac0267/Documents/auto-report-main/web/backend/requirements.txt` — adicionar `Pillow>=11.0.0` (imediatamente antes da seção `# Test`, linha 19).

---

### Task 1: Adicionar dependência Pillow

**Files:**
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/requirements.txt`

Steps:
- [ ] Confirmar F0 pronta: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -c "from models import Criativo, CriativoThumb, AdInsight, RedeAnuncio, ThumbStatus; print('F0 ok')"`. Saída esperada: `F0 ok`. (Se `ImportError`, F0 não está mergeada — pare.)
- [ ] Ler a linha-âncora: `cd /Users/mac0267/Documents/auto-report-main/web/backend && grep -n "httpx\|# Test" requirements.txt`. Saída esperada inclui `9:httpx>=0.28.1` e `19:# Test`.
- [ ] Editar `requirements.txt` com Edit: `old_string` = a linha `# Test` (verificada como linha 19), `new_string` = `Pillow>=11.0.0\n\n# Test`. (Não tocar nas demais linhas.)
- [ ] Instalar a dependência **no venv do projeto**: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pip install "Pillow>=11.0.0"`. Saída esperada: `Successfully installed pillow-...` (ou `Requirement already satisfied`).
- [ ] Verificar import no venv: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -c "from PIL import Image; print(Image.__name__)"`. Saída esperada: `PIL.Image`.
- [ ] Commit:
```
git add web/backend/requirements.txt
git commit -m "$(cat <<'EOF'
chore(backend): adiciona Pillow para resize de thumbnails (Criativos v2 F1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Util `etl/thumbnails.py` — resize ~320px (teste primeiro)

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_thumbnails.py`
- Create: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/thumbnails.py`

Steps:
- [ ] Escrever o teste que falha. Criar `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_thumbnails.py` com o conteúdo completo:
```python
import io

import httpx
import pytest
import respx
from PIL import Image

from etl.thumbnails import fetch_e_redimensionar


def _png_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (123, 45, 67)).save(buf, format="PNG")
    return buf.getvalue()


@respx.mock
def test_redimensiona_para_320_no_maior_lado():
    url = "https://example.com/img.png"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=_png_bytes(1000, 500),
                                    headers={"Content-Type": "image/png"})
    )

    conteudo, mime = fetch_e_redimensionar(url, lado_max=320)

    assert mime == "image/jpeg"
    img = Image.open(io.BytesIO(conteudo))
    assert max(img.size) == 320          # maior lado vira 320
    assert img.size == (320, 160)        # proporção 2:1 mantida


@respx.mock
def test_nao_aumenta_imagem_menor_que_lado_max():
    url = "https://example.com/small.png"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=_png_bytes(100, 80),
                                    headers={"Content-Type": "image/png"})
    )

    conteudo, mime = fetch_e_redimensionar(url, lado_max=320)

    assert mime == "image/jpeg"
    img = Image.open(io.BytesIO(conteudo))
    assert img.size == (100, 80)         # não faz upscale


@respx.mock
def test_levanta_excecao_em_http_erro():
    url = "https://example.com/broken.png"
    respx.get(url).mock(return_value=httpx.Response(404))

    with pytest.raises(Exception):
        fetch_e_redimensionar(url, lado_max=320)


@respx.mock
def test_levanta_excecao_em_conteudo_invalido():
    url = "https://example.com/notimage"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=b"isto nao eh uma imagem")
    )

    with pytest.raises(Exception):
        fetch_e_redimensionar(url, lado_max=320)
```
- [ ] Rodar e ver falhar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_thumbnails.py -v`. Saída esperada: erro de coleta `ModuleNotFoundError: No module named 'etl.thumbnails'` (ou `ImportError: cannot import name 'fetch_e_redimensionar'`).
- [ ] Implementação mínima. Criar `/Users/mac0267/Documents/auto-report-main/web/backend/etl/thumbnails.py` com o conteúdo completo:
```python
from __future__ import annotations

import io

import httpx
from PIL import Image

TIMEOUT = 30


def fetch_e_redimensionar(url: str, *, lado_max: int = 320) -> tuple[bytes, str]:
    """Baixa a imagem da URL, redimensiona para `lado_max` px no maior lado
    (mantém proporção, sem upscale) e retorna (bytes, mime).

    Sempre re-codifica como JPEG (mime 'image/jpeg'). Levanta exceção em
    falha de download (status != 2xx) ou decode (caller marca thumb_status=ERRO).
    """
    resp = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
    resp.raise_for_status()

    img = Image.open(io.BytesIO(resp.content))
    img.load()  # força o decode aqui (levanta se o conteúdo for inválido)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    largura, altura = img.size
    maior = max(largura, altura)
    if maior > lado_max:
        escala = lado_max / maior
        nova = (max(1, round(largura * escala)), max(1, round(altura * escala)))
        img = img.resize(nova, Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=82)
    return buf.getvalue(), "image/jpeg"
```
- [ ] Rodar e ver passar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_thumbnails.py -v`. Saída esperada: `4 passed`.
- [ ] Commit:
```
git add web/backend/etl/thumbnails.py web/backend/tests/test_thumbnails.py
git commit -m "$(cat <<'EOF'
feat(etl): util de rehospedagem de thumbnail com resize ~320px (Criativos v2 F1)

Baixa imagem via httpx, redimensiona com Pillow (maior lado=320, sem upscale)
e re-codifica como JPEG. Erros de download/decode propagam para o caller.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Helper `upsert_ad_insight` — idempotência do fato (teste primeiro)

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`
- Create: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`

Steps:
- [ ] Escrever o teste que falha. Criar `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py` com o conteúdo completo (este arquivo cresce nas Tasks 4–8):
```python
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from models import AdInsight, Categoria, Cliente, Criativo, RedeAnuncio, ThumbStatus
from models.base import Base

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture(scope="module")
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def cliente_id(TS):
    slug = f"test-criativos-{uuid.uuid4().hex[:8]}"
    with TS() as s:
        c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE, ativo=True)
        s.add(c)
        s.commit()
        cid = c.id
    yield cid
    with TS() as s:
        c = s.get(Cliente, cid)
        if c:
            s.delete(c)
            s.commit()


def test_upsert_ad_insight_insere_e_atualiza_sem_duplicar(TS, cliente_id):
    from etl.collect_criativos import upsert_ad_insight

    campos = dict(
        cliente_id=cliente_id,
        rede=RedeAnuncio.META,
        ad_id="ad-1",
        dia=date(2026, 5, 1),
        investimento=Decimal("10.00"),
        faturamento=Decimal("40.00"),
        conversoes=Decimal("2"),
        leads=None,
        impressoes=1000,
        clicks=10,
        video_3s=300,
        reach=800,
    )

    with TS() as s:
        upsert_ad_insight(s, **campos)
        s.commit()

    # mesmo (cliente, rede, ad_id, dia) com novos valores → UPDATE, não duplica
    campos2 = {**campos, "investimento": Decimal("99.00"), "faturamento": Decimal("123.00")}
    with TS() as s:
        upsert_ad_insight(s, **campos2)
        s.commit()

    with TS() as s:
        rows = s.scalars(
            select(AdInsight).where(
                AdInsight.cliente_id == cliente_id,
                AdInsight.ad_id == "ad-1",
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].investimento == Decimal("99.00")
        assert rows[0].faturamento == Decimal("123.00")
        assert rows[0].dia == date(2026, 5, 1)
```
- [ ] Rodar e ver falhar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v`. Saída esperada: erro de coleta `ModuleNotFoundError: No module named 'etl.collect_criativos'`.
- [ ] Implementação mínima. Criar `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py` com o conteúdo inicial (cabeçalho + `upsert_ad_insight`):
```python
from __future__ import annotations

import logging
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

# Garante que a raiz do repo (auto-report) está no PYTHONPATH para `core`/`config`.
# parents[3] = /Users/.../auto-report-main (mesmo cálculo de etl/collect.py).
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models import AdInsight, Criativo, CriativoThumb, RedeAnuncio, ThumbStatus

log = logging.getLogger(__name__)

RETROACAO_DIAS = 3


def upsert_ad_insight(
    session: Session,
    *,
    cliente_id: uuid.UUID,
    rede: RedeAnuncio,
    ad_id: str,
    dia: date,
    investimento: Decimal,
    faturamento: Decimal,
    conversoes: Decimal,
    leads: int | None,
    impressoes: int,
    clicks: int,
    video_3s: int | None,
    reach: int | None,
) -> None:
    """Upsert idempotente de uma linha diária de insight (constraint
    uq_ad_insight_cliente_rede_ad_dia). Reescreve as métricas no conflito —
    suporta a janela de retroação que reprocessa dias já gravados."""
    payload = dict(
        cliente_id=cliente_id,
        rede=rede,
        ad_id=ad_id,
        dia=dia,
        investimento=investimento,
        faturamento=faturamento,
        conversoes=conversoes,
        leads=leads,
        impressoes=impressoes,
        clicks=clicks,
        video_3s=video_3s,
        reach=reach,
    )
    stmt = insert(AdInsight).values(**payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ad_insight_cliente_rede_ad_dia",
        set_={
            k: v
            for k, v in payload.items()
            if k not in {"cliente_id", "rede", "ad_id", "dia"}
        },
    )
    session.execute(stmt)
```
> Nota: `func` e `select` já são importados aqui no topo porque serão usados por `upsert_criativo` (Task 4) e por `coletar_criativos_meta` (Task 7). Mantê-los no import inicial evita reedição do bloco de imports.
- [ ] Rodar e ver passar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v`. Saída esperada: `1 passed`.
- [ ] Commit:
```
git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
git commit -m "$(cat <<'EOF'
feat(etl): upsert idempotente de ad_insights por dia (Criativos v2 F1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Helper `upsert_criativo` — dimensão + janela primeiro_dia/ultimo_dia (teste primeiro)

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py` (adicionar)
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`

Steps:
- [ ] Adicionar o teste que falha. Acrescentar ao final de `tests/test_collect_criativos.py` (o import de `Criativo`/`ThumbStatus` já está na linha `from models import AdInsight, Categoria, Cliente, Criativo, RedeAnuncio, ThumbStatus` da Task 3):
```python
def test_upsert_criativo_insere_metadados_e_expande_janela(TS, cliente_id):
    from etl.collect_criativos import upsert_criativo

    with TS() as s:
        upsert_criativo(
            s,
            cliente_id=cliente_id,
            rede=RedeAnuncio.META,
            ad_id="ad-9",
            nome="Criativo BF",
            tipo="video",
            preview_link="https://fb.com/preview/9",
            dia=date(2026, 5, 10),
        )
        s.commit()

    # dia anterior expande primeiro_dia; dia posterior expande ultimo_dia
    with TS() as s:
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-9",
            nome="Criativo BF", tipo="video",
            preview_link="https://fb.com/preview/9", dia=date(2026, 5, 5),
        )
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-9",
            nome="Criativo BF v2", tipo="video",
            preview_link="https://fb.com/preview/9", dia=date(2026, 5, 20),
        )
        s.commit()

    with TS() as s:
        rows = s.scalars(
            select(Criativo).where(
                Criativo.cliente_id == cliente_id, Criativo.ad_id == "ad-9"
            )
        ).all()
        assert len(rows) == 1
        cri = rows[0]
        assert cri.nome == "Criativo BF v2"      # metadado atualizado
        assert cri.tipo == "video"
        assert cri.preview_link == "https://fb.com/preview/9"
        assert cri.thumb_status == ThumbStatus.PENDENTE  # default no insert
        assert cri.primeiro_dia == date(2026, 5, 5)      # LEAST expandiu p/ trás
        assert cri.ultimo_dia == date(2026, 5, 20)       # GREATEST expandiu p/ frente


def test_upsert_criativo_preserva_thumb_status_existente(TS, cliente_id):
    from etl.collect_criativos import upsert_criativo

    with TS() as s:
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-7",
            nome="X", tipo="image", preview_link=None, dia=date(2026, 5, 1),
        )
        s.commit()
        cri = s.scalar(
            select(Criativo).where(
                Criativo.cliente_id == cliente_id, Criativo.ad_id == "ad-7"
            )
        )
        cri.thumb_status = ThumbStatus.OK
        s.commit()

    # re-upsert (novo dia) NÃO deve resetar thumb_status para PENDENTE
    with TS() as s:
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-7",
            nome="X2", tipo="image", preview_link=None, dia=date(2026, 5, 2),
        )
        s.commit()

    with TS() as s:
        cri = s.scalar(
            select(Criativo).where(
                Criativo.cliente_id == cliente_id, Criativo.ad_id == "ad-7"
            )
        )
        assert cri.thumb_status == ThumbStatus.OK
        assert cri.nome == "X2"
```
- [ ] Rodar e ver falhar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k upsert_criativo`. Saída esperada: `ImportError: cannot import name 'upsert_criativo' from 'etl.collect_criativos'`.
- [ ] Implementação mínima. Em `etl/collect_criativos.py`, adicionar a função `upsert_criativo` logo após `upsert_ad_insight`. O `on_conflict_do_update` usa `func.least`/`func.greatest` com `Criativo.__table__.c.<col>` (valor já gravado) e **não** inclui `thumb_status` no `set_` (preserva o existente). (`func` e `select` já estão importados desde a Task 3.)
```python
def upsert_criativo(
    session: Session,
    *,
    cliente_id: uuid.UUID,
    rede: RedeAnuncio,
    ad_id: str,
    nome: str | None,
    tipo: str | None,
    preview_link: str | None,
    dia: date,
) -> None:
    """Upsert idempotente da dimensão (constraint uq_criativo_cliente_rede_ad).
    No conflito: atualiza nome/tipo/preview_link, expande primeiro_dia (LEAST)
    e ultimo_dia (GREATEST), e PRESERVA thumb_status (gerenciado pela coleta de
    thumb, não pelo upsert de metadados)."""
    payload = dict(
        cliente_id=cliente_id,
        rede=rede,
        ad_id=ad_id,
        nome=nome,
        tipo=tipo,
        preview_link=preview_link,
        primeiro_dia=dia,
        ultimo_dia=dia,
    )
    stmt = insert(Criativo).values(**payload)
    col = Criativo.__table__.c
    stmt = stmt.on_conflict_do_update(
        constraint="uq_criativo_cliente_rede_ad",
        set_={
            "nome": stmt.excluded.nome,
            "tipo": stmt.excluded.tipo,
            "preview_link": stmt.excluded.preview_link,
            "primeiro_dia": func.least(col.primeiro_dia, stmt.excluded.primeiro_dia),
            "ultimo_dia": func.greatest(col.ultimo_dia, stmt.excluded.ultimo_dia),
        },
    )
    session.execute(stmt)
```
- [ ] Rodar e ver passar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v`. Saída esperada: `3 passed`.
- [ ] Commit:
```
git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
git commit -m "$(cat <<'EOF'
feat(etl): upsert idempotente da dimensao criativos com janela primeiro/ultimo dia (Criativos v2 F1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Parsing de insights diários da Meta via httpx (teste primeiro)

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py` (adicionar)
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`

Steps:
- [ ] Adicionar o teste que falha. Acrescentar ao final de `tests/test_collect_criativos.py`:
```python
import httpx
import respx


@respx.mock
def test_meta_insights_diarios_parseia_linhas_por_dia():
    from etl.collect_criativos import _meta_insights_diarios

    payload = {
        "data": [
            {
                "ad_id": "ad-1", "ad_name": "Criativo A", "date_start": "2026-05-01",
                "spend": "10.50", "impressions": "1000", "clicks": "15", "reach": "800",
                "actions": [{"action_type": "omni_purchase", "value": "3"}],
                "action_values": [{"action_type": "omni_purchase", "value": "120.00"}],
                "video_3_sec_watched_actions": [{"value": "250"}],
            },
            {
                "ad_id": "ad-1", "ad_name": "Criativo A", "date_start": "2026-05-02",
                "spend": "5.00", "impressions": "400", "clicks": "4", "reach": "390",
                "actions": [], "action_values": [],
            },
        ]
    }
    respx.get(url__regex=r"https://graph\.facebook\.com/.*/insights").mock(
        return_value=httpx.Response(200, json=payload)
    )

    linhas = _meta_insights_diarios("act_999", date(2026, 5, 1), date(2026, 5, 2))

    assert len(linhas) == 2
    d1 = next(l for l in linhas if l["dia"] == date(2026, 5, 1))
    assert d1["ad_id"] == "ad-1"
    assert d1["ad_name"] == "Criativo A"
    assert d1["investimento"] == Decimal("10.50")
    assert d1["faturamento"] == Decimal("120.00")
    assert d1["conversoes"] == Decimal("3")
    assert d1["impressoes"] == 1000
    assert d1["clicks"] == 15
    assert d1["reach"] == 800
    assert d1["video_3s"] == 250

    d2 = next(l for l in linhas if l["dia"] == date(2026, 5, 2))
    assert d2["faturamento"] == Decimal("0")
    assert d2["conversoes"] == Decimal("0")
    assert d2["video_3s"] is None      # sem campo de vídeo → None
```
- [ ] Rodar e ver falhar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k meta_insights_diarios`. Saída esperada: `ImportError: cannot import name '_meta_insights_diarios'`.
- [ ] Implementação. Em `etl/collect_criativos.py`, adicionar imports do core (reuso do parsing) e constantes Meta, e a função `_meta_insights_diarios`. Acrescentar ao bloco de imports do topo, **após** a linha `from models import ...` (a `sys.path` já foi ajustada antes, então `core`/`config` resolvem):
```python
import json

import httpx

from config.settings import ACCESS_TOKEN_META_SYSTEM
from core.categorias.ecommerce.campaign_facebook_gather import (
    _extract_purchase_metrics,
    _video_3s_views_from_row,
)

META_API_VERSION = "v23.0"
TIMEOUT = 30
_BATCH_SIZE = 50
_ATTR_WINDOW = ["7d_click"]
```
E adicionar a função (após `upsert_criativo`):
```python
def _meta_insights_diarios(ad_account_id: str, since: date, until: date) -> list[dict]:
    """Chama /act_{id}/insights level=ad time_increment=1 e devolve uma lista de
    dicts normalizados, um por (ad_id, dia). Reusa o parsing de actions/
    action_values/video_3s do core (campaign_facebook_gather)."""
    acct_path = f"act_{ad_account_id.removeprefix('act_')}"
    url = f"https://graph.facebook.com/{META_API_VERSION}/{acct_path}/insights"
    params = {
        "level": "ad",
        "time_increment": 1,
        "time_range": json.dumps(
            {"since": since.strftime("%Y-%m-%d"), "until": until.strftime("%Y-%m-%d")},
            separators=(",", ":"),
        ),
        "fields": (
            "ad_id,ad_name,spend,impressions,clicks,reach,"
            "actions,action_values,video_3_sec_watched_actions"
        ),
        "action_attribution_windows": json.dumps(_ATTR_WINDOW, separators=(",", ":")),
        "action_report_time": "conversion",
        "limit": 5000,
        "access_token": ACCESS_TOKEN_META_SYSTEM,
    }

    linhas: list[dict] = []
    next_url: str | None = url
    next_params: dict | None = params
    while next_url:
        resp = httpx.get(next_url, params=next_params, timeout=TIMEOUT,
                         follow_redirects=True)
        resp.raise_for_status()
        body = resp.json()
        for row in body.get("data", []):
            ad_id = row.get("ad_id")
            if not ad_id:
                continue
            conv, fat = _extract_purchase_metrics(
                row.get("actions") or [], row.get("action_values") or []
            )
            linhas.append({
                "ad_id": ad_id,
                "ad_name": row.get("ad_name"),
                "dia": date.fromisoformat(row["date_start"]),
                "investimento": Decimal(str(row.get("spend") or "0")),
                "faturamento": Decimal(str(fat or 0)),
                "conversoes": Decimal(str(conv or 0)),
                "impressoes": int(row.get("impressions") or 0),
                "clicks": int(row.get("clicks") or 0),
                "reach": int(row["reach"]) if row.get("reach") is not None else None,
                "video_3s": _video_3s_views_from_row(row),
            })
        paging = body.get("paging", {}) or {}
        next_url = paging.get("next")
        next_params = None  # o link "next" já vem com todos os params/cursor
    return linhas
```
> **Nota normativa (correção):** o módulo `core` constrói o path como `f"act_{ad_account_id.lstrip('act_')}"`, mas `str.lstrip` remove **caracteres** (`a`,`c`,`t`,`_`), corrompendo IDs cujos dígitos iniciem com esses chars (ex.: `"caa_99".lstrip("act_") == "99"`). Em código **novo** usamos `removeprefix("act_")` (verificado: idêntico para `"act_777"`/`"777"`, sem o footgun). Não reimplementar `_extract_purchase_metrics`/`_video_3s_views_from_row` — são puros (não fazem HTTP), por isso o teste não precisa mocká-los.
- [ ] Rodar e ver passar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k meta_insights_diarios`. Saída esperada: `1 passed`.
- [ ] Commit:
```
git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
git commit -m "$(cat <<'EOF'
feat(etl): coleta de insights Meta ad-level diarios via httpx (Criativos v2 F1)

Reusa parsing de actions/action_values/video_3s do core; time_increment=1,
sem teto de ads, com paginacao via paging.next. Usa removeprefix('act_') para
o path da conta (evita o footgun de lstrip).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Metadados/thumb/preview em lote (teste primeiro)

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py` (adicionar)
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`

Steps:
- [ ] Adicionar o teste que falha. Acrescentar ao final de `tests/test_collect_criativos.py`:
```python
@respx.mock
def test_meta_metadados_lote_extrai_nome_tipo_thumb_e_link():
    from etl.collect_criativos import _meta_metadados_lote

    payload = {
        "ad-1": {
            "id": "ad-1",
            "name": "Criativo A",
            "preview_shareable_link": "https://fb.com/p/1",
            "creative": {
                "object_type": "VIDEO",
                "image_url": "https://cdn.fb.com/img1.jpg",
                "thumbnail_url": "https://cdn.fb.com/thumb1.jpg",
            },
        },
        "ad-2": {
            "id": "ad-2",
            "name": "Criativo B",
            "preview_shareable_link": "https://fb.com/p/2",
            "creative": {"object_type": "SHARE", "thumbnail_url": "https://cdn.fb.com/thumb2.jpg"},
        },
    }
    respx.get(url__regex=r"https://graph\.facebook\.com/v[\d.]+\?.*").mock(
        return_value=httpx.Response(200, json=payload)
    )

    meta = _meta_metadados_lote(["ad-1", "ad-2"])

    assert meta["ad-1"]["nome"] == "Criativo A"
    assert meta["ad-1"]["tipo"] == "video"                          # object_type lower
    assert meta["ad-1"]["preview_link"] == "https://fb.com/p/1"
    assert meta["ad-1"]["imagem_url"] == "https://cdn.fb.com/img1.jpg"    # image_url preferido
    assert meta["ad-2"]["imagem_url"] == "https://cdn.fb.com/thumb2.jpg"  # fallback thumbnail_url
    assert meta["ad-2"]["tipo"] == "share"
```
- [ ] Rodar e ver falhar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k meta_metadados_lote`. Saída esperada: `ImportError: cannot import name '_meta_metadados_lote'`.
- [ ] Implementação. Em `etl/collect_criativos.py`, adicionar (após `_meta_insights_diarios`):
```python
def _meta_metadados_lote(ad_ids: list[str]) -> dict[str, dict]:
    """Busca nome/tipo/preview-link/imagem por ad_id em lotes de _BATCH_SIZE via
    endpoint ?ids=. Retorna {ad_id: {nome, tipo, preview_link, imagem_url}}.
    imagem_url prefere creative.image_url e cai para creative.thumbnail_url."""
    out: dict[str, dict] = {}
    base = f"https://graph.facebook.com/{META_API_VERSION}"
    for i in range(0, len(ad_ids), _BATCH_SIZE):
        chunk = [a for a in ad_ids[i : i + _BATCH_SIZE] if a]
        if not chunk:
            continue
        params = {
            "ids": ",".join(chunk),
            "fields": "name,creative{thumbnail_url,image_url,object_type},preview_shareable_link",
            "access_token": ACCESS_TOKEN_META_SYSTEM,
        }
        resp = httpx.get(base, params=params, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        for ad_id, obj in (resp.json() or {}).items():
            creative = obj.get("creative") or {}
            object_type = creative.get("object_type")
            out[ad_id] = {
                "nome": obj.get("name"),
                "tipo": object_type.lower() if object_type else None,
                "preview_link": obj.get("preview_shareable_link"),
                "imagem_url": creative.get("image_url") or creative.get("thumbnail_url"),
            }
    return out
```
- [ ] Rodar e ver passar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k meta_metadados_lote`. Saída esperada: `1 passed`.
- [ ] Commit:
```
git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
git commit -m "$(cat <<'EOF'
feat(etl): busca em lote de metadados/thumb/preview-link Meta (Criativos v2 F1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: `coletar_criativos_meta` end-to-end + gravação da thumb (teste primeiro)

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py` (adicionar)
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`

Steps:
- [ ] Adicionar o teste que falha. Acrescentar ao final de `tests/test_collect_criativos.py`:
```python
import io as _io

from PIL import Image as _Image

from models import CriativoThumb


def _png(w, h):
    buf = _io.BytesIO()
    _Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


@respx.mock
def test_coletar_criativos_meta_grava_insights_criativos_e_thumb(TS, cliente_id):
    from etl.collect_criativos import coletar_criativos_meta

    with TS() as s:
        c = s.get(Cliente, cliente_id)
        c.id_meta_ads = "act_777"
        s.commit()

    insights = {
        "data": [
            {
                "ad_id": "ad-1", "ad_name": "Criativo A", "date_start": "2026-05-01",
                "spend": "10.00", "impressions": "1000", "clicks": "15", "reach": "800",
                "actions": [{"action_type": "omni_purchase", "value": "3"}],
                "action_values": [{"action_type": "omni_purchase", "value": "120.00"}],
                "video_3_sec_watched_actions": [{"value": "250"}],
            }
        ]
    }
    metadados = {
        "ad-1": {
            "id": "ad-1", "name": "Criativo A",
            "preview_shareable_link": "https://fb.com/p/1",
            "creative": {"object_type": "VIDEO", "image_url": "https://cdn.fb.com/img1.jpg"},
        }
    }

    respx.get(url__regex=r"https://graph\.facebook\.com/.*/insights").mock(
        return_value=httpx.Response(200, json=insights)
    )
    respx.get(url__regex=r"https://graph\.facebook\.com/v[\d.]+\?.*").mock(
        return_value=httpx.Response(200, json=metadados)
    )
    respx.get("https://cdn.fb.com/img1.jpg").mock(
        return_value=httpx.Response(200, content=_png(640, 480),
                                    headers={"Content-Type": "image/png"})
    )

    with TS() as s:
        cliente = s.get(Cliente, cliente_id)
        ok = coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1),
                                    session_factory=TS)
    assert ok is True

    with TS() as s:
        ins = s.scalars(
            select(AdInsight).where(AdInsight.cliente_id == cliente_id)
        ).all()
        assert len(ins) == 1
        assert ins[0].investimento == Decimal("10.00")
        assert ins[0].faturamento == Decimal("120.00")

        cri = s.scalar(
            select(Criativo).where(Criativo.cliente_id == cliente_id)
        )
        assert cri.nome == "Criativo A"
        assert cri.tipo == "video"
        assert cri.preview_link == "https://fb.com/p/1"
        assert cri.thumb_status == ThumbStatus.OK

        thumb = s.get(CriativoThumb, cri.id)
        assert thumb is not None
        assert thumb.mime == "image/jpeg"
        img = _Image.open(_io.BytesIO(thumb.conteudo))
        assert max(img.size) == 320


@respx.mock
def test_coletar_criativos_meta_idempotente_em_rerun(TS, cliente_id):
    from etl.collect_criativos import coletar_criativos_meta

    with TS() as s:
        c = s.get(Cliente, cliente_id)
        c.id_meta_ads = "act_777"
        s.commit()

    insights = {
        "data": [
            {
                "ad_id": "ad-1", "ad_name": "Criativo A", "date_start": "2026-05-01",
                "spend": "10.00", "impressions": "1000", "clicks": "15", "reach": "800",
                "actions": [], "action_values": [],
            }
        ]
    }
    respx.get(url__regex=r"https://graph\.facebook\.com/.*/insights").mock(
        return_value=httpx.Response(200, json=insights)
    )
    respx.get(url__regex=r"https://graph\.facebook\.com/v[\d.]+\?.*").mock(
        return_value=httpx.Response(200, json={"ad-1": {"id": "ad-1", "name": "A",
            "creative": {"object_type": "SHARE"}}})  # sem imagem → SEM_IMAGEM
    )

    with TS() as s:
        cliente = s.get(Cliente, cliente_id)
        coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1), session_factory=TS)
    with TS() as s:
        cliente = s.get(Cliente, cliente_id)
        coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1), session_factory=TS)

    with TS() as s:
        ins = s.scalars(select(AdInsight).where(AdInsight.cliente_id == cliente_id)).all()
        cri = s.scalars(select(Criativo).where(Criativo.cliente_id == cliente_id)).all()
        assert len(ins) == 1     # rerun não duplica o fato
        assert len(cri) == 1     # rerun não duplica a dimensão
        assert cri[0].thumb_status == ThumbStatus.SEM_IMAGEM


def test_coletar_criativos_meta_sem_id_retorna_false(TS, cliente_id):
    from etl.collect_criativos import coletar_criativos_meta

    with TS() as s:
        cliente = s.get(Cliente, cliente_id)   # id_meta_ads = None
        ok = coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1),
                                    session_factory=TS)
    assert ok is False
```
- [ ] Rodar e ver falhar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k coletar_criativos_meta`. Saída esperada: `ImportError: cannot import name 'coletar_criativos_meta'`.
- [ ] Implementação. Em `etl/collect_criativos.py`, acrescentar ao bloco de imports do topo (após os imports de `core`/`config` da Task 5):
```python
from collections.abc import Callable

from db import SessionLocal, engine

from .thumbnails import fetch_e_redimensionar
```
E adicionar as funções (após `_meta_metadados_lote`):
```python
def _gravar_thumb(session: Session, criativo_id: uuid.UUID, conteudo: bytes, mime: str) -> None:
    """Upsert idempotente de criativo_thumbs (PK criativo_id)."""
    payload = dict(criativo_id=criativo_id, conteudo=conteudo, mime=mime)
    stmt = insert(CriativoThumb).values(**payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=[CriativoThumb.criativo_id],
        set_={"conteudo": stmt.excluded.conteudo, "mime": stmt.excluded.mime},
    )
    session.execute(stmt)


def coletar_criativos_meta(
    cliente: Cliente,
    since: date,
    until: date,
    session_factory: Callable[[], Session] = SessionLocal,
) -> bool:
    """Coleta insights ad-level Meta (time_increment=1) + metadados/thumb/link em
    lote. Upsert em ad_insights e criativos; rehospeda a thumb. Retorna True em
    sucesso (False se o cliente não tem id_meta_ads ou se a coleta falhou)."""
    ad_account_id = cliente.id_meta_ads
    if not ad_account_id:
        log.warning("criativos_meta_sem_id", extra={"cliente": cliente.nome})
        return False

    cliente_id = cliente.id
    try:
        linhas = _meta_insights_diarios(ad_account_id, since, until)
    except Exception:
        log.exception("criativos_meta_insights_falhou", extra={"cliente": cliente.nome})
        return False

    if not linhas:
        log.info("criativos_meta_sem_dados", extra={"cliente": cliente.nome})
        return True

    ad_ids = sorted({l["ad_id"] for l in linhas})
    session = session_factory()
    own = session_factory is SessionLocal
    try:
        # 1) Grava o fato (ad_insights) e o esqueleto da dimensão (criativos).
        for l in linhas:
            upsert_ad_insight(
                session,
                cliente_id=cliente_id,
                rede=RedeAnuncio.META,
                ad_id=l["ad_id"],
                dia=l["dia"],
                investimento=l["investimento"],
                faturamento=l["faturamento"],
                conversoes=l["conversoes"],
                leads=None,
                impressoes=l["impressoes"],
                clicks=l["clicks"],
                video_3s=l["video_3s"],
                reach=l["reach"],
            )
            upsert_criativo(
                session,
                cliente_id=cliente_id,
                rede=RedeAnuncio.META,
                ad_id=l["ad_id"],
                nome=l["ad_name"],
                tipo=None,
                preview_link=None,
                dia=l["dia"],
            )
        session.commit()

        # 2) Metadados em lote (nome/tipo/preview/imagem) + thumb.
        try:
            metadados = _meta_metadados_lote(ad_ids)
        except Exception:
            log.exception("criativos_meta_metadados_falhou", extra={"cliente": cliente.nome})
            metadados = {}

        for ad_id in ad_ids:
            meta = metadados.get(ad_id) or {}
            upsert_criativo(
                session,
                cliente_id=cliente_id,
                rede=RedeAnuncio.META,
                ad_id=ad_id,
                nome=meta.get("nome"),
                tipo=meta.get("tipo"),
                preview_link=meta.get("preview_link"),
                dia=until,
            )
            session.flush()
            criativo = session.scalar(
                select(Criativo).where(
                    Criativo.cliente_id == cliente_id,
                    Criativo.rede == RedeAnuncio.META,
                    Criativo.ad_id == ad_id,
                )
            )
            imagem_url = meta.get("imagem_url")
            if not imagem_url:
                criativo.thumb_status = ThumbStatus.SEM_IMAGEM
                continue
            try:
                conteudo, mime = fetch_e_redimensionar(imagem_url, lado_max=320)
                _gravar_thumb(session, criativo.id, conteudo, mime)
                criativo.thumb_status = ThumbStatus.OK
            except Exception:
                log.exception("criativos_meta_thumb_falhou",
                              extra={"cliente": cliente.nome, "ad_id": ad_id})
                criativo.thumb_status = ThumbStatus.ERRO
        session.commit()
        return True
    except Exception:
        session.rollback()
        log.exception("criativos_meta_falhou", extra={"cliente": cliente.nome})
        return False
    finally:
        if own:
            session.close()
```
> **Nota normativa:** a `upsert_criativo` da etapa de metadados pode reescrever `nome`/`tipo`/`preview_link` com `None` quando o lote falha (`metadados = {}`). Isso é aceitável nesta fase (o nome cru de insights já foi gravado na etapa 1 e re-rodadas/incrementais preenchem depois). O `_extract_purchase_metrics` e `_video_3s_views_from_row` são puros — não há HTTP a mockar neles.
- [ ] Rodar e ver passar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k coletar_criativos_meta`. Saída esperada: `3 passed`.
- [ ] Rodar o conjunto desta fase para regressão parcial: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py tests/test_thumbnails.py -v`. Saída esperada: todos `passed` (10 testes: 4 de thumbnails + 6 de collect_criativos até aqui).
- [ ] Commit:
```
git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
git commit -m "$(cat <<'EOF'
feat(etl): coletar_criativos_meta end-to-end com thumb rehospedada (Criativos v2 F1)

Upsert idempotente de ad_insights + criativos + criativo_thumbs; thumb_status
ok/sem_imagem/erro; idempotente em rerun.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: `run_collect_criativos` (modos backfill/incremental) + CLI (teste primeiro)

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py` (adicionar)
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`

Steps:
- [ ] Adicionar o teste que falha. Acrescentar ao final de `tests/test_collect_criativos.py` (testa o cálculo de janela e o XOR de modos via mock de `coletar_criativos_meta`, sem tocar a Graph API):
```python
from unittest.mock import patch


def test_run_collect_criativos_exige_exatamente_um_modo():
    from etl.collect_criativos import run_collect_criativos

    with pytest.raises(ValueError):
        run_collect_criativos()  # nenhum modo
    with pytest.raises(ValueError):
        run_collect_criativos(backfill_meses=6, incremental=True)  # ambos


def test_run_collect_criativos_backfill_chama_coletor_por_cliente(TS, cliente_id):
    from etl import collect_criativos as mod

    with TS() as s:
        c = s.get(Cliente, cliente_id)
        c.id_meta_ads = "act_777"
        s.commit()

    janelas = {}

    def fake_coletar(cliente, since, until, session_factory=None):
        janelas[cliente.id] = (since, until)
        return True

    with patch.object(mod, "coletar_criativos_meta", side_effect=fake_coletar), \
         patch.object(mod, "SessionLocal", TS), \
         patch.object(mod, "advisory_lock") as fake_lock:
        fake_lock.return_value.__enter__ = lambda *a: None
        fake_lock.return_value.__exit__ = lambda *a: False
        resumo = mod.run_collect_criativos(backfill_meses=6)

    assert resumo["ok"] >= 1
    assert resumo["total"] >= 1
    # janela de backfill ~6 meses (>= 150 dias)
    since, until = janelas[cliente_id]
    assert (until - since).days >= 150


def test_run_collect_criativos_incremental_usa_retroacao(TS, cliente_id):
    from datetime import date as _date, timedelta

    from etl import collect_criativos as mod

    with TS() as s:
        c = s.get(Cliente, cliente_id)
        c.id_meta_ads = "act_777"
        s.commit()

    janelas = {}

    def fake_coletar(cliente, since, until, session_factory=None):
        janelas[cliente.id] = (since, until)
        return True

    with patch.object(mod, "coletar_criativos_meta", side_effect=fake_coletar), \
         patch.object(mod, "SessionLocal", TS), \
         patch.object(mod, "advisory_lock") as fake_lock:
        fake_lock.return_value.__enter__ = lambda *a: None
        fake_lock.return_value.__exit__ = lambda *a: False
        mod.run_collect_criativos(incremental=True)

    since, until = janelas[cliente_id]
    ontem = _date.today() - timedelta(days=1)
    assert until == ontem
    assert since == ontem - timedelta(days=mod.RETROACAO_DIAS)
```
- [ ] Rodar e ver falhar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k run_collect_criativos`. Saída esperada: `ImportError: cannot import name 'run_collect_criativos'`.
- [ ] Implementação. Em `etl/collect_criativos.py`, acrescentar ao bloco de imports do topo (após os imports da Task 7):
```python
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

from sqlalchemy import true

from app_settings import get_settings
from etl.lock import LockTaken, advisory_lock
```
E adicionar ao final do arquivo:
```python
def _janela_backfill(backfill_meses: int, hoje: date) -> tuple[date, date]:
    until = hoje
    # aproxima meses por 30 dias (suficiente para a janela de backfill)
    since = hoje - timedelta(days=30 * backfill_meses)
    return since, until


def _janela_incremental(hoje: date) -> tuple[date, date]:
    ontem = hoje - timedelta(days=1)
    return ontem - timedelta(days=RETROACAO_DIAS), ontem


def run_collect_criativos(
    backfill_meses: int | None = None,
    incremental: bool = False,
    today: date | None = None,
) -> dict:
    """Entrypoint. backfill_meses=6 → janela últimos ~6 meses; incremental=True →
    ontem + RETROACAO_DIAS de retroação. Exatamente um modo (XOR). Coleta os
    clientes ativos com id_meta_ads em paralelo. Retorna {ok, fail, total}."""
    if (backfill_meses is None) == (not incremental):
        raise ValueError("Escolha exatamente um modo: backfill_meses XOR incremental")

    hoje = today or date.today()
    if incremental:
        since, until = _janela_incremental(hoje)
    else:
        since, until = _janela_backfill(backfill_meses, hoje)

    settings = get_settings()
    try:
        with advisory_lock(engine, "etl:criativos:run", blocking=False):
            with SessionLocal() as session:
                clientes = session.scalars(
                    select(Cliente).where(
                        Cliente.ativo == true(),
                        Cliente.id_meta_ads.isnot(None),
                    )
                ).all()
                clientes_ids = [c.id for c in clientes]

            ok = 0
            fail = 0

            def _processa(cliente_id: uuid.UUID) -> bool:
                with SessionLocal() as s:
                    cliente = s.get(Cliente, cliente_id)
                    return coletar_criativos_meta(
                        cliente, since, until, session_factory=SessionLocal
                    )

            with ThreadPoolExecutor(max_workers=settings.etl_threads) as pool:
                futures = {pool.submit(_processa, cid): cid for cid in clientes_ids}
                for f in as_completed(futures):
                    if f.result():
                        ok += 1
                    else:
                        fail += 1

            resumo = {"ok": ok, "fail": fail, "total": len(clientes_ids)}
            log.info("criativos_finalizado", extra=resumo)
            return resumo
    except LockTaken:
        log.warning("criativos_skip_lock_ocupado")
        return {"skipped": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta de criativos (Meta ad-level)")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--backfill-meses", type=int, dest="backfill_meses")
    grupo.add_argument("--incremental", action="store_true")
    args = parser.parse_args()
    resumo = run_collect_criativos(
        backfill_meses=args.backfill_meses, incremental=args.incremental
    )
    log.info("criativos_cli_resumo", extra=resumo)
    print(resumo)


if __name__ == "__main__":
    main()
```
> **Nota para o worker:** no teste, `_processa` reabre o cliente via `SessionLocal`, que é patcheado para `TS`; portanto `patch.object(mod, "SessionLocal", TS)` cobre tanto a query de clientes quanto o `_processa`. Como `coletar_criativos_meta` está mockado, `session_factory=SessionLocal` não é exercitado de fato. `_janela_backfill(6, hoje)` produz `(hoje - 180 dias, hoje)` → `(until - since).days == 180 >= 150`, satisfazendo a asserção.
- [ ] Rodar e ver passar: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v -k run_collect_criativos`. Saída esperada: `3 passed`.
- [ ] Verificar a CLI (sem tocar APIs reais — só valida o parser/XOR): `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m etl.collect_criativos 2>&1 | head -3`. Saída esperada: erro do argparse contendo `one of the arguments --backfill-meses --incremental is required` (exit code != 0). Isso confirma o entrypoint montado.
- [ ] Commit:
```
git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
git commit -m "$(cat <<'EOF'
feat(etl): run_collect_criativos (backfill/incremental) + CLI paralelizada (Criativos v2 F1)

Modos XOR; janela incremental = ontem + RETROACAO_DIAS; ThreadPoolExecutor com
SessionLocal por thread e advisory_lock etl:criativos:run.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Regressão completa do backend + fechamento

**Files:**
- (nenhum arquivo novo)

Steps:
- [ ] Rodar a suíte inteira do backend para garantir que F1 não quebrou nada: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/ -v`. Saída esperada: todos os testes de F1 (`test_thumbnails.py` = 4, `test_collect_criativos.py` = 9) `passed`, além dos pré-existentes. Se algum teste **pré-existente** falhar por falta de credenciais externas (ex.: testes que tocam a planilha/API real), confirme que **não** são dos arquivos novos desta fase (`test_thumbnails.py` / `test_collect_criativos.py`) — esses dois devem estar 100% verdes.
- [ ] Verificar que `etl/collect.py` (snapshot mensal) permanece intacto: `cd /Users/mac0267/Documents/auto-report-main && git diff --name-only HEAD~8 -- web/backend/etl/collect.py`. Saída esperada: vazio (nenhuma linha — `collect.py` não foi tocado por esta fase).
- [ ] Confirmar import limpo do módulo final no venv: `cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -c "from etl.collect_criativos import run_collect_criativos, coletar_criativos_meta, upsert_ad_insight, upsert_criativo, RETROACAO_DIAS; from etl.thumbnails import fetch_e_redimensionar; print('imports ok', RETROACAO_DIAS)"`. Saída esperada: `imports ok 3`.
- [ ] (Opcional, se o trabalho for entregue como PR) Usar a sub-skill `superpowers:finishing-a-development-branch` para abrir o PR de F1. Caso contrário, o trabalho já está commitado em série.

---

**Notas de implementação (normativas, para o worker):**
- **Interpretador:** SEMPRE `web/backend/.venv/bin/python` (e `.venv/bin/python -m pip`). Não existe `python` no PATH; o `python3` global não tem `respx` nem `psycopg` v3. (Verificado neste ambiente.)
- **Reuso do core:** `_extract_purchase_metrics` e `_video_3s_views_from_row` são importados de `core.categorias.ecommerce.campaign_facebook_gather` — não reimplementar (DRY). São puros de parsing (não fazem HTTP), então não precisam de mock. A `sys.path.insert(_ROOT)` no topo de `collect_criativos.py` (idêntica a `etl/collect.py`) torna `core`/`config` importáveis a partir de `web/backend/`.
- **HTTP novo** em `collect_criativos.py`/`thumbnails.py` usa **`httpx`** (mockável por `respx`); nunca `requests`.
- **Path da conta Meta:** usar `removeprefix("act_")` (não `lstrip`); o core usa `lstrip`, que é um footgun para IDs iniciando em `a/c/t`.
- **`leads`** em `ad_insights` fica `None` na coleta Meta desta fase (categorias lead/Google são tratados em fases posteriores — YAGNI aqui).
- **`reach`** **é** coletado e gravado em `ad_insights.reach` (decisão fechada do contrato).
- **`Image.Resampling.LANCZOS`** (não `Image.LANCZOS`, deprecado) para o resize — Pillow 11.
- Não criar cron no Render nesta fase (item operacional; fora do contrato de código).
- **Roteamento respx:** os dois regexes (`.../insights` e `v[\d.]+\?.*`) desambiguam corretamente as chamadas de insights e de metadados (verificado), pois a chamada de metadados renderiza a URL `https://graph.facebook.com/v23.0?ids=...`.
