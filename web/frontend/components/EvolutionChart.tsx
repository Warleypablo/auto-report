"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { PontoEvolucao } from "@/lib/types";

export function EvolutionChart({ pontos }: { pontos: PontoEvolucao[] }) {
  const data = pontos.map((p) => ({
    mes: new Date(p.periodo_fim).toLocaleDateString("pt-BR", {
      month: "short",
      year: "2-digit",
    }),
    faturamento: p.faturamento ? Number(p.faturamento) : null,
    roas: p.roas ? Number(p.roas) : null,
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
          <XAxis dataKey="mes" tick={{ fontSize: 12 }} />
          <YAxis
            tick={{ fontSize: 12 }}
            tickFormatter={(v: number) =>
              v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)
            }
          />
          <Tooltip
            formatter={(value) =>
              typeof value === "number"
                ? value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
                : String(value ?? "")
            }
            labelStyle={{ fontWeight: 600 }}
          />
          <Line
            type="monotone"
            dataKey="faturamento"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
