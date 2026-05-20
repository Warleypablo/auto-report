"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
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
    <div className="h-80 w-full">
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
          <defs>
            <linearGradient id="fatFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1F4D3C" stopOpacity={0.32} />
              <stop offset="100%" stopColor="#1F4D3C" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#C9C2AF" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="mes"
            tick={{
              fontSize: 11,
              fill: "#6F6A60",
              fontFamily: "var(--font-geist)",
            }}
            tickLine={false}
            axisLine={{ stroke: "#1A1916", strokeWidth: 1 }}
            tickMargin={10}
          />
          <YAxis
            tick={{
              fontSize: 11,
              fill: "#6F6A60",
              fontFamily: "var(--font-jetbrains)",
            }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => {
              if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1)}M`;
              if (v >= 1000) return `R$ ${(v / 1000).toFixed(0)}k`;
              return `R$ ${v}`;
            }}
            width={80}
          />
          <Tooltip
            cursor={{ stroke: "#1F4D3C", strokeWidth: 1, strokeDasharray: "4 2" }}
            contentStyle={{
              background: "#111110",
              border: "none",
              borderRadius: 0,
              color: "#F2EEE5",
              fontFamily: "var(--font-jetbrains)",
              fontSize: 12,
              padding: "10px 14px",
            }}
            labelStyle={{
              color: "#D7C68C",
              textTransform: "uppercase",
              letterSpacing: "0.15em",
              fontSize: 10,
              marginBottom: 6,
            }}
            formatter={(value) =>
              typeof value === "number"
                ? [
                    value.toLocaleString("pt-BR", {
                      style: "currency",
                      currency: "BRL",
                      maximumFractionDigits: 0,
                    }),
                    "Faturamento",
                  ]
                : [String(value ?? ""), ""]
            }
          />
          <Area
            type="monotone"
            dataKey="faturamento"
            stroke="#1F4D3C"
            strokeWidth={2}
            fill="url(#fatFill)"
            dot={{ r: 3, fill: "#1F4D3C", strokeWidth: 0 }}
            activeDot={{ r: 6, fill: "#1F4D3C", stroke: "#F2EEE5", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
