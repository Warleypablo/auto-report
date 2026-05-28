"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { gestorApi } from "@/lib/api-gestor";

type HistoryPoint = {
  mes: string;
  mesLabel: string;
  roas: number | null;
  cpm: number | null;
  investimento: number | null;
  faturamento: number | null;
};

type FadigaDiag =
  | { kind: "fadiga"; label: string }
  | { kind: "queda"; label: string }
  | { kind: "estavel"; label: string }
  | null;

const MES_ABBR: Record<string, string> = {
  "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
  "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
  "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
};

function deslocarMes(mes: string, delta: number): string {
  const ano = parseInt(mes.slice(0, 4), 10);
  const m = parseInt(mes.slice(5, 7), 10);
  const totalMeses = ano * 12 + (m - 1) + delta;
  const novoAno = Math.floor(totalMeses / 12);
  const novoMes = (totalMeses % 12) + 1;
  return `${novoAno}-${String(novoMes).padStart(2, "0")}`;
}

function fmtK(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `R$${(v / 1_000).toFixed(0)}k`;
  return `R$${v.toFixed(0)}`;
}

function detectFadiga(pts: HistoryPoint[]): FadigaDiag {
  const withRoas = pts.filter((p) => p.roas != null);
  if (withRoas.length < 3) return null;
  const last3 = withRoas.slice(-3);
  const decrescente = last3[0].roas! > last3[1].roas! && last3[1].roas! > last3[2].roas!;
  if (decrescente) return { kind: "fadiga", label: "⚠ ROAS caindo há 3 meses" };
  return { kind: "estavel", label: "ROAS estável" };
}

function EvolucaoTooltip({ active, payload }: { active?: boolean; payload?: { payload: HistoryPoint }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1.5 font-medium text-[var(--ink)]">{d.mesLabel}</p>
      <p style={{ color: "#34d399" }}>ROAS: {d.roas != null ? `${d.roas.toFixed(2)}×` : "—"}</p>
      <p style={{ color: "#f59e0b" }}>CPM: {d.cpm != null ? fmtK(d.cpm) : "—"}</p>
      <p className="text-[var(--muted)]">Faturamento: {fmtK(d.faturamento)}</p>
      <p className="text-[var(--muted)]">Investimento: {fmtK(d.investimento)}</p>
    </div>
  );
}

export type EvolucaoChartProps = {
  clienteSlug: string;
  adNome: string;
  adType: "meta" | "google";
  mes: string;
  mode?: "drawer" | "fullscreen";
};

export function EvolucaoChart({ clienteSlug, adNome, adType, mes, mode = "drawer" }: EvolucaoChartProps) {
  const [history, setHistory] = useState<HistoryPoint[] | null>(null);
  const [loading, setLoading] = useState(true);
  const chartHeight = mode === "fullscreen" ? 320 : 200;

  useEffect(() => {
    const meses = Array.from({ length: 6 }, (_, i) => deslocarMes(mes, -i)).reverse();
    Promise.all(
      meses.map((m) => gestorApi.metricasBreakdown(clienteSlug, m).catch(() => null)),
    )
      .then((results) => {
        const pts: HistoryPoint[] = meses.map((m, i) => {
          const bd = results[i];
          const ads = adType === "meta" ? bd?.meta_ads ?? [] : bd?.google_ads ?? [];
          const ad = ads.find((a) => a.nome === adNome) ?? null;
          const cpm =
            ad?.investimento && ad?.impressoes && ad.impressoes > 0
              ? (ad.investimento / ad.impressoes) * 1000
              : null;
          return {
            mes: m,
            mesLabel: MES_ABBR[m.slice(5, 7)] ?? m.slice(5, 7),
            roas: ad?.roas ?? null,
            cpm,
            investimento: ad?.investimento ?? null,
            faturamento: ad?.faturamento ?? null,
          };
        });
        setHistory(pts);
        setLoading(false);
      })
      .catch(() => {
        setHistory([]);
        setLoading(false);
      });
  }, [clienteSlug, adNome, adType, mes]);

  if (loading) {
    return (
      <div className="mt-6 space-y-3 px-1">
        <div
          className="animate-pulse rounded-xl bg-[var(--paper-deep)]"
          style={{ height: chartHeight - 20 }}
        />
        <div className="flex gap-2">
          {[78, 55, 90, 45, 70, 60].map((w, i) => (
            <div
              key={i}
              className="animate-pulse rounded bg-[var(--paper-deep)]"
              style={{ height: 4, width: `${w}px`, animationDelay: `${i * 80}ms` }}
            />
          ))}
        </div>
      </div>
    );
  }

  const hasAnyData = history?.some((p) => p.roas !== null) ?? false;

  if (!hasAnyData) {
    return (
      <div className="mt-10 text-center text-xs text-[var(--muted)]">
        Sem histórico disponível para este criativo.
      </div>
    );
  }

  const diagnosis = detectFadiga(history!);

  return (
    <div className="mt-4">
      {diagnosis && (
        <div
          className={`mb-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
            diagnosis.kind === "fadiga"
              ? "bg-amber-900/30 text-amber-300"
              : diagnosis.kind === "queda"
                ? "bg-red-900/30 text-red-300"
                : "bg-emerald-900/30 text-emerald-300"
          }`}
        >
          {diagnosis.label}
        </div>
      )}

      <ResponsiveContainer width="100%" height={chartHeight}>
        <ComposedChart data={history!} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="mesLabel" tick={{ fontSize: 9, fill: "#6b7280" }} axisLine={false} tickLine={false} />
          <YAxis
            yAxisId="ratio"
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v}×`}
          />
          <YAxis
            yAxisId="reais"
            orientation="right"
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => fmtK(v)}
          />
          <Bar yAxisId="reais" dataKey="faturamento" fill="#34d399" opacity={0.22} radius={[2, 2, 0, 0]} />
          <Bar yAxisId="reais" dataKey="investimento" fill="#6b7280" opacity={0.18} radius={[2, 2, 0, 0]} />
          <Line yAxisId="ratio" type="monotone" dataKey="roas" stroke="#34d399" strokeWidth={2} dot={{ r: 3, fill: "#34d399", strokeWidth: 0 }} connectNulls={false} />
          <Line yAxisId="reais" type="monotone" dataKey="cpm" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4 2" dot={{ r: 2, fill: "#f59e0b", strokeWidth: 0 }} connectNulls={false} />
          <Tooltip content={<EvolucaoTooltip />} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[9px] text-[var(--muted)]">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 rounded" style={{ background: "#34d399" }} />
          ROAS
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 border-t-2 border-dashed" style={{ borderColor: "#f59e0b" }} />
          CPM
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "#34d399", opacity: 0.5 }} />
          Fat.
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "#6b7280", opacity: 0.4 }} />
          Inv.
        </span>
      </div>
    </div>
  );
}
