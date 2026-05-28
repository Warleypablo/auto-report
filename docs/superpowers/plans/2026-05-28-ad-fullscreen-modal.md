# Modal fullscreen do anúncio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o drawer lateral atual do anúncio por uma experiência híbrida: drawer 380px para preview rápido + modal fullscreen para análise profunda, incluindo novas métricas de funil (CTR, Hook Rate, Frequency) coletadas da Meta/Google API.

**Architecture:** Backend expande coleta Meta/Google e parser do snapshot; frontend cria dois shells coexistentes (`MetaDrawer`/`MetaAdFullscreen` e Google análogos) que consomem blocos atômicos compartilhados (`KpiHeader`, `MetricsRows`, `ContextBlock`, `FunilFadigaBlock`, `EvolucaoChart`, `CriativoPreview`) e um hook `useAdContext` reusado.

**Tech Stack:** Python 3.14 (FastAPI, Pydantic, SQLAlchemy, pytest), Next.js 14 + React + TypeScript, framer-motion, Recharts, Playwright.

**Spec:** `docs/superpowers/specs/2026-05-28-ad-fullscreen-modal-design.md`

---

## Fase A — Backend: schemas e parser do snapshot

### Task A1: Estender schemas Pydantic `MetaAd` e `GoogleAd`

**Files:**
- Modify: `web/backend/schemas/gestor.py` (procurar classe `MetaAd` e `GoogleAd`)

- [ ] **Step 1: Localizar as classes**

Run: `grep -n "^class MetaAd\|^class GoogleAd" /Users/mac0267/Documents/auto-report-main/web/backend/schemas/gestor.py`
Expected: dois números de linha (uma para cada classe).

- [ ] **Step 2: Adicionar campos em `MetaAd`**

Adicionar após `imagem_url`:

```python
    # Funil & fadiga (podem ser None para snapshots antigos ou anúncios estáticos)
    ctr: float | None = None
    frequency: float | None = None
    hook_rate: float | None = None
```

- [ ] **Step 3: Adicionar campo em `GoogleAd`**

Adicionar após o último campo existente:

```python
    ctr: float | None = None
```

- [ ] **Step 4: Verificar que servidor importa sem erro**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/backend && python -c "from schemas.gestor import MetaAd, GoogleAd; print(MetaAd.model_fields.keys()); print(GoogleAd.model_fields.keys())"`
Expected: lista incluindo `ctr`, `frequency`, `hook_rate` em MetaAd; `ctr` em GoogleAd.

- [ ] **Step 5: Commit**

```bash
git add web/backend/schemas/gestor.py
git commit -m "feat(backend): adicionar ctr/frequency/hook_rate em MetaAd e ctr em GoogleAd"
```

---

### Task A2: Parser de `build_breakdown` — teste falhando

**Files:**
- Modify: `web/backend/tests/test_services_metricas.py`

- [ ] **Step 1: Adicionar teste para os novos campos no parser**

Adicionar ao final do arquivo:

```python
def test_build_breakdown_parses_funil_metrics(monkeypatch):
    """build_breakdown deve parsear ctr/freq/hook (Meta) e ctr (Google) quando presentes,
    e devolver None quando ausentes."""
    from unittest.mock import MagicMock
    import services.metricas as svc

    # Snapshot fake com TODOS os placeholders novos no ad #1, e SEM os novos no ad #2.
    raw = {
        "{{nome_adf1}}": "Loop AI",
        "{{inv_adf1}}": "R$ 1.000,00",
        "{{lead_adf1}}": "10",
        "{{cpl_adf1}}": "R$ 100,00",
        "{{conv_adf1}}": "5",
        "{{fat_adf1}}": "R$ 5.000,00",
        "{{roas_adf1}}": "5,00",
        "{{cpa_adf1}}": "R$ 200,00",
        "{{imp_adf1}}": "1.000",
        "{{img_adf1}}": "https://example.com/a.jpg",
        "{{ctr_adf1}}": "2,40",
        "{{freq_adf1}}": "3,20",
        "{{hook_adf1}}": "38,00",
        "{{nome_adf2}}": "Brand B",
        "{{inv_adf2}}": "R$ 500,00",
        "{{imp_adf2}}": "500",
        "{{nome_adg1}}": "Search BR",
        "{{inv_adg1}}": "R$ 200,00",
        "{{ctr_adg1}}": "1,80",
    }

    snap = MagicMock()
    snap.raw_dados = raw
    snap.periodo_fim = None

    session = MagicMock()
    session.execute.return_value.scalars.return_value.first.return_value = snap

    out = svc.build_breakdown(MagicMock(), None, session)

    meta = out["meta_ads"]
    assert meta[0]["nome"] == "Loop AI"
    assert meta[0]["ctr"] == 2.40
    assert meta[0]["frequency"] == 3.20
    assert meta[0]["hook_rate"] == 38.00

    assert meta[1]["nome"] == "Brand B"
    assert meta[1]["ctr"] is None
    assert meta[1]["frequency"] is None
    assert meta[1]["hook_rate"] is None

    google = out["google_ads"]
    assert google[0]["nome"] == "Search BR"
    assert google[0]["ctr"] == 1.80
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/backend && pytest tests/test_services_metricas.py::test_build_breakdown_parses_funil_metrics -v`
Expected: FAIL (KeyError ou os campos retornam ausentes do dict).

- [ ] **Step 3: Commit**

```bash
git add web/backend/tests/test_services_metricas.py
git commit -m "test(backend): teste falhando para parser de ctr/freq/hook"
```

---

### Task A3: Parser de `build_breakdown` — implementação

**Files:**
- Modify: `web/backend/services/metricas.py:99-110` (meta_ads.append) e `web/backend/services/metricas.py:117-125` (google_ads.append)

- [ ] **Step 1: Adicionar parse dos novos campos em `meta_ads.append`**

Substituir o bloco `meta_ads.append({...})` em `services/metricas.py` por:

```python
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
            "ctr": _parse_br(rd.get(f"{{{{ctr_adf{i}}}}}")),
            "frequency": _parse_br(rd.get(f"{{{{freq_adf{i}}}}}")),
            "hook_rate": _parse_br(rd.get(f"{{{{hook_adf{i}}}}}")),
        })
```

- [ ] **Step 2: Adicionar parse do CTR em `google_ads.append`**

Substituir o bloco `google_ads.append({...})` por:

```python
        google_ads.append({
            "nome": nome,
            "investimento": _parse_br(rd.get(f"{{{{inv_adg{i}}}}}")),
            "faturamento": _parse_br(rd.get(f"{{{{fat_adg{i}}}}}")),
            "conversoes": _parse_br(rd.get(f"{{{{conv_adg{i}}}}}")),
            "cpa": _parse_br(rd.get(f"{{{{cpa_adg{i}}}}}")),
            "roas": _parse_br(rd.get(f"{{{{roas_adg{i}}}}}")),
            "impressoes": _parse_int_br(rd.get(f"{{{{imp_adg{i}}}}}")),
            "ctr": _parse_br(rd.get(f"{{{{ctr_adg{i}}}}}")),
        })
```

- [ ] **Step 3: Rodar o teste e confirmar passa**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/backend && pytest tests/test_services_metricas.py::test_build_breakdown_parses_funil_metrics -v`
Expected: PASS.

- [ ] **Step 4: Rodar suite de testes do parser**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/backend && pytest tests/test_services_metricas.py -v`
Expected: todos verdes (4 testes existentes + 1 novo).

- [ ] **Step 5: Commit**

```bash
git add web/backend/services/metricas.py
git commit -m "feat(backend): parser de ctr/frequency/hook_rate em build_breakdown"
```

---

## Fase B — Backend: coletor Meta Ads (gather)

### Task B1: Helper `_video_3s_views_from_row` — teste falhando

**Files:**
- Create: `web/backend/tests/test_video_views_helper.py`

- [ ] **Step 1: Escrever teste**

```python
"""Testa o helper _video_3s_views_from_row presente nos 3 campaign_facebook_gather.py.
Como o helper é local de cada arquivo, importamos de um dos arquivos (são idênticos)."""

import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "core" / "categorias" / "lead_com_site" / "campaign_facebook_gather.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cf_gather_lcs", ROOT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cf_gather_lcs"] = module
    spec.loader.exec_module(module)
    return module


def test_video_3s_views_returns_none_when_key_absent():
    m = _load_module()
    row = {"ad_id": "1", "impressions": "100"}
    assert m._video_3s_views_from_row(row) is None


def test_video_3s_views_reads_video_3_sec_watched_actions():
    m = _load_module()
    row = {
        "video_3_sec_watched_actions": [
            {"action_type": "video_view", "value": "42"},
        ],
    }
    assert m._video_3s_views_from_row(row) == 42


def test_video_3s_views_fallback_to_actions_video_view():
    m = _load_module()
    row = {
        "actions": [
            {"action_type": "post_engagement", "value": "10"},
            {"action_type": "video_view", "value": "15"},
        ],
    }
    assert m._video_3s_views_from_row(row) == 15


def test_video_3s_views_sums_multiple_video_actions():
    m = _load_module()
    row = {
        "video_3_sec_watched_actions": [
            {"action_type": "video_view", "value": "10"},
            {"action_type": "video_view", "value": "20"},
        ],
    }
    assert m._video_3s_views_from_row(row) == 30
```

- [ ] **Step 2: Rodar o teste e confirmar falha**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/backend && pytest tests/test_video_views_helper.py -v`
Expected: FAIL (`AttributeError: module 'cf_gather_lcs' has no attribute '_video_3s_views_from_row'`).

- [ ] **Step 3: Commit**

```bash
git add web/backend/tests/test_video_views_helper.py
git commit -m "test(backend): teste falhando para _video_3s_views_from_row"
```

---

### Task B2: Helper `_video_3s_views_from_row` — implementação (3 arquivos)

**Files:**
- Modify: `core/categorias/lead_com_site/campaign_facebook_gather.py`
- Modify: `core/categorias/ecommerce/campaign_facebook_gather.py`
- Modify: `core/categorias/lead_sem_site/campaign_facebook_gather.py`

- [ ] **Step 1: Adicionar o helper após `_lead_count_from_any` em `lead_com_site/campaign_facebook_gather.py`**

```python
def _video_3s_views_from_row(row: dict) -> Optional[int]:
    """Extrai contagem de 3-second video plays do row da Meta Insights API.

    Tenta na ordem: `video_3_sec_watched_actions` (campo dedicado) e
    `actions[action_type=video_view]` (fallback clássico). Retorna `None`
    quando nenhuma das chaves está presente — sinal de que o anúncio não
    é em vídeo (estático/imagem), distinguindo de "zero views".
    """
    primary = row.get("video_3_sec_watched_actions")
    if primary:
        total = 0
        for item in primary:
            if isinstance(item, dict) and "value" in item:
                try:
                    total += int(float(item["value"]))
                except (TypeError, ValueError):
                    continue
        return total

    actions = row.get("actions")
    if actions and isinstance(actions, list):
        total = 0
        found = False
        for item in actions:
            if not isinstance(item, dict):
                continue
            if item.get("action_type") == "video_view":
                found = True
                try:
                    total += int(float(item.get("value", 0)))
                except (TypeError, ValueError):
                    continue
        return total if found else None

    return None
```

- [ ] **Step 2: Copiar o mesmo helper para `ecommerce/campaign_facebook_gather.py`**

Adicionar na mesma posição (após `_lead_count_from_any`).

- [ ] **Step 3: Copiar o mesmo helper para `lead_sem_site/campaign_facebook_gather.py`**

Adicionar na mesma posição.

- [ ] **Step 4: Rodar os testes e confirmar passam**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/backend && pytest tests/test_video_views_helper.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/categorias/lead_com_site/campaign_facebook_gather.py \
        core/categorias/ecommerce/campaign_facebook_gather.py \
        core/categorias/lead_sem_site/campaign_facebook_gather.py
git commit -m "feat(meta-gather): adicionar _video_3s_views_from_row em 3 categorias"
```

---

### Task B3: Atualizar `fields` e geração de placeholders Meta (3 arquivos)

**Files:**
- Modify: `core/categorias/lead_com_site/campaign_facebook_gather.py`
- Modify: `core/categorias/ecommerce/campaign_facebook_gather.py`
- Modify: `core/categorias/lead_sem_site/campaign_facebook_gather.py`

> Os três arquivos seguem o mesmo pattern — repetir cada mudança nos três.

- [ ] **Step 1: Atualizar `fields` da chamada Insights**

Localizar a linha com `"fields": "ad_id,ad_name,spend,impressions,results,actions,conversions"` (uma em cada arquivo) e substituir por:

```python
        "fields": (
            "ad_id,ad_name,spend,impressions,results,actions,conversions,"
            "clicks,reach,video_3_sec_watched_actions"
        ),
```

- [ ] **Step 2: Estender o loop `ads.append({...})` para capturar `clicks`, `reach`, `video_3s`**

Localizar `ads.append({...})` (logo após o for de rows) e substituir por:

```python
        ads.append({
            "ad_name": row.get("ad_name") or _DEF_DASH,
            "ad_id":   row.get("ad_id"),
            "spend":   float(row.get("spend", 0.0)),
            "lead":    leads,
            "imp":     int(row.get("impressions") or 0),
            "clicks":  int(row.get("clicks") or 0),
            "reach":   int(row.get("reach") or 0),
            "video_3s": _video_3s_views_from_row(row),
        })
```

- [ ] **Step 3: Adicionar novos placeholders no loop `for rank, ad in enumerate(ads_top, start=1)`**

Localizar o bloco `placeholders.update({ ... })` e estender com:

```python
        ctr = (ad["clicks"] / ad["imp"] * 100) if ad["imp"] > 0 else None
        frequency = (ad["imp"] / ad["reach"]) if ad["reach"] > 0 else None
        hook_rate = None
        if ad["video_3s"] is not None and ad["imp"] > 0:
            hook_rate = ad["video_3s"] / ad["imp"] * 100

        placeholders.update({
            f"{{{{nome_adf{rank}}}}}": ad["ad_name"],
            f"{{{{img_adf{rank}}}}}":  ad["thumb"],
            f"{{{{lead_adf{rank}}}}}": _fmt_int(ad["lead"]),
            f"{{{{cpl_adf{rank}}}}}":  _fmt_brl(cpl, 2) if cpl is not None else _DEF_DASH,
            f"{{{{inv_adf{rank}}}}}":  _fmt_brl(ad["spend"], 2),
            f"{{{{lpi_adf{rank}}}}}":  _fmt_percent(lpi) if lpi is not None else _DEF_DASH,
            f"{{{{imp_adf{rank}}}}}":  _fmt_int(ad["imp"]),
            f"{{{{ctr_adf{rank}}}}}":  f"{ctr:.2f}".replace(".", ",") if ctr is not None else _DEF_DASH,
            f"{{{{freq_adf{rank}}}}}": f"{frequency:.2f}".replace(".", ",") if frequency is not None else _DEF_DASH,
            f"{{{{hook_adf{rank}}}}}": f"{hook_rate:.2f}".replace(".", ",") if hook_rate is not None else _DEF_DASH,
        })
```

- [ ] **Step 4: Estender o loop "placeholders restantes com dash"**

Localizar `for rank in range(len(ads_top) + 1, top_n + 1):` e estender o `placeholders.update({...})` com:

```python
            f"{{{{ctr_adf{rank}}}}}":  "-",
            f"{{{{freq_adf{rank}}}}}": "-",
            f"{{{{hook_adf{rank}}}}}": "-",
```

- [ ] **Step 5: Repetir steps 1-4 nos outros dois arquivos** (`ecommerce/campaign_facebook_gather.py` e `lead_sem_site/campaign_facebook_gather.py`)

- [ ] **Step 6: Verificar sintaxe Python dos 3 arquivos**

Run: `cd /Users/mac0267/Documents/auto-report-main && python -c "import ast; ast.parse(open('core/categorias/lead_com_site/campaign_facebook_gather.py').read()); ast.parse(open('core/categorias/ecommerce/campaign_facebook_gather.py').read()); ast.parse(open('core/categorias/lead_sem_site/campaign_facebook_gather.py').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add core/categorias/lead_com_site/campaign_facebook_gather.py \
        core/categorias/ecommerce/campaign_facebook_gather.py \
        core/categorias/lead_sem_site/campaign_facebook_gather.py
git commit -m "feat(meta-gather): coletar clicks/reach/video_3s e gerar placeholders ctr/freq/hook"
```

---

## Fase C — Backend: coletor Google Ads (CTR)

### Task C1: Localizar coleta Google e identificar o que falta

**Files:**
- Read: `core/categorias/lead_com_site/campaign_google_gather.py`
- Read: `core/categorias/ecommerce/campaign_google_gather.py`

- [ ] **Step 1: Verificar quais campos Google Ads o coletor pede**

Run: `grep -n "clicks\|ctr\|GAQL\|impressions" core/categorias/lead_com_site/campaign_google_gather.py core/categorias/ecommerce/campaign_google_gather.py | head -30`
Expected: identificar se `clicks` já é coletado (Google Ads sempre expõe via `metrics.clicks`).

- [ ] **Step 2: Localizar o loop que gera placeholders `{{*_adg<rank>}}`**

Run: `grep -n "nome_adg\|inv_adg\|imp_adg" core/categorias/lead_com_site/campaign_google_gather.py core/categorias/ecommerce/campaign_google_gather.py | head -10`
Expected: linhas com o `placeholders.update({...})`.

- [ ] **Step 3: Anotar diferenças entre os dois arquivos Google**

Confirmar se ambos têm a mesma estrutura ou divergem (talvez um seja Search e outro Display/Performance Max).

> Nenhum commit nesta task — só leitura.

---

### Task C2: Adicionar CTR aos coletores Google (2 arquivos)

**Files:**
- Modify: `core/categorias/lead_com_site/campaign_google_gather.py`
- Modify: `core/categorias/ecommerce/campaign_google_gather.py`

- [ ] **Step 1: Adicionar `metrics.clicks` ao GAQL/query se não estiver**

Localizar a query GAQL (geralmente em string multi-linha) e garantir que `metrics.clicks` está nos campos selecionados. Exemplo:

```python
query = """
    SELECT
        ad_group_ad.ad.id,
        ad_group_ad.ad.name,
        metrics.cost_micros,
        metrics.impressions,
        metrics.clicks,
        metrics.conversions,
        metrics.conversions_value
    FROM ad_group_ad
    WHERE segments.date BETWEEN @since AND @until
"""
```

> Se o arquivo já tem `metrics.clicks`, pular este step.

- [ ] **Step 2: Capturar `clicks` por anúncio no loop de processamento**

No loop que processa cada linha de resultado (similar ao Meta), adicionar:

```python
        clicks = int(row.metrics.clicks or 0)
        # (próximo da onde já captura impressions/cost)
```

Anexar `"clicks": clicks` ao dicionário do ad.

- [ ] **Step 3: Calcular CTR e gerar placeholder**

No bloco `placeholders.update({...})` (loop dos ads_top), adicionar:

```python
        ctr = (ad["clicks"] / ad["imp"] * 100) if ad["imp"] > 0 else None
        placeholders[f"{{{{ctr_adg{rank}}}}}"] = (
            f"{ctr:.2f}".replace(".", ",") if ctr is not None else _DEF_DASH
        )
```

- [ ] **Step 4: Adicionar dash no loop de placeholders restantes**

No loop `for rank in range(len(ads_top) + 1, top_n + 1):` adicionar:

```python
        placeholders[f"{{{{ctr_adg{rank}}}}}"] = "-"
```

- [ ] **Step 5: Repetir steps 1-4 no segundo arquivo**

- [ ] **Step 6: Verificar sintaxe**

Run: `cd /Users/mac0267/Documents/auto-report-main && python -c "import ast; ast.parse(open('core/categorias/lead_com_site/campaign_google_gather.py').read()); ast.parse(open('core/categorias/ecommerce/campaign_google_gather.py').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add core/categorias/lead_com_site/campaign_google_gather.py \
        core/categorias/ecommerce/campaign_google_gather.py
git commit -m "feat(google-gather): coletar clicks e gerar placeholder ctr_adg"
```

---

## Fase D — Frontend: tipos, hook compartilhado e infra

### Task D1: Estender tipos `MetaAd` e `GoogleAd` no TypeScript

**Files:**
- Modify: `web/frontend/lib/api-gestor.ts:102-123`

- [ ] **Step 1: Estender `MetaAd`**

Substituir o type `MetaAd` por:

```ts
export type MetaAd = {
  nome: string;
  investimento: number | null;
  leads: number | null;
  cpl: number | null;
  conversoes: number | null;
  faturamento: number | null;
  roas: number | null;
  cpa: number | null;
  impressoes: number | null;
  imagem_url: string | null;
  ctr: number | null;
  frequency: number | null;
  hook_rate: number | null;
};
```

- [ ] **Step 2: Estender `GoogleAd`**

Substituir o type `GoogleAd` por:

```ts
export type GoogleAd = {
  nome: string;
  investimento: number | null;
  faturamento: number | null;
  conversoes: number | null;
  cpa: number | null;
  roas: number | null;
  impressoes: number | null;
  ctr: number | null;
};
```

- [ ] **Step 3: Verificar type check passa**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: sem erros relacionados aos novos campos. Erros pré-existentes ignoráveis.

> Os componentes `MetaDrawer`/`GoogleDrawer` continuam funcionando — os campos novos são opcionais (`null`) e nenhuma referência ainda existe.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/lib/api-gestor.ts
git commit -m "feat(frontend): adicionar ctr/frequency/hook_rate em MetaAd e ctr em GoogleAd"
```

---

### Task D2: Extrair hook `useAdContext`

**Files:**
- Create: `web/frontend/components/performance/useAdContext.ts`

- [ ] **Step 1: Criar diretório e arquivo**

Run: `mkdir -p /Users/mac0267/Documents/auto-report-main/web/frontend/components/performance`

- [ ] **Step 2: Escrever o hook**

```ts
// web/frontend/components/performance/useAdContext.ts
import { useMemo } from "react";
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";

type RoasTier = "alto" | "medio" | "baixo" | "neutro";

function computeRoasTier(roas: number | null): RoasTier {
  if (roas == null) return "neutro";
  if (roas >= 3) return "alto";
  if (roas >= 1.5) return "medio";
  return "baixo";
}

export type AdContext = {
  tier: RoasTier;
  avgRoas: number | null;
  roasVsAvg: number | null;
  maxRoas: number;
  barPct: number;
  shareInv: number | null;
  shareFat: number | null;
  cpm: number | null;
  // Médias das novas métricas (null se nenhum ad tem o campo populado).
  avgCtr: number | null;
  avgFrequency: number | null;
  avgHookRate: number | null;
};

function avg(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((s, v) => s + v, 0) / values.length;
}

export function useAdContext<T extends MetaAd | GoogleAd>(
  ad: T,
  allAds: T[],
): AdContext {
  return useMemo<AdContext>(() => {
    const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0);
    const avgRoas = avg(adsComRoas.map((a) => a.roas as number));
    const roasVsAvg = avgRoas && ad.roas ? ad.roas / avgRoas : null;
    const maxRoas =
      adsComRoas.length > 0 ? Math.max(...adsComRoas.map((a) => a.roas as number)) : 0;
    const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;

    const totalInv = allAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
    const totalFat = allAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
    const shareInv = totalInv > 0 && ad.investimento ? (ad.investimento / totalInv) * 100 : null;
    const shareFat = totalFat > 0 && ad.faturamento ? (ad.faturamento / totalFat) * 100 : null;

    const cpm =
      ad.impressoes && ad.investimento && ad.impressoes > 0
        ? (ad.investimento / ad.impressoes) * 1000
        : null;

    // Médias do funil — usar guards porque GoogleAd não tem hook_rate/frequency.
    const ctrValues = allAds
      .map((a) => (a as { ctr?: number | null }).ctr)
      .filter((v): v is number => typeof v === "number");
    const freqValues = allAds
      .map((a) => (a as { frequency?: number | null }).frequency)
      .filter((v): v is number => typeof v === "number");
    const hookValues = allAds
      .map((a) => (a as { hook_rate?: number | null }).hook_rate)
      .filter((v): v is number => typeof v === "number");

    return {
      tier: computeRoasTier(ad.roas),
      avgRoas,
      roasVsAvg,
      maxRoas,
      barPct,
      shareInv,
      shareFat,
      cpm,
      avgCtr: avg(ctrValues),
      avgFrequency: avg(freqValues),
      avgHookRate: avg(hookValues),
    };
  }, [ad, allAds]);
}
```

- [ ] **Step 3: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -i useAdContext || echo OK`
Expected: `OK` (sem erros relacionados ao novo arquivo).

- [ ] **Step 4: Commit**

```bash
git add web/frontend/components/performance/useAdContext.ts
git commit -m "feat(frontend): hook useAdContext para cálculos de contexto do anúncio"
```

---

### Task D3: Extrair `EvolucaoChart` como componente reusável com `mode`

**Files:**
- Create: `web/frontend/components/performance/EvolucaoChart.tsx`
- Modify: `web/frontend/app/gestor/performance/page.tsx` (remover `EvolucaoTab` e importar `EvolucaoChart`)

- [ ] **Step 1: Criar o componente extraído**

Copiar a função `EvolucaoTab` de `web/frontend/app/gestor/performance/page.tsx:346-498` para o novo arquivo, renomeando para `EvolucaoChart`, e adicionar prop `mode`:

```tsx
// web/frontend/components/performance/EvolucaoChart.tsx
"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { gestorApi } from "@/lib/api-gestor";

// Reusar helpers do page.tsx. Em vez de duplicar, exportá-los de page.tsx
// pode forçar dependência circular; aqui usamos versões locais minimalistas.

type HistoryPoint = {
  mes: string;
  mesLabel: string;
  roas: number | null;
  cpm: number | null;
  investimento: number | null;
  faturamento: number | null;
};

type FadigaDiag =
  | { kind: "fadiga"; label: string }
  | { kind: "queda"; label: string }
  | { kind: "estavel"; label: string }
  | null;

const MES_ABBR: Record<string, string> = {
  "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
  "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
  "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
};

function deslocarMes(mes: string, delta: number): string {
  const ano = parseInt(mes.slice(0, 4), 10);
  const m = parseInt(mes.slice(5, 7), 10);
  const totalMeses = ano * 12 + (m - 1) + delta;
  const novoAno = Math.floor(totalMeses / 12);
  const novoMes = (totalMeses % 12) + 1;
  return `${novoAno}-${String(novoMes).padStart(2, "0")}`;
}

function fmtK(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `R$${(v / 1_000).toFixed(0)}k`;
  return `R$${v.toFixed(0)}`;
}

function detectFadiga(pts: HistoryPoint[]): FadigaDiag {
  const withRoas = pts.filter((p) => p.roas != null);
  if (withRoas.length < 3) return null;
  const last3 = withRoas.slice(-3);
  const decrescente = last3[0].roas! > last3[1].roas! && last3[1].roas! > last3[2].roas!;
  if (decrescente) return { kind: "fadiga", label: "⚠ ROAS caindo há 3 meses" };
  return { kind: "estavel", label: "ROAS estável" };
}

function EvolucaoTooltip({ active, payload }: { active?: boolean; payload?: { payload: HistoryPoint }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1.5 font-medium text-[var(--ink)]">{d.mesLabel}</p>
      <p style={{ color: "#34d399" }}>ROAS: {d.roas != null ? `${d.roas.toFixed(2)}×` : "—"}</p>
      <p style={{ color: "#f59e0b" }}>CPM: {d.cpm != null ? fmtK(d.cpm) : "—"}</p>
      <p className="text-[var(--muted)]">Faturamento: {fmtK(d.faturamento)}</p>
      <p className="text-[var(--muted)]">Investimento: {fmtK(d.investimento)}</p>
    </div>
  );
}

export type EvolucaoChartProps = {
  clienteSlug: string;
  adNome: string;
  adType: "meta" | "google";
  mes: string;
  mode?: "drawer" | "fullscreen";
};

export function EvolucaoChart({ clienteSlug, adNome, adType, mes, mode = "drawer" }: EvolucaoChartProps) {
  const [history, setHistory] = useState<HistoryPoint[] | null>(null);
  const [loading, setLoading] = useState(true);
  const chartHeight = mode === "fullscreen" ? 320 : 200;

  useEffect(() => {
    const meses = Array.from({ length: 6 }, (_, i) => deslocarMes(mes, -i)).reverse();
    Promise.all(
      meses.map((m) => gestorApi.metricasBreakdown(clienteSlug, m).catch(() => null)),
    )
      .then((results) => {
        const pts: HistoryPoint[] = meses.map((m, i) => {
          const bd = results[i];
          const ads = adType === "meta" ? bd?.meta_ads ?? [] : bd?.google_ads ?? [];
          const ad = ads.find((a) => a.nome === adNome) ?? null;
          const cpm =
            ad?.investimento && ad?.impressoes && ad.impressoes > 0
              ? (ad.investimento / ad.impressoes) * 1000
              : null;
          return {
            mes: m,
            mesLabel: MES_ABBR[m.slice(5, 7)] ?? m.slice(5, 7),
            roas: ad?.roas ?? null,
            cpm,
            investimento: ad?.investimento ?? null,
            faturamento: ad?.faturamento ?? null,
          };
        });
        setHistory(pts);
        setLoading(false);
      })
      .catch(() => {
        setHistory([]);
        setLoading(false);
      });
  }, [clienteSlug, adNome, adType, mes]);

  if (loading) {
    return (
      <div className="mt-6 space-y-3 px-1">
        <div
          className="animate-pulse rounded-xl bg-[var(--paper-deep)]"
          style={{ height: chartHeight - 20 }}
        />
        <div className="flex gap-2">
          {[78, 55, 90, 45, 70, 60].map((w, i) => (
            <div
              key={i}
              className="animate-pulse rounded bg-[var(--paper-deep)]"
              style={{ height: 4, width: `${w}px`, animationDelay: `${i * 80}ms` }}
            />
          ))}
        </div>
      </div>
    );
  }

  const hasAnyData = history?.some((p) => p.roas !== null) ?? false;

  if (!hasAnyData) {
    return (
      <div className="mt-10 text-center text-xs text-[var(--muted)]">
        Sem histórico disponível para este criativo.
      </div>
    );
  }

  const diagnosis = detectFadiga(history!);

  return (
    <div className="mt-4">
      {diagnosis && (
        <div
          className={`mb-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
            diagnosis.kind === "fadiga"
              ? "bg-amber-900/30 text-amber-300"
              : diagnosis.kind === "queda"
                ? "bg-red-900/30 text-red-300"
                : "bg-emerald-900/30 text-emerald-300"
          }`}
        >
          {diagnosis.label}
        </div>
      )}

      <ResponsiveContainer width="100%" height={chartHeight}>
        <ComposedChart data={history!} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="mesLabel" tick={{ fontSize: 9, fill: "#6b7280" }} axisLine={false} tickLine={false} />
          <YAxis
            yAxisId="ratio"
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v}×`}
          />
          <YAxis
            yAxisId="reais"
            orientation="right"
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => fmtK(v)}
          />
          <Bar yAxisId="reais" dataKey="faturamento" fill="#34d399" opacity={0.22} radius={[2, 2, 0, 0]} />
          <Bar yAxisId="reais" dataKey="investimento" fill="#6b7280" opacity={0.18} radius={[2, 2, 0, 0]} />
          <Line yAxisId="ratio" type="monotone" dataKey="roas" stroke="#34d399" strokeWidth={2} dot={{ r: 3, fill: "#34d399", strokeWidth: 0 }} connectNulls={false} />
          <Line yAxisId="reais" type="monotone" dataKey="cpm" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4 2" dot={{ r: 2, fill: "#f59e0b", strokeWidth: 0 }} connectNulls={false} />
          <Tooltip content={<EvolucaoTooltip />} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[9px] text-[var(--muted)]">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 rounded" style={{ background: "#34d399" }} />
          ROAS
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 border-t-2 border-dashed" style={{ borderColor: "#f59e0b" }} />
          CPM
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "#34d399", opacity: 0.5 }} />
          Fat.
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "#6b7280", opacity: 0.4 }} />
          Inv.
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Remover `EvolucaoTab` e `EvolucaoTooltip` de `page.tsx`**

Em `web/frontend/app/gestor/performance/page.tsx`, deletar as funções `EvolucaoTooltip` e `EvolucaoTab` (linhas ~332-498). Apagar também os helpers `MES_ABBR`, `deslocarMes`, `detectFadiga` se estiverem duplicados (mantendo se forem usados em outros lugares — confirmar com grep).

- [ ] **Step 3: Importar e substituir uso no page.tsx**

Adicionar import:
```ts
import { EvolucaoChart } from "@/components/performance/EvolucaoChart";
```

E substituir `<EvolucaoTab clienteSlug={...} adNome={...} adType="meta" mes={mes} />` por:
```tsx
<EvolucaoChart clienteSlug={ad.clienteSlug} adNome={ad.nome} adType="meta" mes={mes} mode="drawer" />
```

Repetir para o GoogleDrawer.

- [ ] **Step 4: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -E "EvolucaoTab|EvolucaoChart" || echo OK`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/components/performance/EvolucaoChart.tsx \
        web/frontend/app/gestor/performance/page.tsx
git commit -m "refactor(frontend): extrair EvolucaoChart com prop mode (drawer|fullscreen)"
```

---

## Fase E — Frontend: blocos atômicos compartilhados

### Task E1: Criar `KpiHeader`

**Files:**
- Create: `web/frontend/components/performance/blocks/KpiHeader.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// web/frontend/components/performance/blocks/KpiHeader.tsx
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import type { AdContext } from "../useAdContext";

type RankedAd = (MetaAd | GoogleAd) & { rank: number };

const MEDAL = ["🥇", "🥈", "🥉"];

const TIER_BAR: Record<string, string> = {
  alto: "bg-emerald-400",
  medio: "bg-amber-400",
  baixo: "bg-red-400",
  neutro: "bg-zinc-500",
};

const TIER_TEXT: Record<string, string> = {
  alto: "text-emerald-400",
  medio: "text-amber-400",
  baixo: "text-red-400",
  neutro: "text-zinc-400",
};

function fmtRoas(roas: number | null): string {
  if (roas == null) return "—";
  return `${roas.toFixed(2)}×`;
}

function fmtK(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `R$${(v / 1_000).toFixed(0)}k`;
  return `R$${v.toFixed(0)}`;
}

export type KpiHeaderProps = {
  ad: RankedAd;
  ctx: AdContext;
  totalAdsComRoas: number;
  mode: "drawer" | "fullscreen";
};

export function KpiHeader({ ad, ctx, totalAdsComRoas, mode }: KpiHeaderProps) {
  if (mode === "drawer") {
    return (
      <div className="mb-5 flex items-center gap-3">
        {ad.rank < 3 && <span className="text-2xl">{MEDAL[ad.rank]}</span>}
        {ad.rank >= 3 && <span className="font-mono-num text-sm text-[var(--muted)]">#{ad.rank + 1}</span>}
        <div className="flex-1 min-w-0">
          <div className="mb-1 flex items-center justify-between">
            <span className={`font-mono-num text-lg font-semibold ${TIER_TEXT[ctx.tier]}`}>
              {fmtRoas(ad.roas)}
            </span>
            <span className="text-[10px] text-[var(--muted)]">{totalAdsComRoas} criativos</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
            <div className={`h-1.5 rounded-full ${TIER_BAR[ctx.tier]}`} style={{ width: `${ctx.barPct}%` }} />
          </div>
        </div>
      </div>
    );
  }

  // mode === "fullscreen"
  return (
    <div className="mb-8">
      <div className="mb-3 flex items-baseline gap-6">
        {ad.rank < 3 && <span className="text-4xl">{MEDAL[ad.rank]}</span>}
        {ad.rank >= 3 && <span className="font-mono-num text-2xl text-[var(--muted)]">#{ad.rank + 1}</span>}
        <span className={`font-mono-num text-5xl font-semibold ${TIER_TEXT[ctx.tier]}`}>
          {fmtRoas(ad.roas)}
        </span>
        <div className="flex flex-wrap gap-6 text-sm">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Faturamento</p>
            <p className="font-mono-num text-lg text-[var(--forest)]">{fmtK(ad.faturamento)}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Investimento</p>
            <p className="font-mono-num text-lg text-[var(--ink)]">{fmtK(ad.investimento)}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">CPM</p>
            <p className="font-mono-num text-lg text-[var(--ink)]">{fmtK(ctx.cpm)}</p>
          </div>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
        <div className={`h-1.5 rounded-full ${TIER_BAR[ctx.tier]}`} style={{ width: `${ctx.barPct}%` }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -i KpiHeader || echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/performance/blocks/KpiHeader.tsx
git commit -m "feat(frontend): bloco KpiHeader compartilhado (modes drawer/fullscreen)"
```

---

### Task E2: Criar `MetricsRows`

**Files:**
- Create: `web/frontend/components/performance/blocks/MetricsRows.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// web/frontend/components/performance/blocks/MetricsRows.tsx
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";

function fmtRoas(roas: number | null): string {
  return roas == null ? "—" : `${roas.toFixed(2)}×`;
}
function fmtK(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `R$${(v / 1_000).toFixed(0)}k`;
  return `R$${v.toFixed(0)}`;
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-[var(--rule-soft)] py-2 last:border-0">
      <span className="text-xs text-[var(--muted)]">{label}</span>
      <span
        className={`font-mono-num text-sm ${
          highlight ? "font-semibold text-[var(--forest)]" : "text-[var(--ink)]"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export type MetricsRowsProps = {
  ad: MetaAd | GoogleAd;
  cpm: number | null;
  mode: "drawer" | "fullscreen";
};

export function MetricsRows({ ad, cpm, mode }: MetricsRowsProps) {
  const isMeta = "leads" in ad;
  const padding = mode === "fullscreen" ? "px-6" : "px-4";

  return (
    <div className={`mb-5 rounded-xl border border-[var(--rule-soft)] ${padding}`}>
      <Row label="Faturamento" value={fmtK(ad.faturamento)} highlight />
      <Row label="Investimento" value={fmtK(ad.investimento)} />
      <Row label="ROAS" value={fmtRoas(ad.roas)} highlight />
      {ad.conversoes != null && <Row label="Conversões" value={String(ad.conversoes)} />}
      {isMeta && (ad as MetaAd).leads != null && <Row label="Leads" value={String((ad as MetaAd).leads)} />}
      {ad.cpa != null && <Row label="CPA" value={fmtK(ad.cpa)} />}
      {isMeta && (ad as MetaAd).cpl != null && <Row label="CPL" value={fmtK((ad as MetaAd).cpl)} />}
      {ad.impressoes != null && <Row label="Impressões" value={ad.impressoes.toLocaleString("pt-BR")} />}
      {cpm != null && <Row label="CPM" value={fmtK(cpm)} />}
    </div>
  );
}
```

- [ ] **Step 2: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -i MetricsRows || echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/performance/blocks/MetricsRows.tsx
git commit -m "feat(frontend): bloco MetricsRows compartilhado"
```

---

### Task E3: Criar `ContextBlock`

**Files:**
- Create: `web/frontend/components/performance/blocks/ContextBlock.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// web/frontend/components/performance/blocks/ContextBlock.tsx
import type { AdContext } from "../useAdContext";

function fmtRoas(roas: number | null): string {
  return roas == null ? "—" : `${roas.toFixed(2)}×`;
}
function fmtPct(p: number): string {
  return `${p.toFixed(1)}%`;
}

function ContextBar({ label, pct }: { label: string; pct: number }) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="mb-1 flex justify-between text-[10px] text-[var(--muted)]">
        <span>{label}</span>
        <span>{fmtPct(pct)}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
        <div
          className="h-1.5 rounded-full bg-[var(--forest)] opacity-70"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

export type ContextBlockProps = {
  ctx: AdContext;
  mode: "drawer" | "fullscreen";
};

export function ContextBlock({ ctx, mode }: ContextBlockProps) {
  if (mode === "drawer") {
    return (
      <>
        <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">
          Contexto · carteira
        </p>
        {ctx.roasVsAvg != null && (
          <div className="mb-4 rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3">
            <p className="text-xs text-[var(--muted)]">ROAS vs. média da carteira</p>
            <p
              className={`mt-1 font-mono-num text-2xl font-semibold ${
                ctx.roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"
              }`}
            >
              {ctx.roasVsAvg >= 1 ? "+" : ""}
              {((ctx.roasVsAvg - 1) * 100).toFixed(0)}%
            </p>
            <p className="mt-0.5 text-[10px] text-[var(--muted)]">
              Média: {fmtRoas(ctx.avgRoas)}
            </p>
          </div>
        )}
        {(ctx.shareInv != null || ctx.shareFat != null) && (
          <div className="rounded-xl border border-[var(--rule-soft)] px-4 py-3">
            {ctx.shareInv != null && <ContextBar label="Share de investimento" pct={ctx.shareInv} />}
            {ctx.shareFat != null && <ContextBar label="Share de faturamento" pct={ctx.shareFat} />}
          </div>
        )}
      </>
    );
  }

  // fullscreen — horizontal, 3 colunas
  return (
    <div className="mt-6 rounded-xl border border-[var(--rule-soft)] px-6 py-5">
      <p className="mb-4 text-[10px] uppercase tracking-widest text-[var(--muted)]">
        Contexto · carteira
      </p>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {ctx.roasVsAvg != null && (
          <div>
            <p className="text-xs text-[var(--muted)]">ROAS vs. média</p>
            <p
              className={`mt-1 font-mono-num text-3xl font-semibold ${
                ctx.roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"
              }`}
            >
              {ctx.roasVsAvg >= 1 ? "+" : ""}
              {((ctx.roasVsAvg - 1) * 100).toFixed(0)}%
            </p>
            <p className="mt-0.5 text-[10px] text-[var(--muted)]">Média: {fmtRoas(ctx.avgRoas)}</p>
          </div>
        )}
        {ctx.shareInv != null && (
          <div>
            <p className="text-xs text-[var(--muted)]">Share de investimento</p>
            <p className="mt-1 font-mono-num text-3xl text-[var(--ink)]">{fmtPct(ctx.shareInv)}</p>
          </div>
        )}
        {ctx.shareFat != null && (
          <div>
            <p className="text-xs text-[var(--muted)]">Share de faturamento</p>
            <p className="mt-1 font-mono-num text-3xl text-[var(--forest)]">{fmtPct(ctx.shareFat)}</p>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -i ContextBlock || echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/performance/blocks/ContextBlock.tsx
git commit -m "feat(frontend): bloco ContextBlock compartilhado"
```

---

### Task E4: Criar `CriativoPreview`

**Files:**
- Create: `web/frontend/components/performance/blocks/CriativoPreview.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// web/frontend/components/performance/blocks/CriativoPreview.tsx
import AdThumbnail from "@/components/AdThumbnail";
import type { MetaAd } from "@/lib/api-gestor";

export type CriativoPreviewProps = {
  ad: MetaAd;
  mode: "drawer" | "fullscreen";
};

export function CriativoPreview({ ad, mode }: CriativoPreviewProps) {
  if (!ad.imagem_url) return null;
  const height = mode === "fullscreen" ? 400 : 220;
  return (
    <div
      className="mb-5 overflow-hidden rounded-xl border border-[var(--rule-soft)]"
      style={{ height }}
    >
      <AdThumbnail src={ad.imagem_url} alt={ad.nome} className="h-full w-full object-cover" />
    </div>
  );
}
```

> Confirmar nome do export de `AdThumbnail` antes (pode ser default ou named). Verificar com: `grep -n "export" web/frontend/components/AdThumbnail.tsx`

- [ ] **Step 2: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -i CriativoPreview || echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/performance/blocks/CriativoPreview.tsx
git commit -m "feat(frontend): bloco CriativoPreview compartilhado"
```

---

### Task E5: Criar `FunilFadigaBlock` (novo)

**Files:**
- Create: `web/frontend/components/performance/blocks/FunilFadigaBlock.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// web/frontend/components/performance/blocks/FunilFadigaBlock.tsx
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import type { AdContext } from "../useAdContext";

type Variant = "meta" | "google";

function fmtPct(v: number | null, suffix = "%"): string {
  return v == null ? "—" : `${v.toFixed(1)}${suffix}`;
}
function fmtDecimal(v: number | null): string {
  return v == null ? "—" : v.toFixed(2);
}

function ComparisonArrow({ value, avg }: { value: number | null; avg: number | null }) {
  if (value == null || avg == null) return null;
  const above = value >= avg;
  return (
    <span className={`text-[10px] ${above ? "text-emerald-400" : "text-red-400"}`}>
      {above ? "↑" : "↓"} média {avg.toFixed(2)}
      {value < 1 || avg < 1 ? "" : "×"}
    </span>
  );
}

function FunilKpi({
  label,
  value,
  avg,
  formatFn,
  unavailableHint,
}: {
  label: string;
  value: number | null;
  avg: number | null;
  formatFn: (v: number | null) => string;
  unavailableHint?: string;
}) {
  return (
    <div className="flex-1">
      <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">{label}</p>
      <p className="mt-1 font-mono-num text-3xl text-[var(--ink)]">{formatFn(value)}</p>
      {value == null && unavailableHint && (
        <p className="mt-0.5 text-[9px] italic text-[var(--muted)]">{unavailableHint}</p>
      )}
      {value != null && <ComparisonArrow value={value} avg={avg} />}
    </div>
  );
}

export type FunilFadigaBlockProps = {
  ad: MetaAd | GoogleAd;
  ctx: AdContext;
  variant: Variant;
};

export function FunilFadigaBlock({ ad, ctx, variant }: FunilFadigaBlockProps) {
  const adAny = ad as MetaAd;
  const allUnavailable =
    variant === "meta"
      ? adAny.ctr == null && adAny.frequency == null && adAny.hook_rate == null
      : adAny.ctr == null;

  return (
    <div className="rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-6 py-5">
      <p className="mb-4 text-[10px] uppercase tracking-widest text-[var(--muted)]">
        Funil &amp; fadiga
      </p>
      <div className="flex gap-8">
        <FunilKpi
          label="CTR"
          value={adAny.ctr ?? null}
          avg={ctx.avgCtr}
          formatFn={(v) => fmtPct(v)}
        />
        {variant === "meta" && (
          <>
            <FunilKpi
              label="Hook rate"
              value={adAny.hook_rate ?? null}
              avg={ctx.avgHookRate}
              formatFn={(v) => fmtPct(v)}
              unavailableHint="Apenas vídeo"
            />
            <FunilKpi
              label="Frequency"
              value={adAny.frequency ?? null}
              avg={ctx.avgFrequency}
              formatFn={fmtDecimal}
            />
          </>
        )}
      </div>
      {allUnavailable && (
        <p className="mt-4 text-[10px] italic text-[var(--muted)]">
          Métricas de funil indisponíveis neste período. Disponíveis a partir do próximo ciclo de
          coleta.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -i FunilFadigaBlock || echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/performance/blocks/FunilFadigaBlock.tsx
git commit -m "feat(frontend): bloco FunilFadigaBlock (CTR + Hook Rate + Frequency)"
```

---

## Fase F — Frontend: refatorar drawers existentes

### Task F1: Refatorar `MetaDrawer` para usar blocos atômicos + botão expandir

**Files:**
- Modify: `web/frontend/app/gestor/performance/page.tsx` (função `MetaDrawer`, ~linhas 529-653)

- [ ] **Step 1: Adicionar imports no topo de `page.tsx`**

Adicionar (perto dos outros imports):

```ts
import { useAdContext } from "@/components/performance/useAdContext";
import { KpiHeader } from "@/components/performance/blocks/KpiHeader";
import { MetricsRows } from "@/components/performance/blocks/MetricsRows";
import { ContextBlock } from "@/components/performance/blocks/ContextBlock";
import { CriativoPreview } from "@/components/performance/blocks/CriativoPreview";
import { FunilFadigaBlock } from "@/components/performance/blocks/FunilFadigaBlock";
```

- [ ] **Step 2: Substituir o corpo de `MetaDrawer`**

Substituir a função inteira `MetaDrawer` por:

```tsx
function MetaDrawer({
  ad,
  allAds,
  onClose,
  onExpand,
  mes,
}: {
  ad: RankedMetaAd;
  allAds: RankedMetaAd[];
  onClose: () => void;
  onExpand: () => void;
  mes: string;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const [drawerTab, setDrawerTab] = useState<"metricas" | "evolucao">("metricas");
  const ctx = useAdContext(ad, allAds);
  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0).length;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-[380px] flex-col bg-[var(--paper)] shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-[var(--rule-soft)] px-5 py-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-[var(--ink)]" title={ad.nome}>
              {ad.nome}
            </p>
            <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
          </div>
          <div className="flex flex-shrink-0 items-center gap-2">
            <button
              onClick={onExpand}
              aria-label="Expandir para tela inteira"
              title="Expandir"
              className="text-base leading-none text-[var(--muted)] transition hover:text-[var(--ink)]"
            >
              ⛶
            </button>
            <button
              onClick={onClose}
              aria-label="Fechar"
              className="text-lg leading-none text-[var(--muted)] transition hover:text-[var(--ink)]"
            >
              ×
            </button>
          </div>
        </div>

        <div className="flex border-b border-[var(--rule-soft)] px-5">
          {(["metricas", "evolucao"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setDrawerTab(t)}
              className={`mr-5 pb-2 pt-2.5 text-xs transition ${
                drawerTab === t
                  ? "border-b-2 border-[var(--forest)] font-medium text-[var(--ink)]"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              {t === "metricas" ? "Métricas" : "Evolução"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {drawerTab === "evolucao" ? (
            <EvolucaoChart
              clienteSlug={ad.clienteSlug}
              adNome={ad.nome}
              adType="meta"
              mes={mes}
              mode="drawer"
            />
          ) : (
            <>
              <CriativoPreview ad={ad} mode="drawer" />
              <KpiHeader ad={ad} ctx={ctx} totalAdsComRoas={adsComRoas} mode="drawer" />
              <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">
                Métricas
              </p>
              <MetricsRows ad={ad} cpm={ctx.cpm} mode="drawer" />
              <ContextBlock ctx={ctx} mode="drawer" />
            </>
          )}
        </div>

        <div className="border-t border-[var(--rule-soft)] px-5 py-3">
          <Link
            href={`/gestor/${ad.clienteSlug}`}
            className="block text-center text-xs text-[var(--forest)] transition hover:underline"
          >
            Ver dashboard do cliente →
          </Link>
        </div>
      </aside>
    </>
  );
}
```

- [ ] **Step 3: Atualizar o uso do `MetaDrawer` em `page.tsx`**

Buscar onde `MetaDrawer` é renderizado e adicionar a prop `onExpand`:

```tsx
{selectedMeta && (
  <MetaDrawer
    ad={selectedMeta}
    allAds={metaAds}
    onClose={() => setSelectedMeta(null)}
    onExpand={() => {
      setSelectedMetaFullscreen(selectedMeta);
      setSelectedMeta(null);
    }}
    mes={mes}
  />
)}
```

> O state `selectedMetaFullscreen` ainda não existe — será criado na Task G3. Por agora, deixar o `onExpand` como `() => {}` placeholder ou comentário `// TODO: wire up fullscreen` se quiser commits intermediários funcionando. **Recomendado:** fazer Task G3 antes desta — ver ordem alternativa abaixo.

- [ ] **Step 4: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: sem erros novos.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/app/gestor/performance/page.tsx
git commit -m "refactor(frontend): MetaDrawer consome blocos atômicos + botão expandir"
```

---

### Task F2: Refatorar `GoogleDrawer` análogo

**Files:**
- Modify: `web/frontend/app/gestor/performance/page.tsx` (função `GoogleDrawer`)

- [ ] **Step 1: Substituir o corpo de `GoogleDrawer`**

Substituir a função inteira `GoogleDrawer` por:

```tsx
function GoogleDrawer({
  ad,
  allAds,
  onClose,
  onExpand,
  mes,
}: {
  ad: RankedGoogleAd;
  allAds: RankedGoogleAd[];
  onClose: () => void;
  onExpand: () => void;
  mes: string;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const [drawerTab, setDrawerTab] = useState<"metricas" | "evolucao">("metricas");
  const ctx = useAdContext(ad, allAds);
  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0).length;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-[380px] flex-col bg-[var(--paper)] shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-[var(--rule-soft)] px-5 py-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-[var(--ink)]" title={ad.nome}>
              {ad.nome}
            </p>
            <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
          </div>
          <div className="flex flex-shrink-0 items-center gap-2">
            <button
              onClick={onExpand}
              aria-label="Expandir para tela inteira"
              title="Expandir"
              className="text-base leading-none text-[var(--muted)] transition hover:text-[var(--ink)]"
            >
              ⛶
            </button>
            <button
              onClick={onClose}
              aria-label="Fechar"
              className="text-lg leading-none text-[var(--muted)] transition hover:text-[var(--ink)]"
            >
              ×
            </button>
          </div>
        </div>

        <div className="flex border-b border-[var(--rule-soft)] px-5">
          {(["metricas", "evolucao"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setDrawerTab(t)}
              className={`mr-5 pb-2 pt-2.5 text-xs transition ${
                drawerTab === t
                  ? "border-b-2 border-[var(--forest)] font-medium text-[var(--ink)]"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              {t === "metricas" ? "Métricas" : "Evolução"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {drawerTab === "evolucao" ? (
            <EvolucaoChart
              clienteSlug={ad.clienteSlug}
              adNome={ad.nome}
              adType="google"
              mes={mes}
              mode="drawer"
            />
          ) : (
            <>
              <KpiHeader ad={ad} ctx={ctx} totalAdsComRoas={adsComRoas} mode="drawer" />
              <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">
                Métricas
              </p>
              <MetricsRows ad={ad} cpm={ctx.cpm} mode="drawer" />
              <ContextBlock ctx={ctx} mode="drawer" />
            </>
          )}
        </div>

        <div className="border-t border-[var(--rule-soft)] px-5 py-3">
          <Link
            href={`/gestor/${ad.clienteSlug}`}
            className="block text-center text-xs text-[var(--forest)] transition hover:underline"
          >
            Ver dashboard do cliente →
          </Link>
        </div>
      </aside>
    </>
  );
}
```

- [ ] **Step 2: Atualizar o uso do `GoogleDrawer`**

```tsx
{selectedGoogle && (
  <GoogleDrawer
    ad={selectedGoogle}
    allAds={googleAds}
    onClose={() => setSelectedGoogle(null)}
    onExpand={() => {
      setSelectedGoogleFullscreen(selectedGoogle);
      setSelectedGoogle(null);
    }}
    mes={mes}
  />
)}
```

- [ ] **Step 3: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: sem erros novos.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/gestor/performance/page.tsx
git commit -m "refactor(frontend): GoogleDrawer consome blocos atômicos + botão expandir"
```

---

## Fase G — Frontend: modal fullscreen

### Task G1: Criar `MetaAdFullscreen`

**Files:**
- Create: `web/frontend/components/performance/MetaAdFullscreen.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// web/frontend/components/performance/MetaAdFullscreen.tsx
"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useEffect } from "react";

import type { MetaAd } from "@/lib/api-gestor";

import { useAdContext } from "./useAdContext";
import { ContextBlock } from "./blocks/ContextBlock";
import { CriativoPreview } from "./blocks/CriativoPreview";
import { EvolucaoChart } from "./EvolucaoChart";
import { FunilFadigaBlock } from "./blocks/FunilFadigaBlock";
import { KpiHeader } from "./blocks/KpiHeader";
import { MetricsRows } from "./blocks/MetricsRows";

type RankedMetaAd = MetaAd & {
  clienteNome: string;
  clienteSlug: string;
  gestorNome: string | null;
  rank: number;
  rankDelta: number | null;
};

export type MetaAdFullscreenProps = {
  ad: RankedMetaAd | null;
  allAds: RankedMetaAd[];
  onClose: () => void;
  mes: string;
};

export function MetaAdFullscreen({ ad, allAds, onClose, mes }: MetaAdFullscreenProps) {
  useEffect(() => {
    if (!ad) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ad, onClose]);

  useEffect(() => {
    if (!ad) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [ad]);

  return (
    <AnimatePresence>
      {ad && <MetaAdFullscreenBody ad={ad} allAds={allAds} onClose={onClose} mes={mes} />}
    </AnimatePresence>
  );
}

function MetaAdFullscreenBody({
  ad,
  allAds,
  onClose,
  mes,
}: {
  ad: RankedMetaAd;
  allAds: RankedMetaAd[];
  onClose: () => void;
  mes: string;
}) {
  const ctx = useAdContext(ad, allAds);
  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0).length;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-[var(--paper)]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="fs-title"
    >
      {/* Header sticky */}
      <header className="sticky top-0 z-10 flex items-start justify-between border-b border-[var(--rule-soft)] bg-[var(--paper)] px-8 py-5">
        <div className="min-w-0">
          <h2 id="fs-title" className="truncate font-display text-xl text-[var(--ink)]" title={ad.nome}>
            {ad.nome}
          </h2>
          <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar"
          className="rounded-full border border-[var(--rule-soft)] px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
        >
          Fechar ✕
        </button>
      </header>

      <div className="flex-1 px-8 py-8">
        <KpiHeader ad={ad} ctx={ctx} totalAdsComRoas={adsComRoas} mode="fullscreen" />

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          <div>
            <CriativoPreview ad={ad} mode="fullscreen" />
            <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
            <MetricsRows ad={ad} cpm={ctx.cpm} mode="fullscreen" />
          </div>

          <div className="space-y-6">
            <FunilFadigaBlock ad={ad} ctx={ctx} variant="meta" />
            <div className="rounded-xl border border-[var(--rule-soft)] px-6 py-5">
              <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">
                Evolução · 6 meses
              </p>
              <EvolucaoChart
                clienteSlug={ad.clienteSlug}
                adNome={ad.nome}
                adType="meta"
                mes={mes}
                mode="fullscreen"
              />
            </div>
          </div>
        </div>

        <ContextBlock ctx={ctx} mode="fullscreen" />
      </div>

      <footer className="border-t border-[var(--rule-soft)] px-8 py-4">
        <Link
          href={`/gestor/${ad.clienteSlug}`}
          className="text-sm text-[var(--forest)] transition hover:underline"
        >
          → Ver dashboard do cliente
        </Link>
      </footer>
    </motion.div>
  );
}
```

- [ ] **Step 2: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -i MetaAdFullscreen || echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/performance/MetaAdFullscreen.tsx
git commit -m "feat(frontend): MetaAdFullscreen com grid de 2 colunas + FunilFadigaBlock"
```

---

### Task G2: Criar `GoogleAdFullscreen`

**Files:**
- Create: `web/frontend/components/performance/GoogleAdFullscreen.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// web/frontend/components/performance/GoogleAdFullscreen.tsx
"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useEffect } from "react";

import type { GoogleAd } from "@/lib/api-gestor";

import { useAdContext } from "./useAdContext";
import { ContextBlock } from "./blocks/ContextBlock";
import { EvolucaoChart } from "./EvolucaoChart";
import { FunilFadigaBlock } from "./blocks/FunilFadigaBlock";
import { KpiHeader } from "./blocks/KpiHeader";
import { MetricsRows } from "./blocks/MetricsRows";

type RankedGoogleAd = GoogleAd & {
  clienteNome: string;
  clienteSlug: string;
  gestorNome: string | null;
  rank: number;
  rankDelta: number | null;
};

export type GoogleAdFullscreenProps = {
  ad: RankedGoogleAd | null;
  allAds: RankedGoogleAd[];
  onClose: () => void;
  mes: string;
};

export function GoogleAdFullscreen({ ad, allAds, onClose, mes }: GoogleAdFullscreenProps) {
  useEffect(() => {
    if (!ad) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ad, onClose]);

  useEffect(() => {
    if (!ad) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [ad]);

  return (
    <AnimatePresence>
      {ad && <GoogleAdFullscreenBody ad={ad} allAds={allAds} onClose={onClose} mes={mes} />}
    </AnimatePresence>
  );
}

function GoogleAdFullscreenBody({
  ad,
  allAds,
  onClose,
  mes,
}: {
  ad: RankedGoogleAd;
  allAds: RankedGoogleAd[];
  onClose: () => void;
  mes: string;
}) {
  const ctx = useAdContext(ad, allAds);
  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0).length;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-[var(--paper)]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="fs-title-g"
    >
      <header className="sticky top-0 z-10 flex items-start justify-between border-b border-[var(--rule-soft)] bg-[var(--paper)] px-8 py-5">
        <div className="min-w-0">
          <h2 id="fs-title-g" className="truncate font-display text-xl text-[var(--ink)]" title={ad.nome}>
            {ad.nome}
          </h2>
          <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar"
          className="rounded-full border border-[var(--rule-soft)] px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
        >
          Fechar ✕
        </button>
      </header>

      <div className="flex-1 px-8 py-8">
        <KpiHeader ad={ad} ctx={ctx} totalAdsComRoas={adsComRoas} mode="fullscreen" />

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          <div>
            <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
            <MetricsRows ad={ad} cpm={ctx.cpm} mode="fullscreen" />
            <FunilFadigaBlock ad={ad} ctx={ctx} variant="google" />
          </div>

          <div className="rounded-xl border border-[var(--rule-soft)] px-6 py-5">
            <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">
              Evolução · 6 meses
            </p>
            <EvolucaoChart
              clienteSlug={ad.clienteSlug}
              adNome={ad.nome}
              adType="google"
              mes={mes}
              mode="fullscreen"
            />
          </div>
        </div>

        <ContextBlock ctx={ctx} mode="fullscreen" />
      </div>

      <footer className="border-t border-[var(--rule-soft)] px-8 py-4">
        <Link
          href={`/gestor/${ad.clienteSlug}`}
          className="text-sm text-[var(--forest)] transition hover:underline"
        >
          → Ver dashboard do cliente
        </Link>
      </footer>
    </motion.div>
  );
}
```

- [ ] **Step 2: Verificar type check**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | grep -i GoogleAdFullscreen || echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/performance/GoogleAdFullscreen.tsx
git commit -m "feat(frontend): GoogleAdFullscreen (sem Hook/Frequency, com CTR)"
```

---

### Task G3: Wireup do state e renderização dos fullscreens em `page.tsx`

**Files:**
- Modify: `web/frontend/app/gestor/performance/page.tsx`

- [ ] **Step 1: Adicionar imports dos fullscreens**

```ts
import { MetaAdFullscreen } from "@/components/performance/MetaAdFullscreen";
import { GoogleAdFullscreen } from "@/components/performance/GoogleAdFullscreen";
```

- [ ] **Step 2: Adicionar states de fullscreen**

Localizar onde `selectedMeta` e `selectedGoogle` são declarados e adicionar:

```ts
const [selectedMetaFullscreen, setSelectedMetaFullscreen] = useState<RankedMetaAd | null>(null);
const [selectedGoogleFullscreen, setSelectedGoogleFullscreen] = useState<RankedGoogleAd | null>(null);
```

- [ ] **Step 3: Renderizar os fullscreens**

Adicionar antes de `</main>` (ou onde os drawers são renderizados):

```tsx
<MetaAdFullscreen
  ad={selectedMetaFullscreen}
  allAds={metaAds}
  onClose={() => setSelectedMetaFullscreen(null)}
  mes={mes}
/>
<GoogleAdFullscreen
  ad={selectedGoogleFullscreen}
  allAds={googleAds}
  onClose={() => setSelectedGoogleFullscreen(null)}
  mes={mes}
/>
```

- [ ] **Step 4: Verificar type check completo**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1 | head -40`
Expected: sem erros relacionados aos novos componentes.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/app/gestor/performance/page.tsx
git commit -m "feat(frontend): wireup dos modais fullscreen na página performance"
```

---

## Fase H — Validação e2e e manual

### Task H1: Smoke test Playwright do fluxo de expansão

**Files:**
- Create: `web/frontend/tests/e2e/gestor-performance-fullscreen.spec.ts`

- [ ] **Step 1: Verificar como outros testes e2e autenticam como gestor**

Run: `grep -rn "gestor/login\|/gestor" /Users/mac0267/Documents/auto-report-main/web/frontend/tests/e2e/ | head -10`
Expected: identificar o pattern de login do gestor (CNPJ/senha ou OAuth).

- [ ] **Step 2: Criar o teste**

```ts
// web/frontend/tests/e2e/gestor-performance-fullscreen.spec.ts
import { test, expect, type Page } from "@playwright/test";

/**
 * NOTA: ajuste a função `loginAsGestor` ao pattern usado em outros .spec.ts
 * (ver `/Users/mac0267/Documents/auto-report-main/web/frontend/tests/e2e/`).
 */
async function loginAsGestor(page: Page) {
  await page.goto("/gestor/login");
  // TODO substituir pelo pattern real do projeto, identificado no step 1.
  // Exemplo placeholder — adaptar:
  await page.getByLabel(/email/i).fill("gestor@turbopartners.com.br");
  await page.getByLabel(/senha/i).fill("test-password");
  await page.getByRole("button", { name: /entrar/i }).click();
  await page.waitForURL((u) => u.pathname.startsWith("/gestor"));
}

test.describe("Gestor performance · drawer → fullscreen", () => {
  test("clica num card de anúncio, abre drawer, expande para fullscreen, fecha", async ({ page }) => {
    await loginAsGestor(page);
    await page.goto("/gestor/performance");

    // Espera a lista de ads renderizar
    const firstAdCard = page.locator('[data-testid="ad-card-meta"]').first();
    await expect(firstAdCard).toBeVisible({ timeout: 10_000 });

    // Clica no primeiro card -> drawer abre
    await firstAdCard.click();
    const drawer = page.getByRole("dialog").or(page.locator("aside").filter({ has: page.getByText(/Métricas/i) }));
    await expect(drawer).toBeVisible();

    // Clica em "Expandir" no drawer
    const expandButton = page.getByRole("button", { name: /expandir/i });
    await expandButton.click();

    // Drawer fecha; fullscreen abre
    const fullscreen = page.getByRole("dialog", { name: /Funil/i }).or(
      page.locator('[role="dialog"][aria-modal="true"]'),
    );
    await expect(fullscreen).toBeVisible();
    await expect(page.getByText(/Funil/i)).toBeVisible();

    // ESC fecha o fullscreen
    await page.keyboard.press("Escape");
    await expect(fullscreen).toBeHidden();

    // Drawer NÃO reabre — só o ranking aparece
    await expect(drawer).toBeHidden();
  });
});
```

> O teste assume que cada card de anúncio Meta tem `data-testid="ad-card-meta"`. Se ainda não existir, adicionar essa marca no card como parte deste step.

- [ ] **Step 3: Adicionar `data-testid` no card do anúncio**

Em `web/frontend/app/gestor/performance/page.tsx`, localizar o `<button>` do card Meta (perto da linha 295-323 referenciada na exploração) e adicionar:

```tsx
<button
  data-testid="ad-card-meta"
  /* ... resto das props ... */
>
```

- [ ] **Step 4: Rodar o teste (pode falhar por login — ajustar conforme necessário)**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx playwright test gestor-performance-fullscreen -x 2>&1 | tail -30`
Expected: idealmente PASS; se falhar por login, ajustar `loginAsGestor` ao pattern correto e re-rodar.

- [ ] **Step 5: Commit (mesmo se o teste estiver skip/fail por login — não bloquear)**

```bash
git add web/frontend/tests/e2e/gestor-performance-fullscreen.spec.ts \
        web/frontend/app/gestor/performance/page.tsx
git commit -m "test(e2e): smoke do fluxo drawer → fullscreen"
```

---

### Task H2: Validação manual no browser

**Files:** nenhum (apenas execução)

- [ ] **Step 1: Subir backend**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/backend && uvicorn main:app --reload --port 8000 &`
Expected: servidor sobe e logs aparecem.

- [ ] **Step 2: Subir frontend**

Run: `cd /Users/mac0267/Documents/auto-report-main/web/frontend && npm run dev &`
Expected: Next.js sobe em `http://localhost:3000`.

- [ ] **Step 3: Login e navegação até /gestor/performance**

Abrir browser em `http://localhost:3000/gestor/login`, autenticar, navegar até `/gestor/performance`.

- [ ] **Step 4: Validar drawer existente**

- Clicar em um card de anúncio Meta com dados → drawer abre
- Clicar em "Métricas" e "Evolução" → tabs alternam
- Botão ⛶ aparece no header

- [ ] **Step 5: Validar fullscreen**

- Clicar em ⛶ → drawer fecha, fullscreen abre
- Header com nome do anúncio + botão fechar
- KPI grande, preview do criativo grande
- Bloco "Funil & Fadiga" presente
  - Se snapshot atual tem CTR/Hook/Freq → valores aparecem
  - Se snapshot é antigo → "—" + nota "indisponíveis neste período"
- Gráfico de evolução com 320px de altura
- Bloco "Contexto · carteira" no rodapé
- ESC fecha; drawer NÃO reabre

- [ ] **Step 6: Validar GoogleAdFullscreen**

- Repetir o fluxo com um card Google
- `FunilFadigaBlock` exibe **só CTR** (sem Hook/Frequency)

- [ ] **Step 7: Validar responsividade**

- Reduzir janela para < 768px → grid colapsa para coluna única
- Header e botão fechar continuam usáveis

- [ ] **Step 8: Validar acessibilidade básica**

- Pressionar `Tab` dentro do fullscreen → foco circula entre botões/links
- ESC fecha o modal
- `role="dialog"` presente no DOM (inspetor)

- [ ] **Step 9: Commit final (se ajustes manuais necessários)**

Se algum ajuste fino de UI for feito durante a validação:

```bash
git add web/frontend/...
git commit -m "fix(frontend): ajustes de UI após validação manual"
```

---

## Self-Review

**Spec coverage:**
- ✅ Modal fullscreen sobre `inset-0` z-50 — Task G1, G2
- ✅ Drawer coexiste com botão ⛶ — Task F1, F2
- ✅ Backend: expandir Meta API com clicks/reach/video_3s — Task B3
- ✅ Backend: helper `_video_3s_views_from_row` com fallback — Task B2
- ✅ Backend: Google API com clicks/CTR — Task C2
- ✅ Backend: parser de novos placeholders — Task A3
- ✅ Backend: schemas Pydantic estendidos — Task A1
- ✅ Frontend: types MetaAd/GoogleAd estendidos — Task D1
- ✅ Frontend: hook useAdContext — Task D2
- ✅ Frontend: EvolucaoChart com mode — Task D3
- ✅ Frontend: 5 blocos atômicos compartilhados — Task E1-E5
- ✅ Frontend: FunilFadigaBlock com fallback "Apenas vídeo" / "indisponível neste período" — Task E5
- ✅ Frontend: estado `selectedXxxFullscreen` + wireup — Task G3
- ✅ Tests backend para o parser — Task A2-A3
- ✅ Tests backend para helper `_video_3s_views_from_row` — Task B1-B2
- ✅ Test e2e do fluxo — Task H1
- ✅ Validação manual — Task H2

**Type consistency:**
- `useAdContext` retorna `AdContext` com os campos referenciados em todos os blocos (`tier`, `barPct`, `cpm`, `avgCtr`, `avgFrequency`, `avgHookRate`, `roasVsAvg`, `shareInv`, `shareFat`, `avgRoas`, `maxRoas`) — consistente entre Task D2 e Task E1-E5.
- `MetaAd` e `GoogleAd` no TypeScript (Task D1) batem com schemas Python (Task A1).
- `EvolucaoChart` aceita `mode?: "drawer" | "fullscreen"` (Task D3) — usado consistentemente em Task F1, F2, G1, G2.

**Placeholder scan:**
- Task H1 step 1 menciona um TODO real (descobrir pattern de login) — necessário, não substituível por código fictício.
- Task C1 é uma task de leitura sem commit — declarado explicitamente.
- Não há "TBD", "implement later" ou "handle edge cases" deixados.

**Ordem alternativa sugerida:** Task F1 e F2 precisam dos states de fullscreen criados em Task G3 para que o `onExpand` funcione. **Ordem mais segura:** executar G1 → G2 → G3 (cria states + render) **antes** de F1 → F2. Mas como F1/F2 só dependem dos *imports* e do *state setter* existir no parent, e Task G3 cria justamente isso, fazer **G3 antes de F1** evita commits intermediários quebrados. Recomendar essa ordem ao executor.
