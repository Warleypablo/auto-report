import { formatBRL, formatInt, formatPct, formatRoas } from "@/lib/format";
import type { CaseDetail } from "@/lib/types";

type MetricDef = {
  key: keyof CaseDetail;
  label: string;
  format: (v: string | number | null | undefined) => string;
  variation?: keyof CaseDetail;
};

const METRICS: MetricDef[] = [
  { key: "faturamento", label: "Faturamento", format: formatBRL, variation: "faturamento_var_pct" },
  { key: "investimento", label: "Investimento", format: formatBRL },
  { key: "roas", label: "ROAS", format: formatRoas, variation: "roas_var_pct" },
  { key: "cpa", label: "CPA", format: formatBRL },
  { key: "vendas", label: "Vendas", format: formatInt },
  { key: "leads", label: "Leads", format: formatInt },
];

export function MetricGrid({ snapshot }: { snapshot: CaseDetail }) {
  const visible = METRICS.filter((m) => snapshot[m.key] != null);

  return (
    <div className="grid gap-px bg-[var(--rule-soft)] sm:grid-cols-2 lg:grid-cols-3">
      {visible.map((m, i) => (
        <div key={m.key as string} className="bg-[var(--paper-soft)] p-7">
          <div className="flex items-center justify-between">
            <p className="eyebrow">{m.label}</p>
            <span className="font-mono-num text-[10px] text-[var(--muted)]">
              {String(i + 1).padStart(2, "0")}
            </span>
          </div>
          <p className="font-mono-num mt-4 text-[2.5rem] font-medium leading-none tracking-tight text-[var(--ink)]">
            {m.format(snapshot[m.key] as string | number | null | undefined)}
          </p>
          {m.variation && snapshot[m.variation] != null && (
            <p className="font-mono-num mt-3 text-xs text-[var(--forest)]">
              ↗ {formatPct(snapshot[m.variation] as string)} vs período anterior
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
