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
