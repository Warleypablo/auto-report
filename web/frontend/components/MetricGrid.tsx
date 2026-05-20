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
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {METRICS.filter((m) => snapshot[m.key] != null).map((m) => (
        <div
          key={m.key as string}
          className="rounded-lg border border-neutral-200 bg-white p-5"
        >
          <p className="text-xs uppercase tracking-wider text-neutral-500">{m.label}</p>
          <p className="mt-1 text-2xl font-bold text-neutral-900">
            {m.format(snapshot[m.key] as string | number | null | undefined)}
          </p>
          {m.variation && snapshot[m.variation] != null && (
            <p className="mt-1 text-sm font-medium text-emerald-600">
              {formatPct(snapshot[m.variation] as string)}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
