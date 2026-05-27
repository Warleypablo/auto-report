# TurboMax Peça 2 — Dados de Criativos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar 2 novas ferramentas ao TurboMax (`buscar_anuncios_meta` e `buscar_anuncios_google`) que retornam métricas no nível de anúncio individual — CTR, CPM, hook rate, frequency, ROAS por criativo.

**Architecture:** Extensão direta do módulo existente `web/backend/api/turbomax.py`. Cada nova ferramenta segue exatamente o padrão das `buscar_campanhas_*` já implementadas: `_check_acesso_cliente` → `_get_cliente_core` → chamada de API com validação de data → retorno de lista de anúncios. A única diferença é `level=ad` na Meta e `FROM ad_group_ad` no GAQL do Google.

**Tech Stack:** FastAPI, requests (Meta Ads Graph API v23.0 `level=ad`), Google Ads SDK (`ad_group_ad` entity), pytest com mocks.

---

## File Structure

| Arquivo | Ação | O que muda |
|---|---|---|
| `web/backend/api/turbomax.py` | Modificar | +2 constantes, +2 funções, +2 entradas no TOOLS, +2 dispatch em `_execute_tool`, update system prompt |
| `web/backend/tests/test_turbomax.py` | Modificar | +4 testes (sem ID Meta, sucesso Meta, sem ID Google, sucesso Google) |

---

### Task 1: `buscar_anuncios_meta` — nível de anúncio no Meta Ads

**Files:**
- Modify: `web/backend/api/turbomax.py`
- Modify: `web/backend/tests/test_turbomax.py`

**Contexto:**
O arquivo `turbomax.py` já tem `_META_API_VERSION = "v23.0"` e `_META_CAMPAIGN_FIELDS`. A nova ferramenta usa o mesmo endpoint com `level=ad` e campos adicionais de vídeo. A constante `_META_AD_FIELDS` deve ser adicionada logo após `_META_CAMPAIGN_FIELDS` (linha ~422). A função `_buscar_anuncios_meta` deve ser adicionada após `_buscar_campanhas_meta` (linha ~488). O dispatch em `_execute_tool` deve ser adicionado após o caso `buscar_campanhas_google` (linha ~587), ANTES do `return {"erro": ...}`.

A entrada no array `TOOLS` deve ser adicionada após o dict `buscar_campanhas_google` (penúltima entrada, antes do `]` que fecha o array, por volta da linha 196).

- [ ] **Step 1: Adicionar entrada no TOOLS**

No arquivo `web/backend/api/turbomax.py`, localizar o fim do array `TOOLS` — está logo antes de `# ─── Access control helper ───`. Adicionar dois novos dicts antes do `]` de fechamento:

```python
    {
        "name": "buscar_anuncios_meta",
        "description": (
            "Busca anúncios individuais no Meta Ads para um cliente num período. "
            "Retorna métricas por criativo: CTR, CPM, hook rate (retenção de 3s), "
            "frequency, purchases e ROAS por anúncio. Use para identificar quais "
            "criativos estão performando melhor ou apresentando fadiga."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "date_start": {"type": "string", "description": "Data início YYYY-MM-DD"},
                "date_end": {"type": "string", "description": "Data fim YYYY-MM-DD"},
            },
            "required": ["slug", "date_start", "date_end"],
        },
    },
    {
        "name": "buscar_anuncios_google",
        "description": (
            "Busca anúncios individuais no Google Ads para um cliente num período. "
            "Retorna métricas por ad: CTR, CPC, conversões, ROAS e ad group. "
            "Use para identificar quais anúncios de texto/display convertem melhor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "date_start": {"type": "string", "description": "Data início YYYY-MM-DD"},
                "date_end": {"type": "string", "description": "Data fim YYYY-MM-DD"},
            },
            "required": ["slug", "date_start", "date_end"],
        },
    },
```

- [ ] **Step 2: Adicionar constante `_META_AD_FIELDS`**

Logo após a linha `_META_CAMPAIGN_FIELDS = (...)`, adicionar:

```python
_META_AD_FIELDS = (
    "ad_id,ad_name,adset_name,campaign_name,"
    "spend,impressions,clicks,reach,frequency,"
    "actions,action_values,video_p3_watched_actions"
)
```

- [ ] **Step 3: Escrever o teste que falha**

Adicionar ao final de `web/backend/tests/test_turbomax.py`:

```python
def test_buscar_anuncios_meta_sem_id_meta(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_meta_ads = None

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core):
            from api.turbomax import _buscar_anuncios_meta
            result = _buscar_anuncios_meta(slug, "2026-05-01", "2026-05-31", admin, s)

    assert "erro" in result
    assert "Meta Ads" in result["erro"]


def test_buscar_anuncios_meta_retorna_lista(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_meta_ads = "act_12345"

    fake_response = {
        "data": [
            {
                "ad_id": "222",
                "ad_name": "UGC_Produto_V1",
                "adset_name": "Prospecção Broad",
                "campaign_name": "Prospecção_CBO",
                "spend": "3000",
                "impressions": "120000",
                "clicks": "2400",
                "reach": "100000",
                "frequency": "1.2",
                "actions": [{"action_type": "purchase", "value": "12"}],
                "action_values": [{"action_type": "purchase", "value": "12000"}],
                "video_p3_watched_actions": [{"action_type": "video_view", "value": "30000"}],
            }
        ]
    }

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core), \
             patch("api.turbomax.requests.get") as mock_get:
            mock_get.return_value.json.return_value = fake_response
            mock_get.return_value.raise_for_status = MagicMock()
            from api.turbomax import _buscar_anuncios_meta
            result = _buscar_anuncios_meta(slug, "2026-05-01", "2026-05-31", admin, s)

    assert len(result["anuncios"]) == 1
    ad = result["anuncios"][0]
    assert ad["nome"] == "UGC_Produto_V1"
    assert ad["purchases"] == 12
    assert ad["hook_rate"] == pytest.approx(25.0, rel=1e-2)  # 30000/120000*100
    assert ad["purchase_roas"] == pytest.approx(4.0, rel=1e-2)  # 12000/3000
```

- [ ] **Step 4: Rodar os testes para verificar que falham**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/pytest tests/test_turbomax.py::test_buscar_anuncios_meta_sem_id_meta tests/test_turbomax.py::test_buscar_anuncios_meta_retorna_lista -v
```

Esperado: `ImportError` ou `AttributeError` — `_buscar_anuncios_meta` ainda não existe.

- [ ] **Step 5: Implementar `_buscar_anuncios_meta`**

Adicionar após a função `_buscar_campanhas_meta` (antes de `_buscar_campanhas_google`):

```python
def _buscar_anuncios_meta(
    slug: str, date_start: str, date_end: str, user: Usuario, session: Session
) -> dict:
    _check_acesso_cliente(slug, user, session)

    cliente_core = _get_cliente_core(slug)
    if cliente_core is None:
        return {"erro": f"Cliente '{slug}' não encontrado na Planilha Central"}

    ad_account_id = getattr(cliente_core, "id_meta_ads", None)
    if not ad_account_id:
        return {"erro": f"Cliente '{slug}' não tem ID Meta Ads configurado"}

    from config.settings import ACCESS_TOKEN_META_SYSTEM  # noqa: PLC0415

    raw = str(ad_account_id)
    acct_path = f"act_{raw.removeprefix('act_')}"
    url = f"https://graph.facebook.com/{_META_API_VERSION}/{acct_path}/insights"
    params = {
        "level": "ad",
        "time_range": json.dumps({"since": date_start, "until": date_end}, separators=(",", ":")),
        "time_increment": "all_days",
        "fields": _META_AD_FIELDS,
        "access_token": ACCESS_TOKEN_META_SYSTEM,
        "limit": 50,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        _log.warning("Meta Ads API (ad level) falhou para %s: %s", slug, exc)
        return {"erro": f"Falha ao acessar Meta Ads: {exc}"}

    anuncios = []
    for a in resp.json().get("data", []):
        spend = float(a.get("spend") or 0)
        impressions = int(a.get("impressions") or 0)
        clicks = int(a.get("clicks") or 0)
        frequency = float(a.get("frequency") or 0)

        actions = {x["action_type"]: float(x["value"]) for x in a.get("actions") or []}
        action_values = {x["action_type"]: float(x["value"]) for x in a.get("action_values") or []}
        video_3s = sum(float(x["value"]) for x in a.get("video_p3_watched_actions") or [])

        purchases = actions.get("purchase", actions.get("offsite_conversion.fb_pixel_purchase", 0))
        purchase_value = action_values.get(
            "purchase", action_values.get("offsite_conversion.fb_pixel_purchase", 0)
        )

        anuncios.append({
            "id": a.get("ad_id"),
            "nome": a.get("ad_name"),
            "adset": a.get("adset_name"),
            "campanha": a.get("campaign_name"),
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions * 100, 2) if impressions else 0,
            "cpm": round(spend / impressions * 1000, 2) if impressions else 0,
            "frequency": round(frequency, 2),
            "hook_rate": round(video_3s / impressions * 100, 2) if impressions else None,
            "purchases": int(purchases),
            "purchase_roas": round(purchase_value / spend, 2) if spend else 0,
        })

    anuncios.sort(key=lambda x: x["spend"], reverse=True)
    return {
        "cliente": slug,
        "periodo": {"inicio": date_start, "fim": date_end},
        "anuncios": anuncios,
    }
```

- [ ] **Step 6: Adicionar dispatch em `_execute_tool`**

Dentro de `_execute_tool`, localizar o bloco `if name == "buscar_campanhas_google": ...` e adicionar APÓS ele (antes do `return {"erro": ...}`):

```python
    if name == "buscar_anuncios_meta":
        return _buscar_anuncios_meta(
            tool_input["slug"], tool_input["date_start"], tool_input["date_end"],
            user, session,
        )
    if name == "buscar_anuncios_google":
        return _buscar_anuncios_google(
            tool_input["slug"], tool_input["date_start"], tool_input["date_end"],
            user, session,
        )
```

- [ ] **Step 7: Rodar os testes — devem passar**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/pytest tests/test_turbomax.py::test_buscar_anuncios_meta_sem_id_meta tests/test_turbomax.py::test_buscar_anuncios_meta_retorna_lista -v
```

Esperado: 2 PASSED.

- [ ] **Step 8: Commit**

```bash
git add web/backend/api/turbomax.py web/backend/tests/test_turbomax.py
git commit -m "feat(turbomax-p2): buscar_anuncios_meta — nível de criativo com hook rate"
```

---

### Task 2: `buscar_anuncios_google` + update system prompt

**Files:**
- Modify: `web/backend/api/turbomax.py`
- Modify: `web/backend/tests/test_turbomax.py`

**Contexto:**
`_buscar_anuncios_google` usa o entity `ad_group_ad` do Google Ads GAQL (diferente de `campaign` usado em `_buscar_campanhas_google`). O dispatch em `_execute_tool` já foi adicionado no Task 1 Step 6 — não adicionar de novo. O system prompt precisa mencionar os dados de criativo agora disponíveis e os benchmarks relevantes.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `web/backend/tests/test_turbomax.py`:

```python
def test_buscar_anuncios_google_sem_id_google(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_google_ads = None

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core):
            from api.turbomax import _buscar_anuncios_google
            result = _buscar_anuncios_google(slug, "2026-05-01", "2026-05-31", admin, s)

    assert "erro" in result
    assert "Google Ads" in result["erro"]


def test_buscar_anuncios_google_mock_client(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_google_ads = "1234567890"

    fake_row = MagicMock()
    fake_row.ad_group_ad.ad.id = 555
    fake_row.ad_group_ad.ad.name = "Headline_Produto_V2"
    fake_row.ad_group_ad.ad.type_.name = "EXPANDED_TEXT_AD"
    fake_row.ad_group.name = "Produto - Exact"
    fake_row.campaign.name = "Search_Brand"
    fake_row.metrics.cost_micros = 1_500_000
    fake_row.metrics.impressions = 8000
    fake_row.metrics.clicks = 400
    fake_row.metrics.conversions = 18.0
    fake_row.metrics.conversions_value = 5400.0

    fake_ga_service = MagicMock()
    fake_ga_service.search.return_value = [fake_row]
    fake_client = MagicMock()
    fake_client.get_service.return_value = fake_ga_service

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core), \
             patch("core.cred_manager._build_google_ads_client", return_value=fake_client):
            from api.turbomax import _buscar_anuncios_google
            result = _buscar_anuncios_google(slug, "2026-05-01", "2026-05-31", admin, s)

    assert len(result["anuncios"]) == 1
    ad = result["anuncios"][0]
    assert ad["nome"] == "Headline_Produto_V2"
    assert ad["spend"] == 1.5
    assert ad["roas"] == pytest.approx(3.6, rel=1e-2)  # 5400/1500
    assert ad["ctr"] == pytest.approx(5.0, rel=1e-2)   # 400/8000*100
```

- [ ] **Step 2: Rodar os testes para verificar que falham**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/pytest tests/test_turbomax.py::test_buscar_anuncios_google_sem_id_google tests/test_turbomax.py::test_buscar_anuncios_google_mock_client -v
```

Esperado: `ImportError` ou `AttributeError` — `_buscar_anuncios_google` ainda não existe.

- [ ] **Step 3: Implementar `_buscar_anuncios_google`**

Adicionar após `_buscar_anuncios_meta` (antes de `_execute_tool`):

```python
def _buscar_anuncios_google(
    slug: str, date_start: str, date_end: str, user: Usuario, session: Session
) -> dict:
    _check_acesso_cliente(slug, user, session)

    cliente_core = _get_cliente_core(slug)
    if cliente_core is None:
        return {"erro": f"Cliente '{slug}' não encontrado na Planilha Central"}

    customer_id = str(getattr(cliente_core, "id_google_ads", "") or "").replace("-", "")
    if not customer_id or customer_id == "0":
        return {"erro": f"Cliente '{slug}' não tem ID Google Ads configurado"}

    for d in (date_start, date_end):
        if len(d) != 10 or d[4] != "-" or d[7] != "-" or not d.replace("-", "").isdigit():
            return {"erro": f"Formato de data inválido: '{d}'. Use YYYY-MM-DD."}

    from core.cred_manager import _build_google_ads_client  # noqa: PLC0415

    gaql = (
        "SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.ad.type, "
        "ad_group.name, campaign.name, "
        "metrics.cost_micros, metrics.impressions, metrics.clicks, "
        "metrics.conversions, metrics.conversions_value "
        "FROM ad_group_ad "
        f"WHERE segments.date BETWEEN '{date_start}' AND '{date_end}' "
        "AND metrics.cost_micros > 0 "
        "ORDER BY metrics.cost_micros DESC "
        "LIMIT 50"
    )

    try:
        client = _build_google_ads_client()
        ga_service = client.get_service("GoogleAdsService")
        response = ga_service.search(customer_id=customer_id, query=gaql)
    except Exception as exc:
        _log.warning("Google Ads API (ad level) falhou para %s: %s", slug, exc)
        return {"erro": f"Falha ao acessar Google Ads: {exc}"}

    anuncios = []
    for row in response:
        cost = row.metrics.cost_micros / 1_000_000
        conv = float(row.metrics.conversions or 0)
        conv_value = float(row.metrics.conversions_value or 0)
        impressions = int(row.metrics.impressions or 0)
        clicks = int(row.metrics.clicks or 0)
        anuncios.append({
            "id": str(row.ad_group_ad.ad.id),
            "nome": row.ad_group_ad.ad.name,
            "tipo": getattr(row.ad_group_ad.ad.type_, "name", None),
            "ad_group": row.ad_group.name,
            "campanha": row.campaign.name,
            "spend": round(cost, 2),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions * 100, 2) if impressions else 0,
            "cpc": round(cost / clicks, 2) if clicks else 0,
            "conversions": round(conv, 1),
            "conv_value": round(conv_value, 2),
            "roas": round(conv_value / cost, 2) if cost else 0,
        })

    return {
        "cliente": slug,
        "periodo": {"inicio": date_start, "fim": date_end},
        "anuncios": anuncios,
    }
```

- [ ] **Step 4: Atualizar o system prompt**

Localizar a seção `CONTEXTO TURBO PARTNERS:` no `_SYSTEM_PROMPT` e substituir:

```python
CONTEXTO TURBO PARTNERS:
- Categorias de clientes: E-commerce (ROAS ≥ 3.0 é referência), Lead Com Site, \
Lead Sem Site (CPL como métrica principal)
- Métricas disponíveis: faturamento, investimento, ROAS, CPA, leads, vendas (mensais)
- Sinais: roas_queda (>20%), faturamento_queda (>25%), roas_brand_inflado, \
oportunidade_escala, cpl_vs_media
```

Por:

```python
CONTEXTO TURBO PARTNERS:
- Categorias de clientes: E-commerce (ROAS ≥ 3.0 é referência), Lead Com Site, \
Lead Sem Site (CPL como métrica principal)
- Métricas disponíveis: faturamento, investimento, ROAS, CPA, leads, vendas (mensais)
- Sinais: roas_queda (>20%), faturamento_queda (>25%), roas_brand_inflado, \
oportunidade_escala, cpl_vs_media
- Dados de criativo disponíveis: hook_rate (% de impressões com 3s de vídeo assistidos), \
frequency por anúncio, CTR por anúncio, ROAS por anúncio, CPM por anúncio
- Benchmarks criativo Meta: hook_rate > 20% = bom, < 10% = problema no início do vídeo; \
CTR > 2% = bom; frequency > 3.5 no mesmo anúncio = fadiga; CPM subindo + CTR caindo = saturação
- Para identificar top criativos use buscar_anuncios_meta; para criativos Google use buscar_anuncios_google
```

- [ ] **Step 5: Rodar todos os testes**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/pytest tests/test_turbomax.py -v
```

Esperado: todos os 21 testes PASSAM (17 existentes + 4 novos).

- [ ] **Step 6: Commit**

```bash
git add web/backend/api/turbomax.py web/backend/tests/test_turbomax.py
git commit -m "feat(turbomax-p2): buscar_anuncios_google + update system prompt criativos"
```

---

## Self-Review

**Spec coverage:**
- ✅ `buscar_anuncios_meta` com `level=ad`, hook_rate, frequency, CTR, CPM, ROAS por anúncio
- ✅ `buscar_anuncios_google` com `ad_group_ad`, CTR, CPC, ROAS por anúncio
- ✅ Ambas adicionadas ao `TOOLS` e ao `_execute_tool`
- ✅ System prompt atualizado com benchmarks de criativo
- ✅ Testes para path sem credencial e path com mock de sucesso

**Placeholder scan:** nenhum "TBD" ou "similar ao task N".

**Type consistency:** `_buscar_anuncios_meta` e `_buscar_anuncios_google` têm a mesma assinatura `(slug, date_start, date_end, user, session) -> dict` — consistente com `_buscar_campanhas_*`. Dispatch em `_execute_tool` usa a mesma pattern de extração de keys obrigatórias.
