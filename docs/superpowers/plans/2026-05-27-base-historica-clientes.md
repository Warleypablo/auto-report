# Base Histórica de Clientes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar endpoint de backfill que roda o ETL mês a mês para todos os clientes (ativos e inativos), e uma view admin que exibe a cobertura de snapshots por cliente × mês com botão de trigger.

**Architecture:** Nova função `backfill_clientes_meses` em `etl/collect.py` chama `run_etl` sequencialmente para cada mês do intervalo, com slugs extraídos do banco de dados. Background thread em `api/gestor.py` com estado em dict `_backfill_jobs`. Frontend exibe matriz de cobertura e controles de trigger.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, threading, Next.js 14, Tailwind CSS, Pydantic v2.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---------|------|------------------|
| `web/backend/etl/collect.py` | Modificar | Adicionar `backfill_clientes_meses()` |
| `web/backend/schemas/gestor.py` | Modificar | Adicionar `BackfillRequest`, `BackfillResponse`, `BackfillJobStatusResponse`, `CoberturaClienteItem`, `CoberturaResponse` |
| `web/backend/schemas/__init__.py` | Modificar | Exportar novos schemas |
| `web/backend/api/gestor.py` | Modificar | Adicionar `_backfill_jobs`, 3 endpoints novos, imports de `Snapshot`/`date` |
| `web/frontend/lib/api-gestor.ts` | Modificar | Adicionar tipos `CoberturaCliente`, `BackfillJobStatus` e métodos `triggerBackfill`, `getBackfillJob`, `cobertura` |
| `web/frontend/app/gestor/admin/historico/page.tsx` | Criar | Página admin com matriz de cobertura e controles de backfill |

---

### Task 1: Função `backfill_clientes_meses` em `etl/collect.py`

**Files:**
- Modify: `web/backend/etl/collect.py`

**Contexto:** `run_etl` já existe e retorna `{"ok": int, "fail": int, "total": int}` ou `{"skipped": True}` se o advisory lock estiver ocupado. Para o backfill histórico de mês `YYYY-MM`, passar `today=date(YYYY, MM+1, 1)` faz `periodo_referencia` retornar aquele mês como período de referência.

- [ ] **Step 1: Adicionar `backfill_clientes_meses` ao final do arquivo**

Adicione no final de `web/backend/etl/collect.py` (após a função `run_etl`):

```python
def backfill_clientes_meses(
    mes_inicio: str,
    mes_fim: str,
    slug: str | None = None,
    progress_callback: "Callable[[int, int, int], None] | None" = None,
) -> dict:
    """Roda ETL para um intervalo de meses usando slugs do banco de dados.

    Para cada mês do intervalo, chama run_etl com today=1º dia do mês seguinte,
    o que faz periodo_referencia retornar o mês-alvo como período de referência.

    Args:
        mes_inicio: "YYYY-MM" (inclusive)
        mes_fim:    "YYYY-MM" (inclusive)
        slug:       se fornecido, processa apenas esse cliente
        progress_callback: chamado após cada mês com (concluidos, total, erros)

    Returns:
        {"meses_processados": int, "meses_com_erro": list[str], "ok": int, "fail": int}
    """
    import time

    def _next_month(ano: int, mes: int) -> tuple[int, int]:
        return (ano + 1, 1) if mes == 12 else (ano, mes + 1)

    ano_i, mes_i = int(mes_inicio[:4]), int(mes_inicio[5:])
    ano_f, mes_f = int(mes_fim[:4]), int(mes_fim[5:])

    meses: list[tuple[int, int]] = []
    ano, mes = ano_i, mes_i
    while (ano, mes) <= (ano_f, mes_f):
        meses.append((ano, mes))
        ano, mes = _next_month(ano, mes)

    # Slugs a processar — do banco, não da planilha
    if slug:
        slugs: set[str] = {slug}
    else:
        with SessionLocal() as session:
            slugs = set(session.execute(select(Cliente.slug)).scalars().all())

    resultados: dict = {
        "meses_processados": 0,
        "meses_com_erro": [],
        "ok": 0,
        "fail": 0,
    }

    for i, (ano_m, mes_m) in enumerate(meses):
        ano_next, mes_next = _next_month(ano_m, mes_m)
        today_ref = date(ano_next, mes_next, 1)
        mes_str = f"{ano_m:04d}-{mes_m:02d}"

        try:
            result = run_etl(today=today_ref, slugs=slugs, incluir_privados=True)
            if result.get("skipped"):
                # Lock ocupado — aguarda e retenta uma vez
                time.sleep(5)
                result = run_etl(today=today_ref, slugs=slugs, incluir_privados=True)
            resultados["ok"] += result.get("ok", 0)
            resultados["fail"] += result.get("fail", 0)
        except Exception:
            log.exception("backfill_mes_falhou", extra={"mes": mes_str})
            resultados["meses_com_erro"].append(mes_str)
            resultados["fail"] += 1

        resultados["meses_processados"] += 1
        if progress_callback:
            progress_callback(
                i + 1,
                len(meses),
                len(resultados["meses_com_erro"]),
            )

    return resultados
```

- [ ] **Step 2: Verificar sintaxe**

```bash
cd web/backend && python -c "from etl.collect import backfill_clientes_meses; print('OK')"
```

Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
git add web/backend/etl/collect.py
git commit -m "feat(etl): adicionar backfill_clientes_meses para histórico de clientes"
```

---

### Task 2: Schemas Pydantic em `schemas/gestor.py` e `schemas/__init__.py`

**Files:**
- Modify: `web/backend/schemas/gestor.py`
- Modify: `web/backend/schemas/__init__.py`

- [ ] **Step 1: Adicionar schemas ao final de `schemas/gestor.py`**

Adicione ao final do arquivo `web/backend/schemas/gestor.py`:

```python
class BackfillRequest(BaseModel):
    mes_inicio: str  # YYYY-MM
    mes_fim: str     # YYYY-MM
    slug: str | None = None


class BackfillResponse(BaseModel):
    job_id: str
    meses: int
    clientes: int


class BackfillJobStatusResponse(BaseModel):
    job_id: str
    status: str  # running | done | error
    meses_total: int
    meses_concluidos: int
    erros: int
    pct: int  # 0-100


class CoberturaClienteItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    nome: str
    ativo: bool
    meses_com_snapshot: list[str]


class CoberturaResponse(BaseModel):
    meses: list[str]
    clientes: list[CoberturaClienteItem]
```

- [ ] **Step 2: Exportar em `schemas/__init__.py`**

Adicione os imports na seção `from .gestor import (...)` existente:

```python
from .gestor import (
    # ... imports existentes ...
    BackfillRequest,
    BackfillResponse,
    BackfillJobStatusResponse,
    CoberturaClienteItem,
    CoberturaResponse,
    # ... resto dos imports existentes ...
)
```

E adicione ao `__all__`:
```python
"BackfillJobStatusResponse",
"BackfillRequest",
"BackfillResponse",
"CoberturaClienteItem",
"CoberturaResponse",
```

- [ ] **Step 3: Verificar importação**

```bash
cd web/backend && python -c "from schemas import BackfillRequest, CoberturaResponse; print('OK')"
```

Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add web/backend/schemas/gestor.py web/backend/schemas/__init__.py
git commit -m "feat(schemas): adicionar schemas de backfill e cobertura histórica"
```

---

### Task 3: Endpoints em `api/gestor.py`

**Files:**
- Modify: `web/backend/api/gestor.py`

**Contexto:** O arquivo já usa `threading.Thread` com semáforo para jobs de relatório (padrão em torno da linha 989). Seguir o mesmo padrão. O `_MES_RE` já existe para validar formato `YYYY-MM`.

- [ ] **Step 1: Adicionar imports necessários no topo de `api/gestor.py`**

Na linha de `from datetime import datetime, timedelta, timezone`, adicionar `date`:

```python
from datetime import date, datetime, timedelta, timezone
```

Após `from models import Cliente, GestorCadastrado, Insight, ReportJob, Usuario, UsuarioCliente`, adicionar:

```python
from models.snapshot import Snapshot
from models.snapshot import Frequencia as SnapFrequencia
```

Na linha `from schemas import (`, adicionar os novos schemas:

```python
    BackfillJobStatusResponse,
    BackfillRequest,
    BackfillResponse,
    CoberturaClienteItem,
    CoberturaResponse,
```

- [ ] **Step 2: Adicionar `_backfill_jobs` próximo dos outros estados de módulo**

Após a linha `_JOB_SEMAPHORE = threading.BoundedSemaphore(_MAX_CONCURRENT_JOBS)`, adicionar:

```python
# Estado em memória para jobs de backfill histórico.
# Suficiente para uso esporádico por admins — não persiste entre reinicializações.
_backfill_jobs: dict[str, dict] = {}
```

- [ ] **Step 3: Adicionar os 3 endpoints admin no final da seção admin (após o último endpoint `DELETE /admin/usuarios/{usuario_id}/clientes/{cliente_id}`)**

```python
# ── Base histórica / Backfill ETL ────────────────────────────────────────────

@router.post("/admin/etl/backfill", status_code=202, response_model=BackfillResponse)
def trigger_backfill(
    body: BackfillRequest,
    user: Usuario = Depends(require_admin),
):
    """Dispara backfill ETL para um intervalo de meses em background."""
    if not _MES_RE.match(body.mes_inicio) or not _MES_RE.match(body.mes_fim):
        raise HTTPException(400, "mes_inicio e mes_fim devem estar no formato YYYY-MM")
    if body.mes_inicio > body.mes_fim:
        raise HTTPException(400, "mes_inicio deve ser <= mes_fim")

    ano_i, mes_i = int(body.mes_inicio[:4]), int(body.mes_inicio[5:])
    ano_f, mes_f = int(body.mes_fim[:4]), int(body.mes_fim[5:])
    meses_total = (ano_f - ano_i) * 12 + (mes_f - mes_i) + 1
    if meses_total > 36:
        raise HTTPException(400, "Intervalo máximo de 36 meses")

    with SessionLocal() as session:
        if body.slug:
            n_clientes = 1
        else:
            n_clientes = session.execute(select(func.count(Cliente.id))).scalar_one()

    job_id = str(uuid.uuid4())
    _backfill_jobs[job_id] = {
        "status": "running",
        "meses_total": meses_total,
        "meses_concluidos": 0,
        "erros": 0,
        "pct": 0,
    }

    def _run() -> None:
        def _progress(concluidos: int, total: int, erros: int) -> None:
            _backfill_jobs[job_id]["meses_concluidos"] = concluidos
            _backfill_jobs[job_id]["erros"] = erros
            _backfill_jobs[job_id]["pct"] = int(concluidos / total * 100) if total else 0

        try:
            from etl.collect import backfill_clientes_meses
            backfill_clientes_meses(
                mes_inicio=body.mes_inicio,
                mes_fim=body.mes_fim,
                slug=body.slug,
                progress_callback=_progress,
            )
            _backfill_jobs[job_id]["status"] = "done"
            _backfill_jobs[job_id]["pct"] = 100
        except Exception:
            _log.exception("[backfill %s] FALHOU", job_id)
            _backfill_jobs[job_id]["status"] = "error"

    threading.Thread(target=_run, daemon=False).start()

    return BackfillResponse(job_id=job_id, meses=meses_total, clientes=n_clientes)


@router.get("/admin/etl/backfill/{job_id}", response_model=BackfillJobStatusResponse)
def get_backfill_status(
    job_id: str,
    user: Usuario = Depends(require_admin),
):
    """Retorna o status de um job de backfill em andamento."""
    job = _backfill_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return BackfillJobStatusResponse(job_id=job_id, **job)


@router.get("/admin/cobertura", response_model=CoberturaResponse)
def get_cobertura(
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retorna matriz de cobertura: para cada cliente, quais meses têm snapshot."""
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    meses: list[str] = []
    for _ in range(36):
        meses.insert(0, f"{ano:04d}-{mes:02d}")
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1

    clientes = session.execute(
        select(Cliente).order_by(Cliente.nome)
    ).scalars().all()

    from collections import defaultdict
    snaps = session.execute(
        select(Snapshot.cliente_id, Snapshot.periodo_inicio)
        .where(Snapshot.frequencia == SnapFrequencia.MENSAL)
    ).all()

    meses_por_cliente: dict[uuid.UUID, set[str]] = defaultdict(set)
    for s in snaps:
        meses_por_cliente[s.cliente_id].add(s.periodo_inicio.strftime("%Y-%m"))

    return CoberturaResponse(
        meses=meses,
        clientes=[
            CoberturaClienteItem(
                id=c.id,
                slug=c.slug,
                nome=c.nome,
                ativo=c.ativo,
                meses_com_snapshot=sorted(meses_por_cliente.get(c.id, set())),
            )
            for c in clientes
        ],
    )
```

- [ ] **Step 4: Verificar sintaxe**

```bash
cd web/backend && python -c "from api.gestor import router; print('OK')"
```

Esperado: `OK`

- [ ] **Step 5: Verificar que o servidor sobe**

```bash
cd web/backend && uvicorn main:app --port 8001 --no-access-log &
sleep 3
curl -s http://localhost:8001/health | python3 -c "import sys,json; print(json.load(sys.stdin))"
kill %1
```

Esperado: objeto JSON com status ok.

- [ ] **Step 6: Commit**

```bash
git add web/backend/api/gestor.py
git commit -m "feat(api): endpoints de backfill ETL e cobertura histórica"
```

---

### Task 4: Tipos e métodos em `lib/api-gestor.ts`

**Files:**
- Modify: `web/frontend/lib/api-gestor.ts`

- [ ] **Step 1: Adicionar tipos após os tipos existentes**

Adicione antes da função `apiCall` em `web/frontend/lib/api-gestor.ts`:

```typescript
export type CoberturaCliente = {
  id: string;
  slug: string;
  nome: string;
  ativo: boolean;
  meses_com_snapshot: string[];
};

export type CoberturaResponse = {
  meses: string[];
  clientes: CoberturaCliente[];
};

export type BackfillJobStatus = {
  job_id: string;
  status: "running" | "done" | "error";
  meses_total: number;
  meses_concluidos: number;
  erros: number;
  pct: number;
};
```

- [ ] **Step 2: Adicionar métodos em `gestorApi`**

Dentro do objeto `gestorApi`, após o método `generateInteligencia`, adicione:

```typescript
  triggerBackfill: (params: { mes_inicio: string; mes_fim: string; slug?: string }) =>
    apiCall<{ job_id: string; meses: number; clientes: number }>(
      "admin/etl/backfill",
      "POST",
      params,
    ),

  getBackfillJob: (job_id: string) =>
    apiCall<BackfillJobStatus>(`admin/etl/backfill/${job_id}`),

  cobertura: () =>
    apiCall<CoberturaResponse>("admin/cobertura"),
```

- [ ] **Step 3: Verificar compilação TypeScript**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | head -20
```

Esperado: sem erros relacionados a `api-gestor.ts`.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/lib/api-gestor.ts
git commit -m "feat(frontend): tipos e métodos de API para backfill e cobertura histórica"
```

---

### Task 5: Página `/gestor/admin/historico/page.tsx`

**Files:**
- Create: `web/frontend/app/gestor/admin/historico/page.tsx`

**Contexto:** O padrão das páginas admin existentes em `app/gestor/admin/usuarios/page.tsx` usa `gestorApi` direto, `useState`, e `max-w-*` no `<main>`. Esta página usa `GestorShell` (criado em `app/gestor/_shell.tsx`) e exibe uma matriz de cobertura com scrollagem horizontal.

- [ ] **Step 1: Criar o arquivo da página**

Crie `web/frontend/app/gestor/admin/historico/page.tsx` com o seguinte conteúdo:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import GestorShell from "../../_shell";
import { gestorApi } from "@/lib/api-gestor";
import type { BackfillJobStatus, CoberturaResponse } from "@/lib/api-gestor";

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]}/${ano.slice(2)}`;
}

function calcMesIntervalo(mesesAtras: number): { ini: string; fim: string } {
  const hoje = new Date();
  const fim = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}`;
  const d = new Date(hoje.getFullYear(), hoje.getMonth() - (mesesAtras - 1), 1);
  const ini = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  return { ini, fim };
}

export default function HistoricoAdminPage() {
  const [data, setData] = useState<CoberturaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [mostrarInativos, setMostrarInativos] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<BackfillJobStatus | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function load() {
    setLoading(true);
    gestorApi
      .cobertura()
      .then(setData)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!jobId) return;
    pollRef.current = setInterval(async () => {
      try {
        const status = await gestorApi.getBackfillJob(jobId);
        setJobStatus(status);
        if (status.status !== "running") {
          clearInterval(pollRef.current!);
          if (status.status === "done") load();
        }
      } catch {
        clearInterval(pollRef.current!);
      }
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [jobId]);

  async function dispararBackfill(slug?: string, nome?: string) {
    const msg = slug
      ? `Iniciar backfill dos últimos 36 meses para "${nome}"?`
      : "Iniciar backfill completo dos últimos 36 meses para todos os clientes?";
    if (!confirm(msg)) return;
    const { ini, fim } = calcMesIntervalo(36);
    try {
      const res = await gestorApi.triggerBackfill({ mes_inicio: ini, mes_fim: fim, slug });
      setJobId(res.job_id);
      setJobStatus({
        job_id: res.job_id,
        status: "running",
        meses_total: res.meses,
        meses_concluidos: 0,
        erros: 0,
        pct: 0,
      });
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao iniciar backfill");
    }
  }

  const meses24 = data?.meses.slice(-24) ?? [];
  const clientes = (data?.clientes ?? []).filter((c) => mostrarInativos || c.ativo);
  const rodando = jobStatus?.status === "running";

  return (
    <GestorShell>
      <main className="px-6 py-10">
        {/* Cabeçalho */}
        <div className="mb-8 flex items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-medium tracking-tight text-[var(--ink)]">
              Base Histórica
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Cobertura de snapshots por cliente e mês
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-xs text-[var(--muted)]">
              <input
                type="checkbox"
                checked={mostrarInativos}
                onChange={(e) => setMostrarInativos(e.target.checked)}
                className="accent-[var(--forest)]"
              />
              Mostrar inativos
            </label>
            <button
              onClick={() => dispararBackfill()}
              disabled={rodando}
              className="rounded-lg border border-[var(--forest)] px-4 py-1.5 text-xs text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:opacity-40"
            >
              Backfill completo
            </button>
          </div>
        </div>

        {/* Barra de progresso */}
        {jobStatus && (
          <div className="mb-6 rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
            <div className="mb-2 flex items-center justify-between text-xs">
              <span className="text-[var(--ink)]">
                {jobStatus.status === "running"
                  ? "Backfill em andamento…"
                  : jobStatus.status === "done"
                  ? "Backfill concluído"
                  : "Backfill com erro"}
              </span>
              <span className="text-[var(--muted)]">
                {jobStatus.meses_concluidos} de {jobStatus.meses_total} meses
                {jobStatus.erros > 0 && ` · ${jobStatus.erros} erros`}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
              <div
                className={`h-1.5 rounded-full transition-all ${
                  jobStatus.status === "error"
                    ? "bg-[var(--crimson)]"
                    : "bg-[var(--forest)]"
                }`}
                style={{ width: `${jobStatus.pct}%` }}
              />
            </div>
          </div>
        )}

        {erro && (
          <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>
        )}

        {loading ? (
          <p className="text-sm text-[var(--muted)]">Carregando…</p>
        ) : !data ? null : (
          <div className="overflow-x-auto rounded-xl border border-[var(--rule-soft)]">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                  <th className="sticky left-0 z-10 bg-[var(--paper-soft)] pb-2 pl-4 pr-6 pt-3 text-left text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap">
                    Cliente
                  </th>
                  {meses24.map((m) => (
                    <th
                      key={m}
                      className="pb-2 px-1 pt-3 text-center text-[10px] font-normal text-[var(--muted)] whitespace-nowrap"
                      style={{ minWidth: 38 }}
                    >
                      {mesLabel(m)}
                    </th>
                  ))}
                  <th className="pb-2 pl-2 pr-3 pt-3 w-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--rule-soft)]">
                {clientes.map((c) => {
                  const snaps = new Set(c.meses_com_snapshot);
                  const cobertura = meses24.filter((m) => snaps.has(m)).length;
                  return (
                    <tr key={c.id} className="group bg-[var(--paper)] hover:bg-[var(--paper-soft)]">
                      <td className="sticky left-0 z-10 bg-inherit py-2 pl-4 pr-6 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-[var(--ink)]">
                            {c.nome}
                          </span>
                          {!c.ativo && (
                            <span className="rounded bg-[var(--paper-deep)] px-1.5 py-0.5 text-[9px] text-[var(--muted)]">
                              inativo
                            </span>
                          )}
                          <span className="text-[10px] text-[var(--muted)]">
                            {cobertura}/{meses24.length}
                          </span>
                        </div>
                      </td>
                      {meses24.map((m) => (
                        <td key={m} className="px-1 py-2 text-center">
                          <span
                            className={`inline-block h-2 w-2 rounded-full ${
                              snaps.has(m)
                                ? "bg-[var(--forest)] opacity-70"
                                : "bg-[var(--paper-deep)]"
                            }`}
                          />
                        </td>
                      ))}
                      <td className="py-2 pl-2 pr-3">
                        <button
                          onClick={() => dispararBackfill(c.slug, c.nome)}
                          disabled={rodando}
                          title="Backfill deste cliente"
                          className="text-sm text-[var(--muted)] opacity-0 transition hover:text-[var(--forest)] group-hover:opacity-100 disabled:pointer-events-none"
                        >
                          ↺
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </GestorShell>
  );
}
```

- [ ] **Step 2: Verificar compilação TypeScript**

```bash
cd web/frontend && npx tsc --noEmit 2>&1 | head -30
```

Esperado: sem erros em `app/gestor/admin/historico/page.tsx`.

- [ ] **Step 3: Verificar que o dev server sobe sem erro**

```bash
cd web/frontend && npm run build 2>&1 | tail -20
```

Esperado: build sem erros de compilação.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/gestor/admin/historico/page.tsx
git commit -m "feat(frontend): página admin de cobertura histórica e backfill ETL"
```

---

## Self-Review

**Spec coverage:**
- ✅ `POST /api/gestor/admin/etl/backfill` — Task 3
- ✅ `GET /api/gestor/admin/etl/backfill/{job_id}` — Task 3
- ✅ `GET /api/gestor/admin/cobertura` — Task 3
- ✅ `backfill_clientes_meses` em `etl/collect.py` — Task 1
- ✅ Matriz de cobertura cliente × mês — Task 5
- ✅ Botão backfill completo + por cliente — Task 5
- ✅ Barra de progresso com polling — Task 5
- ✅ Toggle mostrar inativos — Task 5
- ✅ Máximo 36 meses — Task 3 (validação no endpoint)
- ✅ Estado em `_backfill_jobs` dict — Task 3

**Limites conhecidos:**
- Clientes removidos da planilha central não serão encontrados por `run_etl`, mesmo com seus slugs. Serão silenciosamente pulados.
- O dict `_backfill_jobs` não persiste entre reinicializações do servidor.
