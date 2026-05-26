# Design: Cliente Dashboard Cinemático

**Data:** 2026-05-26
**Branch:** main
**Status:** Aprovado

---

## Problema

A aba do cliente (`/cliente/dashboard`) é o produto que a agência entrega ao cliente final — é onde o cliente acompanha o trabalho que está sendo pago. Hoje ela é funcional, mas densa: KPIs em cards apertados, gráfico padrão, criativos como linhas de tabela com thumbnail de 40 px. Não comunica a qualidade do trabalho da agência, e o cliente fecha rápido porque "é só uma planilha bonita".

A aba precisa virar **vitrine**. Quando o cliente abre, deve sentir que está vendo um relatório de luxo, não um dashboard genérico — isso eleva a percepção de valor do serviço prestado pela agência.

---

## Solução

Refazer a jornada do cliente em três telas (login → splash → dashboard) com tratamento **editorial cinemático**: tipografia Fraunces italic em escala grande, JetBrains Mono nos números, paleta paper/forest preservada, animações ricas de entrada, gráficos como peças visuais centrais, criativos como galeria. Lê-se como uma matéria editorial de cima pra baixo, não como uma planilha.

Sem mudar o stack (Next 14 + Tailwind + Recharts) e sem novo backend — apenas componentes novos no frontend e um endpoint pequeno para "insight do mês" calculado em runtime.

---

## Arquitetura

Tudo dentro da app existente, sem nova infra:

- **Frontend:** novos componentes em `web/frontend/components/`, refator de `web/frontend/app/cliente/login/page.tsx` e `web/frontend/app/cliente/dashboard/page.tsx`
- **Backend:** um endpoint novo (`GET /api/cliente/highlight`) que computa heurísticas sobre a timeline já existente. Sem novo modelo de dados.
- **Dependências novas:** `framer-motion` (animações declarativas), `react-intersection-observer` (gatilhos de scroll). Ambas pequenas, populares, sem conflito com a stack atual.

---

## Direção Visual

**Estilo:** "Editorial cinemático" — paleta paper/forest atual elevada com escala tipográfica grande, animações ricas e elementos cinemáticos pontuais.

**Tipografia:**
- Display: Fraunces italic, pesos 300–400, tamanhos 56–128 px nos heros
- Texto: Geist (sem-serif atual), 11–14 px
- Números/dados: JetBrains Mono com `tabular-nums`
- Eyebrows: Geist 9–11 px, `text-transform: uppercase`, `letter-spacing: 0.2em`

**Cores:** Mantém variáveis CSS atuais (`--paper`, `--ink`, `--forest`, `--amber`, `--crimson`). Dark mode existente (`ThemeToggle.tsx`) é preservado e recebe o mesmo tratamento cinemático.

**Elementos cinemáticos:**
- Gradient mesh sutil no background (radial-gradients já presentes em `globals.css` ficam mais fortes na tela de login e splash)
- Animações de entrada em cascata (`framer-motion` stagger)
- Números que contam ao carregar (`Counter.tsx`)
- Gráfico de linha que se desenha ao entrar em viewport (`stroke-dasharray` animation)
- Hover states com profundidade (escala, sombra, glow no forest)
- Paralaxe sutil no mouse na tela de login

**Acessibilidade:** `prefers-reduced-motion: reduce` desliga todas as animações e mostra estados finais imediatamente.

---

## Jornada (4 telas)

### 1. Login — `/cliente/login`

**Visão:** Porta de hotel boutique. Foco absoluto no ato de entrar.

- Background: paper (light) ou ink (dark) com gradient mesh animado lento (forest + amber, opacidade 0.04–0.08, movimento de 30 s em loop) e paralaxe leve baseada na posição do mouse
- Card central minimalista (sem borda, só espaçamento generoso):
  - "Bem-vindo." em Fraunces italic 56 px
  - Subtítulo em Geist 12 px: "Entre com o CNPJ para ver seus dados de performance"
  - Campo CNPJ (input atual com máscara) — placeholder em Fraunces italic
  - Campo senha (input atual)
  - Botão "Entrar" no estilo `pill` atual, mas com transição suave de fundo no hover
- Sem cabeçalho, sem footer, sem outros elementos. Tela inteira.
- Loading state: botão troca texto para "Entrando…" com pulse sutil

### 2. Splash de boas-vindas — `/cliente/dashboard?intro=1`

**Visão:** Cortina cinematográfica antes do dashboard aparecer. Curta (~2,5 s), com escape.

- Overlay full-screen sobre o dashboard
- Composição:
  - Pequena linha em Geist eyebrow: data ("26 de maio · 2026") e nome do cliente em Fraunces italic ("Calçados Pampa")
  - Saudação grande em Fraunces italic 96–128 px (responsivo): "Boa tarde, {nome_cliente}." — usa o `nome` retornado por `/api/cliente/me` sem truncar (ex: "Calçados Pampa", não "Calçados"). Entra com fade-up + delay 200 ms
  - Linha de highlight em Fraunces italic 18–22 px: gerada pelo backend (`/api/cliente/highlight`). Exemplos:
    - "Maio foi seu melhor mês em ROAS dos últimos 12 meses."
    - "+23% em faturamento vs. abril."
    - Fallback se não houver: "Aqui está sua performance de maio."
  - Botão "Continuar →" em Geist 11 px uppercase, canto inferior direito
- Auto-advance em 3 s ou clique para pular
- Skip automático se `localStorage.getItem('splash-seen-{YYYY-MM-DD}')` existir
- Quando some: fade-out 400 ms revelando o dashboard

### 3. Dashboard — `/cliente/dashboard`

**Visão:** Matéria editorial de cima pra baixo. Cada seção tem revelação em scroll (`RevealOnView`).

Estrutura em ordem vertical:

#### 3.1. Header (fixo no topo, slim)
- Logo do cliente + nome em Fraunces 16 px
- Direita: seletor de mês (estilizado, mantém `<select>` mas com tipografia maior)
- Botão "Sair" no estilo `pill` discreto

#### 3.2. Hero do mês
- Bloco com altura mínima ~50 vh
- Eyebrow: "Faturamento · Maio 2026"
- Número principal: Faturamento em Fraunces italic 96–128 px, JetBrains Mono para o valor — anima de 0 ao valor real em 1,2 s com easing `easeOutExpo`
- Bloco secundário (ROAS): segue mesmo padrão, em forest
- Δ vs mês anterior em Geist mono pequeno: "↗ +23,4% vs. Abril · maior valor em 12 meses"
- Spark de 12 meses como fundo discreto (`opacity: 0.15`), `position: absolute` atrás do número — omitido se timeline tiver < 3 pontos (vira só fundo plano)
- Estado vazio: se `snapMes` for null, mostra "Seus dados estão sendo processados. Volte em breve." centralizado, sem skeleton

#### 3.3. KPIs secundários
- Fileira horizontal de 4 colunas (Investimento · CPA · Leads · Vendas)
- Divididos por filetes verticais (`border-right: 1px solid var(--rule-soft)`)
- Cada coluna:
  - Eyebrow 9 px
  - Valor em JetBrains Mono 22 px
  - Mini-spark SVG de 6 meses, altura 24 px, stroke forest com opacidade 0.6
- Hover: leve subida (`translateY(-2px)`) + tooltip pequeno revela "+X% vs mês anterior"
- Mobile: vira grid 2x2 com mesma elegância

#### 3.4. Evolução
- Bloco full-width altura 400 px
- Toggle de métrica acima (Faturamento / ROAS / Investimento) — segmentos com sublinhado animado no ativo
- Gráfico Recharts:
  - Linha forest 1,8 px com `dot` arredondado de 4 px
  - Gradient fill abaixo da linha (`linearGradient` forest → transparente)
  - Eixos minimalistas: ticks pequenos, sem grid horizontal denso
  - Tooltip rico: card flutuante com mês, valor formatado e Δ vs mês anterior
  - Animação de desenho: stroke começa transparente e revela da esquerda pra direita (1,5 s)
- Se houver < 2 pontos: omitir seção inteira

#### 3.5. Top criativos Meta
- Eyebrow: "Top criativos · Meta Ads"
- 3 cards lado a lado (grid de 3 colunas em desktop, carrossel horizontal scroll-snap em mobile), proporção 16:9
- Cada card:
  - Imagem do criativo cobrindo o card (object-cover)
  - Overlay inferior com gradiente preto → transparente
  - Sobre o overlay: nome do anúncio em Geist 11 px + ROAS grande em JetBrains Mono ("5,8×")
  - Badge "#1", "#2", "#3" no canto superior esquerdo em Geist eyebrow
  - Hover: leve zoom da imagem (1.03), badge ganha glow forest sutil
- Estado vazio: bloco discreto "Sem criativos detalhados neste mês."
- Link inferior "Ver todos os {N} →" abre o drawer (3.7)

#### 3.6. Top campanhas Google
- Eyebrow: "Top campanhas · Google Ads"
- Lista vertical de 5 itens (não grid)
- Cada item: nome em Fraunces 16 px + barra horizontal mostrando proporção de investimento + ROAS à direita em JetBrains Mono
- Barra tem fundo `paper-soft` e fill `forest` com `transform: scaleX()` animado ao entrar em viewport
- Estado vazio: bloco discreto
- Link "Ver todas as {N} →" abre o drawer (3.7)

#### 3.7. Drawer "Ver todos"
- Painel lateral direito (largura 720 px desktop, full-width mobile)
- Slide-in de 300 ms a partir da direita, fundo com backdrop blur leve
- Header com título ("Todos os criativos · Meta Ads") e botão fechar (X)
- Conteúdo: tabela completa atual com tipografia melhorada (mesma estrutura de colunas que existe hoje, mas com espaçamento maior, header sticky, e rows com hover sutil)
- Fechar com ESC ou clique no backdrop

#### 3.8. Rodapé
- Crédito da agência: logo pequeno + "Relatório gerado em {data} · {nome da agência}"
- Tipografia Geist 10 px muted
- Margem superior generosa (96 px+) para fechar como "back cover" de revista

### 4. Estados globais

**Loading inicial:**
- Splash com texto "Carregando…" em Fraunces italic 24 px, centralizado, com fade in/out lento
- Sem skeletons (eles destruiriam a sensação cinemática)

**Erro de fetch:**
- Card central minimalista com mensagem em crimson
- Botão "Tentar novamente" no estilo pill

**Sessão expirada:**
- Redireciona para `/cliente/login?expired=1` (comportamento atual)

---

## Componentes Novos

Em `web/frontend/components/`:

| Componente | Responsabilidade | Props principais |
|---|---|---|
| `LoginScene.tsx` | Substitui `app/cliente/login/page.tsx` (ou é importado por ele) — orquestra background animado + form | — |
| `WelcomeSplash.tsx` | Overlay full-screen de boas-vindas | `nomeCliente: string`, `highlight: Highlight \| null`, `onDismiss: () => void` |
| `HeroMonth.tsx` | Bloco hero com Faturamento + ROAS animados e spark de fundo | `faturamento`, `roas`, `varPct`, `timeline12m` |
| `KpiRow.tsx` | Fileira de 4 KPIs com mini-sparks | `kpis: { label, value, spark6m, varPct }[]` |
| `EvolutionChartHero.tsx` | Gráfico full-width com toggle de métrica e animação de desenho | `timeline: TimelineItem[]` |
| `CreativeGallery.tsx` | Galeria de top 3 criativos Meta + botão "ver todos" | `criativos: MetaAd[]`, `onSeeAll: () => void` |
| `CampaignBars.tsx` | Top 5 campanhas Google com barras de proporção | `campanhas: GoogleAd[]`, `onSeeAll: () => void` |
| `DetailsDrawer.tsx` | Drawer lateral genérico que renderiza tabela completa | `open`, `onClose`, `title`, children |
| `Counter.tsx` | Utilitário: anima de 0 até valor com formatador | `to: number`, `format: (n) => string`, `duration?` |
| `RevealOnView.tsx` | Wrapper que aplica fade-up quando entra em viewport | children, `delay?` |
| `MetricToggle.tsx` | Segmento de toggle (Faturamento/ROAS/Investimento) com sublinhado animado | `options`, `value`, `onChange` |

Cada componente é client-only (`"use client"`), unidade independente, sem dependência cruzada além das props.

---

## Backend

### Novo endpoint: `GET /api/cliente/highlight`

Calcula em runtime sobre a timeline do cliente logado. Retorna o "destaque do mês" para a splash.

**Resposta:**
```json
{
  "type": "best_roas_window" | "best_revenue_window" | "growth_vs_prev" | null,
  "metric": "roas" | "faturamento" | null,
  "value": 4.2,
  "period_months": 12,
  "message": "Maio foi seu melhor mês em ROAS dos últimos 12 meses."
}
```

**Heurísticas (ordem de prioridade):**
1. Se ROAS do mês corrente é o maior dos últimos 12 meses (e existem >=6 meses de dados): `best_roas_window`
2. Senão, se faturamento do mês corrente é o maior dos últimos 12 meses: `best_revenue_window`
3. Senão, se crescimento de faturamento vs. mês anterior é >= +15%: `growth_vs_prev`
4. Senão, `null` (cliente recebe fallback no front: "Aqui está sua performance de {mês}.")

**Implementação:** função pura em `web/backend/services/cliente_highlight.py`, chamada por novo handler em `web/backend/api/cliente/highlight.py`. Lê a mesma fonte que `timeline` já lê (sem nova tabela).

### Endpoints existentes preservados

- `GET /api/cliente/me`
- `GET /api/cliente/timeline?meses=12`
- `GET /api/cliente/meses-disponiveis`
- `GET /api/cliente/breakdown?mes=YYYY-MM`
- `POST /api/cliente/login`
- `POST /api/cliente/logout`

Nada muda na shape de resposta. Apenas o `dashboard/page.tsx` passa a chamar `/highlight` adicionalmente.

---

## Animações & Performance

**Princípios:**
- Animações são **bonus**, nunca bloqueiam interação
- `prefers-reduced-motion: reduce` desliga tudo (estados finais imediatos)
- Toda animação tem duração entre 300–1500 ms; nada lento demais
- `will-change` aplicado apenas em elementos que vão animar

**Lista das animações:**

| Onde | O quê | Duração | Tecnologia |
|---|---|---|---|
| Login background | Gradient mesh lento + paralaxe mouse | loop 30 s | CSS keyframes + JS pointer move |
| Splash entrada | Fade-up da saudação + stagger das linhas | 600 ms | framer-motion |
| Splash saída | Fade-out + slide-up | 400 ms | framer-motion |
| Hero números | Conta de 0 até valor com `easeOutExpo` | 1200 ms | Counter.tsx (rAF) |
| KPIs secundários | Fade-up em cascata (stagger 80 ms) | 500 ms | framer-motion |
| Evolution chart | Desenho da linha (stroke reveal) | 1500 ms | SVG `stroke-dasharray` |
| Creative cards | Fade-up em cascata + scale 0.98→1 | 600 ms | framer-motion |
| Campaign bars | `scaleX` 0→1 das barras (stagger 60 ms) | 800 ms | framer-motion |
| Hover criativos | Image scale 1→1.03 | 300 ms | CSS transition |
| Drawer | Slide-in da direita + backdrop fade | 300 ms | framer-motion |

**Performance:**
- Bundle: framer-motion ~50 KB gzip — aceitável para a página que ela serve
- Imagens dos criativos: já vêm do backend, sem otimização adicional necessária (são thumbnails do Meta)
- Recharts já está instalado e não muda

---

## Responsividade

| Quebra | Estratégia |
|---|---|
| Desktop (>=1024 px) | Layout principal, hero 128 px, grid de 3 criativos |
| Tablet (768–1023 px) | Hero 96 px, KPIs continuam 4 col, criativos 3 col com gap menor |
| Mobile (<768 px) | Hero 64 px, KPIs grid 2x2, criativos viram carrossel horizontal scroll-snap, drawer vira full-screen |

Splash funciona em todas as quebras — apenas tipografia escala.

---

## Estados Vazios / Edge Cases

| Caso | Comportamento |
|---|---|
| Cliente sem dados ainda | Hero some, mostra mensagem central "Seus dados estão sendo processados. Volte em breve." |
| Mês selecionado sem breakdown | Seções de campanhas mostram "Sem detalhamento de campanhas neste mês." |
| Timeline com 1 ponto | Seção de evolução é omitida |
| Highlight retorna null | Splash mostra "Aqui está sua performance de {mês}." |
| Cliente sem logo | Header mostra só o nome em Fraunces |
| Highlight indisponível (erro) | Splash carrega sem highlight (não bloqueia) |
| Sem `prefers-reduced-motion` mas conexão lenta | Animações continuam, mas dados aparecem em estados finais até animação iniciar |

---

## Fora de Escopo

- Editor de comentários manuais da agência (insights são auto-gerados)
- Export PDF, compartilhamento por link, notificações
- Comparativo lado a lado Meta vs. Google
- Funil de conversão visual (impressões → cliques → leads → vendas)
- Refator da aba `/gestor` ou da área pública `/cases`
- Mudança de stack ou backend principal

---

## Testes

- **Visual:** screenshots Playwright nas 3 telas em desktop e mobile (light e dark)
- **Funcional:**
  - Login com CNPJ válido → redireciona para `/cliente/dashboard?intro=1`
  - Splash some após 3 s ou no clique
  - Splash é pulada na segunda visita no mesmo dia
  - Drawer abre/fecha por clique e ESC
  - Toggle de métrica troca a série do gráfico
  - `prefers-reduced-motion` desliga animações
- **Backend:**
  - `/highlight` retorna `best_roas_window` quando ROAS atual é o maior em 12 meses
  - `/highlight` retorna `null` quando não há highlight relevante
  - `/highlight` exige autenticação

---

## Critérios de Aceitação

1. Cliente loga em `/cliente/login` e a tela tem background animado, sem cabeçalho/footer
2. Após login, aparece splash de boas-vindas com nome do cliente e highlight do mês — soma menor que 3,5 s
3. Dashboard tem hero com Faturamento e ROAS em Fraunces italic ≥ 64 px que animam de 0 ao valor
4. KPIs secundários ficam numa única fileira (desktop) com mini-sparks
5. Gráfico de evolução desenha a linha ao entrar em viewport
6. Top 3 criativos Meta aparecem como cards visuais 16:9 com imagem em destaque
7. "Ver todos" abre drawer lateral com tabela completa
8. `prefers-reduced-motion` desativa todas as animações
9. Light mode e dark mode ambos renderizam o mesmo design com elegância
10. Mobile (375 px) funciona — nada quebrado, hierarquia preservada
