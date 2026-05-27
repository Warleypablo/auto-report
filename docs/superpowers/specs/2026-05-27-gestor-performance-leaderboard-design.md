# Design: Gestor — Performance Leaderboard

**Data:** 2026-05-27
**Status:** Aprovado

---

## Problema

A seção "Campanhas" do painel de gestor (`/gestor/[slug]`) exibe Meta Ads e Google Ads como tabelas simples sem hierarquia visual de performance. Um diretor de performance precisa identificar imediatamente os top performers sem interpretar linhas de tabela.

---

## Solução

Substituir as tabelas existentes por um componente `PerformanceLeaderboard` com layout cinemático: cards com imagem para Meta Ads (top 3) e lista ranqueada com barras proporcionais para Google Ads. A mudança é cirúrgica — só a seção "Campanhas" muda.

---

## Escopo

**Incluído:**
- Novo componente `web/frontend/components/PerformanceLeaderboard.tsx`
- Substituição da seção "Campanhas" em `web/frontend/app/gestor/[slug]/page.tsx`

**Excluído:**
- KPIs, gráfico de evolução, disparo de report, ClickUp info, histórico de reports
- Backend: nenhuma alteração
- Dashboard do cliente: nenhuma alteração

---

## Arquitetura

### Componente

`PerformanceLeaderboard` — arquivo único com dois sub-componentes internos:

```
PerformanceLeaderboard (props: metaAds, googleAds, loading, mes)
├── MetaLeaderboard   (top 3 cards + tabela dos demais)
└── GoogleLeaderboard (lista ranqueada com barras)
```

Sub-componentes são funções internas, não exportadas — usados apenas aqui.

### Integração na page

```tsx
// substitui o bloco atual de tabelas em /gestor/[slug]/page.tsx
<PerformanceLeaderboard
  metaAds={metaAds}
  googleAds={googleAds}
  loading={loadingDetail}
  mes={mesLabel(mes)}
/>
```

Estado `verTodosMeta` / `verTodosGoogle` migra para dentro do componente (estado local). Os `useState` correspondentes são removidos da page.

---

## Visual

### MetaLeaderboard

- **Top 3**: grid 3 colunas, cards `aspect-video`, fundo com `imagem_url` ou gradiente placeholder
- **Overlay**: badge `#N` no canto superior esquerdo, gradiente escuro na base com nome + ROAS + investimento
- **ROAS**: número grande, cor determinada pelo tier (ver tabela abaixo)
- **Demais criativos**: tabela compacta abaixo dos cards, inicialmente oculta, toggle "Ver todos os N"
- **Mobile**: cards em scroll horizontal com `snap-x`, tabela em `overflow-x-auto`

### GoogleLeaderboard

- **Cada linha**: `#N` · nome (truncado) · barra de investimento proporcional · ROAS colorido
- **Barra**: largura proporcional ao maior investimento do conjunto, cor determinada pelo tier
- **Exibição**: todas as campanhas direto (sem cards); acima de 8 → mostra 5 + toggle

### Tiers de ROAS

| Tier   | Faixa         | Cor CSS          |
|--------|---------------|------------------|
| Alto   | ≥ 3×          | `var(--forest)`  |
| Médio  | 1.5× – 3×     | âmbar (`#f59e0b`)|
| Baixo  | < 1.5×        | `var(--crimson)` |

Tiers hardcoded — sem configuração por cliente.

---

## Ordenação

Ambos os arrays ordenados por ROAS decrescente no cliente, antes de renderizar. `null` vai para o final da lista.

---

## Edge Cases

| Situação | Comportamento |
|---|---|
| `metaAds.length === 0` | Mensagem "Sem criativos detalhados neste mês" |
| `googleAds.length === 0` | Mensagem "Sem campanhas detalhadas neste mês" |
| Card sem `imagem_url` | Gradiente placeholder escuro |
| ROAS `null` | Exibe `—`, sem coloração de tier |
| Nome muito longo | `truncate` + atributo `title` para tooltip nativo |
| `loading === true` | Skeleton/placeholder "Carregando…" (igual ao padrão atual da page) |

---

## Testes

Nenhum teste novo de unidade — componente puramente apresentacional. Os testes e2e existentes em `cliente-dashboard.spec.ts` não são afetados. Testes e2e do gestor não existem ainda e não são requisito desta entrega.

---

## Arquivos afetados

| Arquivo | Ação |
|---|---|
| `web/frontend/components/PerformanceLeaderboard.tsx` | Criar |
| `web/frontend/app/gestor/[slug]/page.tsx` | Editar (substituir seção Campanhas, remover states de toggle) |
