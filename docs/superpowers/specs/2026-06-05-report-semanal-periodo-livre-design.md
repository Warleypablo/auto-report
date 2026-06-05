# Report semanal com período livre (início e fim selecionáveis)

**Data:** 2026-06-05
**Status:** aprovado (design)

## Problema

Na geração do report **semanal**, o usuário escolhe apenas a *semana* (`<input type="week">`); o período é forçado para a **semana útil seg–sex** (`core.periodo.semana_de`), com o fim derivado, não selecionável. O usuário precisa poder escolher **início e fim 100% livres**.

## Decisões (brainstorming)

- **Comparativo:** período de mesma duração imediatamente anterior (automático, sem pedir mais datas).
- **Limites:** bloquear datas futuras (`fim ≤ hoje`), exigir `início ≤ fim`, sem limite de duração.
- **Default ao abrir:** última semana completa (segunda→sexta anterior), agora editável.
- **Rótulo:** mantém "Semanal".
- **Escopo:** muda só o fluxo SEMANAL; MENSAL inalterado.

## Design

### Frontend (`web/frontend/app/gestor/page.tsx`)
- Substituir o `<input type="week">` (bloco SEMANAL, ~657-665) por dois `<input type="date">`: **Início** e **Fim**.
- Estado `dataInicio` / `dataFim` (YYYY-MM-DD) no lugar de `semana`.
- `max={hoje}` nos dois; botão "Gerar" desabilitado quando `inicio > fim`.
- Default: última semana completa (seg→sex anterior).
- No trigger, enviar `data_inicio` + `data_fim` (em vez de `semana_inicio`).

### Backend — schema (`web/backend/schemas/gestor.py::TriggerRequest`)
- Adicionar `data_inicio: str | None` e `data_fim: str | None` (YYYY-MM-DD; usados no SEMANAL).
- Manter `semana_inicio` aceito como fallback (retrocompat).
- Validação (validator): se presentes, `data_fim ≥ data_inicio` e `data_fim ≤ hoje`; senão `ValueError` → 400.

### Backend — resolução (`web/backend/services/report_slides.py::_resolver_periodo_ref`)
- Estende a assinatura com `data_inicio`/`data_fim`.
- SEMANAL com ambos: `ref = Periodo(inicio, fim, fim+1)`; comparativo de mesma duração:
  `diff = (fim - inicio).days`; `comp_fim = inicio - 1d`; `comp_inicio = comp_fim - diff`.
- Fallback: só `semana_inicio` → `semana_de` (comportamento atual); nada → `semana_vigente`.

### Backend — trigger (`web/backend/api/gestor.py::trigger_report` / `_run`)
- Capturar `body.data_inicio`/`body.data_fim` (como já faz com `semana_inicio`) e repassar a `gerar_slides` → `_resolver_periodo_ref`.
- `ReportJob` **não** ganha colunas novas (sem migration) — o `_run` usa variáveis capturadas; persistir o período no job fica como follow-up opcional.

## Testes (TDD)
- `_resolver_periodo_ref` SEMANAL com datas livres → `ref` e `comp` corretos (mesma duração anterior).
- Validação do schema: `fim < início` → erro; `fim` futuro → erro.
- Retrocompat: só `semana_inicio` mantém seg–sex.
- Frontend: `tsc --noEmit` (sem teste automatizado de UI).

## Fora de escopo
- Comparativo manual (segundo período escolhido à mão).
- Limite máximo de duração.
- Persistir o período livre no `ReportJob`.
