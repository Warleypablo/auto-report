# Criativo — Evolução Temporal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar aba "Evolução" no drawer de criativos em `/gestor/performance` que mostra gráfico histórico de 6 meses (ROAS, CPM, Faturamento, Investimento) com badge automático de diagnóstico de fadiga.

**Architecture:** Tudo em um único arquivo (`performance/page.tsx`). Três adições: (1) tipos/helpers puros, (2) componente `EvolucaoTab` com fetch lazy dos 6 meses, (3) sistema de abas nos drawers existentes. Fetch dispara apenas quando a aba é selecionada pela primeira vez; meses sem dados do criativo viram `null` silenciosamente.

**Tech Stack:** Next.js 14, recharts v3.8.1 (ComposedChart — novo import), TypeScript, Tailwind CSS, `gestorApi.metricasBreakdown`.

---

## Estrutura de arquivos

- **Modificar:** `web/frontend/app/gestor/performance/page.tsx`
  - Novos imports recharts: `ComposedChart`, `Line`, `Bar`
  - Novo tipo: `HistoryPoint`
  - Novas constantes/funções: `MES_ABBR`, `detectFadiga`
  - Novos componentes: `EvolucaoTooltip`, `EvolucaoTab`
  - Modificar: `MetaDrawer` — adicionar prop `mes`, estado `drawerTab`, tab strip, render condicional
  - Modificar: `GoogleDrawer` — mesmo que `MetaDrawer`
  - Modificar: render de `MetaDrawer`/`GoogleDrawer` no corpo da página — passar `mes`

---

### Task 1: Imports + tipos + helpers puros

**Files:**
- Modify: `web/frontend/app/gestor/performance/page.tsx:18-28`

- [ ] **Step 1: Adicionar imports recharts**

Localizar o bloco de imports do recharts (linhas ~18-28):

```typescript
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Cell,
  ReferenceLine,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
```

Substituir por:

```typescript
import {
  ScatterChart,
  Scatter,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  ZAxis,
  Cell,
  ReferenceLine,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
```

- [ ] **Step 2: Adicionar tipo `HistoryPoint` + constante `MES_ABBR`**

Logo após a linha `type RankedGoogleAd = ...` (linha ~31), inserir:

```typescript
type HistoryPoint = {
  mes: string;
  mesLabel: string;
  roas: number | null;
  cpm: number | null;
  investimento: number | null;
  faturamento: number | null;
};

const MES_ABBR: Record<string, string> = {
  "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
  "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
  "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
};
```

- [ ] **Step 3: Adicionar função `detectFadiga`**

Logo após a constante `MES_ABBR` inserida no passo anterior:

```typescript
function detectFadiga(history: HistoryPoint[]): { label: string; kind: "fadiga" | "queda" | "saudavel" } | null {
  const withData = history.filter(p => p.roas !== null);
  if (withData.length < 2) return null;
  const prev = withData[withData.length - 2];
  const last = withData[withData.length - 1];
  if (
    prev.cpm !== null && last.cpm !== null &&
    last.cpm > prev.cpm * 1.15 &&
    prev.roas !== null && last.roas !== null &&
    last.roas < prev.roas * 0.85
  ) {
    return { label: "⚠️ Fadiga detectada", kind: "fadiga" };
  }
  if (prev.roas !== null && last.roas !== null && last.roas < prev.roas * 0.80) {
    return { label: "↘ Performance em queda", kind: "queda" };
  }
  return { label: "✓ Saudável", kind: "saudavel" };
}
```

- [ ] **Step 4: Verificar que TypeScript não tem erros**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | head -30
```

Esperado: sem erros nos novos tipos (pode haver erros pré-existentes no projeto — ok).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/app/gestor/performance/page.tsx
git commit -m "feat(performance): HistoryPoint type + MES_ABBR + detectFadiga helper"
```

---

### Task 2: Componentes `EvolucaoTooltip` e `EvolucaoTab`

**Files:**
- Modify: `web/frontend/app/gestor/performance/page.tsx` — inserir antes da linha `// ── Drawer helpers ─`  (linha ~293)

- [ ] **Step 1: Adicionar `EvolucaoTooltip`**

Inserir logo antes do comentário `// ── Drawer helpers ─`:

```typescript
// ── Evolução temporal ─────────────────────────────────────────────────────────

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
```

- [ ] **Step 2: Adicionar `EvolucaoTab`**

Logo após `EvolucaoTooltip`:

```typescript
function EvolucaoTab({
  clienteSlug,
  adNome,
  adType,
  mes,
}: {
  clienteSlug: string;
  adNome: string;
  adType: "meta" | "google";
  mes: string;
}) {
  const [history, setHistory] = useState<HistoryPoint[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const meses = Array.from({ length: 6 }, (_, i) => deslocarMes(mes, -i)).reverse();
    Promise.all(
      meses.map(m => gestorApi.metricasBreakdown(clienteSlug, m).catch(() => null))
    ).then(results => {
      const pts: HistoryPoint[] = meses.map((m, i) => {
        const bd = results[i];
        const ads = adType === "meta" ? (bd?.meta_ads ?? []) : (bd?.google_ads ?? []);
        const ad = ads.find(a => a.nome === adNome) ?? null;
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
    });
  }, [clienteSlug, adNome, adType, mes]);

  if (loading) {
    return (
      <div className="mt-6 space-y-3 px-1">
        <div className="h-[180px] animate-pulse rounded-xl bg-[var(--paper-deep)]" />
        <div className="flex gap-2">
          {[78, 55, 90, 45, 70, 60].map((w, i) => (
            <div key={i} className="animate-pulse rounded bg-[var(--paper-deep)]" style={{ height: 4, width: `${w}px`, animationDelay: `${i * 80}ms` }} />
          ))}
        </div>
      </div>
    );
  }

  const hasAnyData = history?.some(p => p.roas !== null) ?? false;

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
        <div className={`mb-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
          diagnosis.kind === "fadiga"
            ? "bg-amber-900/30 text-amber-300"
            : diagnosis.kind === "queda"
            ? "bg-red-900/30 text-red-300"
            : "bg-emerald-900/30 text-emerald-300"
        }`}>
          {diagnosis.label}
        </div>
      )}

      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={history!} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="mesLabel"
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
          />
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
          <Line
            yAxisId="ratio"
            type="monotone"
            dataKey="roas"
            stroke="#34d399"
            strokeWidth={2}
            dot={{ r: 3, fill: "#34d399", strokeWidth: 0 }}
            connectNulls={false}
          />
          <Line
            yAxisId="ratio"
            type="monotone"
            dataKey="cpm"
            stroke="#f59e0b"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={{ r: 2, fill: "#f59e0b", strokeWidth: 0 }}
            connectNulls={false}
          />
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

- [ ] **Step 3: Verificar TypeScript**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | grep "performance/page" | head -20
```

Esperado: sem novos erros em `performance/page.tsx`.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/gestor/performance/page.tsx
git commit -m "feat(performance): EvolucaoTooltip + EvolucaoTab com fetch de 6 meses"
```

---

### Task 3: Tab strip nos drawers + passar `mes`

**Files:**
- Modify: `web/frontend/app/gestor/performance/page.tsx:322-503` (MetaDrawer e GoogleDrawer)
- Modify: `web/frontend/app/gestor/performance/page.tsx:1045-1046` (render dos drawers na página)

- [ ] **Step 1: Modificar assinatura e adicionar estado em `MetaDrawer`**

Localizar linha ~322:
```typescript
function MetaDrawer({ ad, allAds, onClose }: { ad: RankedMetaAd; allAds: RankedMetaAd[]; onClose: () => void }) {
```

Substituir por:
```typescript
function MetaDrawer({ ad, allAds, onClose, mes }: { ad: RankedMetaAd; allAds: RankedMetaAd[]; onClose: () => void; mes: string }) {
```

Logo após o `useEffect` de Escape (linha ~327), adicionar:
```typescript
  const [drawerTab, setDrawerTab] = useState<"metricas" | "evolucao">("metricas");
```

- [ ] **Step 2: Adicionar tab strip em `MetaDrawer`**

Localizar o `<div className="flex items-start justify-between ...">` que é o header do MetaDrawer (linha ~345). Logo após o fechamento desse div (`</div>` que fecha o header com o `border-b`), inserir:

```tsx
        {/* Abas */}
        <div className="flex border-b border-[var(--rule-soft)] px-5">
          {(["metricas", "evolucao"] as const).map(t => (
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
```

- [ ] **Step 3: Envolver conteúdo de métricas e adicionar render condicional em `MetaDrawer`**

Localizar `<div className="flex-1 overflow-y-auto px-5 py-4">` dentro de `MetaDrawer` (linha ~353).

Logo dentro desse div, antes do conteúdo atual, adicionar a condição. O conteúdo original começa com `{ad.imagem_url && ...}`. Envolver o conteúdo existente e adicionar a aba de evolução:

O resultado final deve ficar assim (conteúdo original preservado dentro do `else`):

```tsx
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {drawerTab === "evolucao" ? (
            <EvolucaoTab
              clienteSlug={ad.clienteSlug}
              adNome={ad.nome}
              adType="meta"
              mes={mes}
            />
          ) : (
            <>
              {ad.imagem_url && (
                <div className="mb-5 overflow-hidden rounded-xl border border-[var(--rule-soft)]" style={{ height: 220 }}>
                  <AdThumbnail src={ad.imagem_url} alt={ad.nome} className="h-full w-full object-cover" />
                </div>
              )}

              {/* Rank + ROAS */}
              <div className="mb-5 flex items-center gap-3">
                {ad.rank < 3 && <span className="text-2xl">{MEDAL[ad.rank]}</span>}
                {ad.rank >= 3 && <span className="font-mono-num text-sm text-[var(--muted)]">#{ad.rank + 1}</span>}
                <div className="flex-1 min-w-0">
                  <div className="mb-1 flex items-center justify-between">
                    <span className={`font-mono-num text-lg font-semibold ${TIER_TEXT[tier]}`}>{fmtRoas(ad.roas)}</span>
                    <span className="text-[10px] text-[var(--muted)]">{adsComRoas.length} criativos</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
                    <div className={`h-1.5 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
                  </div>
                </div>
              </div>

              <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
              <div className="mb-5 rounded-xl border border-[var(--rule-soft)] px-4">
                <MetricRow label="Faturamento" value={fmtK(ad.faturamento)} highlight />
                <MetricRow label="Investimento" value={fmtK(ad.investimento)} />
                <MetricRow label="ROAS" value={fmtRoas(ad.roas)} highlight />
                {ad.conversoes != null && <MetricRow label="Conversões" value={String(ad.conversoes)} />}
                {ad.leads != null && <MetricRow label="Leads" value={String(ad.leads)} />}
                {ad.cpa != null && <MetricRow label="CPA" value={fmtK(ad.cpa)} />}
                {ad.cpl != null && <MetricRow label="CPL" value={fmtK(ad.cpl)} />}
                {ad.impressoes != null && <MetricRow label="Impressões" value={ad.impressoes.toLocaleString("pt-BR")} />}
                {cpm != null && <MetricRow label="CPM" value={fmtK(cpm)} />}
              </div>

              <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Contexto · carteira</p>

              {roasVsAvg != null && (
                <div className="mb-4 rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3">
                  <p className="text-xs text-[var(--muted)]">ROAS vs. média da carteira</p>
                  <p className={`mt-1 font-mono-num text-2xl font-semibold ${roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                    {roasVsAvg >= 1 ? "+" : ""}{((roasVsAvg - 1) * 100).toFixed(0)}%
                  </p>
                  <p className="mt-0.5 text-[10px] text-[var(--muted)]">Média: {avgRoas ? fmtRoas(avgRoas) : "—"}</p>
                </div>
              )}

              {(shareInv != null || shareFat != null) && (
                <div className="rounded-xl border border-[var(--rule-soft)] px-4 py-3">
                  {shareInv != null && <ContextBar label="Share de investimento" pct={shareInv} />}
                  {shareFat != null && <ContextBar label="Share de faturamento" pct={shareFat} />}
                </div>
              )}
            </>
          )}
        </div>
```

- [ ] **Step 4: Modificar assinatura e adicionar estado em `GoogleDrawer`**

Localizar linha ~418:
```typescript
function GoogleDrawer({ ad, allAds, onClose }: { ad: RankedGoogleAd; allAds: RankedGoogleAd[]; onClose: () => void }) {
```

Substituir por:
```typescript
function GoogleDrawer({ ad, allAds, onClose, mes }: { ad: RankedGoogleAd; allAds: RankedGoogleAd[]; onClose: () => void; mes: string }) {
```

Logo após o `useEffect` de Escape, adicionar:
```typescript
  const [drawerTab, setDrawerTab] = useState<"metricas" | "evolucao">("metricas");
```

- [ ] **Step 5: Adicionar tab strip em `GoogleDrawer`**

Exatamente como no Step 2 para `MetaDrawer` — após o header com `border-b`:

```tsx
        {/* Abas */}
        <div className="flex border-b border-[var(--rule-soft)] px-5">
          {(["metricas", "evolucao"] as const).map(t => (
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
```

- [ ] **Step 6: Envolver conteúdo de métricas com condicional em `GoogleDrawer`**

Mesmo padrão do Step 3. Localizar `<div className="flex-1 overflow-y-auto px-5 py-4">` em `GoogleDrawer` (~linha 449) e envolver o conteúdo com:

```tsx
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {drawerTab === "evolucao" ? (
            <EvolucaoTab
              clienteSlug={ad.clienteSlug}
              adNome={ad.nome}
              adType="google"
              mes={mes}
            />
          ) : (
            <>
              {/* conteúdo original do GoogleDrawer preservado */}
              <div className="mb-5 flex items-center gap-3">
                {ad.rank < 3 && <span className="text-2xl">{MEDAL[ad.rank]}</span>}
                {ad.rank >= 3 && <span className="font-mono-num text-sm text-[var(--muted)]">#{ad.rank + 1}</span>}
                <div className="flex-1 min-w-0">
                  <div className="mb-1 flex items-center justify-between">
                    <span className={`font-mono-num text-lg font-semibold ${TIER_TEXT[tier]}`}>{fmtRoas(ad.roas)}</span>
                    <span className="text-[10px] text-[var(--muted)]">{adsComRoas.length} campanhas</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
                    <div className={`h-1.5 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
                  </div>
                </div>
              </div>

              <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
              <div className="mb-5 rounded-xl border border-[var(--rule-soft)] px-4">
                <MetricRow label="Faturamento" value={fmtK(ad.faturamento)} highlight />
                <MetricRow label="Investimento" value={fmtK(ad.investimento)} />
                <MetricRow label="ROAS" value={fmtRoas(ad.roas)} highlight />
                {ad.conversoes != null && <MetricRow label="Conversões" value={String(ad.conversoes)} />}
                {ad.cpa != null && <MetricRow label="CPA" value={fmtK(ad.cpa)} />}
                {ad.impressoes != null && <MetricRow label="Impressões" value={ad.impressoes.toLocaleString("pt-BR")} />}
                {cpm != null && <MetricRow label="CPM" value={fmtK(cpm)} />}
              </div>

              <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Contexto · carteira</p>

              {roasVsAvg != null && (
                <div className="mb-4 rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3">
                  <p className="text-xs text-[var(--muted)]">ROAS vs. média da carteira</p>
                  <p className={`mt-1 font-mono-num text-2xl font-semibold ${roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                    {roasVsAvg >= 1 ? "+" : ""}{((roasVsAvg - 1) * 100).toFixed(0)}%
                  </p>
                  <p className="mt-0.5 text-[10px] text-[var(--muted)]">Média: {avgRoas ? fmtRoas(avgRoas) : "—"}</p>
                </div>
              )}

              {(shareInv != null || shareFat != null) && (
                <div className="rounded-xl border border-[var(--rule-soft)] px-4 py-3">
                  {shareInv != null && <ContextBar label="Share de investimento" pct={shareInv} />}
                  {shareFat != null && <ContextBar label="Share de faturamento" pct={shareFat} />}
                </div>
              )}
            </>
          )}
        </div>
```

- [ ] **Step 7: Passar `mes` nos renders dos drawers na página principal**

Localizar linhas ~1045-1046 do arquivo:

```tsx
      {selectedMeta && <MetaDrawer ad={selectedMeta} allAds={metaAds} onClose={() => setSelectedMeta(null)} />}
      {selectedGoogle && <GoogleDrawer ad={selectedGoogle} allAds={googleAds} onClose={() => setSelectedGoogle(null)} />}
```

Substituir por:

```tsx
      {selectedMeta && <MetaDrawer ad={selectedMeta} allAds={metaAds} onClose={() => setSelectedMeta(null)} mes={mes} />}
      {selectedGoogle && <GoogleDrawer ad={selectedGoogle} allAds={googleAds} onClose={() => setSelectedGoogle(null)} mes={mes} />}
```

- [ ] **Step 8: Verificar TypeScript sem erros**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | grep "performance/page" | head -20
```

Esperado: sem erros em `performance/page.tsx`.

- [ ] **Step 9: Testar no browser**

Com o dev server rodando (`npm run dev` em `web/frontend`), navegar para `http://localhost:3000/gestor/performance`. Verificar:

1. Clicar num criativo na tabela → drawer abre na aba "Métricas" com conteúdo normal
2. Clicar na aba "Evolução" → spinner animado aparece brevemente
3. Após carregamento: gráfico ComposedChart com barras (faturamento/investimento) e linhas (ROAS verde / CPM âmbar tracejado)
4. Badge de diagnóstico aparece acima do gráfico
5. Hover nos pontos do gráfico → tooltip com 4 métricas
6. Clicar em "Métricas" → volta ao conteúdo original sem perda de dados
7. Repetir com um criativo Google Ads

- [ ] **Step 10: Commit final**

```bash
git add web/frontend/app/gestor/performance/page.tsx
git commit -m "feat(performance): aba Evolução no drawer com histórico de 6 meses e diagnóstico de fadiga"
```
