"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

const CATEGORIAS = [
  { value: "", label: "Todas categorias" },
  { value: "E-commerce", label: "E-commerce" },
  { value: "Lead Com Site", label: "Lead com site" },
  { value: "Lead Sem Site", label: "Lead sem site" },
];

const ORDENS = [
  { value: "faturamento", label: "Maior faturamento" },
  { value: "roas", label: "Maior ROAS" },
  { value: "crescimento", label: "Maior crescimento" },
];

export function Filters() {
  const router = useRouter();
  const sp = useSearchParams();
  const [, startTransition] = useTransition();

  function update(key: string, value: string) {
    const next = new URLSearchParams(sp.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    startTransition(() => {
      router.push(`?${next.toString()}#cases`);
    });
  }

  return (
    <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
      <Field label="Filtrar por" className="min-w-[180px]">
        <select
          defaultValue={sp.get("categoria") ?? ""}
          onChange={(e) => update("categoria", e.target.value)}
          className="select"
        >
          {CATEGORIAS.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Ordenar por" className="min-w-[180px]">
        <select
          defaultValue={sp.get("order_by") ?? "faturamento"}
          onChange={(e) => update("order_by", e.target.value)}
          className="select"
        >
          {ORDENS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </Field>

      <style>{`
        .select {
          background: transparent;
          border: 0;
          border-bottom: 1px solid var(--ink);
          padding: 4px 24px 6px 0;
          font-family: var(--font-fraunces), serif;
          font-size: 18px;
          color: var(--ink);
          letter-spacing: -0.01em;
          appearance: none;
          cursor: pointer;
          background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none'><path d='M1 1.5L6 6.5L11 1.5' stroke='%231A1916' stroke-width='1.4'/></svg>");
          background-repeat: no-repeat;
          background-position: right 0 center;
        }
        .select:focus {
          outline: none;
          border-bottom-color: var(--forest);
        }
      `}</style>
    </div>
  );
}

function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      <span className="eyebrow">{label}</span>
      {children}
    </label>
  );
}
