import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import type { AdContext } from "../useAdContext";

type RankedAd = (MetaAd | GoogleAd) & { rank: number };

const MEDAL = ["🥇", "🥈", "🥉"];

const TIER_BAR: Record<string, string> = {
  alto: "bg-emerald-400",
  medio: "bg-amber-400",
  baixo: "bg-red-400",
  neutro: "bg-zinc-500",
};

const TIER_TEXT: Record<string, string> = {
  alto: "text-emerald-400",
  medio: "text-amber-400",
  baixo: "text-red-400",
  neutro: "text-zinc-400",
};

function fmtRoas(roas: number | null): string {
  if (roas == null) return "—";
  return `${roas.toFixed(2)}×`;
}

function fmtK(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `R$${(v / 1_000).toFixed(0)}k`;
  return `R$${v.toFixed(0)}`;
}

export type KpiHeaderProps = {
  ad: RankedAd;
  ctx: AdContext;
  totalAdsComRoas: number;
  mode: "drawer" | "fullscreen";
};

export function KpiHeader({ ad, ctx, totalAdsComRoas, mode }: KpiHeaderProps) {
  if (mode === "drawer") {
    return (
      <div className="mb-5 flex items-center gap-3">
        {ad.rank < 3 && <span className="text-2xl">{MEDAL[ad.rank]}</span>}
        {ad.rank >= 3 && <span className="font-mono-num text-sm text-[var(--muted)]">#{ad.rank + 1}</span>}
        <div className="flex-1 min-w-0">
          <div className="mb-1 flex items-center justify-between">
            <span className={`font-mono-num text-lg font-semibold ${TIER_TEXT[ctx.tier]}`}>
              {fmtRoas(ad.roas)}
            </span>
            <span className="text-[10px] text-[var(--muted)]">{totalAdsComRoas} criativos</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
            <div className={`h-1.5 rounded-full ${TIER_BAR[ctx.tier]}`} style={{ width: `${ctx.barPct}%` }} />
          </div>
        </div>
      </div>
    );
  }

  // mode === "fullscreen"
  return (
    <div className="mb-8">
      <div className="mb-3 flex items-baseline gap-6">
        {ad.rank < 3 && <span className="text-4xl">{MEDAL[ad.rank]}</span>}
        {ad.rank >= 3 && <span className="font-mono-num text-2xl text-[var(--muted)]">#{ad.rank + 1}</span>}
        <span className={`font-mono-num text-5xl font-semibold ${TIER_TEXT[ctx.tier]}`}>
          {fmtRoas(ad.roas)}
        </span>
        <div className="flex flex-wrap gap-6 text-sm">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Faturamento</p>
            <p className="font-mono-num text-lg text-[var(--forest)]">{fmtK(ad.faturamento)}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Investimento</p>
            <p className="font-mono-num text-lg text-[var(--ink)]">{fmtK(ad.investimento)}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">CPM</p>
            <p className="font-mono-num text-lg text-[var(--ink)]">{fmtK(ctx.cpm)}</p>
          </div>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
        <div className={`h-1.5 rounded-full ${TIER_BAR[ctx.tier]}`} style={{ width: `${ctx.barPct}%` }} />
      </div>
    </div>
  );
}
