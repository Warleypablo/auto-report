# Design: PeriodPicker — Seletor de Intervalo de Meses

**Data:** 2026-05-21
**Branch:** vitrine-cases
**Status:** Aprovado

---

## Problema

O `MonthSelector` atual exibe os meses disponíveis como pills (botões em linha). A UX é limitada: não comunica que é possível selecionar intervalos, não tem filtros rápidos, e a lista cresce indefinidamente à medida que novos meses são adicionados ao banco.

---

## Solução

Substituir `MonthSelector` por um componente `PeriodPicker` com popover de calendário de meses, seleção de range (mês inicial → mês final) e chips de filtro rápido.

---

## Componentes

### `PeriodPicker` (substitui `MonthSelector`)

Trigger button que exibe o range selecionado (ex: `Fev 2026 → Abr 2026`). Ao clicar, abre um popover contendo:

- **Grid de meses** — exibe os 12 meses do ano em grade 4×3 (`Jan · Fev · Mar ...`), navegável por ano com setas `‹ 2025 ›`
- **Highlight de range** — meses entre início e fim ficam destacados; início e fim com bordas arredondadas
- **Meses sem snapshot** — renderizados com opacidade reduzida (não bloqueados, apenas sinalizados)
- **Chips de filtro rápido** — `Últimos 3M` · `Últimos 6M` · `Últimos 12M` · `Este ano`
- **Botão "Aplicar"** — confirma o range e fecha o popover

### Interação de seleção

1. Primeiro clique: define `de` (início do range), highlight de hover mostra o range candidato
2. Segundo clique: define `ate` (fim do range), confirma o range
3. Se o usuário clicar em `ate < de`, os valores são invertidos automaticamente

---

## URL e Roteamento

| Antes | Depois |
|-------|--------|
| `?mes=YYYY-MM` | `?de=YYYY-MM&ate=YYYY-MM` |

**Compatibilidade retroativa:** URLs com `?mes=YYYY-MM` são convertidas em `?de=YYYY-MM&ate=YYYY-MM` (mesmo mês nos dois parâmetros) em `lista/page.tsx`.

**Default:** se nenhum parâmetro estiver presente, `de` e `ate` apontam para os últimos 3 meses completos.

---

## Mudanças no Backend

### `listAllClientes(de, ate)`
- Assinatura muda de `(mes: string)` para `(de: string, ate: string)`
- Query filtra `periodo_inicio >= de AND periodo_inicio <= ate`

### Endpoint interno
- Aceita `de` e `ate` no lugar de `mes`
- Agrega `com_snapshot` e `total` sobre o range completo

### Header de contagem
- Muda de "212 snapshot(s) para **Abril 2026**" para "212 snapshot(s) de **Fev 2026** a **Abr 2026**"

---

## Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| `de > ate` | Range invertido automaticamente |
| Range sem nenhum snapshot | Mensagem inline na tabela: "Nenhum snapshot encontrado para este período" |
| URL legada `?mes=` | Convertida para `?de=&ate=` com mesmo valor |
| Sem parâmetros na URL | Default: últimos 3 meses |
| Mês futuro selecionado | Permitido (dados podem ainda não existir) |

---

## Arquivos Afetados

| Arquivo | Mudança |
|---------|---------|
| `components/MonthSelector.tsx` | Substituído por `components/PeriodPicker.tsx` |
| `components/PeriodPicker.tsx` | Novo componente |
| `app/lista/page.tsx` | Lê `de`/`ate`, compat com `mes`, passa range para API |
| `lib/api-internal.ts` | `listAllClientes` aceita range |
| `lib/mes-utils.ts` | Util `labelRange(de, ate)` adicionada |
| `backend/api/internal.py` | Endpoint atualizado para receber e filtrar range |

---

## Fora do Escopo

- Granularidade por dia
- Múltiplos ranges simultâneos
- Persistência do range em localStorage
