"use client";

import RevealOnView from "./RevealOnView";

type Kpi = {
  label: string;
  value: string;
  spark: number[];
  varPct: number | null;
};

type Props = { kpis: Kpi[] };

function MiniSpark({ values }: { values: number[] }) {
  if (values.length < 2) return <div className="h-6" />;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const w = 100;
  const h = 24;
  const step = w / (values.length - 1);
  const d = values
    .map((v, i) => {
      const x = i * step;
      const y = h - ((v - min) / range) * h * 0.8 - h * 0.1;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-6 w-full opacity-60" aria-hidden>
      <path d={d} fill="none" stroke="var(--forest)" strokeWidth="1.4" />
    </svg>
  );
}

export default function KpiRow({ kpis }: Props) {
  return (
    <RevealOnView className="mb-16">
      <div className="grid grid-cols-2 gap-y-6 gap-x-0 md:grid-cols-4">
        {kpis.map((k, i) => (
          <div
            key={k.label}
            className={`px-4 sm:px-6 ${i > 0 ? "md:border-l md:border-[var(--rule-soft)]" : ""}`}
          >
            <p className="eyebrow mb-1 text-[10px] text-[var(--muted)]">{k.label}</p>
            <p className="font-mono-num text-[22px] text-[var(--ink)] leading-tight">
              {k.value}
            </p>
            <div className="mt-3">
              <MiniSpark values={k.spark} />
            </div>
            {k.varPct != null && (
              <p
                className={`font-mono-num mt-1 text-[10px] ${
                  k.varPct >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"
                }`}
              >
                {k.varPct >= 0 ? "+" : ""}
                {k.varPct.toFixed(1)}% vs período anterior
              </p>
            )}
          </div>
        ))}
      </div>
    </RevealOnView>
  );
}
