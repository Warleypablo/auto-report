# F2 — Coleta Google ad-level diária + thumb (Asset API) + deep-link — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Each task follows strict TDD (write failing test → see it fail → implement → see it pass → commit). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estender `web/backend/etl/collect_criativos.py` (criado na F1) com `coletar_criativos_google(cliente, since, until, session_factory)`, que coleta insights ad-level **diários** do Google Ads via GAQL em `ad_group_ad` (com `segments.date`), resolve a thumbnail por tipo de anúncio (image ad → `image_ad.image_url`; search/sem imagem → `SEM_IMAGEM`), monta o deep-link para o Google Ads UI, e faz upsert idempotente nas mesmas 3 tabelas da F1 (`ad_insights`, `criativos`, `criativo_thumbs`) com `rede=RedeAnuncio.GOOGLE`. `run_collect_criativos` passa a submeter também o coletor Google por cliente ativo.

**Escopo de plataforma (decisão do spec, normativa):** O spec registra que "Google '100%' é limitado pela plataforma". Nesta fase, a thumbnail é resolvida **apenas** a partir de `ad_group_ad.ad.image_ad.image_url` (image ads). Search/text ads → `thumb_status = SEM_IMAGEM`. Anúncios responsive/video cuja imagem só é obtível via segunda chamada à Asset API caem em `SEM_IMAGEM` nesta fase (resolução de assets de responsive/video fica registrada como evolução, não bloqueia F2). O **deep-link** e o **`tipo`** (string do enum do anúncio) são preenchidos para **todos** os tipos.

**Architecture:** A F1 já criou `collect_criativos.py` com: `from __future__ import annotations`, o bloco de `sys.path` para a raiz do repo (`parents[3]`, igual a `etl/collect.py`), `log = logging.getLogger(__name__)`, a constante `RETROACAO_DIAS = 3`, os helpers de upsert `upsert_ad_insight(session, **campos)` / `upsert_criativo(session, **campos) -> Criativo`, a função `coletar_criativos_meta(...)`, e o entrypoint `run_collect_criativos(...)` que orquestra via `ThreadPoolExecutor(max_workers=settings.etl_threads)` + `advisory_lock(engine, "etl:criativos:run", blocking=False)`. A F1 também criou `etl/thumbnails.py` com `fetch_e_redimensionar(url, *, lado_max=320) -> tuple[bytes, str]`, importado em `collect_criativos.py`. **Esta fase não recria nada disso** — apenas adiciona `coletar_criativos_google(...)` e helpers privados de Google ao mesmo arquivo, e estende `run_collect_criativos` para submeter o coletor Google. O cliente Google vem de `core.cred_manager._build_google_ads_client` (a mesma fonte que `core/categorias/.../google_metrics_gather.py` e `api/turbomax.py` usam). Para isolar a rede em teste, a obtenção do `GoogleAdsService` fica num wrapper privado `_get_google_ads_service()` (espelha `etl.collect._get_handler`); o fetch de thumb usa `fetch_e_redimensionar` (mockável). GAQL roda via `service.search(customer_id=..., query=...)` (retorna rows iteráveis diretamente — mesmo padrão de `api/turbomax.py` e `ecommerce/campaign_google_gather.py`, **não** `search_stream`/batches).

**Tech Stack:** Python 3 / SQLAlchemy 2.x ORM, `google-ads` (`GoogleAdsClient.get_service("GoogleAdsService")`, `GoogleAdsService.search`, `from google.ads.googleads.errors import GoogleAdsException`), Postgres (upsert via `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update`, helpers da F1), `httpx`+`Pillow` (via `etl/thumbnails.py` da F1), pytest + `unittest.mock.patch`/`MagicMock` (mock dos rows GAQL — **não** chama a API real). DB de teste: `postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test` (mesmo padrão `Base.metadata.create_all` de `tests/test_collect.py`). Logger: `logging.getLogger(__name__)` com **printf-style** (`log.error("msg %s", x)`), consistente com `etl/collect.py` e `core/`.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py` | **Modify** | Adicionar `from core.cred_manager import _build_google_ads_client`, `from google.ads.googleads.errors import GoogleAdsException`, `_get_google_ads_service()`, `_GOOGLE_AD_FIELDS`, `_build_google_query(...)`, `_google_deep_link(...)`, `_google_thumb_url(...)`, `coletar_criativos_google(...)`; estender `run_collect_criativos(...)` para submeter o coletor Google. **Não** alterar a lógica Meta/upsert/thumbnails da F1. |
| `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py` | **Modify** | Adicionar testes do caminho Google: helpers puros (deep-link, query, escolha de URL de thumb), coleta com GAQL mockado (image ad → upsert + thumb OK; search ad → `SEM_IMAGEM`), idempotência do re-run, `id_google_ads` ausente/`"0"` → retorno cedo sem chamar API, GAQL falho → `False` sem persistir, `run_collect_criativos` chamando Google. Reusa as fixtures `engine`/`TS`/`cliente_google` no padrão de `tests/test_collect.py`. |

Helpers de upsert (`upsert_ad_insight`, `upsert_criativo`), `coletar_criativos_meta`, `RETROACAO_DIAS`, `fetch_e_redimensionar` (import), e a estrutura de `run_collect_criativos` **já existem (F1)** — apenas reusados/estendidos. Os models (`Criativo`, `CriativoThumb`, `AdInsight`, `RedeAnuncio`, `ThumbStatus`) e a migration **já existem (F0)**.

> **Pré-condição operacional para os testes de DB (Tasks 6–9):** Postgres local acessível em `postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test`. Os testes de helpers puros (Tasks 1–5) e os de orquestração mockada não dependem de DB real, exceto onde indicado.

---

### Task 1: Helper `_get_google_ads_service()` (wrapper patchável)

Isola a obtenção do `GoogleAdsService` num ponto único e mockável, espelhando `etl.collect._get_handler`. Sem isso, os testes não conseguem mockar a API sem credenciais.

**Files:**
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste que falha. Adicionar ao fim de `tests/test_collect_criativos.py`:
  ```python
  from unittest.mock import MagicMock, patch


  def test_get_google_ads_service_usa_cred_manager():
      fake_client = MagicMock()
      fake_service = MagicMock()
      fake_client.get_service.return_value = fake_service
      with patch(
          "etl.collect_criativos._build_google_ads_client",
          return_value=fake_client,
      ):
          from etl.collect_criativos import _get_google_ads_service

          svc = _get_google_ads_service()

      assert svc is fake_service
      fake_client.get_service.assert_called_once_with("GoogleAdsService")
  ```
- [ ] Rodar e ver falhar (a partir de `web/backend/`):
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_get_google_ads_service_usa_cred_manager -v
  ```
  Saída esperada: `AttributeError: <module 'etl.collect_criativos'> does not have the attribute '_build_google_ads_client'` (o `patch` falha porque o nome ainda não foi importado no módulo) → `1 error`.
- [ ] Implementação mínima. No topo de `collect_criativos.py`, **após** o bloco `sys.path`/imports de `core` já presentes da F1 (a raiz do repo já está no `sys.path` via `parents[3]`), garantir os imports:
  ```python
  from core.cred_manager import _build_google_ads_client
  from google.ads.googleads.errors import GoogleAdsException
  ```
  E adicionar a função (junto aos outros helpers de módulo, antes de `coletar_criativos_meta`):
  ```python
  def _get_google_ads_service():
      """Wrapper para permitir mock em testes (espelha etl.collect._get_handler)."""
      client = _build_google_ads_client()
      return client.get_service("GoogleAdsService")
  ```
  > `GoogleAdsException` é importado já aqui porque será usado na Task 6/8; importá-lo agora evita um segundo edit no mesmo bloco de imports.
- [ ] Rodar e ver passar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_get_google_ads_service_usa_cred_manager -v
  ```
  Saída esperada: `1 passed`.
- [ ] Commit:
  ```
  git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
  git commit -m "feat(etl): wrapper _get_google_ads_service patchavel em collect_criativos

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 2: GAQL fields + `_build_google_query`

Define a query GAQL em `ad_group_ad` com `segments.date`, com exatamente os campos do spec (linha 113 do design).

**Files:**
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste que falha. Adicionar:
  ```python
  def test_build_google_query_contem_campos_e_datas():
      from datetime import date

      from etl.collect_criativos import _build_google_query

      q = _build_google_query(date(2026, 1, 1), date(2026, 1, 31))

      assert "FROM ad_group_ad" in q
      assert "segments.date BETWEEN '2026-01-01' AND '2026-01-31'" in q
      for campo in (
          "ad_group_ad.ad.id",
          "ad_group_ad.ad.name",
          "ad_group_ad.ad.type",
          "ad_group_ad.ad_group",
          "ad_group_ad.ad.image_ad.image_url",
          "segments.date",
          "metrics.cost_micros",
          "metrics.conversions",
          "metrics.conversions_value",
          "metrics.impressions",
          "metrics.clicks",
      ):
          assert campo in q
  ```
- [ ] Rodar e ver falhar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_build_google_query_contem_campos_e_datas -v
  ```
  Saída esperada: `ImportError: cannot import name '_build_google_query' from 'etl.collect_criativos'` → `1 error`.
- [ ] Implementação mínima. Adicionar (junto aos helpers Google, perto de `_get_google_ads_service`):
  ```python
  _GOOGLE_AD_FIELDS = (
      "ad_group_ad.ad.id",
      "ad_group_ad.ad.name",
      "ad_group_ad.ad.type",
      "ad_group_ad.ad_group",
      "ad_group_ad.ad.image_ad.image_url",
      "segments.date",
      "metrics.cost_micros",
      "metrics.conversions",
      "metrics.conversions_value",
      "metrics.impressions",
      "metrics.clicks",
  )


  def _build_google_query(since: date, until: date) -> str:
      campos = ", ".join(_GOOGLE_AD_FIELDS)
      return (
          f"SELECT {campos} "
          "FROM ad_group_ad "
          f"WHERE segments.date BETWEEN '{since.isoformat()}' AND '{until.isoformat()}'"
      )
  ```
  > `from datetime import date` já é importado no topo do módulo pela F1 (igual a `etl/collect.py`). `ad_group_ad.ad.image_ad.image_url` é selecionado no GAQL para resolver a thumb de image ads sem segunda chamada.
- [ ] Rodar e ver passar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_build_google_query_contem_campos_e_datas -v
  ```
  Saída esperada: `1 passed`.
- [ ] Commit:
  ```
  git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
  git commit -m "feat(etl): GAQL ad_group_ad diario (_build_google_query) para criativos Google

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 3: Deep-link do anúncio no Google Ads UI (`_google_deep_link`)

Constrói a URL "Ver anúncio" para o Ads UI a partir de `customer_id`, `ad_group_id` e `ad_id`. Sem `ad_group_id` → `None` (o spec permite `null` onde não construível).

**Files:**
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste que falha. Adicionar:
  ```python
  def test_google_deep_link():
      from etl.collect_criativos import _google_deep_link

      link = _google_deep_link(customer_id="1234567890", ad_group_id="555", ad_id="999")
      assert link == (
          "https://ads.google.com/aw/ads?ocid=1234567890&__e=999&adGroupId=555"
      )


  def test_google_deep_link_sem_ad_group_retorna_none():
      from etl.collect_criativos import _google_deep_link

      assert _google_deep_link(customer_id="1234567890", ad_group_id=None, ad_id="999") is None
      assert _google_deep_link(customer_id="1234567890", ad_group_id="", ad_id="999") is None
  ```
- [ ] Rodar e ver falhar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -k google_deep_link -v
  ```
  Saída esperada: `ImportError: cannot import name '_google_deep_link' from 'etl.collect_criativos'` → `2 errors`.
- [ ] Implementação mínima. Adicionar:
  ```python
  def _google_deep_link(*, customer_id: str, ad_group_id: str | None, ad_id: str) -> str | None:
      """Deep-link para o anúncio no Google Ads UI. None quando não construível."""
      if not ad_group_id:
          return None
      return (
          f"https://ads.google.com/aw/ads?ocid={customer_id}"
          f"&__e={ad_id}&adGroupId={ad_group_id}"
      )
  ```
- [ ] Rodar e ver passar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -k google_deep_link -v
  ```
  Saída esperada: `2 passed`.
- [ ] Commit:
  ```
  git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
  git commit -m "feat(etl): deep-link do anuncio Google (_google_deep_link)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 4: Seleção da URL de thumb por tipo de anúncio (`_google_thumb_url`)

Decide, a partir do `ad.type_` e de `image_ad.image_url`, qual URL de imagem usar. Image ads → `image_url`. Search/text e demais tipos sem imagem própria expressa → `None` (vira `SEM_IMAGEM`).

**Files:**
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste que falha. Adicionar (usa `MagicMock` para simular o objeto `ad_group_ad.ad` do google-ads, cujo `.type_.name` é a string do enum):
  ```python
  def _fake_ad(type_name, *, image_url=""):
      ad = MagicMock()
      ad.type_.name = type_name
      ad.image_ad.image_url = image_url
      return ad


  def test_google_thumb_url_image_ad():
      from etl.collect_criativos import _google_thumb_url

      ad = _fake_ad("IMAGE_AD", image_url="https://cdn.example/img.png")
      assert _google_thumb_url(ad) == "https://cdn.example/img.png"


  def test_google_thumb_url_search_ad_retorna_none():
      from etl.collect_criativos import _google_thumb_url

      ad = _fake_ad("EXPANDED_TEXT_AD")
      assert _google_thumb_url(ad) is None


  def test_google_thumb_url_image_ad_sem_url_retorna_none():
      from etl.collect_criativos import _google_thumb_url

      ad = _fake_ad("IMAGE_AD", image_url="")
      assert _google_thumb_url(ad) is None
  ```
- [ ] Rodar e ver falhar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -k google_thumb_url -v
  ```
  Saída esperada: `ImportError: cannot import name '_google_thumb_url' from 'etl.collect_criativos'` → `3 errors`.
- [ ] Implementação mínima. Adicionar:
  ```python
  # Tipos de anúncio Google que carregam imagem própria via image_ad.image_url.
  _GOOGLE_IMAGE_AD_TYPES = {"IMAGE_AD"}


  def _google_thumb_url(ad) -> str | None:
      """URL da imagem do anúncio, ou None (search/sem imagem própria).

      `ad` é o objeto `ad_group_ad.ad` retornado pelo google-ads. `ad.type_.name`
      é a string do enum (ex.: 'IMAGE_AD', 'EXPANDED_TEXT_AD', 'RESPONSIVE_DISPLAY_AD').
      Nesta fase só image ads expoem imagem diretamente; responsive/video (cujos
      assets exigem segunda chamada a Asset API) e search/text -> None -> SEM_IMAGEM,
      conforme a limitacao de plataforma registrada no spec.
      """
      tipo = getattr(getattr(ad, "type_", None), "name", "") or ""
      if tipo in _GOOGLE_IMAGE_AD_TYPES:
          url = getattr(getattr(ad, "image_ad", None), "image_url", "") or ""
          return url or None
      return None
  ```
- [ ] Rodar e ver passar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -k google_thumb_url -v
  ```
  Saída esperada: `3 passed`.
- [ ] Commit:
  ```
  git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
  git commit -m "feat(etl): seleciona URL de thumb Google por tipo de anuncio (_google_thumb_url)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 5: `coletar_criativos_google` — guarda de `id_google_ads` ausente/`"0"`

Antes de tocar a API: clientes sem `id_google_ads` (ou `"0"`, igual à guarda de `ecommerce/google_metrics_gather.coletar_metricas_google`) retornam `True` sem coletar e sem chamar o service.

**Files:**
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste que falha. Adicionar (sem DB — só verifica que não chama o service):
  ```python
  from datetime import date


  def test_coletar_google_sem_id_retorna_true_sem_chamar_api():
      from etl.collect_criativos import coletar_criativos_google

      cliente = MagicMock()
      cliente.id_google_ads = None
      cliente.nome = "Sem Google"

      with patch("etl.collect_criativos._get_google_ads_service") as p:
          ok = coletar_criativos_google(cliente, date(2026, 1, 1), date(2026, 1, 31))

      assert ok is True
      p.assert_not_called()


  def test_coletar_google_id_zero_retorna_true_sem_chamar_api():
      from etl.collect_criativos import coletar_criativos_google

      cliente = MagicMock()
      cliente.id_google_ads = "0"
      cliente.nome = "Google Off"

      with patch("etl.collect_criativos._get_google_ads_service") as p:
          ok = coletar_criativos_google(cliente, date(2026, 1, 1), date(2026, 1, 31))

      assert ok is True
      p.assert_not_called()
  ```
- [ ] Rodar e ver falhar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -k "coletar_google_sem_id or coletar_google_id_zero" -v
  ```
  Saída esperada: `ImportError: cannot import name 'coletar_criativos_google' from 'etl.collect_criativos'` → `2 errors`.
- [ ] Implementação mínima. Adicionar a função (esqueleto que cobre só a guarda; o corpo de coleta entra na Task 6). Os imports `from typing import Callable`, `from sqlalchemy.orm import Session`, `from db import SessionLocal`, `from models import Cliente`, `from models.criativo import RedeAnuncio, ThumbStatus` já estão no topo do módulo pela F1.
  ```python
  def coletar_criativos_google(
      cliente: Cliente,
      since: date,
      until: date,
      session_factory: Callable[[], Session] = SessionLocal,
  ) -> bool:
      """Coleta ad_group_ad com segments.date via GAQL + thumb + deep-link.
      Search ads -> thumb_status = SEM_IMAGEM. Faz upsert em ad_insights e
      criativos (rede=GOOGLE). Retorna True em sucesso, False em falha de API."""
      customer_id = getattr(cliente, "id_google_ads", None)
      if not customer_id or customer_id == "0":
          log.info("collect_criativos_google skip sem id: %s", cliente.nome)
          return True
      raise NotImplementedError  # corpo implementado na Task 6
  ```
- [ ] Rodar e ver passar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -k "coletar_google_sem_id or coletar_google_id_zero" -v
  ```
  Saída esperada: `2 passed`.
- [ ] Commit:
  ```
  git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
  git commit -m "feat(etl): coletar_criativos_google guarda de id_google_ads ausente/zero

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 6: `coletar_criativos_google` — coleta, agregação diária e upsert (image ad + search ad)

Itera os rows GAQL mockados, soma por `(ad_id, dia)`, faz upsert em `ad_insights` e `criativos`, baixa/grava thumb quando há URL (image ad) e marca `SEM_IMAGEM` para search ads. Persiste de verdade no DB de teste.

**Files:**
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste que falha. Adicionar no topo do arquivo de teste (apenas se ainda **não** existir, vindo da F1) a fixture de DB, o helper de recarga de cliente e o helper de row GAQL. Imports e fixtures:
  ```python
  import uuid

  import pytest
  from sqlalchemy import create_engine, select
  from sqlalchemy.orm import sessionmaker

  from models import Categoria, Cliente
  from models.base import Base
  from models.ad_insight import AdInsight
  from models.criativo import Criativo, CriativoThumb, RedeAnuncio, ThumbStatus

  TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


  @pytest.fixture(scope="module")
  def engine():
      eng = create_engine(TEST_DB_URL)
      Base.metadata.drop_all(eng)
      Base.metadata.create_all(eng)
      yield eng
      Base.metadata.drop_all(eng)


  @pytest.fixture
  def TS(engine):
      return sessionmaker(bind=engine)


  @pytest.fixture
  def cliente_google(TS):
      slug = f"google-{uuid.uuid4().hex[:8]}"
      with TS() as s:
          c = Cliente(
              slug=slug, nome=slug, categoria=Categoria.ECOMMERCE,
              id_google_ads="1234567890",
          )
          s.add(c)
          s.commit()
          cid = c.id
      yield cid
      with TS() as s:
          c = s.get(Cliente, cid)
          if c:
              s.delete(c)
              s.commit()


  def s_cliente(TS, cliente_id):
      """Recarrega o Cliente numa sessao da fixture para passar ao coletor."""
      with TS() as s:
          return s.get(Cliente, cliente_id)


  def _gaql_row(*, ad_id, ad_group_id, ad_type, day, cost_micros, conversions,
                conv_value, impressions, clicks, name="", image_url=""):
      row = MagicMock()
      row.ad_group_ad.ad.id = int(ad_id)
      row.ad_group_ad.ad.name = name
      row.ad_group_ad.ad.type_.name = ad_type
      row.ad_group_ad.ad.image_ad.image_url = image_url
      row.ad_group_ad.ad_group = f"customers/1234567890/adGroups/{ad_group_id}"
      row.segments.date = day  # "YYYY-MM-DD"
      row.metrics.cost_micros = cost_micros
      row.metrics.conversions = conversions
      row.metrics.conversions_value = conv_value
      row.metrics.impressions = impressions
      row.metrics.clicks = clicks
      return row
  ```
  Teste principal (image ad em 2 dias → 2 insights + thumb OK + primeiro/último dia; search ad → SEM_IMAGEM):
  ```python
  def test_coletar_google_persiste_insights_criativos_e_thumb(cliente_google, TS):
      from etl.collect_criativos import coletar_criativos_google

      rows = [
          _gaql_row(ad_id="999", ad_group_id="555", ad_type="IMAGE_AD",
                    day="2026-01-01", cost_micros=2_000_000, conversions=2.0,
                    conv_value=100.0, impressions=1000, clicks=10,
                    name="Banner Promo", image_url="https://cdn.example/x.png"),
          _gaql_row(ad_id="999", ad_group_id="555", ad_type="IMAGE_AD",
                    day="2026-01-02", cost_micros=1_000_000, conversions=1.0,
                    conv_value=50.0, impressions=500, clicks=5,
                    name="Banner Promo", image_url="https://cdn.example/x.png"),
          _gaql_row(ad_id="111", ad_group_id="555", ad_type="EXPANDED_TEXT_AD",
                    day="2026-01-01", cost_micros=3_000_000, conversions=0.0,
                    conv_value=0.0, impressions=2000, clicks=20, name="Search 1"),
      ]
      fake_service = MagicMock()
      fake_service.search.return_value = rows

      with patch("etl.collect_criativos._get_google_ads_service", return_value=fake_service), \
           patch("etl.collect_criativos.fetch_e_redimensionar",
                 return_value=(b"\xff\xd8jpeg", "image/jpeg")) as fr:
          ok = coletar_criativos_google(
              s_cliente(TS, cliente_google), date(2026, 1, 1), date(2026, 1, 31),
              session_factory=TS,
          )

      assert ok is True
      fr.assert_called_once_with("https://cdn.example/x.png", lado_max=320)

      with TS() as s:
          insights = s.scalars(
              select(AdInsight).where(AdInsight.cliente_id == cliente_google)
              .order_by(AdInsight.ad_id, AdInsight.dia)
          ).all()
          # 999 em 2 dias + 111 em 1 dia = 3 linhas
          assert len(insights) == 3
          i0 = next(i for i in insights if i.ad_id == "999" and i.dia == date(2026, 1, 1))
          assert i0.rede == RedeAnuncio.GOOGLE
          assert i0.investimento == 2  # 2_000_000 micros
          assert i0.faturamento == 100
          assert i0.conversoes == 2
          assert i0.impressoes == 1000
          assert i0.clicks == 10
          assert i0.leads is None
          assert i0.video_3s is None
          assert i0.reach is None

          criativos = s.scalars(
              select(Criativo).where(Criativo.cliente_id == cliente_google)
              .order_by(Criativo.ad_id)
          ).all()
          by_ad = {c.ad_id: c for c in criativos}
          assert by_ad["999"].rede == RedeAnuncio.GOOGLE
          assert by_ad["999"].thumb_status == ThumbStatus.OK
          assert by_ad["999"].nome == "Banner Promo"
          assert by_ad["999"].tipo == "IMAGE_AD"
          assert by_ad["999"].preview_link == (
              "https://ads.google.com/aw/ads?ocid=1234567890&__e=999&adGroupId=555"
          )
          assert by_ad["999"].primeiro_dia == date(2026, 1, 1)
          assert by_ad["999"].ultimo_dia == date(2026, 1, 2)
          assert by_ad["111"].thumb_status == ThumbStatus.SEM_IMAGEM

          thumb = s.get(CriativoThumb, by_ad["999"].id)
          assert thumb is not None
          assert thumb.conteudo == b"\xff\xd8jpeg"
          assert thumb.mime == "image/jpeg"
  ```
- [ ] Rodar e ver falhar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_coletar_google_persiste_insights_criativos_e_thumb -v
  ```
  Saída esperada: `NotImplementedError` (corpo da Task 5 ainda não implementado) → `1 failed`.
- [ ] Implementação mínima. Garantir o import de thumbnails no topo do módulo (F1 já importa; se faltar, adicionar `from .thumbnails import fetch_e_redimensionar`). Substituir o `raise NotImplementedError` da Task 5 por:
  ```python
      from decimal import Decimal

      try:
          service = _get_google_ads_service()
      except Exception:
          log.exception("collect_criativos_google auth falhou (%s)", cliente.nome)
          return False

      query = _build_google_query(since, until)
      try:
          response = service.search(customer_id=str(customer_id), query=query)
          rows = list(response)
      except GoogleAdsException:
          log.exception("collect_criativos_google GAQL falhou (%s)", cliente.nome)
          return False

      # Agrega por (ad_id, dia); guarda metadados por ad_id.
      insights: dict[tuple[str, date], dict] = {}
      metas: dict[str, dict] = {}
      for row in rows:
          ad = row.ad_group_ad.ad
          ad_id = str(ad.id)
          dia = date.fromisoformat(str(row.segments.date))
          acc = insights.setdefault(
              (ad_id, dia),
              {"investimento": Decimal("0"), "faturamento": Decimal("0"),
               "conversoes": Decimal("0"), "impressoes": 0, "clicks": 0},
          )
          acc["investimento"] += Decimal(row.metrics.cost_micros or 0) / Decimal(1_000_000)
          acc["faturamento"] += Decimal(str(row.metrics.conversions_value or 0))
          acc["conversoes"] += Decimal(str(row.metrics.conversions or 0))
          acc["impressoes"] += int(row.metrics.impressions or 0)
          acc["clicks"] += int(row.metrics.clicks or 0)

          ad_group_path = row.ad_group_ad.ad_group
          ad_group_id = str(ad_group_path).rsplit("/", 1)[-1] if ad_group_path else None
          meta = metas.setdefault(
              ad_id,
              {"nome": ad.name or None,
               "tipo": getattr(getattr(ad, "type_", None), "name", None),
               "thumb_url": _google_thumb_url(ad),
               "ad_group_id": ad_group_id,
               "primeiro_dia": dia, "ultimo_dia": dia},
          )
          meta["primeiro_dia"] = min(meta["primeiro_dia"], dia)
          meta["ultimo_dia"] = max(meta["ultimo_dia"], dia)

      session = session_factory()
      own_session = session_factory is SessionLocal
      try:
          for (ad_id, dia), v in insights.items():
              upsert_ad_insight(
                  session,
                  cliente_id=cliente.id,
                  rede=RedeAnuncio.GOOGLE,
                  ad_id=ad_id,
                  dia=dia,
                  investimento=v["investimento"],
                  faturamento=v["faturamento"],
                  conversoes=v["conversoes"],
                  leads=None,
                  impressoes=v["impressoes"],
                  clicks=v["clicks"],
                  video_3s=None,
                  reach=None,
              )

          for ad_id, meta in metas.items():
              thumb_url = meta["thumb_url"]
              if thumb_url:
                  try:
                      conteudo, mime = fetch_e_redimensionar(thumb_url, lado_max=320)
                      thumb_status = ThumbStatus.OK
                  except Exception:
                      log.exception(
                          "collect_criativos_google thumb falhou (%s ad_id=%s)",
                          cliente.nome, ad_id,
                      )
                      conteudo, mime, thumb_status = None, None, ThumbStatus.ERRO
              else:
                  conteudo, mime, thumb_status = None, None, ThumbStatus.SEM_IMAGEM

              preview_link = _google_deep_link(
                  customer_id=str(customer_id),
                  ad_group_id=meta["ad_group_id"],
                  ad_id=ad_id,
              )
              criativo = upsert_criativo(
                  session,
                  cliente_id=cliente.id,
                  rede=RedeAnuncio.GOOGLE,
                  ad_id=ad_id,
                  nome=meta["nome"],
                  tipo=meta["tipo"],
                  preview_link=preview_link,
                  thumb_status=thumb_status,
                  primeiro_dia=meta["primeiro_dia"],
                  ultimo_dia=meta["ultimo_dia"],
              )
              if thumb_status == ThumbStatus.OK and conteudo is not None:
                  session.merge(
                      CriativoThumb(criativo_id=criativo.id, conteudo=conteudo, mime=mime)
                  )

          session.commit()
      finally:
          if own_session:
              session.close()

      log.info(
          "collect_criativos_google ok (%s): ads=%d dias=%d",
          cliente.nome, len(metas), len(insights),
      )
      return True
  ```
  > **Contrato (F1):** `upsert_criativo(session, **campos) -> Criativo` faz `on_conflict_do_update(constraint="uq_criativo_cliente_rede_ad")`, atualiza `primeiro_dia`/`ultimo_dia` com `LEAST/GREATEST`, e retorna a row (com `id`). `upsert_ad_insight(session, **campos)` faz `on_conflict_do_update(constraint="uq_ad_insight_cliente_rede_ad_dia")` com `set_` das métricas (substitui, não soma). Ambos reusados tal qual. `GoogleAdsException` já foi importado na Task 1.
- [ ] Rodar e ver passar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_coletar_google_persiste_insights_criativos_e_thumb -v
  ```
  Saída esperada: `1 passed`. (Requer Postgres local `vitrine_test`.)
- [ ] Commit:
  ```
  git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
  git commit -m "feat(etl): coletar_criativos_google agrega diario + upsert insights/criativos/thumb

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 7: Idempotência do re-run (Google)

Rodar duas vezes a mesma janela não duplica linhas e mantém os valores (sobrescreve, não soma). Garante o requisito do spec "upsert idempotente por `(cliente_id, rede, ad_id, dia)`".

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste. Adicionar:
  ```python
  def test_coletar_google_idempotente(cliente_google, TS):
      from etl.collect_criativos import coletar_criativos_google

      def make_rows():
          return [
              _gaql_row(ad_id="999", ad_group_id="555", ad_type="IMAGE_AD",
                        day="2026-01-01", cost_micros=2_000_000, conversions=2.0,
                        conv_value=100.0, impressions=1000, clicks=10,
                        name="Banner", image_url="https://cdn.example/x.png"),
          ]

      def run_once():
          fake_service = MagicMock()
          fake_service.search.return_value = make_rows()
          with patch("etl.collect_criativos._get_google_ads_service", return_value=fake_service), \
               patch("etl.collect_criativos.fetch_e_redimensionar",
                     return_value=(b"jpegbytes", "image/jpeg")):
              return coletar_criativos_google(
                  s_cliente(TS, cliente_google), date(2026, 1, 1), date(2026, 1, 31),
                  session_factory=TS,
              )

      assert run_once() is True
      assert run_once() is True

      with TS() as s:
          insights = s.scalars(
              select(AdInsight).where(AdInsight.cliente_id == cliente_google)
          ).all()
          assert len(insights) == 1
          assert insights[0].investimento == 2     # nao 4 -> sobrescreveu
          assert insights[0].faturamento == 100

          criativos = s.scalars(
              select(Criativo).where(Criativo.cliente_id == cliente_google)
          ).all()
          assert len(criativos) == 1
          thumbs = s.scalars(
              select(CriativoThumb).where(CriativoThumb.criativo_id == criativos[0].id)
          ).all()
          # uma thumb por criativo (PK = criativo_id, dedup por anuncio)
          assert len(thumbs) == 1
  ```
- [ ] Rodar e ver passar imediatamente (a idempotência já é garantida pelos `on_conflict_do_update` da F1 + `session.merge` na thumb por PK `criativo_id`):
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_coletar_google_idempotente -v
  ```
  Saída esperada: `1 passed`.
  > Se falhar (ex.: acúmulo em `ad_insights` ou duplicação de thumb), aplicar superpowers:systematic-debugging: confirmar que `upsert_ad_insight` usa `on_conflict_do_update(constraint="uq_ad_insight_cliente_rede_ad_dia")` com `set_` dos campos de métrica (substitui, não soma) e que a thumb é `session.merge(CriativoThumb(criativo_id=...))` (PK = `criativo_id`). Não é esperado falhar; este teste é uma rede de proteção do contrato F1, por isso não há passo de "ver falhar".
- [ ] Commit:
  ```
  git add web/backend/tests/test_collect_criativos.py
  git commit -m "test(etl): idempotencia do re-run de coletar_criativos_google

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 8: GAQL falho retorna `False` (não derruba o batch)

Erro de API por cliente não deve quebrar `run_collect_criativos`; a função retorna `False`, não persiste nada, e o orquestrador contabiliza como `fail`.

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste. Adicionar:
  ```python
  def test_coletar_google_gaql_exception_retorna_false(cliente_google, TS):
      from google.ads.googleads.errors import GoogleAdsException

      from etl.collect_criativos import coletar_criativos_google

      fake_service = MagicMock()
      fake_service.search.side_effect = GoogleAdsException(None, None, None, None)

      with patch("etl.collect_criativos._get_google_ads_service", return_value=fake_service):
          ok = coletar_criativos_google(
              s_cliente(TS, cliente_google), date(2026, 1, 1), date(2026, 1, 31),
              session_factory=TS,
          )

      assert ok is False
      with TS() as s:
          assert s.scalars(
              select(AdInsight).where(AdInsight.cliente_id == cliente_google)
          ).all() == []
  ```
  > `GoogleAdsException(error, call, failure, request_id)` aceita 4 posicionais e apenas os armazena como atributos (não valida), então `GoogleAdsException(None, None, None, None)` instancia sem erro — verificado no uso real do projeto.
- [ ] Rodar e ver passar (o `except GoogleAdsException` da Task 6 já trata; `.search` é chamado antes de qualquer commit, então nada é persistido):
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_coletar_google_gaql_exception_retorna_false -v
  ```
  Saída esperada: `1 passed`.
- [ ] Commit:
  ```
  git add web/backend/tests/test_collect_criativos.py
  git commit -m "test(etl): GAQL falho em coletar_criativos_google retorna False sem persistir

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 9: `run_collect_criativos` submete o coletor Google por cliente

Estende o orquestrador (F1, que já submete `coletar_criativos_meta`) para também submeter `coletar_criativos_google` por cliente ativo, mantendo `ThreadPoolExecutor` + `advisory_lock` e o resumo `{"ok","fail","total"}`.

**Files:**
- Modify: `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py`
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Escrever teste que falha. Adicionar (mocka ambos os coletores para isolar a orquestração; `incremental=True` para escolher exatamente um modo; `advisory_lock` patchado para não exigir lock real de Postgres no caminho de orquestração):
  ```python
  def test_run_collect_criativos_invoca_google(cliente_google, TS):
      import etl.collect_criativos as cc

      chamados_google = []

      def fake_google(cliente, since, until, session_factory=cc.SessionLocal):
          chamados_google.append(cliente.id)
          return True

      with patch.object(cc, "coletar_criativos_meta", return_value=True), \
           patch.object(cc, "coletar_criativos_google", side_effect=fake_google), \
           patch.object(cc, "SessionLocal", TS), \
           patch.object(cc, "advisory_lock"):
          resumo = cc.run_collect_criativos(incremental=True)

      assert cliente_google in chamados_google
      assert resumo["total"] >= 1
      assert "ok" in resumo and "fail" in resumo
  ```
  > `advisory_lock` é patchado para virar um no-op (o context manager mockado entra/sai sem lock real). `SessionLocal` é apontado para `TS` para que a seleção de clientes ativos (`Cliente.ativo == True`) enxergue `cliente_google`. O uso de DB real para a coleta em si fica nas Tasks 6–8.
- [ ] Rodar e ver falhar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_run_collect_criativos_invoca_google -v
  ```
  Saída esperada: `AssertionError: assert <uuid> in []` (Google nunca foi chamado — F1 só submetia Meta) → `1 failed`. (Se a F1 estruturou os futures de modo que `coletar_criativos_google` ainda não é referenciada, o `patch.object(cc, "coletar_criativos_google", ...)` ainda funciona porque a função já existe no módulo desde a Task 5; a falha será o `AssertionError`.)
- [ ] Implementação mínima. Localizar em `run_collect_criativos` o `with ThreadPoolExecutor(max_workers=settings.etl_threads) as pool:` (F1) onde os futures de coleta por cliente são submetidos. Estender o laço para submeter **também** o coletor Google ao lado do Meta (variáveis `clientes`, `since`, `until` são as já definidas pela F1):
  ```python
          ok = 0
          fail = 0
          with ThreadPoolExecutor(max_workers=settings.etl_threads) as pool:
              futures = []
              for cliente in clientes:
                  futures.append(pool.submit(coletar_criativos_meta, cliente, since, until))
                  futures.append(pool.submit(coletar_criativos_google, cliente, since, until))
              for f in as_completed(futures):
                  if f.result():
                      ok += 1
                  else:
                      fail += 1

          resumo = {"ok": ok, "fail": fail, "total": len(futures)}
  ```
  > Manter intactos o `advisory_lock(engine, "etl:criativos:run", blocking=False)` e a seleção de clientes ativos da F1. Se a F1 já contava `total` por clientes (não por tarefas), **preservar a semântica da F1** e apenas garantir que `coletar_criativos_google` é submetida no mesmo laço — o contrato exige apenas que o retorno tenha as chaves `{"ok","fail","total"}`, e o teste só verifica que Google foi chamado e que as chaves existem.
- [ ] Rodar e ver passar:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py::test_run_collect_criativos_invoca_google -v
  ```
  Saída esperada: `1 passed`.
- [ ] Commit:
  ```
  git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
  git commit -m "feat(etl): run_collect_criativos passa a coletar Google por cliente

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

### Task 10: Suíte verde + verificação final

Roda toda a suíte do arquivo e da ETL relacionada para garantir que o caminho Google convive com o Meta da F1, sem regressão.

**Files:**
- Test: `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_collect_criativos.py`

Steps:
- [ ] Rodar o arquivo inteiro:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect_criativos.py -v
  ```
  Saída esperada: todos os testes (Meta da F1 + Google das Tasks 1–9) `passed`, `0 failed`. (Requer Postgres local `vitrine_test`.)
- [ ] Rodar a suíte de ETL relacionada para detectar regressão de import/contrato:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_collect.py tests/test_thumbnails.py tests/test_collect_criativos.py -v
  ```
  Saída esperada: `passed`, `0 failed`.
- [ ] Aplicar superpowers:verification-before-completion: confirmar visualmente a linha "N passed" na saída do pytest antes de declarar concluído. Se houver qualquer `failed`/`error`, NÃO declarar pronto — debugar com superpowers:systematic-debugging.
- [ ] Commit final (somente se houver ajuste residual de teste/código nesta task; caso contrário, pular):
  ```
  git add web/backend/etl/collect_criativos.py web/backend/tests/test_collect_criativos.py
  git commit -m "test(etl): suite verde para coleta Google de criativos (F2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Cobertura do spec (F2) — checklist de rastreabilidade

| Requisito do spec (linhas 112–116, 181, 203) | Task |
|---|---|
| GAQL em `ad_group_ad` com `segments.date` + campos exatos (`ad.id`, `ad.name`, `ad.type`, `cost_micros`, `conversions`, `conversions_value`, `impressions`, `clicks`) | Task 2 |
| Granularidade diária por anúncio (agregação por `(ad_id, dia)`) | Task 6 |
| Thumb via image ad; search ads sem imagem → `thumb_status = SEM_IMAGEM` | Tasks 4, 6 |
| Deep-link para o Google Ads UI (ou `null` onde não construível) | Tasks 3, 6 |
| Upsert idempotente por `(cliente_id, rede, ad_id, dia)` e `(cliente_id, rede, ad_id)`, `rede=GOOGLE` | Tasks 6, 7 |
| `ThreadPoolExecutor` + uma `SessionLocal` por thread (orquestração Google integrada ao run) | Task 9 |
| Limitação de plataforma explícita (responsive/video/asset adiados; não bloqueiam F2) | Escopo de plataforma + Task 4 |
| Cliente sem `id_google_ads`/`"0"` → não coleta | Task 5 |
| Falha de API isolada por cliente (não derruba o batch) | Task 8 |

**Itens fora desta fase (cobertos por outras fases do contrato, não regredir):** API agregada e `/thumb` (F3), frontend/date-range/chips (F4), `gestor_travado`/sync (F5), auditoria de IDs e "Turbo" (F6), cron no Render (operacional). O entrypoint CLI `python -m etl.collect_criativos` e a função `coletar_criativos_meta` já existem (F1); F2 não os recria.
