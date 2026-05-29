# Report Week Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir escolher a semana de um report SEMANAL (semana útil seg→sex; default = semana vigente), corrigindo o bug em que o período semanal virava os dias 08–14 do mês seguinte ao selecionado.

**Architecture:** O período semanal deixa de derivar do `mes` (hack do dia 15) e passa a ser uma semana de calendário seg→sex. A lógica de resolução vira um helper puro testável (`_resolver_periodo_ref`). O trigger ganha um campo opcional `semana_inicio` (YYYY-MM-DD) que flui UI → API → `report_jobs` → `gerar_slides`. MENSAL fica inalterado.

**Tech Stack:** Python 3 / SQLAlchemy 2.x / Alembic / FastAPI / pytest (backend, venv `web/backend/.venv`); Next.js / TypeScript / Playwright (frontend). Interpretador: `web/backend/.venv/bin/python` (não há `python` no PATH). Postgres de teste: `vitrine_test`. Alembic head atual: `b1c2d3e4f5a6`.

---

## File Structure

**Backend**
- Modify `core/periodo.py` — `+semana_de()`, `+semana_vigente()`, `periodo_referencia(SEMANAL)` passa a usar semana vigente.
- Create `web/backend/tests/test_periodo.py` — unit das funções de semana.
- Modify `web/backend/services/report_slides.py` — `+_resolver_periodo_ref()` (puro, testável); `gerar_slides(...)` ganha `semana_inicio`.
- Create `web/backend/tests/test_report_slides_periodo.py` — unit do resolvedor de período.
- Modify `web/backend/schemas/gestor.py` — `TriggerRequest.semana_inicio: str | None`.
- Modify `web/backend/models/report_job.py` — coluna `semana_inicio`.
- Create `web/backend/alembic/versions/c2d3e4f5a6b7_add_semana_inicio_report_jobs.py` — migration.
- Modify `web/backend/api/gestor.py` — valida e propaga `semana_inicio`.
- Create `web/backend/tests/test_trigger_semana.py` — API test do trigger com `semana_inicio`.

**Frontend**
- Modify `web/frontend/lib/api-gestor.ts` — `triggerReport(..., semana_inicio?)`.
- Modify `web/frontend/app/gestor/page.tsx` — seletor `<input type="week">` no SEMANAL.
- Create `web/frontend/tests/e2e/report-week-selector.spec.ts` — E2E.

---

## Task 1: `core/periodo.py` — semana útil seg→sex

**Files:**
- Modify: `core/periodo.py`
- Test: `web/backend/tests/test_periodo.py`

- [ ] **Step 1: Escrever os testes (falham)**. Criar `web/backend/tests/test_periodo.py`:

```python
from datetime import date

from core.periodo import Frequencia, periodo_referencia, semana_de, semana_vigente


def test_semana_de_segunda_a_sexta():
    # 2026-06-08 é segunda; 2026-06-12 é sexta
    p = semana_de(date(2026, 6, 8))
    assert p.inicio == date(2026, 6, 8)
    assert p.fim == date(2026, 6, 12)
    assert p.fim_plus_1 == date(2026, 6, 13)


def test_semana_de_qualquer_dia_cai_na_mesma_semana_util():
    # quarta, sexta, sábado e domingo da mesma semana → seg 08 / sex 12
    for d in (date(2026, 6, 10), date(2026, 6, 12), date(2026, 6, 13), date(2026, 6, 14)):
        p = semana_de(d)
        assert (p.inicio, p.fim) == (date(2026, 6, 8), date(2026, 6, 12))


def test_semana_vigente_usa_today():
    p = semana_vigente(today=date(2026, 6, 11))  # quinta
    assert (p.inicio, p.fim) == (date(2026, 6, 8), date(2026, 6, 12))


def test_periodo_referencia_semanal_usa_semana_vigente():
    p = periodo_referencia(today=date(2026, 6, 11), frequencia=Frequencia.SEMANAL)
    assert (p.inicio, p.fim) == (date(2026, 6, 8), date(2026, 6, 12))
```

- [ ] **Step 2: Rodar e ver falhar** (ImportError: `semana_de`/`semana_vigente` não existem):

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_periodo.py -v
```
Esperado: `ImportError: cannot import name 'semana_de'` (coleta falha, `0 items / 1 error`).

- [ ] **Step 3: Implementar**. Em `core/periodo.py`, adicionar as duas funções logo após `ultima_semana_completa` (antes de `ultimo_mes_completo`):

```python
def semana_de(dia: date) -> Periodo:
    """Semana útil (segunda→sexta) que contém ``dia``."""
    inicio = dia - timedelta(days=dia.weekday())   # segunda
    fim = inicio + timedelta(days=4)               # sexta
    fim_plus_1 = fim + timedelta(days=1)           # sábado (útil p/ nomes de arquivo)
    return Periodo(inicio=inicio, fim=fim, fim_plus_1=fim_plus_1)


def semana_vigente(*, today: date | None = None) -> Periodo:
    """Semana útil (seg→sex) corrente — a que contém hoje."""
    return semana_de(today or date.today())
```

E trocar o final de `periodo_referencia` (a linha `return ultima_semana_completa(today=today)`) por:

```python
    return semana_vigente(today=today)
```

E acrescentar `"semana_de"` e `"semana_vigente"` à lista `__all__` (após `"ultima_semana_completa"`).

- [ ] **Step 4: Rodar e ver passar**:

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_periodo.py -v
```
Esperado: `4 passed`.

- [ ] **Step 5: Commit**:

```
git add core/periodo.py web/backend/tests/test_periodo.py
git commit -m "$(cat <<'EOF'
feat(periodo): semana_de/semana_vigente (seg–sex) e periodo_referencia SEMANAL usa semana vigente

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `report_slides.py` — resolvedor de período testável

**Files:**
- Modify: `web/backend/services/report_slides.py`
- Test: `web/backend/tests/test_report_slides_periodo.py`

- [ ] **Step 1: Escrever os testes (falham)**. Criar `web/backend/tests/test_report_slides_periodo.py`:

```python
from datetime import date

from services.report_slides import _resolver_periodo_ref


def test_semanal_com_semana_inicio():
    ref, comp = _resolver_periodo_ref("2026-06", "SEMANAL", "2026-06-08")
    assert (ref.inicio, ref.fim) == (date(2026, 6, 8), date(2026, 6, 12))
    # comparativo = semana anterior (seg 01 / sex 05)
    assert (comp.inicio, comp.fim) == (date(2026, 6, 1), date(2026, 6, 5))


def test_semanal_sem_semana_inicio_usa_vigente():
    ref, _comp = _resolver_periodo_ref("2026-06", "SEMANAL", None, today=date(2026, 6, 11))
    assert (ref.inicio, ref.fim) == (date(2026, 6, 8), date(2026, 6, 12))


def test_semanal_aceita_qualquer_dia_da_semana():
    # quinta 11/06 como semana_inicio ainda resolve seg 08 / sex 12
    ref, _ = _resolver_periodo_ref("2026-06", "SEMANAL", "2026-06-11")
    assert (ref.inicio, ref.fim) == (date(2026, 6, 8), date(2026, 6, 12))


def test_mensal_usa_mes_selecionado_e_ignora_semana_inicio():
    ref, comp = _resolver_periodo_ref("2026-05", "MENSAL", "2026-06-08")
    assert (ref.inicio, ref.fim) == (date(2026, 5, 1), date(2026, 5, 31))
    assert (comp.inicio, comp.fim) == (date(2026, 4, 1), date(2026, 4, 30))
```

- [ ] **Step 2: Rodar e ver falhar** (`ImportError: _resolver_periodo_ref`):

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_report_slides_periodo.py -v
```
Esperado: `ImportError` na coleta.

- [ ] **Step 3: Implementar**. Em `web/backend/services/report_slides.py`:

(a) No topo, ajustar o import de datetime para incluir `timedelta`:
```python
from datetime import date, timedelta
```

(b) Adicionar a função pura ANTES de `gerar_slides`:
```python
def _resolver_periodo_ref(
    mes: str,
    frequencia: str,
    semana_inicio: str | None,
    *,
    today: "date | None" = None,
):
    """Resolve (periodo_ref, periodo_comp) a partir dos dados do trigger.

    - SEMANAL: semana útil seg–sex escolhida (``semana_inicio``, qualquer dia da
      semana serve) ou a semana vigente; comparativo = semana anterior.
    - MENSAL: mês selecionado (via âncora no dia 15 do mês seguinte); comparativo
      = mês anterior. (Comportamento original preservado.)
    """
    from core import periodo as P  # type: ignore

    freq = frequencia.upper()
    if freq == "SEMANAL":
        if semana_inicio:
            ref = P.semana_de(date.fromisoformat(semana_inicio))
        else:
            ref = P.semana_vigente(today=today)
        comp = P.semana_de(ref.inicio - timedelta(days=7))
        return ref, comp

    # MENSAL — âncora no dia 15 do mês seguinte p/ ultimo_mes_completo devolver o mês escolhido
    ano, mes_num = int(mes[:4]), int(mes[5:7])
    proximo = mes_num + 1
    ano_alvo = ano + (1 if proximo > 12 else 0)
    proximo = 1 if proximo > 12 else proximo
    ancora = date(ano_alvo, proximo, 15)
    ref = P.ultimo_mes_completo(today=ancora)
    comp = P.ultimo_mes_completo(today=ref.inicio)
    return ref, comp
```

(c) Na assinatura de `gerar_slides`, adicionar o parâmetro:
```python
def gerar_slides(slug: str, nome_cliente: str, mes: str, frequencia: str = "MENSAL", semana_inicio: str | None = None) -> str:
```

(d) Reorganizar o cálculo do período. No estado atual há (i) o bloco do hack do mês **antes** de `fetch_clientes` (linhas ~60-64: `ano, mes_num = ...` até `today = date(ano_alvo, proximo, 15)`), (ii) `FREQ = frequencia.upper()` (~linha 78), e (iii) as duas linhas `periodo_ref = periodo_mod.periodo_referencia(...)` / `periodo_comp = periodo_mod.periodo_referencia(...)` (~80-81).

- **Apagar** o bloco do hack (i) inteiro (linhas ~60-64) — não é mais usado.
- **Manter** o `FREQ = frequencia.upper()` (ii) que já existe.
- **Substituir** as duas linhas (iii) por uma só:
```python
    periodo_ref, periodo_comp = _resolver_periodo_ref(mes, FREQ, semana_inicio)
```
Resultado: nenhum `FREQ` duplicado; `today`/`date` do hack removidos; o `periodo_mod` continua importado e usado dentro de `_resolver_periodo_ref`.

- [ ] **Step 4: Rodar e ver passar**:

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_report_slides_periodo.py -v
```
Esperado: `4 passed`.

- [ ] **Step 5: Commit**:

```
git add web/backend/services/report_slides.py web/backend/tests/test_report_slides_periodo.py
git commit -m "$(cat <<'EOF'
feat(report): _resolver_periodo_ref — SEMANAL usa semana seg–sex escolhida/vigente

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `TriggerRequest.semana_inicio`

**Files:**
- Modify: `web/backend/schemas/gestor.py`

- [ ] **Step 1: Implementar** (mudança de schema; testada via Task 5). Em `web/backend/schemas/gestor.py`, na classe `TriggerRequest` (após o campo `frequencia`):

```python
    semana_inicio: str | None = None  # YYYY-MM-DD (qualquer dia da semana); só usado quando frequencia=SEMANAL
```

- [ ] **Step 2: Verificar import/validação**:

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -c "from schemas.gestor import TriggerRequest; print(TriggerRequest(slug='x', mes='2026-06', frequencia='SEMANAL', semana_inicio='2026-06-08').semana_inicio)"
```
Esperado: `2026-06-08`.

- [ ] **Step 3: Commit**:

```
git add web/backend/schemas/gestor.py
git commit -m "$(cat <<'EOF'
feat(schemas): TriggerRequest aceita semana_inicio opcional

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Coluna `report_jobs.semana_inicio` + migration

**Files:**
- Modify: `web/backend/models/report_job.py`
- Create: `web/backend/alembic/versions/c2d3e4f5a6b7_add_semana_inicio_report_jobs.py`

- [ ] **Step 1: Implementar o model**. Em `web/backend/models/report_job.py`, após o campo `frequencia`:

```python
    semana_inicio: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD (segunda da semana), só SEMANAL
```

- [ ] **Step 2: Criar a migration** `web/backend/alembic/versions/c2d3e4f5a6b7_add_semana_inicio_report_jobs.py`:

```python
"""add semana_inicio to report_jobs

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("report_jobs", sa.Column("semana_inicio", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("report_jobs", "semana_inicio")
```

- [ ] **Step 3: Aplicar e validar a migration** (contra `vitrine_test`; recria schema dos testes não depende disso):

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic current
```
Esperado: aplica `c2d3e4f5a6b7` e `alembic current` mostra `c2d3e4f5a6b7 (head)`.

- [ ] **Step 4: Confirmar `alembic check` limpo** (model bate com a migration):

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m alembic check
```
Esperado: `No new upgrade operations detected.`

- [ ] **Step 5: Commit**:

```
git add web/backend/models/report_job.py web/backend/alembic/versions/c2d3e4f5a6b7_add_semana_inicio_report_jobs.py
git commit -m "$(cat <<'EOF'
feat(db): report_jobs.semana_inicio (nullable) + migration

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Trigger propaga `semana_inicio`

**Files:**
- Modify: `web/backend/api/gestor.py`
- Test: `web/backend/tests/test_trigger_semana.py`

- [ ] **Step 1: Escrever o teste (falha)**. Criar `web/backend/tests/test_trigger_semana.py`. Use o padrão de app/auth dos testes existentes (`tests/test_auth.py`) — fixture que monta o app com o router do gestor, cria um usuário admin e injeta o cookie/token; mocka `services.report_slides.gerar_slides` para NÃO rodar o fluxo real. O teste:
  1. POST `/gestor/reports/trigger` com `{slug, mes, frequencia:"SEMANAL", semana_inicio:"2026-06-08"}` → 200 com `job_id`.
  2. Lê o `ReportJob` criado no DB e assere `job.semana_inicio == "2026-06-08"`.
  3. POST com `semana_inicio` inválido (`"08/06/2026"`) → 400.

```python
import re
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from api.gestor import router as gestor_router
from api.auth import require_auth
from db import get_session
from models import Base, Cliente, Categoria, Usuario, UsuarioCliente, ReportJob

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def client_e_ts():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine)
    with TS() as s:
        admin = Usuario(email="a@a.com", nome="A", senha_hash="x", is_admin=True, ativo=True)
        cli = Cliente(slug="acme", nome="Acme", categoria=Categoria.ECOMMERCE)
        s.add_all([admin, cli]); s.commit()
        admin_id = admin.id

    app = FastAPI()
    app.include_router(gestor_router, prefix="/gestor")

    def _sess():
        with TS() as s:
            yield s

    def _user():
        with TS() as s:
            return s.get(Usuario, admin_id)

    app.dependency_overrides[get_session] = _sess
    app.dependency_overrides[require_auth] = _user
    return TestClient(app), TS


def test_trigger_semanal_grava_semana_inicio(client_e_ts):
    client, TS = client_e_ts
    with patch("api.gestor.gerar_slides", create=True), \
         patch("services.report_slides.gerar_slides", return_value="https://x"):
        r = client.post("/gestor/reports/trigger", json={
            "slug": "acme", "mes": "2026-06", "frequencia": "SEMANAL", "semana_inicio": "2026-06-08"})
    assert r.status_code == 200, r.text
    with TS() as s:
        job = s.scalar(select(ReportJob))
        assert job.semana_inicio == "2026-06-08"


def test_trigger_semana_inicio_invalido_400(client_e_ts):
    client, _ = client_e_ts
    r = client.post("/gestor/reports/trigger", json={
        "slug": "acme", "mes": "2026-06", "frequencia": "SEMANAL", "semana_inicio": "08/06/2026"})
    assert r.status_code == 400
```

> Nota p/ o implementador: ajuste a fixture ao mecanismo real de auth do `api/gestor.py` (veja `tests/test_auth.py` / como `require_auth` é satisfeito nos testes existentes). Se o teste não passar de primeira por detalhe de auth/fixture, ajuste o TESTE (não o código de produção). Se revelar bug real, pare e reporte.

- [ ] **Step 2: Rodar e ver falhar**:

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_trigger_semana.py -v
```
Esperado: falha (semana_inicio não é gravado / validação 400 não existe ainda).

- [ ] **Step 3: Implementar** em `web/backend/api/gestor.py`, dentro de `trigger_report`:

(a) Após a validação de `mes` (`if not _MES_RE.match(body.mes): ...`), validar `semana_inicio`:
```python
    if body.semana_inicio is not None:
        try:
            date.fromisoformat(body.semana_inicio)
        except ValueError:
            raise HTTPException(status_code=400, detail="semana_inicio deve ser YYYY-MM-DD")
```
(garanta que `from datetime import date` está importado no topo do arquivo; se não estiver, adicione.)

(b) Ao criar o `ReportJob`, incluir o campo:
```python
    job = ReportJob(
        usuario_id=user.id,
        cliente_id=cliente.id,
        mes=body.mes,
        frequencia=body.frequencia,
        semana_inicio=body.semana_inicio,
        status=JobStatus.PENDING,
    )
```

(c) Capturar a variável local (junto de `mes = body.mes` / `frequencia = body.frequencia`):
```python
    semana_inicio = body.semana_inicio
```

(d) Passar ao `gerar_slides` (na linha que chama `url = gerar_slides(...)`):
```python
                url = gerar_slides(slug=cliente_slug, nome_cliente=cliente_nome, mes=mes, frequencia=frequencia, semana_inicio=semana_inicio)
```

- [ ] **Step 4: Rodar e ver passar** + suíte inteira:

```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/test_trigger_semana.py -v && .venv/bin/python -m pytest tests/ -q
```
Esperado: testes do arquivo passam; suíte inteira sem regressão.

- [ ] **Step 5: Commit**:

```
git add web/backend/api/gestor.py web/backend/tests/test_trigger_semana.py
git commit -m "$(cat <<'EOF'
feat(api): trigger valida e propaga semana_inicio até gerar_slides

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Frontend — seletor de semana

**Files:**
- Modify: `web/frontend/lib/api-gestor.ts`
- Modify: `web/frontend/app/gestor/page.tsx`

- [ ] **Step 1: `lib/api-gestor.ts`** — `triggerReport` ganha `semana_inicio` (linha ~411):

```typescript
  triggerReport: (slug: string, mes: string, frequencia: Frequencia = "MENSAL", semana_inicio?: string) =>
    apiCall<{ job_id: string }>("reports/trigger", "POST", { slug, mes, frequencia, semana_inicio }),
```

- [ ] **Step 2: `app/gestor/page.tsx`** — no componente `AbaClientes`:

(a) Adicionar helpers no topo do arquivo (após os imports):
```typescript
function isoWeekAtual(d = new Date()): string {
  const dt = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = (dt.getUTCDay() + 6) % 7;           // 0 = segunda
  dt.setUTCDate(dt.getUTCDate() - day + 3);        // quinta da semana ISO
  const week1 = new Date(Date.UTC(dt.getUTCFullYear(), 0, 4));
  const week = 1 + Math.round(((dt.getTime() - week1.getTime()) / 86400000 - 3 + ((week1.getUTCDay() + 6) % 7)) / 7);
  return `${dt.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

function isoWeekParaSegunda(iso: string): string {
  // "YYYY-Www" -> data da segunda-feira "YYYY-MM-DD"
  const [y, w] = iso.split("-W").map(Number);
  const jan4 = new Date(Date.UTC(y, 0, 4));
  const jan4Day = (jan4.getUTCDay() + 6) % 7;      // 0 = segunda
  const week1Monday = new Date(jan4);
  week1Monday.setUTCDate(jan4.getUTCDate() - jan4Day);
  const monday = new Date(week1Monday);
  monday.setUTCDate(week1Monday.getUTCDate() + (w - 1) * 7);
  return monday.toISOString().slice(0, 10);
}
```

(b) Adicionar estado (junto de `mes`/`frequencia`, ~linha 242):
```typescript
  const [semana, setSemana] = useState(() => isoWeekAtual());
```

(c) Na UI dos seletores (onde estão o select de `mes` e o toggle de `frequencia`), renderizar o seletor de semana quando SEMANAL e esconder o de mês:
```tsx
  {frequencia === "SEMANAL" ? (
    <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
      Semana:
      <input
        type="week"
        value={semana}
        onChange={(e) => setSemana(e.target.value)}
        aria-label="Semana de referência"
        className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
      />
    </label>
  ) : null}
```
(Mantenha o seletor de `mes` visível apenas quando `frequencia === "MENSAL"`.)

(d) No `handleGerar`, passar `semana_inicio` quando SEMANAL:
```typescript
        const semana_inicio = frequencia === "SEMANAL" ? isoWeekParaSegunda(semana) : undefined;
        const { job_id } = await gestorApi.triggerReport(slug, mes, frequencia, semana_inicio);
```

- [ ] **Step 3: Verificar tipos**:

```
cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit
```
Esperado: exit 0.

- [ ] **Step 4: Commit**:

```
git add web/frontend/lib/api-gestor.ts web/frontend/app/gestor/page.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): seletor de semana no trigger SEMANAL (default semana vigente)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: E2E do seletor de semana

**Files:**
- Create: `web/frontend/tests/e2e/report-week-selector.spec.ts`

- [ ] **Step 1: Escrever o E2E** (espelhe o padrão de `tests/e2e/gestor-travado.spec.ts`: injeta cookie `gestor_token`, navega `/gestor?tab=configuracoes`/aba de clientes, mocka os GETs de load). O teste: seleciona um cliente, troca frequência para SEMANAL, preenche `<input type="week">` com `2026-W24`, dispara, e **captura o body do POST `/api/gestor/reports/trigger`** assertando `frequencia:"SEMANAL"` e `semana_inicio:"2026-06-08"` (segunda da semana ISO 24 de 2026).

```typescript
import { test, expect } from "@playwright/test";

test("trigger SEMANAL envia semana_inicio (segunda da semana escolhida)", async ({ page, context }) => {
  await context.addCookies([{ name: "gestor_token", value: "fake", url: "http://localhost:3010" }]);
  // mocks de load — ajuste aos GETs reais que a aba dispara (me, clientes, etc.)
  await page.route("**/api/gestor/me", (r) => r.fulfill({ json: { id: "u1", nome: "A", email: "a@a.com", is_admin: true } }));
  await page.route("**/api/gestor/clientes", (r) => r.fulfill({ json: { items: [{ id: "c1", slug: "acme", nome: "Acme", categoria: "ECOMMERCE", gestor: null, ativo: true, gestor_travado: false, id_meta_ads: "1", id_google_ads: "1" }] } }));
  let body: any = null;
  await page.route("**/api/gestor/reports/trigger", async (r) => {
    body = r.request().postDataJSON();
    await r.fulfill({ json: { job_id: "j1" } });
  });

  await page.goto("/gestor");
  // selecionar a aba de clientes + o cliente (ajuste seletores ao DOM real)
  await page.getByText("Acme").click();
  await page.getByRole("button", { name: /semanal/i }).click().catch(() => {});
  // garantir SEMANAL e preencher a semana
  await page.getByLabel(/semana de referência/i).fill("2026-W24");
  await page.getByRole("button", { name: /gerar/i }).click();

  await expect.poll(() => body?.semana_inicio).toBe("2026-06-08");
  expect(body.frequencia).toBe("SEMANAL");
});
```

> Nota: 2026-W24 (ISO) → segunda = 2026-06-08. Ajuste os seletores/mocks ao DOM real do `app/gestor/page.tsx`. Se o servidor de dev não estiver de pé, o `playwright.config.ts` (com `webServer` + `reuseExistingServer`) sobe um. Se travar por ambiente após 1-2 tentativas, reporte BLOCKED.

- [ ] **Step 2: Rodar o E2E**:

```
cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx playwright test tests/e2e/report-week-selector.spec.ts
```
Esperado: `1 passed`.

- [ ] **Step 3: Commit**:

```
git add web/frontend/tests/e2e/report-week-selector.spec.ts
git commit -m "$(cat <<'EOF'
test(frontend): e2e do seletor de semana no trigger SEMANAL

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Verificação final

**Files:** nenhum (verificação).

- [ ] **Step 1: Suíte backend completa**:
```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m pytest tests/ -q
```
Esperado: tudo verde (incluindo `test_periodo.py`, `test_report_slides_periodo.py`, `test_trigger_semana.py`).

- [ ] **Step 2: Frontend tsc + E2E**:
```
cd /Users/mac0267/Documents/auto-report-main/web/frontend && npx tsc --noEmit && npx playwright test tests/e2e/report-week-selector.spec.ts tests/e2e/gestor-travado.spec.ts
```
Esperado: tsc exit 0; E2E passam (sem regressão no gestor-travado).

- [ ] **Step 3: `alembic check` limpo**:
```
cd /Users/mac0267/Documents/auto-report-main/web/backend && .venv/bin/python -m alembic check
```
Esperado: `No new upgrade operations detected.`

---

**Notas de fechamento (DRY/YAGNI):**
- A resolução de período fica num único helper puro (`_resolver_periodo_ref`), testável sem Drive/coleta.
- MENSAL intocado (mesma âncora do dia 15).
- `semana_de` aceita qualquer dia da semana → o frontend não precisa enviar exatamente a segunda; o backend normaliza (resiliência contra off-by-one na conversão ISO).
- Nada de intervalos livres/quinzenais (YAGNI).
