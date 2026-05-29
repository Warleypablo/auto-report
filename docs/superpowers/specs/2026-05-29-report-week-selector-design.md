# Design: Seletor de semana para o report SEMANAL

**Data:** 2026-05-29
**Branch:** (a criar) `feat/report-week-selector`
**Status:** Aprovado (brainstorming)

---

## Problema

Ao disparar um report **SEMANAL** pela interface do gestor, não há como escolher a semana. O trigger só envia `mes` (YYYY-MM) + `frequencia`, e `web/backend/services/report_slides.py:58-64` faz um hack: define `today = dia 15 do mês SEGUINTE` ao `mes` selecionado e chama `periodo_referencia(today, SEMANAL)`. Esse hack foi desenhado para o **MENSAL** (`ultimo_mes_completo` então retorna o mês escolhido), mas no **SEMANAL** `ultima_semana_completa` devolve a janela móvel D‑7..D‑1 a partir do dia 15 do mês seguinte — ou seja, **os dias 08–14 do mês seguinte ao selecionado** (ex.: `mes=2026-05` → período 08/06–14/06). É uma semana arbitrária, sem relação com a semana desejada. Não há seletor de semana.

## Decisões (do brainstorming)

- **Unidade da semana:** **segunda → sexta** (dias úteis).
- **Default:** **semana vigente** (a semana corrente, seg–sex que contém hoje). O report costuma ser gerado na sexta, cobrindo seg–sex daquela mesma semana.
- **Escopo:** apenas **SEMANAL**. O **MENSAL** continua igual (o seletor de mês já está correto).
- **Consistência:** script e interface usam a mesma definição de semana (seg–sex) e o mesmo default (semana vigente).
- **Seletor na UI:** `<input type="week">` nativo (escolhe a semana pela segunda-feira ISO); interpretamos como seg–sex.

## Comportamento

- Período SEMANAL = **`[segunda, sexta]`** da semana escolhida.
- Trigger com `frequencia = SEMANAL` → mostra o seletor de semana, default = **semana vigente**. Com `MENSAL` → seletor de mês (intocado).
- Período comparativo (`periodo_comp`) = a **semana anterior** (seg–sex).

## Arquitetura / Mudanças

Unidades pequenas e isoladas:

### 1. `core/periodo.py`
- `semana_de(dia: date) -> Periodo`: semana seg–sex que contém `dia`.
  `inicio = dia - timedelta(days=dia.weekday())` (segunda); `fim = inicio + timedelta(days=4)` (sexta); `fim_plus_1 = fim + timedelta(days=1)`.
- `semana_vigente(*, today: date | None = None) -> Periodo`: `semana_de(today or date.today())`.
- `periodo_referencia(SEMANAL)` passa a retornar `semana_vigente(today=today)` (em vez da janela móvel D‑7..D‑1). A função `ultima_semana_completa` (rolling) é mantida apenas se algum outro chamador depender dela; nenhum chamador de produção do report depende — confirmar na implementação e remover se órfã.

### 2. `web/backend/schemas/gestor.py` — `TriggerRequest`
- Novo campo opcional `semana_inicio: str | None = None` (YYYY-MM-DD, a segunda-feira da semana). Usado só quando `frequencia == "SEMANAL"`.

### 3. `web/backend/services/report_slides.py` — `gerar_slides`
- Assinatura ganha `semana_inicio: str | None = None`.
- **SEMANAL:** se `semana_inicio` veio → `periodo_ref = semana_de(date.fromisoformat(semana_inicio))`; senão → `semana_vigente(today=date.today())`. **Não usa mais o hack do mês no semanal.** `periodo_comp = semana_de(periodo_ref.inicio - timedelta(days=7))`.
- **MENSAL:** inalterado (hack do mês → `ultimo_mes_completo`).

### 4. `web/backend/api/gestor.py` + `models/report_job.py` (+ migration)
- `report_jobs` ganha coluna nullable `semana_inicio` (text), consistente com `mes`/`frequencia` já persistidos (sobrevive a restart/recovery do job).
- `trigger_report` repassa `body.semana_inicio` para o job; a thread de background chama `gerar_slides(..., semana_inicio=job.semana_inicio)`.

### 5. Frontend `web/frontend/app/gestor/page.tsx` + `lib/api-gestor.ts`
- `TriggerData` ganha `semana_inicio?: string`.
- Quando `frequencia === "SEMANAL"`: renderiza `<input type="week">` (default = semana vigente em formato ISO `YYYY-Www`), converte o valor para a **segunda-feira** (`YYYY-MM-DD`) e envia em `semana_inicio`. Quando `MENSAL`: seletor de mês atual.
- Exibe o intervalo resolvido (ex.: "08/06 – 12/06/2026") como confirmação visual.

## Tratamento de erros / bordas
- `semana_inicio` inválido (não-ISO date) → 400 no trigger (validação no schema/endpoint).
- `semana_inicio` enviado com `frequencia=MENSAL` → ignorado (MENSAL usa `mes`).
- Semana vigente gerada antes de sexta → dados de dias futuros simplesmente não existem nas fontes; o período ainda é seg–sex (comportamento aceito pelo usuário, que gera na sexta).

## Testes
- `core/periodo.py`: unit determinístico de `semana_de` (várias âncoras: segunda, quarta, sexta, sábado, domingo → mesma seg–sex) e `semana_vigente(today=...)`.
- `gerar_slides`: `semana_inicio` dirige o período (seg–sex); sem `semana_inicio` → semana vigente; `periodo_comp` = semana anterior. (Mockar `fetch_clientes`/coleta; focar na seleção de período.)
- Migration `report_jobs.semana_inicio`: aplica/reverte limpo.
- Frontend: o seletor de semana aparece só no SEMANAL, com default correto, e o trigger envia `semana_inicio` (segunda-feira) — teste E2E/playwright mockando a API.

## Fora de escopo
- Mudar o MENSAL (já funciona).
- Intervalos livres / quinzenais (YAGNI; só semana seg–sex).
- Backfill/retroatividade de reports já gerados.
