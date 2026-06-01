# Re-tema Dark "Turbo" do Painel Gestor — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar tarefa-a-tarefa. Passos usam checkbox (`- [ ]`).

**Goal:** Re-tematizar todo o painel `/gestor` para a identidade "Turbo" (fundo escuro, acento ciano `#00C8FF` + roxo `#7B2FFF`, glows), unificando painel e PDF — sem mexer em layout nem nas páginas do cliente.

**Architecture:** Escopo CSS `.gestor-turbo` num wrapper de `app/gestor/layout.tsx` redefine os CSS variables (paleta Turbo) só para o subtree do gestor — ~90% das telas re-tematizam sozinhas por já usarem `var(--…)`. O resto é (a) override escopado das decorações globais que dependem de `.dark`, (b) realce de marca nos estados ativos/CTAs/KPIs, (c) correção de literais (`text-white` sobre ciano, `bg-*-50`, esmeralda hardcoded).

**Tech Stack:** Next.js 14 (App Router), Tailwind CSS (arbitrary `var()` + `/alpha`), Recharts, CSS custom properties.

**Nota sobre testes:** este é um re-tema puramente visual (CSS/classes). Não há teste unitário cabível; a verificação é **build passando** (`npm run build` / typecheck) + **revisão visual por área** (screenshots). Cada task termina com commit; a verificação visual consolidada é a Task 10.

**Regra de ouro para os Edits:** os `anchorCode` abaixo foram extraídos verbatim do código atual. Se um `old_string` não casar exatamente, **pare e re-leia o arquivo** na região indicada antes de editar — não invente. Vários literais idênticos se repetem; sempre inclua a linha de condição acima para isolar a ocorrência (nunca `replace_all` numa classe solta).

**Tokens permanecem em formato HEX.** O painel já usa `bg-[var(--forest)]/12` (modificador `/alpha` do Tailwind sobre `var()`). Isso só funciona com hex/rgb; **não** converter os tokens para canais `r g b` crus, senão essas classes quebram.

---

## File Structure

- `app/globals.css` — **Modify (append):** novo bloco `.gestor-turbo { … }` com paleta + tokens de marca + `.kpi-turbo` + overrides escopados das decorações (`.mesh-bg`, `.paper-grain::before`, `.select`, `::selection`, `.progress-shimmer`, tint radial).
- `app/gestor/layout.tsx` — **Modify:** adicionar classe `gestor-turbo` ao wrapper.
- `app/gestor/_shell.tsx` — **Modify:** estado ativo da nav → ciano.
- `app/gestor/page.tsx` — **Modify:** Sidebar interno (ativos → ciano), KPI cards (`.kpi-turbo`), gráfico ROAS (degradê ciano→roxo), `text-white`→`--on-accent`, badges, remover fallback `#c0392b`.
- `app/gestor/performance/page.tsx` + `components/AdThumb.tsx` + `components/performance/FiltrosBar.tsx` — **Modify:** estados ativos → ciano, KPI herói, gradientes de thumb, cores do scatter.
- `app/gestor/turbomax/page.tsx` — **Modify:** sweep esmeralda `rgba(52,211,153,…)` → ciano/roxo.
- `app/gestor/inteligencia/page.tsx` — **Modify:** badges `bg-*-50` + `#f59e0b/#b45309` → tokens.
- `app/gestor/admin/*` + `app/gestor/[slug]/page.tsx` — **Modify:** KPI cards, badges, foco, scrim.
- `web/frontend/lib/roas-tier.ts` — **Audit/Modify (condicional):** alinhar tiers se usarem classes Tailwind fixas.

---

## Task 1: Fundação — escopo `.gestor-turbo` (paleta + tokens + `.kpi-turbo` + overrides de decoração)

**Files:**
- Modify: `web/frontend/app/globals.css` (append ao final do arquivo)
- Modify: `web/frontend/app/gestor/layout.tsx`

- [ ] **Step 1: Aplicar a classe de escopo no layout do gestor**

Em `web/frontend/app/gestor/layout.tsx`, trocar:

```tsx
    <div className="min-h-screen bg-[var(--paper)]">
      {children}
    </div>
```

por:

```tsx
    <div className="gestor-turbo min-h-screen bg-[var(--paper)]">
      {children}
    </div>
```

- [ ] **Step 2: Append do bloco Turbo no globals.css**

Adicionar ao **final** de `web/frontend/app/globals.css` (bloco puramente aditivo — não altera `:root`/`.dark`):

```css
/* ===================================================================== */
/* Painel Gestor — escopo dark "Turbo" (ciano + roxo)                    */
/* Redefine os tokens só para o subtree /gestor. Independente de .dark.  */
/* ===================================================================== */
.gestor-turbo {
  --paper:       #060612;   /* fundo da página            */
  --paper-soft:  #0F0F25;   /* cards / sidebar            */
  --paper-deep:  #0C0C22;   /* superfícies recuadas/hover */
  --ink:         #F4F6FB;   /* texto principal            */
  --ink-soft:    #C7CBD9;   /* texto secundário           */
  --muted:       #8A90A6;   /* texto terciário / eixos    */
  --rule:        #20203A;   /* divisórias fortes          */
  --rule-soft:   #1A1A35;   /* bordas de card             */
  --forest:      #00C8FF;   /* ACENTO PRIMÁRIO (ciano)    */
  --forest-deep: #7B2FFF;   /* roxo — gradientes/hover    */
  --amber:       #F5B544;   /* 2ª série / alerta          */
  --crimson:     #FF5C72;   /* erro / destrutivo (texto)  */
  --accent:      #00C8FF;

  /* tokens novos de marca */
  --cyan:        #00C8FF;
  --purple:      #7B2FFF;
  --forest-soft: rgba(0, 200, 255, 0.12); /* fundo do estado ativo      */
  --on-accent:   #04040E;                  /* ink escuro p/ texto sobre acento */
  --gradient:    linear-gradient(90deg, #00C8FF, #7B2FFF);
  --glow-cyan:   0 0 0 1px rgba(0,200,255,.12), 0 10px 32px -12px rgba(0,200,255,.45);

  /* elevação re-equilibrada p/ fundo escuro */
  --elev-sm:     0 1px 2px rgba(0,0,0,.40);
  --elev-md:     0 4px 18px -6px rgba(0,0,0,.55);
  --elev-lift:   0 10px 34px -10px rgba(0,0,0,.65), 0 0 24px -14px rgba(0,200,255,.30);

  color-scheme: dark; /* scrollbars / date-picker nativos em dark */

  /* ambient glow ciano/roxo no fundo do painel (substitui o tint do body) */
  background-image:
    radial-gradient(1100px 560px at 0% -8%, rgba(0,200,255,.07), transparent 60%),
    radial-gradient(900px 520px at 100% -12%, rgba(123,47,255,.06), transparent 55%);
  background-attachment: fixed;
}

/* KPI card: barra-gradiente ciano→roxo no topo + glow no hover */
.gestor-turbo .kpi-turbo::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--gradient);
}
.gestor-turbo .kpi-turbo {
  transition: box-shadow .25s ease, transform .25s ease;
}
.gestor-turbo .kpi-turbo:hover {
  box-shadow: var(--glow-cyan);
}

/* ---- Overrides de decorações globais que dependem de .dark ---- */
/* Sem isto, ao visitar /gestor em tema CLARO, estas usam a variante light e quebram. */

/* seleção de texto: ciano com ink escuro legível */
.gestor-turbo ::selection { background: var(--forest); color: #04040E; }

/* seta do <select className="select">: stroke claro/ciano em vez de #1A1916 */
.gestor-turbo .select {
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none'><path d='M1 1.5L6 6.5L11 1.5' stroke='%2300C8FF' stroke-width='1.4'/></svg>");
}
.gestor-turbo .select:focus { border-bottom-color: var(--forest); box-shadow: 0 1px 0 0 var(--forest); }

/* sheen do progresso em ciano */
.gestor-turbo .progress-shimmer {
  background-image: linear-gradient(100deg, transparent 20%, rgba(0,200,255,0.30) 50%, transparent 80%);
}

/* mesh-bg e paper-grain caso usados sob o gestor (defensivo, escopado) */
.gestor-turbo .mesh-bg {
  background:
    radial-gradient(700px 500px at 20% 30%, rgba(0,200,255,0.18), transparent 60%),
    radial-gradient(600px 400px at 80% 70%, rgba(123,47,255,0.14), transparent 55%);
}
.gestor-turbo .paper-grain::before {
  mix-blend-mode: screen;
  opacity: 0.30;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.0  0 0 0 0 0.78  0 0 0 0 1.0  0 0 0 0.03 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
}
```

- [ ] **Step 3: Verificar build**

Run: `cd web/frontend && npm run build`
Expected: build conclui sem erro de CSS/TS. (Se `npm run build` for lento, `npx tsc --noEmit` valida o TS; o CSS é validado no build.)

- [ ] **Step 4: Commit**

```bash
git add web/frontend/app/globals.css web/frontend/app/gestor/layout.tsx
git commit -m "feat(gestor): escopo dark Turbo — paleta, tokens de marca e overrides de decoração"
```

---

## Task 2: Estado ativo da navegação → ciano (shell + Sidebar interno)

**Files:**
- Modify: `web/frontend/app/gestor/_shell.tsx`
- Modify: `web/frontend/app/gestor/page.tsx`

Padrão de ativo (reutilizado): `"bg-[var(--forest-soft)] font-medium text-[var(--forest)] shadow-[inset_2px_0_0_0_var(--forest)]"`.

- [ ] **Step 1: `_shell.tsx` — item de nav principal (NAV.map)**

Trocar:

```tsx
                  active
                    ? "bg-[var(--paper-deep)] font-medium text-[var(--ink)]"
                    : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
```

por:

```tsx
                  active
                    ? "bg-[var(--forest-soft)] font-medium text-[var(--forest)] shadow-[inset_2px_0_0_0_var(--forest)]"
                    : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
```

- [ ] **Step 2: `_shell.tsx` — link Configurações no rodapé**

Trocar:

```tsx
              currentTab === "configuracoes" && pathname === "/gestor"
                ? "bg-[var(--paper-deep)] font-medium text-[var(--ink)]"
                : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
```

por:

```tsx
              currentTab === "configuracoes" && pathname === "/gestor"
                ? "bg-[var(--forest-soft)] font-medium text-[var(--forest)] shadow-[inset_2px_0_0_0_var(--forest)]"
                : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
```

- [ ] **Step 3: `page.tsx` — Sidebar interno, tab principal (NAV_ITEMS.map)**

Trocar:

```tsx
                tab === id
                  ? "bg-[var(--paper-deep)] font-medium text-[var(--ink)]"
                  : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
```

por:

```tsx
                tab === id
                  ? "bg-[var(--forest-soft)] font-medium text-[var(--forest)] shadow-[inset_2px_0_0_0_var(--forest)]"
                  : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
```

- [ ] **Step 4: `page.tsx` — Sidebar interno, botão Configurações**

Trocar:

```tsx
            tab === "configuracoes"
              ? "bg-[var(--paper-deep)] font-medium text-[var(--ink)]"
              : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
```

por:

```tsx
            tab === "configuracoes"
              ? "bg-[var(--forest-soft)] font-medium text-[var(--forest)] shadow-[inset_2px_0_0_0_var(--forest)]"
              : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
```

- [ ] **Step 5: `page.tsx` — sub-tab ativa de Reportes**

Trocar `reportesTab === subId ? "font-medium text-[var(--ink)]"` por `reportesTab === subId ? "font-medium text-[var(--forest)]"`. Linha completa atual:

```tsx
                    className={["flex w-full items-center rounded-md px-3 py-1.5 text-left text-xs transition", reportesTab === subId ? "font-medium text-[var(--ink)]" : "text-[var(--muted)] hover:text-[var(--ink)]"].join(" ")}
```

vira:

```tsx
                    className={["flex w-full items-center rounded-md px-3 py-1.5 text-left text-xs transition", reportesTab === subId ? "font-medium text-[var(--forest)]" : "text-[var(--muted)] hover:text-[var(--ink)]"].join(" ")}
```

- [ ] **Step 6: `page.tsx` — sub-tab ativa de Configurações**

Trocar:

```tsx
                  configTab === subId ? "font-medium text-[var(--ink)]" : "text-[var(--muted)] hover:text-[var(--ink)]",
```

por:

```tsx
                  configTab === subId ? "font-medium text-[var(--forest)]" : "text-[var(--muted)] hover:text-[var(--ink)]",
```

- [ ] **Step 7: Verificar build e commit**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: sem erros de tipo.

```bash
git add web/frontend/app/gestor/_shell.tsx web/frontend/app/gestor/page.tsx
git commit -m "feat(gestor): estado ativo da navegação em acento ciano (shell + sidebar interno)"
```

---

## Task 3: Aba Dashboard — KPI cards `.kpi-turbo` + gráfico ROAS ciano→roxo

**Files:**
- Modify: `web/frontend/app/gestor/page.tsx` (function `AbaDashboard`)

- [ ] **Step 1: KPI cards ganham `.kpi-turbo` (barra-gradiente + glow)**

Trocar a abertura do div do card (template único que renderiza os 6 via `.map`):

```tsx
          <div key={label} className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
```

por:

```tsx
          <div key={label} className="kpi-turbo relative overflow-hidden rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
```

- [ ] **Step 2: Gráfico ROAS — degradê ciano→roxo (corrige barras escuras)**

O mix atual com `--paper-deep` (quase-preto) faz as barras de ROAS baixo sumirem. Trocar para mix ciano→roxo. Localizar o `<Cell>` do BarChart de ROAS:

```tsx
                    fill={`color-mix(in srgb, var(--forest) ${100 - i * 8}%, var(--paper-deep))`}
```

por:

```tsx
                    fill={`color-mix(in srgb, var(--forest) ${Math.max(100 - i * 10, 25)}%, var(--forest-deep))`}
```

(Topo = ciano puro; descendo mistura com roxo; piso 25% ciano / 75% roxo — sempre vívido.)

- [ ] **Step 3: (Opcional, recomendado) realçar o número do KPI financeiro/ROAS**

Manter como está — o realce de marca já vem da barra-gradiente do card. **Não** alterar `text-[var(--ink)]` do número para não poluir. (Decisão registrada: realce só na barra.)

- [ ] **Step 4: Verificar build e commit**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: sem erros.

```bash
git add web/frontend/app/gestor/page.tsx
git commit -m "feat(gestor): dashboard — KPI cards com barra-gradiente/glow e gráfico ROAS ciano→roxo"
```

---

## Task 4: Aba Reportes (AbaClientes) — ink-on-accent + realces de seleção

**Files:**
- Modify: `web/frontend/app/gestor/page.tsx` (function `AbaClientes`)

Regra desta task: todo `text-white` sobre `bg-[var(--forest)]` (ciano) vira `text-[var(--on-accent)]` (ink escuro legível). Spinner/checkmark idem.

- [ ] **Step 1: Toggle Mensal/Semanal ativo**

Trocar:

```tsx
                  frequencia === f
                    ? "bg-[var(--forest)] text-white shadow-[var(--elev-sm)]"
                    : "text-[var(--muted)] hover:text-[var(--ink)]",
```

por:

```tsx
                  frequencia === f
                    ? "bg-[var(--forest)] text-[var(--on-accent)] shadow-[0_0_0_1px_var(--forest),0_0_12px_-2px_var(--forest)]"
                    : "text-[var(--muted)] hover:text-[var(--ink)]",
```

- [ ] **Step 2: Card/linha de cliente selecionada (realce ciano)**

Trocar:

```tsx
                          isSel
                            ? "border-[var(--forest)] bg-[var(--forest)]/[0.06] shadow-[var(--elev-sm)]"
                            : "border-[var(--rule-soft)] bg-[var(--paper-soft)] hover:-translate-y-px hover:border-[var(--forest)]/60 hover:shadow-[var(--elev-md)]",
```

por:

```tsx
                          isSel
                            ? "border-[var(--forest)] bg-[var(--forest)]/[0.10] shadow-[0_0_0_1px_var(--forest),var(--elev-sm)]"
                            : "border-[var(--rule-soft)] bg-[var(--paper-soft)] hover:-translate-y-px hover:border-[var(--forest)]/60 hover:shadow-[var(--elev-md)]",
```

- [ ] **Step 3: Checkbox marcado (✓ escuro sobre ciano)**

Trocar:

```tsx
                          isSel
                            ? "border-[var(--forest)] bg-[var(--forest)] text-white shadow-[var(--elev-sm)]"
                            : "border-[var(--rule-soft)] bg-[var(--paper)] text-transparent hover:border-[var(--forest)] hover:bg-[var(--forest)]/5",
```

por:

```tsx
                          isSel
                            ? "border-[var(--forest)] bg-[var(--forest)] text-[var(--on-accent)] shadow-[0_0_8px_-1px_var(--forest)]"
                            : "border-[var(--rule-soft)] bg-[var(--paper)] text-transparent hover:border-[var(--forest)] hover:bg-[var(--forest)]/5",
```

- [ ] **Step 4: Botão "Abrir report" (linha 536)**

Trocar `text-white` por `text-[var(--on-accent)]` no botão. Anchor:

```tsx
                      className="group/btn inline-flex items-center gap-1 rounded-lg bg-[var(--forest)] px-3.5 py-1.5 text-xs font-medium text-white shadow-[var(--elev-sm)] transition-all duration-200 hover:shadow-[var(--elev-lift)] hover:brightness-110 active:scale-[0.97]">
```

vira (só `text-white` → `text-[var(--on-accent)]`):

```tsx
                      className="group/btn inline-flex items-center gap-1 rounded-lg bg-[var(--forest)] px-3.5 py-1.5 text-xs font-medium text-[var(--on-accent)] shadow-[var(--elev-sm)] transition-all duration-200 hover:shadow-[var(--elev-lift)] hover:brightness-110 active:scale-[0.97]">
```

- [ ] **Step 5: Botão primário "Gerar N reports" (linha 673) + spinner (linha 677)**

Botão — trocar `text-white` por `text-[var(--on-accent)]`:

```tsx
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--forest)] px-5 py-2.5 text-sm font-medium text-white shadow-[var(--elev-md)] transition-all duration-200 hover:shadow-[var(--elev-lift)] hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
```

vira:

```tsx
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--forest)] px-5 py-2.5 text-sm font-medium text-[var(--on-accent)] shadow-[var(--elev-md)] transition-all duration-200 hover:shadow-[var(--elev-lift)] hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
```

Spinner — trocar:

```tsx
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
```

por:

```tsx
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[var(--on-accent)]/30 border-t-[var(--on-accent)]" />
```

- [ ] **Step 6: Verificar build e commit**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: sem erros.

```bash
git add web/frontend/app/gestor/page.tsx
git commit -m "fix(gestor): reportes — ink escuro sobre acento ciano + realce de seleção/checkbox"
```

---

## Task 5: Fila/Meus Reports + Configurações — ink-on-accent, StatusBadge pill, remover #c0392b

**Files:**
- Modify: `web/frontend/app/gestor/page.tsx` (`AbaMeusReports`, `StatusBadge`, `AbaConfiguracoes`, `GestorSelect`)

- [ ] **Step 1: Botão "Abrir →" da fila (linha 751) — CTA gradiente + ink escuro**

Trocar:

```tsx
                        className="rounded-md bg-[var(--forest)] px-3 py-1 text-xs font-medium text-white transition hover:opacity-90">
```

por:

```tsx
                        className="rounded-md bg-[var(--forest)] px-3 py-1 text-xs font-medium text-[var(--on-accent)] transition hover:shadow-[0_0_12px_-2px_var(--forest)] hover:brightness-110">
```

- [ ] **Step 2: StatusBadge — virar pílula com fundo translúcido + cor cheia**

Trocar a function inteira:

```tsx
function StatusBadge({ status }: { status: JobInfo["status"] }) {
  const map: Record<JobInfo["status"], { label: string; cls: string }> = {
    done:    { label: "Concluído", cls: "text-[var(--forest)]" },
    error:   { label: "Erro",      cls: "text-[var(--crimson)]" },
    running: { label: "Gerando…",  cls: "text-[var(--amber)]" },
    pending: { label: "Na fila",   cls: "text-[var(--muted)]" },
  };
  const { label, cls } = map[status];
  return <span className={`text-xs ${cls}`}>{label}</span>;
}
```

por:

```tsx
function StatusBadge({ status }: { status: JobInfo["status"] }) {
  const map: Record<JobInfo["status"], { label: string; cls: string }> = {
    done:    { label: "Concluído", cls: "border-[var(--forest)]/30 bg-[var(--forest)]/12 text-[var(--forest)]" },
    error:   { label: "Erro",      cls: "border-[var(--crimson)]/30 bg-[var(--crimson)]/12 text-[var(--crimson)]" },
    running: { label: "Gerando…",  cls: "border-[var(--amber)]/30 bg-[var(--amber)]/12 text-[var(--amber)]" },
    pending: { label: "Na fila",   cls: "border-[var(--rule-soft)] bg-[var(--paper-deep)] text-[var(--muted)]" },
  };
  const { label, cls } = map[status];
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {label}
    </span>
  );
}
```

- [ ] **Step 3: Item selecionado do combobox GestorSelect → realce ciano**

Trocar:

```tsx
                  className={[
                    "block w-full px-3 py-2 text-left text-sm transition hover:bg-[var(--paper-soft)]",
                    value === g.nome ? "font-medium text-[var(--forest)]" : "text-[var(--ink)]",
                  ].join(" ")}
```

por:

```tsx
                  className={[
                    "block w-full px-3 py-2 text-left text-sm transition hover:bg-[var(--paper-soft)]",
                    value === g.nome ? "border-l-2 border-[var(--forest)] bg-[var(--forest)]/10 font-medium text-[var(--forest)]" : "border-l-2 border-transparent text-[var(--ink)]",
                  ].join(" ")}
```

- [ ] **Step 4: Botão "+ Adicionar cliente" — ink escuro + glow**

Trocar:

```tsx
            className="rounded-md bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
```

por:

```tsx
            className="rounded-md bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-[var(--on-accent)] transition hover:shadow-[0_0_16px_-4px_var(--forest)] hover:brightness-110"
```

- [ ] **Step 5: Botão "Desativar" — remover fallback #c0392b + ink escuro**

Trocar:

```tsx
              <button onClick={handleDesativar} disabled={deleting} className="flex-1 rounded-md bg-[var(--crimson,#c0392b)] py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50">{deleting ? "Desativando…" : "Desativar"}</button>
```

por:

```tsx
              <button onClick={handleDesativar} disabled={deleting} className="flex-1 rounded-md bg-[var(--crimson)] py-2 text-sm font-medium text-[var(--on-accent)] transition hover:brightness-110 disabled:opacity-50">{deleting ? "Desativando…" : "Desativar"}</button>
```

- [ ] **Step 6: Demais botões `text-white` sobre acento na aba Configurações**

Os modais editar/criar têm botões primários `bg-[var(--forest)] ... text-white` nas linhas ~1612, 1688, 1707, 1744, 1820, 1852. Para cada um, **localizar e trocar apenas `text-white` por `text-[var(--on-accent)]`** (mesma transformação dos passos anteriores). Re-leia cada linha antes de editar para casar o `old_string` exato (as classes ao redor variam). Se algum botão for `bg-[var(--crimson)] ... text-white`, aplicar a mesma troca para `text-[var(--on-accent)]`.

- [ ] **Step 7: Verificar build e commit**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: sem erros. Confirme com `grep -n "text-white" web/frontend/app/gestor/page.tsx` que não restou `text-white` sobre acento (matches remanescentes só devem existir se o fundo NÃO for token de acento — avalie caso a caso).

```bash
git add web/frontend/app/gestor/page.tsx
git commit -m "fix(gestor): fila/config — StatusBadge pill, ink-on-accent e remoção do fallback #c0392b"
```

---

## Task 6: Criativos (performance) — estados ativos ciano, KPI herói, gradientes de thumb, scatter

**Files:**
- Modify: `web/frontend/app/gestor/performance/page.tsx`
- Modify: `web/frontend/components/AdThumb.tsx`
- Modify: `web/frontend/components/performance/FiltrosBar.tsx`
- Audit/Modify: `web/frontend/lib/roas-tier.ts`

- [ ] **Step 1: KPI cards (KpiStrip) — barra-gradiente + glow no herói**

Trocar:

```tsx
          <div className="absolute left-0 top-3 bottom-3 w-0.5 rounded-full bg-[var(--forest)] opacity-30" />
```

por:

```tsx
          <div className="absolute left-0 top-3 bottom-3 w-0.5 rounded-full bg-gradient-to-b from-[var(--forest)] to-[var(--forest-deep)]" />
```

E na div externa do card (`relative overflow-hidden rounded-xl border ... px-5 py-5`), adicionar glow condicional ao `highlight`. Anchor atual:

```tsx
        <div key={label} className="relative overflow-hidden rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-5 py-5">
```

vira:

```tsx
        <div key={label} className={`relative overflow-hidden rounded-xl border bg-[var(--paper-soft)] px-5 py-5 ${highlight ? "border-[var(--forest)]/40 shadow-[0_0_28px_-8px_var(--forest)]" : "border-[var(--rule-soft)]"}`}>
```

- [ ] **Step 2: Tabs de rede (ativo) → ciano**

Trocar:

```tsx
                filtros.rede === r
                  ? "bg-[var(--ink)] text-[var(--paper)]"
                  : "bg-[var(--paper-soft)] text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]"
```

por:

```tsx
                filtros.rede === r
                  ? "bg-[var(--forest)] text-[var(--on-accent)] shadow-[0_0_16px_-4px_var(--forest)]"
                  : "bg-[var(--paper-soft)] text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]"
```

- [ ] **Step 3: Toggle Ranking/Scatter (ativo) → acento ciano**

Trocar:

```tsx
                view === v
                  ? "bg-[var(--paper-deep)] text-[var(--ink)]"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
```

por:

```tsx
                view === v
                  ? "bg-[var(--paper-deep)] text-[var(--forest)] ring-1 ring-[var(--forest)]/25"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
```

- [ ] **Step 4: FiltrosBar — chip de categoria ativo → ciano**

Em `components/performance/FiltrosBar.tsx`, trocar:

```tsx
                active
                  ? "bg-[var(--ink)] text-[var(--paper)]"
                  : "bg-[var(--paper-soft)] text-[var(--muted)] hover:text-[var(--ink)]"
```

por:

```tsx
                active
                  ? "bg-[var(--forest)] text-[var(--on-accent)] shadow-[0_0_14px_-4px_var(--forest)]"
                  : "bg-[var(--paper-soft)] text-[var(--muted)] hover:text-[var(--ink)]"
```

- [ ] **Step 5: FiltrosBar — toggle de faixa (ativo) → acento ciano**

Trocar:

```tsx
                state.faixaScope === s
                  ? "bg-[var(--paper-deep)] text-[var(--ink)]"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
```

por:

```tsx
                state.faixaScope === s
                  ? "bg-[var(--paper-deep)] text-[var(--forest)] ring-1 ring-[var(--forest)]/25"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
```

- [ ] **Step 6: Gradientes de miniatura — trocar o par verde por ciano (2 arquivos idênticos)**

Os arrays `THUMB_GRADIENTS` (`performance/page.tsx:50`) e `GRAD_PAIRS` (`AdThumb.tsx:3`) começam com o par verde-floresta `["#1a3d2e","#0d2019"]` do tema antigo. Em **ambos** os arquivos, trocar esse primeiro par por um par ciano escuro:

```tsx
  ["#0a2e3d", "#06181f"],
```

(Manter os demais pares — só o primeiro é o verde herdado. Re-leia cada array para confirmar a posição exata antes de editar.)

- [ ] **Step 7: Cores do scatter → tokens semânticos**

Em `performance/page.tsx`, trocar o objeto `TIER_SCATTER_COLORS`:

```tsx
const TIER_SCATTER_COLORS: Record<string, string> = {
```

Atualizar os valores para usar os tokens (mantendo as chaves): `high: "var(--forest)"`, `mid: "var(--amber)"`, `low: "var(--crimson)"`, `none: "var(--muted)"`. Re-leia as 4 linhas (148-151) e troque os hex (`#34d399`/`#facc15`/`#f87171`/`#6b7280`) pelos tokens correspondentes.

- [ ] **Step 8: Auditar `lib/roas-tier.ts`**

Run: `grep -nE "#[0-9A-Fa-f]{3,6}|emerald|amber-|red-|green-|gray-|slate-" web/frontend/lib/roas-tier.ts`
- Se `TIER_TEXT`/`TIER_BAR` usarem `var(--…)`: **nenhuma ação** (cascateia).
- Se usarem classes Tailwind fixas (`text-emerald-500`, `bg-amber-500`…): trocar pelas equivalentes em token (`text-[var(--forest)]`, `bg-[var(--amber)]`, etc.), mantendo a semântica high/mid/low. Cores saturadas não quebram no dark, mas alinhe à paleta para coerência.

- [ ] **Step 9: Verificar build e commit**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: sem erros.

```bash
git add web/frontend/app/gestor/performance/page.tsx web/frontend/components/AdThumb.tsx web/frontend/components/performance/FiltrosBar.tsx web/frontend/lib/roas-tier.ts
git commit -m "feat(gestor): criativos — estados ativos ciano, KPI herói, thumbs/scatter alinhados à marca"
```

---

## Task 7: TurboMax — sweep esmeralda `rgba(52,211,153,…)` → ciano/roxo

**Files:**
- Modify: `web/frontend/app/gestor/turbomax/page.tsx`

Contexto: `--forest` vira ciano, mas dezenas de glows/sombras/bordas usam `rgba(52,211,153,…)` (esmeralda) hardcoded e ficariam verdes. Trocar todos por ciano `rgba(0,200,255,…)`, com toques de roxo `rgba(123,47,255,…)` nos halos secundários. **Mantém o mesmo padrão de alpha** de cada ocorrência.

- [ ] **Step 1: Avatar do agente (raio) — glow**

Trocar:

```tsx
          boxShadow: pulsing
            ? "0 0 22px rgba(52,211,153,0.5), 0 0 40px rgba(52,211,153,0.15)"
            : "0 0 12px rgba(52,211,153,0.22)",
```

por:

```tsx
          boxShadow: pulsing
            ? "0 0 22px rgba(0,200,255,0.5), 0 0 40px rgba(123,47,255,0.15)"
            : "0 0 12px rgba(0,200,255,0.22)",
```

- [ ] **Step 2: Header brand badge (logo raio) — glow**

Trocar:

```tsx
                    boxShadow: loading
                      ? "0 0 28px rgba(52,211,153,0.55), 0 0 56px rgba(52,211,153,0.2)"
                      : "0 0 16px rgba(52,211,153,0.3)",
```

por:

```tsx
                    boxShadow: loading
                      ? "0 0 28px rgba(0,200,255,0.55), 0 0 56px rgba(123,47,255,0.2)"
                      : "0 0 16px rgba(0,200,255,0.3)",
```

- [ ] **Step 3: Thinking bubble — borda + glow**

Trocar:

```tsx
            borderColor: "rgba(52,211,153,0.18)",
            boxShadow: "0 0 24px rgba(52,211,153,0.06)",
```

por:

```tsx
            borderColor: "rgba(0,200,255,0.18)",
            boxShadow: "0 0 24px rgba(0,200,255,0.06)",
```

- [ ] **Step 4: Pílula "AI Agent" — borda + fundo**

Trocar:

```tsx
                      borderColor: "rgba(52,211,153,0.3)",
                      background: "rgba(52,211,153,0.07)",
```

por:

```tsx
                      borderColor: "rgba(0,200,255,0.3)",
                      background: "rgba(0,200,255,0.07)",
```

- [ ] **Step 5: Bolha do usuário — sombra**

Trocar:

```tsx
                      boxShadow: "0 2px 12px rgba(52,211,153,0.2)",
```

por:

```tsx
                      boxShadow: "0 2px 12px rgba(0,200,255,0.25)",
```

- [ ] **Step 6: Halo radial da área de mensagens**

Trocar:

```tsx
            background: "radial-gradient(ellipse at 50% 40%, rgba(52,211,153,0.09) 0%, transparent 60%), var(--paper)",
```

por:

```tsx
            background: "radial-gradient(ellipse at 50% 40%, rgba(0,200,255,0.10) 0%, transparent 60%), var(--paper)",
```

- [ ] **Step 7: Input wrapper — focus ring + borda de foco**

Trocar:

```tsx
              className="flex gap-3 rounded-2xl border p-2 transition-all duration-200 focus-within:shadow-[0_0_0_2px_rgba(52,211,153,0.1)]"
              style={{
                background: "var(--paper-deep)",
                borderColor: "var(--rule-soft)",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(52,211,153,0.35)")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "var(--rule-soft)")}
```

por:

```tsx
              className="flex gap-3 rounded-2xl border p-2 transition-all duration-200 focus-within:shadow-[0_0_0_2px_rgba(0,200,255,0.18)]"
              style={{
                background: "var(--paper-deep)",
                borderColor: "var(--rule-soft)",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(0,200,255,0.45)")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "var(--rule-soft)")}
```

- [ ] **Step 8: Watermark (raio gigante) — drop-shadow**

Trocar:

```tsx
                filter: "drop-shadow(0 0 40px rgba(52,211,153,0.3))",
```

por:

```tsx
                filter: "drop-shadow(0 0 40px rgba(0,200,255,0.3))",
```

- [ ] **Step 9: Indicador de status (dot) — bg-emerald/amber**

Trocar:

```tsx
                    className={`h-1.5 w-1.5 rounded-full ${loading ? "animate-pulse bg-amber-400" : "bg-emerald-400"}`}
```

por:

```tsx
                    className={`h-1.5 w-1.5 rounded-full ${loading ? "animate-pulse bg-[var(--amber)]" : "bg-[var(--forest)]"}`}
```

- [ ] **Step 10: Varredura final de esmeralda remanescente**

Run: `grep -n "52,211,153\|emerald" web/frontend/app/gestor/turbomax/page.tsx`
Expected: **sem matches**. Se restar algum, aplicar a mesma troca (ciano `0,200,255`; halos secundários roxo `123,47,255`).

- [ ] **Step 11: Verificar build e commit**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: sem erros.

```bash
git add web/frontend/app/gestor/turbomax/page.tsx
git commit -m "feat(gestor): turbomax — glows/sombras em ciano+roxo (substitui esmeralda do tema antigo)"
```

---

## Task 8: Inteligência — badges `bg-*-50` + `#f59e0b/#b45309` → tokens

**Files:**
- Modify: `web/frontend/app/gestor/inteligencia/page.tsx`

- [ ] **Step 1: Mapa de severidade (linhas 18-20)**

Trocar as 3 linhas do objeto de severidade:

```tsx
  critico:      { label: "Crítico",      dot: "bg-[var(--crimson)]", text: "text-[var(--crimson)]",  badge: "bg-red-50 text-[var(--crimson)]" },
  atencao:      { label: "Atenção",      dot: "bg-[#f59e0b]",        text: "text-[#f59e0b]",         badge: "bg-amber-50 text-[#b45309]" },
  oportunidade: { label: "Oportunidade", dot: "bg-[var(--forest)]",  text: "text-[var(--forest)]",   badge: "bg-green-50 text-[var(--forest)]" },
```

por:

```tsx
  critico:      { label: "Crítico",      dot: "bg-[var(--crimson)]", text: "text-[var(--crimson)]", badge: "border border-[var(--crimson)]/30 bg-[var(--crimson)]/15 text-[var(--crimson)]" },
  atencao:      { label: "Atenção",      dot: "bg-[var(--amber)]",   text: "text-[var(--amber)]",   badge: "border border-[var(--amber)]/30 bg-[var(--amber)]/15 text-[var(--amber)]" },
  oportunidade: { label: "Oportunidade", dot: "bg-[var(--forest)]",  text: "text-[var(--forest)]",  badge: "border border-[var(--forest)]/30 bg-[var(--forest)]/15 text-[var(--forest)]" },
```

- [ ] **Step 2: Pílulas de contagem (linhas 129, 134, 139)**

Trocar cada `<span>`:

```tsx
            <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-[var(--crimson)]">
```
→
```tsx
            <span className="rounded-full border border-[var(--crimson)]/30 bg-[var(--crimson)]/15 px-3 py-1 text-xs font-medium text-[var(--crimson)]">
```

```tsx
            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-[#b45309]">
```
→
```tsx
            <span className="rounded-full border border-[var(--amber)]/30 bg-[var(--amber)]/15 px-3 py-1 text-xs font-medium text-[var(--amber)]">
```

```tsx
            <span className="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-[var(--forest)]">
```
→
```tsx
            <span className="rounded-full border border-[var(--forest)]/30 bg-[var(--forest)]/15 px-3 py-1 text-xs font-medium text-[var(--forest)]">
```

- [ ] **Step 3: Varredura final**

Run: `grep -nE "#f59e0b|#b45309|bg-(red|amber|green|emerald|gray|slate)-(50|100)" web/frontend/app/gestor/inteligencia/page.tsx`
Expected: **sem matches**.

- [ ] **Step 4: Verificar build e commit**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: sem erros.

```bash
git add web/frontend/app/gestor/inteligencia/page.tsx
git commit -m "fix(gestor): inteligência — badges de severidade em tokens (sem bg-*-50 nem amber hardcoded)"
```

---

## Task 9: Admin + [slug] — KPI cards, badges, foco, scrim

**Files:**
- Modify: `web/frontend/app/gestor/[slug]/page.tsx`
- Modify: `web/frontend/app/gestor/admin/usuarios/page.tsx`
- Modify: `web/frontend/app/gestor/admin/historico/page.tsx`
- Modify: `web/frontend/app/gestor/admin/clickup-vinculos/page.tsx`

- [ ] **Step 1: `[slug]` — KPI cards com barra-gradiente (reuso de `.kpi-turbo`)**

Trocar a abertura do card:

```tsx
              <div key={kpi.label} className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-3">
```

por:

```tsx
              <div key={kpi.label} className="kpi-turbo relative overflow-hidden rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-3">
```

- [ ] **Step 2: `admin/usuarios` — badge "admin" vira pílula de marca**

Trocar:

```tsx
                    <span className="ml-2 text-xs text-[var(--amber)]">admin</span>
```

por:

```tsx
                    <span className="ml-2 rounded-full border border-[var(--forest)]/40 bg-[var(--forest)]/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-[var(--forest)]">admin</span>
```

- [ ] **Step 3: `admin/usuarios` — hover do item de gestor → glow ciano**

Trocar:

```tsx
              className="flex items-center justify-between rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3 transition hover:border-[var(--forest)]"
```

por:

```tsx
              className="flex items-center justify-between rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3 transition hover:border-[var(--forest)] hover:shadow-[0_0_18px_-6px_var(--forest)]"
```

- [ ] **Step 4: `admin/historico` — badge "inativo" com borda**

Trocar:

```tsx
                            <span className="rounded bg-[var(--paper-deep)] px-1.5 py-0.5 text-[9px] text-[var(--muted)]">
                              inativo
                            </span>
```

por:

```tsx
                            <span className="rounded border border-[var(--rule-soft)] bg-[var(--paper-deep)] px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-[var(--muted)]">
                              inativo
                            </span>
```

- [ ] **Step 5: `admin/clickup-vinculos` — scrim do modal em token**

Trocar:

```tsx
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
```

por:

```tsx
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#04040E]/80 p-6">
```

- [ ] **Step 6: (Opcional) reforço de foco ciano nos inputs admin/[slug]**

Onde houver `focus:ring-1 focus:ring-[var(--forest)]` (busca de clickup-vinculos, atribuir clientes em usuarios/[id], select de mês em [slug]), pode-se subir para `focus:ring-2 focus:ring-[var(--forest)] focus:border-[var(--forest)]`. O foco já vira ciano via token; este passo é só realce. Aplicar se quiser foco mais visível; caso contrário, pular sem prejuízo.

- [ ] **Step 7: Verificar build e commit**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: sem erros.

```bash
git add web/frontend/app/gestor/[slug]/page.tsx web/frontend/app/gestor/admin/
git commit -m "feat(gestor): admin/[slug] — KPI cards, badges de marca, hover/foco ciano e scrim em token"
```

---

## Task 10: Verificação visual consolidada

**Files:** nenhum (verificação).

- [ ] **Step 1: Build completo**

Run: `cd web/frontend && npm run build`
Expected: build conclui sem erros.

- [ ] **Step 2: Subir o stack local**

Backend: `cd web/backend && source .venv/bin/activate && uvicorn app:app --reload --port 8000` (ou o script do projeto).
Frontend: `cd web/frontend && npm run dev`.
Logar em `/gestor` (senha local `changeme`).

- [ ] **Step 3: Revisão por área (procurar "vazamento" de cor clara/creme)**

Conferir cada superfície — capturar screenshot:
1. **Shell/sidebar** — item ativo em ciano (faixa lateral + texto), hover, rodapé do usuário, links admin.
2. **Dashboard** — 6 KPI cards (barra-gradiente ciano→roxo + glow no hover); gráfico Faturamento×Investimento (ciano + âmbar legíveis); gráfico ROAS (degradê ciano→roxo, barras de baixo ROAS ainda visíveis); tabela.
3. **Reportes** — toggle Mensal/Semanal ativo (ciano, texto escuro); cards de cliente selecionados (realce ciano); checkbox ✓ (escuro sobre ciano); botões "Abrir report"/"Gerar N reports" (texto escuro legível); badges de status (pílulas).
4. **Configurações** — formulários, combobox GestorSelect (item ativo ciano), selects (seta visível), botões primários e "Desativar" (texto legível), foco ciano.
5. **Criativos** — KPI herói com glow; tabs de rede/view/chips ativos em ciano; miniaturas (sem par verde destoante); scatter.
6. **TurboMax** — todos os glows/halos em ciano/roxo (zero verde); foco do input ciano.
7. **Inteligência** — badges de severidade (sem fundo lavado).
8. **Admin/[slug]** — KPI cards, badges, hover, scrim do modal.

- [ ] **Step 4: Contraste**

Verificar legibilidade de `--muted`/`--ink-soft` sobre `--paper`, e ink escuro (`--on-accent`) sobre ciano/âmbar/crimson nos botões (alvo WCAG AA). Ajustar tom do token no `globals.css` se algo ficar fraco.

- [ ] **Step 5: Confirmar isolamento**

Abrir uma página `/cliente/*` (ou o report do cliente) e confirmar que **continua no tema original** (não foi afetada pelo escopo).

- [ ] **Step 6: Commit final (se houve ajuste de contraste)**

```bash
git add -A
git commit -m "chore(gestor): ajustes finais de contraste do tema dark Turbo"
```

---

## Self-Review (preenchido)

- **Cobertura da spec:** escopo `.gestor-turbo` (Task 1) ✓; cascade dos tokens ✓; polish de KPI/sidebar/charts/inputs (Tasks 2-9) ✓; risco de cor hardcoded — `#c0392b` (Task 5), `bg-*-50`/`#f59e0b` (Task 8), esmeralda (Task 7), `.select`/decorações `.dark` (Task 1) ✓; isolamento das páginas do cliente (Task 10 Step 5) ✓.
- **Itens além da spec original (descobertos na auditoria, incluídos):** override das decorações presas a `.dark`; padronização ink-on-accent; correção do mix do gráfico ROAS; sweep esmeralda do TurboMax. Registrados aqui para o revisor.
- **Consistência de tipos/tokens:** `--forest`=ciano, `--forest-deep`=roxo (usado em gradientes), `--forest-soft`=fundo ativo, `--on-accent`=ink sobre acento, `--gradient`, `--glow-cyan` — todos definidos na Task 1 e referenciados depois. `--purple` é alias de `--forest-deep` (mesmo valor) e só aparece via `--gradient`.
- **Sem placeholders:** todo passo de código traz o `old_string`/`new_string` concreto; os poucos passos "localize e troque" (Task 5 Step 6, Task 6 Steps 7-8) instruem re-leitura por haver múltiplas ocorrências variáveis.
