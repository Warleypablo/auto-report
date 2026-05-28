# Modal fullscreen do anúncio (Performance) — Design

**Status:** Spec aprovado, pronto para implementação
**Data:** 2026-05-28
**Origem:** brainstorming com usuário em 2026-05-28
**Página afetada:** `/gestor/performance`

---

## 1. Objetivo

Permitir análise aprofundada de um anúncio sem sair da página de performance. Hoje, clicar num card abre um drawer lateral de 380px (`MetaDrawer` / `GoogleDrawer`) com métricas básicas e gráfico de evolução de 6 meses. O usuário pediu uma "tela inteira" para aproveitar o espaço com novas métricas de **funil e fadiga** (CTR, Hook Rate, Frequency, Thumb Stop Ratio) — métricas hoje inexistentes no snapshot.

Resultado esperado: a partir do drawer atual, o usuário clica em um botão "⛶ expandir" no header e o modal fullscreen abre com layout amplo (grid de duas colunas), KPIs grandes, preview do criativo ampliado, e o novo bloco "Funil & Fadiga".

## 2. Escopo

**Dentro do escopo:**
- Expandir coleta Meta Ads (`core/categorias/*/campaign_facebook_gather.py`) para incluir `clicks`, `reach`, `video_p25_watched_actions` e gerar novos placeholders no `raw_dados`
- Atualizar `services/metricas.py::build_breakdown` para parsear e expor `ctr`, `hook_rate`, `frequency` no schema `MetaAd`
- Adicionar `ctr` ao schema `GoogleAd` (coletado em `campaign_google_gather.py`)
- Criar componentes `MetaAdFullscreen` e `GoogleAdFullscreen` (modais fullscreen)
- Criar bloco novo `FunilFadigaBlock` (CTR + Hook Rate + Frequency + comparação com média)
- Refatorar `MetaDrawer` / `GoogleDrawer` para consumir blocos atômicos compartilhados (`KpiHeader`, `MetricsRows`, `ContextBlock`, `EvolucaoChart`, `CriativoPreview`)
- Extrair cálculos pesados para hook compartilhado `useAdContext`
- Adicionar botão "⛶ expandir" no header dos drawers

**Fora do escopo:**
- Histórico das novas métricas (CTR/Hook/Frequency em 6 meses) — só o mês selecionado nesta fase, porque snapshots antigos não terão esses dados. Histórico fica para uma fase posterior, depois que a nova ETL acumular meses suficientes.
- Outros canais além de Meta/Google Ads (TikTok, LinkedIn, etc.)
- Comentários, reações, audiência demográfica do anúncio
- Compartilhamento por URL (modal não muda URL — é estado in-memory)

## 3. Decisões de design

| Decisão | Escolha | Motivo |
|---|---|---|
| Forma da expansão | Modal fullscreen (`inset-0`, z-50) | Mantém estado dos filtros e ranking por trás; não precisa rota dedicada |
| Drawer atual | Coexiste | Preview rápido (380px) continua valioso; fullscreen é para análise |
| Escopo da entrega | Backend + frontend em um único PR | Usuário quer ver tudo funcionando junto |
| Arquitetura | Dois shells (`MetaDrawer` e `MetaAdFullscreen`) + blocos atômicos compartilhados | Layouts são fundamentalmente diferentes (vertical denso vs. grid amplo); blocos atômicos eliminam a duplicação real |
| Stack do modal | `framer-motion` + `AnimatePresence` (mesmo do drawer) | Já é a stack do projeto |
| Ao abrir fullscreen | Drawer fecha automaticamente | Evita "stack" de modais; ao fechar fullscreen, drawer não reabre |

## 4. Fluxo do usuário

```
Lista de anúncios (página /gestor/performance)
   │
   ├── clica no card ─────────────▶ Drawer 380px (preview rápido, como hoje)
   │                                       │
   │                                       ├── clica em "⛶ expandir" ──▶ Modal fullscreen
   │                                       │    (drawer fecha)
   │                                       └── ESC ou X ─────────────────▶ fecha drawer
   │
   └── Modal fullscreen
         ├── ESC ou X ────────▶ fecha (drawer não reabre)
         └── → Ver dashboard ─▶ navega para /gestor/[slug]
```

## 5. Arquitetura

### 5.1 Hierarquia de componentes

Todos em `web/frontend/app/gestor/performance/page.tsx` por enquanto. Se o arquivo passar de ~1500 linhas, extrair `MetaAdFullscreen` e `GoogleAdFullscreen` para arquivos próprios.

```
page.tsx
├── MetaDrawer (existente, refatorado)              ← 380px, abre ao clicar no card
│   ├── DrawerHeader (com botão ⛶ expandir + X)
│   └── DrawerBody (versão compacta dos blocos)
│
├── MetaAdFullscreen (novo)                          ← modal inset-0
│   ├── FullscreenHeader (com X)
│   └── FullscreenBody (versão ampla dos blocos)
│
├── GoogleDrawer / GoogleAdFullscreen                ← análogos, sem FunilFadigaBlock
│
└── Blocos atômicos (compartilhados)
    ├── KpiHeader(ad, mode)                          ← ROAS + rank + barra de tier
    ├── MetricsRows(ad, mode)                        ← Fat/Inv/ROAS/Conv/…
    ├── ContextBlock(ad, ctx)                        ← ROAS vs média + share carteira
    ├── FunilFadigaBlock(ad, ctx)         (novo)     ← CTR + Hook + Frequency + diagnóstico
    ├── EvolucaoChart(history, mode)                 ← refatorado de EvolucaoTab
    └── CriativoPreview(ad, mode)                    ← reusa AdThumbnail com altura variável
```

### 5.2 Hook compartilhado `useAdContext`

Os cálculos pesados (`avgRoas`, `shareInv`, `shareFat`, `roasVsAvg`, `cpm`, `tier`, `barPct`) hoje estão duplicados em `MetaDrawer` e `GoogleDrawer`. Extrair para:

```ts
function useAdContext<T extends MetaAd | GoogleAd>(ad: T, allAds: T[]) {
  return useMemo(() => {
    const adsComRoas = allAds.filter(a => a.roas != null && a.roas > 0);
    const avgRoas = adsComRoas.length > 0
      ? adsComRoas.reduce((s, a) => s + (a.roas ?? 0), 0) / adsComRoas.length
      : null;
    const roasVsAvg = avgRoas && ad.roas ? ad.roas / avgRoas : null;
    const maxRoas = adsComRoas.length > 0
      ? Math.max(...adsComRoas.map(a => a.roas ?? 0))
      : 0;
    const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
    const totalInv = allAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
    const totalFat = allAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
    const shareInv = totalInv > 0 && ad.investimento ? (ad.investimento / totalInv) * 100 : null;
    const shareFat = totalFat > 0 && ad.faturamento ? (ad.faturamento / totalFat) * 100 : null;
    const cpm = ad.impressoes && ad.investimento && ad.impressoes > 0
      ? (ad.investimento / ad.impressoes) * 1000
      : null;
    const tier = roasTier(ad.roas);

    // novos: médias para comparativos do Funil
    const adsComCtr = allAds.filter(a => 'ctr' in a && a.ctr != null);
    const avgCtr = adsComCtr.length > 0
      ? adsComCtr.reduce((s, a) => s + ((a as any).ctr ?? 0), 0) / adsComCtr.length
      : null;
    // (análogo para avgHookRate e avgFrequency, só no caso de MetaAd)

    return { tier, avgRoas, roasVsAvg, maxRoas, barPct, shareInv, shareFat, cpm, avgCtr, /* … */ };
  }, [ad, allAds]);
}
```

### 5.3 Modo `mode: "drawer" | "fullscreen"` nos blocos atômicos

Cada bloco recebe `mode` e ajusta tipografia/spacing/altura, sem alterar a lógica:

| Bloco | Drawer (compacto) | Fullscreen (amplo) |
|---|---|---|
| `KpiHeader` | ROAS `text-lg` + barra | ROAS `text-5xl` + Fat/Inv/Conv em cards horizontais |
| `EvolucaoChart` | Altura 200px | Altura 320px + legenda lateral |
| `CriativoPreview` | 220px altura | 400px altura |
| `MetricsRows` | Lista vertical compacta | Mesma lista mas com mais padding e tipografia maior |
| `FunilFadigaBlock` | (não renderizado no drawer) | Card com 3 KPIs grandes + comparação |
| `ContextBlock` | Vertical (share inv / share fat empilhados) | Horizontal (lado a lado em 3 colunas) |

### 5.4 Estado no `page.tsx`

```ts
const [selectedMeta, setSelectedMeta] = useState<RankedMetaAd | null>(null);
const [selectedMetaFullscreen, setSelectedMetaFullscreen] = useState<RankedMetaAd | null>(null);
const [selectedGoogle, setSelectedGoogle] = useState<RankedGoogleAd | null>(null);
const [selectedGoogleFullscreen, setSelectedGoogleFullscreen] = useState<RankedGoogleAd | null>(null);
```

Handlers:
- `onCardClick(ad)` → `setSelectedMeta(ad)`
- `onExpand()` no drawer → `setSelectedMetaFullscreen(selectedMeta); setSelectedMeta(null);`
- `onCloseFullscreen()` → `setSelectedMetaFullscreen(null)` (drawer NÃO reabre)

### 5.5 Wrapper do modal fullscreen

Reusa o pattern do `DetailsDrawer` com `inset-0`:

```tsx
<AnimatePresence>
  {open && (
    <motion.div
      className="fixed inset-0 z-50 flex flex-col bg-[var(--paper)] overflow-y-auto"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="fs-title"
    >
      {/* header + body + footer */}
    </motion.div>
  )}
</AnimatePresence>
```

ESC fecha (mesma lógica do drawer). Sem backdrop — é fullscreen. Botão X grande no canto superior direito.

## 6. Backend

### 6.1 Coleta Meta Ads

Arquivos afetados:
- `core/categorias/lead_com_site/campaign_facebook_gather.py`
- `core/categorias/ecommerce/campaign_facebook_gather.py`
- `core/categorias/lead_sem_site/campaign_facebook_gather.py`

Mudança em `fields` da chamada `/insights`:

```python
"fields": (
    "ad_id,ad_name,spend,impressions,results,actions,conversions,"
    "clicks,reach,video_3_sec_watched_actions"
),
```

Cálculos derivados (no Python do gather, não no front). Adicionar helper `_video_3s_views_from_row(row)` no mesmo arquivo `campaign_facebook_gather.py`, que lê `video_3_sec_watched_actions` (lista de objetos `{action_type, value}`) e retorna a soma como `int`, ou `None` se a chave não existir:

```python
clicks = int(row.get("clicks") or 0)
reach = int(row.get("reach") or 0)
video_3s = _video_3s_views_from_row(row)  # None se não houver chave (anúncio estático)

ctr = round(clicks / impressions * 100, 2) if impressions > 0 else None
frequency = round(impressions / reach, 2) if reach > 0 else None
hook_rate = round(video_3s / impressions * 100, 2) if impressions > 0 and video_3s else None
```

**Nota sobre vídeo vs estático:** anúncios não-vídeo ficam com `hook_rate=None` (não `0`) — distinguir "não aplicável" de "métrica zero". `_video_3s_views_from_row` retorna `None` quando a chave `video_3_sec_watched_actions` está ausente (Meta omite a chave para anúncios sem componente de vídeo).

**Fallback se a app token não expõe `video_3_sec_watched_actions`:** tentar `actions[action_type=video_view]` — a Meta usa "video_view" como ação de 3-second video plays no breakdown clássico. Se nenhum dos dois estiver disponível, `hook_rate=None` para todos os anúncios e o frontend mostra "—".

### 6.2 Novos placeholders no `raw_dados`

```
{{ctr_adf1}}    {{ctr_adf2}}   …   {{ctr_adf20}}
{{freq_adf1}}   {{freq_adf2}}  …   {{freq_adf20}}
{{hook_adf1}}   {{hook_adf2}}  …   {{hook_adf20}}
```

E para Google Ads (em `campaign_google_gather.py`):

```
{{ctr_adg1}}    {{ctr_adg2}}   …   {{ctr_adg20}}
```

Formato: número PT-BR (ex: `"2,40"` para 2.4%, `"3,20"` para frequency 3.2). `None` vira `"-"` ou string vazia, seguindo a convenção atual.

### 6.3 Parser (`services/metricas.py::build_breakdown`)

Adicionar leitura das novas chaves, com fallback `None`:

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
    # novos:
    "ctr": _parse_br(rd.get(f"{{{{ctr_adf{i}}}}}")),
    "frequency": _parse_br(rd.get(f"{{{{freq_adf{i}}}}}")),
    "hook_rate": _parse_br(rd.get(f"{{{{hook_adf{i}}}}}")),
})
```

E para Google:

```python
google_ads.append({
    # … existentes
    "ctr": _parse_br(rd.get(f"{{{{ctr_adg{i}}}}}")),
})
```

### 6.4 Schemas

**Python (`web/backend/schemas/gestor.py`):**

```python
class MetaAd(BaseModel):
    # existentes
    nome: str
    investimento: float | None = None
    leads: int | None = None
    cpl: float | None = None
    conversoes: int | None = None
    faturamento: float | None = None
    roas: float | None = None
    cpa: float | None = None
    impressoes: int | None = None
    imagem_url: str | None = None
    # novos
    ctr: float | None = None
    frequency: float | None = None
    hook_rate: float | None = None

class GoogleAd(BaseModel):
    # existentes
    # novos
    ctr: float | None = None
```

**TypeScript (`web/frontend/lib/api-gestor.ts`):**

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
  // novos
  ctr: number | null;
  frequency: number | null;
  hook_rate: number | null;
};

export type GoogleAd = {
  // existentes
  ctr: number | null;
};
```

### 6.5 Compatibilidade com snapshots antigos

Snapshots já existentes não terão essas chaves. O parser devolve `None` e o frontend mostra `—` com texto sutil indicando indisponibilidade no período. Sem regenerar histórico.

## 7. Layout do `MetaAdFullscreen`

```
┌────────────────────────────────────────────────────────────────────┐
│ Loop AI                              turbo_partners            [X] │  ← header sticky
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ROAS 5.2× #1    Fat R$120k    Inv R$23k    Conv 84    CPM R$15   │  ← KpiHeader (mode=fs)
│  ▓▓▓▓▓▓▓▓▓░░░░ (barra de tier)                                    │
│                                                                    │
├──────────────────────────────┬─────────────────────────────────────┤
│                              │                                     │
│  ┌────────────────────────┐  │  ┌─── Funil & Fadiga ────────────┐ │
│  │                        │  │  │  CTR        Hook      Freq    │ │
│  │   Preview do criativo  │  │  │  2.4%       38%       3.2     │ │
│  │   (400px de altura)    │  │  │  ↑ vs 1.8%  ↑ vs 22%  ↑ alta  │ │
│  │                        │  │  └───────────────────────────────┘ │
│  └────────────────────────┘  │                                     │
│                              │  ┌─── Evolução (6m) ─────────────┐ │
│  Métricas detalhadas         │  │                               │ │
│   Faturamento  R$120k  ↑     │  │    [gráfico altura 320px]     │ │
│   Investimento R$23k         │  │                               │ │
│   ROAS         5.2×          │  │  Diagnóstico:                 │ │
│   CPL          R$15          │  │  ⚠ Frequency alta + ROAS      │ │
│   …                          │  │    caindo há 3 meses          │ │
│                              │  └───────────────────────────────┘ │
│                              │                                     │
├──────────────────────────────┴─────────────────────────────────────┤
│  Contexto · carteira                                               │
│   ROAS vs. média:  +47%        Share inv: 18%    Share fat: 22%   │
├────────────────────────────────────────────────────────────────────┤
│  → Ver dashboard do cliente                                        │  ← footer
└────────────────────────────────────────────────────────────────────┘
```

**Responsividade:** em telas < 768px, o grid de duas colunas vira coluna única (`md:grid-cols-2`).

**`GoogleAdFullscreen`:** mesma estrutura, mas `FunilFadigaBlock` exibe **só CTR** (sem Hook/Frequency). O bloco de evolução fica com mais largura.

## 8. Estados — vazio / erro / loading

| Cenário | Comportamento |
|---|---|
| Snapshot antigo (sem CTR/Hook/Freq) | `FunilFadigaBlock` mostra `—` em cada KPI + linha sutil: *"Métricas de funil indisponíveis neste período. Disponíveis a partir do próximo ciclo de coleta."* |
| Anúncio não-vídeo (sem Hook Rate) | KPI Hook Rate mostra `—` + tooltip: *"Apenas para anúncios em vídeo."* |
| `EvolucaoChart` falha em todos os meses | Fallback do drawer hoje: *"Sem histórico disponível para este criativo."* |
| `EvolucaoChart` ainda carregando | Skeleton (mesmo do drawer) — mas com altura 320px |
| Fullscreen aberto sem `ad` (estado inconsistente) | `if (!ad) return null;` no início do componente |

## 9. Acessibilidade

- `role="dialog"` + `aria-modal="true"` + `aria-labelledby="fs-title"` no wrapper
- Focus trap dentro do modal — usar `useFocusTrap` simples baseado em `useEffect` que captura `Tab`/`Shift+Tab`. Se já houver lib instalada, usar.
- ESC fecha (já no padrão atual)
- Botão X com `aria-label="Fechar"`
- O thumbnail tem `alt={ad.nome}`

## 10. Performance

- O fullscreen reusa o fetch do `EvolucaoChart` (mesma função `gestorApi.metricasBreakdown` para 6 meses). Não há request novo ao abrir fullscreen — se o usuário acabou de ver no drawer, o cache do React Query / state local já tem.
- O preview da imagem usa `AdThumbnail` existente (lazy load + fallback).
- Cálculos do `useAdContext` usam `useMemo` com dependência `[ad, allAds]` — recalcula só quando o mês muda.

## 11. Testes

### 11.1 Backend (`web/backend/tests/test_services_metricas.py`)

1. `build_breakdown` parseia `ctr_adf1`, `freq_adf1`, `hook_adf1` quando presentes → valores corretos
2. Retorna `None` para esses campos em snapshots antigos sem as chaves
3. `hook_rate=None` quando placeholder ausente; `ctr=0` quando explicitamente `"0,00"`
4. `GoogleAd.ctr` parseado de `{{ctr_adg1}}`

### 11.2 Backend — coletor (`tests/test_campaign_facebook_gather.py` se existir; senão pular)

Mock da Meta API com `clicks`, `reach`, `video_play_actions` → verifica que CTR/Frequency/Hook Rate são calculados corretamente e os placeholders certos são gerados.

### 11.3 Frontend e2e (`web/frontend/tests/e2e/`)

1. Clicar num card abre drawer; clicar em ⛶ no drawer abre fullscreen; drawer fecha; ESC no fullscreen volta para a lista (e drawer não reabre)
2. Fullscreen exibe KPIs do funil quando o snapshot tem dados; exibe "—" + texto explicativo quando não tem
3. `GoogleAdFullscreen` não exibe Hook Rate nem Frequency
4. Botão "Ver dashboard do cliente" navega para `/gestor/[slug]`

### 11.4 Unit (se houver setup de Vitest/Jest)

- `useAdContext` retorna `avgCtr` correto a partir de uma lista de ads
- `useAdContext` retorna `null` quando `allAds` está vazio ou nenhum ad tem CTR

## 12. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Meta API não retorna `video_3_sec_watched_actions` para a app token atual | Helper `_video_3s_views_from_row` tenta `actions[action_type=video_view]` como fallback; se nenhum existir, `hook_rate=None` para todos e o frontend mostra "—" sem quebrar |
| Snapshots antigos quebram o frontend ao receber `null` em CTR/Hook/Freq | Frontend já trata `null` em todos os outros campos; estender o mesmo padrão (`fmtX(value)` retorna `"—"` para null) |
| `useAdContext` se torna caro para listas grandes | `useMemo` com deps corretas; se necessário, mover cálculos para o `page.tsx` e passar via prop |
| Modal fullscreen quebra layout em mobile pequeno | Grid colapsa para 1 coluna em < 768px; testar manualmente |
| Coleta Meta com novos `fields` aumenta latência da chamada | Insights API já suporta múltiplos fields; medir e se necessário paralelizar |

## 13. Próximos passos pós-implementação

- Acumular meses com as novas métricas e habilitar histórico de CTR/Hook/Frequency no `EvolucaoChart` (fase 2)
- Avaliar adição de outros canais (TikTok Ads) com mesma estrutura
- Possível bloco "Texto do anúncio" (copy) se o coletor passar a expor `creative.body`
