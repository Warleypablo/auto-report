"use client";

import {
  CATEGORIA_CHIPS,
  CATEGORIA_LABELS,
  PRESETS_DATA,
  PRESET_LABELS,
  type CategoriaChave,
  type FaixaScope,
  type FiltrosState,
  type OrderBy,
} from "@/lib/criativos-filtros";

const SELECT =
  "rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-xs text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none";
const INPUT =
  "w-24 rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-2 py-2 text-xs text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none";

export type GestorOpt = { value: string; label: string };
export type ClienteOpt = { slug: string; nome: string };

type Props = {
  state: FiltrosState;
  onChange: (next: FiltrosState) => void;
  gestores: GestorOpt[];
  clientes: ClienteOpt[];
};

export function FiltrosBar({ state, onChange, gestores, clientes }: Props) {
  const set = (patch: Partial<FiltrosState>) => onChange({ ...state, ...patch });

  function aplicarPreset(key: string) {
    const fn = PRESETS_DATA[key];
    if (!fn) return;
    const { de, ate } = fn();
    set({ de, ate });
  }

  function toggleChip(c: CategoriaChave) {
    const has = state.categorias.includes(c);
    set({
      categorias: has
        ? state.categorias.filter((x) => x !== c)
        : [...state.categorias, c],
    });
  }

  return (
    <div className="mb-6 flex flex-col gap-3">
      {/* Date range + presets */}
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-[var(--muted)]">
          De
          <input
            aria-label="Data inicial"
            type="date"
            value={state.de}
            onChange={(e) => set({ de: e.target.value })}
            className={SELECT}
          />
        </label>
        <label className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-[var(--muted)]">
          Até
          <input
            aria-label="Data final"
            type="date"
            value={state.ate}
            onChange={(e) => set({ ate: e.target.value })}
            className={SELECT}
          />
        </label>
        <div className="flex flex-wrap gap-1">
          {PRESET_LABELS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => aplicarPreset(key)}
              className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-2.5 py-1.5 text-[10px] text-[var(--muted)] transition hover:text-[var(--ink)]"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Chips de categoria */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[10px] uppercase tracking-widest text-[var(--muted)]">
          Categoria
        </span>
        {CATEGORIA_CHIPS.map((c) => {
          const active = state.categorias.includes(c);
          return (
            <button
              key={c}
              type="button"
              aria-pressed={active}
              onClick={() => toggleChip(c)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                active
                  ? "bg-[var(--forest)] text-[var(--on-accent)] shadow-[0_0_14px_-4px_var(--forest)]"
                  : "bg-[var(--paper-soft)] text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              {CATEGORIA_LABELS[c]}
            </button>
          );
        })}
      </div>

      {/* Faixas + scope + selects */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1">
          <span className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Faixa</span>
          {(["criativo", "cliente"] as FaixaScope[]).map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={state.faixaScope === s}
              onClick={() => set({ faixaScope: s })}
              className={`rounded-md px-2.5 py-1.5 text-[10px] font-medium transition ${
                state.faixaScope === s
                  ? "bg-[var(--paper-deep)] text-[var(--forest)] ring-1 ring-[var(--forest)]/25"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              {s === "criativo" ? "Por criativo" : "Por cliente"}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Fat.</span>
          <input
            aria-label="Faturamento mínimo"
            type="number"
            placeholder="min"
            value={state.fatMin}
            onChange={(e) => set({ fatMin: e.target.value })}
            className={INPUT}
          />
          <input
            aria-label="Faturamento máximo"
            type="number"
            placeholder="max"
            value={state.fatMax}
            onChange={(e) => set({ fatMax: e.target.value })}
            className={INPUT}
          />
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Inv.</span>
          <input
            aria-label="Investimento mínimo"
            type="number"
            placeholder="min"
            value={state.invMin}
            onChange={(e) => set({ invMin: e.target.value })}
            className={INPUT}
          />
          <input
            aria-label="Investimento máximo"
            type="number"
            placeholder="max"
            value={state.invMax}
            onChange={(e) => set({ invMax: e.target.value })}
            className={INPUT}
          />
        </div>

        {gestores.length > 0 && (
          <select
            aria-label="Gestor"
            value={state.gestor}
            onChange={(e) => set({ gestor: e.target.value, cliente: "" })}
            className={SELECT}
          >
            <option value="">Todos os gestores</option>
            {gestores.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        )}

        {clientes.length > 0 && (
          <select
            aria-label="Cliente"
            value={state.cliente}
            onChange={(e) => set({ cliente: e.target.value })}
            className={SELECT}
          >
            <option value="">Todos os clientes</option>
            {clientes.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.nome}
              </option>
            ))}
          </select>
        )}

        <select
          aria-label="Ordenar por"
          value={state.orderBy}
          onChange={(e) => set({ orderBy: e.target.value as OrderBy })}
          className={SELECT}
        >
          <option value="roas">Ordenar: ROAS</option>
          <option value="faturamento">Ordenar: Faturamento</option>
          <option value="investimento">Ordenar: Investimento</option>
        </select>
      </div>
    </div>
  );
}
