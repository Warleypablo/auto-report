# Re-tema do Painel Gestor — Dark "Turbo" — Design

**Data:** 2026-06-01
**Status:** Aprovado (design) — aguardando revisão da spec

## Objetivo

Re-tematizar o painel do gestor (`/gestor/*`) para a identidade visual "Turbo" — fundo
escuro, acentos ciano + roxo, glows — unificando o painel com o novo report em PDF.
Hoje o painel usa um tema editorial claro (creme/verde floresta, serif Fraunces).

**Efeito desejado:** painel e PDF passam a ser a mesma marca ("growth/tech"),
sem refazer layout — só a pele (cores + acentos + brilhos).

## Escopo

**Dentro do escopo** (tudo sob `/gestor`):
- Shell / sidebar (`app/gestor/_shell.tsx` e o `Sidebar` interno em `page.tsx`)
- Aba **Dashboard** (KPIs, gráficos Recharts, tabelas)
- Aba **Reportes** (`AbaClientes`, fila de jobs, filtros)
- Aba **Configurações** (`AbaConfiguracoes`, formulários)
- Páginas filhas que herdam o shell: **Criativos** (`performance`), **TurboMax**,
  **Inteligência**, **admin/\***

**Fora do escopo:**
- Páginas voltadas ao cliente (`/cliente/*`) e o report HTML do cliente — continuam
  no tema atual. **Por isso o re-tema é escopado, não global** (ver Arquitetura).
- O PDF (`core/templates/*`) — já está na identidade Turbo; não muda.
- Layout/estrutura/markup — só muda cor, acento e brilho.

## Arquitetura

### Decisão central: escopar o tema, não mexer no `:root`

O `globals.css` define a paleta em `:root` (claro) e `.dark` (escuro editorial),
e **essas variáveis valem para o app inteiro** — inclusive as páginas do cliente.
Trocar o `:root` re-tematizaria tudo, o que não queremos.

Em vez disso, defino a paleta Turbo sob um seletor **escopado ao subtree do gestor**.
Variáveis CSS são herdadas: um `--paper` redefinido num ancestral do gestor vence o
`--paper` de `:root`/`.dark` para todo o subtree, sem tocar no resto do app.

```css
/* globals.css — novo bloco */
.gestor-turbo {
  --paper:       #060612;   /* fundo da página            */
  --paper-soft:  #0F0F25;   /* cards / sidebar            */
  --paper-deep:  #0C0C22;   /* superfícies recuadas/hover */
  --ink:         #FFFFFF;   /* texto principal            */
  --ink-soft:    #C7CBD9;   /* texto secundário           */
  --muted:       #8A90A6;   /* texto terciário / eixos    */
  --rule:        #20203A;   /* divisórias fortes          */
  --rule-soft:   #1A1A35;   /* bordas de card             */
  --forest:      #00C8FF;   /* ACENTO PRIMÁRIO (ciano)    */
  --forest-deep: #0094CC;   /* hover do acento            */
  --amber:       #D9A24B;   /* 2ª série / alerta ámbar    */
  --crimson:     #FF5C72;   /* erro / destrutivo          */
  --accent:      #00C8FF;

  /* novas — específicas da marca Turbo */
  --cyan:        #00C8FF;
  --purple:      #7B2FFF;
  --gradient:    linear-gradient(90deg, #00C8FF, #7B2FFF);
  --glow-cyan:   0 0 0 1px rgba(0,200,255,.10), 0 8px 30px -12px rgba(0,200,255,.35);
  --glow-purple: 0 8px 30px -12px rgba(123,47,255,.30);

  /* elevação re-equilibrada para fundo escuro */
  --elev-sm:   0 1px 2px rgba(0,0,0,.40);
  --elev-md:   0 4px 18px -6px rgba(0,0,0,.55);
  --elev-lift: 0 10px 34px -10px rgba(0,0,0,.65), 0 0 24px -14px rgba(0,200,255,.30);

  color-scheme: dark; /* scrollbars / date-picker nativos em dark */
}
```

O wrapper recebe a classe em **`app/gestor/layout.tsx`** (raiz de todas as rotas
`/gestor`). Como o `layout.tsx` já existe e envolve tudo, é o ponto natural:

```tsx
<div className="gestor-turbo min-h-screen bg-[var(--paper)]"> … </div>
```

Vantagens: zero risco para `/cliente/*`; vence o toggle global `.dark` (o gestor fica
Turbo independentemente do tema do sistema); um único ponto de verdade para a paleta.

### Como o cascade resolve ~80% sozinho

Verificado no código: shell, KPI cards, eixos/barras dos gráficos Recharts
(`fill="var(--forest)"`, `stroke="var(--rule-soft)"`, `color-mix(... var(--forest) ...)`),
tabelas, inputs, badges e progress bars **já consomem as variáveis**. Trocar os tokens
re-tematiza tudo isso automaticamente.

### Polish direcionado (onde token sozinho não basta)

1. **KPI cards (Dashboard):** classe utilitária nova `.kpi-turbo` aplicada ao card,
   com a barra-gradiente ciano→roxo no topo via `::before` (`height:2px`, `--gradient`)
   + `--glow-cyan` sutil no `box-shadow`. Número grande mantém `.font-mono-num`.
2. **Gráficos Recharts:**
   - Série "Faturamento" → `var(--cyan)`; série "Investimento" → `var(--amber)`
     (ámbar dá contraste melhor que roxo contra ciano em barras lado a lado).
   - ROAS top-10 já usa `color-mix(var(--forest) → var(--paper-deep))` = vira
     degradê ciano→escuro automaticamente. Sem mudança.
   - Grid/eixos herdam `--rule-soft`/`--muted`. Sem mudança.
3. **Sidebar:** item ativo passa de "fundo `--paper-deep`" para acento ciano —
   fundo `rgba(0,200,255,.10)` + texto `--cyan` + barra lateral ciano. Ajuste nas
   classes do `Sidebar`/`_shell`.
4. **Inputs / selects / foco:** o anel de foco já é `--forest` → vira ciano. Conferir
   a classe global `.select` (seta SVG com cor fixa `#1A1916`) — se usada no gestor,
   trocar a seta para clara; senão deixar.
5. **Uma cor hardcoded:** `page.tsx:1869` usa `#c0392b` → trocar por `var(--crimson)`.

## Tipografia

**Mantém as fontes atuais** (Fraunces display nos títulos, JetBrains Mono nos números).
Serif branca sobre fundo escuro lê como "premium", e manter as fontes evita churn em
dezenas de usos. O caráter "Turbo" vem do fundo escuro + acentos + glows, não da troca
de fonte. (Trocar para Inter-bold, como no PDF, fica como possível iteração futura.)

## Riscos e auditoria

| Risco | Tratamento |
|---|---|
| Cor clara hardcoded "vazando" branco no dark | Auditoria: só há `#c0392b` em `page.tsx`. `EvolutionChart` (cheio de hex) **não** é usado no gestor — confirmado por grep. |
| `performance/page.tsx` (Criativos) tem muitos hex escuros próprios | Já é escuro; herda o shell. Validar visualmente, mas não deve quebrar. |
| Classe global `.select` com seta SVG escura | Verificar se aparece no gestor; trocar seta para clara só se necessário. |
| Toggle global `.dark` + bootstrap em `app/layout.tsx` | Não tocar. O escopo `.gestor-turbo` vence por ser descendente. Páginas do cliente seguem com o toggle. |
| `::selection` / glows do `body` são globais | `::selection` herda `--forest` (vira ciano) ok. Glow de fundo: adicionar radial ciano/roxo sutil no wrapper `.gestor-turbo`, sem mexer no `body`. |

## Verificação

1. Subir o localhost (frontend + backend) e logar no `/gestor`.
2. Conferir **visualmente** cada área, procurando "vazamento" de branco/creme:
   - Shell + sidebar (item ativo ciano, hover, rodapé do usuário)
   - Dashboard: KPI cards (barra-gradiente + glow), os 2 gráficos, tabela
   - Reportes: filtros, fila de jobs (badges/progress), tabela de clientes
   - Configurações: formulários, selects, inputs (foco ciano)
   - Criativos, TurboMax (herança do shell — sanity check)
3. Conferir contraste de texto (WCAG AA) nos tons `--muted`/`--ink-soft` sobre `--paper`.
4. Screenshot de cada aba para revisão.

## Critérios de sucesso

- Painel inteiramente escuro, coeso com o PDF (ciano + roxo, glows).
- Nenhuma superfície creme/clara remanescente nas áreas do gestor.
- Páginas `/cliente/*` **inalteradas**.
- Sem regressão de layout/funcionalidade — só pele.
