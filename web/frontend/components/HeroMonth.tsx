"use client";

import Counter from "./Counter";
import RevealOnView from "./RevealOnView";

type TimelinePoint = { mes: string; faturamento: number | null };

type Props = {
  mesLabel: string;
  faturamento: number | null;
  roas: number | null;
  varFaturamento: number | null;
  varRoas: number | null;
  timeline12m: TimelinePoint[];
};

const fmtBRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtRoas = (v: number) => `${v.toFixed(2).replace(".", ",")}×`;
const fmtPct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

function buildSparkPath(points: number[], w = 1200, h = 240): string {
  if (points.length < 2) return "";
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const step = w / (points.length - 1);
  return points
    .map((v, i) => {
      const x = i * step;
      const y = h - ((v - min) / range) * h * 0.8 - h * 0.1;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export default function HeroMonth({
  mesLabel, faturamento, roas, varFaturamento, varRoas, timeline12m,
}: Props) {
  const sparkPts = timeline12m.map((p) => p.faturamento ?? 0).filter((_, i, a) => a.length >= 3);
  const sparkPath = sparkPts.length >= 3 ? buildSparkPath(sparkPts) : "";

  return (
    <section className="relative mb-16 min-h-[50vh]">
      {sparkPath && (
        <svg
          viewBox="0 0 1200 240"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-[60%] w-full opacity-[0.12]"
          aria-hidden
        >
          <path d={sparkPath} fill="none" stroke="var(--forest)" strokeWidth="2" />
        </svg>
      )}

      <RevealOnView className="relative">
        <p className="eyebrow mb-2 text-xs text-[var(--muted)]">Faturamento · {mesLabel}</p>
        <h2 className="font-display font-light italic leading-none tracking-tight text-[var(--ink)] text-[64px] sm:text-[88px] lg:text-[128px]">
          {faturamento != null ? (
            <Counter to={faturamento} format={(v) => fmtBRL(v)} />
          ) : (
            "—"
          )}
        </h2>
        {varFaturamento != null && (
          <p className="font-mono-num mt-3 text-xs text-[var(--muted)]">
            <span className={varFaturamento >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}>
              {varFaturamento >= 0 ? "↗" : "↘"} {fmtPct(varFaturamento)}
            </span>{" "}
            vs. mês anterior
          </p>
        )}
      </RevealOnView>

      <RevealOnView delay={0.15} className="relative mt-12">
        <p className="eyebrow mb-2 text-xs text-[var(--muted)]">ROAS · {mesLabel}</p>
        <h3 className="font-display font-light italic leading-none tracking-tight text-[var(--forest)] text-[44px] sm:text-[64px] lg:text-[88px]">
          {roas != null ? <Counter to={roas} format={(v) => fmtRoas(v)} /> : "—"}
        </h3>
        {varRoas != null && (
          <p className="font-mono-num mt-3 text-xs text-[var(--muted)]">
            <span className={varRoas >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}>
              {varRoas >= 0 ? "↗" : "↘"} {fmtPct(varRoas)}
            </span>{" "}
            vs. mês anterior
          </p>
        )}
      </RevealOnView>
    </section>
  );
}
