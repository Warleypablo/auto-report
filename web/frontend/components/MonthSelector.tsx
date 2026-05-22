"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { labelMes } from "@/lib/mes-utils";

type Props = {
  available: Array<{ mes: string; com_snapshot: number }>;
  selected: string;
  recentes: string[];
};

export default function MonthSelector({ available, selected, recentes }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const known = useMemo(() => new Map(available.map((p) => [p.mes, p.com_snapshot])), [available]);

  function pickMes(mes: string) {
    const next = new URLSearchParams(searchParams);
    next.set("mes", mes);
    router.push(`?${next.toString()}`);
  }

  return (
    <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
      <div className="flex items-center justify-between">
        <p className="eyebrow">Período</p>
        <p className="text-xs text-[var(--muted)]">
          {known.get(selected) ?? 0} snapshot(s) para{" "}
          <span className="font-mono-num text-[var(--ink-soft)]">{labelMes(selected)}</span>
        </p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {recentes.map((mes) => {
          const n = known.get(mes) ?? 0;
          const ativo = mes === selected;
          return (
            <button
              key={mes}
              type="button"
              onClick={() => pickMes(mes)}
              className={[
                "rounded-full border px-3 py-1 text-xs transition",
                ativo
                  ? "border-[var(--ink)] bg-[var(--ink)] text-[var(--paper)]"
                  : "border-[var(--rule-soft)] text-[var(--ink-soft)] hover:border-[var(--ink-soft)] hover:text-[var(--ink)]",
                n === 0 && !ativo ? "opacity-50" : "",
              ].join(" ")}
              title={`${n} snapshot(s)`}
            >
              <span>{labelMes(mes)}</span>
              <span className="font-mono-num ml-2 text-[10px] opacity-70">{n}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export { labelMes } from "@/lib/mes-utils";
