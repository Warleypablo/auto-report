"use client";

import { useMemo, useState } from "react";

import type { ClienteListItem } from "@/lib/types";
import { formatBRL, formatInt, formatPct, formatRoas } from "@/lib/format";

type SortKey =
  | "nome"
  | "categoria"
  | "setor"
  | "porte"
  | "faturamento"
  | "investimento"
  | "roas"
  | "cpa"
  | "leads"
  | "vendas"
  | "faturamento_var_pct"
  | "publicar_vitrine";

type SortDir = "asc" | "desc";

type ColumnDef = {
  key: SortKey;
  label: string;
  align?: "left" | "right";
  width?: string;
  format: (item: ClienteListItem) => React.ReactNode;
  sortValue: (item: ClienteListItem) => number | string | null;
  className?: string;
};

function num(v: string | number | null | undefined): number | null {
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

const COLUMNS: ColumnDef[] = [
  {
    key: "nome",
    label: "Cliente",
    align: "left",
    format: (i) => (
      <span className="flex items-baseline gap-3">
        {i.destaque && (
          <span
            className="font-mono-num text-[9px] uppercase tracking-[0.18em] text-[var(--amber)]"
            title="Destaque na vitrine"
          >
            ★
          </span>
        )}
        <span className="font-display text-base text-[var(--ink)]">{i.nome}</span>
      </span>
    ),
    sortValue: (i) => i.nome.toLowerCase(),
  },
  {
    key: "categoria",
    label: "Categoria",
    align: "left",
    format: (i) => <span className="text-[var(--ink-soft)]">{i.categoria}</span>,
    sortValue: (i) => i.categoria,
  },
  {
    key: "setor",
    label: "Setor",
    align: "left",
    format: (i) => <span className="text-[var(--ink-soft)]">{i.setor ?? "—"}</span>,
    sortValue: (i) => i.setor ?? "",
  },
  {
    key: "porte",
    label: "Porte",
    align: "left",
    format: (i) => <span className="text-[var(--ink-soft)]">{i.porte ?? "—"}</span>,
    sortValue: (i) => i.porte ?? "",
  },
  {
    key: "faturamento",
    label: "Faturamento",
    align: "right",
    className: "font-mono-num",
    format: (i) => formatBRL(i.faturamento),
    sortValue: (i) => num(i.faturamento),
  },
  {
    key: "investimento",
    label: "Investimento",
    align: "right",
    className: "font-mono-num",
    format: (i) => formatBRL(i.investimento),
    sortValue: (i) => num(i.investimento),
  },
  {
    key: "roas",
    label: "ROAS",
    align: "right",
    className: "font-mono-num",
    format: (i) => formatRoas(i.roas),
    sortValue: (i) => num(i.roas),
  },
  {
    key: "cpa",
    label: "CPA / CPL",
    align: "right",
    className: "font-mono-num",
    format: (i) => formatBRL(i.cpa),
    sortValue: (i) => num(i.cpa),
  },
  {
    key: "leads",
    label: "Leads",
    align: "right",
    className: "font-mono-num",
    format: (i) => formatInt(i.leads),
    sortValue: (i) => i.leads,
  },
  {
    key: "vendas",
    label: "Vendas",
    align: "right",
    className: "font-mono-num",
    format: (i) => formatInt(i.vendas),
    sortValue: (i) => i.vendas,
  },
  {
    key: "faturamento_var_pct",
    label: "Crescimento",
    align: "right",
    className: "font-mono-num",
    format: (i) =>
      i.faturamento_var_pct != null ? (
        <span
          className={
            num(i.faturamento_var_pct)! >= 0
              ? "text-[var(--forest)]"
              : "text-[var(--crimson)]"
          }
        >
          {num(i.faturamento_var_pct)! >= 0 ? "↗" : "↘"} {formatPct(i.faturamento_var_pct)}
        </span>
      ) : (
        "—"
      ),
    sortValue: (i) => num(i.faturamento_var_pct),
  },
  {
    key: "publicar_vitrine",
    label: "Vitrine",
    align: "left",
    format: (i) =>
      i.publicar_vitrine ? (
        <span className="inline-flex items-center gap-1.5 text-xs">
          <span className="block h-1.5 w-1.5 rounded-full bg-[var(--forest)]" />
          Pública
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--muted)]">
          <span className="block h-1.5 w-1.5 rounded-full bg-[var(--amber)]" />
          Privada
        </span>
      ),
    sortValue: (i) => (i.publicar_vitrine ? 1 : 0),
  },
];

const CATEGORIAS = ["Todas", "E-commerce", "Lead Com Site", "Lead Sem Site"];
const VITRINES = ["Todos", "Pública", "Privada"];

export function ClientesTable({ items }: { items: ClienteListItem[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("faturamento");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [query, setQuery] = useState("");
  const [categoria, setCategoria] = useState("Todas");
  const [setor, setSetor] = useState("Todos");
  const [vitrine, setVitrine] = useState("Todos");

  const setores = useMemo(() => {
    const s = new Set(items.map((i) => i.setor).filter(Boolean) as string[]);
    return ["Todos", ...Array.from(s).sort()];
  }, [items]);

  const filtered = useMemo(() => {
    return items.filter((i) => {
      if (query && !i.nome.toLowerCase().includes(query.toLowerCase())) return false;
      if (categoria !== "Todas" && i.categoria !== categoria) return false;
      if (setor !== "Todos" && i.setor !== setor) return false;
      if (vitrine === "Pública" && !i.publicar_vitrine) return false;
      if (vitrine === "Privada" && i.publicar_vitrine) return false;
      return true;
    });
  }, [items, query, categoria, setor, vitrine]);

  const sorted = useMemo(() => {
    const col = COLUMNS.find((c) => c.key === sortKey)!;
    const sgn = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const va = col.sortValue(a);
      const vb = col.sortValue(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1; // null sempre no fim
      if (vb == null) return -1;
      if (typeof va === "number" && typeof vb === "number") return (va - vb) * sgn;
      return String(va).localeCompare(String(vb), "pt-BR") * sgn;
    });
  }, [filtered, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      // numéricos começam desc, texto começa asc
      const col = COLUMNS.find((c) => c.key === key)!;
      const first = items.find((i) => col.sortValue(i) != null);
      const isNum = first != null && typeof col.sortValue(first) === "number";
      setSortDir(isNum ? "desc" : "asc");
    }
  }

  const stats = useMemo(() => {
    const totalFat = sorted.reduce((acc, i) => acc + (num(i.faturamento) ?? 0), 0);
    const totalInv = sorted.reduce((acc, i) => acc + (num(i.investimento) ?? 0), 0);
    const totalLeads = sorted.reduce((acc, i) => acc + (i.leads ?? 0), 0);
    return { n: sorted.length, totalFat, totalInv, totalLeads };
  }, [sorted]);

  return (
    <div>
      {/* Filtros */}
      <div className="border-y border-[var(--rule)] bg-[var(--paper-soft)]/40 px-6 py-5">
        <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
          <Field label="Buscar por nome">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ex: Atlas, fashion..."
              className="border-0 border-b border-[var(--ink)] bg-transparent py-1 font-display text-lg text-[var(--ink)] placeholder:text-[var(--muted)]/60 focus:border-[var(--forest)] focus:outline-none"
            />
          </Field>
          <Field label="Categoria">
            <Select value={categoria} onChange={setCategoria} options={CATEGORIAS} />
          </Field>
          <Field label="Setor">
            <Select value={setor} onChange={setSetor} options={setores} />
          </Field>
          <Field label="Vitrine">
            <Select value={vitrine} onChange={setVitrine} options={VITRINES} />
          </Field>

          <button
            type="button"
            onClick={() => {
              setQuery("");
              setCategoria("Todas");
              setSetor("Todos");
              setVitrine("Todos");
            }}
            className="ml-auto self-end text-xs text-[var(--muted)] underline decoration-[var(--rule-soft)] underline-offset-4 hover:text-[var(--ink)] hover:decoration-[var(--ink)]"
          >
            Limpar filtros
          </button>
        </div>
      </div>

      {/* Tabela */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b-2 border-[var(--ink)]">
              <th className="px-4 py-3 text-left font-mono-num text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">
                #
              </th>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 text-${col.align ?? "left"} eyebrow cursor-pointer select-none hover:text-[var(--ink)]`}
                  onClick={() => handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    <span
                      className={`text-[var(--ink)] transition-opacity ${
                        sortKey === col.key ? "opacity-100" : "opacity-20"
                      }`}
                    >
                      {sortKey === col.key ? (sortDir === "asc" ? "↑" : "↓") : "↕"}
                    </span>
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td
                  colSpan={COLUMNS.length + 1}
                  className="px-4 py-12 text-center font-display text-xl text-[var(--muted)]"
                >
                  Nenhum cliente encontrado.
                </td>
              </tr>
            ) : (
              sorted.map((item, idx) => (
                <tr
                  key={item.slug}
                  className={`group border-b border-[var(--rule-soft)] transition-colors hover:bg-[var(--paper-soft)] ${
                    !item.publicar_vitrine ? "bg-[var(--paper-soft)]/40" : ""
                  }`}
                >
                  <td className="px-4 py-3 font-mono-num text-[11px] text-[var(--muted)]">
                    {String(idx + 1).padStart(2, "0")}
                  </td>
                  {COLUMNS.map((col) => (
                    <td
                      key={col.key}
                      className={`px-4 py-3 text-${col.align ?? "left"} ${col.className ?? ""} text-[var(--ink)]`}
                    >
                      {col.format(item)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
          {sorted.length > 0 && (
            <tfoot>
              <tr className="border-t-2 border-[var(--ink)] bg-[var(--paper-soft)]">
                <td colSpan={4} className="px-4 py-3">
                  <span className="eyebrow">Totais — {stats.n} {stats.n === 1 ? "cliente" : "clientes"}</span>
                </td>
                <td className="px-4 py-3 text-right font-mono-num font-medium text-[var(--ink)]">
                  {formatBRL(stats.totalFat)}
                </td>
                <td className="px-4 py-3 text-right font-mono-num font-medium text-[var(--ink)]">
                  {formatBRL(stats.totalInv)}
                </td>
                <td colSpan={2} />
                <td className="px-4 py-3 text-right font-mono-num font-medium text-[var(--ink)]">
                  {formatInt(stats.totalLeads)}
                </td>
                <td colSpan={3} />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="eyebrow">{label}</span>
      {children}
    </label>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="cursor-pointer appearance-none border-0 border-b border-[var(--ink)] bg-transparent py-1 pr-6 font-display text-lg text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none"
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none'><path d='M1 1.5L6 6.5L11 1.5' stroke='%231A1916' stroke-width='1.4'/></svg>\")",
        backgroundRepeat: "no-repeat",
        backgroundPosition: "right 0 center",
      }}
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
