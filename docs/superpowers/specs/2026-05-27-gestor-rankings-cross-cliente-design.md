# Design: Gestor — Página de Rankings Cross-Cliente

**Data:** 2026-05-27
**Status:** Aprovado

---

## Problema

O gestor não tem uma visão consolidada de quais criativos e campanhas performam melhor em toda a sua carteira de clientes. A única forma de comparar é navegar cliente a cliente.

---

## Solução

Nova página dedicada `/gestor/rankings` que agrega os breakdowns de todos os clientes do gestor para um mês selecionado, exibindo dois rankings completos do #1 ao último: top criativos Meta Ads e top campanhas Google Ads da carteira inteira.

---

## Escopo

**Incluído:**
- Nova página `web/frontend/app/gestor/rankings/page.tsx`
- Novo módulo `web/frontend/lib/roas-tier.ts` (extrai helpers compartilhados)
- Refactor `PerformanceLeaderboard.tsx` para importar de `roas-tier.ts`
- Link "Rankings" adicionado ao header de `app/gestor/page.tsx`

**Excluído:**
- Nenhuma alteração de backend
- Nenhuma paginação (lista completa)
- Nenhum filtro por categoria ou gestor

---

## Arquitetura

### Fluxo de dados

```
gestorApi.clientes()               → lista de todos os clientes
  ↓ Promise.all
gestorApi.metricasBreakdown(slug, mes)  × N clientes em paralelo
  ↓ agregação
MetaAd[] + clienteNome + clienteSlug   (todos os clientes)
GoogleAd[] + clienteNome + clienteSlug  (todos os clientes)
  ↓ sortByRoas() (de roas-tier.ts)
Rankings #1…#N renderizados
```

### Arquivos

| Ação | Arquivo | Responsabilidade |
|---|---|---|
| Criar | `web/frontend/lib/roas-tier.ts` | `roasTier`, `TIER_TEXT`, `TIER_BAR`, `sortByRoas`, `fmtBRL`, `fmtRoas` |
| Criar | `web/frontend/app/gestor/rankings/page.tsx` | Página completa de rankings cross-cliente |
| Modificar | `web/frontend/components/PerformanceLeaderboard.tsx` | Importa helpers de `roas-tier.ts` |
| Modificar | `web/frontend/app/gestor/page.tsx` | Adiciona link "Rankings" no header |

---

## Visual

### Header da página

- Link `← Seus clientes` para `/gestor`
- Título `Rankings` + selector de mês (default: `mesUltimoFechado()`)

### Seção Meta Ads

- Eyebrow: `Top criativos · Meta Ads · carteira`
- Cada linha:
  - `#N` colorido por posição (ouro/prata/bronze para top 3, cinza demais)
  - Thumbnail 28×20px (`imagem_url` ou gradiente placeholder)
  - Nome do criativo (truncado, `title` para tooltip)
  - Nome do cliente como subtext cinza (link para `/gestor/[clienteSlug]`)
  - ROAS colorido por tier (via `TIER_TEXT`)
  - Investimento formatado
- Clicar em qualquer linha navega para `/gestor/[clienteSlug]`

### Seção Google Ads

- Eyebrow: `Top campanhas · Google Ads · carteira`
- Mesma estrutura de linha, sem thumbnail
- Barra de investimento proporcional ao maior da lista (animada no viewport com framer-motion)

---

## Tiers de ROAS (extraídos para `roas-tier.ts`)

| Tier | Faixa | Cor CSS |
|---|---|---|
| high | ≥ 3× | `var(--forest)` |
| mid | 1.5× – 3× | `#f59e0b` |
| low | < 1.5× | `var(--crimson)` |
| none | null | `var(--muted)` |

---

## Edge Cases

| Situação | Comportamento |
|---|---|
| Cliente sem breakdown no mês | Ignorado silenciosamente na agregação |
| ROAS null | Item vai ao final da lista |
| Nome longo | Truncado + `title` attr |
| Nenhum dado no mês | Empty state: "Nenhum dado disponível para este mês" |
| Erro em um breakdown | Cliente ignorado, demais carregam normalmente |
| Loading | Mensagem "Carregando rankings…" enquanto `Promise.all` resolve |

---

## Refactor: `roas-tier.ts`

Extrai de `PerformanceLeaderboard.tsx` para módulo compartilhado:

```ts
// web/frontend/lib/roas-tier.ts
export type RoasTier = "high" | "mid" | "low" | "none"
export function roasTier(v: number | null): RoasTier
export const TIER_TEXT: Record<RoasTier, string>
export const TIER_BAR: Record<RoasTier, string>
export function sortByRoas<T extends { roas: number | null }>(items: T[]): T[]
export function fmtBRL(v: number | null): string
export function fmtRoas(v: number | null): string
```

`PerformanceLeaderboard.tsx` passa a importar deste módulo. Comportamento idêntico.

---

## Testes

Nenhum teste novo. Sem lógica de negócio nova — apenas orquestração de chamadas existentes e renderização. Os testes e2e existentes não são afetados.
