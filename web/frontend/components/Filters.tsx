"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

const CATEGORIAS = ["", "E-commerce", "Lead Com Site", "Lead Sem Site"];
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
      router.push(`?${next.toString()}`);
    });
  }

  return (
    <div className="mb-8 flex flex-wrap items-center gap-3">
      <select
        defaultValue={sp.get("categoria") ?? ""}
        onChange={(e) => update("categoria", e.target.value)}
        className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-900 focus:outline-none"
      >
        {CATEGORIAS.map((c) => (
          <option key={c} value={c}>
            {c || "Todas as categorias"}
          </option>
        ))}
      </select>

      <select
        defaultValue={sp.get("order_by") ?? "faturamento"}
        onChange={(e) => update("order_by", e.target.value)}
        className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-900 focus:outline-none"
      >
        {ORDENS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
