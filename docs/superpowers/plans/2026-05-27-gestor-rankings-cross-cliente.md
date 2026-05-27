# Gestor Rankings Cross-Cliente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar uma página dedicada `/gestor/rankings` que exibe dois rankings completos (Meta Ads criativos e Google Ads campanhas) agregados de todos os clientes da carteira, ordenados por ROAS do melhor ao pior.

**Architecture:** Extrai helpers de ROAS para `lib/roas-tier.ts` (compartilhado), cria a página de rankings que busca breakdown de todos os clientes em paralelo e agrega os resultados, e adiciona link na sidebar do gestor. Sem alterações de backend.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, framer-motion ^11

---

## Arquivo Map

| Ação | Arquivo | Responsabilidade |
|---|---|---|
| Criar | `web/frontend/lib/roas-tier.ts` | Helpers compartilhados: `fmtBRL`, `fmtRoas`, `roasTier`, `TIER_TEXT`, `TIER_BAR`, `sortByRoas` |
| Modificar | `web/frontend/components/PerformanceLeaderboard.tsx` | Importar helpers de `roas-tier.ts` em vez de definir localmente |
| Criar | `web/frontend/app/gestor/rankings/page.tsx` | Página completa de rankings cross-cliente |
| Modificar | `web/frontend/app/gestor/page.tsx` | Adicionar link "Rankings" na sidebar |

---

### Task 1: Criar `lib/roas-tier.ts`

**Files:**
- Create: `web/frontend/lib/roas-tier.ts`

- [ ] **Step 1: Criar o arquivo**

Crie `web/frontend/lib/roas-tier.ts` com o conteúdo abaixo:

```ts
export const fmtBRL = (v: number | null): string =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

export const fmtRoas = (v: number | null): string =>
  v == null ? "—" : `${v.toFixed(2).replace(".", ",")}×`;

export type RoasTier = "high" | "mid" | "low" | "none";

export function roasTier(v: number | null): RoasTier {
  if (v == null) return "none";
  if (v >= 3) return "high";
  if (v >= 1.5) return "mid";
  return "low";
}

export const TIER_TEXT: Record<RoasTier, string> = {
  high: "text-[var(--forest)]",
  mid: "text-[#f59e0b]",
  low: "text-[var(--crimson)]",
  none: "text-[var(--muted)]",
};

export const TIER_BAR: Record<RoasTier, string> = {
  high: "bg-[var(--forest)]",
  mid: "bg-[#f59e0b]",
  low: "bg-[var(--crimson)]",
  none: "bg-[var(--muted)]",
};

export function sortByRoas<T extends { roas: number | null }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    if (a.roas == null && b.roas == null) return 0;
    if (a.roas == null) return 1;
    if (b.roas == null) return -1;
    return b.roas - a.roas;
  });
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1
```

Esperado: sem output (zero erros).

- [ ] **Step 3: Commit**

```bash
git -C /Users/mac0267/Documents/auto-report-main add web/frontend/lib/roas-tier.ts
git -C /Users/mac0267/Documents/auto-report-main commit -m "feat(gestor): extrair helpers de ROAS para lib/roas-tier.ts"
```

---

### Task 2: Refatorar `PerformanceLeaderboard.tsx` para importar de `roas-tier.ts`

**Files:**
- Modify: `web/frontend/components/PerformanceLeaderboard.tsx`

- [ ] **Step 1: Substituir definições locais por importações**

No topo de `web/frontend/components/PerformanceLeaderboard.tsx`, substitua as definições locais de `fmtBRL`, `fmtRoas`, `RoasTier`, `roasTier`, `TIER_TEXT`, `TIER_BAR` e `sortByRoas` por uma única linha de import:

**Remover** (linhas 8–45 aproximadamente — as definições locais dessas funções/constantes/tipos):
```tsx
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
```

**Adicionar** logo após os imports existentes (após `import type { GoogleAd, MetaAd } from "@/lib/api-gestor";`):
```tsx
import {
  fmtBRL,
  fmtRoas,
  type RoasTier,
  roasTier,
  TIER_TEXT,
  TIER_BAR,
  sortByRoas,
} from "@/lib/roas-tier";
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1
```

Esperado: sem output. Se houver erros, verifique que todos os símbolos removidos estão sendo importados corretamente.

- [ ] **Step 3: Commit**

```bash
git -C /Users/mac0267/Documents/auto-report-main add web/frontend/components/PerformanceLeaderboard.tsx
git -C /Users/mac0267/Documents/auto-report-main commit -m "refactor(gestor): PerformanceLeaderboard importa helpers de roas-tier.ts"
```

---

### Task 3: Criar `app/gestor/rankings/page.tsx`

**Files:**
- Create: `web/frontend/app/gestor/rankings/page.tsx`

- [ ] **Step 1: Criar o arquivo da página completo**

Crie `web/frontend/app/gestor/rankings/page.tsx`:

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

import { gestorApi } from "@/lib/api-gestor";
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import { deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";
import {
  fmtBRL,
  fmtRoas,
  roasTier,
  sortByRoas,
  TIER_BAR,
  TIER_TEXT,
} from "@/lib/roas-tier";

type RankedMetaAd = MetaAd & { clienteNome: string; clienteSlug: string };
type RankedGoogleAd = GoogleAd & { clienteNome: string; clienteSlug: string };

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}

function rankColor(i: number): string {
  if (i === 0) return "text-[#d97706] font-bold";
  if (i === 1) return "text-[#6b7280] font-semibold";
  if (i === 2) return "text-[#92400e] font-semibold";
  return "text-[var(--muted)]";
}

export default function RankingsPage() {
  const [mes, setMes] = useState(mesUltimoFechado());
  const [loading, setLoading] = useState(true);
  const [metaAds, setMetaAds] = useState<RankedMetaAd[]>([]);
  const [googleAds, setGoogleAds] = useState<RankedGoogleAd[]>([]);

  const mesOpcoes = useMemo(
    () => Array.from({ length: 12 }, (_, i) => deslocarMes(mesUltimoFechado(), -i)),
    [],
  );

  useEffect(() => {
    setLoading(true);
    gestorApi
      .clientes()
      .then(({ items }) => {
        const ativos = items.filter((c) => c.ativo);
        return Promise.all(
          ativos.map((c) =>
            gestorApi
              .metricasBreakdown(c.slug, mes)
              .then((bd) => ({ cliente: c, bd }))
              .catch(() => ({ cliente: c, bd: null })),
          ),
        );
      })
      .then((results) => {
        const allMeta: RankedMetaAd[] = [];
        const allGoogle: RankedGoogleAd[] = [];
        for (const { cliente, bd } of results) {
          if (!bd) continue;
          for (const ad of bd.meta_ads) {
            allMeta.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug });
          }
          for (const ad of bd.google_ads) {
            allGoogle.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug });
          }
        }
        setMetaAds(sortByRoas(allMeta));
        setGoogleAds(sortByRoas(allGoogle));
      })
      .finally(() => setLoading(false));
  }, [mes]);

  const maxInvGoogle = useMemo(
    () => Math.max(...googleAds.map((c) => c.investimento ?? 0), 1),
    [googleAds],
  );

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <Link
        href="/gestor"
        className="mb-6 block text-xs text-[var(--muted)] transition hover:text-[var(--ink)]"
      >
        ← Seus clientes
      </Link>

      <div className="mb-8 flex items-baseline justify-between gap-4">
        <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
          Rankings
        </h1>
        <div className="flex items-center gap-2">
          <label htmlFor="mes-ref" className="text-xs text-[var(--muted)]">
            Mês:
          </label>
          <select
            id="mes-ref"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          >
            {mesOpcoes.map((m) => (
              <option key={m} value={m}>
                {mesLabel(m)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
          Carregando rankings…
        </p>
      ) : (
        <div className="flex flex-col gap-12">
          {/* Meta Ads */}
          <section>
            <p className="eyebrow mb-4 text-xs text-[var(--muted)]">
              Top criativos · Meta Ads · carteira
            </p>
            {metaAds.length === 0 ? (
              <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
                Nenhum dado disponível para este mês.
              </p>
            ) : (
              <div className="flex flex-col divide-y divide-[var(--rule-soft)] rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                {metaAds.map((ad, i) => {
                  const tier = roasTier(ad.roas);
                  return (
                    <Link
                      key={`${ad.clienteSlug}-${ad.nome}`}
                      href={`/gestor/${ad.clienteSlug}`}
                      className="grid grid-cols-[2rem_2rem_1fr_auto] items-center gap-3 px-4 py-3 transition hover:bg-[var(--paper-deep)]"
                    >
                      <span className={`font-mono-num text-xs ${rankColor(i)}`}>#{i + 1}</span>
                      {ad.imagem_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={ad.imagem_url}
                          alt={ad.nome}
                          className="h-5 w-7 rounded object-cover"
                        />
                      ) : (
                        <div className="h-5 w-7 rounded bg-gradient-to-br from-[var(--paper-deep)] to-[var(--paper-soft)]" />
                      )}
                      <div className="min-w-0">
                        <p className="truncate text-sm text-[var(--ink)]" title={ad.nome}>
                          {ad.nome}
                        </p>
                        <p className="text-[10px] text-[var(--muted)]">{ad.clienteNome}</p>
                      </div>
                      <div className="text-right">
                        <p className={`font-mono-num text-base font-semibold ${TIER_TEXT[tier]}`}>
                          {fmtRoas(ad.roas)}
                        </p>
                        <p className="font-mono-num text-[10px] text-[var(--muted)]">
                          {fmtBRL(ad.investimento)}
                        </p>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </section>

          {/* Google Ads */}
          <section>
            <p className="eyebrow mb-4 text-xs text-[var(--muted)]">
              Top campanhas · Google Ads · carteira
            </p>
            {googleAds.length === 0 ? (
              <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
                Nenhum dado disponível para este mês.
              </p>
            ) : (
              <div className="flex flex-col divide-y divide-[var(--rule-soft)] rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                {googleAds.map((c, i) => {
                  const tier = roasTier(c.roas);
                  const pct = (c.investimento ?? 0) / maxInvGoogle;
                  return (
                    <Link
                      key={`${c.clienteSlug}-${c.nome}`}
                      href={`/gestor/${c.clienteSlug}`}
                      className="grid grid-cols-[2rem_1fr_auto] items-center gap-4 px-4 py-3 transition hover:bg-[var(--paper-deep)]"
                    >
                      <span className={`font-mono-num text-xs ${rankColor(i)}`}>#{i + 1}</span>
                      <div className="min-w-0">
                        <p className="truncate text-sm text-[var(--ink)]" title={c.nome}>
                          {c.nome}
                        </p>
                        <p className="text-[10px] text-[var(--muted)]">{c.clienteNome}</p>
                        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--paper-deep)]">
                          <motion.div
                            className={`h-full origin-left ${TIER_BAR[tier]}`}
                            initial={{ scaleX: 0 }}
                            whileInView={{ scaleX: pct }}
                            viewport={{ once: true, margin: "-15%" }}
                            transition={{ duration: 0.8, delay: i * 0.04, ease: "easeOut" }}
                          />
                        </div>
                        <p className="font-mono-num mt-1 text-[10px] text-[var(--muted)]">
                          Invest: {fmtBRL(c.investimento)}
                        </p>
                      </div>
                      <p className={`font-mono-num text-base font-semibold ${TIER_TEXT[tier]}`}>
                        {fmtRoas(c.roas)}
                      </p>
                    </Link>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1
```

Esperado: sem output.

- [ ] **Step 3: Commit**

```bash
git -C /Users/mac0267/Documents/auto-report-main add web/frontend/app/gestor/rankings/page.tsx
git -C /Users/mac0267/Documents/auto-report-main commit -m "feat(gestor): página de rankings cross-cliente /gestor/rankings"
```

---

### Task 4: Adicionar link "Rankings" na sidebar do gestor

**Files:**
- Modify: `web/frontend/app/gestor/page.tsx`

A sidebar está no componente `Sidebar` (função `function Sidebar(...)`) dentro de `app/gestor/page.tsx`. O `<nav>` interno tem o `{NAV_ITEMS.map(...)}` loop. O link deve ser adicionado **após** o fechamento desse map e **antes** do `</nav>`.

- [ ] **Step 1: Adicionar o link na sidebar**

Localize o trecho exato dentro da função `Sidebar`:

```tsx
      </nav>
      <div className="border-t border-[var(--rule-soft)] px-4 py-4">
```

Substitua por:

```tsx
        <Link
          href="/gestor/rankings"
          className="mb-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]"
        >
          <span className="text-[10px] opacity-60">◈</span>
          Rankings
        </Link>
      </nav>
      <div className="border-t border-[var(--rule-soft)] px-4 py-4">
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit 2>&1
```

Esperado: sem output.

- [ ] **Step 3: Commit**

```bash
git -C /Users/mac0267/Documents/auto-report-main add web/frontend/app/gestor/page.tsx
git -C /Users/mac0267/Documents/auto-report-main commit -m "feat(gestor): link Rankings na sidebar"
```
