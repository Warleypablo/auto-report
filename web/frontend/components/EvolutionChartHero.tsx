"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import MetricToggle from "./MetricToggle";
import RevealOnView from "./RevealOnView";

type Point = {
  mes: string;
  faturamento: number | null;
  roas: number | null;
  investimento: number | null;
};

type Metric = "faturamento" | "roas" | "investimento";

const LABELS: Record<Metric, string> = {
  faturamento: "Faturamento",
  roas: "ROAS",
  investimento: "Investimento",
};

const NOMES_MES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const mesLabel = (mes: string) => {
  const [a, m] = mes.split("-");
  return `${NOMES_MES[parseInt(m) - 1]} ${a.slice(2)}`;
};

const fmtBRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtRoas = (v: number) => `${v.toFixed(2).replace(".", ",")}×`;

function tooltipContent(metric: Metric) {
  return ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const p = payload[0];
    const raw = p.value as number;
    const v = metric === "roas" ? fmtRoas(raw) : fmtBRL(raw);
    return (
      <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-xs shadow-sm">
        <p className="text-[var(--muted)]">{p.payload.mes}</p>
        <p className="font-mono-num text-[var(--ink)]">{v}</p>
      </div>
    );
  };
}

type Props = { timeline: Point[] };

export default function EvolutionChartHero({ timeline }: Props) {
  const [metric, setMetric] = useState<Metric>("faturamento");

  if (timeline.length < 2) return null;

  const data = timeline.map((p) => ({
    mes: mesLabel(p.mes),
    value: p[metric] ?? 0,
  }));

  return (
    <RevealOnView className="mb-16">
      <div className="mb-4 flex items-center justify-between">
        <p className="eyebrow text-xs text-[var(--muted)]">
          Evolução · últimos {timeline.length} meses
        </p>
        <MetricToggle
          options={[
            { value: "faturamento", label: LABELS.faturamento },
            { value: "roas", label: LABELS.roas },
            { value: "investimento", label: LABELS.investimento },
          ]}
          value={metric}
          onChange={setMetric}
        />
      </div>

      <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
        <ResponsiveContainer width="100%" height={360}>
          <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="evo-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--forest)" stopOpacity={0.25} />
                <stop offset="100%" stopColor="var(--forest)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--rule-soft)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="mes"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              tickFormatter={(v) => (metric === "roas" ? `${v}×` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
              axisLine={false}
              tickLine={false}
              width={50}
            />
            <Tooltip content={tooltipContent(metric)} cursor={{ stroke: "var(--rule-soft)" }} />
            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--forest)"
              strokeWidth={1.8}
              fill="url(#evo-fill)"
              isAnimationActive
              animationDuration={1200}
              animationEasing="ease-out"
              dot={{ r: 3, fill: "var(--forest)" }}
              activeDot={{ r: 5 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </RevealOnView>
  );
}
