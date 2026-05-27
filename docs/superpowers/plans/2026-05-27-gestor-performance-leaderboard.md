# Gestor Performance Leaderboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir as tabelas simples de campanhas no painel do gestor por um leaderboard cinemático: cards 16:9 com imagem para Meta Ads (top 3) e lista ranqueada com barras coloridas para Google Ads, com ROAS colorido por tier.

**Architecture:** Um único novo componente `PerformanceLeaderboard` com dois sub-componentes internos (`MetaLeaderboard`, `GoogleLeaderboard`). A seção "Campanhas" em `/gestor/[slug]/page.tsx` é substituída por esse componente; os estados `verTodosMeta`/`verTodosGoogle` migram para dentro do componente. Nenhuma alteração de backend.

**Tech Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, framer-motion ^11

---

## Arquivo Map

| Ação | Arquivo |
|---|---|
| Criar | `web/frontend/components/PerformanceLeaderboard.tsx` |
| Modificar | `web/frontend/app/gestor/[slug]/page.tsx` |

---

### Task 1: Criar o componente PerformanceLeaderboard

**Files:**
- Create: `web/frontend/components/PerformanceLeaderboard.tsx`

- [ ] **Step 1: Criar o arquivo com helpers, MetaLeaderboard e GoogleLeaderboard**

Crie `web/frontend/components/PerformanceLeaderboard.tsx` com o conteúdo completo abaixo:

```tsx
"use client";

import { motion } from "framer-motion";
import { useState } from "react";

import type { GoogleAd, MetaAd } from "@/lib/api-gestor";

const fmtBRL = (v: number | null) =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const fmtRoas = (v: number | null) =>
  v == null ? "—" : `${v.toFixed(2).replace(".", ",")}×`;

type RoasTier = "high" | "mid" | "low" | "none";

function roasTier(v: number | null): RoasTier {
  if (v == null) return "none";
  if (v >= 3) return "high";
  if (v >= 1.5) return "mid";
  return "low";
}

const TIER_TEXT: Record<RoasTier, string> = {
  high: "text-[var(--forest)]",
  mid: "text-[#f59e0b]",
  low: "text-[var(--crimson)]",
  none: "text-[var(--muted)]",
};

const TIER_BAR: Record<RoasTier, string> = {
  high: "bg-[var(--forest)]",
  mid: "bg-[#f59e0b]",
  low: "bg-[var(--crimson)]",
  none: "bg-[var(--muted)]",
};

function sortByRoas<T extends { roas: number | null }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    if (a.roas == null && b.roas == null) return 0;
    if (a.roas == null) return 1;
    if (b.roas == null) return -1;
    return b.roas - a.roas;
  });
}

function MetaLeaderboard({ ads }: { ads: MetaAd[] }) {
  const [showAll, setShowAll] = useState(false);
  const sorted = sortByRoas(ads);
  const top3 = sorted.slice(0, 3);
  const rest = sorted.slice(3);

  if (ads.length === 0) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Sem criativos detalhados neste mês.
      </p>
    );
  }

  return (
    <div>
      <div className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 md:grid md:grid-cols-3 md:overflow-visible md:pb-0">
        {top3.map((ad, i) => {
          const tier = roasTier(ad.roas);
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              whileInView={{ opacity: 1, y: 0, scale: 1 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.5, delay: i * 0.08, ease: [0.2, 0.7, 0.2, 1] }}
              whileHover={{ scale: 1.02 }}
              className="group relative aspect-video min-w-[85%] snap-start overflow-hidden rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-deep)] md:min-w-0"
            >
              {ad.imagem_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={ad.imagem_url}
                  alt={ad.nome}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
              ) : (
                <div className="h-full w-full bg-gradient-to-br from-[var(--paper-deep)] to-[var(--paper-soft)]" />
              )}

              <div className="absolute left-3 top-3 rounded-sm bg-black/55 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-white font-semibold">
                #{i + 1}
              </div>

              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/50 to-transparent p-4">
                <p className="line-clamp-1 text-[11px] text-white/90" title={ad.nome}>
                  {ad.nome}
                </p>
                <div className="mt-1 flex items-baseline justify-between">
                  <span className={`font-mono-num text-lg font-semibold ${TIER_TEXT[tier]}`}>
                    {fmtRoas(ad.roas)}
                  </span>
                  <span className="font-mono-num text-[11px] text-white/60">
                    {fmtBRL(ad.investimento)}
                  </span>
                </div>
                <p className="font-mono-num mt-0.5 text-[10px] text-white/50">
                  {ad.leads != null
                    ? `${ad.leads.toLocaleString("pt-BR")} leads`
                    : ad.conversoes != null
                    ? `${ad.conversoes.toLocaleString("pt-BR")} conv.`
                    : ""}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>

      {rest.length > 0 && (
        <div className="mt-3">
          {showAll && (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--rule-soft)]">
                  <th className="py-1.5 pr-3 text-left font-medium text-[var(--muted)]">#</th>
                  <th className="py-1.5 pr-3 text-left font-medium text-[var(--muted)]">Anúncio</th>
                  <th className="py-1.5 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
                  <th className="py-1.5 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
                  <th className="py-1.5 text-right font-medium text-[var(--muted)]">Leads / Conv.</th>
                </tr>
              </thead>
              <tbody>
                {rest.map((ad, i) => {
                  const tier = roasTier(ad.roas);
                  return (
                    <tr
                      key={i}
                      className="border-b border-[var(--rule-soft)]/40 hover:bg-[var(--paper-soft)]"
                    >
                      <td className="py-2 pr-3 text-[var(--muted)]">{i + 4}</td>
                      <td className="py-2 pr-3 max-w-[200px]" title={ad.nome}>
                        <span className="block truncate text-[var(--ink)]">{ad.nome}</span>
                      </td>
                      <td
                        className={`py-2 pr-3 text-right font-mono-num font-semibold ${TIER_TEXT[tier]}`}
                      >
                        {fmtRoas(ad.roas)}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                        {fmtBRL(ad.investimento)}
                      </td>
                      <td className="py-2 text-right font-mono-num text-[var(--ink)]">
                        {ad.leads != null
                          ? ad.leads.toLocaleString("pt-BR")
                          : ad.conversoes != null
                          ? ad.conversoes.toLocaleString("pt-BR")
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="mt-2 text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
          >
            {showAll ? "Mostrar só top 3" : `Ver todos os ${ads.length} →`}
          </button>
        </div>
      )}
    </div>
  );
}

function GoogleLeaderboard({ ads }: { ads: GoogleAd[] }) {
  const [showAll, setShowAll] = useState(false);
  const INITIAL_LIMIT = 5;
  const sorted = sortByRoas(ads);
  const visible = showAll ? sorted : sorted.slice(0, INITIAL_LIMIT);
  const maxInv = Math.max(...sorted.map((c) => c.investimento ?? 0), 1);

  if (ads.length === 0) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Sem campanhas detalhadas neste mês.
      </p>
    );
  }

  return (
    <div className="flex flex-col divide-y divide-[var(--rule-soft)] rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
      {visible.map((c, i) => {
        const tier = roasTier(c.roas);
        const pct = (c.investimento ?? 0) / maxInv;
        return (
          <div
            key={i}
            className="grid grid-cols-[2rem_1fr_auto] items-center gap-4 px-4 py-3"
          >
            <span className="font-mono-num text-xs text-[var(--muted)]">#{i + 1}</span>
            <div className="min-w-0">
              <p className="truncate text-sm text-[var(--ink)]" title={c.nome}>
                {c.nome}
              </p>
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--paper-deep)]">
                <motion.div
                  className={`h-full origin-left ${TIER_BAR[tier]}`}
                  initial={{ scaleX: 0 }}
                  whileInView={{ scaleX: pct }}
                  viewport={{ once: true, margin: "-15%" }}
                  transition={{ duration: 0.8, delay: i * 0.06, ease: "easeOut" }}
                />
              </div>
              <p className="font-mono-num mt-1 text-[10px] text-[var(--muted)]">
                Invest: {fmtBRL(c.investimento)}
              </p>
            </div>
            <p className={`font-mono-num text-base font-semibold ${TIER_TEXT[tier]}`}>
              {fmtRoas(c.roas)}
            </p>
          </div>
        );
      })}

      {ads.length > INITIAL_LIMIT && (
        <div className="px-4 py-2">
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
          >
            {showAll ? "Mostrar só top 5" : `Ver todas as ${ads.length} →`}
          </button>
        </div>
      )}
    </div>
  );
}

type Props = {
  metaAds: MetaAd[];
  googleAds: GoogleAd[];
  loading: boolean;
  mes: string;
};

export default function PerformanceLeaderboard({ metaAds, googleAds, loading, mes }: Props) {
  if (loading) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Carregando…
      </p>
    );
  }

  if (metaAds.length === 0 && googleAds.length === 0) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Sem dados granulares para este mês.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {metaAds.length > 0 && (
        <div>
          <p className="eyebrow mb-3 text-[10px] font-medium text-[var(--muted)]">
            Meta Ads — top criativos
          </p>
          <MetaLeaderboard ads={metaAds} />
        </div>
      )}
      {googleAds.length > 0 && (
        <div>
          <p className="eyebrow mb-3 text-[10px] font-medium text-[var(--muted)]">
            Google Ads — campanhas
          </p>
          <GoogleLeaderboard ads={googleAds} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verificar que não há erros de TypeScript no novo arquivo**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | grep PerformanceLeaderboard
```

Esperado: sem output (sem erros neste arquivo).

- [ ] **Step 3: Commit do componente**

```bash
git add web/frontend/components/PerformanceLeaderboard.tsx
git commit -m "feat(gestor): componente PerformanceLeaderboard (leaderboard cinemático)"
```

---

### Task 2: Integrar PerformanceLeaderboard na página do gestor

**Files:**
- Modify: `web/frontend/app/gestor/[slug]/page.tsx`

- [ ] **Step 1: Adicionar o import do novo componente**

No topo de `web/frontend/app/gestor/[slug]/page.tsx`, adicione a linha de import após os imports existentes de componentes:

```tsx
import PerformanceLeaderboard from "@/components/PerformanceLeaderboard";
```

- [ ] **Step 2: Remover os estados verTodosMeta e verTodosGoogle**

Localize e remova as duas linhas:

```tsx
const [verTodosMeta, setVerTodosMeta] = useState(false);
const [verTodosGoogle, setVerTodosGoogle] = useState(false);
```

- [ ] **Step 3: Substituir a seção "Breakdown de campanhas" pelo novo componente**

Localize o bloco inteiro da seção de campanhas (de `{/* Breakdown de campanhas */}` até o `</section>` correspondente) e substitua por:

```tsx
{/* Breakdown de campanhas */}
<section className="mb-8">
  <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Campanhas · {mesLabel(mes)}</p>
  <PerformanceLeaderboard
    metaAds={metaAds}
    googleAds={googleAds}
    loading={loadingDetail}
    mes={mesLabel(mes)}
  />
</section>
```

- [ ] **Step 4: Verificar que não há erros de TypeScript**

```bash
cd web/frontend && npx tsc --noEmit 2>&1
```

Esperado: sem output (zero erros). Se houver erros de `verTodosMeta`/`verTodosGoogle` ainda referenciados em algum lugar, remova os usos remanescentes.

- [ ] **Step 5: Commit da integração**

```bash
git add web/frontend/app/gestor/[slug]/page.tsx
git commit -m "feat(gestor): integrar PerformanceLeaderboard na seção de campanhas"
```

---

### Task 3: Verificação visual

**Files:** nenhum arquivo modificado nesta task

- [ ] **Step 1: Iniciar o servidor de desenvolvimento**

```bash
cd web/frontend && npm run dev
```

Aguarde a mensagem `Ready in Xs` na saída.

- [ ] **Step 2: Acessar o painel do gestor**

Abrir `http://localhost:3000/gestor/login` no browser, fazer login e navegar até um cliente que tenha dados de Meta Ads e Google Ads no mês mais recente.

- [ ] **Step 3: Verificar os casos felizes**

Confirme que todos os itens abaixo estão corretos:

1. **Cards Meta Ads**: top 3 criativos aparecem como cards 16:9 com badge `#1`, `#2`, `#3`
2. **Imagem**: se o criativo tem `imagem_url`, a imagem é exibida; sem imagem aparece gradiente escuro
3. **ROAS nos cards**: número grande na cor correta — verde se ≥ 3×, âmbar se 1.5–3×, vermelho se < 1.5×
4. **Toggle Meta**: se há mais de 3 criativos, o botão "Ver todos os N" aparece e expande a tabela
5. **Google Ads bars**: campanhas em lista ranqueada com `#1`, barra de investimento proporcional e ROAS colorido
6. **Barra de animação**: as barras do Google animam ao entrar no viewport (scaleX de 0 → valor)
7. **Toggle Google**: se há mais de 5 campanhas, o botão "Ver todas as N" aparece
8. **Estado loading**: ao trocar de mês, o componente exibe "Carregando…" enquanto o breakdown carrega
9. **Estado vazio**: mês sem dados exibe "Sem dados granulares para este mês."

- [ ] **Step 4: Verificar responsividade mobile**

Abrir DevTools → dispositivo mobile (ex: iPhone 12). Confirmar que os cards Meta aparecem em scroll horizontal com snap.

- [ ] **Step 5: Commit final se algum ajuste menor foi necessário**

Se precisou de algum ajuste cosmético durante a verificação visual:

```bash
git add web/frontend/components/PerformanceLeaderboard.tsx web/frontend/app/gestor/[slug]/page.tsx
git commit -m "fix(gestor): ajustes visuais do PerformanceLeaderboard"
```

Se não precisou de ajuste, não crie commit vazio.
