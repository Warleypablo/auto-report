# Cliente Dashboard Cinemático Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refazer login + splash + dashboard do cliente como uma jornada editorial cinemática (tipografia Fraunces gigante, animações ricas, galeria de criativos), preservando stack e modelo de dados atuais.

**Architecture:** Frontend Next.js 14 com novos componentes em `web/frontend/components/` que substituem o conteúdo de `app/cliente/login/page.tsx` e `app/cliente/dashboard/page.tsx`. Backend FastAPI ganha um endpoint `/cliente/metricas/highlight` com heurísticas puras sobre a timeline já existente. Animações com `framer-motion` + `react-intersection-observer`.

**Tech Stack:** Next 14 + React 18 + TypeScript + Tailwind + Recharts + framer-motion (novo) + react-intersection-observer (novo) · FastAPI + SQLAlchemy + Postgres · Playwright (E2E) + pytest (unit).

**Spec:** `docs/superpowers/specs/2026-05-26-cliente-dashboard-cinematic-design.md`

---

## File Structure

**Backend (criar):**
- `web/backend/services/cliente_highlight.py` — função pura que calcula highlight a partir da timeline
- `web/backend/tests/test_cliente_highlight.py` — testes unitários da heurística
- `web/backend/tests/test_cliente_highlight_endpoint.py` — teste de integração do endpoint

**Backend (modificar):**
- `web/backend/api/cliente.py` — adicionar handler `/metricas/highlight`

**Frontend — proxy/api (modificar):**
- `web/frontend/lib/api-cliente.ts` — adicionar tipo `Highlight` + método `clienteApi.highlight()`
- `web/frontend/app/api/cliente/metricas/` — criar subpasta `highlight/route.ts`

**Frontend — utilitários (criar):**
- `web/frontend/components/Counter.tsx` — número que conta de 0 ao valor
- `web/frontend/components/RevealOnView.tsx` — wrapper fade-up em viewport
- `web/frontend/components/MetricToggle.tsx` — segmento com sublinhado animado

**Frontend — conteúdo (criar):**
- `web/frontend/components/HeroMonth.tsx`
- `web/frontend/components/KpiRow.tsx`
- `web/frontend/components/EvolutionChartHero.tsx`
- `web/frontend/components/CreativeGallery.tsx`
- `web/frontend/components/CampaignBars.tsx`
- `web/frontend/components/DetailsDrawer.tsx`
- `web/frontend/components/WelcomeSplash.tsx`
- `web/frontend/components/LoginScene.tsx`

**Frontend (modificar):**
- `web/frontend/app/cliente/login/page.tsx` — passar a renderizar `<LoginScene />`
- `web/frontend/app/cliente/dashboard/page.tsx` — reescrever orquestrando os novos componentes
- `web/frontend/app/globals.css` — keyframes do gradient mesh + utilitários
- `web/frontend/package.json` — adicionar `framer-motion`, `react-intersection-observer`

**Tests E2E (modificar):**
- `web/frontend/tests/e2e/cliente-dashboard.spec.ts` — atualizar para nova UI
- `web/frontend/tests/e2e/cliente-login.spec.ts` — adicionar verificação do background animado (smoke)

---

## Task 1: Setup de dependências e estilos globais

**Files:**
- Modify: `web/frontend/package.json`
- Modify: `web/frontend/app/globals.css`

- [ ] **Step 1: Instalar dependências novas**

Run:
```bash
cd web/frontend && npm install framer-motion@^11.0.0 react-intersection-observer@^9.10.0
```

Expected: dependencies adicionadas ao `package.json` e `package-lock.json` atualizado, sem erros de peer dependency.

- [ ] **Step 2: Adicionar keyframes e utilitários no globals.css**

Em `web/frontend/app/globals.css`, no final do arquivo (depois do bloco `::selection`), adicionar:

```css
/* === Cinematic enhancements === */

@keyframes mesh-drift {
  0%   { transform: translate3d(0,0,0) scale(1); }
  50%  { transform: translate3d(2%, -1.5%, 0) scale(1.05); }
  100% { transform: translate3d(0,0,0) scale(1); }
}

.mesh-bg {
  position: absolute;
  inset: -10%;
  pointer-events: none;
  background:
    radial-gradient(700px 500px at 20% 30%, rgba(31, 77, 60, 0.18), transparent 60%),
    radial-gradient(600px 400px at 80% 70%, rgba(181, 122, 31, 0.12), transparent 55%);
  filter: blur(60px);
  animation: mesh-drift 30s ease-in-out infinite;
  will-change: transform;
}

.dark .mesh-bg {
  background:
    radial-gradient(700px 500px at 20% 30%, rgba(111, 181, 151, 0.18), transparent 60%),
    radial-gradient(600px 400px at 80% 70%, rgba(217, 162, 75, 0.12), transparent 55%);
}

@keyframes stroke-draw {
  from { stroke-dashoffset: var(--len, 1000); }
  to   { stroke-dashoffset: 0; }
}

.stroke-reveal {
  stroke-dasharray: var(--len, 1000);
  stroke-dashoffset: var(--len, 1000);
  animation: stroke-draw 1.5s cubic-bezier(.2,.7,.2,1) forwards;
}

@media (prefers-reduced-motion: reduce) {
  .mesh-bg,
  .reveal,
  .stroke-reveal {
    animation: none !important;
    transition: none !important;
  }
  .stroke-reveal { stroke-dashoffset: 0 !important; }
  .reveal { opacity: 1 !important; transform: none !important; }
}
```

- [ ] **Step 3: Verificar que o frontend compila**

Run:
```bash
cd web/frontend && npm run build 2>&1 | tail -20
```

Expected: build conclui sem erros (warnings sobre o tamanho do bundle são esperados).

- [ ] **Step 4: Commit**

```bash
git add web/frontend/package.json web/frontend/package-lock.json web/frontend/app/globals.css
git commit -m "chore(cliente-fe): add framer-motion + intersection-observer + mesh keyframes"
```

---

## Task 2: Serviço de highlight no backend (TDD)

**Files:**
- Create: `web/backend/services/cliente_highlight.py`
- Create: `web/backend/tests/test_cliente_highlight.py`

- [ ] **Step 1: Escrever o teste de unidade primeiro**

Criar `web/backend/tests/test_cliente_highlight.py`:

```python
from services.cliente_highlight import compute_highlight


def _row(mes: str, fat: float | None = None, roas: float | None = None,
         fat_var: float | None = None):
    return {
        "mes": mes,
        "faturamento": fat,
        "roas": roas,
        "investimento": None,
        "cpa": None,
        "leads": None,
        "vendas": None,
        "faturamento_var_pct": fat_var,
        "roas_var_pct": None,
        "periodo_inicio": "",
        "periodo_fim": "",
    }


def test_returns_none_when_timeline_empty():
    assert compute_highlight([]) is None


def test_returns_none_when_less_than_six_months():
    tl = [_row(f"2026-0{m}", roas=3.0) for m in range(1, 6)]
    assert compute_highlight(tl) is None


def test_best_roas_window_when_last_is_max_in_12m():
    # 12 meses, último com ROAS maior
    tl = [_row(f"2025-{m:02d}", roas=2.0) for m in range(6, 13)] + \
         [_row(f"2026-{m:02d}", roas=2.5) for m in range(1, 5)] + \
         [_row("2026-05", roas=4.2)]
    h = compute_highlight(tl)
    assert h is not None
    assert h["type"] == "best_roas_window"
    assert h["metric"] == "roas"
    assert h["value"] == 4.2
    assert h["period_months"] == 12
    assert "ROAS" in h["message"]


def test_best_revenue_when_roas_not_best_but_revenue_is():
    # Último mês com ROAS médio mas maior faturamento
    tl = [_row(f"2025-{m:02d}", fat=1000.0, roas=4.0) for m in range(6, 13)] + \
         [_row(f"2026-{m:02d}", fat=1500.0, roas=4.0) for m in range(1, 5)] + \
         [_row("2026-05", fat=2000.0, roas=3.5)]
    h = compute_highlight(tl)
    assert h is not None
    assert h["type"] == "best_revenue_window"
    assert h["metric"] == "faturamento"
    assert h["value"] == 2000.0


def test_growth_vs_prev_when_no_window_best():
    # ROAS e faturamento estáveis exceto crescimento de 20% no último
    tl = [_row(f"2025-{m:02d}", fat=2000.0, roas=4.0) for m in range(6, 13)] + \
         [_row(f"2026-{m:02d}", fat=2000.0, roas=4.0) for m in range(1, 5)] + \
         [_row("2026-05", fat=1700.0, roas=4.0, fat_var=20.0)]
    h = compute_highlight(tl)
    assert h is not None
    assert h["type"] == "growth_vs_prev"
    assert h["value"] == 20.0


def test_returns_none_when_nothing_remarkable():
    tl = [_row(f"2025-{m:02d}", fat=2000.0, roas=4.0) for m in range(6, 13)] + \
         [_row(f"2026-{m:02d}", fat=2000.0, roas=4.0) for m in range(1, 6)]
    assert compute_highlight(tl) is None
```

- [ ] **Step 2: Rodar testes e confirmar que falham por módulo inexistente**

Run:
```bash
cd web/backend && python -m pytest tests/test_cliente_highlight.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'services.cliente_highlight'` ou similar.

- [ ] **Step 3: Implementar o serviço**

Criar `web/backend/services/cliente_highlight.py`:

```python
"""Compute o 'destaque do mês' para a splash do cliente.

Toda a heurística é pura — opera sobre a lista de dicts retornada por
`build_timeline` (services/metricas.py). Sem I/O.
"""
from __future__ import annotations

NOMES_MES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _mes_pt(mes_yyyymm: str) -> str:
    """'2026-05' -> 'Maio'."""
    try:
        return NOMES_MES[int(mes_yyyymm[5:7]) - 1]
    except (ValueError, IndexError):
        return mes_yyyymm


def compute_highlight(timeline: list[dict]) -> dict | None:
    """Calcula o highlight do último ponto da timeline.

    timeline: lista ordenada cronologicamente (antigo → recente), mesmo
    formato que `build_timeline` retorna.

    Retorna dict com keys: type, metric, value, period_months, message
    ou None se nada relevante.
    """
    if not timeline or len(timeline) < 6:
        return None

    janela = timeline[-12:]
    atual = timeline[-1]
    mes_label = _mes_pt(atual["mes"])

    roas_values = [r["roas"] for r in janela if r["roas"] is not None]
    if (
        atual["roas"] is not None
        and roas_values
        and atual["roas"] == max(roas_values)
        and len(roas_values) >= 6
        and roas_values.count(atual["roas"]) == 1
    ):
        return {
            "type": "best_roas_window",
            "metric": "roas",
            "value": atual["roas"],
            "period_months": len(janela),
            "message": f"{mes_label} foi seu melhor mês em ROAS dos últimos {len(janela)} meses.",
        }

    fat_values = [r["faturamento"] for r in janela if r["faturamento"] is not None]
    if (
        atual["faturamento"] is not None
        and fat_values
        and atual["faturamento"] == max(fat_values)
        and len(fat_values) >= 6
        and fat_values.count(atual["faturamento"]) == 1
    ):
        return {
            "type": "best_revenue_window",
            "metric": "faturamento",
            "value": atual["faturamento"],
            "period_months": len(janela),
            "message": f"{mes_label} foi seu melhor mês em faturamento dos últimos {len(janela)} meses.",
        }

    fat_var = atual.get("faturamento_var_pct")
    if fat_var is not None and fat_var >= 15.0:
        return {
            "type": "growth_vs_prev",
            "metric": "faturamento",
            "value": fat_var,
            "period_months": 1,
            "message": f"+{fat_var:.0f}% em faturamento vs. mês anterior.",
        }

    return None
```

- [ ] **Step 4: Rodar testes e confirmar PASS**

Run:
```bash
cd web/backend && python -m pytest tests/test_cliente_highlight.py -v 2>&1 | tail -15
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/backend/services/cliente_highlight.py web/backend/tests/test_cliente_highlight.py
git commit -m "feat(cliente): serviço puro de highlight do mês com heurísticas"
```

---

## Task 3: Endpoint /cliente/metricas/highlight

**Files:**
- Modify: `web/backend/api/cliente.py:232-237`
- Create: `web/backend/tests/test_cliente_highlight_endpoint.py`

- [ ] **Step 1: Escrever o teste de integração primeiro**

Criar `web/backend/tests/test_cliente_highlight_endpoint.py`:

```python
"""Teste do endpoint /cliente/metricas/highlight.

Reaproveita a fixture `app_with_db` de test_cliente_metricas.py via import.
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text

from models import Cliente
from models.cliente import Categoria
from models.snapshot import Frequencia, Snapshot

from tests.test_cliente_metricas import app_with_db  # noqa: F401  (fixture)


def _seed_with_snaps(TS, *, nome, cnpj, task_id, snaps):
    """snaps: lista de (mes_yyyymm, faturamento, roas, fat_var_pct)."""
    with TS() as s:
        c = Cliente(
            slug=nome.lower(),
            nome=nome,
            categoria=Categoria.LEAD_COM_SITE,
            cup_task_id=task_id,
            ativo=True,
        )
        s.add(c); s.commit(); s.refresh(c)
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome, cnpj) VALUES (:t, :n, :c)"),
            {"t": task_id, "n": nome, "c": cnpj},
        )
        for mes, fat, roas, fat_var in snaps:
            ano, m = int(mes[:4]), int(mes[5:7])
            s.add(Snapshot(
                cliente_id=c.id,
                periodo_inicio=date(ano, m, 1),
                periodo_fim=date(ano, m, 28),
                frequencia=Frequencia.MENSAL,
                faturamento=Decimal(str(fat)),
                investimento=Decimal("100"),
                roas=Decimal(str(roas)),
                faturamento_var_pct=Decimal(str(fat_var)) if fat_var is not None else None,
            ))
        s.commit()
        return c.id


def _login(client: TestClient, cnpj: str, senha: str) -> str:
    # Garante cliente_senhas seeded
    r = client.post("/cliente/auth/login", json={"cnpj": cnpj, "senha": senha})
    assert r.status_code == 200
    return r.cookies.get("cliente_token") or r.headers.get("set-cookie", "")


def test_highlight_returns_401_without_token(app_with_db):
    app, _ = app_with_db
    client = TestClient(app)
    r = client.get("/cliente/metricas/highlight")
    assert r.status_code == 401


def test_highlight_returns_null_with_few_data(app_with_db):
    app, TS = app_with_db
    snaps = [("2026-04", 1000, 3.5, None), ("2026-05", 1100, 3.6, None)]
    _seed_with_snaps(TS, nome="loja-a", cnpj="11111111000111", task_id="t-a", snaps=snaps)
    # cria senha
    with TS() as s:
        from models.cliente_senha import ClienteSenha
        from passlib.hash import bcrypt
        cli = s.query(Cliente).filter_by(slug="loja-a").first()
        s.add(ClienteSenha(cliente_id=cli.id, senha_hash=bcrypt.hash("senha123")))
        s.commit()

    client = TestClient(app)
    client.post("/cliente/auth/login", json={"cnpj": "11.111.111/0001-11", "senha": "senha123"})
    r = client.get("/cliente/metricas/highlight")
    assert r.status_code == 200
    assert r.json() == {"highlight": None}


def test_highlight_returns_best_roas_window(app_with_db):
    app, TS = app_with_db
    snaps = [(f"2025-{m:02d}", 1000, 2.5, None) for m in range(6, 13)] + \
            [(f"2026-{m:02d}", 1100, 2.6, None) for m in range(1, 5)] + \
            [("2026-05", 1200, 4.2, None)]
    _seed_with_snaps(TS, nome="loja-b", cnpj="22222222000122", task_id="t-b", snaps=snaps)
    with TS() as s:
        from models.cliente_senha import ClienteSenha
        from passlib.hash import bcrypt
        cli = s.query(Cliente).filter_by(slug="loja-b").first()
        s.add(ClienteSenha(cliente_id=cli.id, senha_hash=bcrypt.hash("senha123")))
        s.commit()

    client = TestClient(app)
    client.post("/cliente/auth/login", json={"cnpj": "22.222.222/0001-22", "senha": "senha123"})
    r = client.get("/cliente/metricas/highlight")
    assert r.status_code == 200
    body = r.json()
    assert body["highlight"] is not None
    assert body["highlight"]["type"] == "best_roas_window"
    assert body["highlight"]["value"] == 4.2
```

- [ ] **Step 2: Rodar testes e confirmar que falham por endpoint inexistente**

Run:
```bash
cd web/backend && python -m pytest tests/test_cliente_highlight_endpoint.py -v 2>&1 | tail -20
```

Expected: 404 nos GETs (endpoint não existe ainda).

- [ ] **Step 3: Adicionar o handler em api/cliente.py**

Em `web/backend/api/cliente.py`, ao final do arquivo (depois de `metricas_meses_disponiveis`), adicionar:

```python
from services.cliente_highlight import compute_highlight as _compute_highlight


@router.get("/metricas/highlight")
def metricas_highlight(
    cliente: Cliente = Depends(require_cliente),
    session: Session = Depends(get_session),
) -> dict:
    timeline = build_timeline(cliente.id, 12, session)
    return {"highlight": _compute_highlight(timeline)}
```

Importante: o import `from services.cliente_highlight import compute_highlight as _compute_highlight` deve ir no topo do arquivo junto com os outros imports — não inline. Apenas mostrei inline aqui pra contextualizar.

- [ ] **Step 4: Mover o import para o topo**

Editar `web/backend/api/cliente.py`. Localizar o bloco de imports (linhas iniciais, próximas a `from services.metricas import build_breakdown, build_timeline, meses_disponiveis_for_cliente`) e adicionar logo abaixo:

```python
from services.cliente_highlight import compute_highlight as _compute_highlight
```

Depois remover o import inline do handler (deixar só o `_compute_highlight(timeline)` na função).

- [ ] **Step 5: Rodar testes e confirmar PASS**

Run:
```bash
cd web/backend && python -m pytest tests/test_cliente_highlight_endpoint.py -v 2>&1 | tail -15
```

Expected: 3 tests pass.

- [ ] **Step 6: Rodar suíte completa de testes do cliente para garantir que nada quebrou**

Run:
```bash
cd web/backend && python -m pytest tests/test_cliente_metricas.py tests/test_cliente_auth.py tests/test_cliente_highlight.py tests/test_cliente_highlight_endpoint.py -v 2>&1 | tail -15
```

Expected: todos os testes existentes continuam passando + os novos passam.

- [ ] **Step 7: Commit**

```bash
git add web/backend/api/cliente.py web/backend/tests/test_cliente_highlight_endpoint.py
git commit -m "feat(cliente-api): endpoint /metricas/highlight retorna destaque do mês"
```

---

## Task 4: Proxy e cliente HTTP no frontend

**Files:**
- Create: `web/frontend/app/api/cliente/metricas/highlight/route.ts`
- Modify: `web/frontend/lib/api-cliente.ts`

- [ ] **Step 1: Criar a rota proxy do Next**

Criar `web/frontend/app/api/cliente/metricas/highlight/route.ts`:

```typescript
import { NextRequest } from "next/server";

import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  return proxyGet(req, "/cliente/metricas/highlight");
}
```

- [ ] **Step 2: Adicionar tipo + método no `api-cliente.ts`**

Em `web/frontend/lib/api-cliente.ts`, depois do bloco `export type Breakdown = ...` (linha 47), adicionar:

```typescript
export type Highlight = {
  type: "best_roas_window" | "best_revenue_window" | "growth_vs_prev";
  metric: "roas" | "faturamento";
  value: number;
  period_months: number;
  message: string;
};
```

E dentro do objeto `clienteApi`, adicionar o método:

```typescript
  highlight: () =>
    call<{ highlight: Highlight | null }>("/metricas/highlight"),
```

(adicionar como última propriedade, antes do `}` que fecha o objeto)

- [ ] **Step 3: Verificar typecheck**

Run:
```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -10
```

Expected: sem erros de tipo.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/api/cliente/metricas/highlight web/frontend/lib/api-cliente.ts
git commit -m "feat(cliente-fe): proxy + tipo + método clienteApi.highlight()"
```

---

## Task 5: Componente Counter (número que anima)

**Files:**
- Create: `web/frontend/components/Counter.tsx`

- [ ] **Step 1: Implementar Counter**

Criar `web/frontend/components/Counter.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  to: number;
  format?: (n: number) => string;
  duration?: number;
  /** Se true, renderiza o valor final imediatamente. */
  disabled?: boolean;
};

const easeOutExpo = (t: number) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t));

export default function Counter({ to, format, duration = 1200, disabled }: Props) {
  const [value, setValue] = useState<number>(disabled ? to : 0);
  const rafRef = useRef<number | null>(null);
  const startedAt = useRef<number | null>(null);

  useEffect(() => {
    if (disabled) {
      setValue(to);
      return;
    }
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setValue(to);
      return;
    }

    startedAt.current = null;
    const tick = (ts: number) => {
      if (startedAt.current === null) startedAt.current = ts;
      const elapsed = ts - startedAt.current;
      const t = Math.min(1, elapsed / duration);
      setValue(to * easeOutExpo(t));
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [to, duration, disabled]);

  return <>{format ? format(value) : Math.round(value).toLocaleString("pt-BR")}</>;
}
```

- [ ] **Step 2: Typecheck**

Run:
```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/Counter.tsx
git commit -m "feat(cliente-fe): componente Counter (rAF + easeOutExpo + reduced-motion)"
```

---

## Task 6: Componente RevealOnView

**Files:**
- Create: `web/frontend/components/RevealOnView.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/RevealOnView.tsx`:

```tsx
"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useInView } from "react-intersection-observer";

type Props = {
  children: React.ReactNode;
  delay?: number;
  className?: string;
};

export default function RevealOnView({ children, delay = 0, className }: Props) {
  const prefersReduced = useReducedMotion();
  const { ref, inView } = useInView({ triggerOnce: true, rootMargin: "-10% 0px" });

  if (prefersReduced) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 16 }}
      animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
      transition={{ duration: 0.6, delay, ease: [0.2, 0.7, 0.2, 1] }}
    >
      {children}
    </motion.div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/components/RevealOnView.tsx
git commit -m "feat(cliente-fe): RevealOnView (fade-up em viewport)"
```

---

## Task 7: Componente MetricToggle

**Files:**
- Create: `web/frontend/components/MetricToggle.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/MetricToggle.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import { useId } from "react";

type Option<T extends string> = { value: T; label: string };

type Props<T extends string> = {
  options: Option<T>[];
  value: T;
  onChange: (v: T) => void;
};

export default function MetricToggle<T extends string>({ options, value, onChange }: Props<T>) {
  const layoutId = useId();
  return (
    <div className="flex gap-6 text-[10px] uppercase tracking-[0.18em]">
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`relative pb-1 transition-colors ${
              active ? "text-[var(--forest)]" : "text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            {opt.label}
            {active && (
              <motion.span
                layoutId={`metric-underline-${layoutId}`}
                className="absolute inset-x-0 -bottom-px h-px bg-[var(--forest)]"
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/MetricToggle.tsx
git commit -m "feat(cliente-fe): MetricToggle (segmento com sublinhado animado)"
```

---

## Task 8: Componente HeroMonth

**Files:**
- Create: `web/frontend/components/HeroMonth.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/HeroMonth.tsx`:

```tsx
"use client";

import Counter from "./Counter";
import RevealOnView from "./RevealOnView";

type TimelinePoint = { mes: string; faturamento: number | null };

type Props = {
  mesLabel: string;
  faturamento: number | null;
  roas: number | null;
  varFaturamento: number | null;
  varRoas: number | null;
  timeline12m: TimelinePoint[];
};

const fmtBRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtRoas = (v: number) => `${v.toFixed(2).replace(".", ",")}×`;
const fmtPct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

function buildSparkPath(points: number[], w = 1200, h = 240): string {
  if (points.length < 2) return "";
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const step = w / (points.length - 1);
  return points
    .map((v, i) => {
      const x = i * step;
      const y = h - ((v - min) / range) * h * 0.8 - h * 0.1;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export default function HeroMonth({
  mesLabel, faturamento, roas, varFaturamento, varRoas, timeline12m,
}: Props) {
  const sparkPts = timeline12m.map((p) => p.faturamento ?? 0).filter((_, i, a) => a.length >= 3);
  const sparkPath = sparkPts.length >= 3 ? buildSparkPath(sparkPts) : "";

  return (
    <section className="relative mb-16 min-h-[50vh]">
      {sparkPath && (
        <svg
          viewBox="0 0 1200 240"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-[60%] w-full opacity-[0.12]"
          aria-hidden
        >
          <path d={sparkPath} fill="none" stroke="var(--forest)" strokeWidth="2" />
        </svg>
      )}

      <RevealOnView className="relative">
        <p className="eyebrow mb-2 text-xs text-[var(--muted)]">Faturamento · {mesLabel}</p>
        <h2 className="font-display font-light italic leading-none tracking-tight text-[var(--ink)] text-[64px] sm:text-[88px] lg:text-[128px]">
          {faturamento != null ? (
            <Counter to={faturamento} format={(v) => fmtBRL(v)} />
          ) : (
            "—"
          )}
        </h2>
        {varFaturamento != null && (
          <p className="font-mono-num mt-3 text-xs text-[var(--muted)]">
            <span className={varFaturamento >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}>
              {varFaturamento >= 0 ? "↗" : "↘"} {fmtPct(varFaturamento)}
            </span>{" "}
            vs. mês anterior
          </p>
        )}
      </RevealOnView>

      <RevealOnView delay={0.15} className="relative mt-12">
        <p className="eyebrow mb-2 text-xs text-[var(--muted)]">ROAS · {mesLabel}</p>
        <h3 className="font-display font-light italic leading-none tracking-tight text-[var(--forest)] text-[44px] sm:text-[64px] lg:text-[88px]">
          {roas != null ? <Counter to={roas} format={(v) => fmtRoas(v)} /> : "—"}
        </h3>
        {varRoas != null && (
          <p className="font-mono-num mt-3 text-xs text-[var(--muted)]">
            <span className={varRoas >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}>
              {varRoas >= 0 ? "↗" : "↘"} {fmtPct(varRoas)}
            </span>{" "}
            vs. mês anterior
          </p>
        )}
      </RevealOnView>
    </section>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/HeroMonth.tsx
git commit -m "feat(cliente-fe): HeroMonth (faturamento + ROAS gigantes + spark fundo)"
```

---

## Task 9: Componente KpiRow

**Files:**
- Create: `web/frontend/components/KpiRow.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/KpiRow.tsx`:

```tsx
"use client";

import RevealOnView from "./RevealOnView";

type Kpi = {
  label: string;
  value: string;
  spark: number[];
  varPct: number | null;
};

type Props = { kpis: Kpi[] };

function MiniSpark({ values }: { values: number[] }) {
  if (values.length < 2) return <div className="h-6" />;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const w = 100;
  const h = 24;
  const step = w / (values.length - 1);
  const d = values
    .map((v, i) => {
      const x = i * step;
      const y = h - ((v - min) / range) * h * 0.8 - h * 0.1;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-6 w-full opacity-60" aria-hidden>
      <path d={d} fill="none" stroke="var(--forest)" strokeWidth="1.4" />
    </svg>
  );
}

export default function KpiRow({ kpis }: Props) {
  return (
    <RevealOnView className="mb-16">
      <div className="grid grid-cols-2 gap-y-6 gap-x-0 md:grid-cols-4">
        {kpis.map((k, i) => (
          <div
            key={k.label}
            className={`px-4 sm:px-6 ${i > 0 ? "md:border-l md:border-[var(--rule-soft)]" : ""}`}
          >
            <p className="eyebrow mb-1 text-[10px] text-[var(--muted)]">{k.label}</p>
            <p className="font-mono-num text-[22px] text-[var(--ink)] leading-tight">
              {k.value}
            </p>
            <div className="mt-3">
              <MiniSpark values={k.spark} />
            </div>
            {k.varPct != null && (
              <p
                className={`font-mono-num mt-1 text-[10px] ${
                  k.varPct >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"
                }`}
              >
                {k.varPct >= 0 ? "+" : ""}
                {k.varPct.toFixed(1)}% vs período anterior
              </p>
            )}
          </div>
        ))}
      </div>
    </RevealOnView>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/KpiRow.tsx
git commit -m "feat(cliente-fe): KpiRow (4 KPIs com mini-sparks e filetes)"
```

---

## Task 10: Componente EvolutionChartHero

**Files:**
- Create: `web/frontend/components/EvolutionChartHero.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/EvolutionChartHero.tsx`:

```tsx
"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import MetricToggle from "./MetricToggle";
import RevealOnView from "./RevealOnView";

type Point = {
  mes: string;
  faturamento: number | null;
  roas: number | null;
  investimento: number | null;
};

type Metric = "faturamento" | "roas" | "investimento";

const LABELS: Record<Metric, string> = {
  faturamento: "Faturamento",
  roas: "ROAS",
  investimento: "Investimento",
};

const NOMES_MES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const mesLabel = (mes: string) => {
  const [a, m] = mes.split("-");
  return `${NOMES_MES[parseInt(m) - 1]} ${a.slice(2)}`;
};

const fmtBRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtRoas = (v: number) => `${v.toFixed(2).replace(".", ",")}×`;

function tooltipContent(metric: Metric) {
  return ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const p = payload[0];
    const raw = p.value as number;
    const v = metric === "roas" ? fmtRoas(raw) : fmtBRL(raw);
    return (
      <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-xs shadow-sm">
        <p className="text-[var(--muted)]">{p.payload.mes}</p>
        <p className="font-mono-num text-[var(--ink)]">{v}</p>
      </div>
    );
  };
}

type Props = { timeline: Point[] };

export default function EvolutionChartHero({ timeline }: Props) {
  const [metric, setMetric] = useState<Metric>("faturamento");

  if (timeline.length < 2) return null;

  const data = timeline.map((p) => ({
    mes: mesLabel(p.mes),
    value: p[metric] ?? 0,
  }));

  return (
    <RevealOnView className="mb-16">
      <div className="mb-4 flex items-center justify-between">
        <p className="eyebrow text-xs text-[var(--muted)]">
          Evolução · últimos {timeline.length} meses
        </p>
        <MetricToggle
          options={[
            { value: "faturamento", label: LABELS.faturamento },
            { value: "roas", label: LABELS.roas },
            { value: "investimento", label: LABELS.investimento },
          ]}
          value={metric}
          onChange={setMetric}
        />
      </div>

      <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
        <ResponsiveContainer width="100%" height={360}>
          <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="evo-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--forest)" stopOpacity={0.25} />
                <stop offset="100%" stopColor="var(--forest)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--rule-soft)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="mes"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              tickFormatter={(v) => (metric === "roas" ? `${v}×` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
              axisLine={false}
              tickLine={false}
              width={50}
            />
            <Tooltip content={tooltipContent(metric)} cursor={{ stroke: "var(--rule-soft)" }} />
            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--forest)"
              strokeWidth={1.8}
              fill="url(#evo-fill)"
              isAnimationActive
              animationDuration={1200}
              animationEasing="ease-out"
              dot={{ r: 3, fill: "var(--forest)" }}
              activeDot={{ r: 5 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </RevealOnView>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/EvolutionChartHero.tsx
git commit -m "feat(cliente-fe): EvolutionChartHero (área cheia + toggle + animação)"
```

---

## Task 11: Componente CreativeGallery

**Files:**
- Create: `web/frontend/components/CreativeGallery.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/CreativeGallery.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";

import type { MetaAd } from "@/lib/api-cliente";

import RevealOnView from "./RevealOnView";

type Props = {
  criativos: MetaAd[];
  onSeeAll: () => void;
};

const fmtBRL = (v: number | null) =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtRoas = (v: number | null) => (v == null ? "—" : `${v.toFixed(2).replace(".", ",")}×`);

export default function CreativeGallery({ criativos, onSeeAll }: Props) {
  if (criativos.length === 0) {
    return (
      <RevealOnView className="mb-16">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Top criativos · Meta Ads</p>
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
          Sem criativos detalhados neste mês.
        </p>
      </RevealOnView>
    );
  }

  const top3 = criativos.slice(0, 3);

  return (
    <RevealOnView className="mb-16">
      <div className="mb-4 flex items-end justify-between">
        <p className="eyebrow text-xs text-[var(--muted)]">Top criativos · Meta Ads</p>
        {criativos.length > 3 && (
          <button
            type="button"
            onClick={onSeeAll}
            className="text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
          >
            Ver todos os {criativos.length} →
          </button>
        )}
      </div>

      <div className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 md:grid md:grid-cols-3 md:overflow-visible md:pb-0">
        {top3.map((ad, i) => (
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
              <div className="flex h-full w-full items-center justify-center text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">
                sem imagem
              </div>
            )}

            <div className="absolute left-3 top-3 rounded-sm bg-black/55 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-white">
              #{i + 1}
            </div>

            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/50 to-transparent p-4">
              <p className="line-clamp-1 text-[11px] text-white/90">{ad.nome}</p>
              <div className="mt-1 flex items-baseline justify-between">
                <span className="font-mono-num text-lg text-white">{fmtRoas(ad.roas)}</span>
                <span className="font-mono-num text-[11px] text-white/80">{fmtBRL(ad.investimento)}</span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </RevealOnView>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/CreativeGallery.tsx
git commit -m "feat(cliente-fe): CreativeGallery (top 3 cards 16:9 com overlay)"
```

---

## Task 12: Componente CampaignBars

**Files:**
- Create: `web/frontend/components/CampaignBars.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/CampaignBars.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";

import type { GoogleAd } from "@/lib/api-cliente";

import RevealOnView from "./RevealOnView";

type Props = {
  campanhas: GoogleAd[];
  onSeeAll: () => void;
};

const fmtBRL = (v: number | null) =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtRoas = (v: number | null) => (v == null ? "—" : `${v.toFixed(2).replace(".", ",")}×`);

export default function CampaignBars({ campanhas, onSeeAll }: Props) {
  if (campanhas.length === 0) {
    return (
      <RevealOnView className="mb-16">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Top campanhas · Google Ads</p>
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
          Sem campanhas detalhadas neste mês.
        </p>
      </RevealOnView>
    );
  }

  const top5 = campanhas.slice(0, 5);
  const maxInv = Math.max(...top5.map((c) => c.investimento ?? 0), 1);

  return (
    <RevealOnView className="mb-16">
      <div className="mb-4 flex items-end justify-between">
        <p className="eyebrow text-xs text-[var(--muted)]">Top campanhas · Google Ads</p>
        {campanhas.length > 5 && (
          <button
            type="button"
            onClick={onSeeAll}
            className="text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
          >
            Ver todas as {campanhas.length} →
          </button>
        )}
      </div>

      <div className="flex flex-col divide-y divide-[var(--rule-soft)] rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
        {top5.map((c, i) => {
          const pct = (c.investimento ?? 0) / maxInv;
          return (
            <div key={i} className="grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-3">
              <div className="min-w-0">
                <p className="font-display truncate text-base text-[var(--ink)]">{c.nome}</p>
                <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--paper-deep)]">
                  <motion.div
                    className="h-full origin-left bg-[var(--forest)]"
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
              <p className="font-mono-num text-base text-[var(--ink)]">{fmtRoas(c.roas)}</p>
            </div>
          );
        })}
      </div>
    </RevealOnView>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/CampaignBars.tsx
git commit -m "feat(cliente-fe): CampaignBars (top 5 Google com barras de proporção)"
```

---

## Task 13: Componente DetailsDrawer (genérico)

**Files:**
- Create: `web/frontend/components/DetailsDrawer.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/DetailsDrawer.tsx`:

```tsx
"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
};

export default function DetailsDrawer({ open, onClose, title, children }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            aria-hidden
          />
          <motion.aside
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[720px] flex-col bg-[var(--paper)] shadow-2xl"
            role="dialog"
            aria-label={title}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.3, ease: [0.2, 0.7, 0.2, 1] }}
          >
            <header className="flex items-center justify-between border-b border-[var(--rule-soft)] px-6 py-4">
              <h2 className="font-display text-lg text-[var(--ink)]">{title}</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Fechar"
                className="rounded-full border border-[var(--rule-soft)] px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
              >
                Fechar
              </button>
            </header>
            <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/DetailsDrawer.tsx
git commit -m "feat(cliente-fe): DetailsDrawer (slide-in com ESC + backdrop + body-lock)"
```

---

## Task 14: Componente WelcomeSplash

**Files:**
- Create: `web/frontend/components/WelcomeSplash.tsx`

- [ ] **Step 1: Implementar**

Criar `web/frontend/components/WelcomeSplash.tsx`:

```tsx
"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import type { Highlight } from "@/lib/api-cliente";

type Props = {
  nomeCliente: string;
  highlight: Highlight | null;
  mesLabel: string;
  onDismiss: () => void;
};

const horaSaudacao = () => {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
};

const dataExtenso = () => {
  const d = new Date();
  const meses = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
  ];
  return `${d.getDate()} de ${meses[d.getMonth()]} · ${d.getFullYear()}`;
};

export default function WelcomeSplash({ nomeCliente, highlight, mesLabel, onDismiss }: Props) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setVisible(false), 3000);
    return () => clearTimeout(t);
  }, []);

  function handleDismiss() {
    setVisible(false);
  }

  return (
    <AnimatePresence onExitComplete={onDismiss}>
      {visible && (
        <motion.div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden bg-[var(--paper)] px-6"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
          onClick={handleDismiss}
          role="dialog"
          aria-label="Boas-vindas"
        >
          <div className="mesh-bg" />

          <motion.p
            className="eyebrow relative text-[10px] text-[var(--muted)]"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            {dataExtenso()} · {nomeCliente}
          </motion.p>

          <motion.h1
            className="font-display relative mt-3 max-w-4xl text-center font-light italic leading-[0.95] tracking-tight text-[var(--ink)] text-[56px] sm:text-[88px] lg:text-[128px]"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2, ease: [0.2, 0.7, 0.2, 1] }}
          >
            {horaSaudacao()}, {nomeCliente}.
          </motion.h1>

          <motion.p
            className="font-display relative mt-6 max-w-2xl text-center italic text-[var(--muted)] text-[18px] sm:text-[22px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.6 }}
          >
            {highlight?.message ?? `Aqui está sua performance de ${mesLabel}.`}
          </motion.p>

          <motion.button
            type="button"
            onClick={handleDismiss}
            className="absolute bottom-10 right-10 text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:text-[var(--ink)]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 1.2 }}
          >
            Continuar →
          </motion.button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/WelcomeSplash.tsx
git commit -m "feat(cliente-fe): WelcomeSplash (overlay com saudação + highlight + auto-dismiss)"
```

---

## Task 15: Componente LoginScene + atualizar página de login

**Files:**
- Create: `web/frontend/components/LoginScene.tsx`
- Modify: `web/frontend/app/cliente/login/page.tsx`

- [ ] **Step 1: Implementar LoginScene**

Criar `web/frontend/components/LoginScene.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiError, clienteApi } from "@/lib/api-cliente";

function maskCNPJ(v: string): string {
  const d = v.replace(/\D/g, "").slice(0, 14);
  if (d.length <= 2) return d;
  if (d.length <= 5) return `${d.slice(0, 2)}.${d.slice(2)}`;
  if (d.length <= 8) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5)}`;
  if (d.length <= 12) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8)}`;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

export default function LoginScene() {
  const router = useRouter();
  const search = useSearchParams();
  const meshRef = useRef<HTMLDivElement | null>(null);
  const [cnpj, setCnpj] = useState("");
  const [senha, setSenha] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(
    search.get("expired") ? "Sua sessão expirou. Entre novamente." : null,
  );

  // Paralaxe sutil no mouse
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!meshRef.current) return;
      const x = (e.clientX / window.innerWidth - 0.5) * 12;
      const y = (e.clientY / window.innerHeight - 0.5) * 12;
      meshRef.current.style.translate = `${x}px ${y}px`;
    }
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      await clienteApi.login(cnpj, senha);
      router.push("/cliente/dashboard?intro=1");
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : "Erro ao entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6">
      <div ref={meshRef} className="mesh-bg" style={{ transition: "translate 0.4s ease-out" }} />

      <div className="relative w-full max-w-sm">
        <h1 className="font-display mb-1 text-3xl font-light italic tracking-tight text-[var(--ink)]">
          Bem-vindo.
        </h1>
        <p className="mb-10 text-xs text-[var(--muted)]">
          Entre com o CNPJ para ver seus dados de performance.
        </p>

        <form onSubmit={onSubmit} className="flex flex-col gap-5">
          <label htmlFor="cnpj" className="flex flex-col gap-1.5">
            <span className="eyebrow text-[10px] text-[var(--muted)]">CNPJ</span>
            <input
              id="cnpj"
              inputMode="numeric"
              autoComplete="off"
              value={cnpj}
              onChange={(e) => setCnpj(maskCNPJ(e.target.value))}
              placeholder="00.000.000/0000-00"
              className="border-b border-[var(--rule-soft)] bg-transparent py-2 text-base text-[var(--ink)] placeholder:font-display placeholder:italic placeholder:text-[var(--muted)] focus:border-[var(--forest)] focus:outline-none"
            />
          </label>

          <label htmlFor="senha" className="flex flex-col gap-1.5">
            <span className="eyebrow text-[10px] text-[var(--muted)]">Senha</span>
            <input
              id="senha"
              type="password"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className="border-b border-[var(--rule-soft)] bg-transparent py-2 text-base text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none"
            />
          </label>

          {err && (
            <p role="alert" className="text-xs text-[var(--crimson)]">
              {err}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || cnpj.replace(/\D/g, "").length < 11 || senha.length === 0}
            className="mt-6 rounded-full border border-[var(--forest)] px-6 py-2.5 text-[11px] uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Atualizar a página /cliente/login para usar LoginScene**

Substituir o conteúdo de `web/frontend/app/cliente/login/page.tsx` por:

```tsx
"use client";

import { Suspense } from "react";

import LoginScene from "@/components/LoginScene";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center">
          <p className="text-sm text-[var(--muted)]">Carregando…</p>
        </main>
      }
    >
      <LoginScene />
    </Suspense>
  );
}
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -5
git add web/frontend/components/LoginScene.tsx web/frontend/app/cliente/login/page.tsx
git commit -m "feat(cliente-fe): LoginScene cinemático (mesh + paralaxe + redirect com intro)"
```

---

## Task 16: Reescrever a página /cliente/dashboard

**Files:**
- Modify: `web/frontend/app/cliente/dashboard/page.tsx` (substituir conteúdo)

- [ ] **Step 1: Reescrever o page.tsx**

Substituir TODO o conteúdo de `web/frontend/app/cliente/dashboard/page.tsx` por:

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  ApiError,
  Breakdown,
  ClientePublic,
  Highlight,
  TimelineItem,
  clienteApi,
} from "@/lib/api-cliente";

import CampaignBars from "@/components/CampaignBars";
import CreativeGallery from "@/components/CreativeGallery";
import DetailsDrawer from "@/components/DetailsDrawer";
import EvolutionChartHero from "@/components/EvolutionChartHero";
import HeroMonth from "@/components/HeroMonth";
import KpiRow from "@/components/KpiRow";
import WelcomeSplash from "@/components/WelcomeSplash";

const NOMES_MES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

function mesLabel(mes: string): string {
  if (!mes) return "";
  const [a, m] = mes.split("-");
  return `${NOMES_MES[parseInt(m) - 1]} ${a}`;
}

const fmtBRL = (v: number | null) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtInt = (v: number | null) => (v == null ? "—" : v.toLocaleString("pt-BR"));

export default function ClienteDashboardPage() {
  const router = useRouter();
  const search = useSearchParams();
  const wantIntro = search.get("intro") === "1";

  const [cliente, setCliente] = useState<ClientePublic | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const [mesesDisponiveis, setMesesDisponiveis] = useState<string[]>([]);
  const [mes, setMes] = useState<string>("");
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [showSplash, setShowSplash] = useState(false);
  const [drawerMeta, setDrawerMeta] = useState(false);
  const [drawerGoogle, setDrawerGoogle] = useState(false);

  useEffect(() => {
    Promise.all([
      clienteApi.me(),
      clienteApi.timeline(12),
      clienteApi.mesesDisponiveis(),
      clienteApi.highlight().catch(() => ({ highlight: null })),
    ])
      .then(([me, tl, md, hl]) => {
        setCliente(me);
        setTimeline(tl.items);
        setMesesDisponiveis(md.meses);
        setHighlight(hl.highlight);
        if (md.meses.length > 0) setMes(md.meses[0]);

        if (wantIntro) {
          const today = new Date().toISOString().slice(0, 10);
          const key = `splash-seen-${today}`;
          if (typeof window !== "undefined" && !localStorage.getItem(key)) {
            setShowSplash(true);
            localStorage.setItem(key, "1");
          }
          // Limpa query param ?intro=1
          router.replace("/cliente/dashboard");
        }
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) {
          router.push("/cliente/login?expired=1");
          return;
        }
        setErr(e instanceof Error ? e.message : "Erro ao carregar dados.");
      })
      .finally(() => setLoading(false));
  }, [router, wantIntro]);

  useEffect(() => {
    if (!mes) return;
    clienteApi.breakdown(mes).then(setBreakdown).catch(() => setBreakdown(null));
  }, [mes]);

  const snapMes = useMemo(() => timeline.find((i) => i.mes === mes) ?? null, [timeline, mes]);

  // Sparks de 6 meses para KPIs secundários
  const last6 = useMemo(() => timeline.slice(-6), [timeline]);

  async function handleLogout() {
    await clienteApi.logout().catch(() => {});
    router.push("/cliente/login");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="font-display text-xl italic text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  if (err) {
    return (
      <main className="mx-auto max-w-md px-6 py-12">
        <p className="text-sm text-[var(--crimson)]">{err}</p>
      </main>
    );
  }

  const metaAds = breakdown?.meta_ads ?? [];
  const googleAds = breakdown?.google_ads ?? [];

  const kpis = snapMes
    ? [
        {
          label: "Investimento",
          value: fmtBRL(snapMes.investimento),
          spark: last6.map((p) => p.investimento ?? 0),
          varPct: null,
        },
        {
          label: "CPA",
          value: fmtBRL(snapMes.cpa),
          spark: last6.map((p) => p.cpa ?? 0),
          varPct: null,
        },
        {
          label: "Leads",
          value: fmtInt(snapMes.leads),
          spark: last6.map((p) => p.leads ?? 0),
          varPct: null,
        },
        {
          label: "Vendas",
          value: fmtInt(snapMes.vendas),
          spark: last6.map((p) => p.vendas ?? 0),
          varPct: null,
        },
      ]
    : [];

  return (
    <>
      {showSplash && cliente && (
        <WelcomeSplash
          nomeCliente={cliente.nome}
          highlight={highlight}
          mesLabel={mesLabel(mes)}
          onDismiss={() => setShowSplash(false)}
        />
      )}

      <main className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-12 flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {cliente?.logo_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={cliente.logo_url}
                alt={cliente.nome}
                className="h-9 w-9 rounded object-contain"
              />
            )}
            <div>
              <p className="font-display text-base text-[var(--ink)]">{cliente?.nome ?? "Cliente"}</p>
              <p className="eyebrow text-[10px] text-[var(--muted)]">
                {cliente?.setor ?? cliente?.categoria}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {mesesDisponiveis.length > 0 && (
              <select
                aria-label="Mês"
                value={mes}
                onChange={(e) => setMes(e.target.value)}
                className="select font-display text-base"
              >
                {mesesDisponiveis.map((m) => (
                  <option key={m} value={m}>
                    {mesLabel(m)}
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={handleLogout}
              className="rounded-full border border-[var(--rule-soft)] px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
            >
              Sair
            </button>
          </div>
        </header>

        {!snapMes ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
            Seus dados estão sendo processados. Volte em breve.
          </p>
        ) : (
          <HeroMonth
            mesLabel={mesLabel(mes)}
            faturamento={snapMes.faturamento}
            roas={snapMes.roas}
            varFaturamento={snapMes.faturamento_var_pct}
            varRoas={snapMes.roas_var_pct}
            timeline12m={timeline.map((p) => ({ mes: p.mes, faturamento: p.faturamento }))}
          />
        )}

        {kpis.length > 0 && <KpiRow kpis={kpis} />}

        {timeline.length >= 2 && <EvolutionChartHero timeline={timeline} />}

        <CreativeGallery criativos={metaAds} onSeeAll={() => setDrawerMeta(true)} />
        <CampaignBars campanhas={googleAds} onSeeAll={() => setDrawerGoogle(true)} />

        <footer className="mt-24 border-t border-[var(--rule-soft)] pt-6 text-center">
          <p className="eyebrow text-[10px] text-[var(--muted)]">
            Relatório gerado em {new Date().toLocaleDateString("pt-BR")}
          </p>
        </footer>
      </main>

      <DetailsDrawer
        open={drawerMeta}
        onClose={() => setDrawerMeta(false)}
        title={`Todos os criativos · Meta Ads · ${mesLabel(mes)}`}
      >
        <FullMetaTable ads={metaAds} />
      </DetailsDrawer>

      <DetailsDrawer
        open={drawerGoogle}
        onClose={() => setDrawerGoogle(false)}
        title={`Todas as campanhas · Google Ads · ${mesLabel(mes)}`}
      >
        <FullGoogleTable ads={googleAds} />
      </DetailsDrawer>
    </>
  );
}

// === Tabelas completas usadas dentro do Drawer ===

function FullMetaTable({ ads }: { ads: any[] }) {
  if (ads.length === 0) return <p className="text-xs text-[var(--muted)]">Sem dados.</p>;
  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-[var(--paper)]">
        <tr className="border-b border-[var(--rule-soft)]">
          <th className="py-2 pr-3 text-left font-medium text-[var(--muted)]">Criativo</th>
          <th className="py-2 pr-3 text-left font-medium text-[var(--muted)]">Anúncio</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Leads</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Conv.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Fat.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
          <th className="py-2 text-right font-medium text-[var(--muted)]">Impressões</th>
        </tr>
      </thead>
      <tbody>
        {ads.map((ad, i) => (
          <tr key={i} className="border-b border-[var(--rule-soft)]/40 hover:bg-[var(--paper-soft)]">
            <td className="py-2 pr-3">
              {ad.imagem_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={ad.imagem_url} alt={ad.nome} className="h-10 w-10 rounded object-cover" />
              ) : (
                <div className="h-10 w-10 rounded bg-[var(--paper-deep)]" />
              )}
            </td>
            <td className="py-2 pr-3 text-[var(--ink)]">{ad.nome}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.investimento == null ? "—" : ad.investimento.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.leads ?? "—"}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.conversoes ?? "—"}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.faturamento == null ? "—" : ad.faturamento.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.roas == null ? "—" : `${ad.roas.toFixed(2).replace(".", ",")}×`}
            </td>
            <td className="py-2 text-right font-mono-num text-[var(--ink)]">
              {ad.impressoes == null ? "—" : ad.impressoes.toLocaleString("pt-BR")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FullGoogleTable({ ads }: { ads: any[] }) {
  if (ads.length === 0) return <p className="text-xs text-[var(--muted)]">Sem dados.</p>;
  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-[var(--paper)]">
        <tr className="border-b border-[var(--rule-soft)]">
          <th className="py-2 pr-3 text-left font-medium text-[var(--muted)]">Campanha</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Conv.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Fat.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">CPA</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
          <th className="py-2 text-right font-medium text-[var(--muted)]">Impressões</th>
        </tr>
      </thead>
      <tbody>
        {ads.map((ad, i) => (
          <tr key={i} className="border-b border-[var(--rule-soft)]/40 hover:bg-[var(--paper-soft)]">
            <td className="py-2 pr-3 text-[var(--ink)]">{ad.nome}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.investimento == null ? "—" : ad.investimento.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.conversoes ?? "—"}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.faturamento == null ? "—" : ad.faturamento.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.cpa == null ? "—" : ad.cpa.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.roas == null ? "—" : `${ad.roas.toFixed(2).replace(".", ",")}×`}
            </td>
            <td className="py-2 text-right font-mono-num text-[var(--ink)]">
              {ad.impressoes == null ? "—" : ad.impressoes.toLocaleString("pt-BR")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 2: Typecheck**

Run:
```bash
cd web/frontend && npx tsc --noEmit 2>&1 | tail -10
```

Expected: sem erros.

- [ ] **Step 3: Build de produção para garantir que tudo compila**

Run:
```bash
cd web/frontend && npm run build 2>&1 | tail -25
```

Expected: build conclui. Aviso sobre tamanho do bundle pra rota `/cliente/dashboard` é esperado.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/cliente/dashboard/page.tsx
git commit -m "feat(cliente-fe): reescrever dashboard com componentes cinemáticos"
```

---

## Task 17: Atualizar testes E2E Playwright

**Files:**
- Modify: `web/frontend/tests/e2e/cliente-dashboard.spec.ts`
- Modify: `web/frontend/tests/e2e/cliente-login.spec.ts`

- [ ] **Step 1: Reescrever cliente-dashboard.spec.ts**

Substituir TODO o conteúdo de `web/frontend/tests/e2e/cliente-dashboard.spec.ts` por:

```typescript
import { test, expect, Page } from "@playwright/test";

const CNPJ_SEED = "00000000000001";

async function login(page: Page) {
  await page.goto("/cliente/login");
  await page.getByLabel("CNPJ").fill(CNPJ_SEED);
  await page.getByLabel("Senha").fill("Warley20192020");
  await page.getByRole("button", { name: /entrar/i }).click();
  // Aceita ?intro=1 ou /cliente/dashboard
  await page.waitForURL((url) => url.pathname === "/cliente/dashboard");
}

test.describe("Cliente dashboard (cinemático)", () => {
  test("splash aparece na primeira vez do dia e some no clique", async ({ page, context }) => {
    await context.clearCookies();
    await page.addInitScript(() => localStorage.clear());
    await login(page);

    // Splash com "Boa tarde/dia/noite, ..." pode aparecer
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    // Se houver dados, splash aparece; clica para pular
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) {
      await splash.click();
      await expect(splash).toBeHidden({ timeout: 2000 });
    }
  });

  test("hero de faturamento aparece com dados ou mensagem 'processando'", async ({ page }) => {
    await login(page);
    // Pula splash se houver
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) await splash.click();

    // OU vemos o hero, OU vemos a mensagem de "processando"
    const hero = page.getByText("Faturamento ·", { exact: false }).first();
    const empty = page.getByText(/dados estão sendo processados/i);
    await expect(hero.or(empty)).toBeVisible({ timeout: 5000 });
  });

  test("seletor de mês continua funcionando", async ({ page }) => {
    await login(page);
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) await splash.click();

    const select = page.getByLabel("Mês");
    if (await select.isVisible()) {
      const options = await select.locator("option").allTextContents();
      if (options.length > 1) {
        await select.selectOption({ index: 1 });
      }
    }
  });

  test("drawer 'ver todos' abre e fecha (se houver criativos)", async ({ page }) => {
    await login(page);
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) await splash.click();

    const verTodos = page.getByRole("button", { name: /ver todos os/i }).first();
    if (await verTodos.isVisible().catch(() => false)) {
      await verTodos.click();
      const drawer = page.getByRole("dialog", { name: /Todos os criativos/i });
      await expect(drawer).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(drawer).toBeHidden({ timeout: 1000 });
    }
  });

  test("botão Sair redireciona para login e limpa cookie", async ({ page, context }) => {
    await login(page);
    const splash = page.getByRole("dialog", { name: /Boas-vindas/i });
    if (await splash.isVisible({ timeout: 1500 }).catch(() => false)) await splash.click();

    await page.getByRole("button", { name: /sair/i }).click();
    await page.waitForURL("**/cliente/login");
    const cookies = await context.cookies();
    expect(cookies.find((c) => c.name === "cliente_token")).toBeUndefined();
  });
});
```

- [ ] **Step 2: Atualizar cliente-login.spec.ts**

Em `web/frontend/tests/e2e/cliente-login.spec.ts`, garantir que o teste existente continua passando — o seletor que mudou é o título. Ler o arquivo primeiro:

```bash
cat web/frontend/tests/e2e/cliente-login.spec.ts
```

Se houver `getByRole("heading", { name: /Área do Cliente/i })`, trocar por `getByRole("heading", { name: /Bem-vindo/i })`. Se houver `getByText("Área do Cliente")`, trocar por `getByText("Bem-vindo.")`.

- [ ] **Step 3: Rodar a suíte Playwright contra um backend local**

Pré-requisito: backend rodando em `http://localhost:8765` e seed_dev aplicado.

Run:
```bash
cd web/frontend && npm run test:e2e 2>&1 | tail -25
```

Expected: testes passam. Se algum falhar por timing (animações), aumentar `timeout` específico do teste, não desligar o teste.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/tests/e2e/cliente-dashboard.spec.ts web/frontend/tests/e2e/cliente-login.spec.ts
git commit -m "test(cliente-fe): cobrir splash, drawer e novo header do dashboard"
```

---

## Task 18: Smoke test visual no browser

**Files:** nenhum (verificação manual)

- [ ] **Step 1: Subir o backend localmente**

Em um terminal separado:
```bash
cd web/backend && uvicorn main:app --port 8765 --reload
```

Confirmar que sobe sem erro.

- [ ] **Step 2: Subir o frontend em dev**

Em outro terminal:
```bash
cd web/frontend && npm run dev
```

Esperar `Ready` na saída.

- [ ] **Step 3: Verificar no navegador**

Abrir http://localhost:3000/cliente/login e verificar:

- [ ] Background tem gradient mesh visível e animado lentamente
- [ ] Cursor move levemente o mesh (paralaxe)
- [ ] Inputs sublinhados (não com border completo)
- [ ] Login com seed (`00000000000001` / `Warley20192020`) leva ao splash
- [ ] Splash mostra "Boa tarde/dia/noite, {nome}" em Fraunces italic gigante
- [ ] Splash some sozinho em ~3s ou no clique
- [ ] Dashboard mostra hero com Faturamento gigante animando de 0 ao valor
- [ ] KPIs em linha (4 colunas em desktop)
- [ ] Gráfico de evolução com área preenchida + toggle de métrica
- [ ] Criativos como cards 16:9 com hover de zoom
- [ ] Barras de campanhas Google animam o `scaleX`
- [ ] "Ver todos" abre drawer lateral
- [ ] ESC fecha o drawer
- [ ] Recarregar com `?intro=1` na mesma data NÃO mostra splash (localStorage)
- [ ] Toggle dark mode (se existir): tudo continua elegante

- [ ] **Step 4: Testar reduced-motion**

No DevTools do Chrome:
- Cmd+Shift+P → "Show Rendering"
- Em "Emulate CSS media feature prefers-reduced-motion", selecionar "reduce"
- Recarregar `/cliente/dashboard?intro=1` e verificar:
  - [ ] Splash aparece e some sem animação de fade
  - [ ] Números aparecem em estado final imediatamente
  - [ ] Gráfico não anima desenho
  - [ ] Cards aparecem sem cascata

- [ ] **Step 5: Testar mobile (375 px)**

DevTools → device toolbar → iPhone SE (375px):
- [ ] Hero do mês fica legível (não estoura)
- [ ] KPIs viram grid 2x2
- [ ] Criativos viram carrossel horizontal scroll-snap
- [ ] Drawer fica full-width
- [ ] Nada quebrado

- [ ] **Step 6: Se houver problemas, corrigir e commitar**

Se algum item acima falhou, fazer fix focado no problema e commitar individualmente. Não acumular mudanças não-relacionadas em um commit.

---

## Self-Review

**Checklist contra a spec:**

| Spec section | Implementado em |
|---|---|
| Direção visual editorial cinemático | Tasks 1, 8, 14, 15 |
| Login com mesh + paralaxe + sem chrome | Task 15 |
| Splash com saudação, highlight, skip 1x/dia | Tasks 4, 14, 16 (lógica do skip em 16) |
| Hero do mês com Counter | Tasks 5, 8 |
| KPIs secundários com mini-sparks | Task 9 |
| EvolutionChart full-width com toggle | Tasks 7, 10 |
| Top criativos Meta como galeria | Task 11 |
| Top campanhas Google com barras | Task 12 |
| Drawer "ver todos" | Tasks 13, 16 |
| Endpoint /highlight com heurísticas | Tasks 2, 3 |
| `prefers-reduced-motion` | Tasks 1, 5, 6 (e Task 18 verifica) |
| Dark mode preservado | Task 1 (vars CSS) + verificação em 18 |
| Mobile responsivo | Tasks 9, 11 + verificação em 18 |
| Estados vazios | Tasks 8, 11, 12, 16 |
| Tabela completa no drawer | Task 16 (`FullMetaTable` / `FullGoogleTable`) |
| Footer "Relatório gerado em…" | Task 16 |
| Testes backend | Tasks 2, 3 |
| Testes E2E frontend | Task 17 |
