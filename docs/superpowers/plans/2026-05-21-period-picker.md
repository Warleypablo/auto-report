# PeriodPicker — Seletor de Intervalo de Meses — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o `MonthSelector` (pills de mês) por um `PeriodPicker` com popover de calendário de meses, seleção de range (início → fim), filtros rápidos e suporte completo no backend.

**Architecture:** O frontend passa `?de=YYYY-MM&ate=YYYY-MM` na URL; o backend aceita `de`/`ate` e filtra snapshots onde `periodo_inicio` está dentro do range. A URL `?mes=YYYY-MM` continua funcionando como compat layer (equivalente a `de=mes&ate=mes`). O componente `PeriodPicker` é client-only, sem biblioteca externa — popover com `absolute`, click-outside via `useEffect`.

**Tech Stack:** Next.js 14 App Router, Tailwind CSS (design tokens CSS vars), FastAPI + SQLAlchemy, pytest

---

## Mapa de Arquivos

| Arquivo | Operação | Responsabilidade |
|---------|----------|-----------------|
| `web/frontend/lib/mes-utils.ts` | Modify | Adicionar `labelRange`, `deslocarMes`, `mesUltimoFechado` |
| `web/frontend/lib/api-internal.ts` | Modify | `listAllClientes(de, ate)` com query `?de=&ate=` |
| `web/frontend/components/PeriodPicker.tsx` | Create | Novo componente: trigger + popover + grid + quick filters |
| `web/frontend/app/lista/page.tsx` | Modify | Ler `de`/`ate`, compat `mes`, default 3M, passar para API, atualizar header |
| `web/backend/api/internal.py` | Modify | Endpoint `/clientes` aceita `de`/`ate`, compat `mes` |
| `web/backend/tests/test_internal_clientes_range.py` | Create | Testes para a lógica de range no backend |

---

## Task 1: Backend — suporte a range `de`/`ate` no endpoint `/clientes`

**Files:**
- Modify: `web/backend/api/internal.py`
- Create: `web/backend/tests/test_internal_clientes_range.py`

- [ ] **Step 1: Escrever o teste antes de alterar o código**

Criar `web/backend/tests/test_internal_clientes_range.py`:

```python
import calendar
from datetime import date
import pytest


def _primeira_data(mes: str) -> date:
    """Converte 'YYYY-MM' na data do primeiro dia do mês."""
    y, m = int(mes[:4]), int(mes[5:7])
    return date(y, m, 1)


def _ultima_data(mes: str) -> date:
    """Converte 'YYYY-MM' na data do último dia do mês."""
    y, m = int(mes[:4]), int(mes[5:7])
    return date(y, m, calendar.monthrange(y, m)[1])


def test_primeira_data():
    assert _primeira_data("2026-02") == date(2026, 2, 1)
    assert _primeira_data("2025-12") == date(2025, 12, 1)


def test_ultima_data():
    assert _ultima_data("2026-02") == date(2026, 2, 28)
    assert _ultima_data("2024-02") == date(2024, 2, 29)  # ano bissexto
    assert _ultima_data("2026-04") == date(2026, 4, 30)


def test_range_de_ate_ordenado():
    """Se de > ate, a função deve inverter automaticamente."""
    de_mes = "2026-04"
    ate_mes = "2026-02"
    de, ate = sorted([de_mes, ate_mes])
    assert de == "2026-02"
    assert ate == "2026-04"


def test_range_mesmo_mes():
    """Range de um único mês deve ser equivalente ao antigo ?mes=."""
    de_date = _primeira_data("2026-04")
    ate_date = _ultima_data("2026-04")
    # Simula o período que o backend calcularia
    assert de_date == date(2026, 4, 1)
    assert ate_date == date(2026, 4, 30)
```

- [ ] **Step 2: Rodar os testes para confirmar que passam (são testes de lógica pura)**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend
.venv/bin/python -m pytest tests/test_internal_clientes_range.py -v
```

Esperado: 4 testes PASS.

- [ ] **Step 3: Atualizar o endpoint `/clientes` em `internal.py`**

Substituir a função `list_clientes` completa (linhas 113–188 do arquivo atual):

```python
@router.get(
    "/clientes",
    response_model=ClientesListResponse,
    dependencies=[Depends(_require_token)],
)
def list_clientes(
    session: Session = Depends(get_session),
    mes: str | None = Query(default=None, description="Compat: equivale a de=mes&ate=mes"),
    de: str | None = Query(default=None, description="Início do range YYYY-MM"),
    ate: str | None = Query(default=None, description="Fim do range YYYY-MM"),
) -> ClientesListResponse:
    """Lista todos os clientes + snapshot mais recente dentro do range pedido.

    Precedência: de/ate > mes > sem parâmetro (snapshot mais recente de cada cliente).
    """
    # Normalizar: mes é compat layer para de=mes&ate=mes
    if de is None and ate is None and mes is not None:
        de = mes
        ate = mes

    # Se de > ate, inverter
    if de and ate and de > ate:
        de, ate = ate, de

    periodo_inicio_alvo: date | None = None
    periodo_fim_alvo: date | None = None

    if de and ate:
        de_date, _ = _mes_para_periodo(de)
        ate_date, _ = _mes_para_periodo(ate)
        periodo_inicio_alvo = de_date
        _, periodo_fim_alvo = _mes_para_periodo(ate)
        snap_filter = and_(
            Snapshot.periodo_inicio >= de_date,
            Snapshot.periodo_inicio <= ate_date,
        )
        sub = (
            select(Snapshot.cliente_id, Snapshot.id.label("snap_id"))
            .where(snap_filter)
            .distinct(Snapshot.cliente_id)
            .order_by(Snapshot.cliente_id, Snapshot.data_coleta.desc())
        ).subquery()
    else:
        sub = (
            select(Snapshot.cliente_id, Snapshot.id.label("snap_id"))
            .distinct(Snapshot.cliente_id)
            .order_by(Snapshot.cliente_id, Snapshot.periodo_fim.desc(), Snapshot.data_coleta.desc())
        ).subquery()

    stmt = (
        select(Cliente, Snapshot)
        .join(sub, sub.c.cliente_id == Cliente.id, isouter=True)
        .join(Snapshot, Snapshot.id == sub.c.snap_id, isouter=True)
        .order_by(Cliente.nome.asc())
    )

    items: list[ClienteListItem] = []
    com_snapshot = 0
    for cliente, snap in session.execute(stmt).all():
        if snap is not None:
            com_snapshot += 1
        items.append(
            ClienteListItem(
                slug=cliente.slug,
                nome=cliente.nome,
                categoria=cliente.categoria.value,
                setor=cliente.setor,
                porte=cliente.porte,
                publicar_vitrine=cliente.publicar_vitrine,
                destaque=cliente.destaque,
                periodo_inicio=snap.periodo_inicio if snap else None,
                periodo_fim=snap.periodo_fim if snap else None,
                data_coleta=snap.data_coleta if snap else None,
                faturamento=snap.faturamento if snap else None,
                investimento=snap.investimento if snap else None,
                roas=snap.roas if snap else None,
                cpa=snap.cpa if snap else None,
                leads=snap.leads if snap else None,
                vendas=snap.vendas if snap else None,
                faturamento_var_pct=snap.faturamento_var_pct if snap else None,
                roas_var_pct=snap.roas_var_pct if snap else None,
            )
        )
    return ClientesListResponse(
        items=items,
        total=len(items),
        periodo_inicio=periodo_inicio_alvo,
        periodo_fim=periodo_fim_alvo,
        com_snapshot=com_snapshot,
    )
```

- [ ] **Step 4: Verificar que o backend importa sem erros**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend
.venv/bin/python -c "from api.internal import router; print('OK')"
```

Esperado: `OK`

- [ ] **Step 5: Commit**

```bash
git add web/backend/api/internal.py web/backend/tests/test_internal_clientes_range.py
git commit -m "feat(backend): endpoint /clientes aceita range de/ate, compat mes"
```

---

## Task 2: Frontend utils — `mes-utils.ts` e `api-internal.ts`

**Files:**
- Modify: `web/frontend/lib/mes-utils.ts`
- Modify: `web/frontend/lib/api-internal.ts`

- [ ] **Step 1: Estender `mes-utils.ts` com `labelRange`, `deslocarMes`, `mesUltimoFechado`**

Substituir o conteúdo completo de `web/frontend/lib/mes-utils.ts`:

```ts
const MESES_PT = [
  "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro",
];

const MESES_CURTOS = [
  "Jan","Fev","Mar","Abr","Mai","Jun",
  "Jul","Ago","Set","Out","Nov","Dez",
];

export function labelMes(mes: string): string {
  const [y, m] = mes.split("-");
  const idx = Number(m) - 1;
  return `${MESES_PT[idx] ?? m} ${y}`;
}

export function labelMesCurto(mes: string): string {
  const [, m] = mes.split("-");
  return MESES_CURTOS[Number(m) - 1] ?? m;
}

export function labelRange(de: string, ate: string): string {
  if (de === ate) return labelMes(de);
  return `${labelMesCurto(de)} ${de.slice(0, 4)} → ${labelMesCurto(ate)} ${ate.slice(0, 4)}`;
}

export function deslocarMes(mes: string, delta: number): string {
  const [y, m] = mes.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function mesUltimoFechado(): string {
  const d = new Date();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() - 1);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}
```

- [ ] **Step 2: Atualizar `listAllClientes` em `api-internal.ts`**

Substituir a função `listAllClientes` (linha 24–27):

```ts
export function listAllClientes(de: string, ate: string): Promise<ClientesListResponse> {
  const qs = `?de=${encodeURIComponent(de)}&ate=${encodeURIComponent(ate)}`;
  return fetchInternal<ClientesListResponse>(`/internal/clientes${qs}`);
}
```

- [ ] **Step 3: Verificar tipos com tsc**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/frontend
npx tsc --noEmit 2>&1 | head -30
```

Esperado: erros apenas nas referências antigas a `mes` em `lista/page.tsx` (que será corrigido na Task 4). Sem erros novos em `mes-utils.ts` ou `api-internal.ts`.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/lib/mes-utils.ts web/frontend/lib/api-internal.ts
git commit -m "feat(frontend): labelRange, deslocarMes, mesUltimoFechado em mes-utils; listAllClientes aceita range"
```

---

## Task 3: Componente `PeriodPicker`

**Files:**
- Create: `web/frontend/components/PeriodPicker.tsx`

- [ ] **Step 1: Criar o componente**

Criar `web/frontend/components/PeriodPicker.tsx` com o conteúdo abaixo:

```tsx
"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  deslocarMes,
  labelMesCurto,
  labelRange,
  mesUltimoFechado,
} from "@/lib/mes-utils";

const MESES_CURTOS = [
  "Jan","Fev","Mar","Abr","Mai","Jun",
  "Jul","Ago","Set","Out","Nov","Dez",
];

type Props = {
  available: Array<{ mes: string; com_snapshot: number }>;
  de: string;
  ate: string;
};

function ymParaMes(y: number, m: number): string {
  return `${y}-${String(m).padStart(2, "0")}`;
}

function clampRange(a: string, b: string): [string, string] {
  return a <= b ? [a, b] : [b, a];
}

const ref_mes = mesUltimoFechado();
const anoAtual = Number(ref_mes.slice(0, 4));

const QUICK_FILTERS: Array<{ label: string; de: string; ate: string }> = [
  { label: "Últimos 3M", de: deslocarMes(ref_mes, -2), ate: ref_mes },
  { label: "Últimos 6M", de: deslocarMes(ref_mes, -5), ate: ref_mes },
  { label: "Últimos 12M", de: deslocarMes(ref_mes, -11), ate: ref_mes },
  { label: "Este ano", de: `${anoAtual}-01`, ate: ref_mes },
];

export default function PeriodPicker({ available, de, ate }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(() => Number(ate.slice(0, 4)));
  const [picking, setPicking] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const snapshotCount = new Map(available.map((a) => [a.mes, a.com_snapshot]));

  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setPicking(null);
      }
    }
    if (open) document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  function applyRange(newDe: string, newAte: string) {
    const [d, a] = clampRange(newDe, newAte);
    const next = new URLSearchParams(searchParams);
    next.set("de", d);
    next.set("ate", a);
    next.delete("mes");
    router.push(`?${next.toString()}`);
    setOpen(false);
    setPicking(null);
    setHovered(null);
  }

  function handleClickMes(mes: string) {
    if (!picking) {
      setPicking(mes);
    } else {
      applyRange(picking, mes);
    }
  }

  const snapshotTotal = available.reduce((acc, a) => acc + a.com_snapshot, 0);

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger */}
      <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => { setOpen((v) => !v); setPicking(null); }}
            className="flex items-center gap-2 group"
          >
            <p className="eyebrow group-hover:text-[var(--ink)] transition">Período</p>
            <svg className="h-3 w-3 text-[var(--muted)] group-hover:text-[var(--ink-soft)] transition" viewBox="0 0 12 12" fill="none">
              <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <p className="text-xs text-[var(--muted)]">
            {snapshotTotal} snapshot(s) ·{" "}
            <span className="font-mono-num text-[var(--ink-soft)]">{labelRange(de, ate)}</span>
          </p>
        </div>
      </div>

      {/* Popover */}
      {open && (
        <div className="absolute left-0 top-full z-50 mt-2 w-72 rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] p-4 shadow-xl">
          {/* Quick filters */}
          <div className="mb-4 flex flex-wrap gap-1.5">
            {QUICK_FILTERS.map((f) => {
              const active = f.de === de && f.ate === ate;
              return (
                <button
                  key={f.label}
                  type="button"
                  onClick={() => applyRange(f.de, f.ate)}
                  className={[
                    "rounded-full border px-2.5 py-0.5 text-[11px] transition",
                    active
                      ? "border-[var(--ink)] bg-[var(--ink)] text-[var(--paper)]"
                      : "border-[var(--rule-soft)] text-[var(--ink-soft)] hover:border-[var(--ink-soft)] hover:text-[var(--ink)]",
                  ].join(" ")}
                >
                  {f.label}
                </button>
              );
            })}
          </div>

          {/* Year navigation */}
          <div className="mb-3 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setYear((y) => y - 1)}
              className="rounded p-1.5 hover:bg-[var(--paper-soft)] transition"
              aria-label="Ano anterior"
            >
              <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                <path d="M8 2L4 6l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <span className="font-mono-num text-sm font-medium">{year}</span>
            <button
              type="button"
              onClick={() => setYear((y) => y + 1)}
              className="rounded p-1.5 hover:bg-[var(--paper-soft)] transition"
              aria-label="Próximo ano"
            >
              <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>

          {/* Month grid */}
          <div className="grid grid-cols-4 gap-1">
            {MESES_CURTOS.map((label, idx) => {
              const mes = ymParaMes(year, idx + 1);
              const isSelected = mes === de || mes === ate;
              const isPicking = mes === picking;
              const inCurrentRange = mes >= de && mes <= ate;
              const [cA, cB] = picking && hovered ? clampRange(picking, hovered) : ["", ""];
              const inCandidateRange = cA && cB && mes >= cA && mes <= cB;
              const hasSnapshot = snapshotCount.has(mes);

              return (
                <button
                  key={mes}
                  type="button"
                  onClick={() => handleClickMes(mes)}
                  onMouseEnter={() => picking && setHovered(mes)}
                  onMouseLeave={() => picking && setHovered(null)}
                  className={[
                    "rounded py-1.5 text-xs font-medium transition select-none",
                    isSelected || isPicking
                      ? "bg-[var(--ink)] text-[var(--paper)]"
                      : inCurrentRange || inCandidateRange
                      ? "bg-[var(--paper-deep)] text-[var(--ink)]"
                      : "text-[var(--ink-soft)] hover:bg-[var(--paper-soft)] hover:text-[var(--ink)]",
                    !hasSnapshot && !isSelected && !isPicking ? "opacity-40" : "",
                  ].filter(Boolean).join(" ")}
                  title={hasSnapshot ? `${snapshotCount.get(mes)} snapshot(s)` : "Sem snapshots"}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Hint */}
          <p className="mt-3 text-center text-[10px] text-[var(--muted)]">
            {picking
              ? `Início: ${labelMesCurto(picking)} — clique no mês final`
              : "Clique no mês inicial do período"}
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verificar tipos com tsc**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/frontend
npx tsc --noEmit 2>&1 | grep -i "PeriodPicker\|mes-utils\|api-internal" | head -20
```

Esperado: sem erros relacionados ao novo componente.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/PeriodPicker.tsx
git commit -m "feat(frontend): componente PeriodPicker com calendário de meses e range"
```

---

## Task 4: Integrar `PeriodPicker` em `lista/page.tsx`

**Files:**
- Modify: `web/frontend/app/lista/page.tsx`

- [ ] **Step 1: Substituir o conteúdo completo de `lista/page.tsx`**

```tsx
import { ClientesTable } from "@/components/ClientesTable";
import PeriodPicker from "@/components/PeriodPicker";
import { labelRange, deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";
import TriggerColetaButton from "@/components/TriggerColetaButton";
import { listAllClientes, listPeriodos } from "@/lib/api-internal";

export const dynamic = "force-dynamic";

function defaultRange(): { de: string; ate: string } {
  const ate = mesUltimoFechado();
  const de = deslocarMes(ate, -2);
  return { de, ate };
}

function isoToMes(iso: string): string {
  return iso.slice(0, 7);
}

type SearchParams = { mes?: string; de?: string; ate?: string };

export default async function ListaPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const MES_RE = /^\d{4}-\d{2}$/;

  // Compat: ?mes= é tratado como de=mes&ate=mes
  let { de, ate } = defaultRange();
  if (params.de && MES_RE.test(params.de) && params.ate && MES_RE.test(params.ate)) {
    de = params.de;
    ate = params.ate;
    if (de > ate) [de, ate] = [ate, de];
  } else if (params.mes && MES_RE.test(params.mes)) {
    de = params.mes;
    ate = params.mes;
  }

  const [data, periodos] = await Promise.all([
    listAllClientes(de, ate),
    listPeriodos(),
  ]);

  const publicos = data.items.filter((i) => i.publicar_vitrine).length;
  const privados = data.total - publicos;
  const semSnapshotNoRange = data.total - data.com_snapshot;

  const disponiveis = periodos.items.map((p) => ({
    mes: isoToMes(p.periodo_inicio),
    com_snapshot: p.com_snapshot,
  }));

  const labelPeriodo = labelRange(de, ate);

  return (
    <main className="mx-auto max-w-[1440px] px-8">
      <section className="grid gap-10 pb-8 pt-16 md:grid-cols-12">
        <div className="md:col-span-8">
          <div className="flex items-center gap-4 text-[var(--muted)]">
            <span className="eyebrow">Painel interno</span>
            <span className="block h-px w-12 bg-[var(--rule-soft)]" />
            <span className="eyebrow">Acesso restrito</span>
          </div>
          <h1 className="font-display mt-5 text-[clamp(2.5rem,5vw,4.5rem)] font-medium leading-[0.95] tracking-tight">
            Lista completa de clientes
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-[var(--ink-soft)]">
            Inclui todos os clientes na base, sejam ou não publicados na
            vitrine. Cabeçalhos da tabela são clicáveis para ordenar; use o
            seletor de período para mudar o intervalo de referência.
          </p>
        </div>

        <aside className="md:col-span-4">
          <div className="grid grid-cols-3 gap-px bg-[var(--rule-soft)]">
            <div className="bg-[var(--paper)] p-4">
              <p className="eyebrow">Total</p>
              <p className="font-mono-num mt-2 text-2xl font-medium text-[var(--ink)]">
                {data.total}
              </p>
            </div>
            <div className="bg-[var(--paper)] p-4">
              <p className="eyebrow">Públicos</p>
              <p className="font-mono-num mt-2 text-2xl font-medium text-[var(--forest)]">
                {publicos}
              </p>
            </div>
            <div className="bg-[var(--paper)] p-4">
              <p className="eyebrow">Privados</p>
              <p className="font-mono-num mt-2 text-2xl font-medium text-[var(--amber)]">
                {privados}
              </p>
            </div>
          </div>
          <p className="mt-4 text-xs text-[var(--muted)]">
            Referência:{" "}
            <span className="font-mono-num text-[var(--ink-soft)]">
              {labelPeriodo}
            </span>
            {" · "}
            {data.com_snapshot} com snapshot, {semSnapshotNoRange} sem
          </p>
        </aside>
      </section>

      <section className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="w-full max-w-3xl">
          <PeriodPicker
            available={disponiveis}
            de={de}
            ate={ate}
          />
        </div>
        {data.com_snapshot === 0 && (
          <TriggerColetaButton mes={ate} label={labelPeriodo} />
        )}
      </section>

      <ClientesTable items={data.items} />

      <p className="mt-8 text-xs text-[var(--muted)]">
        Dados extraídos diretamente do banco — não passam pelo filtro de
        publicação. Não compartilhar fora do time.
      </p>
    </main>
  );
}
```

- [ ] **Step 2: Verificar que `tsc` passa sem erros**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/frontend
npx tsc --noEmit 2>&1 | head -30
```

Esperado: sem erros de tipo.

- [ ] **Step 3: Subir o frontend e verificar manualmente**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/frontend
npm run dev
```

Abrir `http://localhost:3000/lista` e verificar:
- O trigger exibe o range atual (ex: "Mar 2026 → Mai 2026")
- Clicar no trigger abre o popover
- Quick filters funcionam e fecham o popover
- Grid de meses navega por ano
- Dois cliques definem início e fim do range
- URL atualiza para `?de=YYYY-MM&ate=YYYY-MM`
- URL legada `?mes=YYYY-MM` funciona sem erros
- Meses sem snapshot aparecem com opacidade reduzida

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/lista/page.tsx
git commit -m "feat(lista): PeriodPicker integrado, URL de/ate, compat mes, default 3M"
```

---

## Verificação Final

- [ ] `npx tsc --noEmit` sem erros
- [ ] Backend responde a `GET /internal/clientes?de=2026-02&ate=2026-04` com token correto
- [ ] URL `?mes=2026-04` redireciona/funciona como `de=2026-04&ate=2026-04`
- [ ] URL sem parâmetros carrega com os últimos 3 meses
- [ ] Quick filter "Últimos 3M" seleciona o range correto
- [ ] Seleção via grid: primeiro clique = início (hint muda), segundo clique = aplica
- [ ] Click fora do popover fecha sem alterar o range
